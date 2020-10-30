import os
from copy import deepcopy
from csv import DictReader
from importlib import import_module
from time import time
from typing import List

from .automatix import Automatix
from .command import Command, SkipBatchItemException, AbortException
from .config import arguments, CONFIG, get_script, LOG, update_script_from_row, collect_vars, SCRIPT_FIELDS

if CONFIG.get('logging_lib'):
    log_lib = import_module(CONFIG.get('logging_lib'))
    init_logger = log_lib.init_logger
else:
    from .logger import init_logger

if CONFIG.get('bundlewrap'):
    from bundlewrap.repo import Repository
    from .bundlewrap import BWCommand

    CONFIG['bw_repo'] = Repository(repo_path=os.environ.get('BW_REPO_PATH'))
    cmdClass = BWCommand
else:
    cmdClass = Command


def main():
    starttime = time()
    args = arguments()
    init_logger(name=CONFIG['logger'], debug=args.debug)

    script = get_script(args=args)

    batch_items: List[dict] = [{}]
    if args.vars_file:
        with open(args.vars_file) as csvfile:
            batch_items = list(DictReader(csvfile))
        script['batch_mode'] = True
        LOG.notice('Detected batch processing from CSV file.')

    for i, row in enumerate(batch_items, start=1):
        script_copy = deepcopy(script)
        update_script_from_row(row=row, script=script_copy, index=i)

        variables = collect_vars(script_copy)

        auto = Automatix(
            script=script_copy,
            variables=variables,
            config=CONFIG,
            cmd_class=cmdClass,
            script_fields=SCRIPT_FIELDS,
        )

        try:
            auto.run(args=args)
        except SkipBatchItemException as exc:
            LOG.info(str(exc))
            LOG.notice('=====> Jumping to next batch item.')
            continue
        except AbortException as exc:
            exit(int(exc))
        except KeyboardInterrupt:
            LOG.warning('\nAborted by user. Exiting.')
            exit(130)

    if 'AUTOMATIX_TIME' in os.environ:
        LOG.info(f'The Automatix script took {round(time() - starttime)}s!')
