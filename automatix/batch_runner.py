import sys
from argparse import Namespace
from copy import deepcopy
from csv import DictReader

from .automatix import Automatix
from .command import SkipBatchItemException, AbortException
from .config import CONFIG, get_script, LOG, update_script_from_row, collect_vars, SCRIPT_FIELDS


def get_script_and_batch_items(args: Namespace) -> (dict, list):
    script = get_script(args=args)

    batch_items: list[dict] = [{}]
    if args.vars_file:
        with open(args.vars_file) as csvfile:
            batch_items = list(DictReader(csvfile))
        script['_batch_mode'] = False if args.parallel else True
        script['_batch_items_count'] = 1 if args.parallel else len(batch_items)
        LOG.notice(f'Detected {"parallel" if args.parallel else "batch"} processing from CSV file.')

    return script, batch_items


def run_batch_items(script: dict, batch_items: list, args: Namespace):
    for i, row in enumerate(batch_items, start=1):
        script_copy = deepcopy(script)
        update_script_from_row(row=row, script=script_copy, index=i)

        variables = collect_vars(script_copy)

        auto = Automatix(
            script=script_copy,
            variables=variables,
            config=CONFIG,
            script_fields=SCRIPT_FIELDS,
            cmd_args=args,
            batch_index=i,
        )
        auto.env.attach_logger()
        auto.set_command_count()
        try:
            auto.run()
        except SkipBatchItemException as exc:
            LOG.info(str(exc))
            LOG.notice('=====> Jumping to next batch item.')
            continue
        except AbortException as exc:
            sys.exit(int(exc))
        except KeyboardInterrupt:
            print()
            LOG.warning('Aborted by user. Exiting.')
            sys.exit(130)
