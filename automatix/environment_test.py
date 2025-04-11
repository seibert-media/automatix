from unittest import TestCase

from automatix.environment import AttributedDict, AttributedDummyDict

tc = TestCase()


def test__attributed_dict():
    test_dict = AttributedDict()

    test_dict['a'] = 5
    assert test_dict.a == 5

    test_dict.b = 'abcde'
    assert test_dict['b'] == 'abcde'

    with tc.assertRaises(AttributeError):
        _ = test_dict.not_existent

    with tc.assertRaises(KeyError):
        _ = test_dict['not_existent']


def test__attributed_dummy_dict():
    test_dict = AttributedDummyDict('DICTNAME')

    test_dict['a'] = 5
    assert test_dict.a == 5

    test_dict.b = 'abcde'
    assert test_dict['b'] == 'abcde'

    assert test_dict.not_existent == test_dict['not_existent'] == '{DICTNAME.not_existent}'
    assert test_dict.__name__ == 'DICTNAME'
