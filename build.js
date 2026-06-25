/**
 * build.js — Static site builder for the i.MX Security Explorer.
 *
 * Reads all YAML data files from data/ and data/documents/, merges them into
 * a single JSON dataset, then injects that dataset as an inline <script> block
 * into the HTML template.  The result is a fully self-contained static site in
 * dist/ that needs no backend and no runtime HTTP requests.
 *
 * Build pipeline
 * ──────────────
 *  1. Load data/config.yaml   → site metadata, families, features, use-cases,
 *                               document types.
 *  2. Load data/socs.yaml     → SoC catalogue.
 *  3. Load data/documents/*.yaml (sorted) → flatten all document entries into
 *                               a single array; attach the feature id from each
 *                               file's top-level "feature" key.
 *  4. Assemble the combined dataset object.
 *  5. Copy src/css/style.css  → dist/css/style.css
 *     Copy src/js/app.js      → dist/js/app.js
 *  6. Read src/index.html, replace the placeholder comment with
 *         const DATA = { … };
 *     and write the result to dist/index.html.
 *
 * The placeholder in index.html is the literal comment:
 *     /* __INJECT_DATA__ *\/
 * app.js references the global DATA object that this injection creates.
 *
 * Usage
 * ─────
 *   node build.js          (or: npm run build)
 *
 * Exit codes
 * ──────────
 *   0  — success
 *   1  — any YAML parse error or missing source file
 */

'use strict';

const fs   = require('fs');
const path = require('path');
const yaml = require('js-yaml');   // js-yaml is the only runtime dependency

// ── Directory constants ───────────────────────────────────────────────────────

const DATA_DIR = path.join(__dirname, 'data');
const DOCS_DIR = path.join(DATA_DIR, 'documents');
const SRC_DIR  = path.join(__dirname, 'src');
const DIST_DIR = path.join(__dirname, 'dist');

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Parse a YAML file and return its contents as a JS object.
 * Exits the process with code 1 on any read or parse error so the CI job
 * fails loudly rather than producing a silently broken build.
 */
function loadYaml(filepath) {
  try {
    return yaml.load(fs.readFileSync(filepath, 'utf8')) || {};
  } catch (err) {
    console.error(`  ERROR loading ${filepath}: ${err.message}`);
    process.exit(1);
  }
}

/**
 * Create a directory (and any missing parents) if it does not already exist.
 * Equivalent to `mkdir -p`.
 */
function ensureDir(...parts) {
  fs.mkdirSync(path.join(...parts), { recursive: true });
}

// ── Step 1 & 2: Load primary data files ──────────────────────────────────────

console.log('Building i.MX Security Explorer…\n');

const config = loadYaml(path.join(DATA_DIR, 'config.yaml'));
const socs   = loadYaml(path.join(DATA_DIR, 'socs.yaml')).socs || [];

// ── Step 3: Load and flatten all per-feature document files ──────────────────

const documents = [];

for (const filename of fs.readdirSync(DOCS_DIR).sort()) {
  if (!filename.endsWith('.yaml')) continue;   // skip non-YAML files

  const data    = loadYaml(path.join(DOCS_DIR, filename));
  const feature = data.feature || '';   // top-level feature id for this file

  for (const doc of data.documents || []) {
    documents.push({
      id:          doc.id          || '',
      title:       doc.title       || '',
      description: doc.description || '',
      doc_type:    doc.doc_type    || '',
      url:         doc.url         || '',
      // images is kept as an array; fall back to empty array if absent.
      images:      Array.isArray(doc.images) ? doc.images : [],
      // Attach the feature id from the file-level key rather than storing it
      // redundantly in every document entry in the YAML source.
      feature,
      soc:         doc.soc || [],
      // use-case may be stored as a single string in older entries — normalise
      // to an array so app.js never has to handle both shapes.
      'use-case':  Array.isArray(doc['use-case'])
                     ? doc['use-case']
                     : doc['use-case'] ? [doc['use-case']] : [],
    });
  }

  console.log(`  ✓ ${filename} (${(data.documents || []).length} docs)`);
}

// ── NEW: Expand 'all_soc' keyword ────────────────────────────────────────────

const allSocIds = socs.map(s => s.id);

// Validate that we have SoCs before expanding
if (allSocIds.length === 0) {
  console.error('  ERROR: No SoCs found in socs.yaml. Cannot expand all_soc.');
  process.exit(1);
}

let expandedCount = 0;
for (const doc of documents) {
  if (doc.soc && doc.soc.includes('all_soc')) {
    doc.soc = allSocIds;
    expandedCount++;
  }
}

if (expandedCount > 0) {
  console.log(`  ✓ Expanded 'all_soc' in ${expandedCount} document(s)`);
}

// ── Step 4: Assemble the combined dataset ─────────────────────────────────────
//
// This object is serialised as JSON and injected verbatim into index.html.
// app.js reads it via the global DATA variable.
//
// Key-name mapping (YAML → JS):
//   config.use-cases         → dataset.useCases   (camelCase for JS consumers)
//   config.document_types or
//   config.document_categories → dataset.documentTypes

const dataset = {
  site:          config.site         || {},
  families:      config.families     || [],
  features:      config.features     || [],
  useCases:      config['use-cases'] || [],
  // Support both the current key name and a legacy alternative.
  documentTypes: config.document_categories || config.document_types || [],
  socs,
  documents,
};

// ── Step 5 & 6: Write dist/ ───────────────────────────────────────────────────

// Create output directories (idempotent).
ensureDir(DIST_DIR);
ensureDir(DIST_DIR, 'css');
ensureDir(DIST_DIR, 'js');

// Copy static assets unchanged.
fs.copyFileSync(path.join(SRC_DIR, 'css', 'style.css'),
                path.join(DIST_DIR, 'css', 'style.css'));
fs.copyFileSync(path.join(SRC_DIR, 'js',  'app.js'),
                path.join(DIST_DIR, 'js',  'app.js'));

// Inject the dataset into the HTML template.
// The placeholder comment /* __INJECT_DATA__ */ sits inside a <script> tag in
// src/index.html.  Replacing it with `const DATA = ...;` makes DATA a global
// variable available to app.js which is loaded immediately after.
const template = fs.readFileSync(path.join(SRC_DIR, 'index.html'), 'utf8');
const html     = template.replace(
  '/* __INJECT_DATA__ */',
  `const DATA = ${JSON.stringify(dataset, null, 2)};`
);
fs.writeFileSync(path.join(DIST_DIR, 'index.html'), html);

// ── Summary ───────────────────────────────────────────────────────────────────

console.log(`
Build complete → dist/
  ${socs.length} SoCs
  ${documents.length} documents
  ${config.features?.length || 0} features
`);
