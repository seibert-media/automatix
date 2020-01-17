import subprocess
from argparse import Namespace
from time import sleep

import pytest

from . import get_script, collect_vars, CONFIG, cmdClass, SCRIPT_FIELDS
from .automatix import Automatix

pytest_plugins = ["docker_compose"]

default_args = Namespace(
    scriptfile='tests/test.yaml',
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

environment = testauto.env


def run_command_and_check(cmd):
    subprocess.run(cmd, shell=True).check_returncode()


@pytest.fixture(scope='function')
def ssh_up(function_scoped_container_getter):
    max_retries = 20
    for i in range(max_retries):
        sleep(1)
        try:
            run_command_and_check('ssh docker-test /bin/true')
        except subprocess.CalledProcessError:
            continue
        return
    Exception('Maximum retries exceeded: SSH test setup could not be created.')
