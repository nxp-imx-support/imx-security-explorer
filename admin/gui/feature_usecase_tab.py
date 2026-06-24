"""
feature_usecase_tab.py — "Features & Use-Cases" tab for the Admin GUI.

Provides CRUD management for two sections of data/config.yaml:
  • features   (key: "features")
  • use-cases  (key: "use-cases")

Both sections share exactly the same data shape:
    - id          : str  (slug, immutable after creation)
    - name        : str
    - description : str  (optional)

The shared shape is exploited via the reusable SectionTable widget, which is
instantiated twice — once per section — and hosted in a QTabWidget.

Layout (FeatureUseCaseTab)
──────────────────────────
QTabWidget
  ├─ "Features"   tab  →  SectionTable("features",  "Feature")
  └─ "Use-Cases"  tab  →  SectionTable("use-cases", "Use-Case")

Layout (SectionTable — same for both tabs)
──────────────────────────────────────────
┌───────────────────────────────┐
│  QTableWidget (ID/Name/Desc)  │  ← top pane
├───────────────────────────────┤  splitter handle
│  QGroupBox "Details"          │  ← bottom pane (read-only)
├───────────────────────────────┤
│  [Add]  [Edit]  [Delete]      │  ← always visible
└───────────────────────────────┘

Stale-selection safety
──────────────────────
_guard_row() re-reads config.yaml before any mutating operation and checks
that the selected row index is still within bounds.  This prevents acting on
a stale index if the file was modified between the last refresh and the button
click.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QMessageBox, QHeaderView, QTabWidget, QSplitter, QGroupBox
)
from PySide6.QtCore import Qt
from utils import load_config_raw, save_config

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

class EntryDialog(QDialog):
    """
    Generic modal dialog for adding or editing a Feature or Use-Case entry.

    The *label* parameter customises the window title and is set to either
    "Feature" or "Use-Case" by the caller.

    In Add mode (*entry* is None):
      - ID field is editable.
    In Edit mode (*entry* is a dict):
      - ID field is disabled; all other fields are pre-populated.
    """

    def __init__(self, parent=None, entry=None, label="Entry"):
        super().__init__(parent)
        self.setWindowTitle(f"Add {label}" if entry is None else f"Edit {label}")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)

        self.id_edit = QLineEdit(entry.get("id", "") if entry else "")
        self.id_edit.setPlaceholderText("e.g. secure-boot")
        if entry:
            # ID is the primary key — prevent renaming after creation.
            self.id_edit.setEnabled(False)

        self.name_edit = QLineEdit(entry.get("name", "") if entry else "")
        self.desc_edit = QLineEdit(entry.get("description", "") if entry else "")

        layout.addRow("ID:",          self.id_edit)
        layout.addRow("Name:",        self.name_edit)
        layout.addRow("Description:", self.desc_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self) -> None:
        """
        Validate required fields before allowing the dialog to close.

        Keeping validation here instead of in the caller ensures the user's
        input is preserved when a validation error is shown.
        """
        if not self.id_edit.text().strip() or not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation Error",
                                "ID and Name are required.")
            return
        super().accept()

    def get_data(self) -> dict:
        """Return current field values as a plain dict."""
        return {
            "id":          self.id_edit.text().strip(),
            "name":        self.name_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
        }


# ── Reusable section table ────────────────────────────────────────────────────

class SectionTable(QWidget):
    """
    Reusable CRUD table for a single list section within config.yaml.

    Parameters
    ----------
    section_key : str
        The top-level YAML key to manage ("features" or "use-cases").
    label : str
        Human-readable singular name shown in dialogs ("Feature" / "Use-Case").

    State
    -----
    entries : list[dict]
        In-memory snapshot of the managed section as of the last refresh().
        Used by _on_selection() to avoid re-reading the file on every click.
    """

    def __init__(self, section_key: str, label: str):
        super().__init__()
        self.section_key = section_key
        self.label       = label
        self.entries     = []

        main_layout = QVBoxLayout(self)

        # ── Vertical splitter ─────────────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(_SPLITTER_STYLE)

        # ── Top pane: table ───────────────────────────────────────────────────
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        top_layout.addWidget(self.table)

        splitter.addWidget(top_widget)

        # ── Bottom pane: read-only detail panel ───────────────────────────────
        detail_box  = QGroupBox("Details")
        detail_form = QFormLayout(detail_box)

        self.detail_id   = QLineEdit(); self.detail_id.setReadOnly(True)
        self.detail_name = QLineEdit(); self.detail_name.setReadOnly(True)
        self.detail_desc = QLineEdit(); self.detail_desc.setReadOnly(True)

        detail_form.addRow("ID:",          self.detail_id)
        detail_form.addRow("Name:",        self.detail_name)
        detail_form.addRow("Description:", self.detail_desc)

        splitter.addWidget(detail_box)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        self.add_btn    = QPushButton("Add")
        self.edit_btn   = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        for btn in (self.add_btn, self.edit_btn, self.delete_btn):
            btn.setFixedWidth(90)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        self.add_btn.clicked.connect(self.add_entry)
        self.edit_btn.clicked.connect(self.edit_entry)
        self.delete_btn.clicked.connect(self.delete_entry)

        self.refresh()

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """
        Reload config.yaml, extract self.section_key, and repopulate the table.

        Called at construction time and after every mutation.
        """
        config       = load_config_raw()
        self.entries = config.get(self.section_key, [])
        self.table.setRowCount(len(self.entries))
        for row, e in enumerate(self.entries):
            self.table.setItem(row, 0, QTableWidgetItem(e.get("id", "")))
            self.table.setItem(row, 1, QTableWidgetItem(e.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(e.get("description", "")))
        self._clear_detail()

    # ── Detail panel helpers ──────────────────────────────────────────────────

    def _clear_detail(self) -> None:
        for field in (self.detail_id, self.detail_name, self.detail_desc):
            field.clear()

    def _on_selection(self) -> None:
        """Populate detail panel from the selected row's in-memory entry."""
        row = self.selected_row()
        if row is None or row >= len(self.entries):
            self._clear_detail()
            return
        e = self.entries[row]
        self.detail_id.setText(e.get("id", ""))
        self.detail_name.setText(e.get("name", ""))
        self.detail_desc.setText(e.get("description", ""))

    def selected_row(self):
        """Return the selected row index, or None if nothing is selected."""
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _guard_row(self, row: int) -> bool:
        """
        Verify that *row* is still a valid index in the on-disk list.

        Re-reads config.yaml (cheap, small file) and shows a warning if the
        row is out of bounds, then refreshes the table.  Returns True if the
        row is valid and the caller may proceed.
        """
        config  = load_config_raw()
        entries = config.get(self.section_key, [])
        if row >= len(entries):
            QMessageBox.warning(
                self, "Stale Selection",
                "The selection is no longer valid. "
                "The table has been refreshed."
            )
            self.refresh()
            return False
        return True

    # ── CRUD operations ───────────────────────────────────────────────────────

    def add_entry(self) -> None:
        """Open the Add dialog; on acceptance validate and append to config.yaml."""
        dialog = EntryDialog(self, label=self.label)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["id"] or not data["name"]:
                QMessageBox.warning(self, "Error", "ID and Name are required.")
                return

            # Re-read to catch duplicates added by another session.
            config  = load_config_raw()
            entries = config.setdefault(self.section_key, [])
            if any(e.get("id") == data["id"] for e in entries):
                QMessageBox.warning(self, "Error",
                                    f"ID '{data['id']}' already exists.")
                return

            entries.append(data)
            save_config(config)
            self.refresh()

    def edit_entry(self) -> None:
        """
        Open the Edit dialog for the selected row.

        _guard_row() ensures the index is still valid before loading the
        dialog, preventing an edit from overwriting the wrong record.
        """
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "Info",
                                    f"Select a {self.label} to edit.")
            return
        if not self._guard_row(row):
            return

        config  = load_config_raw()
        entries = config.get(self.section_key, [])
        dialog  = EntryDialog(self, entry=entries[row], label=self.label)
        if dialog.exec() == QDialog.Accepted:
            data         = dialog.get_data()
            data["id"]   = entries[row].get("id", "")   # preserve the immutable ID
            entries[row] = data
            save_config(config)
            self.refresh()

    def delete_entry(self) -> None:
        """Delete the selected entry after user confirmation."""
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "Info",
                                    f"Select a {self.label} to delete.")
            return
        if not self._guard_row(row):
            return

        config  = load_config_raw()
        entries = config.get(self.section_key, [])
        entry   = entries[row]
        reply   = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{entry.get('name', entry.get('id', '?'))}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            entries.pop(row)
            save_config(config)
            self.refresh()


# ── Tab widget ────────────────────────────────────────────────────────────────

class FeatureUseCaseTab(QWidget):
    """
    Top-level widget for the "Features & Use-Cases" tab.

    Hosts a QTabWidget with two sub-tabs, each backed by a SectionTable
    that manages the corresponding section of config.yaml.
    """

    def __init__(self):
        super().__init__()
        layout   = QVBoxLayout(self)
        sub_tabs = QTabWidget()
        sub_tabs.addTab(SectionTable("features",  "Feature"),  "Features")
        sub_tabs.addTab(SectionTable("use-cases", "Use-Case"), "Use-Cases")
        layout.addWidget(sub_tabs)