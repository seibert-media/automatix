import argparse
import logging
import os
import re
import sys
from collections import OrderedDict
from importlib import metadata, import_module
from time import sleep

import yaml

yaml.warnings({'YAMLLoadWarning': False})


def read_yaml(yamlfile: str) -> dict:
    with open(yamlfile) as file:
        return yaml.load(file.read(), Loader=yaml.SafeLoader)


try:
    from argcomplete import autocomplete
    from .bash_completion import ScriptFileCompleter

    bash_completion = True
except ImportError:
    bash_completion = False

VERSION = metadata.version('automatix_cmd')

DEPRECATED_SYNTAX = {
    # 0: REGEX pattern
    # 1: replacement, formatted with group = re.Match.groups(), e.g. 'something {group[0]} foo'
    # 2: special flags (p: python, b: Bundlewrap, s: replace '{s}' with pipe separated system names)
    (r'({s})_node(?!\w)', 'NODES.{group[0]}', 'bps'),  # Removed in 2.0.0
    (r'{\s*system_(\w*)\s*}', '{{SYSTEMS.{group[0]}}}', ''),  # Removed in 2.0.0
    (r'{\s*const_(\w*)\s*}', '{{CONST.{group[0]}}}', ''),  # Removed in 2.0.0
    (r'(?<!\w)global\s+(\w*)', 'PERSISTENT_VARS[\'{group[0]}\'] = {group[0]}', 'p'),
}

SCRIPT_FIELDS = OrderedDict()
SCRIPT_FIELDS['systems'] = 'Systems'
SCRIPT_FIELDS['vars'] = 'Variables'

CONFIG = {
    'script_dir': '~/automatix-config',
    'constants': {},
    'encoding': 'utf-8',
    'import_path': '.',
    'ssh_cmd': 'ssh {hostname} sudo ',
    'remote_tmp_dir': 'automatix_tmp',
    'logger': 'automatix',
    'logfile_dir': 'automatix_logs',
    'bundlewrap': False,
    'teamvault': False,
}

configfile = os.path.expanduser(os.path.expandvars(os.getenv('AUTOMATIX_CONFIG', '~/.automatix.cfg.yaml')))
if os.path.isfile(configfile):
    CONFIG.update(read_yaml(configfile))
    CONFIG['config_file'] = configfile

for key, value in CONFIG.items():
    if not isinstance(value, str):
        continue
    if os.getenv(f'AUTOMATIX_{key.upper()}'):
        CONFIG[key] = os.getenv(f'AUTOMATIX_{key.upper()}')

if CONFIG.get('logging_lib'):
    log_lib = import_module(CONFIG.get('logging_lib'))
    init_logger = log_lib.init_logger  # noqa F401
else:
    from .logger import init_logger  # noqa F401

LOG = logging.getLogger(CONFIG['logger'])

SCRIPT_PATH = os.path.expanduser(os.path.expandvars(CONFIG['script_dir']))

if CONFIG['teamvault']:
    import bwtv

    SCRIPT_FIELDS['secrets'] = 'Secrets'

    class UnknownSecretTypeException(Exception):
        pass

progress_bar = None
PROGRESS_BAR = False
if (CONFIG.get('progress_bar', False) or os.getenv('AUTOMATIX_PROGRESS_BAR', False)) and \
        os.getenv('AUTOMATIX_PROGRESS_BAR', False) not in ['False', 'false']:
    try:
        import python_progress_bar as progress_bar  # noqa F401

        PROGRESS_BAR = True
    except ImportError:
        pass


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Automation wrapper for bash and python commands.',
        epilog='Explanations and README at https://github.com/vanadinit/automatix',
    )
    scriptfile_action = parser.add_argument(
        'scriptfile',
        help='Path to scriptfile (yaml), use " -- " if needed to delimit this from argument fields',
    )
    if bash_completion:
        scriptfile_action.completer = ScriptFileCompleter(script_path=SCRIPT_PATH)

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
        help='Jump to step instead of starting at the beginning',
        type=int,
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
    return parser.parse_args()


def _overwrite(script: dict, key: str, data: list[str]):
    script.setdefault(key, {})
    for item in data:
        k, v = item.split('=')
        script[key][k] = v


def _tupelize(string) -> tuple:
    return tuple([int(i) for i in string.split('.')])


def get_script(args: argparse.Namespace) -> dict:
    s_file = args.scriptfile
    if not os.path.isfile(args.scriptfile):
        s_file = f'{SCRIPT_PATH}/{args.scriptfile}'

    try:
        script = read_yaml(s_file)
        validate_script(script)
    except Exception:
        LOG.exception('Script validation failed! Please fix syntax before retrying!')
        if input('To reload and proceed after fixing type "R" and press Enter.\a') == 'R':
            return get_script(args=args)
        sys.exit(1)

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
        if 's' in flags:
            match = re.search(pattern.format(s='|'.join(script.get('systems', {}).keys())), entry)
        else:
            match = re.search(pattern, entry)
        if match:
            warn += 1
            LOG.warning('{prefix} Using "{match}" is deprecated. Use "{repl}" instead.'.format(
                prefix=prefix,
                match=match.group(0),
                repl=replacement.format(group=match.groups())
            ))
    return warn


def validate_script(script: dict):
    script_required_version = script.get('require_version', '0.0.0')
    if _tupelize(VERSION) < _tupelize(script_required_version):
        LOG.error(f'The script requires minimum version {script_required_version}. We have {VERSION}.')
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
