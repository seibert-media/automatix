import os
import pickle
import subprocess
import sys
from argparse import Namespace
from copy import deepcopy
from csv import DictReader
from tempfile import TemporaryDirectory
from time import time
from typing import List

from .automatix import Automatix
from .command import SkipBatchItemException, AbortException
from .config import (
    arguments, CONFIG, get_script, LOG, update_script_from_row, collect_vars, SCRIPT_FIELDS, VERSION, init_logger
)
from .parallel import screen_switch_loop
from .progress_bar import setup_scroll_area, destroy_scroll_area


def check_for_original_automatix():
    p = subprocess.run('pip list | grep automatix', shell=True, stdout=subprocess.PIPE)

    for line in p.stdout.decode().split('\n'):
        if line.strip().split(' ', maxsplit=1)[0].strip() == 'automatix':
            raise Exception(
                'This package MUST NOT be installed along with the "automatix" package.'
                ' Both packages use the same entry point and module names and therefore'
                ' are conflicting. Please uninstall automatix AND automatix_cmd first,'
                ' THEN reinstall the package you want to use!')


def setup(args: Namespace):
    """Setup logger and print version information"""
    init_logger(name=CONFIG['logger'], debug=args.debug)

    LOG.info(f'Automatix Version {VERSION} (automatix_cmd)')

    configfile = CONFIG.get('config_file')
    if configfile:
        LOG.info(f'Using configuration from: {configfile}')
    else:
        LOG.warning('Configuration file not found or not configured. Using defaults.')


def get_script_and_batch_items(args: Namespace) -> (dict, list):
    script = get_script(args=args)

    batch_items: List[dict] = [{}]
    if args.vars_file:
        with open(args.vars_file) as csvfile:
            batch_items = list(DictReader(csvfile))
        script['batch_mode'] = False if args.parallel else True
        script['batch_items_count'] = 1 if args.parallel else len(batch_items)
        LOG.notice(f'Detected {"parallel" if args.parallel else "batch"} processing from CSV file.')

    if args.steps:
        exclude = script['exclude'] = args.steps.startswith('e')
        script['steps'] = {int(s) for s in (args.steps[1:] if exclude else args.steps).split(',')}

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


def create_auto_files(script: dict, batch_items: list, args: Namespace, tempdir: str):
    LOG.info(f'Using temporary directory to save object files: {tempdir}')
    digits = len(str(len(batch_items)))
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
            batch_index=1,
        )
        id = str(i).rjust(digits, '0')

        with open(f'{tempdir}/auto{id}', 'wb') as f:
            # The auto.cmd_class attribute MUST NOT be called before this!!!
            # Otherwise, the Bundlewrap integration will fail for parallel processing,
            # because the BWCommand is not pickleable.

            pickle.dump(obj=auto, file=f)


def run_parallel_screens(script: dict, batch_items: list, args: Namespace):
    LOG.info('Preparing automatix objects for parallel processing')

    with TemporaryDirectory() as tempdir:
        create_auto_files(script=script, batch_items=batch_items, args=args, tempdir=tempdir)

        time_id = round(time())
        os.mkfifo(f'{tempdir}/{time_id}_finished')

        logfile_dir = f'{CONFIG.get("logfile_dir")}/{time_id}'
        os.makedirs(logfile_dir)
        LOG.info(f'Created directory for logfiles at {logfile_dir}')

        subprocess.run(
            f'screen -d -m -S {time_id}_overview'
            f' automatix-manager {tempdir} {time_id} {"--debug" if args.debug else ""}',
            shell=True,
        )

        LOG.info(f'Overview / manager screen started at "{time_id}_overview".')

        LOG.info('Start loop with information to switch between running screens.\n')
        screen_switch_loop(tempdir=tempdir, time_id=time_id)

        with open(f'{tempdir}/{time_id}_finished') as fifo:
            print()
            LOG.info('Wait for overview to finish')
            for _ in fifo:
                LOG.info('Automatix finished parallel processing')
    LOG.info('Temporary directory cleaned up')
    LOG.info(f'All logfiles are available at {logfile_dir}')


def check_screen():
    p = subprocess.run('screen -v', shell=True, stdout=subprocess.PIPE)
    screen_version = p.stdout.decode()
    if 'GNU' in screen_version:
        return
    if 'FAU' in screen_version:
        LOG.error(
            'Parallel processing only supported for the "GNU" version of screen. You have the "FAU" version.\n'
            'On MacOS you can try to install the GNU version via Homebrew: `brew install screen`.'
        )
    raise Exception('No supported GNU screen version found')


def main():
    check_for_original_automatix()

    if os.getenv('AUTOMATIX_SHELL'):
        print('You are running Automatix from an interactive shell of an already running Automatix!')
        answer = input('Do you really want to proceed? Then type "yes" and ENTER.\n')
        if answer != 'yes':
            sys.exit(0)

    starttime = time()
    args = arguments()
    setup(args=args)

    script, batch_items = get_script_and_batch_items(args=args)

    if args.vars_file and args.parallel:
        check_screen()
        run_parallel_screens(script=script, batch_items=batch_items, args=args)
        sys.exit(0)

    try:
        if CONFIG['progress_bar']:
            setup_scroll_area()

        run_batch_items(script=script, batch_items=batch_items, args=args)
    finally:
        if CONFIG['progress_bar']:
            destroy_scroll_area()

    if 'AUTOMATIX_TIME' in os.environ:
        LOG.info(f'The Automatix script took {round(time() - starttime)}s!')
