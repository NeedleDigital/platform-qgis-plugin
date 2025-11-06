"""
Custom UI components for the ND Data Importer plugin.
Contains reusable widgets and layouts for the plugin interface.
"""

from qgis.PyQt.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLayout, QComboBox,
    QListView, QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QMessageBox,
    QColorDialog, QProgressDialog, QScrollArea, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QToolButton, QDoubleSpinBox, QApplication
)
from qgis.PyQt.QtGui import QFont, QColor, QStandardItemModel, QStandardItem, QCursor, QIcon
from qgis.PyQt.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize, QEvent, QTimer
from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsMapToolZoom, QgsMapTool, QgsRubberBand
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsCoordinateReferenceSystem, QgsRectangle,
    QgsGeometry, QgsPointXY, QgsWkbTypes, QgsFeature, QgsFillSymbol, QgsRasterLayer
)

from ..utils.logging import log_info, log_error, log_warning, log_debug
from ..config.constants import (
    MAX_SAFE_IMPORT, OSM_LAYER_NAME, OSM_LAYER_URL, PARTIAL_IMPORT_LIMIT, TRACE_SCALE_THRESHOLD
)


def get_theme_aware_button_style() -> str:
    """Get theme-aware styling for dialog buttons (OK, Cancel, Close).

    Returns:
        CSS stylesheet string for QPushButton
    """
    palette = QApplication.palette()
    window_color = palette.color(palette.Window)
    is_dark_theme = window_color.lightness() < 128

    if is_dark_theme:
        return """
            QPushButton {
                background-color: #3C3C3C;
                color: #FFFFFF;
                border: 1px solid #555555;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
                border: 1px solid #666666;
            }
            QPushButton:pressed {
                background-color: #2A2A2A;
            }
            QPushButton:default {
                background-color: #0D47A1;
                border: 1px solid #1976D2;
            }
            QPushButton:default:hover {
                background-color: #1565C0;
                border: 1px solid #1E88E5;
            }
        """
    else:
        return """
            QPushButton {
                background-color: #F5F5F5;
                color: #000000;
                border: 1px solid #CCCCCC;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #E0E0E0;
                border: 1px solid #999999;
            }
            QPushButton:pressed {
                background-color: #D5D5D5;
            }
            QPushButton:default {
                background-color: #2196F3;
                color: #FFFFFF;
                border: 1px solid #1976D2;
            }
            QPushButton:default:hover {
                background-color: #1E88E5;
                border: 1px solid #1565C0;
            }
        """


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
        layout.setContentsMargins(6, 2, 2, 2)
        layout.setSpacing(4)

        self.label = QLabel(text, self)

        self.close_button = QPushButton("×", self)
        self.close_button.setFixedSize(14, 14)
        self.close_button.setDefault(False)
        self.close_button.setAutoDefault(False)

        # Detect theme (dark or light)
        from qgis.PyQt.QtWidgets import QApplication
        palette = QApplication.palette()
        window_color = palette.color(palette.Window)
        is_dark_theme = window_color.lightness() < 128

        # Theme-aware button styling with proper contrast
        if is_dark_theme:
            button_bg = "#E3F2FD"
            button_hover = "#BBDEFB"
            button_pressed = "#90CAF9"
            button_text = "#0D47A1"
        else:
            button_bg = "#1976D2"
            button_hover = "#1565C0"
            button_pressed = "#0D47A1"
            button_text = "#FFFFFF"

        self.close_button.setStyleSheet(f"""
            QPushButton {{
                font-family: "Arial", sans-serif;
                font-weight: bold;
                border-radius: 7px;
                border: none;
                background-color: {button_bg};
                color: {button_text};
                font-size: 11px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {button_hover};
            }}
            QPushButton:pressed {{
                background-color: {button_pressed};
            }}
        """)
        self.close_button.clicked.connect(self._emit_removed_signal)

        layout.addWidget(self.label)
        layout.addWidget(self.close_button)

        # Theme-aware chip styling with blue accent
        if is_dark_theme:
            chip_bg = "#0D47A1"
            chip_border = "#1976D2"
            chip_text = "#E3F2FD"
        else:
            chip_bg = "#E3F2FD"
            chip_border = "#2196F3"
            chip_text = "#0D47A1"

        self.setStyleSheet(f"""
            Chip {{
                background-color: {chip_bg};
                border-radius: 10px;
                border: 1px solid {chip_border};
            }}
            Chip QLabel {{
                color: {chip_text};
                font-size: 11px;
                font-weight: 500;
            }}
        """)

    def _emit_removed_signal(self):
        """Emit the removed signal with this chip's data."""
        self.removed.emit(self.data)

