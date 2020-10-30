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
        self.imports = imports
        self.batch_mode = batch_mode
        self.LOG = LOG
