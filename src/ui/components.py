"""
Custom UI components for the ND Data Importer plugin.
Contains reusable widgets and layouts for the plugin interface.
"""

from qgis.PyQt.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLayout, QComboBox,
    QListView, QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QMessageBox,
    QColorDialog, QProgressDialog
)
from qgis.PyQt.QtGui import QFont, QColor, QStandardItemModel, QStandardItem
from qgis.PyQt.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize

from ..utils.logging import log_info, log_error, log_warning, log_debug
from ..config.constants import (
    MAX_SAFE_IMPORT, PARTIAL_IMPORT_LIMIT,
    MAX_SAFE_IMPORT_LOCATION_ONLY, PARTIAL_IMPORT_LIMIT_LOCATION_ONLY
)


class FlowLayout(QLayout):
    """A custom layout that arranges widgets in a flowing manner."""
    
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margin, _, _, _ = self.getContentsMargins()
        size += QSize(2 * margin, 2 * margin)
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        space_x = self.spacing()
        space_y = self.spacing()

        for item in self.itemList:
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()

class Chip(QWidget):
    """A widget representing a single selected item, with a close button."""
    
    removed = pyqtSignal(object)

    def __init__(self, text, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.text = text
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 2, 2)
        layout.setSpacing(4)
        
        self.label = QLabel(text, self)
        
        self.close_button = QPushButton("×", self)
        self.close_button.setFixedSize(16, 16)
        self.close_button.setDefault(False)
        self.close_button.setAutoDefault(False)
        self.close_button.setStyleSheet("""
            QPushButton {
                font-family: "Arial", sans-serif; 
                font-weight: bold; 
                border-radius: 8px;
                border: 1px solid #ccc; 
                background-color: #f0f0f0;
                font-size: 12px;
            }
            QPushButton:hover { 
                background-color: #e0e0e0; 
            }
            QPushButton:pressed { 
                background-color: #d0d0d0; 
            }
        """)
        self.close_button.clicked.connect(self._emit_removed_signal)
        
        layout.addWidget(self.label)
        layout.addWidget(self.close_button)
        
        self.setStyleSheet("""
            Chip { 
                background-color: #e1e1e1; 
                border-radius: 8px; 
                border: 1px solid #c0c0c0; 
            }
        """)

    def _emit_removed_signal(self):
        """Emit the removed signal with this chip's data."""
        self.removed.emit(self.data)

class CheckableComboBox(QComboBox):
    """A combo box that allows multiple selections with checkboxes."""

    selectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setEditable(True)
        self.lineEdit().setReadOnly(True)

        self.setModel(QStandardItemModel(self))

        # Connect to view pressed signal for item interaction
        # This is more reliable than clicked for checkboxes
        self.view().pressed.connect(self.handleItemPressed)

        self._selected_data = []
        self._updating_internally = False  # Flag to prevent recursive updates

        self.lineEdit().setPlaceholderText("Select items...")
        self.lineEdit().setText("")

    def handleItemPressed(self, index):
        """Handle item press to toggle checkbox state."""
        if self._updating_internally:
            return

        item = self.model().itemFromIndex(index)
        if not item:
            return

        # Toggle the checkbox state
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)

        # Handle "All States" logic
        item_data = item.data(Qt.UserRole)
        if item_data == "":  # "All States" selected
            if item.checkState() == Qt.Checked:
                # Uncheck all other items when "All States" is selected
                for i in range(self.model().rowCount()):
                    other_item = self.model().item(i)
                    if other_item and other_item.data(Qt.UserRole) != "":
                        other_item.setCheckState(Qt.Unchecked)
        else:
            # If any specific state is selected, uncheck "All States"
            if item.checkState() == Qt.Checked:
                all_states_item = self.model().item(0)
                if all_states_item and all_states_item.data(Qt.UserRole) == "":
                    all_states_item.setCheckState(Qt.Unchecked)

        self._update_selection()

    def hidePopup(self):
        """Override to maintain popup behavior."""
        super().hidePopup()

    def _update_selection(self):
        """Update internal selection list and emit signal."""
        self._selected_data = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item and item.checkState() == Qt.Checked:
                self._selected_data.append(item.data(Qt.UserRole))
        self.updateDisplayText()
        self.selectionChanged.emit(self.currentData())

    def updateDisplayText(self):
        """Update the display text based on selection."""
        count = len(self._selected_data)
        if count == 0:
            self.lineEdit().setText("")
        elif count == 1:
            for i in range(self.model().rowCount()):
                item = self.model().item(i)
                if item.data(Qt.UserRole) == self._selected_data[0]:
                    self.lineEdit().setText(item.text())
                    return
        else:
            self.lineEdit().setText(f"{count} items selected")

    def addItem(self, text, userData=None):
        """Add an item with optional user data."""
        item = QStandardItem(text)
        item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setData(userData or text, Qt.UserRole)
        item.setCheckState(Qt.Checked if (userData or text) in self._selected_data else Qt.Unchecked)
        self.model().appendRow(item)
    
    def addItems(self, items):
        """Add multiple items from a list of (text, data) tuples."""
        for text, data in items:
            self.addItem(text, data)
    
    def currentData(self):
        """Return the list of selected data values."""
        return self._selected_data

    def setCurrentData(self, data_list):
        """Set the current selection by data values."""
        if not isinstance(data_list, list):
            data_list = []

        self._updating_internally = True
        self._selected_data = data_list
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item:
                item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in data_list else Qt.Unchecked)
        self._updating_internally = False
        self._update_selection()

