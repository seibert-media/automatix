from logging import Logger


class PipelineEnvironment:
    def __init__(self, config: dict, systems: dict, vars: dict, imports: list, LOG: Logger):
        self.config = config
        self.systems = systems
        self.vars = vars
        self.imports = imports
        self.LOG = LOG
