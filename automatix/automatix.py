import logging
from argparse import Namespace
from collections import OrderedDict
from typing import List

from .command import Command, AbortException, SkipBatchItemException, PERSISTENT_VARS
from .environment import PipelineEnvironment


class Automatix:
    def __init__(
            self,
            script: dict,
            variables: dict,
            config: dict,
            cmd_class: type,
            script_fields: OrderedDict,
            cmd_args: Namespace,
    ):
        self.script = script
        self.script_fields = script_fields
        self.cmd_class = cmd_class
        self.env = PipelineEnvironment(
            name=script['name'],
            config=config,
            systems=script.get('systems', {}),
            variables=variables,
            imports=script.get('imports', []),
            batch_mode=script.get('batch_mode', False),
            cmd_args=cmd_args,
            logger=logging.getLogger(config['logger']),
        )

    def build_command_list(self, pipeline: str) -> List[Command]:
        command_list = []
        for index, cmd in enumerate(self.script[pipeline]):
            new_cmd = self.cmd_class(
                cmd=cmd,
                index=index,
                env=self.env,
                pipeline=pipeline,
            )
            command_list.append(new_cmd)
            if new_cmd.assignment_var and new_cmd.assignment_var not in self.env.vars:
                self.env.vars[new_cmd.assignment_var] = f'{{{new_cmd.assignment_var}}}'
        return command_list

    def print_main_data(self):
        self.env.LOG.info('\n\n')
        self.env.LOG.info(f' ------ Overview ------')
        for field_key, field_value in self.script_fields.items():
            self.env.LOG.info(f'\n{field_value}:')
            for key, value in self.script.get(field_key, {}).items():
                self.env.LOG.info(f" {key}: {value}")

    def print_command_line_steps(self, command_list: List[Command]):
        self.env.LOG.info('\nCommandline Steps:')
        for cmd in command_list:
            self.env.LOG.info(f"({cmd.index}) [{cmd.orig_key}]: {cmd.get_resolved_value()}")

    def execute_main_pipeline(self, command_list: List[Command]):
        self.env.LOG.info('\n------------------------------')
        self.env.LOG.info(' --- Start MAIN pipeline ---')

        steps = self.script.get('steps')

        for cmd in command_list[self.env.cmd_args.jump_to:]:
            if steps and (self.script['exclude'] == (cmd.index in steps)):
                # Case 1: exclude is True  and index is in steps => skip
                # Case 2: exclude is False and index is in steps => execute
                self.env.LOG.notice(f'\n({cmd.index}) Not selected for execution: skip')
                continue
            cmd.execute(interactive=self.env.cmd_args.interactive, force=self.env.cmd_args.force)

        self.env.LOG.info('\n --- End MAIN pipeline ---')
        self.env.LOG.info('------------------------------\n')

    def execute_extra_pipeline(self, pipeline: str):
        if self.script.get(pipeline):
            self.env.LOG.info('\n------------------------------')
            self.env.LOG.info(f' --- Start {pipeline.upper()} pipeline ---')
            for cmd in self.build_command_list(pipeline=pipeline):
                cmd.execute()
            self.env.LOG.info(f'\n --- End {pipeline.upper()} pipeline ---')
            self.env.LOG.info('------------------------------\n')

    def run(self):
        self.env.LOG.info('\n\n')
        self.env.LOG.info('//////////////////////////////////////////////////////////////////////')
        self.env.LOG.info(f"---- {self.script['name']} ----")
        self.env.LOG.info('//////////////////////////////////////////////////////////////////////')

        PERSISTENT_VARS.clear()

        command_list = self.build_command_list(pipeline='pipeline')

        self.execute_extra_pipeline(pipeline='always')

        self.print_main_data()
        self.print_command_line_steps(command_list)
        if self.env.cmd_args.print_overview:
            exit()

        try:
            self.execute_main_pipeline(command_list=command_list)
        except (AbortException, SkipBatchItemException):
            self.env.LOG.debug('Abort requested. Cleaning up.')
            self.execute_extra_pipeline(pipeline='cleanup')
            self.env.LOG.debug('Clean up done. Exiting.')
            raise

        self.execute_extra_pipeline(pipeline='cleanup')

        self.env.LOG.info('---------------------------------------------------------------')
        self.env.LOG.info('Automatix finished: Congratulations and have a N.I.C.E. day :-)')
        self.env.LOG.info('---------------------------------------------------------------')
