from typing import Union
import logging

def setup_logger(logger: Union[str, logging.Logger], level='DEBUG', **kwargs):
    """
    Wrapper to simplify logging setup.
    """
    def mklevel(level: Union[int, str]) -> int:
        if isinstance(level, str):
            level = level.upper()
            return getattr(logging, level)
        else:
            return level
    lvl = mklevel(level)

    if isinstance(logger, str):
        logger = logging.getLogger(logger)

    try:
        # try logzero first, so user gets nice colored logs
        import logzero  # type: ignore
        # TODO meh, default formatter shorthands logging levels making it harder to search errors..
    except ModuleNotFoundError:
        import warnings
        warnings.warn("You might want to install 'logzero' for nice colored logs")

        # ugh. why does it have to be so verbose?
        logger.setLevel(lvl)
        ch = logging.StreamHandler()
        ch.setLevel(lvl)
        FMT = '[%(levelname)s %(name)s %(asctime)s %(filename)s:%(lineno)d] %(message)s'
        ch.setFormatter(logging.Formatter(FMT))
        logger.addHandler(ch)
    else:
        logzero.setup_logger(logger.name, level=lvl)


class LazyLogger(logging.Logger):
    """
    Calling logger = logging.getLogger() on the top level is not safe: it happens before logging configuration (if you do it in main).
    Normally you get around it by defining get_logger() -> Logger, but this is annoying to do every time you want to use logger.
    LazyLogger allows you to use logger = LazyLogger('name') on the top level, and it will be initialized on the first use.
    """
    def __new__(cls, name, level: Union[int, str] = 'DEBUG'):
        logger = logging.getLogger(name)
        # this is called prior to all _log calls so makes sense to do it here?
        def isEnabledFor_lazyinit(*args, logger=logger, orig=logger.isEnabledFor, **kwargs):
            att = 'lazylogger_init_done'
            if not getattr(logger, att, False): # init once, if necessary
                setup_logger(logger, level=level)
                setattr(logger, att, True)
            return orig(*args, **kwargs)

        logger.isEnabledFor = isEnabledFor_lazyinit  # type: ignore[method-assign]
        return logger


def logger(logger, **kwargs) -> logging.Logger:
    return LazyLogger(logger, **kwargs)
