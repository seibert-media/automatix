import pytest
import subprocess
import time

from .command import Command
from .testdata import environment

pytest_plugins = ["docker_compose"]


@pytest.fixture(scope='function')
def ssh_up(function_scoped_container_getter):
    for i in range(100):
        time.sleep(1)
        try:
            subprocess.run('ssh docker-test /bin/true', shell=True).check_returncode()
        except subprocess.CalledProcessError:
            continue
        return


def test__simple_remote_cmd(ssh_up):
    cmd = Command(pipeline_cmd={'remote@testsystem': 'uptime'}, index=2, env=environment)
    cmd.execute()
    assert True
