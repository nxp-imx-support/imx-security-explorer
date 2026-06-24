"""
gui/__init__.py — Package initialiser for the admin GUI sub-package.

Ensures that the admin/ directory (one level above this file) is on sys.path
before any sibling module (soc_tab, feature_usecase_tab, doc_tab) is imported.
This allows those modules to use bare imports such as:

    from utils import load_socs, save_socs
    from logger import get_logger

without requiring the caller to manipulate sys.path themselves.

This approach is safe to run multiple times — the path entry is only inserted
if it is not already present.
"""

import sys
import os

# Resolve the absolute path to admin/ and prepend it to sys.path exactly once.
_admin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _admin_dir not in sys.path:
    sys.path.insert(0, _admin_dir)