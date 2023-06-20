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
            cmd_args: Namespace,
            logger: Logger,
    ):
        self.name = name
        self.config = config
        self.systems = systems
        self.vars = variables
        self.imports = imports
        self.batch_mode = batch_mode
        self.cmd_args = cmd_args
        self.LOG = logger
