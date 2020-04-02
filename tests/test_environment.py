import subprocess
from argparse import Namespace
from os.path import abspath, dirname
from time import sleep

import pytest

from automatix import get_script, collect_vars, CONFIG, cmdClass, SCRIPT_FIELDS
from automatix.automatix import Automatix

SELFDIR = dirname(abspath(__file__))

pytest_plugins = ["docker_compose"]

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
    cmd_class=cmdClass,
    script_fields=SCRIPT_FIELDS,
)

testauto.env.vars.update({
    'false_var': False,
    'true_var': True,
    'empty_var': '',
    'none_var': None,
    'example_string': 'example',
})

environment = testauto.env


def run_command_and_check(cmd):
    subprocess.run(cmd, shell=True).check_returncode()


@pytest.fixture(scope='function')
def ssh_up(function_scoped_container_getter):
    max_retries = 20
    for i in range(max_retries):
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
        run_command_and_check(cmd=f'ssh-keygen -R localhost:2222 >/dev/null 2>&1')
        run_command_and_check(cmd=f'ssh-keyscan -t ecdsa -p 2222 localhost 2>/dev/null >> ~/.ssh/known_hosts')
        return
    raise Exception('Maximum retries exceeded: SSH test setup could not be created.')
