# PYTHON_ARGCOMPLETE_OK
import argparse
import os
import subprocess
import sys
from time import time, strftime, gmtime

from .batch_runner import get_script_and_batch_items, run_batch_items
from .config import init_logger, CONFIG, LOG, VERSION, arguments, MAGIC_SELECTION_INT
from .helpers import empty_queued_input_data, selector
from .parallel_runner import run_parallel_screens
from .progress_bar import setup_scroll_area, destroy_scroll_area


def check_for_original_automatix():
    p = subprocess.run('pip list | grep automatix', shell=True, stdout=subprocess.PIPE)

    for line in p.stdout.decode().split('\n'):
        if line.strip().split(' ', maxsplit=1)[0].strip() == 'automatix_cmd':
            raise Exception(
                'This package MUST NOT be installed along with the "automatix_cmd" package.'
                ' Both packages use the same entry point and module names and therefore'
                ' are conflicting. Please uninstall automatix AND automatix_cmd first,'
                ' THEN reinstall the package you want to use!')


def run_startup_script():
    if not CONFIG.get('startup_script'):
        return

    cmds = [os.path.expandvars(CONFIG["startup_script"])]
    cmds.extend(sys.argv)
    subprocess.run(cmds)


def setup(args: argparse.Namespace) -> float:
    """Setup logger and print version information"""
    init_logger(name=CONFIG['logger'], debug=args.debug)
    starttime = time()

    LOG.info(f'Automatix Version {VERSION}')
    LOG.info(f'Started at: {strftime("%a, %d %b %Y %H:%M:%S UTC", gmtime(starttime))}')

    configfile = CONFIG.get('config_file')
    if configfile:
        LOG.info(f'Using configuration from: {configfile}')
    else:
        LOG.warning('Configuration file not found or not configured. Using defaults.')

    return starttime


def check_screen():
    p = subprocess.run('screen -v', shell=True, stdout=subprocess.PIPE)
    screen_version = p.stdout.decode()
    if p.returncode != 0 or 'command not found' in screen_version:
        raise Exception('No GNU screen version found')
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
        empty_queued_input_data()
        answer = input('Do you really want to proceed? Then type "yes" and ENTER.\n')
        if answer != 'yes':
            sys.exit(0)

    args = arguments()
    run_startup_script()

    starttime = setup(args=args)

    script, batch_items = get_script_and_batch_items(args=args)

    if args.jump_to == MAGIC_SELECTION_INT:
        # next(iter(pi.items())) is here needed, because the pipeline items are all dictionaries with only one key.
        pipeline_items = [next(iter(pi.items())) for pi in script['pipeline']]
        args.jump_to = selector(
            entries=[
                (i, f'[{key}]: {cmd}')
                for i, (key, cmd) in enumerate(pipeline_items)
            ],
            message='Please choose index of desired start command:'
        )

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
