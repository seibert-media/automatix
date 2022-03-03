from logging import Logger


class PipelineEnvironment:
    def __init__(
            self,
            name: str,
            config: dict,
            systems: dict,
            variables: dict,
            imports: list,
            batch_mode: bool,
            LOG: Logger,
    ):
        self.name = name
        self.config = config
        self.systems = systems
        self.vars = variables
        self.pyvars = PyVarsWrapper()
        self.imports = imports
        self.batch_mode = batch_mode
        self.LOG = LOG


class PyVarsWrapper:
    def __getattr__(self, key: str):
        return self.__dict__[key]

    def __hasattr__(self, key: str):
        return key in self.__dict__

    def __setattr__(self, key: str, value):
        self.__dict__[key] = value
