import os
import pickle
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


# TODO
#  * add communication from automatix via pipe
#  * add controls for switching screens
#  * update README

@dataclass
class Autos:
    count: int
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


def run_from_pipe(pipe: str):
    if pipe.endswith('overview'):
        run_overview(name=pipe)
    else:
        run_auto(name=pipe)


def get_files(tempdir: str) -> set:
    return {f for f in listdir(tempdir) if isfile(f'{tempdir}/{f}') and f.startswith('auto')}


def print_status(autos: Autos):
    tmpl = 'waiting: {w}, running: {r}, user input required: {u}, finished: {f}              '
    print(tmpl.format(
        w=yellow(len(autos.waiting)),
        r=cyan(len(autos.running)),
        u=red(len(autos.user_input)),
        f=green(f'{len(autos.finished)}/{autos.count}'),
    ))


def print_status_verbose(autos: Autos):
    print_status(autos=autos)
    print(f'waiting: {sorted(autos.waiting)}')
    print(f'running: {sorted(autos.running)}')
    print(f'user input required: {sorted(autos.user_input)}')
    print(f'finished: {sorted(autos.finished)}')


def run_overview(name: str):
    tempdir, screen_id = name.rsplit(sep='/', maxsplit=1)
    time_id = screen_id.split('_')[0]
    auto_files = get_files(tempdir)
    autos = Autos(count=len(auto_files), waiting=auto_files)

    LOG.debug(f'Overview names pipe at {name}')
    LOG.info(f'Found {autos.count} files to process. Screens name are like "{time_id}_autoX"')
    LOG.info('To switch to screens detach from this screen via "<ctrl>+a d".')

    max_parallel = 2

    open(name, 'a').close()
    try:
        while len(autos.finished) < autos.count:
            if len(autos.running) < max_parallel and autos.waiting:
                auto_file = autos.waiting.pop()
                LOG.info(f'Starting new screen at {time_id}_{auto_file}')
                autos.running.add(auto_file)
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
        file_path = f'{tempdir}/{time_id}_overview'
        with FileWithLock(file_path, 'a') as sf:
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
    while not isfile(f'{tempdir}/autos'):
        sleep(1)
    while True:
        with FileWithLock(f'{tempdir}/autos', 'rb') as f:
            autos = pickle.load(file=f)
        print_status_verbose(autos=autos)

        if len(autos.running) + len(autos.waiting) + len(autos.user_input) == 0:
            break

        answer = input(
            'o: overview, n: next user input required, X (number): switch to autoX, Enter: update information\n'
        )
        if answer == 'o':
            screen_id = f'{time_id}_overview'
        elif answer == 'n' and autos.user_input:
            screen_id = f'{time_id}_{next(iter(autos.user_input))}'
        elif answer == '':
            continue
        elif answer == 'b':
            break
        else:
            try:
                screen_id = f'{time_id}_auto{int(answer)}'
            except ValueError:
                screen_id = None
                LOG.warning('Invalid answer')
        if screen_id:
            subprocess.run(f'screen -r {screen_id}', shell=True)
            sleep(1)
