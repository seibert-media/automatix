from automatix.command import Command
from tests.test_environment import testauto, environment


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
    assert testauto.get_command_position(index=3, pipeline='main') == 7  # 4 commands in always pipeline
    assert testauto.get_command_position(index=3, pipeline='pipeline') == 7  # 4 commands in always pipeline
    assert testauto.get_command_position(index=2, pipeline='cleanup') == 23  # 21 commands in always + main pipeline


def test__automatix__set_command_count():
    testauto.env.command_count = None
    testauto.set_command_count()
    assert testauto.env.command_count == 24
