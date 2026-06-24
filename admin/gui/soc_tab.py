"""
soc_tab.py — "SoCs" tab for the i.MX Security Explorer Admin GUI.

Provides a full CRUD interface for the SoC catalogue stored in
data/socs.yaml.  All reads and writes go through utils.load_socs() /
utils.save_socs() so the file is never opened directly here.

Layout (top → bottom)
──────────────────────
┌─────────────────────────────────────┐
│  QTableWidget  (ID / Name / Family  │  ← top pane of QSplitter
│                / Description)       │
├─────────────────────────────────────┤  splitter handle
│  QGroupBox "Details"                │  ← bottom pane (read-only fields)
├─────────────────────────────────────┤
│  [Add]  [Edit]  [Delete]            │  ← always visible, outside splitter
└─────────────────────────────────────┘

Stale-selection safety
──────────────────────
Between the time a row is selected and the time Edit/Delete is acted on, an
external process could modify socs.yaml.  edit_soc() and delete_soc() reload
the file and locate the target by *ID* rather than by row index, so they are
safe even if rows have been inserted or removed in the meantime.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QHeaderView, QSplitter, QGroupBox
)
from PySide6.QtCore import Qt
from utils import load_socs, save_socs, load_config

# ── Shared splitter style ─────────────────────────────────────────────────────
# Applied to all QSplitter instances in the admin GUI for a consistent look.
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

class SocDialog(QDialog):
    """
    Modal dialog for adding or editing a single SoC entry.

    When *soc* is None the dialog is in "Add" mode:
      - The ID field is editable.

    When *soc* is a dict the dialog is in "Edit" mode:
      - The ID field is disabled (IDs are immutable after creation).
      - All other fields are pre-populated from the existing entry.

    The Family combo box is populated from config.yaml → families so that
    only families defined in the configuration can be assigned.
    """

    def __init__(self, parent=None, soc=None):
        super().__init__(parent)
        self.setWindowTitle("Add SoC" if soc is None else "Edit SoC")
        self.setMinimumWidth(420)

        # Load families from config so the combo reflects the current config.
        config   = load_config()
        families = config.get("families", [])

        layout = QFormLayout(self)

        # ── ID field ──────────────────────────────────────────────────────────
        self.id_edit = QLineEdit(soc["id"] if soc else "")
        self.id_edit.setPlaceholderText("e.g. imx93")
        if soc:
            # Prevent accidental renaming — the ID is the primary key used to
            # locate this record in the YAML file.
            self.id_edit.setEnabled(False)

        self.name_edit = QLineEdit(soc.get("name", "") if soc else "")
        self.desc_edit = QLineEdit(soc.get("description", "") if soc else "")

        # ── Family combo ──────────────────────────────────────────────────────
        # userData for each item is the family *id* string; displayText is the
        # human-readable name.  This keeps the stored value stable even if the
        # display name is later changed in config.yaml.
        self.family_combo = QComboBox()
        for f in families:
            self.family_combo.addItem(f["name"], f["id"])
        if soc and soc.get("family"):
            idx = self.family_combo.findData(soc["family"])
            if idx >= 0:
                self.family_combo.setCurrentIndex(idx)

        layout.addRow("ID:",          self.id_edit)
        layout.addRow("Name:",        self.name_edit)
        layout.addRow("Family:",      self.family_combo)
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
        """Return the current field values as a dict ready to store in YAML."""
        return {
            "id":          self.id_edit.text().strip(),
            "name":        self.name_edit.text().strip(),
            # currentData() returns the family *id* stored as userData.
            "family":      self.family_combo.currentData(),
            "description": self.desc_edit.text().strip(),
        }


# ── Tab widget ────────────────────────────────────────────────────────────────

class SocTab(QWidget):
    """
    Top-level widget for the "SoCs" tab.

    State
    -----
    all_socs : list[dict]
        In-memory snapshot of the SoC list as of the last refresh().
        Used by _on_selection() to populate the detail panel without re-reading
        the file on every selection change.

    The snapshot is refreshed after every add / edit / delete operation and
    also at construction time.
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)

        # ── Vertical splitter: table (top) + detail panel (bottom) ────────────
        splitter = QSplitter(Qt.Vertical)
        # Handle thickness is controlled by the stylesheet height property below;
        # do not call setHandleWidth() here as it would override the stylesheet.
        splitter.setStyleSheet(_SPLITTER_STYLE)

        # ── Top pane: table ───────────────────────────────────────────────────
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Family", "Description"])
        # Each column stretches equally to fill the available width.
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        # Update the detail panel whenever the selection changes.
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        top_layout.addWidget(self.table)

        splitter.addWidget(top_widget)

        # ── Bottom pane: read-only detail panel ───────────────────────────────
        detail_box  = QGroupBox("Details")
        detail_form = QFormLayout(detail_box)

        self.detail_id     = QLineEdit(); self.detail_id.setReadOnly(True)
        self.detail_name   = QLineEdit(); self.detail_name.setReadOnly(True)
        self.detail_family = QLineEdit(); self.detail_family.setReadOnly(True)
        self.detail_desc   = QLineEdit(); self.detail_desc.setReadOnly(True)

        detail_form.addRow("ID:",          self.detail_id)
        detail_form.addRow("Name:",        self.detail_name)
        detail_form.addRow("Family:",      self.detail_family)
        detail_form.addRow("Description:", self.detail_desc)

        splitter.addWidget(detail_box)

        # Give the table 3× more vertical space than the detail panel.
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # ── Buttons (outside splitter so they are always visible) ─────────────
        btn_layout = QHBoxLayout()
        self.add_btn    = QPushButton("Add")
        self.edit_btn   = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        for btn in (self.add_btn, self.edit_btn, self.delete_btn):
            btn.setFixedWidth(90)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()   # push buttons to the left
        main_layout.addLayout(btn_layout)

        self.add_btn.clicked.connect(self.add_soc)
        self.edit_btn.clicked.connect(self.edit_soc)
        self.delete_btn.clicked.connect(self.delete_soc)

        self.all_socs = []
        self.refresh()

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """
        Reload socs.yaml and repopulate the table.

        Called after every mutation (add / edit / delete) and at startup.
        Also clears the detail panel to avoid showing stale data for the
        previously selected row.
        """
        self.all_socs = load_socs()
        self.table.setRowCount(len(self.all_socs))
        for row, s in enumerate(self.all_socs):
            values = [
                s.get("id", ""),
                s.get("name", ""),
                s.get("family", ""),
                s.get("description", ""),
            ]
            for col, val in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(val) if val else ""))
        self._clear_detail()

    # ── Detail panel helpers ──────────────────────────────────────────────────

    def _clear_detail(self) -> None:
        """Clear all read-only detail fields (called after refresh or deselect)."""
        for field in (self.detail_id, self.detail_name,
                      self.detail_family, self.detail_desc):
            field.clear()

    def _on_selection(self) -> None:
        """
        Populate the detail panel from the currently selected row.

        Uses the in-memory snapshot (self.all_socs) rather than re-reading the
        file, so this is cheap and always consistent with what the table shows.
        """
        row = self.selected_row()
        if row is None or row >= len(self.all_socs):
            self._clear_detail()
            return
        s = self.all_socs[row]
        self.detail_id.setText(s.get("id", ""))
        self.detail_name.setText(s.get("name", ""))
        self.detail_family.setText(s.get("family", ""))
        self.detail_desc.setText(s.get("description", ""))

    def selected_row(self):
        """Return the index of the currently selected row, or None."""
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    # ── CRUD operations ───────────────────────────────────────────────────────

    def add_soc(self) -> None:
        """Open the Add dialog; on acceptance validate and append to socs.yaml."""
        dialog = SocDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()

            # Reload from disk to check for duplicates added by another session.
            socs = load_socs()
            if any(s["id"] == data["id"] for s in socs):
                QMessageBox.warning(self, "Error",
                                    f"SoC ID '{data['id']}' already exists.")
                return

            socs.append(data)
            save_socs(socs)
            self.refresh()

    def edit_soc(self) -> None:
        """
        Open the Edit dialog for the selected row.

        Locates the record by ID in a freshly loaded list to be safe against
        concurrent modifications since the last refresh.
        """
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Select a SoC to edit.")
            return

        # Capture the ID from the snapshot (safe even if socs.yaml was modified).
        original = self.all_socs[row]
        socs     = load_socs()

        # Find by ID — not by index — so the correct record is edited even if
        # rows were inserted or removed since the last refresh.
        live_row = next(
            (i for i, s in enumerate(socs) if s.get("id") == original.get("id")),
            None
        )
        if live_row is None:
            QMessageBox.warning(self, "Stale Selection",
                                "This SoC no longer exists. "
                                "The table has been refreshed.")
            self.refresh()
            return

        dialog = SocDialog(self, soc=socs[live_row])
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            # Merge the updated fields over the existing record, preserving any
            # keys not exposed by the dialog (future-proofing).
            merged       = {**socs[live_row], **data}
            merged["id"] = socs[live_row]["id"]   # ID must never change
            socs[live_row] = merged
            save_socs(socs)
            self.refresh()

    def delete_soc(self) -> None:
        """
        Delete the selected SoC after confirmation.

        Like edit_soc(), locates the record by ID in a fresh load before
        removing it, so the wrong entry is never deleted due to a stale index.
        """
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Select a SoC to delete.")
            return

        original = self.all_socs[row]
        socs     = load_socs()

        live_row = next(
            (i for i, s in enumerate(socs) if s.get("id") == original.get("id")),
            None
        )
        if live_row is None:
            QMessageBox.warning(self, "Stale Selection",
                                "This SoC no longer exists. "
                                "The table has been refreshed.")
            self.refresh()
            return

        soc   = socs[live_row]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{soc.get('name', soc.get('id', '?'))}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            socs.pop(live_row)
            save_socs(socs)
            self.refresh()