class DynamicSearchFilterWidget(QWidget):
    """A widget for live search functionality with a results popup and chip display."""
    
    selectionChanged = pyqtSignal(list)
    textChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_items = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Type to search...")
        self.search_box.textChanged.connect(self.textChanged.emit)
        main_layout.addWidget(self.search_box)

        self.chip_container = QWidget(self)
        self.chip_layout = FlowLayout(self.chip_container, spacing=4)
        self.chip_container.setVisible(False)
        main_layout.addWidget(self.chip_container)

        self.popup = QDialog(self, Qt.Popup)
        self.popup_layout = QVBoxLayout(self.popup)
        self.results_list = QListView(self.popup)
        self.results_list.setModel(QStandardItemModel(self.results_list))
        self.results_list.clicked.connect(self.onResultClicked)
        self.popup_layout.addWidget(self.results_list)
        self.popup.setMinimumWidth(300)

    def onResultClicked(self, index):
        """Handle result click to add selected item."""
        item = self.results_list.model().itemFromIndex(index)
        if item:
            self.addItem(item.text(), item.data(Qt.UserRole))
        self.popup.hide()
        self.search_box.clear()

    def showPopup(self, results):
        """Show popup with search results."""
        self.results_list.model().clear()
        for text, data in results:
            item = QStandardItem(text)
            item.setData(data, Qt.UserRole)
            self.results_list.model().appendRow(item)
        if self.results_list.model().rowCount() > 0:
            point = self.mapToGlobal(self.search_box.geometry().bottomLeft())
            self.popup.move(point)
            self.popup.show()
        else:
            self.popup.hide()

    def addItem(self, text, data):
        """Add an item to the selection."""
        if data not in self._selected_items:
            self._selected_items[data] = text
            self._updateChips()
            self.selectionChanged.emit(self.currentData())

    def removeChip(self, data_to_remove):
        """Remove a chip from the selection."""
        if data_to_remove in self._selected_items:
            del self._selected_items[data_to_remove]
            self._updateChips()
            self.selectionChanged.emit(self.currentData())

    def _updateChips(self):
        """Update the chip display."""
        while self.chip_layout.count():
            child = self.chip_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not self._selected_items:
            self.chip_container.setVisible(False)
            return
        for data, text in self._selected_items.items():
            chip = Chip(text, data)
            chip.removed.connect(self.removeChip)
            self.chip_layout.addWidget(chip)
        self.chip_container.setVisible(True)

    def currentData(self):
        """Return the list of selected data values."""
        return list(self._selected_items.keys())

    def setCurrentData(self, data_list):
        """Set the current selection by data values."""
        self._selected_items = {item: item for item in data_list}
        self._updateChips()

