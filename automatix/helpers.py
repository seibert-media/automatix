import os
from sys import stdin
from time import sleep
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


class FileWithLock:
    def __init__(self, file_path: str, method: str):
        self.file_path = file_path
        self.method = method
        self.file_obj = None

    def __enter__(self):
        get_lock(self.file_path)
        self.file_obj = open(self.file_path, self.method)
        return self.file_obj

    def __exit__(self, type, value, traceback):
        self.file_obj.close()
        release_lock(self.file_path)


def get_lock(file_path: str):
    while True:
        try:
            os.mkdir(f'{file_path}.lock')
        except FileExistsError:
            sleep(1)
            continue
        break


def release_lock(file_path: str):
    os.rmdir(f'{file_path}.lock')
