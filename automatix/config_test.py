from unittest import TestCase
from unittest.mock import patch

from automatix.config import _overwrite, _tupelize, check_deprecated_syntax, check_version

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
    assert 'Using "{const_apt}" does not work any longer. Use "{CONST.apt}" instead.' in caplog.text


def test__check_deprecated_syntax__global(caplog):
    check_deprecated_syntax(ckey='python', entry='import xy; global xy', script={}, prefix='[always:5]')
    assert '[always:5] Using "global xy" does not work any longer. Use "PERSISTENT_VARS[\'xy\'] = xy" instead.' in caplog.text


def test__check_deprecated_syntax__vars(caplog):
    check_deprecated_syntax(ckey='python', entry='vars["myvar"] = xyz', script={}, prefix='[pipeline:7]')
    assert '[pipeline:7] Using "vars["myvar"]" does not work any longer. Use "VARS.myvar" instead.' in caplog.text


def test__check_deprecated_syntax__a_vars(caplog):
    check_deprecated_syntax(ckey='python', entry='a_vars["myvar"] = xyz', script={}, prefix='[pipeline:7]')
    assert '[pipeline:7] Using "a_vars["myvar"]" is deprecated. Use "VARS.myvar" instead.' in caplog.text


@patch('automatix.config.VERSION', '2.1.5')
def test__check_version__pass():
    check_version('==2.1.5')
    check_version('2.1.5')
    check_version('2.1.4')
    check_version('2')
    check_version('>2.1')
    check_version('> 2, < 3')
    check_version('!=2.1.4')
    check_version('~=2.1')
    check_version('~= 2.0')
    check_version('~=2')


@patch('automatix.config.VERSION', '2.1.5')
def test__check_version__fail():
    with tc.assertRaises(AssertionError):
        check_version('<2.0.0')

    with tc.assertRaises(AssertionError):
        check_version('>1.0, <2')

    with tc.assertRaises(AssertionError):
        check_version('~= 2.2')

    with tc.assertRaises(AssertionError):
        check_version('~= 3.1')

    with tc.assertRaises(AssertionError):
        check_version('~= 3')

    with tc.assertRaises(AssertionError):
        check_version('<=2.1')

    with tc.assertRaises(SyntaxError):
        check_version('!! 3.7.2')