class StaticFilterWidget(QWidget):
    """A composite widget that combines a CheckableComboBox with a chip container."""
    
    selectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        self.combo_box = CheckableComboBox(self)
        self.chip_container = QWidget(self)
        self.chip_layout = FlowLayout(self.chip_container, spacing=4)
        self.chip_container.setVisible(False)

        main_layout.addWidget(self.combo_box)
        main_layout.addWidget(self.chip_container)

        self.combo_box.selectionChanged.connect(self.updateChips)
        self.combo_box.selectionChanged.connect(self.selectionChanged.emit)

    def addItems(self, items):
        """Add items to the combo box."""
        self.combo_box.addItems(items)

    def updateItems(self, items):
        """Clear existing items and add new items to the combo box."""
        self.combo_box.clear()
        self.combo_box.addItems(items)
    
    def currentData(self):
        """Return the current selection."""
        return self.combo_box.currentData()
    
    def setCurrentData(self, data_list):
        """Set the current selection."""
        self.combo_box.setCurrentData(data_list)
        self.updateChips(data_list)

    def updateChips(self, selected_data_list):
        """Update the chip display based on selection."""
        while self.chip_layout.count():
            child = self.chip_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not selected_data_list:
            self.chip_container.setVisible(False)
            return
        model = self.combo_box.model()
        for data in selected_data_list:
            display_text = ""
            for i in range(model.rowCount()):
                if model.item(i).data(Qt.UserRole) == data:
                    display_text = model.item(i).text()
                    break
            if display_text:
                chip = Chip(display_text, data)
                chip.removed.connect(self.removeChip)
                self.chip_layout.addWidget(chip)
        self.chip_container.setVisible(True)

    def removeChip(self, data_to_remove):
        """Remove a chip and update selection."""
        current_selection = self.currentData()
        if data_to_remove in current_selection:
            current_selection.remove(data_to_remove)
            self.setCurrentData(current_selection)

class LoginDialog(QDialog):
    """Dialog for user authentication."""
    
    login_attempt = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle("Login - Needle Digital")
        self.setMinimumWidth(350)
        self.setModal(True)
        
        # Email input
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter your email address")
        
        # Password input
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your password")
        
        # Form layout
        form_layout = QFormLayout()
        form_layout.addRow("Email:", self.email_input)
        form_layout.addRow("Password:", self.password_input)
        
        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-weight: bold;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Ok).setText("Login")
        # Fix focus issues
        self.button_box.button(QDialogButtonBox.Ok).setDefault(False)
        self.button_box.button(QDialogButtonBox.Ok).setAutoDefault(False)
        self.button_box.button(QDialogButtonBox.Cancel).setDefault(False) 
        self.button_box.button(QDialogButtonBox.Cancel).setAutoDefault(False)
        self.button_box.accepted.connect(self.handle_login_attempt)
        self.button_box.rejected.connect(self.reject)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.error_label)
        main_layout.addWidget(self.button_box)
        
        # Connect Enter key to login
        self.password_input.returnPressed.connect(self.handle_login_attempt)
    
    def handle_login_attempt(self):
        """Handle login button click."""
        self.error_label.setVisible(False)
        email = self.email_input.text().strip()
        password = self.password_input.text()
        self.login_attempt.emit(email, password)
        
    def on_login_result(self, success, message):
        """Handle login result."""
        if success:
            self.accept()
        else:
            self.error_label.setText(message)
            self.error_label.setVisible(True)
            self.password_input.clear()
            self.password_input.setFocus()

    def get_credentials(self):
        """Get entered credentials."""
        return self.email_input.text().strip(), self.password_input.text()

class LayerOptionsDialog(QDialog):
    """Dialog for configuring layer import options."""
    
    def __init__(self, default_name="Imported Layer", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Layer Import Options")
        self.setModal(True)
        
        # Layer name input
        self.layer_name_input = QLineEdit(default_name)
        
        # Color selection
        self.color_button = QPushButton("Select Point Color")
        self.color_button.setDefault(False)
        self.color_button.setAutoDefault(False)
        self.selected_color = QColor(255, 0, 0)  # Default red
        self.update_color_button_stylesheet()
        self.color_button.clicked.connect(self.select_color)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        # Layout
        layout = QFormLayout(self)
        layout.addRow("Layer Name:", self.layer_name_input)
        layout.addRow("Point Color:", self.color_button)
        layout.addWidget(self.button_box)

    def select_color(self):
        """Open color picker dialog."""
        color = QColorDialog.getColor(self.selected_color, self, "Choose Point Color")
        if color.isValid():
            self.selected_color = color
            self.update_color_button_stylesheet()

    def update_color_button_stylesheet(self):
        """Update the color button appearance."""
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.selected_color.name()};
                border: 2px solid #333;
                padding: 8px;
                font-weight: bold;
            }}
        """)

    def get_options(self):
        """Get the configured options."""
        return self.layer_name_input.text(), self.selected_color

class LargeImportWarningDialog(QDialog):
    """Dialog to warn users about large dataset imports."""
    
    # Constants for user choices
    IMPORT_ALL = 1
    IMPORT_PARTIAL = 2
    CANCEL = 0
    
    def __init__(self, record_count: int, is_location_only: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Large Dataset Import Warning")
        self.setModal(True)
        self.setMinimumWidth(450)

        self.record_count = record_count
        self.is_location_only = is_location_only
        self.user_choice = self.CANCEL

        # Use appropriate limits based on data type
        self.max_safe_import = MAX_SAFE_IMPORT_LOCATION_ONLY if is_location_only else MAX_SAFE_IMPORT
        self.partial_limit = PARTIAL_IMPORT_LIMIT_LOCATION_ONLY if is_location_only else PARTIAL_IMPORT_LIMIT
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Warning icon and title
        title_layout = QHBoxLayout()
        warning_label = QLabel("⚠️")
        warning_label.setStyleSheet("font-size: 24px;")
        title_label = QLabel("Large Dataset Import")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        title_layout.addWidget(warning_label)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # Warning message
        message_text = f"""
