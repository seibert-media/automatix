import argparse
import logging

from collections import OrderedDict

CONFIG_FIELDS = OrderedDict()
CONFIG_FIELDS['systems'] = 'Systems'
CONFIG_FIELDS['vars'] = 'Variables'
CONFIG_FIELDS['secrets'] = 'Secrets'

LOG = logging.getLogger(__name__)


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


def main():
    args = _arguments()
    
    print('Not implemented yet!')
