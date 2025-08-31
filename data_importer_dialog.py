# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTableWidgetItem,
    QPushButton, QTableWidget, QProgressBar, QDialogButtonBox, QWidget,
    QFormLayout, QSpacerItem, QSizePolicy, QHeaderView, QMessageBox, QColorDialog,
    QTabWidget, QComboBox, QListView, QLayout, QFrame, QCheckBox, QStackedLayout
)
from qgis.PyQt.QtGui import QFont, QColor, QStandardItemModel, QStandardItem
from qgis.PyQt.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize

# ==============================================================================
# FlowLayout for Chip Container
# ==============================================================================
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

# ==============================================================================
# Chip Widget for displaying selections
# ==============================================================================
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
        
        self.close_button = QPushButton("x", self)
        self.close_button.setFixedSize(16, 16)
        self.close_button.setStyleSheet("""
            QPushButton {
                font-family: "Arial", sans-serif; font-weight: bold; border-radius: 8px;
                border: 1px solid #ccc; background-color: #f0f0f0;
            }
            QPushButton:hover { background-color: #e0e0e0; }
            QPushButton:pressed { background-color: #d0d0d0; }
        """)
        self.close_button.clicked.connect(self._emit_removed_signal)
        
        layout.addWidget(self.label)
        layout.addWidget(self.close_button)
        
        self.setStyleSheet("Chip { background-color: #e1e1e1; border-radius: 8px; border: 1px solid #c0c0c0; }")

    def _emit_removed_signal(self):
        self.removed.emit(self.data)

# ==============================================================================
# Checkable ComboBox
# ==============================================================================
class CheckableComboBox(QComboBox):
    selectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        
        self.setModel(QStandardItemModel(self))
        self.view().pressed.connect(self.handleItemPressed)
        
        self._selected_data = []
        
        self.lineEdit().setPlaceholderText("Select state(s)...")
        self.lineEdit().setText("")

    def handleItemPressed(self, index):
        item = self.model().itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        self._update_selection()

    def hidePopup(self):
        super().hidePopup()

    def _update_selection(self):
        self._selected_data = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                self._selected_data.append(item.data(Qt.UserRole))
        self.updateDisplayText()
        self.selectionChanged.emit(self.currentData())

    def updateDisplayText(self):
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
        item = QStandardItem(text)
        item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setData(userData or text, Qt.UserRole)
        item.setCheckState(Qt.Checked if (userData or text) in self._selected_data else Qt.Unchecked)
        self.model().appendRow(item)
    
    def addItems(self, items):
        for text, data in items:
            self.addItem(text, data)
    
    def currentData(self):
        return self._selected_data

    def setCurrentData(self, data_list):
        if not isinstance(data_list, list): data_list = []
        self._selected_data = data_list
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in data_list else Qt.Unchecked)
        self._update_selection()
        
# ==============================================================================
# Widget for Dynamic Search with Chips
# ==============================================================================
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
        self.search_box.setPlaceholderText("Type to search companies...")
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
        item = self.results_list.model().itemFromIndex(index)
        if item:
            self.addItem(item.text(), item.data(Qt.UserRole))
        self.popup.hide()
        self.search_box.clear()

    def showPopup(self, results):
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
        if data not in self._selected_items:
            self._selected_items[data] = text
            self._updateChips()
            self.selectionChanged.emit(self.currentData())

    def removeChip(self, data_to_remove):
        if data_to_remove in self._selected_items:
            del self._selected_items[data_to_remove]
            self._updateChips()
            self.selectionChanged.emit(self.currentData())

    def _updateChips(self):
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
        return list(self._selected_items.keys())

    def setCurrentData(self, data_list):
        self._selected_items = {item: item for item in data_list}
        self._updateChips()

# ==============================================================================
# Filter Widget for Static Data
# ==============================================================================
class StaticFilterWidget(QWidget):
    """A composite widget that combines a CheckableComboBox with a chip container."""
    selectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
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
        self.combo_box.addItems(items)
    
    def currentData(self):
        return self.combo_box.currentData()
    
    def setCurrentData(self, data_list):
        self.combo_box.setCurrentData(data_list)
        self.updateChips(data_list)

    def updateChips(self, selected_data_list):
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
        current_selection = self.currentData()
        if data_to_remove in current_selection:
            current_selection.remove(data_to_remove)
            self.setCurrentData(current_selection)

