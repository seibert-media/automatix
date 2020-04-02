from subprocess import CalledProcessError

import pytest

from automatix.command import Command, parse_key
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


def test__execute_local_with_condition(capfd):
    condition_tests = {
        'false_var': False,
        'true_var': True,
        'none_var': False,
        'empty_var': False,
        'example_string': True,
    }

    for condition_var, condition_out in condition_tests.items():
        # empty captured stdin and stderr
        _ = capfd.readouterr()

        cmd = Command(pipeline_cmd={f'{condition_var}?local': 'pwd'}, index=2, env=environment)
        cmd.execute()

        out, err = capfd.readouterr()
        assert condition_out == ('automatix' in out)
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


def test__parse_key():
    assert parse_key('python') == (None, None, 'python')
    assert parse_key('remote@v1') == (None, None, 'remote@v1')
    assert parse_key('host=remote@v1') == (None, 'host', 'remote@v1')
    assert parse_key('is_jira?host=remote@v1') == ('is_jira', 'host', 'remote@v1')
    assert parse_key('is_jira?python') == ('is_jira', None, 'python')
