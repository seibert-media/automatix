from argparse import Namespace
from logging import getLogger
from pathlib import Path

from .config import init_logger
from .helpers import empty_queued_input_data
from .progress_bar import block_progress_bar, draw_progress_bar


class AttributedDict(dict):
    def __getattr__(self, key: str):
        if key in self:
            return self[key]
        raise AttributeError

    def __hasattr__(self, key: str):
        return key in self

    def __setattr__(self, key: str, value):
        self[key] = value


class AttributedDummyDict(AttributedDict):
    def __init__(self, name: str, *args):
        super().__init__(*args)
        self.__name__ = name

    def __getattr__(self, key: str):
        return self[key]

    def __getitem__(self, item):
        try:
            return super().__getitem__(item)
        except KeyError:
            return f'{{{self.__name__}.{item}}}'


class PipelineEnvironment:
    def __init__(
            self,
            config: dict,
            script: dict,
            variables: dict,
            batch_index: int,
            cmd_args: Namespace,
    ):
        self.config = config
        self.script = script
        self.vars = AttributedDict(variables)
        self.batch_index = batch_index
        self.cmd_args = cmd_args

        self.name = script['name']
        self.script_file_path = Path(script['_script_file_path'])
        self.systems = script.get('systems', {})
        self.batch_mode = script.get('_batch_mode', False)
        self.batch_items_count = script.get('_batch_items_count', 1)

        self.LOG = None
        self.auto_file = None

        # This will be set at runtime
        self.command_count = None

    def attach_logger(self):
        self.LOG = getLogger(self.config['logger'])

    def reinit_logger(self):
        self.LOG.handlers.clear()
        init_logger(name=self.LOG.name, debug=self.cmd_args.debug)

    def send_status(self, status: str):
        # In parallel processing this method is overwritten to communicate with the UI
        return

    def interact(self, question: str, progress_portion: int = None) -> str:
        if progress_portion is not None and self.config['progress_bar']:
            block_progress_bar(progress_portion)
        self.send_status('user_input_add')
        empty_queued_input_data()
        answer = input(question)
        self.send_status('user_input_remove')
        if progress_portion is not None and self.config['progress_bar']:
            draw_progress_bar(progress_portion)
        return answer
