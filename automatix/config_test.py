from unittest import TestCase

from automatix.config import _overwrite, _tupelize, check_deprecated_syntax

tc = TestCase()


def test__overwrite():
    start_dict = {
        'variables': {
            'a': 7,
            'b': 'test',
            'c': True,
        }
    }

    _overwrite(script=start_dict, key='variables', data=['a=27', 'b=true', 'd=s8'])

    assert start_dict == {
        'variables': {
            'a': '27',
            'b': 'true',
            'c': True,
            'd': 's8',
        }
    }


def test__tupelize():
    assert _tupelize('1.2.3.4') == (1, 2, 3, 4)
    with tc.assertRaises(ValueError):
        _tupelize('4.7.dev32')


def test__check_deprecated_syntax__dict(caplog):
    check_deprecated_syntax(ckey='local', entry={'test': ''}, script={}, prefix='')
    assert 'Command is not a string' in caplog.text


def test__check_deprecated_syntax__const(caplog):
    check_deprecated_syntax(ckey='local', entry='{const_apt}', script={}, prefix='')
    assert 'Using "{const_apt}" is deprecated. Use "{CONST.apt}" instead.' in caplog.text


def test__check_deprecated_syntax__global(caplog):
    check_deprecated_syntax(ckey='python', entry='import xy; global xy', script={}, prefix='[always:5]')
    assert '[always:5] Using "global xy" is deprecated. Use "PERSISTENT_VARS[\'xy\'] = xy" instead.'
