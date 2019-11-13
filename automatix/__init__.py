import argparse
import logging
import os
import yaml

from collections import OrderedDict

from .command import Command, AbortException, LOG



CONFIG_PATH = os.getenv('AUTOMATIX_CONFIG_DIR', '~/automatix-config')

CONFIG_FIELDS = OrderedDict()
CONFIG_FIELDS['systems'] = 'Systems'
CONFIG_FIELDS['vars'] = 'Variables'

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


def collect_vars(config: dict) -> dict:
    var_dict = config.get('vars', {})
    config['vars'] = var_dict  # just for the case it was empty
    for syskey, system in config.get('systems', {}).items():
        var_dict[f'system_{syskey}'] = system
    return var_dict


def build_command_list(config: dict, variables: dict, pipeline: str) -> [Command]:
    command_list = []
    for index, cmd in enumerate(config[pipeline]):
        new_cmd = Command(
            pipeline_cmd=cmd,
            index=index,
            systems=config.get('systems', {}),
            variables=variables,
            imports=config.get('imports', []),
        )
        command_list.append(new_cmd)
        if new_cmd.assignment:
            variables[new_cmd.assignment_var] = f'{{{new_cmd.assignment_var}}}'
    return command_list


def print_main_data(config: dict):
    LOG.info(f"\nName: {config['name']}")
    for fieldkey, fieldvalue in CONFIG_FIELDS.items():
        LOG.info(f'\n{fieldvalue}:')
        for key, value in config.get(fieldkey, {}).items():
            LOG.info(f" {key}: {value}")


def print_command_line_steps(command_list: [Command]):
    LOG.info('\nCommandline Steps:')
    for cmd in command_list:
        LOG.info(f"({cmd.index}) [{cmd.orig_key}]: {cmd.get_resolved_value()}")


def execute_pipeline(command_list: [Command], args: argparse.Namespace, start_index: int = 0):
    for cmd in command_list[start_index:]:
        cmd.execute(interactive=args.interactive, force=args.force)


def execute_extra_pipeline(config: dict, variables: dict, pipeline: str):
    try:
        if config.get(pipeline):
            pipeline_list = build_command_list(config=config, variables=variables, pipeline=pipeline)
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

    if args.debug:
        LOG.setLevel(logging.DEBUG)

    config = get_config(args=args)

    for field in CONFIG_FIELDS.keys():
        if vars(args).get(field):
            _overwrite(config=config, key=field, data=vars(args)[field])

    variables = collect_vars(config)

    command_list = build_command_list(config=config, variables=variables, pipeline='pipeline')

    execute_extra_pipeline(config=config, variables=variables, pipeline='always')

    print_main_data(config)
    print_command_line_steps(command_list)
    if args.print_overview:
        exit()

    try:
        execute_pipeline(command_list=command_list, args=args, start_index=int(args.jump_to))
    except AbortException as exc:
        LOG.debug('Abort requested. Cleaning up.')
        execute_extra_pipeline(config=config, variables=variables, pipeline='cleanup')
        LOG.debug('Clean up done. Exiting.')
        exit(int(str(exc)))
    except KeyboardInterrupt:
        LOG.warning('\nAborted by user. Exiting.')
        exit(130)

    execute_extra_pipeline(config=config, variables=variables, pipeline='cleanup')

    LOG.info('---------------------------------------------------------------')
    LOG.info('Automatix finished: Congratulations and have a N.I.C.E. day :-)')
    LOG.info('---------------------------------------------------------------')