class ViewAllChip(QWidget):
    """A chip-like widget that looks like a chip but shows 'view all' functionality."""

    clicked = pyqtSignal()

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(4)

        self.label = QLabel(text, self)
        layout.addWidget(self.label)

        self.setStyleSheet("""
            ViewAllChip {
                background-color: #d1e7ff;
                border-radius: 8px;
                border: 1px solid #4dabf7;
            }
            ViewAllChip:hover {
                background-color: #a8d8ff;
                cursor: pointer;
            }
        """)

    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class MessageBar(QWidget):
    """A message bar widget that shows messages with different types (info, success, warning, error)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)  # Hidden by default
        try:
            self.hide_timer = QTimer()
            self.hide_timer.setSingleShot(True)
            self.hide_timer.timeout.connect(self.hide_message)
            self.setupUI()
        except Exception as e:
            # If there's an error setting up MessageBar, just create a basic QLabel as fallback
            layout = QHBoxLayout(self)
            self.message_label = QLabel("MessageBar initialization failed")
            layout.addWidget(self.message_label)

    def setupUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Message text
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        # Close button
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(self.hide_message)
        layout.addWidget(self.close_button)

    def show_message(self, message, message_type="info", duration=3000):
        """Show a message with specified type and duration."""
        try:
            if hasattr(self, 'message_label'):
                self.message_label.setText(f"[{message_type.upper()}] {message}")
            else:
                # Fallback if setupUI failed
                return

            # Detect theme for appropriate styling
            from PyQt5.QtWidgets import QApplication
            palette = QApplication.palette()
            window_color = palette.color(palette.Window)
            is_dark_theme = window_color.lightness() < 128

            # Theme-aware styling based on message type
            # Message bars should be bright enough to stand out in both themes
            if message_type.lower() == "success":
                bg_color = "#2E7D32" if is_dark_theme else "#4CAF50"
                self.setStyleSheet(f"background-color: {bg_color}; color: white; padding: 8px; border-radius: 4px;")
            elif message_type.lower() == "error" or message_type.lower() == "critical":
                bg_color = "#C62828" if is_dark_theme else "#f44336"
                self.setStyleSheet(f"background-color: {bg_color}; color: white; padding: 8px; border-radius: 4px;")
            elif message_type.lower() == "warning":
                bg_color = "#EF6C00" if is_dark_theme else "#FF9800"
                self.setStyleSheet(f"background-color: {bg_color}; color: white; padding: 8px; border-radius: 4px;")
            else:  # info
                bg_color = "#1565C0" if is_dark_theme else "#2196F3"
                self.setStyleSheet(f"background-color: {bg_color}; color: white; padding: 8px; border-radius: 4px;")

            self.setVisible(True)

            # Set timer to auto-hide after duration
            if duration > 0 and hasattr(self, 'hide_timer'):
                self.hide_timer.start(duration)
        except Exception as e:
            # If there's any error, just show the message without styling
            if hasattr(self, 'message_label'):
                self.message_label.setText(message)
                self.setVisible(True)

    def hide_message(self):
        """Hide the message bar."""
        try:
            if hasattr(self, 'hide_timer'):
                self.hide_timer.stop()
            self.setVisible(False)
        except Exception as e:
            # If there's an error, at least try to hide the widget
            self.setVisible(False)

class AllSelectedItemsDialog(QDialog):
    """Dialog to show all selected items in a scrollable view."""

    item_removed = pyqtSignal(object)

    def __init__(self, selected_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("All Selected Companies")
        self.setModal(True)
        self.setMinimumSize(400, 300)
        self.selected_items = selected_items.copy()  # Make a copy to avoid modifying original

        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel(f"Selected Companies ({len(self.selected_items)})")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Scroll area for chips
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Container widget for chips
        container_widget = QWidget()
        self.container_layout = FlowLayout(container_widget, spacing=4)
        scroll_area.setWidget(container_widget)

        layout.addWidget(scroll_area)

        # Update chips display
        self.update_chips_display()

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def update_chips_display(self):
        """Update the chip display in the dialog."""
        # Clear existing chips
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add chips for all selected items
        for data, text in self.selected_items.items():
            chip = Chip(text, data)
            chip.removed.connect(self.on_chip_removed)
            self.container_layout.addWidget(chip)

    def on_chip_removed(self, data):
        """Handle chip removal from the dialog."""
        if data in self.selected_items:
            del self.selected_items[data]
            self.item_removed.emit(data)
            self.update_chips_display()

            # Update title
            title_label = self.findChild(QLabel)
            if title_label:
                title_label.setText(f"Selected Companies ({len(self.selected_items)})")

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

        # Create container for search box with icons
        search_container = QWidget(self)
        search_container.setFixedHeight(30)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        # Detect theme for styling
        from qgis.PyQt.QtWidgets import QApplication
        palette = QApplication.palette()
        window_color = palette.color(palette.Window)
        is_dark_theme = window_color.lightness() < 128

        # Theme-aware colors
        if is_dark_theme:
            border_color = "#555555"
            bg_color = "#2b2b2b"
            text_color = "#E0E0E0"
            icon_color = "#888888"
        else:
            border_color = "#C0C0C0"
            bg_color = "#FFFFFF"
            text_color = "#000000"
            icon_color = "#666666"

        # Search icon label (left side)
        self.search_icon = QLabel("🔍", search_container)
        self.search_icon.setFixedWidth(28)
        self.search_icon.setAlignment(Qt.AlignCenter)
        self.search_icon.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {icon_color};
                font-size: 12px;
                padding: 0px;
                border: 1px solid {border_color};
                border-right: none;
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
            }}
        """)

        self.search_box = QLineEdit(search_container)
        self.search_box.setPlaceholderText("Type to search...")
        self.search_box.textChanged.connect(self.textChanged.emit)
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                padding: 6px 8px;
                border: 1px solid {border_color};
                border-left: none;
                border-right: none;
                background-color: {bg_color};
                color: {text_color};
                font-size: 13px;
            }}
            QLineEdit:hover {{
                border-color: {border_color};
            }}
            QLineEdit:focus {{
                border-color: {border_color};
                outline: none;
            }}
        """)

        # Create loading indicator (circular spinner) - positioned on the right
        self.loading_label = QLabel(self)
        self.loading_label.setFixedSize(30, 30)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setVisible(False)
        self.loading_label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: red;
                font-size: 24px;
                border: 1px solid {border_color};
                border-left: none;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)

        # Create a simple animated loading indicator using Unicode spinner
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self._update_loading_animation)
        self.loading_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.loading_frame_index = 0

        # Dropdown arrow icon label (right side, hidden when loading)
        self.dropdown_icon = QLabel("▼", search_container)
        self.dropdown_icon.setFixedWidth(28)
        self.dropdown_icon.setAlignment(Qt.AlignCenter)
        self.dropdown_icon.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {icon_color};
                font-size: 10px;
                padding: 0px;
                border: 1px solid {border_color};
                border-left: none;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)

        search_layout.addWidget(self.search_icon)
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(self.loading_label)
        search_layout.addWidget(self.dropdown_icon)

        main_layout.addWidget(search_container)

        self.chip_container = QWidget(self)
        self.chip_layout = FlowLayout(self.chip_container, spacing=4)
        self.chip_container.setVisible(False)
        main_layout.addWidget(self.chip_container)

        self.popup = QDialog(self, Qt.Popup)
        self.popup_layout = QVBoxLayout(self.popup)
        self.results_list = QListView(self.popup)
        self.results_list.setModel(QStandardItemModel(self.results_list))
        self.results_list.clicked.connect(self.onResultClicked)
        # Prevent the list from taking keyboard focus
        self.results_list.setFocusPolicy(Qt.NoFocus)
        self.popup_layout.addWidget(self.results_list)
        self.popup.setMinimumWidth(300)
        # Prevent the popup dialog from taking keyboard focus
        self.popup.setFocusPolicy(Qt.NoFocus)
        # Install event filter on the popup to redirect keyboard events
        self.popup.installEventFilter(self)
        self.results_list.installEventFilter(self)

    def onResultClicked(self, index):
        """Handle result click to add selected item."""
        item = self.results_list.model().itemFromIndex(index)
        if item:
            self.addItem(item.text(), item.data(Qt.UserRole))
            # Remove the selected item from the current results to avoid re-selection
            self.results_list.model().removeRow(index.row())

            # Keep popup open if there are still results, close if empty
            if self.results_list.model().rowCount() == 0:
                self.popup.hide()
                self.search_box.clear()

        # Always restore focus to search box after selection
        self.search_box.setFocus()

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
            # Ensure search box maintains focus after popup is shown
            self.search_box.setFocus()
            # Force focus to stay on the search box by raising it
            self.search_box.raise_()
            # Process events to ensure focus is properly set
            from qgis.PyQt.QtWidgets import QApplication
            QApplication.processEvents()
            self.search_box.setFocus()  # Set focus again to be sure
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
        """Update the chip display with 4+ item limitation."""
        # Clear existing chips
        while self.chip_layout.count():
            child = self.chip_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._selected_items:
            self.chip_container.setVisible(False)
            return

        selected_items_list = list(self._selected_items.items())
        total_items = len(selected_items_list)

        if total_items <= 4:
            # Show all chips if 4 or fewer
            for data, text in selected_items_list:
                chip = Chip(text, data)
                chip.removed.connect(self.removeChip)
                self.chip_layout.addWidget(chip)
        else:
            # Show first 4 chips + "view all" button
            for data, text in selected_items_list[:4]:
                chip = Chip(text, data)
                chip.removed.connect(self.removeChip)
                self.chip_layout.addWidget(chip)

            # Add "view all" chip-like button
            remaining_count = total_items - 4
            view_all_chip = ViewAllChip(f"+ {remaining_count} more")
            view_all_chip.clicked.connect(self.show_all_items_dialog)
            self.chip_layout.addWidget(view_all_chip)

        self.chip_container.setVisible(True)

    def currentData(self):
        """Return the list of selected data values."""
        return list(self._selected_items.keys())

    def setCurrentData(self, data_list):
        """Set the current selection by data values."""
        self._selected_items = {item: item for item in data_list}
        self._updateChips()

    def eventFilter(self, obj, event):
        """Event filter to redirect keyboard events from popup to search box."""
        if obj == self.popup or obj == self.results_list:
            if event.type() == QEvent.KeyPress:
                # Handle Escape key to close popup
                if event.key() == Qt.Key_Escape:
                    self.popup.hide()
                    self.search_box.clear()
                    self.search_box.setFocus()
                    return True

                # Redirect key press events to the search box
                if self.search_box.isVisible() and self.search_box.isEnabled():
                    # Send the key event to the search box
                    from qgis.PyQt.QtWidgets import QApplication
                    QApplication.sendEvent(self.search_box, event)
                    return True  # Event handled
        return super().eventFilter(obj, event)

    def show_all_items_dialog(self):
        """Show dialog with all selected items."""
        dialog = AllSelectedItemsDialog(self._selected_items, self)
        dialog.item_removed.connect(self.removeChip)
        if dialog.exec_() == QDialog.Accepted:
            # Update the main widget's selected items from the dialog
            # in case items were removed in the dialog
            self._selected_items = dialog.selected_items.copy()
            self._updateChips()
            self.selectionChanged.emit(self.currentData())

    def show_loading(self):
        """Show loading indicator and start animation."""
        self.dropdown_icon.setVisible(False)
        self.loading_label.setVisible(True)
        self.loading_frame_index = 0
        self.loading_timer.start(100)  # Update every 100ms

    def hide_loading(self):
        """Hide loading indicator and stop animation."""
        self.loading_timer.stop()
        self.loading_label.setVisible(False)
        self.dropdown_icon.setVisible(True)

    def _update_loading_animation(self):
        """Update the loading animation frame."""
        self.loading_label.setText(self.loading_frames[self.loading_frame_index])
        self.loading_frame_index = (self.loading_frame_index + 1) % len(self.loading_frames)

    def has_unselected_text(self):
        """Check if there's text in the search box that hasn't been selected.

        Returns True only if there's text AND no items are selected.
        If items are selected, the text will be cleared automatically.
        """
        has_text = bool(self.search_box.text().strip())
        has_selections = bool(self._selected_items)

        # Only return True if there's text but NO selections
        return has_text and not has_selections

    def clear_search_text(self):
        """Clear the search text field."""
        self.search_box.clear()

class SearchableStaticFilterWidget(QWidget):
    """A widget for searchable static data with chip display (no API calls)."""

    selectionChanged = pyqtSignal(list)

    def __init__(self, static_data=None, parent=None, show_all_chips=False, show_search_icon=True, read_only=False):
        super().__init__(parent)
        self._selected_items = {}
        self._static_data = static_data or []  # List of strings or tuples (display, value)
        self._show_all_chips = show_all_chips  # Control whether to show all chips or limit to 4
        self._show_search_icon = show_search_icon  # Control whether to show search icon
        self._read_only = read_only  # Control whether search box is read-only (click-only selection)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # Create a container for the search box with icons
        search_container = QWidget(self)
        search_container.setFixedHeight(30)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        # Detect theme for styling
        from qgis.PyQt.QtWidgets import QApplication
        palette = QApplication.palette()
        window_color = palette.color(palette.Window)
        is_dark_theme = window_color.lightness() < 128

        # Theme-aware colors
        if is_dark_theme:
            border_color = "#555555"
            bg_color = "#2b2b2b"
            text_color = "#E0E0E0"
            placeholder_color = "#888888"
            hover_border = "#2196F3"
            focus_border = "#1976D2"
            icon_color = "#888888"
        else:
            border_color = "#C0C0C0"
            bg_color = "#FFFFFF"
            text_color = "#000000"
            placeholder_color = "#999999"
            hover_border = "#2196F3"
            focus_border = "#1976D2"
            icon_color = "#666666"

        # Search icon label (left side) - conditionally shown
        if self._show_search_icon:
            self.search_icon = QLabel("🔍", search_container)
            self.search_icon.setFixedWidth(28)
            self.search_icon.setAlignment(Qt.AlignCenter)
            self.search_icon.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    color: {icon_color};
                    font-size: 12px;
                    padding: 0px;
                    border: 1px solid {border_color};
                    border-right: none;
                    border-top-left-radius: 4px;
                    border-bottom-left-radius: 4px;
                }}
            """)

        self.search_box = QLineEdit(search_container)

        # Set read-only mode if specified
        if self._read_only:
            self.search_box.setReadOnly(True)
            self.search_box.setPlaceholderText("Click to select...")
        else:
            self.search_box.setPlaceholderText("Click to select or type to search...")
            self.search_box.textChanged.connect(self._on_search_text_changed)

        # Adjust search box borders based on whether search icon is shown
        if self._show_search_icon:
            search_box_style = f"""
                QLineEdit {{
                    padding: 6px 8px;
                    border: 1px solid {border_color};
                    border-left: none;
                    border-right: none;
                    background-color: {bg_color};
                    color: {text_color};
                    font-size: 13px;
                }}
                QLineEdit:hover {{
                    border-color: {border_color};
                }}
                QLineEdit:focus {{
                    border-color: {border_color};
                    outline: none;
                }}
            """
        else:
            search_box_style = f"""
                QLineEdit {{
                    padding: 6px 8px;
                    border: 1px solid {border_color};
                    border-right: none;
                    border-top-left-radius: 4px;
                    border-bottom-left-radius: 4px;
                    background-color: {bg_color};
                    color: {text_color};
                    font-size: 13px;
                }}
                QLineEdit:hover {{
                    border-color: {border_color};
                }}
                QLineEdit:focus {{
                    border-color: {border_color};
                    outline: none;
                }}
            """

        self.search_box.setStyleSheet(search_box_style)

        # Dropdown arrow icon label (right side)
        self.dropdown_icon = QLabel("▼", search_container)
        self.dropdown_icon.setFixedWidth(28)
        self.dropdown_icon.setAlignment(Qt.AlignCenter)
        self.dropdown_icon.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {icon_color};
                font-size: 10px;
                padding: 0px;
                border: 1px solid {border_color};
                border-left: none;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)

        # Add widgets to layout based on whether search icon is shown
        if self._show_search_icon:
            search_layout.addWidget(self.search_icon)
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(self.dropdown_icon)

        main_layout.addWidget(search_container)

        # Store original mouse press event
        self._original_mouse_press_event = self.search_box.mousePressEvent
        # Override mouse press event to show all options on click
        self.search_box.mousePressEvent = self._on_search_box_mouse_press

        self.chip_container = QWidget(self)
        self.chip_layout = FlowLayout(self.chip_container, spacing=6)
        self.chip_container.setVisible(False)
        main_layout.addWidget(self.chip_container)

        self.popup = QDialog(self, Qt.Popup)
        self.popup_layout = QVBoxLayout(self.popup)
        self.popup_layout.setContentsMargins(0, 0, 0, 0)
        self.popup_layout.setSpacing(0)

        self.results_list = QListView(self.popup)
        self.results_list.setModel(QStandardItemModel(self.results_list))
        self.results_list.clicked.connect(self.onResultClicked)
        # Prevent the list from taking keyboard focus
        self.results_list.setFocusPolicy(Qt.NoFocus)

        # Enhanced popup styling with theme-awareness
        if is_dark_theme:
            popup_bg = "#2b2b2b"
            popup_border = "#555555"
            item_text = "#E0E0E0"
            item_hover_bg = "#0D47A1"
            item_selected_bg = "#1565C0"
        else:
            popup_bg = "#FFFFFF"
            popup_border = "#C0C0C0"
            item_text = "#000000"
            item_hover_bg = "#E3F2FD"
            item_selected_bg = "#BBDEFB"

        self.popup.setStyleSheet(f"""
            QDialog {{
                background-color: {popup_bg};
                border: 1px solid {popup_border};
                border-radius: 4px;
            }}
        """)

        self.results_list.setStyleSheet(f"""
            QListView {{
                background-color: {popup_bg};
                color: {item_text};
                border: none;
                outline: none;
                padding: 4px;
                font-size: 13px;
            }}
            QListView::item {{
                padding: 8px 10px;
                border-radius: 3px;
                margin: 2px;
            }}
            QListView::item:hover {{
                background-color: {item_hover_bg};
            }}
            QListView::item:selected {{
                background-color: {item_selected_bg};
            }}
        """)

        self.popup_layout.addWidget(self.results_list)
        self.popup.setMinimumWidth(300)
        # Prevent the popup dialog from taking keyboard focus
        self.popup.setFocusPolicy(Qt.NoFocus)
        # Install event filter on the popup to redirect keyboard events
        self.popup.installEventFilter(self)
        self.results_list.installEventFilter(self)

    def setStaticData(self, data):
        """Set the static data for searching."""
        self._static_data = data

    def _on_search_text_changed(self, text):
        """Handle search text changes and show filtered results."""
        query = text.strip().lower()
        if not query:
            self.popup.hide()
            return

        # Filter static data based on query
        filtered_results = []
        for item in self._static_data:
            if isinstance(item, tuple):
                display_text, value = item
                if query in display_text.lower() or query in value.lower():
                    filtered_results.append((display_text, value))
            elif isinstance(item, str):
                if query in item.lower():
                    filtered_results.append((item, item))

        if filtered_results:
            self.showPopup(filtered_results)
        else:
            self.popup.hide()

    def _on_search_box_mouse_press(self, event):
        """Handle mouse press event on search box to show all options."""
        # Call original mouse press event first to handle normal behavior
        self._original_mouse_press_event(event)

        # Show all options if search box is empty
        if not self.search_box.text().strip():
            self._show_all_options()

    def _show_all_options(self):
        """Show all available options in the popup."""
        all_results = []
        for item in self._static_data:
            if isinstance(item, tuple):
                display_text, value = item
                # Exclude already selected items
                if value not in self._selected_items:
                    all_results.append((display_text, value))
            elif isinstance(item, str):
                # Exclude already selected items
                if item not in self._selected_items:
                    all_results.append((item, item))

        if all_results:
            self.showPopup(all_results)

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
            # Ensure search box maintains focus after popup is shown
            self.search_box.setFocus()
            # Force focus to stay on the search box by raising it
            self.search_box.raise_()
            # Process events to ensure focus is properly set
            from qgis.PyQt.QtWidgets import QApplication
            QApplication.processEvents()
            self.search_box.setFocus()  # Set focus again to be sure
        else:
            self.popup.hide()

    def onResultClicked(self, index):
        """Handle result click to add selected item."""
        item = self.results_list.model().itemFromIndex(index)
        if item:
            self.addItem(item.text(), item.data(Qt.UserRole))
            # Remove the selected item from the current results to avoid re-selection
            self.results_list.model().removeRow(index.row())

            # Keep popup open if there are still results, close if empty
            if self.results_list.model().rowCount() == 0:
                self.popup.hide()
                self.search_box.clear()

        # Always restore focus to search box after selection
        self.search_box.setFocus()

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
        """Update the chip display with 4+ item limitation."""
        # Clear existing chips
        while self.chip_layout.count():
            child = self.chip_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._selected_items:
            self.chip_container.setVisible(False)
            return

        selected_items_list = list(self._selected_items.items())
        total_items = len(selected_items_list)

        if total_items <= 4:
            # Show all chips if 4 or fewer
            for data, text in selected_items_list:
                chip = Chip(text, data)
                chip.removed.connect(self.removeChip)
                self.chip_layout.addWidget(chip)
        else:
            # Show first 4 chips + "view all" button
            for data, text in selected_items_list[:4]:
                chip = Chip(text, data)
                chip.removed.connect(self.removeChip)
                self.chip_layout.addWidget(chip)

            # Add "view all" chip-like button
            remaining_count = total_items - 4
            view_all_chip = ViewAllChip(f"+ {remaining_count} more")
            view_all_chip.clicked.connect(self.show_all_items_dialog)
            self.chip_layout.addWidget(view_all_chip)

        self.chip_container.setVisible(True)

    def currentData(self):
        """Return the list of selected data values."""
        return list(self._selected_items.keys())

    def setCurrentData(self, data_list):
        """Set the current selection by data values."""
        self._selected_items = {item: item for item in data_list}
        self._updateChips()

    def set_show_all_chips(self, show_all):
        """Set whether to show all chips or limit to 4."""
        self._show_all_chips = show_all
        self._updateChips()  # Refresh display

    def eventFilter(self, obj, event):
        """Event filter to redirect keyboard events from popup to search box."""
        if obj == self.popup or obj == self.results_list:
            if event.type() == QEvent.KeyPress:
                # Handle Escape key to close popup
                if event.key() == Qt.Key_Escape:
                    self.popup.hide()
                    self.search_box.clear()
                    self.search_box.setFocus()
                    return True

                # Redirect key press events to the search box
                if self.search_box.isVisible() and self.search_box.isEnabled():
                    # Send the key event to the search box
                    from qgis.PyQt.QtWidgets import QApplication
                    QApplication.sendEvent(self.search_box, event)
                    return True  # Event handled
        return super().eventFilter(obj, event)

    def show_all_items_dialog(self):
        """Show dialog with all selected items."""
        dialog = AllSelectedItemsDialog(self._selected_items, self)
        dialog.item_removed.connect(self.removeChip)
        if dialog.exec_() == QDialog.Accepted:
            # Update the main widget's selected items from the dialog
            # in case items were removed in the dialog
            self._selected_items = dialog.selected_items.copy()
            self._updateChips()
            self.selectionChanged.emit(self.currentData())

    def has_unselected_text(self):
        """Check if there's text in the search box that hasn't been selected.

        Returns True only if there's text AND no items are selected.
        If items are selected, the text will be cleared automatically.
        """
        has_text = bool(self.search_box.text().strip())
        has_selections = bool(self._selected_items)

        # Only return True if there's text but NO selections
        return has_text and not has_selections

    def clear_search_text(self):
        """Clear the search text field."""
        self.search_box.clear()

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

    def __init__(self, parent=None, api_client=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle("Login - Needle Digital")
        self.setMinimumWidth(350)
        self.setModal(True)
        self.api_client = api_client

        # Email input
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter your email address")

        # Auto-fill email if available
        if self.api_client:
            last_email = self.api_client.get_last_login_email()
            if last_email:
                self.email_input.setText(last_email)

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

        # Apply theme-aware button styling
        button_style = get_theme_aware_button_style()
        self.button_box.button(QDialogButtonBox.Ok).setStyleSheet(button_style)
        self.button_box.button(QDialogButtonBox.Cancel).setStyleSheet(button_style)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.error_label)
        main_layout.addWidget(self.button_box)
        
        # Connect Enter key to login
        self.password_input.returnPressed.connect(self.handle_login_attempt)

        # Set focus: password if email is pre-filled, otherwise email
        if self.email_input.text():
            self.password_input.setFocus()
        else:
            self.email_input.setFocus()

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

    def __init__(self, default_name="Imported Layer", is_assay_data=False, parent=None):
        """
        Initialize layer options dialog.

        Args:
            default_name: Default layer name
            is_assay_data: True if importing assay data (shows trace range options)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Layer Import Options")
        self.setModal(True)
        self.is_assay_data = is_assay_data
        self.trace_range_config = None

        # Initialize trace config for assay data
        if self.is_assay_data:
            from ..config.trace_ranges import get_industry_standard_preset
            self.trace_range_config = get_industry_standard_preset()

        self._setup_ui(default_name)

    def _setup_ui(self, default_name):
        """Setup the dialog UI."""
        from ..config.trace_ranges import get_available_presets

        layout = QVBoxLayout(self)
        self.setMinimumWidth(600)

        # Form layout for basic options
        form_layout = QFormLayout()

        # For assay data, show group name, collar layer name, and trace layer name
        if self.is_assay_data:
            # Group name
            self.group_name_input = QLineEdit(default_name + " Group")
            form_layout.addRow("Group Name:", self.group_name_input)

            # Collar layer name
            self.collar_layer_name_input = QLineEdit(default_name + " - Collars")
            form_layout.addRow("Collar Layer Name:", self.collar_layer_name_input)

            # Trace layer name
            self.trace_layer_name_input = QLineEdit(default_name + " - Traces")
            form_layout.addRow("Trace Layer Name:", self.trace_layer_name_input)
        else:
            # For holes, just layer name
            self.layer_name_input = QLineEdit(default_name)
            form_layout.addRow("Layer Name:", self.layer_name_input)

        # Create a horizontal layout for styling controls
        point_style_layout = QHBoxLayout()
        
        # --- Point Size Widgets (SpinBox with label) ---
        # Add size label
        point_style_layout.addWidget(QLabel("Point Size:"))
        # Point size input (Already defined)
        self.point_size_spin = NoScrollDoubleSpinBox()
        self.point_size_spin.setRange(1.0, 20.0)
        self.point_size_spin.setDecimals(1)
        self.point_size_spin.setValue(3.0)
        self.point_size_spin.setSuffix(" px")
        self.point_size_spin.setFocusPolicy(Qt.StrongFocus) 

        point_style_layout.addWidget(self.point_size_spin)
        
        # --- Spacing (12 pixels) ---
        point_style_layout.addSpacing(12)

        # --- Point Color Widgets (Button with label) ---
        # Add color label
        point_style_layout.addWidget(QLabel("Color:"))
        # Color selection button (Already defined with its style)
        self.color_button = QPushButton()
        self.color_button.setFixedHeight(20)
        self.color_button.setFixedWidth(48)
        self.color_button.setAutoDefault(False)
        # ... connect and style button (ensure the rounded style is applied)
        self.selected_color = QColor(255, 0, 0)
        self.update_color_button_stylesheet() # Make sure this applies the rounded style
        self.color_button.clicked.connect(self.select_color)

        point_style_layout.addWidget(self.color_button)


        # --- Add Stretch to Push Elements to the Left ---
        # This line is crucial: it pushes the combined widgets to the left and fills the rest of the row.
        point_style_layout.addStretch()

        # Add the final layout to your form
        form_layout.addRow("Styling:", point_style_layout)

        layout.addLayout(form_layout)

        # Trace range configuration section (only for assay data)
        if self.is_assay_data:
            # Separator
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            layout.addWidget(separator)

            # Trace range section
            trace_group_label = QLabel("Trace Range Configuration")
            trace_font = QFont()
            trace_font.setBold(True)
            trace_group_label.setFont(trace_font)
            layout.addWidget(trace_group_label)

            # Preset selector
            preset_layout = QHBoxLayout()
            preset_label = QLabel("Preset:")
            preset_layout.addWidget(preset_label)

            self.trace_preset_combo = QComboBox()
            for preset_name in get_available_presets():
                display_name = f"{preset_name}"
                self.trace_preset_combo.addItem(display_name, preset_name)  # Store original name as data
            self.trace_preset_combo.addItem("Custom")  # Add Custom option
            self.trace_preset_combo.setCurrentText("Default")
            self.trace_preset_combo.currentTextChanged.connect(self._on_preset_changed)
            self.trace_preset_combo.setFocusPolicy(Qt.ClickFocus)  # Prevent wheel scrolling when not focused
            preset_layout.addWidget(self.trace_preset_combo, stretch=1)
            preset_layout.addStretch()

            layout.addLayout(preset_layout)

            # Trace scale visibility configuration
            scale_layout = QHBoxLayout()
            scale_label = QLabel("Trace Visibility Scale:")
            scale_label.setToolTip("Map scale at which trace lines become visible.\nLower values = need to zoom in more to see traces.\nDefault: 1:50,000")
            scale_layout.addWidget(scale_label)

            self.trace_scale_spin = QDoubleSpinBox()
            self.trace_scale_spin.setRange(1000, 500000)  # Reasonable range for map scales
            self.trace_scale_spin.setDecimals(0)
            self.trace_scale_spin.setValue(TRACE_SCALE_THRESHOLD)  # Default from constants
            self.trace_scale_spin.setSuffix("")
            self.trace_scale_spin.setPrefix("1:")
            self.trace_scale_spin.setSingleStep(10000)
            self.trace_scale_spin.setToolTip("Traces visible when zoomed in closer than this scale.\nExample: 1:50,000 means traces show at scales like 1:25,000, 1:10,000, etc.")
            self.trace_scale_spin.setFocusPolicy(Qt.StrongFocus)
            scale_layout.addWidget(self.trace_scale_spin)
            scale_layout.addStretch()

            layout.addLayout(scale_layout)

            # Scroll area for range widgets
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMinimumHeight(250)
            scroll_area.setMaximumHeight(400)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

            self.ranges_container = QWidget()
            self.ranges_layout = QVBoxLayout(self.ranges_container)
            self.ranges_layout.setContentsMargins(0, 0, 0, 0)
            self.ranges_layout.setSpacing(0)

            scroll_area.setWidget(self.ranges_container)
            layout.addWidget(scroll_area)

            # Add/Remove buttons (only visible when Custom selected)
            button_layout = QHBoxLayout()
            self.add_range_button = QPushButton("+ Add Range")
            self.add_range_button.clicked.connect(self._add_range)
            self.add_range_button.setVisible(False)  # Hidden by default
            button_layout.addWidget(self.add_range_button)
            button_layout.addStretch()
            layout.addLayout(button_layout)

            # Initialize range widgets list
            self.range_widgets = []

            # Populate initial ranges
            self._populate_ranges()

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

        # Apply theme-aware button styling
        button_style = get_theme_aware_button_style()
        self.button_box.button(QDialogButtonBox.Ok).setStyleSheet(button_style)
        self.button_box.button(QDialogButtonBox.Cancel).setStyleSheet(button_style)

        layout.addWidget(self.button_box)

        # Apply theme-aware styling to combo boxes
        if self.is_assay_data:
            self._apply_combobox_styling()

    def _populate_ranges(self):
        """Populate range widgets from current configuration."""
        # Clear existing widgets
        for widget in self.range_widgets:
            widget.deleteLater()
        self.range_widgets.clear()

        # Add widget for each range
        for trace_range in self.trace_range_config.ranges:
            self._add_range_widget(trace_range)

        # Add stretch at the end
        self.ranges_layout.addStretch()

        # Update editability based on preset
        is_custom = self.trace_preset_combo.currentText() == "Custom"
        self._set_ranges_editable(is_custom)

        # Apply theme-aware styling to newly added combo boxes
        self._apply_combobox_styling()

    def _add_range_widget(self, trace_range):
        """Add a range widget to the layout."""
        widget = TraceRangeWidget(trace_range)
        widget.removed.connect(self._remove_range_widget)
        widget.changed.connect(self._mark_as_custom)
        self.range_widgets.append(widget)

        # Insert before the stretch
        self.ranges_layout.insertWidget(len(self.range_widgets) - 1, widget)

    def _add_range(self):
        """Add a new empty range."""
        from ..config.trace_ranges import TraceRange, BoundaryFormula, RangeType
        from qgis.PyQt.QtGui import QColor

        # Create a default range
        new_range = TraceRange(
            "New Range",
            QColor(150, 150, 150),
            BoundaryFormula(RangeType.DIRECT_PPM, 0.0),
            BoundaryFormula(RangeType.DIRECT_PPM, 100.0)
        )
        self._add_range_widget(new_range)

    def _remove_range_widget(self, widget):
        """Remove a range widget."""
        from ..config.constants import MIN_TRACE_RANGES

        if len(self.range_widgets) <= MIN_TRACE_RANGES:
            QMessageBox.warning(
                self,
                "Cannot Remove Range",
                f"You must have at least {MIN_TRACE_RANGES} ranges."
            )
            return

        if widget in self.range_widgets:
            self.range_widgets.remove(widget)
            widget.deleteLater()

    def _mark_as_custom(self):
        """Mark configuration as custom when user edits."""
        if self.trace_preset_combo.currentText() != "Custom":
            self.trace_preset_combo.blockSignals(True)
            self.trace_preset_combo.setCurrentText("Custom")
            self.trace_preset_combo.blockSignals(False)

    def _set_ranges_editable(self, editable):
        """Enable/disable editing of range widgets."""
        for widget in self.range_widgets:
            widget.setEnabled(editable)

        # Show/hide add button
        if hasattr(self, 'add_range_button'):
            self.add_range_button.setVisible(editable)

    def _apply_combobox_styling(self):
        """Apply theme-aware styling to all combo boxes in the dialog."""
        try:
            from PyQt5.QtWidgets import QApplication
            palette = QApplication.palette()
            window_color = palette.color(palette.Window)
            is_dark_theme = window_color.lightness() < 128

            if is_dark_theme:
                combobox_style = """
                    QComboBox {
                        color: #FFFFFF;
                        background-color: #3C3C3C;
                        border: 1px solid #555555;
                        padding: 3px 25px 3px 3px;
                    }
                    QComboBox:hover {
                        border: 1px solid #777777;
                    }
                    QComboBox:disabled {
                        color: #808080;
                        background-color: #2A2A2A;
                        border: 1px solid #444444;
                    }
                    QComboBox::drop-down {
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 20px;
                        border-left: 1px solid #555555;
                        background-color: #4A4A4A;
                    }
                    QComboBox::drop-down:hover {
                        background-color: #555555;
                    }
                    QComboBox::drop-down:disabled {
                        background-color: #2A2A2A;
                        border-left: 1px solid #444444;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-left: 4px solid transparent;
                        border-right: 4px solid transparent;
                        border-top: 6px solid #FFFFFF;
                        width: 0px;
                        height: 0px;
                    }
                    QComboBox::down-arrow:disabled {
                        border-top: 6px solid #555555;
                    }
                    QComboBox QAbstractItemView {
                        color: #FFFFFF;
                        background-color: #3C3C3C;
                        selection-background-color: #4A4A4A;
                        selection-color: #FFFFFF;
                    }
                """
            else:
                combobox_style = """
                    QComboBox {
                        color: #000000;
                        background-color: #FFFFFF;
                        border: 1px solid #CCCCCC;
                        padding: 3px 25px 3px 3px;
                    }
                    QComboBox:hover {
                        border: 1px solid #999999;
                    }
                    QComboBox:disabled {
                        color: #999999;
                        background-color: #F5F5F5;
                        border: 1px solid #E0E0E0;
                    }
                    QComboBox::drop-down {
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 20px;
                        border-left: 1px solid #CCCCCC;
                        background-color: #F0F0F0;
                    }
                    QComboBox::drop-down:hover {
                        background-color: #E0E0E0;
                    }
                    QComboBox::drop-down:disabled {
                        background-color: #F5F5F5;
                        border-left: 1px solid #E0E0E0;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-left: 4px solid transparent;
                        border-right: 4px solid transparent;
                        border-top: 6px solid #000000;
                        width: 0px;
                        height: 0px;
                    }
                    QComboBox::down-arrow:disabled {
                        border-top: 6px solid #BBBBBB;
                    }
                    QComboBox QAbstractItemView {
                        color: #000000;
                        background-color: #FFFFFF;
                        selection-background-color: #E3F2FD;
                        selection-color: #000000;
                    }
                """

            # Apply to trace preset combo
            self.trace_preset_combo.setStyleSheet(combobox_style)

            # Apply to all range widget combos (lower/upper type combos)
            for widget in self.range_widgets:
                if hasattr(widget, 'lower_type_combo'):
                    widget.lower_type_combo.setStyleSheet(combobox_style)
                if hasattr(widget, 'upper_type_combo'):
                    widget.upper_type_combo.setStyleSheet(combobox_style)

        except Exception:
            # Fail silently - styling is optional
            pass

    def _on_preset_changed(self, preset_name):
        """Handle preset selection change."""
        from ..config.trace_ranges import get_preset_by_name, get_industry_standard_preset, TraceRange

        if preset_name == "Custom":
            # Load Default as template with generic "Range N" names
            industry_config = get_industry_standard_preset()
            custom_ranges = []
            for idx, preset_range in enumerate(industry_config.ranges, start=1):
                custom_range = TraceRange(
                    name=f"Range {idx}",
                    color=preset_range.color,
                    lower_boundary=preset_range.lower_boundary,
                    upper_boundary=preset_range.upper_boundary
                )
                custom_ranges.append(custom_range)

            # Update config with custom ranges
            from ..config.trace_ranges import TraceRangeConfiguration
            self.trace_range_config = TraceRangeConfiguration(custom_ranges, "Custom")
            self._populate_ranges()
        else:
            # Extract actual preset name from display name (remove " (Cannot edit)" suffix)
            actual_preset_name = preset_name.replace(" (Cannot edit)", "")
            # Load preset configuration
            self.trace_range_config = get_preset_by_name(actual_preset_name)
            self._populate_ranges()

    def _on_accept(self):
        """Validate and accept the configuration."""
        if self.is_assay_data:
            # Get all ranges from widgets
            ranges = [widget.get_trace_range() for widget in self.range_widgets]

            # Validate minimum number of ranges
            if len(ranges) < 2:
                QMessageBox.warning(
                    self,
                    "Invalid Configuration",
                    "You must define at least 2 ranges."
                )
                return

            # Validate range configuration
            validation_result = self._validate_ranges(ranges)
            if not validation_result['valid']:
                QMessageBox.warning(
                    self,
                    "Invalid Range Configuration",
                    validation_result['message']
                )
                return

            # Update configuration
            from ..config.trace_ranges import TraceRangeConfiguration
            self.trace_range_config = TraceRangeConfiguration(
                ranges,
                self.trace_preset_combo.currentText()
            )

        self.accept()

    def _validate_ranges(self, ranges):
        """
        Validate trace range configuration.

        Checks for:
        - Empty range names
        - Duplicate range names
        - Logical consistency (lower < upper for direct PPM values)

        Args:
            ranges: List of TraceRange objects

        Returns:
            Dictionary with 'valid' (bool) and 'message' (str) keys
        """
        from ..config.trace_ranges import RangeType

        # Check for empty names
        for i, r in enumerate(ranges):
            if not r.name or r.name.strip() == "" or r.name == "Unnamed Range":
                return {
                    'valid': False,
                    'message': f"Range {i + 1} has no name. Please provide a name for all ranges."
                }

        # Check for duplicate names
        names = [r.name for r in ranges]
        if len(names) != len(set(names)):
            duplicates = [name for name in names if names.count(name) > 1]
            return {
                'valid': False,
                'message': f"Duplicate range names found: {', '.join(set(duplicates))}. Each range must have a unique name."
            }

        # Check logical consistency for direct PPM ranges
        for i, r in enumerate(ranges):
            # If both boundaries are direct PPM values, verify lower < upper
            if (r.lower_boundary.formula_type == RangeType.DIRECT_PPM and
                r.upper_boundary.formula_type == RangeType.DIRECT_PPM):
                if r.lower_boundary.value >= r.upper_boundary.value:
                    return {
                        'valid': False,
                        'message': f"Range '{r.name}': Lower boundary ({r.lower_boundary.value}) must be less than upper boundary ({r.upper_boundary.value})."
                    }

        return {'valid': True, 'message': ''}

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
                border: 1px solid #333;
                padding: 8px;
                font-weight: bold;
                border-radius: 0px; 
            }}
            QPushButton:hover {{
                cursor:pointer
            }}
        """)

    def get_options(self):
        """Get the configured options.

        Returns:
            For assay data: (group_name, collar_layer_name, trace_layer_name, point_size, color, trace_config, trace_scale)
            For holes: (layer_name, point_size, color)
        """
        if self.is_assay_data:
            return (
                self.group_name_input.text(),
                self.collar_layer_name_input.text(),
                self.trace_layer_name_input.text(),
                self.point_size_spin.value(),
                self.selected_color,
                self.trace_range_config,
                self.trace_scale_spin.value()
            )
        else:
            return (
                self.layer_name_input.text(),
                self.point_size_spin.value(),
                self.selected_color
            )

