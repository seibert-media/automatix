BLUE = '\033[34m'
CYAN = '\033[36m'
GREEN = '\033[32m'
RED = '\033[31m'
YELLOW = '\033[33m'

BOLD = '\033[1m'
ITALIC = '\033[3m'

RESET = '\033[0m'


def blue(text):
    return f'{BLUE}{text}{RESET}'


def cyan(text):
    return f'{CYAN}{text}{RESET}'


def green(text):
    return f'{GREEN}{text}{RESET}'


def red(text):
    return f'{RED}{text}{RESET}'


def yellow(text):
    return f'{YELLOW}{text}{RESET}'


def bold(text):
    return f'{BOLD}{text}{RESET}'


def italic(text):
    return f'{ITALIC}{text}{RESET}'


def nocolor(text):
    return f'{RESET}{text}'
