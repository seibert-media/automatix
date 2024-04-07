from logging import Logger
from argparse import Namespace


class PipelineEnvironment:
    def __init__(
            self,
            name: str,
            config: dict,
            systems: dict,
            variables: dict,
            imports: list,
            batch_mode: bool,
            batch_items_count: int,
            batch_index: int,
            cmd_args: Namespace,
            logger: Logger,
    ):
        self.name = name
        self.config = config
        self.systems = systems
        self.vars = variables
        self.imports = imports
        self.batch_mode = batch_mode
        self.batch_items_count = batch_items_count
        self.batch_index = batch_index
        self.cmd_args = cmd_args
        self.LOG = logger

        # This will be set on runtime
        self.command_count = None
