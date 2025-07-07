import sys
from argparse import Namespace
from copy import deepcopy
from csv import DictReader
from typing import Callable

from .automatix import Automatix
from .command import SkipBatchItemException, AbortException
from .config import CONFIG, get_script, LOG, update_script_from_row, collect_vars, SCRIPT_FIELDS


def get_script_and_batch_items(args: Namespace) -> (dict, list):
    script = get_script(args=args)

    # Empty item means: there is nothing to update, take the script as it is
    batch_items: list[dict] = [{}]
    if args.vars_file:
        with open(args.vars_file) as csvfile:
            batch_items = list(DictReader(csvfile))

    return script, batch_items


def create_automatix_list(script: dict, batch_items: list, args: Namespace) -> list[Automatix]:
    automatix_list = []
    for i, row in enumerate(batch_items, start=1):
        script_copy = deepcopy(script)
        script_copy['_batch_mode'] = len(batch_items) > 1
        script_copy['_batch_items_count'] = len(batch_items)

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
        automatix_list.append(auto)
    return automatix_list


def run_automatix_list(automatix_list: list[Automatix], send_status_callback: Callable = None):
    for auto in automatix_list:
        auto.set_command_count()
        auto.env.attach_logger()
        auto.env.reinit_logger()
        if send_status_callback:
            auto.env.send_status = send_status_callback
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


def run_batch_items(script: dict, batch_items: list, args: Namespace):
    automatix_list = create_automatix_list(script=script, batch_items=batch_items, args=args)
    run_automatix_list(automatix_list=automatix_list)
