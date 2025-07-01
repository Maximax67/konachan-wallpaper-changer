# Used code from:
# https://github.com/pycontribs/tendo/blob/94462ec914fba04351c9530b69e99ac056b4e156/src/tendo/singleton.py

import os
import sys
import tempfile
from typing import Any

from logger import logger

if sys.platform != "win32":
    import fcntl


class SingleInstanceException(BaseException):
    pass


class SingleInstance:
    """Class that can be instantiated only once per machine"""

    def __init__(self, label: str):
        self.initialized = False
        self.lockfile = os.path.normpath(tempfile.gettempdir() + f"/{label}.lock")
        logger.debug(f"SingleInstance lockfile: {self.lockfile}")

    def __enter__(self) -> "SingleInstance":
        if sys.platform == "win32":
            try:
                # file already exists, we try to remove (in case previous
                # execution was interrupted)
                if os.path.exists(self.lockfile):
                    os.unlink(self.lockfile)
                self.fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except OSError:
                type, e, tb = sys.exc_info()
                if e.errno == 13:  # type: ignore[union-attr]
                    logger.error("Another instance is already running, quitting")
                    raise SingleInstanceException
                raise
        else:  # non Windows
            self.fp = open(self.lockfile, "w")
            self.fp.flush()
            try:
                fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                logger.warning("Another instance is already running, quitting")
                raise SingleInstanceException

        self.initialized = True

        return self

    def __exit__(self, exc_type: Any, exc_value: Any, exc_tb: Any) -> None:
        if not self.initialized:
            return

        try:
            if sys.platform == "win32":
                if hasattr(self, "fd"):
                    os.close(self.fd)
                    os.unlink(self.lockfile)
            else:
                fcntl.lockf(self.fp, fcntl.LOCK_UN)
                if os.path.isfile(self.lockfile):
                    os.unlink(self.lockfile)
        except Exception as e:
            if logger:
                logger.warning(e)

            if exc_value is not None:
                raise e from exc_value

            sys.exit(-1)
