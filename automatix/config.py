import argparse
import logging
import os
import re
import sys
from collections import OrderedDict
from importlib import metadata, import_module
from time import sleep

from .colors import red
from .helpers import read_yaml, selector

try:
    from argcomplete import autocomplete
    from .bash_completion import ScriptFileCompleter, ScriptFieldCompleter

    bash_completion = True
except ImportError:
    bash_completion = False

VERSION = metadata.version('automatix')

DEPRECATED_SYNTAX = {
    # 0: REGEX pattern
    # 1: replacement, formatted with group = re.Match.groups(), e.g. 'something {group[0]} foo'
    # 2: special flags (p: python, b: Bundlewrap, s: replace '{s}' with pipe separated system names, r: already removed)
    (r'({s})_node(?!\w)', 'NODES.{group[0]}', 'bpsr'),  # Removed in 2.0.0
    (r'{\s*system_(\w*)\s*}', '{{SYSTEMS.{group[0]}}}', 'r'),  # Removed in 2.0.0
    (r'{\s*const_(\w*)\s*}', '{{CONST.{group[0]}}}', 'r'),  # Removed in 2.0.0
    (r'(?<!\w)global\s+(\w*)', 'PERSISTENT_VARS[\'{group[0]}\'] = {group[0]}', 'pr'),  # Removed in 2.4.0
    (r'(?<!\w)vars\[[\'"](\w+)[\'"]\]', 'VARS.{group[0]}', 'pr'),  # Changed vars -> VARS in 2.6.0
    (r'(?<!\w)a_vars\[[\'"](\w+)[\'"]\]', 'VARS.{group[0]}', 'p'),  # Changed a_vars -> VARS in 2.6.0
}

SCRIPT_FIELDS = OrderedDict()
SCRIPT_FIELDS['systems'] = 'Systems'
SCRIPT_FIELDS['vars'] = 'Variables'

CONFIG = {
    'script_dir': '~/automatix-config',
    'constants': {},
    'encoding': 'utf-8',
    'import_path': '.',
    'bash_path': '/bin/bash',
    'ssh_cmd': 'ssh {hostname} sudo ',
    'remote_tmp_dir': 'automatix_tmp',
    'logger': 'automatix',
    'logfile_dir': 'automatix_logs',
    'bundlewrap': False,
    'teamvault': False,
    'progress_bar': False,
    'startup_script': '',
}

MAGIC_SELECTION_INT = -999999999  # Some number nobody would normally type to mark that selection is wanted.

configfile = os.path.expanduser(os.path.expandvars(os.getenv('AUTOMATIX_CONFIG', '~/.automatix.cfg.yaml')))
if os.path.isfile(configfile):
    CONFIG.update(read_yaml(configfile))
    CONFIG['config_file'] = configfile

for c_key, c_value in CONFIG.items():
    env_value = os.getenv(f'AUTOMATIX_{c_key.upper()}')
    if not env_value:
        continue

    if isinstance(c_value, bool) and env_value.lower() in ['false', 'true']:
        CONFIG[c_key] = True if env_value.lower() == 'true' else False
        continue

    if isinstance(c_value, str):
        CONFIG[c_key] = env_value
        continue

    print(red(f'Warning: environment variable "AUTOMATIX_{c_key.upper()}" ignored: wrong value type!'))
    sleep(2)

if CONFIG.get('logging_lib'):
    log_lib = import_module(CONFIG.get('logging_lib'))
    init_logger = log_lib.init_logger  # noqa F401
else:
    from .logger import init_logger  # noqa F401

LOG = logging.getLogger(CONFIG['logger'])

SCRIPT_DIR = os.path.expanduser(os.path.expandvars(CONFIG['script_dir']))

