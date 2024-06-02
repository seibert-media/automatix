import pickle
import sys

from automatix import AbortException, LOG


def run_from_pipe(pipe: str):
    if pipe == 'overview':
        run_overview()
    else:
        with open(pipe, 'r') as p:
            data = p.readline().encode()
        auto = pickle.loads(data)
        auto.env.attach_logger()
        try:
            auto.run()
        except AbortException as exc:
            sys.exit(int(exc))
        except KeyboardInterrupt:
            LOG.warning('\nAborted by user. Exiting.')
            sys.exit(130)


def run_overview():
    raise NotImplemented
