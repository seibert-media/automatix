from subprocess import CalledProcessError

import pytest

from automatix.command import Command
from tests.test_environment import environment, run_command_and_check, ssh_up

pytest_plugins = ["docker_compose"]


def test__execute_remote_cmd(ssh_up):
    cmd = Command(pipeline_cmd={'remote@testsystem': 'touch /test_remote_cmd'}, index=2, env=environment)
    cmd.execute()
    try:
        run_command_and_check('ssh docker-test ls /test_remote_cmd >/dev/null')
    except CalledProcessError:
        pytest.fail('Check for remote file not successful')


def test__execute_local_cmd(capfd):
    test_string = "Local Test String"

    # empty captured stdin and stderr
    _ = capfd.readouterr()

    cmd = Command(pipeline_cmd={'local': f'echo {test_string}'}, index=2, env=environment)
    cmd.execute()

    out, err = capfd.readouterr()
    assert test_string in out
    assert err == ''


def test__execute_python_cmd():
    test_cmd = """
from uuid import uuid4
from pprint import pprint
PERSISTENT_VARS.update(locals())
"""

    cmd = Command(pipeline_cmd={'python': test_cmd}, index=2, env=environment)
    cmd.execute()

    cmd = Command(pipeline_cmd={'python': 'print(uuid4())'}, index=2, env=environment)
    cmd.execute()
