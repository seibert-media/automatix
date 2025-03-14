import argparse
import os
import pickle
import subprocess
import sys
from dataclasses import dataclass, field
from os import listdir, unlink
from os.path import isfile
from pathlib import Path
from time import sleep, strftime, gmtime

import select

from .automatix import Automatix
from .colors import yellow, green, red, cyan
from .command import AbortException
from .config import LOG, init_logger, CONFIG
from .progress_bar import setup_scroll_area, destroy_scroll_area

# See https://en.wikipedia.org/wiki/ANSI_escape_code
LINE_UP = '\033[1A'
LINE_CLEAR = '\033[2K'
LINE_END = '\033[20C'  # Moves cursor 20 times forward, should be sufficient.
LINE_START = '\033[20D'  # Moves cursor 20 times backward, should be sufficient.
CURSOR_SAVE = '\033[s'
CURSOR_RESTORE = '\033[u'

LOOP_LINES = 18


@dataclass
class Autos:
    status_file: str
    time_id: int
    count: int
    tempdir: str

    max_parallel: int = 2
    waiting: set = field(default_factory=set)
    running: set = field(default_factory=set)
    user_input: set = field(default_factory=set)
    finished: set = field(default_factory=set)


class FileWithLock:
    def __init__(self, file_path: str, method: str):
        self.file_path = file_path
        self.method = method
        self.file_obj = None

    def __enter__(self):
        get_lock(self.file_path)
        self.file_obj = open(self.file_path, self.method)
        return self.file_obj

    def __exit__(self, type, value, traceback):
        self.file_obj.close()
        release_lock(self.file_path)


def get_lock(file_path: str):
    while True:
        try:
            os.mkdir(f'{file_path}.lock')
        except FileExistsError:
            sleep(1)
            continue
        break


def release_lock(file_path: str):
    os.rmdir(f'{file_path}.lock')


def get_logfile_dir(time_id: int, scriptfile: str) -> str:
    human_readable_time = strftime('%Y-%m-%d_%H-%M-%S_UTC', gmtime(time_id))
    return f'{CONFIG.get("logfile_dir")}/{human_readable_time}__{Path(scriptfile).stem}'


def get_files(tempdir: str) -> set:
    return {f for f in listdir(tempdir) if isfile(f'{tempdir}/{f}') and f.startswith('auto')}


def print_status(autos: Autos):
    tmpl = 'waiting: {w}, running: {r}, user input required: {u}, finished: {f}'
    print(tmpl.format(
        w=yellow(len(autos.waiting)),
        r=cyan(len(autos.running)),
        u=red(len(autos.user_input)),
        f=green(f'{len(autos.finished)}/{autos.count}'),
    ))


def print_status_verbose(autos: Autos):
    print(f'Working directory: {autos.tempdir}')
    print(f'------------------ Screens (max. {autos.max_parallel} running) ------------------')
    print_status(autos=autos)
    print('--------------------------------------------------------------')
    print(f'waiting:             {sorted(autos.waiting)}')
    print(f'running:             {sorted(autos.running)}')
    print(f'user input required: {red(sorted(autos.user_input))}')
    print(f'finished:            {sorted(autos.finished)}')


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
                    autos.user_input.add(auto_file)
                    LOG.info(f'{auto_file} is waiting for user input')
                case 'finished':
                    autos.running.remove(auto_file)
                    autos.finished.add(auto_file)
                    LOG.info(f'{auto_file} finished')
                case _:
                    LOG.warning(f'[{auto_file}] Unrecognized status "{status}"\n')
        sf.truncate(0)


