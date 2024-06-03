import pickle
import subprocess
import sys
from dataclasses import dataclass, field
from os import listdir, unlink, mkfifo
from os.path import isfile
from time import sleep

from automatix import AbortException, LOG
from automatix.colors import yellow, green, red, cyan


# TODO
#  * add communication from automatix via pipe
#  * add controls for switching screens
#  * update README

@dataclass
class Autos:
    waiting: set = field(default_factory=set)
    running: set = field(default_factory=set)
    user_input: set = field(default_factory=set)
    finished: set = field(default_factory=set)


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
        f=green(len(autos.finished)),
    ))


def print_status_verbose(autos: Autos):
    print_status(autos=autos)
    print(f'waiting: {autos.waiting}')
    print(f'running: {autos.running}')
    print(f'user input required: {autos.user_input}')
    print(f'finished: {autos.finished}')


def run_overview(name: str):
    tempdir, screen_id = name.rsplit(sep='/', maxsplit=1)
    time_id = screen_id.split('_')[0]
    auto_files = get_files(tempdir)

    LOG.debug(f'Overview names pipe at {name}')
    LOG.info(f'Found {len(auto_files)} files to process. Screens name are like "{time_id}_autoX"')
    LOG.info('To switch to screens detach from this screen via "<ctrl>+a d".')

    autos = Autos(waiting=auto_files)
    max_parallel = 2

    mkfifo(name)
    try:
        while len(autos.finished) < len(auto_files):
            if len(autos.running) < max_parallel and autos.waiting:
                auto_file = autos.waiting.pop()
                LOG.debug(f'Starting new screen at {time_id}_{auto_file}')
                subprocess.run(
                    f'screen -d -m -S {time_id}_{auto_file}'
                    f' automatix nonexistent --prepared-from-pipe "{tempdir}/{auto_file}_{time_id}"',
                    shell=True,
                )

            print_status(autos=autos)
            with open(f'{tempdir}/autos', 'wb') as f:
                pickle.dump(obj=autos, file=f)

            with open(name) as fifo:
                LOG.debug(f'\nWait for input on named pipe {name}')
                for line in fifo:
                    LOG.debug(f'Line: {line}')
                    auto_file, status = line.strip().split(':')
                    LOG.debug(f'Got {auto_file}:{status}')
                    match status:
                        case 'running':
                            autos.running.add(auto_file)
                        case 'user_input_remove':
                            autos.user_input.remove(auto_file)
                        case 'user_input_add':
                            autos.user_input.add(auto_file)
                        case 'finished':
                            autos.running.remove(auto_file)
                            autos.finished.add(auto_file)
                        case _:
                            LOG.warning(f'[{auto_file}] Unrecognized status "{status}"\n')
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
        with open(f'{tempdir}/{time_id}_overview', 'w') as fifo:
            fifo.write(f'{auto_file}:{status}\n')

    with open(auto_path, 'rb') as f:
        auto = pickle.load(file=f)
    auto.env.attach_logger()
    auto.env.send_status = send_status

    send_status('running')
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
