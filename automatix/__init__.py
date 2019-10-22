import argparse
import logging
import os
import yaml

from collections import OrderedDict

from .logger import LOG

CONFIG_PATH = os.getenv('AUTOMATIX_CONFIG_DIR', '~/automatix-config')

CONFIG_FIELDS = OrderedDict()
CONFIG_FIELDS['systems'] = 'Systems'
CONFIG_FIELDS['vars'] = 'Variables'
CONFIG_FIELDS['secrets'] = 'Secrets'

yaml.warnings({'YAMLLoadWarning': False})


def _arguments():
    parser = argparse.ArgumentParser(
        description='Process automation tool',
    )
    parser.add_argument(
        'configfile',
        help='Path to configfile (yaml), use " -- " if needed to delimit this from argument fields',
    )
    for field in CONFIG_FIELDS.keys():
        parser.add_argument(
            f'--{field}',
            nargs='*',
            help=f'Use this to set {field} without adding them to the config or to overwrite them. '
            f'You can specify multiple {field} like: --{field} v1=string1 v2=string2 v3=string3',
        )
    parser.add_argument(
        '--print-overview', '-p',
        action='store_true',
        help='Just print command pipeline overview with indices then exit without executing the commandline. '
             'Note that the *always pipeline* will be executed beforehand.',
    )
    parser.add_argument(
        '--jump-to', '-j',
        help='Jump to step instead of starting at the beginning',
        default=0,
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Confirm actions before executing',
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='try always to proceed (except manual steps), even if errors occur (no retries)'
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='activate debug log level',
    )
    return parser.parse_args()


def _overwrite(config: dict, key: str, data: str):
    config.setdefault(key, {})
    for item in data:
        k, v = item.split('=')
        config[key][k] = v


def get_config(args: argparse.Namespace) -> dict:
    configfile = args.configfile
    if not os.path.isfile(args.configfile):
        configfile = f'{CONFIG_PATH}/{args.configfile}'

    config = read_config(configfile)

    for field in CONFIG_FIELDS.keys():
        if vars(args).get(field):
            _overwrite(config=config, key=field, data=vars(args)[field])

    return config


def read_config(configfile: str) -> dict:
    with open(configfile) as file:
        return yaml.load(file.read())


def main():
    args = _arguments()

    if args.debug:
        LOG.setLevel(logging.DEBUG)

    config = get_config(args=args)

    print('Not implemented yet!')