class LargeImportWarningDialog(QDialog):
    """Dialog to warn users about large dataset imports."""
    
    # Constants for user choices
    IMPORT_ALL = 1
    IMPORT_PARTIAL = 2
    CANCEL = 0
    
    def __init__(self, record_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Large Dataset Import Warning")
        self.setModal(True)
        self.setMinimumWidth(450)

        self.record_count = record_count
        self.user_choice = self.CANCEL

        # Use standard limits
        self.max_safe_import = MAX_SAFE_IMPORT
        self.partial_limit = PARTIAL_IMPORT_LIMIT
        
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

        # Apply theme-aware button styling
        button_style = get_theme_aware_button_style()
        self.cancel_btn.setStyleSheet(button_style)

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


class FetchDetailsDialog(QDialog):
    """Dialog to show detailed information about fetched records."""

    def __init__(self, fetch_info: dict, parent=None):
        """
        Initialize the fetch details dialog.

        Args:
            fetch_info: Dictionary containing:
                - total_fetched: Number of records fetched
                - requested_count: Number of records requested
                - fetch_time: Time taken to fetch in seconds
                - state_contributions: Dict of state -> count
                - data_type: 'Holes' or 'Assays'
        """
        super().__init__(parent)
        self.fetch_info = fetch_info
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("Fetch Details")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # Summary section
        summary_label = QLabel("Fetch Summary")
        summary_font = QFont()
        summary_font.setBold(True)
        summary_font.setPointSize(12)
        summary_label.setFont(summary_font)
        layout.addWidget(summary_label)

        # Add separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator1)

        # Summary info
        total_fetched = self.fetch_info.get('total_fetched', 0)
        requested_count = self.fetch_info.get('requested_count', 0)
        fetch_time = self.fetch_info.get('fetch_time', 0)
        data_type = self.fetch_info.get('data_type', 'Records')

        summary_text = f"<b>Data Type:</b> {data_type}<br>"
        summary_text += f"<b>Records Fetched:</b> {total_fetched:,}<br>"
        summary_text += f"<b>Records Requested:</b> {requested_count:,}<br>"
        summary_text += f"<b>Time Taken:</b> {fetch_time:.1f} seconds"

        summary_info = QLabel(summary_text)
        summary_info.setTextFormat(Qt.RichText)
        summary_info.setWordWrap(True)
        summary_info.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px; color: #333333;")
        layout.addWidget(summary_info)

        # Show message if fetched < requested
        if total_fetched < requested_count:
            availability_msg = QLabel(
                f"ℹ️ Only {total_fetched:,} records are available in our database for the selected filters. "
                f"This is the complete dataset matching your criteria."
            )
            availability_msg.setWordWrap(True)
            availability_msg.setStyleSheet(
                "padding: 10px; background-color: #fff3cd; border: 1px solid #ffc107; "
                "border-radius: 5px; color: #856404; margin-top: 10px;"
            )
            layout.addWidget(availability_msg)

        layout.addSpacing(20)

        # State contributions section
        state_label = QLabel("State-wise Distribution")
        state_font = QFont()
        state_font.setBold(True)
        state_font.setPointSize(12)
        state_label.setFont(state_font)
        layout.addWidget(state_label)

        # Add separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)

        # State contributions table
        state_contributions = self.fetch_info.get('state_contributions', {})

        if state_contributions:
            table = QTableWidget()
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["State", "Records", "Percentage"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionBehavior(QTableWidget.SelectRows)

            # Sort states by record count (descending)
            sorted_states = sorted(
                state_contributions.items(),
                key=lambda x: x[1],
                reverse=True
            )

            table.setRowCount(len(sorted_states))

            for row, (state, count) in enumerate(sorted_states):
                # State name
                state_item = QTableWidgetItem(state if state else "Unknown")
                table.setItem(row, 0, state_item)

                # Record count
                count_item = QTableWidgetItem(f"{count:,}")
                count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(row, 1, count_item)

                # Percentage
                percentage = (count / total_fetched * 100) if total_fetched > 0 else 0
                percentage_item = QTableWidgetItem(f"{percentage:.1f}%")
                percentage_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(row, 2, percentage_item)

            layout.addWidget(table)
        else:
            no_data_label = QLabel("No state-wise distribution data available.")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: #666; font-style: italic; padding: 20px;")
            layout.addWidget(no_data_label)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)

        # Apply theme-aware button styling
        button_style = get_theme_aware_button_style()
        button_box.button(QDialogButtonBox.Close).setStyleSheet(button_style)

        layout.addWidget(button_box)


class BoundingBoxRectangleTool(QgsMapTool):
    """Custom map tool for drawing bounding box rectangles by click and drag."""

    rectangle_created = pyqtSignal(QgsRectangle)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubberBand = None
        self.startPoint = None
        self.endPoint = None
        self.isDrawing = False

        # Create rubber band for visual feedback
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(QColor(255, 0, 0, 100))  # Semi-transparent red
        self.rubberBand.setWidth(2)
        self.rubberBand.setLineStyle(Qt.DashLine)

    def canvasPressEvent(self, event):
        """Handle mouse press - start drawing rectangle."""
        if event.button() == Qt.LeftButton:
            self.startPoint = self.toMapCoordinates(event.pos())
            self.endPoint = self.startPoint
            self.isDrawing = True
            self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def canvasMoveEvent(self, event):
        """Handle mouse move - update rectangle preview."""
        if not self.isDrawing:
            return

        self.endPoint = self.toMapCoordinates(event.pos())
        self._updateRubberBand()

    def canvasReleaseEvent(self, event):
        """Handle mouse release - finalize rectangle."""
        if event.button() == Qt.LeftButton and self.isDrawing:
            self.endPoint = self.toMapCoordinates(event.pos())
            self.isDrawing = False

            # Create rectangle and emit signal
            rect = QgsRectangle(self.startPoint, self.endPoint)
            if not rect.isEmpty():
                self.rectangle_created.emit(rect)

    def _updateRubberBand(self):
        """Update rubber band to show current rectangle."""
        if self.startPoint is None or self.endPoint is None:
            return

        # Create rectangle points
        rect = QgsRectangle(self.startPoint, self.endPoint)
        points = [
            QgsPointXY(rect.xMinimum(), rect.yMinimum()),
            QgsPointXY(rect.xMaximum(), rect.yMinimum()),
            QgsPointXY(rect.xMaximum(), rect.yMaximum()),
            QgsPointXY(rect.xMinimum(), rect.yMaximum()),
            QgsPointXY(rect.xMinimum(), rect.yMinimum())  # Close the rectangle
        ]

        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        for point in points:
            self.rubberBand.addPoint(point, True)
        self.rubberBand.show()

    def reset(self):
        """Reset the tool."""
        self.startPoint = None
        self.endPoint = None
        self.isDrawing = False
        if self.rubberBand:
            self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def deactivate(self):
        """Clean up when tool is deactivated."""
        super().deactivate()
        if self.rubberBand:
            self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)


