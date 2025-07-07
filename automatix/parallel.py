import argparse
import pickle
import subprocess
from dataclasses import dataclass, field
from os import listdir, unlink
from os.path import isfile
from pathlib import Path
from time import sleep, strftime, gmtime

from .batch_runner import run_automatix_list
from .colors import yellow, green, red, cyan
from .config import LOG, init_logger, CONFIG
from .helpers import FileWithLock
from .progress_bar import setup_scroll_area, destroy_scroll_area

STATUS_TEMPLATE = 'waiting: {w}, running: {r}, user input required: {u}, finished: {f}'


@dataclass
class Autos:
    status_file: str
    time_id: int
    count: int
    tempdir: str

    max_parallel: int = 2
    waiting: list = field(default_factory=list)
    running: list = field(default_factory=list)
    user_input: list = field(default_factory=list)
    finished: list = field(default_factory=list)


def get_logfile_dir(time_id: int, scriptfile: str) -> str:
    human_readable_time = strftime('%Y-%m-%d_%H-%M-%S_UTC', gmtime(time_id))
    return f'{CONFIG.get("logfile_dir")}/{human_readable_time}__{Path(scriptfile).stem}'


def get_files(tempdir: str) -> set:
    return {f for f in listdir(tempdir) if isfile(f'{tempdir}/{f}') and f.startswith('auto')}


def print_status(autos: Autos):
    print(STATUS_TEMPLATE.format(
        w=yellow(len(autos.waiting)),
        r=cyan(len(autos.running)),
        u=red(len(autos.user_input)),
        f=green(f'{len(autos.finished)}/{autos.count}'),
    ))


def get_screen_status_line(label: str) -> str:
    status_line = yellow(f'### {label}')
    status_line += f' | detach: {cyan("<ctrl>+a d")}'
    status_line += f' | copy mode: {cyan("<ctrl>+a Esc")}'
    status_line += f' | abort copy mode: {cyan("Esc ")}'
    # It seems we need the space after this Esc,  ^^^
    # otherwise the color reset escape sequence stops working.
    return status_line


def check_for_status_change(autos: Autos, status_file: str):
    with FileWithLock(status_file, 'r+') as sf:
        for line in sf:
            if not line:
                continue
            LOG.debug(f'Line: {line}')
            auto_file, status = line.strip().split(':')
            LOG.debug(f'Got {auto_file}:{status}')
            match status:
                case 'max_parallel':
                    # In this case we misuse the "auto_file" part as number
                    # for how many parallel screens are allowed.
                    autos.max_parallel = int(auto_file)
                    LOG.info(f'Now process max {auto_file} screens parallel')
                case 'user_input_remove':
                    autos.user_input.remove(auto_file)
                case 'user_input_add':
                    autos.user_input.append(auto_file)
                    LOG.info(f'{auto_file} is waiting for user input')
                case 'finished':
                    autos.running.remove(auto_file)
                    autos.finished.append(auto_file)
                    LOG.info(f'{auto_file} finished')
                case _:
                    LOG.warning(f'[{auto_file}] Unrecognized status "{status}"\n')
        # Empty status file as all status have been processed
        sf.truncate(0)


def run_manage_loop(tempdir: str, time_id: int):
    status_file = f'{tempdir}/{time_id}_overview'
    auto_files = sorted(get_files(tempdir))
    autos = Autos(status_file=status_file, time_id=time_id, count=len(auto_files), waiting=auto_files, tempdir=tempdir)
    with open(f'{tempdir}/{next(iter(auto_files))}', 'rb') as f:
        logfile_dir = pickle.load(f)['logfile_dir']

    LOG.info(f'Found {autos.count} files to process. Screens name are like "{time_id}_autoX"')
    LOG.info('To switch screens detach from this screen via "<ctrl>+a d".')
    LOG.info('To scroll back in history press "<ctrl>+a Esc" to enable "copy mode". Switch back with "Esc".')
    LOG.info('You can modify this behaviour by screen configuration options (`~/.screenrc`).')

    open(status_file, 'a').close()
    try:
        while len(autos.finished) < autos.count:
            if len(autos.running) < autos.max_parallel and autos.waiting:
                auto_file = autos.waiting.pop(0)
                autos.running.append(auto_file)

                auto_path = f'{tempdir}/{auto_file}'
                with open(auto_path, 'rb') as f:
                    auto_file_data = pickle.load(file=f)
                status_line = get_screen_status_line(label=auto_file_data['label'])

                session_name = f'{time_id}_{auto_file}'
                logfile_path = f'{logfile_dir}/{auto_file}.log'

                LOG.info(f'Starting new screen at {session_name}')
                subprocess.run([
                    'screen', '-d', '-m', '-S', session_name,
                    '-h', '100000',
                    '-L', '-Logfile', logfile_path,
                    'automatix-from-file', tempdir, str(time_id), auto_file
                ])
                subprocess.run(['screen', '-S', session_name, '-X', 'hardstatus', 'alwayslastline'])
                subprocess.run(['screen', '-S', session_name, '-X', 'hardstatus', 'string', status_line])

            check_for_status_change(autos=autos, status_file=status_file)

            print_status(autos=autos)

            # Write status to file for screen switch loop
            with FileWithLock(f'{tempdir}/autos', 'wb') as f:
                pickle.dump(obj=autos, file=f)

            sleep(1)

        LOG.info(f'All parallel screen reported finished ({len(autos.finished)}/{autos.count}).')
    except Exception as exc:
        LOG.exception(exc)
        sleep(60)  # For debugging
    finally:
        with open(f'{tempdir}/{time_id}_finished', 'w') as fifo:
            fifo.write('finished')


def run_manager():
    parser = argparse.ArgumentParser(
        description='Automatix manager for parallel processing (called by the automatix main programm)',
        epilog='Explanations and README at https://github.com/vanadinit/automatix',
    )
    parser.add_argument('tempdir')
    parser.add_argument('time_id')
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='activate debug log level',
    )
    args = parser.parse_args()

    init_logger(name=CONFIG['logger'], debug=args.debug)
    run_manage_loop(tempdir=args.tempdir, time_id=int(args.time_id))


def run_auto(tempdir: str, time_id: int, auto_file: str):
    auto_path = f'{tempdir}/{auto_file}'

    def send_status(status: str):
        with FileWithLock(f'{tempdir}/{time_id}_overview', 'a') as sf:
            sf.write(f'{auto_file}:{status}\n')

    with open(auto_path, 'rb') as f:
        auto_file_data = pickle.load(file=f)
    try:
        run_automatix_list(automatix_list=auto_file_data['autolist'], send_status_callback=send_status)
    finally:
        send_status('finished')
        unlink(auto_path)


def run_auto_from_file():
    parser = argparse.ArgumentParser(
        description='Automatix from file for parallel processing (called by the automatix-manager)',
        epilog='Explanations and README at https://github.com/vanadinit/automatix',
    )
    parser.add_argument('tempdir')
    parser.add_argument('time_id')
    parser.add_argument('auto_file')
    args = parser.parse_args()

    try:
        if CONFIG['progress_bar']:
            setup_scroll_area()

        run_auto(tempdir=args.tempdir, time_id=args.time_id, auto_file=args.auto_file)
    finally:
        if CONFIG['progress_bar']:
            destroy_scroll_area()
