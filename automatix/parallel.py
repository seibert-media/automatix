import pickle
import sys
from time import sleep

from automatix import AbortException, LOG


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


def run_overview(name: str):
    print('Hier ist der Overview')
    sleep(20)
