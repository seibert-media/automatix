from subprocess import CalledProcessError

import pytest

from automatix.command import Command
from tests.test_environment import environment, run_command_and_check, ssh_up

pytest_plugins = ["docker_compose"]


def test__execute_remote_cmd(ssh_up):
    cmd = Command(pipeline_cmd={'remote@testsystem': 'touch /test_remote_cmd'}, index=2, env=environment)
    cmd.execute()
    try:
        run_command_and_check('ssh docker-test ls /test_remote_cmd')
    except CalledProcessError:
        pytest.fail('Check for remote file not successful')
