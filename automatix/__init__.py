import argparse
import os
import yaml

from collections import OrderedDict

from .command import Command, AbortException
from .logger import LOG, init_logger

SCRIPT_PATH = os.getenv('AUTOMATIX_SCRIPTS_DIR', '~/automatix-config')

SCRIPT_FIELDS = OrderedDict()
SCRIPT_FIELDS['systems'] = 'Systems'
SCRIPT_FIELDS['vars'] = 'Variables'

yaml.warnings({'YAMLLoadWarning': False})


def _arguments():
    parser = argparse.ArgumentParser(
        description='Process automation tool',
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
    scriptfile = args.scriptfile
    if not os.path.isfile(args.scriptfile):
        file = f'{SCRIPT_PATH}/{args.scriptfile}'

    script = read_script(scriptfile)

    for field in SCRIPT_FIELDS.keys():
        if vars(args).get(field):
            _overwrite(script=script, key=field, data=vars(args)[field])

    return script


def read_script(scriptfile: str) -> dict:
    with open(scriptfile) as file:
        return yaml.load(file.read())


def collect_vars(script: dict) -> dict:
    var_dict = script.get('vars', {})
    script['vars'] = var_dict  # just for the case it was empty
    for syskey, system in script.get('systems', {}).items():
        var_dict[f'system_{syskey}'] = system
    return var_dict


def build_command_list(script: dict, variables: dict, pipeline: str) -> [Command]:
    command_list = []
    for index, cmd in enumerate(script[pipeline]):
        new_cmd = Command(
            pipeline_cmd=cmd,
            index=index,
            systems=script.get('systems', {}),
            variables=variables,
            imports=script.get('imports', []),
        )
        command_list.append(new_cmd)
        if new_cmd.assignment:
            variables[new_cmd.assignment_var] = f'{{{new_cmd.assignment_var}}}'
    return command_list


def print_main_data(script: dict):
    LOG.info(f"\nName: {script['name']}")
    for fieldkey, fieldvalue in SCRIPT_FIELDS.items():
        LOG.info(f'\n{fieldvalue}:')
        for key, value in script.get(fieldkey, {}).items():
            LOG.info(f" {key}: {value}")


def print_command_line_steps(command_list: [Command]):
    LOG.info('\nCommandline Steps:')
    for cmd in command_list:
        LOG.info(f"({cmd.index}) [{cmd.orig_key}]: {cmd.get_resolved_value()}")


def execute_pipeline(command_list: [Command], args: argparse.Namespace, start_index: int = 0):
    for cmd in command_list[start_index:]:
        cmd.execute(interactive=args.interactive, force=args.force)


def execute_extra_pipeline(script: dict, variables: dict, pipeline: str):
    try:
        if script.get(pipeline):
            pipeline_list = build_command_list(script=script, variables=variables, pipeline=pipeline)
            LOG.info('\n------------------------------')
            LOG.info(f' --- Start {pipeline.upper()} pipeline ---')
            execute_pipeline(command_list=pipeline_list, args=argparse.Namespace(interactive=False, force=False))
            LOG.info(f'\n --- End {pipeline.upper()} pipeline ---')
            LOG.info('------------------------------\n')
    except AbortException as exc:
        exit(int(str(exc)))
    except KeyboardInterrupt:
        LOG.warning('\nAborted by user. Exiting.')
        exit(130)


def main():
    args = _arguments()
    init_logger(debug=args.debug)

    script = get_script(args=args)

    for field in SCRIPT_FIELDS.keys():
        if vars(args).get(field):
            _overwrite(script=script, key=field, data=vars(args)[field])

    variables = collect_vars(script)

    command_list = build_command_list(script=script, variables=variables, pipeline='pipeline')

    execute_extra_pipeline(script=script, variables=variables, pipeline='always')

    print_main_data(script)
    print_command_line_steps(command_list)
    if args.print_overview:
        exit()

    try:
        execute_pipeline(command_list=command_list, args=args, start_index=int(args.jump_to))
    except AbortException as exc:
        LOG.debug('Abort requested. Cleaning up.')
        execute_extra_pipeline(script=script, variables=variables, pipeline='cleanup')
        LOG.debug('Clean up done. Exiting.')
        exit(int(str(exc)))
    except KeyboardInterrupt:
        LOG.warning('\nAborted by user. Exiting.')
        exit(130)

    execute_extra_pipeline(script=script, variables=variables, pipeline='cleanup')

    LOG.info('---------------------------------------------------------------')
    LOG.info('Automatix finished: Congratulations and have a N.I.C.E. day :-)')
    LOG.info('---------------------------------------------------------------')
