import argparse
import logging
import os
import re
import sys
from collections import OrderedDict
from time import sleep

import yaml

yaml.warnings({'YAMLLoadWarning': False})


def read_yaml(yamlfile: str) -> dict:
    with open(yamlfile) as file:
        return yaml.load(file.read(), Loader=yaml.SafeLoader)


if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata

VERSION = metadata.version('automatix')

DEPRECATED_SYNTAX = {
    # 0: REGEX pattern
    # 1: replacement, formatted with group = re.Match.groups(), e.g. 'something {group[0]} foo'
    # 2: special flags (p: python, b: Bundlewrap, s: replace '{s}' with pipe separated system names)
    (r'({s})_node(?!\w)', 'NODES.{group[0]}', 'bps'),
    (r'{\s*system_(\w*)\s*}', '{{SYSTEMS.{group[0]}}}', ''),
    (r'{\s*const_(\w*)\s*}', '{{CONST.{group[0]}}}', ''),
    (r'(?<!\w)global\s+(\w*)', 'PERSISTENT_VARS[\'{group[0]}\'] = {group[0]}', 'p'),
}

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
    CONFIG['config_file'] = configfile

if os.getenv('AUTOMATIX_SCRIPT_DIR'):
    CONFIG['script_dir'] = os.getenv('AUTOMATIX_SCRIPT_DIR')

LOG = logging.getLogger(CONFIG['logger'])

SCRIPT_PATH = os.path.expanduser(CONFIG['script_dir'])

if CONFIG['teamvault']:
    import bwtv

    SCRIPT_FIELDS['secrets'] = 'Secrets'


    class UnknownSecretTypeException(Exception):
        pass


def arguments() -> argparse.Namespace:
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
        '--vars-file',
        help='Path to a CSV file containing variables for batch processing',
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
    validate_script(script)

    for field in SCRIPT_FIELDS.keys():
        if vars(args).get(field):
            _overwrite(script=script, key=field, data=vars(args)[field])

    return script


def validate_script(script: dict):
    warn = False
    for pipeline in ['always', 'pipeline', 'cleanup']:
        for index, command in enumerate(script.get(pipeline, [])):
            for ckey, entry in command.items():
                prefix = f'[{pipeline}:{index}]'

                if isinstance(entry, dict):
                    warn = True
                    LOG.warning(
                        f'{prefix} Command is not a string! Please use quotes!'
                    )
                    entry = f'{{{next(iter(entry))}}}'

                for pattern, replacement, flags in DEPRECATED_SYNTAX:
                    if 'b' in flags and not CONFIG['bundlewrap']:
                        continue
                    if 'p' in flags and 'python' not in ckey:
                        continue
                    if 's' in flags:
                        match = re.search(pattern.format(s='|'.join(script.get('systems', {}).keys())), entry)
                    else:
                        match = re.search(pattern, entry)
                    if match:
                        warn = True
                        LOG.warning(
                            '{prefix} Using "{match}" is deprecated. Use "{repl}" instead.'.format(
                                prefix=prefix,
                                match=match.group(0),
                                repl=replacement.format(group=match.groups())
                            )
                        )

                break  # there always should be only one entry
    if warn:
        # To give people a chance to see warnings before the following output happens.
        sleep(5)


def collect_vars(script: dict) -> dict:
    var_dict = script.get('vars', {})
    if var_dict is None:
        LOG.warning('Vars section defined, but empty!\nThis is illegal, either remove the section or add variables.')
        var_dict = {}
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
        # DEPRECATED, use SYSTEMS instead
        var_dict[f'system_{syskey}'] = system.replace('hostname!', '')
    return var_dict


def update_script_from_row(row: dict, script: dict, index: int):
    if not row:
        return
    try:
        script['name'] += f" ({index} {row.pop('label')})"
    except KeyError:
        script['name'] += f" ({index})"
    for key, value in row.items():
        assert len(key.split(':')) == 2, \
            'First row in CSV must contain "label" or the field name and key seperated by colons' \
            ' like "label,systems:mysystem,vars:myvar".'
        key_type, key_name = key.split(':')
        assert key_type in SCRIPT_FIELDS.keys(), \
            f'First row in CSV: Field name is \'{key_type}\', but has to be one of {list(SCRIPT_FIELDS.keys())}.'
        script[key_type][key_name] = value
