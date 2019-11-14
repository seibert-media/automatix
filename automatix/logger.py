import logging

from sys import stderr, stdout

NOTICE = 25

C_RED = '\033[91m'
C_BLUE = '\033[94m'
C_END = '\033[0m'


class LevelFilter(logging.Filter):

    def __init__(self, min_level: int = logging.DEBUG, max_level: int = logging.WARNING) -> None:
        super().__init__()
        self._min_level = min_level
        self._max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return self._min_level <= record.levelno <= self._max_level


class ErrorFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno < logging.WARNING:
            return logging.Formatter.format(self, record)

        original_format = self._style._fmt
        self._style._fmt = C_RED + '%(name)s: ' + original_format + C_END

        formatted_record = logging.Formatter.format(self, record)
        self._style._fmt = original_format
        return formatted_record


class ConsoleFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno != NOTICE:
            return logging.Formatter.format(self, record)

        original_format = self._style._fmt
        self._style._fmt = C_BLUE + original_format + C_END

        formatted_record = logging.Formatter.format(self, record)
        self._style._fmt = original_format
        return formatted_record


def init_logger(name: str = 'automatix', debug: bool = False):
    log = logging.getLogger(name=name)
    if log.hasHandlers():
        return

    log.setLevel(logging.DEBUG)  # accept everything and let handlers decide

    for handler in _setup_handlers(debug=debug):
        log.addHandler(handler)


def _setup_handlers(debug: bool = False) -> [logging.Handler]:
    handlers = []
    console_handler = logging.StreamHandler(stream=stdout)
    console_handler.setLevel(logging.DEBUG)
    error_handler = logging.StreamHandler(stream=stderr)
    error_handler.setLevel(logging.WARNING)

    handlers.append(error_handler)
    handlers.append(console_handler)

    if debug:
        min_level = logging.DEBUG
        base_format = '%(asctime)s [ %(levelname)s ] %(message)s (%(filename)s:%(lineno)d)'
    else:
        min_level = logging.INFO
        base_format = '%(message)s'
    console_handler.addFilter(LevelFilter(min_level=min_level, max_level=NOTICE))
    console_handler.setFormatter(ConsoleFormatter(fmt=base_format))
    error_handler.setFormatter(ErrorFormatter(fmt=base_format))

    return handlers


def _patch_add_notice_level_to_logging() -> None:
    logging.addLevelName(NOTICE, 'NOTICE')
    logging.Logger.notice = _notice


def _notice(self, msg, *args, **kwargs):
    if self.isEnabledFor(NOTICE):
        self._log(NOTICE, msg, args, **kwargs)


_patch_add_notice_level_to_logging()
