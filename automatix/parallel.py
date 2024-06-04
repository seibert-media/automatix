import os
import pickle
import select
import subprocess
import sys
from dataclasses import dataclass, field
from os import listdir, unlink
from os.path import isfile
from time import sleep

from .automatix import Automatix
from .colors import yellow, green, red, cyan
from .command import AbortException
from .config import LOG

# TODO parallel processing
#  * update README
#  * refactoring and testing
#  * make things prettier...
#  * logging to files?

LINE_UP = '\033[1A'
LINE_CLEAR = '\x1b[2K'


@dataclass
class Autos:
    count: int

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
    print(f'------------------ Screens (max. {autos.max_parallel} running) ------------------')
    print_status(autos=autos)
    print('--------------------------------------------------------------')
    print(f'waiting: {sorted(autos.waiting)}')
    print(f'running: {sorted(autos.running)}')
    print(f'user input required: {red(sorted(autos.user_input))}')
    print(f'finished: {sorted(autos.finished)}')


def run_overview(name: str):
    tempdir, screen_id = name.rsplit(sep='/', maxsplit=1)
    time_id = screen_id.split('_')[0]
    auto_files = get_files(tempdir)
    autos = Autos(count=len(auto_files), waiting=auto_files)

    LOG.info(f'Found {autos.count} files to process. Screens name are like "{time_id}_autoX"')
    LOG.info('To switch to screens detach from this screen via "<ctrl>+a d".')

    open(name, 'a').close()
    try:
        while len(autos.finished) < autos.count:
            if len(autos.running) < autos.max_parallel and autos.waiting:
                auto_file = autos.waiting.pop()
                autos.running.add(auto_file)
                LOG.info(f'Starting new screen at {time_id}_{auto_file}')
                subprocess.run(
                    f'screen -d -m -S {time_id}_{auto_file}'
                    f' automatix nonexistent --prepared-from-pipe {tempdir}/{auto_file}_{time_id}',
                    # for debugging replace line above with:
                    # f' bash -c "automatix nonexistent --prepared-from-pipe {tempdir}/{auto_file}_{time_id} || bash"',
                    shell=True,
                )

            with FileWithLock(name, 'r+') as sf:
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

            print_status(autos=autos)

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


def run_auto(name: str):
    auto_path, time_id = name.rsplit('_', maxsplit=1)
    tempdir, auto_file = auto_path.rsplit(sep='/', maxsplit=1)

    def send_status(status: str):
        with FileWithLock(f'{tempdir}/{time_id}_overview', 'a') as sf:
            sf.write(f'{auto_file}:{status}\n')

    with open(auto_path, 'rb') as f:
        auto: Automatix = pickle.load(file=f)
    auto.env.attach_logger()
    auto.env.reinit_logger()
    auto.env.send_status = send_status

    try:
        auto.run()
    except AbortException as exc:
        sys.exit(int(exc))
    except KeyboardInterrupt:
        LOG.warning('\nAborted by user. Exiting.')
        sys.exit(130)
    finally:
        send_status('finished')
        unlink(auto_path)


def screen_switch_loop(tempdir: str, time_id: int):
    try:
        while not isfile(f'{tempdir}/autos'):
            sleep(1)
        while True:
            with FileWithLock(f'{tempdir}/autos', 'rb') as f:
                autos = pickle.load(file=f)
            print_status_verbose(autos=autos)

            if len(autos.running) + len(autos.waiting) + len(autos.user_input) == 0:
                break

            print()
            LOG.notice('Please notice: To come back to this selection press "<ctrl>+a d" in a screen session!')
            LOG.info('Following options are available:')
            LOG.info(
                'o: overview / manager loop,'
                ' n: next user input required,'
                ' X (number): switch to autoX,'
                f' mX: set max parallel screens to X (actual {autos.max_parallel})\n'
            )
            i, _, _ = select.select([sys.stdin], [], [], 1)
            if i:
                answer = sys.stdin.readline().strip()
            else:
                answer = ''

            screen_id = None
            if answer == 'o':
                screen_id = f'{time_id}_overview'
            elif answer == 'n' and autos.user_input:
                screen_id = f'{time_id}_{next(iter(autos.user_input))}'
            elif answer == '':
                for _ in range(12):
                    print(LINE_UP, end=LINE_CLEAR)
                continue
            elif answer.startswith('m'):
                try:
                    max_parallel = int(answer[1:])
                    with FileWithLock(f'{tempdir}/{time_id}_overview', 'a') as sf:
                        sf.write(f'{max_parallel}:max_parallel\n')
                except ValueError:
                    pass
            # elif answer == 'b': # for debugging
            #    break            # for debugging
            else:
                try:
                    screen_id = f'{time_id}_auto{str(int(answer)).rjust(len(str(autos.count)), "0")}'
                except ValueError:
                    LOG.warning(f'Invalid answer: {answer}')
            if screen_id:
                subprocess.run(f'screen -r {screen_id}', shell=True)
                sleep(1)
    except (KeyboardInterrupt, Exception) as exc:
        print('\n'*8)
        LOG.exception(exc)
        LOG.info('\nAn exception occurred! Please decide what to do:')
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
