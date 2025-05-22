from sys import stdin
from typing import List

import yaml
from termios import tcflush, TCIFLUSH

yaml.warnings({'YAMLLoadWarning': False})


def read_yaml(yamlfile: str) -> dict:
    with open(yamlfile) as file:
        return yaml.load(file.read(), Loader=yaml.SafeLoader)


def empty_queued_input_data():
    tcflush(stdin, TCIFLUSH)


def selector(entries: List[tuple], message: str = 'Found multiple entries, please choose:'):
    """Provides a command line interface for selecting from multiple entries
    :param entries: List of Tuples(entry: Any, label: str)
    :param message: message to be displayed for selection
    """
    match len(entries):
        case 0:
            return None
        case 1:
            return entries[0][0]
        case _:
            entry_labels = '\n'.join([
                f'{index}: {entry[1]}'
                for index, entry in enumerate(entries)
            ])
            try:
                empty_queued_input_data()
                return entries[int(input(f'\n{message} \n{entry_labels}\n\nYour choice:\n'))][0]
            except (ValueError, IndexError):
                print('Invalid answer! Please try again and type the number of your desired answer.')
                return selector(entries)
