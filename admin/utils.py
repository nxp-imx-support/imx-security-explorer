import os
import yaml
import logging
import tempfile

log = logging.getLogger("imx_admin.utils")

# Directory paths for configuration and data files
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "data", "config.yaml")
SOCS_PATH   = os.path.join(BASE_DIR, "data", "socs.yaml")
DOCS_DIR    = os.path.join(BASE_DIR, "data", "documents")


def load_yaml(path: str) -> dict:
    """
    Load and parse a YAML file from the given path.
    
    Returns an empty dict if the file is empty or contains only whitespace.
    Raises FileNotFoundError, OSError, or yaml.YAMLError on failure.
    """
    log.debug(f"Loading YAML: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        log.error(f"File not found: {path}")
        raise
    except OSError as exc:
        log.error(f"Cannot read '{path}': {exc}")
        raise
    except yaml.YAMLError as exc:
        log.error(f"YAML parse error in '{path}': {exc}")
        raise

def save_yaml(path: str, data: dict) -> None:
    """
    Atomically save a dictionary as YAML to the given path.
    
    Uses a temporary file and os.replace() to ensure the write is atomic,
    preventing corruption if the process is interrupted. Creates parent
    directories if they don't exist.
    """
    log.debug(f"Saving YAML: {path}")
    dir_name = os.path.dirname(path)
    if not dir_name:
        dir_name = "."
    
    # Ensure the target directory exists
    os.makedirs(dir_name, exist_ok=True)
    
    tmp_path = None
    try:
        # Write to a temporary file in the same directory
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=dir_name, delete=False, suffix=".tmp"
        ) as tmp:
            yaml.dump(data, tmp, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)
            tmp_path = tmp.name
        # Atomically replace the target file with the temp file
        os.replace(tmp_path, path)
    except Exception as exc:
        # Clean up orphaned temp file before re-raising
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        log.error(f"Failed to write '{path}': {exc}")
        raise

def load_config() -> dict:
    """Load the main application configuration from config.yaml."""
    return load_yaml(CONFIG_PATH)


def load_config_raw() -> dict:
    """
    Return the full config dict for mutation and write-back via save_config().

    Callers that intend to modify the config in-place and then call
    save_config() should use this function rather than load_config(), making
    the intent explicit at the call site.
    """
    return load_yaml(CONFIG_PATH)


def save_config(config: dict) -> None:
    """Save the application configuration dict back to config.yaml."""
    save_yaml(CONFIG_PATH, config)


def load_socs() -> list:
    """
    Load the list of SoCs (System on Chips) from socs.yaml.
    
    Returns an empty list if the 'socs' key is missing or not a list.
    """
    data = load_yaml(SOCS_PATH)
    socs = data.get("socs", [])
    if not isinstance(socs, list):
        log.error(f"'socs' in {SOCS_PATH} is not a list (got {type(socs).__name__}). "
                  f"Returning empty list.")
        return []
    return socs


def save_socs(socs: list) -> None:
    """Save the list of SoCs back to socs.yaml under the 'socs' key."""
    save_yaml(SOCS_PATH, {"socs": socs})

# ── CLI helpers ───────────────────────────────────────────────────────────────
# NOTE: the four functions below (dropdown, multi_select, input_with_default,
# divider) are not imported by any GUI module.  If no CLI script outside this
# set references them, they can be safely removed.

def dropdown(prompt: str, options: list, allow_empty: bool = False):
    """
    Display a numbered single-select menu in the terminal.
    
    Args:
        prompt: The question or instruction to display
        options: List of strings or dicts with 'id' and 'name' keys
        allow_empty: If True, allows selecting "0" to return None
    
    Returns the selected id string (or None if allow_empty and user chose 0).
    """
    print(f"\n{prompt}")
    if allow_empty:
        print("  0. (none)")
    for i, opt in enumerate(options, 1):
        if isinstance(opt, dict):
            print(f"  {i}. {opt['name']}  [{opt['id']}]")
        else:
            print(f"  {i}. {opt}")
    while True:
        raw = input("Select: ").strip()
        if allow_empty and raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            selected = options[int(raw) - 1]
            return selected["id"] if isinstance(selected, dict) else selected
        print("  Invalid — try again.")


def multi_select(prompt: str, options: list, current: list = None) -> list:
    """
    Display a numbered multi-select menu in the terminal.
    
    Args:
        prompt: The question or instruction to display
        options: List of strings or dicts with 'id' and 'name' keys
        current: The current selection to display and fall back to
    
    User enters space-separated numbers. Pressing Enter with no input keeps
    the current selection. Returns a list of id strings.
    """
    current = current or []
    print(f"\n{prompt}  (current: {', '.join(current) if current else 'none'})")
    for i, opt in enumerate(options, 1):
        if isinstance(opt, dict):
            print(f"  {i}. {opt['name']}  [{opt['id']}]")
        else:
            print(f"  {i}. {opt}")
    print("  Enter numbers separated by spaces, or press Enter to keep current:")
    while True:
        raw = input("Select: ").strip().split()
        if not raw:
            log.debug("multi_select: keeping current selection")
            return current
        if all(r.isdigit() and 1 <= int(r) <= len(options) for r in raw):
            selected = [options[int(r) - 1] for r in raw]
            return [s["id"] if isinstance(s, dict) else s for s in selected]
        print("  Invalid — try again.")


def input_with_default(prompt: str, default: str = "") -> str:
    """
    Prompt the user for input with a default value shown in brackets.
    
    If the user presses Enter without typing anything, returns the default.
    """
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else default


def divider() -> None:
    """Print a visual divider line to separate sections in CLI output."""
    print("\n" + "─" * 60)
    print("\n" + "─" * 60)