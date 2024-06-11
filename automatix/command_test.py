import builtins
from copy import deepcopy
from subprocess import CalledProcessError
from unittest import mock

import pytest

from automatix.command import Command, parse_key
from tests.test_environment import environment, run_command_and_check, ssh_up  # noqa: F401


def test__integration__execute_remote_cmd(ssh_up):  # noqa: F811
    cmd = Command(
        cmd={'remote@testsystem': 'touch /test_remote_cmd'},
        index=2,
        pipeline='pipeline',
        env=environment,
        position=1,
    )
    cmd.execute()
    try:
        run_command_and_check('ssh docker-test ls /test_remote_cmd >/dev/null')
    except CalledProcessError:
        pytest.fail('Check for remote file not successful')


def test__execute_local_cmd(capfd):
    test_string = "Local Test String"

    # empty captured stdin and stderr
    _ = capfd.readouterr()

    cmd = Command(
        cmd={'local': f'echo {test_string}'},
        index=2,
        pipeline='pipeline',
        env=environment,
        position=1,
    )
    cmd.execute()

    out, err = capfd.readouterr()
    assert test_string in out
    assert err == ''


def test__execute_local_with_condition(capfd):
    env = deepcopy(environment)
    env.vars.update({
        'false_var': False,
        'true_var': True,
        'empty_var': '',
        'none_var': None,
        'example_string': 'example',
    })

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

        cmd = Command(
            cmd={f'{condition_var}?local': 'pwd'},
            pipeline='pipeline',
            index=2,
            env=env,
            position=1,
        )
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

    cmd = Command(cmd={'python': test_cmd}, index=2, pipeline='pipeline', env=environment, position=1)
    cmd.execute()

    cmd = Command(cmd={'python': 'print(uuid4())'}, index=2, pipeline='pipeline', env=environment, position=1)
    cmd.execute()


def test__parse_key():
    assert parse_key('python') == (None, None, 'python')
    assert parse_key('remote@v1') == (None, None, 'remote@v1')
    assert parse_key('host=remote@v1') == (None, 'host', 'remote@v1')
    assert parse_key('is_jira?host=remote@v1') == ('is_jira', 'host', 'remote@v1')
    assert parse_key('is_jira!?python') == ('is_jira!', None, 'python')


def test__show_and_change_variables():
    cmd = Command(cmd={'python': 'pass'}, index=2, pipeline='pipeline', env=deepcopy(environment), position=1)
    assert cmd.env.vars == {
        'a': '{a}',
        'myvar': 'huhu',
        'cond': '{cond}',
        'cond2': '{cond2}',
    }
    with mock.patch.object(builtins, 'input', lambda _: 'var1=xyz'):
        cmd.show_and_change_variables()

    with mock.patch.object(builtins, 'input', lambda _: 'myvar=hallo'):
        cmd.show_and_change_variables()

    with mock.patch.object(builtins, 'input', lambda _: ' cond2  =  !dgkls=432 \n\t  '):
        cmd.show_and_change_variables()

    assert cmd.env.vars == {
        'a': '{a}',
        'myvar': 'hallo',
        'cond': '{cond}',
        'cond2': '!dgkls=432',
        'var1': 'xyz',
    }
