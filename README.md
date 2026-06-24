# i.MX Security Explorer

A static reference site for browsing NXP i.MX SoC security documentation.  
Select a device, explore its security features and use cases, and jump directly to the relevant NXP documents.

---

## Overview

The i.MX Security Explorer helps users quickly find security-related documentation for NXP i.MX processors. It is a fully static site — no backend, no database — built from YAML data files.

---

## Getting Started

### Prerequisites

- **Node.js** ≥ 18
- **npm** ≥ 9
- **Python** ≥ 3.10 *(admin tool only)*

---

### Build the Site

```bash
# Install Node dependencies (first time only)
npm install

# Build → outputs to dist/
npm run build
```

### Preview Locally

```bash
npm run dev
```

This builds the site and serves it at `http://localhost:3000`.

---

## Cleaning

### Standard clean

Removes the `dist/` build output and all Python bytecode caches (`__pycache__/` directories and `.pyc` files) from the `admin/` tree.  
Safe to run at any time — it does not touch `node_modules/` or `admin/venv/`.

```bash
npm run clean
```

### Full clean

Removes everything above **plus** `node_modules/` and `admin/venv/`.  
Use this to return the repository to a completely pristine state — for example, before archiving it or to force a full dependency reinstall.

```bash
npm run clean:all
```

After a full clean, restore dependencies with:

```bash
# Restore Node dependencies
npm install

# Restore Python dependencies
cd admin
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
deactivate
cd ..
```

### Rebuild from scratch

Clean the build output and rebuild in one step:

```bash
npm run rebuild
```

> `rebuild` only removes `dist/` — it does **not** wipe `node_modules/` or `admin/venv/`.  
> Use `npm run clean:all` first if you also need to reset dependencies.

---

## Data Files

All content lives in the `data/` directory. The build script reads these files and injects the compiled dataset into the HTML at build time — no runtime fetching.

### `data/config.yaml`

Defines global site metadata, SoC families, security features, use cases, and document types.

### `data/socs.yaml`

Defines all supported i.MX SoC entries (id, name, family, description).

### `data/documents/<feature>.yaml`

One file per security feature. Each document entry references the SoCs it applies to and any relevant use cases.

---

## Admin Tool

A Python + PySide6 desktop GUI for managing the YAML data files without hand-editing them.

### Quick Launch (recommended)

Launcher script is provided to handle venv creation, dependency installation, and cleanup automatically.

**Linux / macOS — Bash script**

```bash
./run_admin.sh [--verbose]
```

> Launcher will:
> - Abort if you are already inside an active virtual environment
> - Create `admin/venv/` on first run
> - Install / sync dependencies from `admin/requirements.txt`
> - Launch the admin tool
> - Deactivate / release the virtual environment on exit

---

### Manual Setup

If you prefer to manage the venv yourself:

```bash
cd admin
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 admin_gui.py [--verbose]
deactivate
```

---

### Admin Tool

> The admin tool writes directly to the `data/` YAML files.
