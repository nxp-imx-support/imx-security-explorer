"""
doc_tab.py — "Documents" tab for the i.MX Security Explorer Admin GUI.

Manages the per-feature document YAML files located in data/documents/.
Each file follows the schema:

    feature: <feature-id>
    documents:
      - id: <doc-id>
        title: ...
        description: ...
        doc_type: ...
        url: ...
        image: ...
        soc: [<soc-id>, ...]
        use-case: [<use-case-id>, ...]

Documents are loaded from all *.yaml files in DOCS_DIR into a flat list with
two synthetic keys injected at load time:
    _feature  : str   — the value of the file's top-level "feature" key
    _filepath : str   — absolute path to the source file

These synthetic keys (prefix "_") are stripped before writing back to disk.

Layout
──────
┌──────────────────────────────────────────────────────┐
│  QTableWidget (Title/DocType/Feature/UseCases/SoCs/  │  ← top pane
│               URL)                                   │
├──────────────────────────────────────────────────────┤  splitter handle
│  QGroupBox "Details" (all fields, read-only)         │  ← bottom pane
├──────────────────────────────────────────────────────┤
│  [Add]  [Edit]  [Delete]                             │  ← always visible
└──────────────────────────────────────────────────────┘

Feature reassignment (Edit)
───────────────────────────
A document can be moved to a different feature during editing.  The edit
workflow handles this atomically:
  1. Load both the old and new feature files into memory.
  2. Prepare the updated document lists in memory only.
  3. Write the new feature file first; then overwrite the old one.
     If step 3 fails, a critical error dialog is shown and no data is lost
     because both writes are atomic (via tempfile + os.replace).

URL validation
──────────────
DocDialog performs live URL validation as the user types, using
_is_valid_url().  The OK button is disabled while the URL is invalid.
"""

import os
import yaml
import tempfile
import re
import logging

_log = logging.getLogger("imx_admin.doc_tab")

from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox, QListWidget,
    QDialogButtonBox, QMessageBox, QHeaderView, QAbstractItemView, QLabel,
    QSplitter, QGroupBox, QTextEdit, QListWidgetItem, QTabWidget
)
from PySide6.QtCore import Qt
from utils import load_config, load_socs, DOCS_DIR


# ── Module-level helpers ──────────────────────────────────────────────────────

def _is_valid_url(url: str) -> bool:
    """
    Return True if *url* is a well-formed http or https URL.

    An empty string is considered valid (the URL field is optional).
    Malformed URLs (missing scheme, missing host, wrong scheme) return False.
    """
    if not url:
        return True
    try:
        result = urlparse(url.strip())
        return result.scheme in ("http", "https") and bool(result.netloc)
    except ValueError:
        return False


# ── YAML file helpers ─────────────────────────────────────────────────────────

