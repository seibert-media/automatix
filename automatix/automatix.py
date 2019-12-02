import logging

from argparse import Namespace
from collections import OrderedDict
from typing import List

from .command import Command, AbortException
from .environment import PipelineEnvironment


class Automatix:
    def __init__(self, script: dict, variables: dict, config: dict, cmd_class: type, script_fields: OrderedDict):
        self.script = script
        self.script_fields = script_fields
        self.cmdClass = cmd_class
        self.env = PipelineEnvironment(
            config=config,
            systems=script.get('systems', {}),
            variables=variables,
            imports=script.get('imports', []),
            LOG=logging.getLogger(config['logger']),
        )

    def build_command_list(self, pipeline: str) -> List[Command]:
        command_list = []
        for index, cmd in enumerate(self.script[pipeline]):
            new_cmd = self.cmdClass(
                pipeline_cmd=cmd,
                index=index,
                env=self.env,
            )
            command_list.append(new_cmd)
            if new_cmd.assignment:
                self.env.vars[new_cmd.assignment_var] = f'{{{new_cmd.assignment_var}}}'
        return command_list

    def print_main_data(self):
        self.env.LOG.info(f"\nName: {self.script['name']}")
        for field_key, field_value in self.script_fields.items():
            self.env.LOG.info(f'\n{field_value}:')
            for key, value in self.script.get(field_key, {}).items():
                self.env.LOG.info(f" {key}: {value}")

    def print_command_line_steps(self, command_list: List[Command]):
        self.env.LOG.info('\nCommandline Steps:')
        for cmd in command_list:
            self.env.LOG.info(f"({cmd.index}) [{cmd.orig_key}]: {cmd.get_resolved_value()}")

    def execute_pipeline(self, command_list: List[Command], args: Namespace, start_index: int = 0):
        for cmd in command_list[start_index:]:
            cmd.execute(interactive=args.interactive, force=args.force)

    def execute_extra_pipeline(self, pipeline: str):
        try:
            if self.script.get(pipeline):
                pipeline_list = self.build_command_list(pipeline=pipeline)
                self.env.LOG.info('\n------------------------------')
                self.env.LOG.info(f' --- Start {pipeline.upper()} pipeline ---')
                self.execute_pipeline(command_list=pipeline_list, args=Namespace(interactive=False, force=False))
                self.env.LOG.info(f'\n --- End {pipeline.upper()} pipeline ---')
                self.env.LOG.info('------------------------------\n')
        except AbortException as exc:
            exit(int(str(exc)))
        except KeyboardInterrupt:
            self.env.LOG.warning('\nAborted by user. Exiting.')
            exit(130)

    def run(self, args: Namespace):

        command_list = self.build_command_list(pipeline='pipeline')

        self.execute_extra_pipeline(pipeline='always')

        self.print_main_data()
        self.print_command_line_steps(command_list)
        if args.print_overview:
            exit()

        try:
            self.execute_pipeline(command_list=command_list, args=args, start_index=int(args.jump_to))
        except AbortException as exc:
            self.env.LOG.debug('Abort requested. Cleaning up.')
            self.execute_extra_pipeline(pipeline='cleanup')
            self.env.LOG.debug('Clean up done. Exiting.')
            exit(int(str(exc)))
        except KeyboardInterrupt:
            self.env.LOG.warning('\nAborted by user. Exiting.')
            exit(130)

        self.execute_extra_pipeline(pipeline='cleanup')

        self.env.LOG.info('---------------------------------------------------------------')
        self.env.LOG.info('Automatix finished: Congratulations and have a N.I.C.E. day :-)')
        self.env.LOG.info('---------------------------------------------------------------')
