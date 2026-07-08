# Copyright 2026 NXP
# SPDX-License-Identifier: BSD-3-Clause

import logging
import os
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler

LOG_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_lock        = threading.Lock()
_initialized = False


def setup_logger(verbose: bool = False, log_level: str = None) -> logging.Logger:
    """
    Initialise the root admin logger.

    Console level: DEBUG if --verbose, else INFO (overridden by --log-level).
    File level   : always DEBUG.
    """
    global _initialized
    with _lock:
        if _initialized:
            return logging.getLogger("imx_admin")

        os.makedirs(LOG_DIR, exist_ok=True)

        log_file = os.path.join(LOG_DIR, f"admin_{datetime.now().strftime('%Y%m%d')}.log")

        logger = logging.getLogger("imx_admin")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # ── Console handler ──────────────────────────────────────────────────
        if log_level:
            console_level = getattr(logging, log_level.upper(), None)
            if console_level is None:
                console_level = logging.INFO
                # Can't use logger here (not set up yet), so print directly
                print(f"WARNING: Unknown log level '{log_level}', defaulting to INFO")
        else:
            console_level = logging.DEBUG if verbose else logging.INFO
        ch = logging.StreamHandler()
        ch.setLevel(console_level)
        ch.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
        logger.addHandler(ch)

        # ── File handler (always DEBUG) ───────────────────────────────────────
        fh = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,   # 5 MB per file
            backupCount=3,               # keep 3 rotated files
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(fh)

        _initialized = True
        logger.debug(f"Logger initialised — file: {log_file}  verbose: {verbose}")
        return logger


def get_logger(name: str = "imx_admin") -> logging.Logger:
    """Return (or lazily create) a child logger."""
    if not _initialized:
        setup_logger()
    return logging.getLogger(name)
