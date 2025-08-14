from automatix.command import Command
from tests.test_environment import testauto, environment

len_always = len(testauto.script.get('always', []))
len_main = len(testauto.script.get('pipeline', []))
len_cleanup = len(testauto.script.get('cleanup', []))


def test__automatix__command_list():
    assert testauto.command_list('main') == testauto.command_list('pipeline')
    cmd = Command(
        cmd={'local': "echo 'Print this always :-)'"},
        index=0,
        pipeline='always',
        env=environment,
        position=0,
    )
    first_cleanup = testauto.command_list('always')[0]
    assert isinstance(first_cleanup, Command)
    assert vars(first_cleanup) == vars(cmd)


def test__automatix__get_command_position():
    assert testauto.get_command_position(index=4, pipeline='always') == 4
    assert testauto.get_command_position(index=3, pipeline='always') != 4
    assert testauto.get_command_position(index=3, pipeline='main') == len_always + 3
    assert testauto.get_command_position(index=3, pipeline='pipeline') == len_always + 3
    assert testauto.get_command_position(index=2, pipeline='cleanup') == len_always + len_main + 2


def test__automatix__set_command_count():
    testauto.env.command_count = None
    testauto.set_command_count()
    assert testauto.env.command_count == len_always + len_main + len_cleanup
