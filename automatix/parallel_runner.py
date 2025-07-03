import os
import pickle
import subprocess
from argparse import Namespace
from copy import deepcopy
from tempfile import TemporaryDirectory
from time import time

from .automatix import Automatix
from .config import CONFIG, LOG, update_script_from_row, collect_vars, SCRIPT_FIELDS
from .parallel import get_logfile_dir
from .parallel_ui import screen_switch_loop


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
        auto.env.auto_file = auto_file = f'{tempdir}/auto{id}'

        with open(auto_file, 'wb') as f:
            # The auto.cmd_class attribute MUST NOT be called before this!!!
            # Otherwise, the Bundlewrap integration will fail for parallel processing,
            # because the BWCommand is not pickleable.

            pickle.dump(obj=auto, file=f)


def display_screen_control_hints():
    LOG.notice('--- Please read and understand these hints for controlling screen sessions before you proceed ---')
    LOG.notice('- If you switched to a screen session you can detach the session with "<ctrl>+a d".'
               ' This takes you back to the information interface.')
    LOG.notice('- To scroll back in history press "<ctrl>+a Esc" to enable "copy mode". Switch back with "Esc".')
    LOG.notice('- You can modify this behaviour by screen configuration options (`~/.screenrc`).')
    LOG.notice('- To suppress this message set the `AUTOMATIX_SUPPRESS_SCREEN_CONTROL_NOTICE` environment variable.')
    input('Press ENTER to continue...')


def run_parallel_screens(script: dict, batch_items: list, args: Namespace):
    LOG.info('Preparing automatix objects for parallel processing')

    with TemporaryDirectory() as tempdir:
        create_auto_files(script=script, batch_items=batch_items, args=args, tempdir=tempdir)

        time_id = round(time())
        os.mkfifo(f'{tempdir}/{time_id}_finished')

        logfile_dir = get_logfile_dir(time_id=time_id, scriptfile=args.scriptfile)
        os.makedirs(logfile_dir)
        LOG.info(f'Created directory for logfiles at {logfile_dir}')

        subprocess.run(
            f'screen -d -m -S {time_id}_overview'
            f' automatix-manager {tempdir} {time_id} {"--debug" if args.debug else ""}',
            shell=True,
        )

        LOG.info(f'Overview / manager screen started at "{time_id}_overview".')

        LOG.info('Start loop with information to switch between running screens.\n')
        if not os.getenv('AUTOMATIX_SUPPRESS_SCREEN_CONTROL_NOTICE'):
            display_screen_control_hints()

        screen_switch_loop(tempdir=tempdir)

        with open(f'{tempdir}/{time_id}_finished') as fifo:
            print()
            LOG.info('Wait for overview to finish')
            for _ in fifo:
                LOG.info('Automatix finished parallel processing')
    LOG.info('Temporary directory cleaned up')
    LOG.info(f'All logfiles are available at {logfile_dir}')