class PolygonSelectionDialog(QDialog):
    """Interactive map dialog for selecting a polygon over Australia."""

    def __init__(self, parent=None, existing_polygon=None):
        """
        Initialize the polygon selection map dialog.

        Args:
            parent: Parent widget
            existing_polygon: Existing polygon dict with key 'coords': [(lat, lon), ...]
        """
        super().__init__(parent)
        self.selected_polygon = existing_polygon
        self._setup_ui()
        self._setup_map()

        # If there's an existing bounding box, show it on the map
        if existing_polygon:
            self._show_existing_bbox(existing_polygon)

        # Trigger a delayed refresh to ensure basemap renders
        QTimer.singleShot(100, self._delayed_refresh)

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("Select Geographic Area - Draw Bounding Box")
        self.setMinimumSize(900, 700)

        layout = QVBoxLayout(self)

        # Header with instructions
        header_label = QLabel("🗺️ Draw a Bounding Box on the Map")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(14)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # Instructions
        instructions = QLabel(
            "• Click and drag to draw a rectangular bounding box\n"
            "• Use Pan and Zoom tools to navigate the map\n"
            "• Your selection will filter data within the box boundaries"
        )
        instructions.setStyleSheet("padding: 10px; background-color: #e3f2fd; border-radius: 5px; color: #1976d2;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Map toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)

        # Tool buttons
        self.pan_button = QPushButton("🖐️ Pan")
        self.pan_button.setCheckable(True)
        self.pan_button.setToolTip("Pan the map")
        self.pan_button.clicked.connect(self._activate_pan_tool)

        self.zoom_in_button = QPushButton("🔍 Zoom In")
        self.zoom_in_button.setCheckable(True)
        self.zoom_in_button.setToolTip("Zoom in to the map")
        self.zoom_in_button.clicked.connect(self._activate_zoom_in_tool)

        self.zoom_out_button = QPushButton("🔍 Zoom Out")
        self.zoom_out_button.setCheckable(True)
        self.zoom_out_button.setToolTip("Zoom out from the map")
        self.zoom_out_button.clicked.connect(self._activate_zoom_out_tool)

        self.draw_button = QPushButton("📐 Draw Box")
        self.draw_button.setCheckable(True)
        self.draw_button.setChecked(True)  # Default tool
        self.draw_button.setToolTip("Draw a bounding box")
        self.draw_button.clicked.connect(self._activate_draw_tool)

        self.reset_view_button = QPushButton("🌏 Reset View")
        self.reset_view_button.setToolTip("Reset to Australia view")
        self.reset_view_button.clicked.connect(self._reset_map_view)

        self.clear_box_button = QPushButton("🗑️ Clear Box")
        self.clear_box_button.setToolTip("Clear the current bounding box")
        self.clear_box_button.clicked.connect(self._clear_bbox)

        toolbar_layout.addWidget(self.pan_button)
        toolbar_layout.addWidget(self.zoom_in_button)
        toolbar_layout.addWidget(self.zoom_out_button)
        toolbar_layout.addWidget(self.draw_button)
        toolbar_layout.addWidget(self.reset_view_button)
        toolbar_layout.addWidget(self.clear_box_button)
        toolbar_layout.addStretch()

        layout.addLayout(toolbar_layout)

        # Map canvas
        self.map_canvas = QgsMapCanvas()
        self.map_canvas.setMinimumSize(800, 500)
        layout.addWidget(self.map_canvas)

        # Coordinates display
        self.coords_label = QLabel("No bounding box selected - Click and drag to draw")
        self.coords_label.setStyleSheet(
            "padding: 10px; background-color: #f5f5f5; border: 1px solid #ddd; "
            "border-radius: 5px; font-family: monospace; color: #333;"
        )
        self.coords_label.setWordWrap(True)
        layout.addWidget(self.coords_label)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)

        # Apply theme-aware button styling
        button_style = get_theme_aware_button_style()
        button_box.button(QDialogButtonBox.Ok).setStyleSheet(button_style)
        button_box.button(QDialogButtonBox.Cancel).setStyleSheet(button_style)

        layout.addWidget(button_box)

    def _setup_map(self):
        """Setup the map canvas with Australia-centered view and basemap."""
        from qgis.core import (
            QgsCoordinateReferenceSystem,
            QgsCoordinateTransform,
            QgsProject,
            QgsRasterLayer,
            QgsRectangle
        )

        # Use Web Mercator (EPSG:3857)
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        self.map_canvas.setDestinationCrs(crs)
        self.map_canvas.setCanvasColor(QColor(255, 255, 255))
        self.map_canvas.enableAntiAliasing(True)

        # ✅ FIX 1: Use provider "xyz" (not "wms")
        # basemap_url = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        basemap_layer = QgsRasterLayer(OSM_LAYER_URL, OSM_LAYER_NAME, "wms")

        if basemap_layer.isValid():
            # ✅ FIX 2: Add to project before setting canvas layers
            QgsProject.instance().addMapLayer(basemap_layer, addToLegend=False)
            self.map_canvas.setLayers([basemap_layer])
            log_info("OpenStreetMap basemap loaded successfully")
        else:
            log_warning("Failed to load OpenStreetMap basemap - using blank canvas")

        # ✅ FIX 3: Reset extent to valid area (Australia)
        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            crs,
            QgsProject.instance()
        )

        australia_extent_4326 = QgsRectangle(113, -44, 154, -10)
        australia_extent = transform.transformBoundingBox(australia_extent_4326)
        self.map_canvas.setExtent(australia_extent)

        # ✅ FIX 4: Unfreeze and refresh *after* extent and layers set
        self.map_canvas.freeze(False)
        self.map_canvas.setRenderFlag(True)
        self.map_canvas.refresh()
        self.map_canvas.refreshAllLayers()

        # ✅ Tools and rubber bands
        self.pan_tool = QgsMapToolPan(self.map_canvas)
        self.zoom_in_tool = QgsMapToolZoom(self.map_canvas, False)
        self.zoom_out_tool = QgsMapToolZoom(self.map_canvas, True)
        self.draw_tool = BoundingBoxRectangleTool(self.map_canvas)
        self.draw_tool.rectangle_created.connect(self._on_rectangle_created)

        self.bbox_rubber_band = QgsRubberBand(self.map_canvas, QgsWkbTypes.PolygonGeometry)
        self.bbox_rubber_band.setColor(QColor(0, 120, 255, 80))
        self.bbox_rubber_band.setWidth(3)

        # ✅ Activate draw tool and refresh again after short delay
        self._activate_draw_tool()
        QTimer.singleShot(200, self.map_canvas.refreshAllLayers)


    def _show_existing_bbox(self, bbox):
        """Show existing bounding box on map."""
        coords = bbox.get('coords', [])
        if coords and len(coords) == 4:
            # Coords are 4 corners: [bottom-left, bottom-right, top-right, top-left]
            # Extract min/max lat/lon
            lats = [lat for lat, lon in coords]
            lons = [lon for lat, lon in coords]
            rect_4326 = QgsRectangle(min(lons), min(lats), max(lons), max(lats))

            # Convert to map CRS (Web Mercator)
            from qgis.core import QgsCoordinateTransform, QgsProject
            transform = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:4326"),
                self.map_canvas.mapSettings().destinationCrs(),
                QgsProject.instance()
            )
            rect = transform.transformBoundingBox(rect_4326)
            self._update_bbox_display(rect)

    def _activate_pan_tool(self):
        """Activate pan tool."""
        self._uncheck_all_tool_buttons()
        self.pan_button.setChecked(True)
        self.map_canvas.setMapTool(self.pan_tool)

    def _activate_zoom_in_tool(self):
        """Activate zoom in tool."""
        self._uncheck_all_tool_buttons()
        self.zoom_in_button.setChecked(True)
        self.map_canvas.setMapTool(self.zoom_in_tool)

    def _activate_zoom_out_tool(self):
        """Activate zoom out tool."""
        self._uncheck_all_tool_buttons()
        self.zoom_out_button.setChecked(True)
        self.map_canvas.setMapTool(self.zoom_out_tool)

    def _activate_draw_tool(self):
        """Activate draw tool."""
        self._uncheck_all_tool_buttons()
        self.draw_button.setChecked(True)
        self.map_canvas.setMapTool(self.draw_tool)

    def _uncheck_all_tool_buttons(self):
        """Uncheck all tool buttons."""
        self.pan_button.setChecked(False)
        self.zoom_in_button.setChecked(False)
        self.zoom_out_button.setChecked(False)
        self.draw_button.setChecked(False)

    def _reset_map_view(self):
        """Reset map view to Australia."""
        # Convert WGS84 bounds to Web Mercator
        from qgis.core import QgsCoordinateTransform, QgsProject
        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            self.map_canvas.mapSettings().destinationCrs(),
            QgsProject.instance()
        )
        australia_extent_4326 = QgsRectangle(113, -44, 154, -10)
        australia_extent = transform.transformBoundingBox(australia_extent_4326)
        self.map_canvas.setExtent(australia_extent)
        self.map_canvas.refresh()

    def _clear_bbox(self):
        """Clear the current bounding box."""
        self.selected_polygon = None
        self.bbox_rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        self.coords_label.setText("No bounding box selected - Click and drag to draw")
        self.draw_tool.reset()

    def _on_rectangle_created(self, rect):
        """Handle rectangle creation from draw tool."""
        self._update_bbox_display(rect)

    def _update_bbox_display(self, rect):
        """Update the bounding box display on map and in UI."""
        # Convert rectangle from map CRS to WGS84 for storage
        from qgis.core import QgsCoordinateTransform, QgsProject
        transform = QgsCoordinateTransform(
            self.map_canvas.mapSettings().destinationCrs(),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance()
        )
        rect_4326 = transform.transformBoundingBox(rect)

        # Store as 4 corner coordinates (bottom-left, bottom-right, top-right, top-left) in lat,lon format
        coords = [
            (rect_4326.yMinimum(), rect_4326.xMinimum()),  # Bottom-left
            (rect_4326.yMinimum(), rect_4326.xMaximum()),  # Bottom-right
            (rect_4326.yMaximum(), rect_4326.xMaximum()),  # Top-right
            (rect_4326.yMaximum(), rect_4326.xMinimum())   # Top-left
        ]

        self.selected_polygon = {
            'coords': coords
        }

        # Update rubber band display (in map CRS)
        points = [
            QgsPointXY(rect.xMinimum(), rect.yMinimum()),
            QgsPointXY(rect.xMaximum(), rect.yMinimum()),
            QgsPointXY(rect.xMaximum(), rect.yMaximum()),
            QgsPointXY(rect.xMinimum(), rect.yMaximum()),
            QgsPointXY(rect.xMinimum(), rect.yMinimum())
        ]

        self.bbox_rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        for point in points:
            self.bbox_rubber_band.addPoint(point, True)
        self.bbox_rubber_band.show()

        # Update coordinates label
        self.coords_label.setText(
            f"✓ Bounding Box Selected:\n"
            f"Latitude: {rect_4326.yMinimum():.4f}° to {rect_4326.yMaximum():.4f}° | "
            f"Longitude: {rect_4326.xMinimum():.4f}° to {rect_4326.xMaximum():.4f}°"
        )

    def _on_accept(self):
        """Handle OK button click."""
        if self.selected_polygon is None:
            QMessageBox.warning(
                self,
                "No Bounding Box Selected",
                "Please draw a bounding box on the map before clicking OK.\nClick and drag to draw a rectangle."
            )
            return

        self.accept()

    def get_polygon(self):
        """Get the selected bounding box coordinates as 4 corners."""
        return self.selected_polygon

    def _delayed_refresh(self):
        """Delayed refresh to ensure basemap tiles load properly."""
        self.map_canvas.refresh()
        self.map_canvas.refreshAllLayers()


