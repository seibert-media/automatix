import subprocess
from argparse import Namespace
from os.path import abspath, dirname
from time import sleep

import pytest

from automatix import get_script, collect_vars, CONFIG, Command, SCRIPT_FIELDS
from automatix.automatix import Automatix
from automatix.logger import init_logger

SELFDIR = dirname(abspath(__file__))

default_args = Namespace(
    scriptfile=f'{SELFDIR}/test.yaml',
    systems=None,
    vars=None,
    secrets=None,
    print_overview=False,
    jump_to=0,
    interactive=False,
    force=False,
    debug=False,
)

script = get_script(args=default_args)

variables = collect_vars(script=script)

testauto = Automatix(
    script=script,
    variables=variables,
    config=CONFIG,
    cmd_class=Command,
    script_fields=SCRIPT_FIELDS,
    cmd_args=default_args,
    batch_index=1,
)

testauto.env.attach_logger()

environment = testauto.env

init_logger(name=CONFIG['logger'], debug=True)


def run_command_and_check(cmd):
    subprocess.run(cmd, shell=True).check_returncode()


@pytest.fixture(scope='function')
def ssh_up(docker_services):
    max_retries = 20
    for _ in range(max_retries):
        sleep(1)
        try:
            run_command_and_check(
                'ssh 2>/dev/null'
                ' -o StrictHostKeyChecking=no'
                ' -o "UserKnownHostsFile /dev/null"'
                ' -o ControlMaster=no'
                ' -o ControlPath=none'
                ' -o ConnectTimeout=10'
                ' docker-test /bin/true')
        except subprocess.CalledProcessError:
            continue
        run_command_and_check(cmd='ssh-keygen -R [localhost]:2222 >/dev/null 2>&1')
        run_command_and_check(cmd='ssh-keygen -R localhost:2222 >/dev/null 2>&1')
        run_command_and_check(cmd='ssh-keyscan -t ecdsa -p 2222 localhost 2>/dev/null >> ~/.ssh/known_hosts')
        return
    raise Exception('Maximum retries exceeded: SSH test setup could not be created.')
