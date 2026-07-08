/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 */

/**
 * clean.js — Build artefact cleanup script for the i.MX Security Explorer.
 *
 * Two modes
 * ─────────
 *   node clean.js          Standard clean — removes dist/ and all Python
 *   npm run clean          bytecode caches (__pycache__ dirs, .pyc files)
 *                          from the admin/ tree.
 *
 *   node clean.js --all    Full clean — everything above PLUS node_modules/
 *   npm run clean:all      and admin/venv/.  Use this to return the repo to a
 *                          completely pristine state (e.g. before archiving or
 *                          to force a full dependency reinstall).
 *
 * After `--all`, the console prints the commands needed to restore both
 * dependency trees so you don't have to look them up.
 *
 * Design notes
 * ────────────
 * • fs.rmSync with { recursive, force } is used instead of a shell `rm -rf`
 *   so the script works on Windows, macOS, and Linux without extra tools.
 * • "skip" messages are printed for targets that don't exist so the output
 *   remains informative on a partially-clean workspace.
 * • walk() visits the directory tree depth-first and collects matching paths
 *   before removing anything, avoiding "directory modified during iteration"
 *   issues that can occur when removing while iterating.
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// Parse the --all flag from the command line.
const ALL  = process.argv.includes('--all');
const ROOT = __dirname;

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Return *p* relative to the repo root for shorter, readable log lines. */
function rel(p) {
  return path.relative(ROOT, p);
}

/**
 * Remove a file or directory tree at *target*.
 * Prints "skip" if the path does not exist (non-fatal).
 */
function remove(target) {
  if (!fs.existsSync(target)) {
    console.log(`  skip     ${rel(target)}  (not found)`);
    return;
  }
  fs.rmSync(target, { recursive: true, force: true });
  console.log(`  removed  ${rel(target)}`);
}

/**
 * Recursively walk *dir*, calling cb(fullPath) for every entry where
 * match(entry) returns true.
 *
 * When match returns false for a directory entry the walk descends into it,
 * allowing partial matches to be found at any depth.
 *
 * @param {string}   dir   — directory to start from
 * @param {Function} match — predicate: (fs.Dirent) => boolean
 * @param {Function} cb    — called with the full path of each matching entry
 * @param {Set}      skip  — directory names to never descend into or match;
 *                           defaults to an empty set.  Use this to exclude
 *                           large dependency trees (e.g. 'venv', 'node_modules')
 *                           from the walk without a separate existence check.
 */
// Added `skip` parameter so callers can exclude specific directory names.
function walk(dir, match, cb, skip = new Set()) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory() && skip.has(entry.name)) continue;
    if (match(entry)) {
      cb(full);
    } else if (entry.isDirectory()) {
      walk(full, match, cb, skip);
    }
  }
}

/**
 * Find and remove all __pycache__ directories under *baseDir*.
 * Python creates these automatically when .py files are imported; they are
 * safe to delete and will be recreated on the next run.
 *
 * @param {string} baseDir — root directory to search from
 * @param {Set}    skip    — directory names to exclude from the walk
 */
// Added `skip` parameter and forwarded it to walk().
function removePycache(baseDir, skip = new Set()) {
  const found = [];
  walk(
    baseDir,
    e => e.isDirectory() && e.name === '__pycache__',
    p => found.push(p),
    skip
  );
  if (found.length === 0) {
    console.log(`  skip     no __pycache__ dirs found under ${rel(baseDir)}`);
    return;
  }
  found.forEach(remove);
}

/**
 * Find and remove all compiled Python bytecode files (*.pyc) under *baseDir*.
 * These occasionally appear outside __pycache__ in older Python setups.
 *
 * @param {string} baseDir — root directory to search from
 * @param {Set}    skip    — directory names to exclude from the walk
 */
// Added `skip` parameter and forwarded it to walk().
function removePyc(baseDir, skip = new Set()) {
  const found = [];
  walk(
    baseDir,
    e => e.isFile() && e.name.endsWith('.pyc'),
    p => found.push(p),
    skip
  );
  if (found.length === 0) {
    console.log(`  skip     no .pyc files found under ${rel(baseDir)}`);
    return;
  }
  found.forEach(remove);
}

// ── Clean targets ─────────────────────────────────────────────────────────────

const ADMIN_DIR = path.join(ROOT, 'admin');

console.log(`\nCleaning${ALL ? ' (full)' : ''} …\n`);

// ── Always: remove the compiled site output ───────────────────────────────────
console.log('── Build output ─────────────────────────────');
remove(path.join(ROOT, 'dist'));

// ── Always: remove Python bytecode from the admin tool source tree ────────────
// node_modules and admin/venv are excluded because cleaning inside large
// dependency trees is slow and those directories have their own removal step.
console.log('\n── Admin tool — Python cache ────────────────');
// Pass PY_SKIP so admin/venv is not walked. 
const PY_SKIP = new Set(['venv']);
removePycache(ADMIN_DIR, PY_SKIP);
removePyc(ADMIN_DIR, PY_SKIP);

// ── --all only: remove dependency trees ──────────────────────────────────────
if (ALL) {
  console.log('\n── Dependencies (--all) ─────────────────────');
  remove(path.join(ROOT,      'node_modules'));   // Node.js packages
  remove(path.join(ADMIN_DIR, 'venv'));           // Python virtual environment
}

console.log('\nDone.\n');

// Remind the developer how to restore dependencies after a full clean.
if (ALL) {
  console.log('  Restore Node deps  :  npm install');
  console.log('  Restore Python deps:  cd admin && python -m venv venv'
            + ' && source venv/bin/activate'
            + ' && pip install -r requirements.txt\n');
}