def load_all_documents() -> list:
    """
    Scan DOCS_DIR and return a flat list of all document dicts.

    Each dict is augmented with:
        _feature  : the feature id string from the file's top-level key
        _filepath : absolute path to the source .yaml file

    Files that cannot be read or parsed are skipped with an error log entry
    so a single corrupt file does not prevent the rest from loading.

    Returns an empty list if DOCS_DIR does not exist yet.
    """
    all_docs = []
    if not os.path.exists(DOCS_DIR):
        return all_docs
    try:
        filenames = sorted(os.listdir(DOCS_DIR))
    except OSError as exc:
        _log.error(f"Cannot read documents directory '{DOCS_DIR}': {exc}")
        return all_docs

    for filename in filenames:
        if not filename.endswith(".yaml"):
            continue
        filepath = os.path.join(DOCS_DIR, filename)
        try:
            with open(filepath, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as exc:
            _log.error(f"Failed to load {filepath}: {exc}")
            continue

        feature = data.get("feature", "")
        for doc in data.get("documents") or []:
            doc["_feature"]  = feature
            doc["_filepath"] = filepath
            all_docs.append(doc)

    return all_docs


def save_document_file(filepath: str, feature: str, docs: list) -> None:
    """
    Write a feature document file atomically.

    Strips all synthetic "_*" keys from each document before serialising so
    that internal GUI metadata (``_feature``, ``_filepath``) is never written
    to disk.  Ensures ``soc`` and ``use-case`` are always lists (not None).

    Uses a sibling temp-file + os.replace() for an atomic write.
    Cleans up the orphaned temp file if any step fails before replacement.
    """
    clean = []
    for d in docs:
        entry = {k: v for k, v in d.items() if not k.startswith("_")}
        entry["soc"]      = entry.get("soc")      or []
        entry["use-case"] = entry.get("use-case") or []
        clean.append(entry)

    dir_name = os.path.dirname(filepath)
    os.makedirs(dir_name, exist_ok=True)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=dir_name, delete=False, suffix=".tmp"
        ) as tmp:
            yaml.dump(
                {"feature": feature, "documents": clean},
                tmp,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            tmp_path = tmp.name
        os.replace(tmp_path, filepath)
    except Exception as exc:
        # Clean up orphaned temp file before re-raising
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        _log.error(f"Failed to write '{filepath}': {exc}")
        raise


def get_feature_filepath(feature_id: str) -> str:
    """
    Return the absolute path to the document file for *feature_id*.

    Validates *feature_id* against a strict allowlist (alphanumerics, hyphens,
    underscores) to prevent path-traversal attacks.  Also checks that the
    resolved path stays within DOCS_DIR.

    Raises ValueError if the id is invalid or the resolved path escapes DOCS_DIR.
    """
    if not re.match(r'^[\w\-]+$', feature_id or ""):
        raise ValueError(f"Invalid feature_id: '{feature_id}'")
    path = os.path.join(DOCS_DIR, f"{feature_id}.yaml")
    if not os.path.abspath(path).startswith(os.path.abspath(DOCS_DIR) + os.sep):
        raise ValueError(f"Path traversal detected for feature_id: '{feature_id}'")
    return path


def load_feature_file(filepath: str):
    """
    Read a single feature document file and return (feature_id, docs_list).

    Returns ("", []) if the file does not exist yet (new feature, no documents
    added yet).  Raises RuntimeError for other I/O or parse errors so the
    caller can display a user-facing message.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return "", []
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Cannot read '{filepath}': {exc}") from exc
    return data.get("feature", ""), data.get("documents") or []


# ── Splitter style ────────────────────────────────────────────────────────────

_SPLITTER_STYLE = """
    QSplitter::handle {
        background: #aaaaaa;
        border: 1px solid #888888;
        height: 6px;
    }
    QSplitter::handle:hover {
        background: #666666;
    }
"""


# ── Add / Edit dialog ─────────────────────────────────────────────────────────

class DocDialog(QDialog):
    """
    Modal dialog for adding or editing a document entry.

    Fields
    ------
    id          : Unique document identifier (slug).
    title       : Human-readable document title.
    description : Optional one-line summary.
    doc_type    : Selected from the document_types list in config.yaml.
    url         : Optional link; validated live with _is_valid_url().
    image       : Optional relative path to a thumbnail image.
    feature     : Combo populated from config.yaml → features.
    use-case    : Multi-select list populated from config.yaml → use-cases.
    soc         : Multi-select list populated from socs.yaml.

    URL validation
    --------------
    A QLabel below the URL field shows a live ✔/✖ indicator.
    The OK button is disabled while the URL is non-empty but invalid.
    _on_accept() performs a final guard before calling self.accept() in case
    the signal-slot validation was bypassed.
    """

    def __init__(self, parent=None, doc=None):
        super().__init__(parent)
        self.setWindowTitle("Add Document" if doc is None else "Edit Document")
        self.setMinimumWidth(560)

        config    = load_config()
        socs      = load_socs()
        features  = config.get("features", [])
        use_cases = config.get("use-cases", [])
        doc_types = config.get("document_types", [])

        layout = QFormLayout(self)
        layout.setVerticalSpacing(10)

        # ── Text fields ───────────────────────────────────────────────────────
        self.id_edit    = QLineEdit(doc.get("id", "")    if doc else "")
        self.title_edit = QLineEdit(doc.get("title", "") if doc else "")
        self.desc_edit  = QLineEdit(doc.get("description", "") if doc else "")
        self.desc_edit.setPlaceholderText("Optional short summary of the document")

        # ── Document type combo ───────────────────────────────────────────────
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems(doc_types)
        current_type = doc.get("doc_type", "") if doc else ""
        if current_type in doc_types:
            self.doc_type_combo.setCurrentText(current_type)

        # ── URL field + live validation label ─────────────────────────────────
        self.url_edit = QLineEdit(doc.get("url", "") if doc else "")
        self.url_edit.setPlaceholderText("https://...")
        self.url_status = QLabel("")
        self.url_edit.textChanged.connect(self._validate_url)

        # ── Image path field ──────────────────────────────────────────────────
        self.image_edit = QLineEdit(doc.get("image", "") if doc else "")
        self.image_edit.setPlaceholderText("e.g. images/secure-boot.png")

        # ── Feature combo ─────────────────────────────────────────────────────
        # userData stores the feature id; display text is the human name.
        self.feature_combo = QComboBox()
        for f in features:
            self.feature_combo.addItem(f["name"], f["id"])
        if doc and doc.get("_feature"):
            idx = self.feature_combo.findData(doc["_feature"])
            if idx >= 0:
                self.feature_combo.setCurrentIndex(idx)

        # ── Use-case multi-select list ────────────────────────────────────────
        current_usecases = doc.get("use-case") or [] if doc else []
        if isinstance(current_usecases, str):
            current_usecases = [current_usecases]

        self.usecase_list = QListWidget()
        self.usecase_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.usecase_list.setFixedHeight(80)
        self._usecase_ids = []
        for uc in use_cases:
            self.usecase_list.addItem(uc["name"])
            self._usecase_ids.append(uc["id"])
            if uc["id"] in current_usecases:
                self.usecase_list.item(self.usecase_list.count() - 1).setSelected(True)

        # ── SoC multi-select list ─────────────────────────────────────────────
        current_socs = doc.get("soc") or [] if doc else []

        self.soc_list = QListWidget()
        self.soc_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.soc_list.setFixedHeight(120)  # Taller to fit "All SoCs" option
        self._soc_ids = []

        # Add "All SoCs" as the first option
        self.soc_list.addItem("✓ All SoCs")
        self._soc_ids.append("all_soc")
        if "all_soc" in current_socs:
            self.soc_list.item(0).setSelected(True)

        # Add a visual separator
        separator = QListWidgetItem("─────────────────────────────────")
        separator.setFlags(Qt.NoItemFlags)  # Not selectable
        self.soc_list.addItem(separator)
        self._soc_ids.append(None)  # Placeholder for separator

        # Add individual SoCs
        for s in socs:
            self.soc_list.addItem(f"{s['id']} — {s.get('name', '')}")
            self._soc_ids.append(s["id"])
            if s["id"] in current_socs:
                self.soc_list.item(self.soc_list.count() - 1).setSelected(True)

        # ── Form rows ─────────────────────────────────────────────────────────
        layout.addRow("ID:",          self.id_edit)
        layout.addRow("Title:",       self.title_edit)
        layout.addRow("Description:", self.desc_edit)
        layout.addRow("Doc Type:",    self.doc_type_combo)
        layout.addRow("URL:",         self.url_edit)
        layout.addRow("",             self.url_status)   # validation indicator
        layout.addRow("Image:",       self.image_edit)
        layout.addRow("Feature:",     self.feature_combo)
        layout.addRow(QLabel("Use-Cases (multi-select):"))
        layout.addRow(self.usecase_list)
        layout.addRow(QLabel("SoCs (multi-select):"))
        layout.addRow(self.soc_list)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

        # Run validation immediately so the OK button state is correct when
        # the dialog opens with a pre-filled (possibly invalid) URL.
        self._validate_url(self.url_edit.text())

    def _validate_url(self, text: str) -> None:
        """
        Live URL validation triggered on every keystroke.

        Updates the status label colour and text, and enables / disables the
        OK button to prevent saving an invalid URL.
        """
        url = text.strip()
        if not url:
            # Empty URL is valid — field is optional.
            self.url_status.setStyleSheet("")
            self.url_status.setText("")
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)
        elif _is_valid_url(url):
            self.url_status.setStyleSheet("color: green; font-size: 11px;")
            self.url_status.setText("✔ Valid URL")
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.url_status.setStyleSheet("color: red; font-size: 11px;")
            self.url_status.setText("✖ Must start with http:// or https://")
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)

    def _on_accept(self) -> None:
        """
        Final validation guard before closing the dialog.

        Validates required fields (ID, Title) and the optional URL before
        allowing the dialog to close.  Keeping all validation here ensures
        the user's input is preserved when an error is shown.
        """
        if not self.id_edit.text().strip() or not self.title_edit.text().strip():
            QMessageBox.warning(self, "Validation Error",
                                "ID and Title are required.")
            return

        url = self.url_edit.text().strip()
        if url and not _is_valid_url(url):
            QMessageBox.warning(
                self, "Invalid URL",
                f"The URL is not valid:\n{url}\n\n"
                "Please enter a URL starting with http:// or https://, "
                "or leave the field empty."
            )
            self.url_edit.setFocus()
            return

        self.accept()

    def get_data(self) -> dict:
        """
        Return the current dialog values as a dict.

        Includes the synthetic _feature key (the selected feature id) so that
        DocTab.add_doc() / edit_doc() know which file to write to.
        """
        selected_usecases = [
            self._usecase_ids[self.usecase_list.row(item)]
            for item in self.usecase_list.selectedItems()
        ]
        selected_socs = []
        for item in self.soc_list.selectedItems():
            row = self.soc_list.row(item)
            soc_id = self._soc_ids[row]
            if soc_id is not None:  # Skip separator
                selected_socs.append(soc_id)

        # Smart behavior: If 'all_soc' is selected, ignore individual selections
        if 'all_soc' in selected_socs:
            selected_socs = ['all_soc']

        return {
            "id":          self.id_edit.text().strip(),
            "title":       self.title_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "doc_type":    self.doc_type_combo.currentText(),
            "url":         self.url_edit.text().strip(),
            "image":       self.image_edit.text().strip(),
            "soc":         selected_socs,
            "use-case":    selected_usecases,
            "_feature":    self.feature_combo.currentData(),
        }

# ── Tab widget ────────────────────────────────────────────────────────────────

class DocTab(QWidget):
    """
    Top-level widget for the "Documents" tab.

    Creates a sub-tab for each feature, where each sub-tab shows only the
    documents belonging to that feature. Tab labels show document counts
    that update automatically after add/edit/delete operations.
    """

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create sub-tabs for features
        self.feature_tabs = QTabWidget()

        # Load features from config
        config = load_config()
        features = config.get("features", [])

        if not features:
            # No features defined — show a placeholder
            placeholder = QLabel("No features defined in config.yaml")
            placeholder.setAlignment(Qt.AlignCenter)
            layout.addWidget(placeholder)
            return

        # Store feature table widgets
        self.feature_tables = {}

        # Load all documents once to count them
        all_docs = load_all_documents()

        # Create one sub-tab per feature
        for feature in features:
            feature_id = feature["id"]
            feature_name = feature["name"]

            # Count documents for this feature
            doc_count = len([d for d in all_docs if d.get("_feature") == feature_id])

            # Create a table widget for this feature
            table_widget = FeatureDocTable(feature_id, feature_name, self)
            self.feature_tables[feature_id] = table_widget

            # Add as a tab with document count
            tab_label = f"{feature_name} ({doc_count})"
            self.feature_tabs.addTab(table_widget, tab_label)

        layout.addWidget(self.feature_tabs)

    def refresh_tab_counts(self) -> None:
        """
        Refresh the document count in all tab labels.

        Called after add/edit/delete operations to keep counts accurate.
        """
        all_docs = load_all_documents()

        for idx in range(self.feature_tabs.count()):
            widget = self.feature_tabs.widget(idx)
            if isinstance(widget, FeatureDocTable):
                feature_id = widget.feature_id
                feature_name = widget.feature_name
                doc_count = len([d for d in all_docs if d.get("_feature") == feature_id])

                # Update tab label
                tab_label = f"{feature_name} ({doc_count})"
                self.feature_tabs.setTabText(idx, tab_label)


# ── Feature-specific document table ──────────────────────────────────────────

class FeatureDocTable(QWidget):
    """
    Document table for a single feature.

    Shows only documents belonging to the specified feature.
    Provides Add/Edit/Delete operations scoped to this feature.
    """

    def __init__(self, feature_id: str, feature_name: str, parent_tab=None):
        super().__init__()
        self.feature_id = feature_id
        self.feature_name = feature_name
        self.parent_tab = parent_tab  # Reference to DocTab for refreshing counts
        self.all_docs = []

        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Vertical)
        # Handle thickness is controlled by the stylesheet height property below;
        # do not call setHandleWidth() here as it would override the stylesheet.
        splitter.setStyleSheet(_SPLITTER_STYLE)

        # ── Top pane: table ───────────────────────────────────────────────────
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(5)  # Removed "Feature" column since it's implicit
        self.table.setHorizontalHeaderLabels([
            "Title", "Doc Type", "Use-Cases", "SoCs", "URL"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        top_layout.addWidget(self.table)

        splitter.addWidget(top_widget)

        # ── Bottom pane: read-only detail panel ───────────────────────────────
        detail_box = QGroupBox("Details")
        detail_form = QFormLayout(detail_box)

        self.detail_id = QLineEdit(); self.detail_id.setReadOnly(True)
        self.detail_title = QLineEdit(); self.detail_title.setReadOnly(True)
        self.detail_desc = QLineEdit(); self.detail_desc.setReadOnly(True)
        self.detail_doc_type = QLineEdit(); self.detail_doc_type.setReadOnly(True)
        self.detail_url = QLineEdit(); self.detail_url.setReadOnly(True)
        self.detail_image = QLineEdit(); self.detail_image.setReadOnly(True)
        self.detail_usecases = QLineEdit(); self.detail_usecases.setReadOnly(True)
        self.detail_socs = QTextEdit(); self.detail_socs.setReadOnly(True)
        self.detail_socs.setFixedHeight(48)

        detail_form.addRow("ID:", self.detail_id)
        detail_form.addRow("Title:", self.detail_title)
        detail_form.addRow("Description:", self.detail_desc)
        detail_form.addRow("Doc Type:", self.detail_doc_type)
        detail_form.addRow("URL:", self.detail_url)
        detail_form.addRow("Image:", self.detail_image)
        detail_form.addRow("Use-Cases:", self.detail_usecases)
        detail_form.addRow("SoCs:", self.detail_socs)

        splitter.addWidget(detail_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        for btn in (self.add_btn, self.edit_btn, self.delete_btn):
            btn.setFixedWidth(90)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        self.add_btn.clicked.connect(self.add_doc)
        self.edit_btn.clicked.connect(self.edit_doc)
        self.delete_btn.clicked.connect(self.delete_doc)

        self.refresh()

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload documents for this feature and repopulate the table."""
        all_docs = load_all_documents()

        # Filter to only this feature's documents
        self.all_docs = [d for d in all_docs if d.get("_feature") == self.feature_id]

        self.table.setRowCount(len(self.all_docs))
        for row, doc in enumerate(self.all_docs):
            socs = ", ".join(doc.get("soc") or [])
            use_cases = doc.get("use-case") or []
            if isinstance(use_cases, str):
                use_cases = [use_cases]
            uc_str = ", ".join(use_cases) if use_cases else "—"

            values = [
                doc.get("title", ""),
                doc.get("doc_type", ""),
                uc_str,
                socs,
                doc.get("url", ""),
            ]
            for col, val in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(val))

        self._clear_detail()

        # Update tab counts in parent
        if self.parent_tab:
            self.parent_tab.refresh_tab_counts()

    # ── Detail panel helpers ──────────────────────────────────────────────────

    def _clear_detail(self) -> None:
        for field in (
            self.detail_id, self.detail_title, self.detail_desc,
            self.detail_doc_type, self.detail_url, self.detail_image,
            self.detail_usecases,
        ):
            field.clear()
        self.detail_socs.clear()

    def _on_selection(self) -> None:
        """Populate the detail panel from the selected row's in-memory doc."""
        row = self.selected_row()
        if row is None or row >= len(self.all_docs):
            self._clear_detail()
            return
        doc = self.all_docs[row]
        use_cases = doc.get("use-case") or []
        if isinstance(use_cases, str):
            use_cases = [use_cases]
        socs = doc.get("soc") or []

        self.detail_id.setText(doc.get("id", ""))
        self.detail_title.setText(doc.get("title", ""))
        self.detail_desc.setText(doc.get("description", ""))
        self.detail_doc_type.setText(doc.get("doc_type", ""))
        self.detail_url.setText(doc.get("url", ""))
        self.detail_image.setText(doc.get("image", ""))
        self.detail_usecases.setText(", ".join(use_cases) if use_cases else "—")
        self.detail_socs.setPlainText(", ".join(socs) if socs else "—")

    def selected_row(self):
        """Return the selected row index, or None."""
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    # ── CRUD operations ───────────────────────────────────────────────────────

    def add_doc(self) -> None:
        """Open the Add dialog with this feature pre-selected."""
        try:
            dialog = DocDialog(self)
        except Exception as exc:
            QMessageBox.critical(self, "Configuration Error",
                                  f"Failed to open dialog:\n{exc}\n\n"
                                  "Check that config.yaml and socs.yaml are valid.")
            return

        # Pre-select this feature in the dialog
        idx = dialog.feature_combo.findData(self.feature_id)
        if idx >= 0:
            dialog.feature_combo.setCurrentIndex(idx)
            # Lock the feature combo so user can't change it
            dialog.feature_combo.setEnabled(False)

        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()

            # Ensure the feature is set correctly
            data["_feature"] = self.feature_id

            try:
                filepath = get_feature_filepath(self.feature_id)
            except ValueError as exc:
                QMessageBox.critical(self, "Error", str(exc))
                return

            try:
                _, docs = load_feature_file(filepath)
            except RuntimeError as exc:
                QMessageBox.critical(self, "Error", str(exc))
                return

            if any(d.get("id") == data["id"] for d in docs):
                QMessageBox.warning(self, "Error",
                                    f"Document ID '{data['id']}' already exists.")
                return

            docs.append(data)
            try:
                save_document_file(filepath, self.feature_id, docs)
            except Exception as exc:
                QMessageBox.critical(self, "Save Error",
                                      f"Failed to save document:\n{exc}")
                return
            self.refresh()

    def edit_doc(self) -> None:
        """
        Open the Edit dialog for the selected document.

        Handles feature reassignment: if the user changes the Feature combo,
        the document is removed from the old feature file and appended to the
        new one.  Both writes use atomic temp-file replacement so a partial
        failure cannot corrupt either file.
        """
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Select a document to edit.")
            return

        existing = self.all_docs[row]
        filepath = existing["_filepath"]

        try:
            dialog = DocDialog(self, doc=existing)
        except Exception as exc:
            QMessageBox.critical(self, "Configuration Error",
                                  f"Failed to open dialog:\n{exc}\n\n"
                                  "Check that config.yaml and socs.yaml are valid.")
            return

        # Lock the feature combo (can't move documents between features in this UI)
        dialog.feature_combo.setEnabled(False)

        if dialog.exec() == QDialog.Accepted:
            updated = dialog.get_data()
            updated["_feature"] = self.feature_id  # Ensure feature doesn't change

            try:
                _, docs = load_feature_file(filepath)

                # Stale-document guard
                if not any(d.get("id") == existing.get("id") for d in docs):
                    QMessageBox.warning(
                        self, "Stale Selection",
                        f"Document '{existing.get('id')}' no longer exists.\n"
                        "The table will be refreshed."
                    )
                    self.refresh()
                    return

                # Replace the document in-place
                docs = [updated if d.get("id") == existing.get("id") else d for d in docs]

                save_document_file(filepath, self.feature_id, docs)
            except Exception as exc:
                QMessageBox.critical(self, "Save Error",
                                      f"Failed to save changes:\n{exc}\n\n"
                                      "No data was lost.")
                return

            self.refresh()

    def delete_doc(self) -> None:
        """
        Delete the selected document after confirmation.

        Checks that the document still exists in the file (stale-selection
        guard) before removing it, so the wrong document is never silently
        deleted.
        """
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Select a document to delete.")
            return

        doc = self.all_docs[row]
        doc_id = doc.get("id")
        if not doc_id:
            QMessageBox.warning(self, "Error",
                                "This document has no ID and cannot be safely deleted.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{doc.get('title', '')}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            filepath = doc["_filepath"]
            try:
                feature, docs = load_feature_file(filepath)
            except RuntimeError as exc:
                QMessageBox.critical(self, "Error", str(exc))
                return

            # Stale-document guard
            if not any(d.get("id") == doc_id for d in docs):
                QMessageBox.warning(
                    self, "Stale Selection",
                    f"Document '{doc_id}' no longer exists.\n"
                    "The table will be refreshed."
                )
                self.refresh()
                return

            docs = [d for d in docs if d.get("id") != doc_id]
            try:
                save_document_file(filepath, feature, docs)
            except Exception as exc:
                QMessageBox.critical(self, "Save Error",
                                      f"Failed to delete document:\n{exc}")
                return
            self.refresh()