# ==============================================================================
# Standard Dialog Classes
# ==============================================================================
class LoginDialog(QDialog):
    login_attempt = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle("Login")
        self.setMinimumWidth(300)
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout = QFormLayout()
        form_layout.addRow("Email:", self.email_input)
        form_layout.addRow("Password:", self.password_input)
        
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.handle_login_attempt)
        self.button_box.rejected.connect(self.reject)
        
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.error_label)
        main_layout.addWidget(self.button_box)
    
    def handle_login_attempt(self):
        self.error_label.setVisible(False)
        email = self.email_input.text()
        password = self.password_input.text()
        self.login_attempt.emit(email, password)
        
    def on_login_result(self, success, message):
        if success:
            self.accept()
        else:
            self.error_label.setText(message)
            self.error_label.setVisible(True)
            self.password_input.clear()

    def get_credentials(self):
        return self.email_input.text(), self.password_input.text()

class DataImporterDialog(QDialog):
    def __init__(self, parent=None):
        super(DataImporterDialog, self).__init__(parent)
        self.setWindowTitle("Needle Digital - Mining Data Importer")
        self.setMinimumSize(850, 700)

        self.main_layout = QVBoxLayout(self)
        header_layout = QHBoxLayout()
        brand_label = QLabel("Geochemical Data Importer")
        font = QFont(); font.setBold(True); font.setPointSize(16)
        brand_label.setFont(font)
        header_layout.addWidget(brand_label)
        header_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.reset_all_button = QPushButton("Reset All")
        self.reset_all_button.setVisible(False)
        self.login_button = QPushButton("Login")
        header_layout.addWidget(self.reset_all_button)
        header_layout.addWidget(self.login_button)
        self.main_layout.addLayout(header_layout)

        self.tabs = QTabWidget()
        self.holes_tab = self._create_data_tab("Holes")
        self.assays_tab = self._create_data_tab("Assays")
        self.tabs.addTab(self.holes_tab, "Holes")
        self.tabs.addTab(self.assays_tab, "Assays")
        self.main_layout.addWidget(self.tabs)

        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready. Please log in.")
        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        self.main_layout.addLayout(status_layout)

    def _create_data_tab(self, tab_type):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls_layout = QFormLayout()
        controls_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        
        states = [("New South Wales", "NSW"), ("Queensland", "QLD"), ("South Australia", "SA"),
                  ("Tasmania", "TAS"), ("Victoria", "VIC"), ("Western Australia", "WA"), ("Northern Territory", "NT")]

        if tab_type == "Holes":
            self.holes_company_filter = DynamicSearchFilterWidget()
            controls_layout.addRow("Company Name(s):", self.holes_company_filter)
            self.holes_state_filter = StaticFilterWidget()
            self.holes_state_filter.addItems(states)
            controls_layout.addRow("State(s):", self.holes_state_filter)
            self.holes_count_input = QLineEdit("100")
            self.holes_fetch_all_checkbox = QCheckBox("Fetch all records")
            self.holes_fetch_all_checkbox.toggled.connect(self.holes_count_input.setDisabled)
            records_hbox_h = QHBoxLayout()
            records_hbox_h.addWidget(self.holes_count_input)
            records_hbox_h.addWidget(self.holes_fetch_all_checkbox)
            records_hbox_h.addStretch()
            controls_layout.addRow("No. of Records:", records_hbox_h)
            self.fetch_holes_button = QPushButton("Fetch Holes")
            controls_layout.addRow("", self.fetch_holes_button)
        elif tab_type == "Assays":
            self.assays_state_filter = StaticFilterWidget()
            self.assays_state_filter.addItems(states)
            controls_layout.addRow("State(s):", self.assays_state_filter)
            self.assay_element_input = QComboBox()
            # Add elements with display names and lowercase symbols for API calls
            elements = [
                ('Silver - Ag', 'ag'), ('Aluminum - Al', 'al'), ('Americium - Am', 'am'), ('Argon - Ar', 'ar'), 
                ('Arsenic - As', 'as'), ('Astatine - At', 'at'), ('Gold - Au', 'au'), ('Boron - B', 'b'), 
                ('Barium - Ba', 'ba'), ('Beryllium - Be', 'be'), ('Berkelium - Bk', 'bk'), ('Bromine - Br', 'br'), 
                ('Carbon - C', 'c'), ('Calcium - Ca', 'ca'), ('Cadmium - Cd', 'cd'), ('Cerium - Ce', 'ce'), 
                ('Californium - Cf', 'cf'), ('Chlorine - Cl', 'cl'), ('Curium - Cm', 'cm'), ('Cobalt - Co', 'co'), 
                ('Chromium - Cr', 'cr'), ('Cesium - Cs', 'cs'), ('Copper - Cu', 'cu'), ('Dysprosium - Dy', 'dy'), 
                ('Erbium - Er', 'er'), ('Einsteinium - Es', 'es'), ('Europium - Eu', 'eu'), ('Fluorine - F', 'f'), 
                ('Iron - Fe', 'fe'), ('Fermium - Fm', 'fm'), ('Francium - Fr', 'fr'), ('Gallium - Ga', 'ga'), 
                ('Gadolinium - Gd', 'gd'), ('Germanium - Ge', 'ge'), ('Hydrogen - H', 'h'), ('Hafnium - Hf', 'hf'), 
                ('Mercury - Hg', 'hg'), ('Holmium - Ho', 'ho'), ('Iodine - I', 'i'), ('Indium - In', 'in'), 
                ('Iridium - Ir', 'ir'), ('Potassium - K', 'k'), ('Krypton - Kr', 'kr'), ('Lanthanum - La', 'la'), 
                ('Lithium - Li', 'li'), ('Lawrencium - Lr', 'lr'), ('Lutetium - Lu', 'lu'), ('Mendelevium - Md', 'md'), 
                ('Magnesium - Mg', 'mg'), ('Manganese - Mn', 'mn'), ('Molybdenum - Mo', 'mo'), ('Nitrogen - N', 'n'), 
                ('Sodium - Na', 'na'), ('Niobium - Nb', 'nb'), ('Neodymium - Nd', 'nd'), ('Neon - Ne', 'ne'), 
                ('Nickel - Ni', 'ni'), ('Nobelium - No', 'no'), ('Neptunium - Np', 'np'), ('Oxygen - O', 'o'), 
                ('Osmium - Os', 'os'), ('Phosphorus - P', 'p'), ('Protactinium - Pa', 'pa'), ('Lead - Pb', 'pb'), 
                ('Palladium - Pd', 'pd'), ('Promethium - Pm', 'pm'), ('Polonium - Po', 'po'), ('Praseodymium - Pr', 'pr'), 
                ('Platinum - Pt', 'pt'), ('Plutonium - Pu', 'pu'), ('Radium - Ra', 'ra'), ('Rubidium - Rb', 'rb'), 
                ('Rhenium - Re', 're'), ('Rutherfordium - Rf', 'rf'), ('Rhodium - Rh', 'rh'), ('Radon - Rn', 'rn'), 
                ('Ruthenium - Ru', 'ru'), ('Sulfur - S', 's'), ('Antimony - Sb', 'sb'), ('Scandium - Sc', 'sc'), 
                ('Selenium - Se', 'se'), ('Silicon - Si', 'si'), ('Samarium - Sm', 'sm'), ('Tin - Sn', 'sn'), 
                ('Strontium - Sr', 'sr'), ('Tantalum - Ta', 'ta'), ('Terbium - Tb', 'tb'), ('Technetium - Tc', 'tc'), 
                ('Tellurium - Te', 'te'), ('Thorium - Th', 'th'), ('Titanium - Ti', 'ti'), ('Thallium - Tl', 'tl'), 
                ('Thulium - Tm', 'tm'), ('Uranium - U', 'u'), ('Vanadium - V', 'v'), ('Tungsten - W', 'w'), 
                ('Xenon - Xe', 'xe'), ('Yttrium - Y', 'y'), ('Ytterbium - Yb', 'yb'), ('Zinc - Zn', 'zn'), 
                ('Zirconium - Zr', 'zr')
            ]
            for display_name, symbol in elements:
                self.assay_element_input.addItem(display_name, symbol)
            self.assay_operator_input = QComboBox()
            self.assay_operator_input.addItems(['>', '<', '=', '!=', '>=', '<='])
            self.assay_value_input = QLineEdit()
            element_filter_hbox = QHBoxLayout()
            element_filter_hbox.setContentsMargins(0,0,0,0)
            element_filter_hbox.addWidget(QLabel("Element:"))
            element_filter_hbox.addWidget(self.assay_element_input)
            element_filter_hbox.addSpacing(20)
            element_filter_hbox.addWidget(QLabel("Filter by Value:"))
            element_filter_hbox.addWidget(self.assay_operator_input)
            element_filter_hbox.addWidget(self.assay_value_input)
            element_filter_hbox.addStretch()
            controls_layout.addRow(element_filter_hbox)
            self.assay_count_input = QLineEdit("100")
            self.assay_fetch_all_checkbox = QCheckBox("Fetch all records")
            self.assay_fetch_all_checkbox.toggled.connect(self.assay_count_input.setDisabled)
            records_hbox_a = QHBoxLayout()
            records_hbox_a.addWidget(self.assay_count_input)
            records_hbox_a.addWidget(self.assay_fetch_all_checkbox)
            records_hbox_a.addStretch()
            controls_layout.addRow("No. of Records:", records_hbox_a)
            self.fetch_assay_button = QPushButton("Fetch Assay Data")
            controls_layout.addRow("", self.fetch_assay_button)

        layout.addLayout(controls_layout)
        
        content_stack = QStackedLayout()
        
        table = QTableWidget()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        loading_label = QLabel("Waiting for data...")
        loading_label.setAlignment(Qt.AlignCenter)
        font = loading_label.font(); font.setPointSize(12); loading_label.setFont(font)

        content_stack.addWidget(table)
        content_stack.addWidget(loading_label)
        layout.addLayout(content_stack)
        
        content_stack.setCurrentWidget(loading_label)

        pagination_layout = QHBoxLayout()
        prev_button = QPushButton("<< Previous")
        page_label = QLabel("Page 0 of 0")
        next_button = QPushButton("Next >>")
        pagination_layout.addStretch()
        pagination_layout.addWidget(prev_button)
        pagination_layout.addWidget(page_label)
        pagination_layout.addWidget(next_button)
        pagination_layout.addStretch()
        layout.addLayout(pagination_layout)

        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.addStretch()
        clear_button = QPushButton("Clear Filters & Data")
        import_button = QPushButton("Import All Data to QGIS")
        action_buttons_layout.addWidget(clear_button)
        action_buttons_layout.addWidget(import_button)
        layout.addLayout(action_buttons_layout)
        
        widgets = {
            'table': table, 'clear_button': clear_button, 'import_button': import_button,
            'prev_button': prev_button, 'next_button': next_button, 'page_label': page_label,
            'loading_label': loading_label, 'content_stack': content_stack
        }

        if tab_type == "Holes":
            self.holes_widgets = widgets
        else:
            self.assays_widgets = widgets
        
        return tab

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)

    def show_table_for_tab(self, widgets, data, headers):
        table_widget = widgets['table']
        loading_label = widgets['loading_label']
        content_stack = widgets['content_stack']
        
        has_data = bool(data)
        
        content_stack.setCurrentWidget(table_widget)
        
        widgets['import_button'].setVisible(has_data)
        widgets['clear_button'].setVisible(True)
        
        if not has_data:
            table_widget.setRowCount(0)
            loading_label.setText("No data to display.")
            content_stack.setCurrentWidget(loading_label)
            return

        table_widget.setRowCount(len(data))
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)

        for r, row_dict in enumerate(data):
            for c, header in enumerate(headers):
                cell_value = row_dict.get(header, '')
                table_widget.setItem(r, c, QTableWidgetItem(str(cell_value or '')))
        table_widget.resizeColumnsToContents()

class LayerOptionsDialog(QDialog):
    def __init__(self, default_name="Imported Layer", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Layer Options")
        self.layer_name_input = QLineEdit(default_name)
        self.color_button = QPushButton("Select Point Color")
        self.selected_color = QColor(255, 0, 0)
        self.update_color_button_stylesheet()
        self.color_button.clicked.connect(self.select_color)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout = QFormLayout(self)
        layout.addRow("Layer Name:", self.layer_name_input)
        layout.addRow("Point Style:", self.color_button)
        layout.addWidget(self.button_box)

    def select_color(self):
        color = QColorDialog.getColor(self.selected_color, self, "Choose a color")
        if color.isValid():
            self.selected_color = color
            self.update_color_button_stylesheet()

    def update_color_button_stylesheet(self):
        self.color_button.setStyleSheet(f"background-color: {self.selected_color.name()};")

    def get_options(self):
        return self.layer_name_input.text(), self.selected_color