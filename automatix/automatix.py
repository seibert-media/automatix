import sys
from argparse import Namespace
from collections import OrderedDict
from typing import List

from .command import Command, AbortException, SkipBatchItemException, PERSISTENT_VARS, ReloadFromFile
from .config import get_script
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
            batch_index: int,
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
            batch_items_count=script.get('batch_items_count', 1),
            batch_index=batch_index,
            cmd_args=cmd_args,
        )

        self._command_lists: dict = {}

    def command_list(self, pipeline: str) -> list:
        if pipeline == 'main':
            pipeline = 'pipeline'
        if not self._command_lists.get(pipeline):
            self._command_lists[pipeline] = self.build_command_list(pipeline=pipeline)
        return self._command_lists[pipeline]

    def get_command_position(self, index: int, pipeline: str) -> int:
        if pipeline == 'always':
            return index
        if pipeline in ['pipeline', 'main']:
            return index + len(self.command_list('always'))
        if pipeline == 'cleanup':
            return index + len(self.command_list('always')) + len(self.command_list('main'))

    def set_command_count(self):
        if not self.env.command_count:
            self.env.command_count = len(
                self.command_list('always') + self.command_list('main') + self.command_list('cleanup')
            )

    def build_command_list(self, pipeline: str) -> List[Command]:
        command_list = []
        for index, cmd in enumerate(self.script.get(pipeline, [])):
            new_cmd = self.cmd_class(
                cmd=cmd,
                index=index,
                env=self.env,
                pipeline=pipeline,
                position=self.get_command_position(index=index, pipeline=pipeline),
            )
            command_list.append(new_cmd)
            if new_cmd.assignment_var and new_cmd.assignment_var not in self.env.vars:
                self.env.vars[new_cmd.assignment_var] = f'{{{new_cmd.assignment_var}}}'
        return command_list

    def reload_script(self):
        self.script = get_script(args=self.env.cmd_args)
        self._command_lists = {}  # Clear cache

    def print_main_data(self):
        print('\n')
        self.env.LOG.info(' ------ Overview ------')
        for field_key, field_value in self.script_fields.items():
            print()
            self.env.LOG.info(f'{field_value}:')
            for key, value in self.script.get(field_key, {}).items():
                self.env.LOG.info(f" {key}: {value}")

    def print_command_line_steps(self, command_list: List[Command]):
        print()
        self.env.LOG.info('Commandline Steps:')
        for cmd in command_list:
            self.env.LOG.info(f"({cmd.index}) [{cmd.orig_key}]: {cmd.get_resolved_value()}")

    def _execute_command_list(self, name: str, start_index: int, treat_as_main: bool):
        try:
            steps = self.script.get('steps')
            for cmd in self.command_list(name)[start_index:]:
                if treat_as_main:
                    if steps and (self.script['exclude'] == (cmd.index in steps)):
                        # Case 1: exclude is True  and index is in steps => skip
                        # Case 2: exclude is False and index is in steps => execute
                        print()
                        self.env.LOG.notice(f'({cmd.index}) Not selected for execution: skip')
                        continue
                    cmd.execute(interactive=self.env.cmd_args.interactive, force=self.env.cmd_args.force)
                else:
                    cmd.execute()
        except ReloadFromFile as exc:
            print()
            self.env.LOG.info(f'Reload script from file and retry => ({exc.index})')
            self.reload_script()
            self._execute_command_list(name=name, start_index=exc.index, treat_as_main=treat_as_main)

    def execute_pipeline(self, name: str):
        if not self.command_list(name):
            return

        if name == 'main':
            treat_as_main = True
            start_index = self.env.cmd_args.jump_to
        else:
            treat_as_main = False
            start_index = 0

        print()
        self.env.LOG.info('------------------------------')
        self.env.LOG.info(f' --- Start {name.upper()} pipeline ---')

        self._execute_command_list(name=name, start_index=start_index, treat_as_main=treat_as_main)

        print()
        self.env.LOG.info(f' --- End {name.upper()} pipeline ---')
        self.env.LOG.info('------------------------------\n')

    def run(self):
        print('\n')
        self.env.LOG.info('//////////////////////////////////////////////////////////////////////')
        self.env.LOG.info(f"---- {self.script['name']} ----")
        self.env.LOG.info('//////////////////////////////////////////////////////////////////////')

        PERSISTENT_VARS.clear()

        self.execute_pipeline(name='always')

        self.print_main_data()
        self.print_command_line_steps(command_list=self.command_list('main'))
        if self.env.cmd_args.print_overview:
            sys.exit()

        try:
            self.execute_pipeline(name='main')
        except (AbortException, SkipBatchItemException):
            self.env.LOG.debug('Abort requested. Cleaning up.')
            self.execute_pipeline(name='cleanup')
            self.env.LOG.debug('Clean up done. Exiting.')
            raise

        self.execute_pipeline(name='cleanup')

        self.env.LOG.info('---------------------------------------------------------------')
        self.env.LOG.info('Automatix finished: Congratulations and have a N.I.C.E. day :-)')
        self.env.LOG.info('---------------------------------------------------------------')
