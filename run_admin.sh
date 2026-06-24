#!/usr/bin/env bash
# run_admin.sh — Launcher for the i.MX Security Explorer Admin GUI.
#
# What this script does (in order)
# ─────────────────────────────────
#  1. Verifies that requirements.txt and admin_gui.py exist.
#  2. Refuses to run if the shell is already inside a virtual environment
#     (prevents venv-inside-venv confusion).
#  3. Finds a Python 3.10+ interpreter on PATH.
#  4. Creates admin/venv/ on first run (skips if it already exists).
#  5. Activates the venv.
#  6. Upgrades pip and installs / syncs all dependencies from requirements.txt.
#  7. Launches admin_gui.py, forwarding any extra arguments (e.g. --verbose).
#  8. Deactivates the venv on exit (via an EXIT trap so cleanup always runs,
#     even if the GUI crashes or the script is interrupted with Ctrl-C).
#
# Usage
# ─────
#   ./run_admin.sh              # normal launch
#   ./run_admin.sh --verbose    # enable DEBUG console logging
#   ./run_admin.sh --log-level WARNING
#
# All arguments after the script name are forwarded verbatim to admin_gui.py.

set -euo pipefail   # -e exit on error, -u treat unset vars as errors,
                    # -o pipefail propagate pipe failures

# Resolve absolute path to admin/ regardless of where the script is invoked from.
ADMIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/admin" && pwd)"
VENV_DIR="${ADMIN_DIR}/venv"
REQUIREMENTS="${ADMIN_DIR}/requirements.txt"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

# ── EXIT trap: always deactivate the venv ─────────────────────────────────────
# This flag is set to true only after a successful activation so that the trap
# does not attempt to call `deactivate` when the venv was never activated
# (e.g. if the script exits during the sanity-check phase).
VENV_ACTIVATED=false

cleanup() {
  if [ "${VENV_ACTIVATED}" = true ]; then
    info "Deactivating virtual environment…"
    deactivate 2>/dev/null || true   # `|| true` so the trap never fails
    success "Virtual environment deactivated."
  fi
}

trap cleanup EXIT

# ── 1. Sanity checks ──────────────────────────────────────────────────────────
# Fail fast with a clear message rather than a confusing Python traceback.

if [ ! -f "${REQUIREMENTS}" ]; then
  error "requirements.txt not found at: ${REQUIREMENTS}"
  exit 1
fi

if [ ! -f "${ADMIN_DIR}/admin_gui.py" ]; then
  error "admin_gui.py not found at: ${ADMIN_DIR}/admin_gui.py"
  exit 1
fi

# ── 2. Refuse to run inside an existing virtual environment ───────────────────
# VIRTUAL_ENV is set by `source venv/bin/activate`; its presence means the
# user's shell is already in a venv.  Nesting venvs causes subtle path and
# package-resolution bugs.
if [ -n "${VIRTUAL_ENV:-}" ]; then
  warn "You are already inside a virtual environment: ${VIRTUAL_ENV}"
  warn "Please deactivate it first ('deactivate') and re-run this script."
  exit 1
fi

# ── 3. Locate a suitable Python interpreter ───────────────────────────────────
# Try `python3` first, then `python`.  PySide6 requires Python 3.10+.
PYTHON_BIN=""
for candidate in python3 python; do
  if command -v "${candidate}" &>/dev/null; then
    version=$("${candidate}" -c 'import sys; print(sys.version_info >= (3,10))')
    if [ "${version}" = "True" ]; then
      PYTHON_BIN="${candidate}"
      break
    fi
  fi
done

if [ -z "${PYTHON_BIN}" ]; then
  error "Python 3.10+ is required but could not be found on PATH."
  exit 1
fi

PY_VERSION=$("${PYTHON_BIN}" --version 2>&1)
info "Using ${PY_VERSION} (${PYTHON_BIN})"

# ── 4. Create the virtual environment if it does not exist ────────────────────
# On subsequent runs this step is skipped, keeping startup time short.
if [ ! -d "${VENV_DIR}" ]; then
  info "Creating virtual environment at ${VENV_DIR} …"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  success "Virtual environment created."
else
  info "Virtual environment already exists at ${VENV_DIR}"
fi

# ── 5. Activate the virtual environment ──────────────────────────────────────
info "Activating virtual environment…"
# shellcheck source=/dev/null — tells shellcheck not to follow the dynamic path
source "${VENV_DIR}/bin/activate"
VENV_ACTIVATED=true
success "Virtual environment activated."

# ── 6. Install / sync dependencies ───────────────────────────────────────────
# `pip install -r requirements.txt` is idempotent — it upgrades or installs
# only what has changed, so subsequent launches are fast.
# Upgrading pip first avoids "pip is out of date" warnings that can obscure
# real error output.
info "Installing/updating dependencies from requirements.txt…"
pip install --quiet --upgrade pip
pip install --quiet -r "${REQUIREMENTS}"
success "Dependencies are up to date."

# ── 7. Launch the admin GUI ───────────────────────────────────────────────────
# cd into admin/ so that relative imports inside admin_gui.py resolve correctly.
# "$@" forwards all arguments passed to this script (e.g. --verbose) to Python.
info "Launching i.MX Security Explorer admin tool…"
echo ""
cd "${ADMIN_DIR}"
python3 admin_gui.py "$@"
# The EXIT trap (cleanup) runs automatically after python3 returns.