You are about to import {record_count:,} records to QGIS.

Performance Impact:
• QGIS may become unresponsive during import.
• Large datasets can cause memory issues.
• Consider importing a subset for testing first.
        """
        
        message_label = QLabel(message_text)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("padding: 12px; background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; color: #333;")
        layout.addWidget(message_label)
        
        # Options
        options_label = QLabel("<b>What would you like to do?</b>")
        layout.addWidget(options_label)
        
        # Buttons
        button_layout = QVBoxLayout()
        
        # Import all button
        self.import_all_btn = QPushButton(f"Import All {record_count:,} Records")
        self.import_all_btn.setStyleSheet("padding: 8px; font-weight: bold;")
        if record_count > self.max_safe_import:
            self.import_all_btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: #ffebee; color: #c62828;")
            self.import_all_btn.setText(f"⚠️ Import All {record_count:,} Records (Not Recommended)")

        # Import partial button
        partial_count = min(self.partial_limit, record_count)
        self.import_partial_btn = QPushButton(f"Import First {partial_count:,} Records")
        self.import_partial_btn.setStyleSheet("padding: 8px; background-color: #e8f5e8; color: #2e7d32;")
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel Import")
        self.cancel_btn.setStyleSheet("padding: 8px;")
        
        button_layout.addWidget(self.import_all_btn)
        button_layout.addWidget(self.import_partial_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.import_all_btn.clicked.connect(self._import_all)
        self.import_partial_btn.clicked.connect(self._import_partial)
        self.cancel_btn.clicked.connect(self._cancel)
        
        # Set default focus
        if record_count > self.max_safe_import:
            self.import_partial_btn.setDefault(True)
        else:
            self.import_all_btn.setDefault(True)
    
    def _import_all(self):
        """User chose to import all records."""
        self.user_choice = self.IMPORT_ALL
        self.accept()
    
    def _import_partial(self):
        """User chose to import partial records."""
        self.user_choice = self.IMPORT_PARTIAL
        self.accept()
    
    def _cancel(self):
        """User chose to cancel import."""
        self.user_choice = self.CANCEL
        self.reject()
    
    def get_user_choice(self):
        """Get the user's choice after dialog closes."""
        return self.user_choice

class ImportProgressDialog(QProgressDialog):
    """Progress dialog for chunked imports with cancellation."""
    
    def __init__(self, total_records: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importing Data to QGIS")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self.total_records = total_records
        self.processed_records = 0
        
        # Set up progress dialog
        self.setMinimum(0)
        self.setMaximum(total_records)
        self.setValue(0)
        
        # Labels
        self.setLabelText(f"Preparing to import {total_records:,} records...")
        self.setCancelButtonText("Cancel Import")
        
        # Don't auto-reset or auto-close
        self.setAutoReset(False)
        self.setAutoClose(False)
        
        # Show immediately
        self.show()
    
    def update_progress(self, processed: int, chunk_info: str = ""):
        """Update progress with current status."""
        self.processed_records = processed
        self.setValue(processed)
        
        # Calculate percentage
        percentage = int((processed / self.total_records) * 100) if self.total_records > 0 else 0
        
        # Update label with detailed information
        if chunk_info:
            label_text = f"Importing records... ({percentage}%)\n{chunk_info}\nProcessed: {processed:,} of {self.total_records:,}"
        else:
            label_text = f"Importing records... ({percentage}%)\nProcessed: {processed:,} of {self.total_records:,}"
        
        self.setLabelText(label_text)
        
        # Process events to keep UI responsive
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.processEvents()
    
    def finish_import(self, success: bool, final_count: int, message: str = ""):
        """Finish the import process."""
        if success:
            self.setLabelText(f"✅ Import completed successfully!\nImported {final_count:,} records to QGIS.\n{message}")
        else:
            self.setLabelText(f"❌ Import failed or was cancelled.\nProcessed {self.processed_records:,} of {self.total_records:,} records.\n{message}")
        
        self.setCancelButtonText("Close")
        self.setValue(self.maximum())  # Set to 100%