#!/bin/bash

# Copyright 2026 NXP
# SPDX-License-Identifier: BSD-3-Clause

# generate_patch.sh — Generate patch file for Admin tool changes
# Usage: ./generate_patch.sh

set -e

# ── Configuration ─────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PATCHES_DIR="$REPO_DIR/patches"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
PATCH_FILE="$PATCHES_DIR/data-changes-$TIMESTAMP.patch"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Helper Functions ──────────────────────────────────────────────────────────
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✖${NC} $1"
}

log_step() {
    echo -e "${BLUE}▶${NC} $1"
}

# ── Header ────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  i.MX Security Explorer — Generate Patch File"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ── Pre-flight Checks ─────────────────────────────────────────────────────────
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    log_error "Not a git repository. Please run this from the repository root."
    exit 1
fi

# ── Check for Changes ─────────────────────────────────────────────────────────
log_step "Checking for changes in data/ folder..."

CHANGED_FILES=$(git status --porcelain)

if [ -z "$CHANGED_FILES" ]; then
    log_warn "No changes detected. Nothing to generate."
    exit 0
fi

# Filter for data/ folder changes only
DATA_CHANGES=$(echo "$CHANGED_FILES" | grep "data/" || true)
NON_DATA_CHANGES=$(echo "$CHANGED_FILES" | grep -v "data/" || true)

if [ -z "$DATA_CHANGES" ]; then
    log_error "No changes detected in data/ folder."
    exit 1
fi

if [ -n "$NON_DATA_CHANGES" ]; then
    log_warn "Changes detected outside data/ folder (will be excluded from patch):"
    echo "$NON_DATA_CHANGES" | sed 's/^/  /'
    echo ""
fi

# ── Display Changes ───────────────────────────────────────────────────────────
log_info "Changes detected in data/ folder:"
echo "$DATA_CHANGES" | sed 's/^/  /'
echo ""

# ── Get User Information ──────────────────────────────────────────────────────
USER_NAME=$(git config user.name)
USER_EMAIL=$(git config user.email)

if [ -z "$USER_NAME" ] || [ -z "$USER_EMAIL" ]; then
    log_error "Git user name and email not configured. Please run:"
    echo "  git config user.name \"Your Name\""
    echo "  git config user.email \"your.email@example.com\""
    exit 1
fi

read -p "Brief description of changes (optional): " DESCRIPTION

if [ -z "$DESCRIPTION" ]; then
    DESCRIPTION="Update data files via Admin tool"
fi

# ── Create Patches Directory ──────────────────────────────────────────────────
mkdir -p "$PATCHES_DIR"

# ── Generate Patch ────────────────────────────────────────────────────────────
log_step "Generating patch file..."

# Stage only data/ folder changes
git add data/

# Create a temporary commit (will be reset after patch generation)
git commit -s -m "data: $DESCRIPTION" \
    --author="$USER_NAME <$USER_EMAIL>" \
    > /dev/null 2>&1

# Generate the patch file
git format-patch -1 HEAD --stdout > "$PATCH_FILE"

# Reset the commit (keep changes in working directory)
git reset --soft HEAD~1
git reset HEAD data/

log_info "Patch file created: $PATCH_FILE"

# ── Generate Submission Instructions ──────────────────────────────────────────
INSTRUCTIONS_FILE="$PATCHES_DIR/SUBMISSION_INSTRUCTIONS.txt"

cat > "$INSTRUCTIONS_FILE" << EOF
═══════════════════════════════════════════════════════════════
  How to Submit Your Patch
═══════════════════════════════════════════════════════════════

Your patch file has been generated:
  $PATCH_FILE

GitHub Pull Request Submission
─────────────────────────────────────────────────────────────────
1. Fork the repository on GitHub:
   https://github.com/nxp-imx-support/imx-security-explorer

2. Clone your fork:
   git clone https://github.com/YOUR_USERNAME/imx-security-explorer.git

3. Apply the patch:
   cd imx-security-explorer
   git apply $PATCH_FILE

4. Commit and push:
   git add data/
   git commit -s -m "data: $DESCRIPTION"
   git push origin main

5. Create a Pull Request on GitHub:
   - Go to your fork: https://github.com/YOUR_USERNAME/imx-security-explorer
   - Click "Contribute" → "Open pull request"
   - Click "New Pull Request"
   - Ensure base repository is: nxp-imx-support/imx-security-explorer
   - Ensure base branch is: main
   - Ensure head repository is: YOUR_USERNAME/imx-security-explorer
   - Add a descriptive title and description
   - Click "Create Pull Request"

═══════════════════════════════════════════════════════════════
EOF

log_info "Submission instructions saved: $INSTRUCTIONS_FILE"

# ── Display Summary ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
log_info "Patch generation complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Files created:"
echo "  📄 Patch file:    $PATCH_FILE"
echo "  📋 Instructions:  $INSTRUCTIONS_FILE"
echo ""
echo "Next steps:"
echo "  1. Open the instructions file for submission details"
echo "  2. Submit via GitHub Pull Request"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""