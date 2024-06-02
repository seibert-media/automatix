import os
import pickle
import subprocess
import sys
from dataclasses import dataclass
from os import listdir
from os.path import isfile

from automatix import AbortException, LOG
from automatix.colors import yellow, green, red, cyan


@dataclass
class Autos:
    waiting: set = set(),
    running: set = set(),
    user_input: set = set(),
    finished: set = set(),


def run_from_pipe(pipe: str):
    if pipe.endswith('overview'):
        run_overview(name=pipe)
    else:
        with open(pipe, 'rb') as f:
            auto = pickle.load(file=f)
        auto.env.attach_logger()
        try:
            auto.run()
        except AbortException as exc:
            sys.exit(int(exc))
        except KeyboardInterrupt:
            LOG.warning('\nAborted by user. Exiting.')
            sys.exit(130)


def get_files(tempdir: str) -> set:
    return {f for f in listdir(tempdir) if isfile(f'{tempdir}/{f}') and f.startswith('auto')}


def print_status(autos: Autos):
    tmpl = 'waiting: {w}, running: {r}, user input required: {u}, finished: {f}'
    print(
        tmpl.format(
            w=yellow(len(autos.waiting)),
            r=cyan(len(autos.running)),
            u=red(len(autos.user_input)),
            f=green(len(autos.finished)),
        ),
        end='\r',
    )


def run_overview(name: str):
    tempdir, screen_id = name.rsplit(sep='/', maxsplit=1)
    time_id = screen_id.split('_')[0]
    count = len(get_files(tempdir))
    autos = Autos(waiting=get_files(tempdir))
    max_parallel = 2

    os.mkfifo(name)

    while len(autos.finished) < count:
        if len(autos.running) < max_parallel and autos.waiting:
            auto_file = autos.waiting.pop()
            subprocess.run(
                f'screen -d -m -S {time_id}_{auto_file}'
                f' automatix nonexistent --prepared-from-pipe "{tempdir}/{time_id}_{auto_file}"',
                shell=True,
            )

        print_status(autos=autos)

        with open(name) as fifo:
            for line in fifo:
                auto_file, status = line.strip().split(':')
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

    with open(f'{tempdir}/{time_id}_finished', 'w') as fifo:
        fifo.write('finished')
