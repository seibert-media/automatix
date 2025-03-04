from argparse import Namespace
from logging import getLogger

from .config import init_logger


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
        self.LOG = None

        # This will be set at runtime
        self.command_count = None

    def attach_logger(self):
        self.LOG = getLogger(self.config['logger'])

    def reinit_logger(self):
        self.LOG.handlers.clear()
        init_logger(name=self.LOG.name, debug=self.cmd_args.debug)

    def send_status(self, status: str):
        return
