import logging

NOTICE = 25


def _patch_add_notice_level_to_logging() -> None:
    logging.addLevelName(NOTICE, 'NOTICE')
    logging.Logger.notice = _notice


def _notice(self, msg, *args, **kwargs):
    if self.isEnabledFor(NOTICE):
        self._log(NOTICE, msg, args, **kwargs)


_patch_add_notice_level_to_logging()
LOG = logging.getLogger('automatix')
LOG.setLevel(logging.DEBUG)
