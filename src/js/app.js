/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 */

'use strict';

(function () {

  // ── State ──────────────────────────────────────────────────────────────────
  // Currently selected SoC object
  let activeSoc    = null;
  // Currently active family filter ('all' or a family id)
  let activeFamily = 'all';
  // Current search query string (lowercase)
  let searchQuery  = '';

  // ── DOM ────────────────────────────────────────────────────────────────────
  // Helper function to get element by ID
  const $ = id => document.getElementById(id);

  // Cache all DOM element references
  const elVersion           = $('siteVersion');
  const elFamilyTabs        = $('familyTabs');
  const elSocList           = $('socList');
  const elSocSearch         = $('socSearch');
  const elViewPlaceholder   = $('viewPlaceholder');
  const elViewSoc           = $('viewSoc');
  const elViewDocs          = $('viewDocs');
  const elDetailName        = $('detailName');
  const elDetailDesc        = $('detailDesc');
  const elDetailFamily      = $('detailFamily');
  const elUsecaseCards      = $('usecaseCards');
  const elFeatureCards      = $('featureCards');
  const elEmptyUsecases     = $('emptyUsecases');
  const elEmptyFeatures     = $('emptyFeatures');
  const elBackBtn           = $('backBtn');
  const elBreadcrumbSoc     = $('breadcrumbSoc');
  const elBreadcrumbCurrent = $('breadcrumbCurrent');
  const elDocViewTitle      = $('docViewTitle');
  const elDocViewCount      = $('docViewCount');
  const elDocList           = $('docList');

  // ── Bootstrap ──────────────────────────────────────────────────────────────
  /**
   * Initialize the application:
   *   - Set version number
   *   - Build family tabs
   *   - Build SoC list
   *   - Wire up event listeners
   */
  function init() {
    elVersion.textContent = `v${DATA.site.version || ''}`;
    buildFamilyTabs();
    buildSocList();
    elSocSearch.addEventListener('input', onSearch);
    elBackBtn.addEventListener('click', () => showView('soc'));
  }

  // ── View switcher ──────────────────────────────────────────────────────────
  /**
   * Switch between the three main views: placeholder, soc, and docs.
   * Only one view is visible at a time.
   * @param {string} view - The view to show ('placeholder', 'soc', or 'docs')
   */
  function showView(view) {
    elViewPlaceholder.classList.toggle('hidden', view !== 'placeholder');
    elViewSoc.classList.toggle('hidden',         view !== 'soc');
    elViewDocs.classList.toggle('hidden',        view !== 'docs');
    // Reset scroll position when showing docs view
    if (view === 'docs') elViewDocs.scrollTop = 0;
  }

  // ── Family tabs ────────────────────────────────────────────────────────────
  /**
   * Build the family filter tabs.
   * Creates an "All" tab plus one tab per family in DATA.families.
   */
  function buildFamilyTabs() {
    const all = makeTab('all', 'All');
    all.classList.add('active');
    elFamilyTabs.appendChild(all);
    DATA.families.forEach(f => elFamilyTabs.appendChild(makeTab(f.id, f.name)));
  }

  /**
   * Create a single family tab button.
   * @param {string} id - The family id (or 'all')
   * @param {string} label - The display label
   * @returns {HTMLElement} The tab button element
   */
  function makeTab(id, label) {
    const btn = document.createElement('button');
    btn.className   = 'family-tab';
    btn.dataset.fam = id;
    btn.textContent = label;
    btn.addEventListener('click', () => selectFamily(id));
    return btn;
  }

  /**
   * Select a family tab and filter the SoC list accordingly.
   * @param {string} id - The family id to select
   */
  function selectFamily(id) {
    activeFamily = id;
    // Update active state on all tabs
    elFamilyTabs.querySelectorAll('.family-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.fam === id)
    );
    applyListFilters();
  }

  // ── SoC list ───────────────────────────────────────────────────────────────
  /**
   * Build the list of SoC items from DATA.socs.
   * Each item is clickable and filterable by family and search query.
   */
  function buildSocList() {
    DATA.socs.forEach(soc => {
      const item = document.createElement('div');
      item.className      = 'soc-item';
      item.dataset.id     = soc.id;
      item.dataset.family = soc.family || '';
      // Pre-compute lowercase search string for efficient filtering
      item.dataset.search = `${soc.id} ${soc.name}`.toLowerCase();
      item.innerHTML = `
        <div class="soc-item-name">${esc(soc.name)}</div>
        <div class="soc-item-id">${esc(soc.id)}</div>
      `;
      item.addEventListener('click', () => selectSoc(soc, item));
      elSocList.appendChild(item);
    });
  }

  /**
   * Apply both family and search filters to the SoC list.
   * Hides items that don't match the current filters.
   */
  function applyListFilters() {
    elSocList.querySelectorAll('.soc-item').forEach(item => {
      const famOk    = activeFamily === 'all' || item.dataset.family === activeFamily;
      const searchOk = item.dataset.search.includes(searchQuery);
      item.classList.toggle('hidden', !(famOk && searchOk));
    });
  }

  /**
   * Handle search input changes.
   * @param {Event} e - The input event
   */
  function onSearch(e) {
    searchQuery = e.target.value.toLowerCase().trim();
    applyListFilters();
  }

  // ── SoC selection ──────────────────────────────────────────────────────────
  /**
   * Select a SoC and display its details and overview.
   * @param {Object} soc - The SoC object
   * @param {HTMLElement} item - The clicked list item element
   */
  function selectSoc(soc, item) {
    activeSoc = soc;

    // Update active state on all SoC items
    elSocList.querySelectorAll('.soc-item').forEach(el =>
      el.classList.toggle('active', el === item)
    );

    // Populate detail fields
    elDetailName.textContent   = soc.name;
    elDetailDesc.textContent   = soc.description || '';
    elDetailFamily.textContent = familyLabel(soc.family);

    // Build the overview cards (use cases and features)
    buildSocOverview(soc);
    showView('soc');
  }

  /**
   * Get the display name for a family id.
   * @param {string} id - The family id
   * @returns {string} The family name or the id if not found
   */
  function familyLabel(id) {
    const f = DATA.families.find(f => f.id === id);
    return f ? f.name : id || '';
  }

  // ── SoC overview ───────────────────────────────────────────────────────────
  /**
   * Build the overview section showing use cases and features for the selected SoC.
   * @param {Object} soc - The selected SoC object
   */
  function buildSocOverview(soc) {
    // Filter documents that belong to this SoC
    const socDocs = DATA.documents.filter(d => (d.soc || []).includes(soc.id));

    // Collect all unique use case IDs from the SoC's documents
    const ucIds    = new Set(socDocs.flatMap(d => d['use-case'] || []));
    const useCases = DATA.useCases.filter(u => ucIds.has(u.id));

    // Collect all unique feature IDs from the SoC's documents
    const featIds  = new Set(socDocs.map(d => d.feature).filter(Boolean));
    const features = DATA.features.filter(f => featIds.has(f.id));

    // Build use case cards
    elUsecaseCards.innerHTML = '';
    elEmptyUsecases.classList.toggle('hidden', useCases.length > 0);
    useCases.forEach(uc => {
      const count = socDocs.filter(d => (d['use-case'] || []).includes(uc.id)).length;
      elUsecaseCards.appendChild(buildOverviewCard(uc, count, 'usecase'));
    });

    // Build feature cards
    elFeatureCards.innerHTML = '';
    elEmptyFeatures.classList.toggle('hidden', features.length > 0);
    features.forEach(f => {
      const count = socDocs.filter(d => d.feature === f.id).length;
      elFeatureCards.appendChild(buildOverviewCard(f, count, 'feature'));
    });
  }

  /**
   * Build a single overview card (for use case or feature).
   * @param {Object} item - The use case or feature object
   * @param {number} docCount - Number of documents associated with this item
   * @param {string} type - Either 'usecase' or 'feature'
   * @returns {HTMLElement} The card element
   */
  function buildOverviewCard(item, docCount, type) {
    const card = document.createElement('div');
    card.className = `overview-card overview-card--${type}`;
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.innerHTML = `
      <div class="card-name">${esc(item.name)}</div>
      ${item.description ? `<div class="card-desc">${esc(item.description)}</div>` : ''}
      <div class="card-count">${docCount} document${docCount !== 1 ? 's' : ''}</div>
    `;
    // Handler to show documents for this use case or feature
    const handler = () => type === 'usecase'
      ? showUseCaseDocs(item)
      : showFeatureDocs(item);

    card.addEventListener('click', handler);
    // Support keyboard navigation
    // Added e.preventDefault() for Space so the page does not scroll
    // while the card action fires.
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); }
    });
    return card;
  }

  // ── Document views ─────────────────────────────────────────────────────────
  /**
   * Show all documents for a specific feature within the active SoC.
   * @param {Object} feature - The feature object
   */
  function showFeatureDocs(feature) {
    const docs = DATA.documents.filter(d =>
      d.feature === feature.id && (d.soc || []).includes(activeSoc.id)
    );
    renderDocView(feature.name, docs);
  }

  /**
   * Show all documents for a specific use case within the active SoC.
   * @param {Object} useCase - The use case object
   */
  function showUseCaseDocs(useCase) {
    const docs = DATA.documents.filter(d =>
      (d['use-case'] || []).includes(useCase.id) && (d.soc || []).includes(activeSoc.id)
    );
    renderDocView(useCase.name, docs);
  }

  /**
   * Render the document list view.
   * @param {string} title - The title to display (feature or use case name)
   * @param {Array} docs - Array of document objects to display
   */
  function renderDocView(title, docs) {
    // Update breadcrumb and header
    elBreadcrumbSoc.textContent     = activeSoc.name;
    elBreadcrumbCurrent.textContent = title;
    elDocViewTitle.textContent      = title;
    elDocViewCount.textContent      = `${docs.length} document${docs.length !== 1 ? 's' : ''}`;

    // Build document cards
    elDocList.innerHTML = '';
    if (docs.length === 0) {
      elDocList.innerHTML = '<div class="no-docs">No documents available.</div>';
    } else {
      docs.forEach(doc => elDocList.appendChild(buildDocCard(doc)));
    }
    showView('docs');
  }

  /**
   * Build a single document card.
   * @param {Object} doc - The document object
   * @returns {HTMLElement} The card element
   */
  function buildDocCard(doc) {
    // Look up feature name
    const feature = DATA.features.find(f => f.id === doc.feature);
    // Look up use case names
    const ucs     = (doc['use-case'] || []).map(id => {
      const u = DATA.useCases.find(u => u.id === id);
      return u ? u.name : id;
    });

    // Build tag HTML for feature and use cases
    const tags = [
      feature ? `<span class="tag tag-feature">${esc(feature.name)}</span>` : '',
      ...ucs.map(n => `<span class="tag tag-usecase">${esc(n)}</span>`),
    ].join('');

    const card = document.createElement('div');
    card.className = 'doc-card';
    card.setAttribute('role', 'link');
    card.setAttribute('tabindex', '0');
    card.innerHTML = `
      <div class="doc-card-top">
        <span class="doc-title">${esc(doc.title)}</span>
        ${doc.doc_type ? `<span class="doc-type-badge">${esc(doc.doc_type)}</span>` : ''}
      </div>
      ${doc.description ? `<p class="doc-description">${esc(doc.description)}</p>` : ''}
      ${tags ? `<div class="doc-meta">${tags}</div>` : ''}
    `;

    // Validate URL before opening.
    // - Skips cards with no URL (no blank tab opened).
    // - Blocks non-http(s) protocols (e.g. javascript:) regardless of browser version.
    const open = () => {
      const url = doc.url;
      if (!url) return;
      if (!/^https?:\/\//i.test(url)) return;
      window.open(url, '_blank', 'noopener,noreferrer');
    };

    card.addEventListener('click', open);
    // Support keyboard navigation
    // Added e.preventDefault() for Space so the page does not scroll
    // while the card action fires.
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
    return card;
  }

  // ── Utility ────────────────────────────────────────────────────────────────
  /**
   * Escape HTML special characters to prevent XSS.
   * @param {string} str - The string to escape
   * @returns {string} The escaped string
   */
  function esc(str) {
    // Corrected entity strings — were unescaped literals
    // Replacement strings must be HTML entities, not the bare characters
    // they are meant to replace.  The previous version was a no-op (replacing
    // each character with itself) providing zero XSS protection.
    return String(str || '')
      .replace(/&/g,  '&')
      .replace(/</g,  '<')
      .replace(/>/g,  '>')
      .replace(/"/g,  '"');
  }

  // ── Go ─────────────────────────────────────────────────────────────────────
  // Start the application
  init();

  // ── CSV Export ────────────────────────────────────────────────────────────────
  //
  // Populates the header SoC dropdown from DATA.socs and wires the Export button
  // to generate a CSV of all documents associated with the chosen SoC.
  //
  // CSV columns (in order):
  //   Feature | Document Title | URL | Document Type | Description

  /**
   * Initialize the CSV export functionality.
   * Populates the SoC dropdown and wires the export button.
   */
  (function initCsvExport() {
    const selectEl = document.getElementById('exportSocSelect');
    const btnEl    = document.getElementById('exportCsvBtn');

    // Exit if elements don't exist
    if (!selectEl || !btnEl) return;

    // ── 1. Populate the dropdown ──────────────────────────────────────────────

    // Build a map of family IDs to family names
    const familyMap = {};
    (DATA.families || []).forEach(f => { familyMap[f.id] = f.name; });

    // Group SoCs by family for organized dropdown
    const grouped = {};
    (DATA.socs || []).forEach(soc => {
      const fam = soc.family || 'other';
      if (!grouped[fam]) grouped[fam] = [];
      grouped[fam].push(soc);
    });

    // Create optgroups and options
    Object.keys(grouped).forEach(famId => {
      const group = document.createElement('optgroup');
      group.label = familyMap[famId] || famId;
      grouped[famId].forEach(soc => {
        const opt = document.createElement('option');
        opt.value       = soc.id;
        opt.textContent = soc.name;
        group.appendChild(opt);
      });
      selectEl.appendChild(group);
    });

    // ── 2. Enable / disable the button based on selection ────────────────────

    // Disable button when no SoC is selected
    selectEl.addEventListener('change', () => {
      btnEl.disabled = selectEl.value === '';
    });

    // ── 3. Build and trigger CSV download on click ───────────────────────────

    btnEl.addEventListener('click', () => {
      const socId = selectEl.value;
      if (!socId) return;

      // Find the selected SoC
      const soc = (DATA.socs || []).find(s => s.id === socId);
      if (!soc) return;

      // Build a lookup map: feature id → feature name
      const featureNameMap = {};
      (DATA.features || []).forEach(f => { featureNameMap[f.id] = f.name; });

      // Filter documents that include this SoC
      const docs = (DATA.documents || []).filter(doc =>
        Array.isArray(doc.soc) && doc.soc.includes(socId)
      );

      if (docs.length === 0) {
        alert(`No documents found for ${soc.name}.`);
        return;
      }

      // ── Build CSV content ─────────────────────────────────────────────────

      /**
       * Escape a single CSV cell value:
       *   • wrap in double-quotes
       *   • escape any internal double-quotes by doubling them
       *   • replace newlines so the cell stays on one row
       * @param {*} value - The value to escape
       * @returns {string} The escaped CSV cell
       */
      function csvCell(value) {
        const str = (value == null ? '' : String(value))
          .replace(/\r?\n/g, ' ')
          .replace(/"/g, '""');
        return `"${str}"`;
      }

      // Define CSV column headers
      const COLUMNS = ['Feature', 'Document Title', 'URL', 'Document Type', 'Description'];

      // Build CSV rows (header + data)
      const rows = [
        // Header row
        COLUMNS.map(csvCell).join(','),
        // Data rows
        ...docs.map(doc => [
          csvCell(featureNameMap[doc.feature] || doc.feature),
          csvCell(doc.title),
          csvCell(doc.url),
          csvCell(doc.doc_type),
          csvCell(doc.description),
        ].join(',')),
      ];

      // Join rows with CRLF line endings
      const csvContent = rows.join('\r\n');

      // ── Trigger download ──────────────────────────────────────────────────

      // Create a Blob from the CSV content
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url  = URL.createObjectURL(blob);

      // Create a temporary link element and trigger download
      const link = document.createElement('a');
      link.href     = url;
      link.download = `imx-security-docs_${socId}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Release the object URL after a short delay to free memory
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    });
  })();
})();