if CONFIG['teamvault']:
    import bwtv

    SCRIPT_FIELDS['secrets'] = 'Secrets'


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Automation wrapper for bash and python commands.',
        epilog='Explanations and README at https://github.com/seibert-media/automatix',
    )
    scriptfile_action = parser.add_argument(
        'scriptfile',
        help='Path to scriptfile (yaml), use " -- " if needed to delimit this from argument fields',
    )
    if bash_completion:
        scriptfile_action.completer = ScriptFileCompleter(script_dir=SCRIPT_DIR)

    for field in SCRIPT_FIELDS.keys():
        field_action = parser.add_argument(
            f'--{field}',
            nargs='+',
            help=f'Use this to set {field} without adding them to the script or to overwrite them. '
                 f'You can specify multiple {field} like: --{field} v1=string1 v2=string2 v3=string3',
        )
        if bash_completion:
            field_action.completer = ScriptFieldCompleter(script_dir=SCRIPT_DIR)
    parser.add_argument(
        '--vars-file',
        help='Path to a CSV file containing variables for batch processing',
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run CSV file entries parallel in screen sessions; only valid with --vars-file. '
             'GNU screen has to be installed. See EXTRAS section in README.',
    )
    parser.add_argument(
        '--print-overview', '-p',
        action='store_true',
        help='Just print command pipeline overview with indices then exit without executing the commandline. '
             'Note that the *always pipeline* will be executed beforehand.',
    )
    parser.add_argument(
        '--jump-to', '-j',
        help='Jump to step instead of starting at the beginning. Empty argument shows an interactive selection',
        type=int,
        nargs='?',
        const=MAGIC_SELECTION_INT,  # This is to provide selection.
        default=0,
    )
    parser.add_argument(
        '--steps', '-s',
        help='Only execute these steps (comma-separated indices) or exclude steps (prepend "e")',
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
    if bash_completion:
        autocomplete(parser)
    return parser


def arguments(args: list[str] = None) -> argparse.Namespace:
    return create_parser().parse_args(args=args)


def _overwrite(script: dict, key: str, data: list[str]):
    script.setdefault(key, {})
    for item in data:
        k, v = item.split('=')
        script[key][k] = v


def _tupelize(string) -> tuple:
    return tuple([int(i) for i in string.split('.')])


def search_script(name: str) -> str:
    paths = []
    for dirpath, dirnames, filenames in os.walk(SCRIPT_DIR):
        for filename in filenames:
            if filename == name:
                path = str(os.path.join(dirpath, filename))
                paths.append((path, path))  # Second one is the label for the selector
    return selector(entries=paths, message='Script found at multiple locations. Please choose:')


def get_script_path(name: str):
    s_file = name
    LOG.debug(f'Scriptfile input: {s_file}')
    # First try relative path
    if not os.path.isfile(s_file):
        LOG.debug('Script not found at relative path')
        s_file = f'{SCRIPT_DIR}/{name}'
    # Second try relative path from SCRIPT_DIR
    if not os.path.isfile(s_file):
        LOG.debug('Script not found at relative path from SCRIPT_DIR')
        # Third search and offer selection
        s_file = search_script(name=name)
    if not s_file:
        LOG.debug('Script not found at all.')
        raise ValueError('Script not found')
    LOG.notice(f'Script found at {s_file}.')
    return s_file


def get_script(args: argparse.Namespace) -> dict:
    s_file = get_script_path(name=args.scriptfile)

    try:
        script = read_yaml(s_file)
        validate_script(script)
    except Exception:
        LOG.exception('Script validation failed! Please fix syntax before retrying!')
        if input('To reload and proceed after fixing type "R" and press Enter.\a') == 'R':
            return get_script(args=args)
        sys.exit(1)

    script['_script_file_path'] = s_file

    if args.steps:
        exclude = script['_exclude'] = args.steps.startswith('e')
        script['_steps'] = {int(s) for s in (args.steps[1:] if exclude else args.steps).split(',')}

    for field in SCRIPT_FIELDS.keys():
        if vars(args).get(field):
            _overwrite(script=script, key=field, data=vars(args)[field])

    return script


def check_deprecated_syntax(ckey: str, entry: str, script: dict, prefix: str) -> int:
    warn = 0
    if isinstance(entry, dict):
        warn += 1
        LOG.warning(f'{prefix} Command is not a string! Please use quotes!')
        entry = f'{{{next(iter(entry))}}}'

    for pattern, replacement, flags in DEPRECATED_SYNTAX:
        if 'b' in flags and not CONFIG['bundlewrap']:
            continue
        if 'p' in flags and 'python' not in ckey:
            continue
        if 's' in flags and script.get('systems'):
            match = re.search(pattern.format(s='|'.join(script['systems'].keys())), entry)
        else:
            match = re.search(pattern, entry)
        if match:
            warn += 1
            LOG.warning('{prefix} Using "{match}" {state}. Use "{repl}" instead.'.format(
                prefix=prefix,
                match=match.group(0),
                repl=replacement.format(group=match.groups()),
                state='does not work any longer' if 'r' in flags else 'is deprecated',
            ))
    return warn


def check_version(version_str: str):
    installed_version = _tupelize(VERSION)

    for condition in version_str.split(','):
        match = re.match(pattern=r'([><=!~]{0,2})\s*((\d+\.){0,3}\d+)', string=condition.strip())
        operator = match.group(1)
        required_version = _tupelize(match.group(2))

        match operator:
            case '==':
                assert installed_version == required_version
            case '!=':
                assert installed_version != required_version
            case '>=' | '':
                assert installed_version >= required_version
            case '<=':
                assert installed_version <= required_version
            case '>':
                assert installed_version > required_version
            case '<':
                assert installed_version < required_version
            case '~=':
                assert installed_version[:len(required_version) - 1] == required_version[:-1]
                assert installed_version >= required_version
            case _:
                raise SyntaxError(f'Unknown operator "{operator}"')


def validate_script(script: dict):
    version_str = script.get('require_version', '0.0.0')
    try:
        check_version(version_str=version_str)
    except AssertionError:
        LOG.error(f'The script requires version {version_str}. We have {VERSION}.')
        sys.exit(1)

    warn = 0
    for pipeline in ['always', 'pipeline', 'cleanup']:
        for index, command in enumerate(script.get(pipeline, [])):
            for ckey, entry in command.items():
                warn += check_deprecated_syntax(ckey=ckey, entry=entry, script=script, prefix=f'[{pipeline}:{index}]')
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
    return var_dict


def update_script_from_row(row: dict, script: dict, index: int):
    if not row:
        return

    group = row.pop('group', None)
    label = row.pop('label', None)

    ids = [_id for _id in [group, str(index), label] if _id]
    script['name'] += f" ({' | '.join(ids)})"

    for key, value in row.items():
        assert len(key.split(':')) == 2, \
            'First row in CSV must contain "label" or the field name and key seperated by colons' \
            ' like "label,systems:mysystem,vars:myvar".'
        key_type, key_name = key.split(':')
        assert key_type in SCRIPT_FIELDS.keys(), \
            f'First row in CSV: Field name is \'{key_type}\', but has to be one of {list(SCRIPT_FIELDS.keys())}.'
        script[key_type][key_name] = value


class UnknownSecretTypeException(Exception):
    pass
