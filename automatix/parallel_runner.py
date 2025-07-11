import os
import pickle
import subprocess
from argparse import Namespace
from tempfile import TemporaryDirectory
from time import time

from .batch_runner import create_automatix_list
from .config import LOG
from .parallel import get_logfile_dir, get_screen_status_line
from .parallel_ui import screen_switch_loop


def get_batch_groups(batch_items: list) -> dict:
    batch_groups = {'_default_': []}
    for batch_item in batch_items:
        if group := batch_item.get('group'):
            assert group != '_default_', 'The group name "_default_" is reserved. Please use something different.'
            if group not in batch_groups.keys():
                batch_groups[group] = []
            batch_groups[group].append(batch_item)
        else:
            batch_groups['_default_'].append(batch_item)
    return batch_groups


def write_auto_file(auto_id: str, label: str, autolist: list, tempdir: str, logfile_dir: str):
    with open(f'{tempdir}/auto{auto_id}', 'wb') as f:
        pickle.dump(obj={
            'autolist': autolist,
            'auto_file': f'{tempdir}/auto{auto_id}',
            'label': label,
            'logfile_dir': logfile_dir,
        }, file=f)


def create_auto_files(script: dict, batch_items: list, args: Namespace, tempdir: str, logfile_dir: str):
    LOG.info(f'Using temporary directory to save object files: {tempdir}')

    batch_groups = get_batch_groups(batch_items=batch_items)
    default_group = batch_groups.pop('_default_')

    digits = len(str(len(batch_groups) + len(default_group)))

    i = 1
    # Create grouped automatix files for each "real" group
    for i, (group, items) in enumerate(batch_groups.items(), start=1):
        write_auto_file(
            auto_id=str(i).rjust(digits, '0'),
            autolist=create_automatix_list(script=script, batch_items=items, args=args),
            label=f'Group: {group}',
            tempdir=tempdir,
            logfile_dir=logfile_dir,
        )

    # All rows/batch_items in the default group get their own automatix file and screen
    for j, batch_item in enumerate(default_group, start=i + 1):
        auto_id = str(j).rjust(digits, '0')

        # Get label before create_automatix_list, where the label field is removed
        label = batch_item.get('label', f'auto{auto_id}')

        autolist = create_automatix_list(script=script, batch_items=[batch_item], args=args)
        write_auto_file(
            auto_id=auto_id,
            autolist=autolist,
            label=label,
            tempdir=tempdir,
            logfile_dir=logfile_dir,
        )


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
        time_id = round(time())
        logfile_dir = get_logfile_dir(time_id=time_id, scriptfile=args.scriptfile)
        os.makedirs(logfile_dir)
        os.mkfifo(f'{tempdir}/{time_id}_finished')

        create_auto_files(script=script, batch_items=batch_items, args=args, tempdir=tempdir, logfile_dir=logfile_dir)

        LOG.info(f'Created directory for logfiles at {logfile_dir}')

        cmds = [
            'screen', '-d', '-m', '-S', f'{time_id}_overview',
            '-h', '100000',
            '-L', '-Logfile', f'{logfile_dir}/overview.log',
            'automatix-manager', tempdir, str(time_id),
        ]
        if args.debug:
            cmds.append('--debug')

        subprocess.run(cmds)

        status_line = get_screen_status_line(label='Manager screen')
        subprocess.run(['screen', '-S', f'{time_id}_overview', '-X', 'hardstatus', 'alwayslastline'])
        subprocess.run(['screen', '-S', f'{time_id}_overview', '-X', 'hardstatus', 'string', status_line])

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
