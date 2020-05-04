import argparse
import logging
import os
from collections import OrderedDict
from importlib import import_module
from time import time

import yaml

from .automatix import Automatix
from .command import Command

yaml.warnings({'YAMLLoadWarning': False})


def read_yaml(yamlfile: str) -> dict:
    with open(yamlfile) as file:
        return yaml.load(file.read())


SCRIPT_FIELDS = OrderedDict()
SCRIPT_FIELDS['systems'] = 'Systems'
SCRIPT_FIELDS['vars'] = 'Variables'

CONFIG = {
    'script_dir': '~/automatix-config',
    'constants': {},
    'encoding': os.getenv('ENCODING', 'utf-8'),
    'import_path': '.',
    'ssh_cmd': 'ssh {hostname} sudo ',
    'remote_tmp_dir': 'automatix_tmp',
    'logger': 'automatix',
    'bundlewrap': False,
    'teamvault': False,
}

configfile = os.path.expanduser(os.getenv('AUTOMATIX_CONFIG', '~/.automatix.cfg.yaml'))
if os.path.isfile(configfile):
    CONFIG.update(read_yaml(configfile))

if os.getenv('AUTOMATIX_SCRIPT_DIR'):
    CONFIG['script_dir'] = os.getenv('AUTOMATIX_SCRIPT_DIR')

if CONFIG.get('logging_lib'):
    log_lib = import_module(CONFIG.get('logging_lib'))
    init_logger = log_lib.init_logger
else:
    from .logger import init_logger

if CONFIG.get('bundlewrap'):
    from bundlewrap.repo import Repository
    from .bundlewrap import BWCommand

    CONFIG['bw_repo'] = Repository(repo_path=os.environ.get('BW_REPO_PATH'))
    cmdClass = BWCommand
else:
    cmdClass = Command

LOG = logging.getLogger(CONFIG['logger'])

SCRIPT_PATH = os.path.expanduser(CONFIG['script_dir'])

if CONFIG['teamvault']:
    import bwtv

    SCRIPT_FIELDS['secrets'] = 'Secrets'


    class UnknownSecretTypeException(Exception):
        pass


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Automation wrapper for bash and python commands.',
        epilog='Explanations and README at https://github.com/seibert-media/automatix',
    )
    parser.add_argument(
        'scriptfile',
        help='Path to scriptfile (yaml), use " -- " if needed to delimit this from argument fields',
    )
    for field in SCRIPT_FIELDS.keys():
        parser.add_argument(
            f'--{field}',
            nargs='*',
            help=f'Use this to set {field} without adding them to the script or to overwrite them. '
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


def _overwrite(script: dict, key: str, data: str):
    script.setdefault(key, {})
    for item in data:
        k, v = item.split('=')
        script[key][k] = v


def get_script(args: argparse.Namespace) -> dict:
    file = args.scriptfile
    if not os.path.isfile(args.scriptfile):
        file = f'{SCRIPT_PATH}/{args.scriptfile}'

    script = read_yaml(file)

    for field in SCRIPT_FIELDS.keys():
        if vars(args).get(field):
            _overwrite(script=script, key=field, data=vars(args)[field])

    return script


def collect_vars(script: dict) -> dict:
    var_dict = script.get('vars', {})
    script['vars'] = var_dict  # just for the case it was empty
    if CONFIG['teamvault']:
        for key, secret in script.get('secrets', {}).items():
            sid, field = secret.split('_')
            if field == 'password':
                var_dict[key] = bwtv.password(sid)
            elif field == 'username':
                var_dict[key] = bwtv.username(sid)
            elif field == 'file':
                var_dict[key] = bwtv.file(sid)
            else:
                raise UnknownSecretTypeException(field)
    for syskey, system in script.get('systems', {}).items():
        var_dict[f'system_{syskey}'] = system
    return var_dict


def main():
    starttime = time()
    args = _arguments()
    init_logger(name=CONFIG['logger'], debug=args.debug)

    script = get_script(args=args)

    variables = collect_vars(script)

    auto = Automatix(
        script=script,
        variables=variables,
        config=CONFIG,
        cmd_class=cmdClass,
        script_fields=SCRIPT_FIELDS,
    )

    auto.run(args=args)
    if 'AUTOMATIX_TIME' in os.environ:
        auto.env.LOG.info(f'The Automatix script took {round(time()-starttime)}s!')
