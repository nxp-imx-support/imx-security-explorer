# Copyright 2026 NXP
# SPDX-License-Identifier: BSD-3-Clause

"""
admin_gui.py — Entry point for the i.MX Security Explorer Admin GUI.

This module:
                  1. Parses command-line arguments (--verbose, --log-level).
                  2. Initialises the logging system via setup_logger() so all child loggers
                     in the gui/* modules are ready before any widget is constructed.
                  3. Creates the QApplication and MainWindow, then enters the Qt event loop.

Usage (via the launcher script — recommended):
                    ./run_admin.sh [--verbose]

Usage (manual, with venv activated):
                    python3 admin_gui.py [--verbose] [--log-level DEBUG|INFO|WARNING|ERROR]
"""

import argparse
import os
import sys

# Ensure the admin/ directory is the first entry on sys.path so that
# 'from utils import ...' and 'from logger import ...' resolve correctly
# regardless of the working directory from which the script is launched.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import setup_logger, get_logger

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

# Import the three top-level tab widgets.
from gui.soc_tab          import SocTab
from gui.feature_usecase_tab import FeatureUseCaseTab
from gui.doc_tab          import DocTab


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """
    Top-level application window.

    Contains a single QTabWidget with three tabs:
        • SoCs                — manage data/socs.yaml
        • Features & Use-Cases — manage config.yaml features / use-cases sections
        • Documents           — manage data/documents/<feature>.yaml files

    Each tab is a self-contained widget that handles its own data loading,
    display, and CRUD operations.  They do not communicate directly with each
    other; they all read from and write to the same YAML files on disk.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("i.MX Security Explorer — Admin")
        self.setMinimumSize(1000, 640)   # sensible minimum so no content is clipped

        tabs = QTabWidget()
        tabs.addTab(SocTab(),            "SoCs")
        tabs.addTab(FeatureUseCaseTab(), "Features & Use-Cases")
        tabs.addTab(DocTab(),            "Documents")
        self.setCentralWidget(tabs)


# ── Application entry point ───────────────────────────────────────────────────

def main() -> None:
    """
    Parse arguments, set up logging, build the Qt application, and run it.

    Exit codes:
        The process exit code is whatever sys.exit() receives from app.exec()
        (0 on normal close, non-zero on error).
    """
    parser = argparse.ArgumentParser(
        description="i.MX Security Explorer — Admin GUI"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG-level console logging (shorthand for --log-level DEBUG)."
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Override the console log level explicitly."
                " Takes precedence over --verbose."
    )
    args = parser.parse_args()

    # Initialise the root logger before constructing any widget so that
    # log calls inside tab __init__ methods are captured from the start.
    setup_logger(verbose=args.verbose, log_level=args.log_level)
    log = get_logger("imx_admin.gui")
    log.info("Admin GUI started")

    # Create the Qt application object.  sys.argv is passed so Qt can process
    # any platform-specific arguments (e.g. display server options on Linux).
    app = QApplication(sys.argv)

    # "Fusion" gives a consistent cross-platform appearance and works well
    # with both light and dark system themes.
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    # app.exec() enters the Qt event loop and blocks until the window is closed.
    # sys.exit() ensures the process exits with Qt's return code.
    sys.exit(app.exec())


if __name__ == "__main__":
    main()