def run_manage_loop(tempdir: str, time_id: int):
    status_file = f'{tempdir}/{time_id}_overview'
    auto_files = get_files(tempdir)
    autos = Autos(status_file=status_file, time_id=time_id, count=len(auto_files), waiting=auto_files, tempdir=tempdir)
    with open(f'{tempdir}/{next(iter(auto_files))}', 'rb') as f:
        scriptfile = pickle.load(f).env.cmd_args.scriptfile

    LOG.info(f'Found {autos.count} files to process. Screens name are like "{time_id}_autoX"')
    LOG.info('To switch screens detach from this screen via "<ctrl>+a d".')
    LOG.info('To scroll back in history press "<ctrl>+a Esc" to enable "copy mode". Switch back with "Esc".')
    LOG.info('You can modify this behaviour by screen configuration options (`~/.screenrc`).')

    open(status_file, 'a').close()
    try:
        while len(autos.finished) < autos.count:
            if len(autos.running) < autos.max_parallel and autos.waiting:
                auto_file = autos.waiting.pop()
                autos.running.add(auto_file)
                LOG.info(f'Starting new screen at {time_id}_{auto_file}')
                subprocess.run(
                    f'screen -d -m -S {time_id}_{auto_file}'
                    f' -L -Logfile {get_logfile_dir(time_id=time_id, scriptfile=scriptfile)}/{auto_file}.log'
                    f' automatix-from-file {tempdir} {time_id} {auto_file}',
                    # for debugging replace line above with:
                    # f' bash -c "automatix-from-file {tempdir} {time_id} {auto_file} || bash"',
                    shell=True,
                )

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
        auto: Automatix = pickle.load(file=f)
    auto.set_command_count()
    auto.env.attach_logger()
    auto.env.reinit_logger()
    auto.env.send_status = send_status

    try:
        auto.run()
    except AbortException as exc:
        sys.exit(int(exc))
    except KeyboardInterrupt:
        print()
        LOG.warning('Aborted by user. Exiting.')
        sys.exit(130)
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


def clear_loop():
    print(CURSOR_SAVE, end='', flush=True)
    print(LINE_START, end='')
    for _ in range(LOOP_LINES):
        print(LINE_UP, end=LINE_CLEAR)


def ask_for_options(autos: Autos) -> str | None:
    print()
    LOG.notice('Please notice: To come back to this selection press "<ctrl>+a d" in a screen session!')
    LOG.notice('To scroll back in history press "<ctrl>+a Esc" to enable "copy mode". Switch back with "Esc".')
    LOG.notice('You can modify this behaviour by screen configuration options (`~/.screenrc`).')
    print()
    LOG.info('Following options are available:')
    LOG.info(
        ' o: overview / manager loop\n'
        ' n: next user input required\n'
        ' X (number): switch to autoX\n'
        f' mX: set max parallel screens to X (actual {autos.max_parallel})\n'
    )
    print(CURSOR_RESTORE, end='', flush=True)


def check_for_option(autos: Autos) -> str | None:
    i, _, _ = select.select([sys.stdin], [], [], 1)
    if i:
        answer = sys.stdin.readline().strip()
        print(LINE_UP, end=LINE_CLEAR)
    else:
        return None

    if answer == '':
        return None

    if answer == 'o':
        return f'{autos.time_id}_overview'

    if answer == 'n' and autos.user_input:
        return f'{autos.time_id}_{next(iter(autos.user_input))}'

    if answer.startswith('m'):
        try:
            max_parallel = int(answer[1:])
            with FileWithLock(autos.status_file, 'a') as sf:
                sf.write(f'{max_parallel}:max_parallel\n')
            return None
        except ValueError:
            LOG.warning(f'Invalid answer: {answer}')
            sleep(1)
            return None

    try:
        number = int(answer)
        return f'{autos.time_id}_auto{str(number).rjust(len(str(autos.count)), "0")}'
    except ValueError:
        LOG.warning(f'Invalid answer: {answer}')
        sleep(1)
        print(LINE_UP, end=LINE_CLEAR, flush=True)
        return None


def screen_switch_loop(tempdir: str, time_id: int):
    try:
        while not isfile(f'{tempdir}/autos'):
            sleep(1)
        print('\n' * LOOP_LINES)  # some initial space for the loop
        while True:
            with FileWithLock(f'{tempdir}/autos', 'rb') as f:
                autos = pickle.load(file=f)

            if screen_id := check_for_option(autos=autos):
                subprocess.run(f'screen -r {screen_id}', shell=True)
                sleep(1)

            clear_loop()
            print_status_verbose(autos=autos)

            if len(autos.running) + len(autos.waiting) + len(autos.user_input) == 0:
                break

            ask_for_options(autos=autos)

    except (KeyboardInterrupt, Exception) as exc:
        print('\n' * 8)
        LOG.exception(exc)
        print()
        LOG.info('An exception occurred! Please decide what to do:')
        match input(
            'Press "r" and Enter to reraise.'
            ' This will cause this programm to terminate.'
            ' Check "screen -list" afterwards for still running screens.\n'
            ' Press something else to restart the loop, where you can switch to the different screens.\n'
        ):
            case 'r':
                raise
            case _:
                screen_switch_loop(tempdir=tempdir, time_id=time_id)