class TraceRangeWidget(QWidget):
    """Widget for configuring a single trace range with name, color, and boundaries."""

    removed = pyqtSignal(object)  # Emits self when remove button clicked
    changed = pyqtSignal()  # Emits when any value changes

    def __init__(self, trace_range=None, parent=None):
        """
        Initialize trace range widget.

        Args:
            trace_range: TraceRange object to initialize with (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        from ..config.trace_ranges import TraceRange, BoundaryFormula, RangeType

        self.trace_range = trace_range
        self._setup_ui()

        # Populate from trace_range if provided
        if trace_range:
            self._populate_from_trace_range(trace_range)

    def _setup_ui(self):
        """Setup the widget UI."""
        from ..config.trace_ranges import RangeType

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Top row: Name and color
        top_row = QHBoxLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Range name")
        self.name_input.textChanged.connect(self.changed.emit)
        top_row.addWidget(self.name_input, stretch=3)

        self.color_button = QPushButton(" ")  # Single space to ensure button is clickable
        self.color_button.setFixedHeight(20)
        self.color_button.setFixedWidth(48)
        self.color_button.setDefault(False)
        self.color_button.setAutoDefault(False)
        self.color_button.setCursor(QCursor(Qt.PointingHandCursor))  # Show pointer cursor on hover
        self.selected_color = QColor(100, 181, 246)  # Default blue
        self._update_color_button()
        self.color_button.clicked.connect(self._select_color)
        top_row.addWidget(self.color_button)

        self.remove_button = QPushButton("×")
        self.remove_button.setFixedSize(20, 20)
        self.remove_button.setDefault(False)
        self.remove_button.setAutoDefault(False)
        self.remove_button.setToolTip("Remove this range")
        self.remove_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 16px;
                border-radius: 10px;
                border: 1px solid #ccc;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #ffcccc;
                border-color: #ff0000;
            }
        """)
        self.remove_button.clicked.connect(lambda: self.removed.emit(self))
        top_row.addWidget(self.remove_button)

        layout.addLayout(top_row)

        # Lower boundary row
        lower_row = QHBoxLayout()
        lower_label = QLabel("Lower:")
        lower_label.setFixedWidth(50)
        lower_row.addWidget(lower_label)

        self.lower_type_combo = NoScrollComboBox()
        for range_type in RangeType:
            self.lower_type_combo.addItem(range_type.value, range_type)
        self.lower_type_combo.currentIndexChanged.connect(self.changed.emit)
        self.lower_type_combo.setFocusPolicy(Qt.ClickFocus)  # Prevent wheel scrolling when not focused
        lower_row.addWidget(self.lower_type_combo, stretch=2)

        self.lower_value_spin = NoScrollDoubleSpinBox()
        self.lower_value_spin.setRange(-1000000.0, 1000000.0)
        self.lower_value_spin.setDecimals(2)
        self.lower_value_spin.setValue(0.0)
        self.lower_value_spin.valueChanged.connect(self.changed.emit)
        self.lower_value_spin.setFocusPolicy(Qt.ClickFocus)  # Prevent wheel scrolling when not focused
        lower_row.addWidget(self.lower_value_spin, stretch=1)

        layout.addLayout(lower_row)

        # Upper boundary row
        upper_row = QHBoxLayout()
        upper_label = QLabel("Upper:")
        upper_label.setFixedWidth(50)
        upper_row.addWidget(upper_label)

        self.upper_type_combo = NoScrollComboBox()
        for range_type in RangeType:
            self.upper_type_combo.addItem(range_type.value, range_type)
        self.upper_type_combo.currentIndexChanged.connect(self.changed.emit)
        self.upper_type_combo.setFocusPolicy(Qt.ClickFocus)  # Prevent wheel scrolling when not focused
        upper_row.addWidget(self.upper_type_combo, stretch=2)

        self.upper_value_spin = NoScrollDoubleSpinBox()
        self.upper_value_spin.setRange(-1000000.0, 1000000.0)
        self.upper_value_spin.setDecimals(2)
        self.upper_value_spin.setValue(1.0)
        self.upper_value_spin.valueChanged.connect(self.changed.emit)
        self.upper_value_spin.setFocusPolicy(Qt.ClickFocus)  # Prevent wheel scrolling when not focused
        upper_row.addWidget(self.upper_value_spin, stretch=1)

        layout.addLayout(upper_row)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

    def _select_color(self):
        """Open color picker dialog."""
        color = QColorDialog.getColor(self.selected_color, self, "Choose Range Color")
        if color.isValid():
            self.selected_color = color
            self._update_color_button()
            self.changed.emit()

    def _update_color_button(self):
        """Update color button appearance."""
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.selected_color.name()};
                border: 1px solid #333;
                padding: 4px;
                font-weight: bold;
            }}
        """)

    def _populate_from_trace_range(self, trace_range):
        """Populate widget from TraceRange object."""
        self.name_input.setText(trace_range.name)
        self.selected_color = trace_range.color
        self._update_color_button()

        # Set lower boundary
        lower_idx = self.lower_type_combo.findData(trace_range.lower_boundary.formula_type)
        if lower_idx >= 0:
            self.lower_type_combo.setCurrentIndex(lower_idx)
        self.lower_value_spin.setValue(trace_range.lower_boundary.value)

        # Set upper boundary
        upper_idx = self.upper_type_combo.findData(trace_range.upper_boundary.formula_type)
        if upper_idx >= 0:
            self.upper_type_combo.setCurrentIndex(upper_idx)
        self.upper_value_spin.setValue(trace_range.upper_boundary.value)

    def get_trace_range(self):
        """Get TraceRange object from widget values."""
        from ..config.trace_ranges import TraceRange, BoundaryFormula

        name = self.name_input.text().strip() or "Unnamed Range"

        lower_type = self.lower_type_combo.currentData()
        lower_value = self.lower_value_spin.value()
        lower_boundary = BoundaryFormula(lower_type, lower_value)

        upper_type = self.upper_type_combo.currentData()
        upper_value = self.upper_value_spin.value()
        upper_boundary = BoundaryFormula(upper_type, upper_value)

        return TraceRange(name, self.selected_color, lower_boundary, upper_boundary)


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    """
    A custom QDoubleSpinBox that ignores the mouse wheel event
    unless the widget is currently focused (i.e., clicked on or tabbed into).
    This prevents accidental value changes when scrolling the dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Setting focus policy to StrongFocus is a good practice, but not always enough
        self.setFocusPolicy(Qt.StrongFocus) 

    def wheelEvent(self, event):
        # Check if the widget has focus.
        if self.hasFocus():
            # If focused, process the wheel event (change the value).
            super().wheelEvent(event)
        else:
            # If not focused (user is likely scrolling the parent dialog), 
            # ignore the event so it propagates up to the parent widget.
            event.ignore()

class NoScrollComboBox(QComboBox):
    """
    A custom QComboBox that ignores the mouse wheel event
    unless the dropdown list is currently visible (open).
    This prevents accidental selection changes when scrolling the dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Set focus policy to prevent gaining focus on wheel, 
        # though the wheelEvent override is the main fix.
        self.setFocusPolicy(Qt.StrongFocus) 

    def wheelEvent(self, event):
        # Check if the combo box's list is currently visible (open).
        if self.view().isVisible():
            # If the list is open, process the wheel event (change selection).
            super().wheelEvent(event)
        else:
            # If the list is NOT open (user is likely scrolling the parent dialog), 
            # ignore the event so it propagates up to the parent widget.
            event.ignore()