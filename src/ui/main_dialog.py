"""
Main dialog UI for the Needle Digital Mining Data Importer plugin.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTabWidget, QTableWidget, QTableWidgetItem, QProgressBar, QWidget,
    QFormLayout, QSpacerItem, QSizePolicy, QHeaderView, QMessageBox,
    QStackedLayout, QComboBox, QCheckBox
)
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtCore import Qt, pyqtSignal

from .components import (
    DynamicSearchFilterWidget, StaticFilterWidget, LoginDialog, LayerOptionsDialog
)
from ..config.constants import AUSTRALIAN_STATES, CHEMICAL_ELEMENTS, COMPARISON_OPERATORS, UI_CONFIG
from ..utils.logging import get_logger

logger = get_logger(__name__)

class DataImporterDialog(QDialog):
    """Main plugin dialog."""
    
    # Signals
    login_requested = pyqtSignal()
    logout_requested = pyqtSignal()
    data_fetch_requested = pyqtSignal(str, dict, bool)  # tab_name, params, fetch_all
    data_clear_requested = pyqtSignal(str)  # tab_name
    data_import_requested = pyqtSignal(str, str, object)  # tab_name, layer_name, color
    
    def __init__(self, parent=None):
        super(DataImporterDialog, self).__init__(parent)
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the main UI."""
        config = UI_CONFIG['main_window']
        self.setWindowTitle(config['title'])
        self.setMinimumSize(config['min_width'], config['min_height'])

        self.main_layout = QVBoxLayout(self)
        
        # Header
        self._create_header()
        
        # Tabs
        self._create_tabs()
        
        # Status bar
        self._create_status_bar()
    
    def _create_header(self):
        """Create the header section."""
        header_layout = QHBoxLayout()
        
        # Brand label
        brand_config = UI_CONFIG['brand_label']
        brand_label = QLabel(brand_config['text'])
        font = QFont()
        font.setBold(brand_config['bold'])
        font.setPointSize(brand_config['font_size'])
        brand_label.setFont(font)
        
        header_layout.addWidget(brand_label)
        header_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Action buttons
        self.reset_all_button = QPushButton("Reset All")
        self.reset_all_button.setVisible(False)
        self.login_button = QPushButton("Login")
        
        # Fix focus issues - prevent login button from stealing Enter key presses
        self.login_button.setDefault(False)
        self.login_button.setAutoDefault(False)
        self.reset_all_button.setDefault(False)
        self.reset_all_button.setAutoDefault(False)
        
        header_layout.addWidget(self.reset_all_button)
        header_layout.addWidget(self.login_button)
        
        self.main_layout.addLayout(header_layout)
    
    def _create_tabs(self):
        """Create the tab widget."""
        self.tabs = QTabWidget()
        
        # Create tabs
        self.holes_tab = self._create_data_tab("Holes")
        self.assays_tab = self._create_data_tab("Assays") 
        
        self.tabs.addTab(self.holes_tab['widget'], "Holes")
        self.tabs.addTab(self.assays_tab['widget'], "Assays")
        
        self.main_layout.addWidget(self.tabs)
    
    def _create_data_tab(self, tab_type: str) -> dict:
        """Create a data tab (Holes or Assays)."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Controls
        controls_layout = QFormLayout()
        controls_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        
        # State filter (common to both tabs)
        state_filter = StaticFilterWidget()
        state_filter.addItems(AUSTRALIAN_STATES)
        # Set "All States" as default (first item, empty value)
        state_filter.setCurrentData([""])
        controls_layout.addRow("State(s):", state_filter)
        
        widgets = {
            'widget': tab_widget,
            'state_filter': state_filter
        }
        
        if tab_type == "Holes":
            # Company filter
            company_filter = DynamicSearchFilterWidget()
            company_filter.search_box.setPlaceholderText("Type to search companies...")
            controls_layout.addRow("Company Name(s):", company_filter)
            widgets['company_filter'] = company_filter
            
            # Record count controls
            count_input = QLineEdit("100")
            fetch_all_checkbox = QCheckBox("Fetch all records")
            fetch_all_checkbox.toggled.connect(count_input.setDisabled)
            
            records_layout = QHBoxLayout()
            records_layout.addWidget(count_input)
            records_layout.addWidget(fetch_all_checkbox)
            records_layout.addStretch()
            controls_layout.addRow("No. of Records:", records_layout)
            
            widgets.update({
                'count_input': count_input,
                'fetch_all_checkbox': fetch_all_checkbox
            })
            
            # Fetch button
            fetch_button = QPushButton("Fetch Holes")
            fetch_button.setDefault(False)
            fetch_button.setAutoDefault(False)
            controls_layout.addRow("", fetch_button)
            widgets['fetch_button'] = fetch_button
            
        elif tab_type == "Assays":
            # Element filter
            element_input = QComboBox()
            for display_name, symbol in CHEMICAL_ELEMENTS:
                element_input.addItem(display_name, symbol)
            
            operator_input = QComboBox()
            operator_input.addItems(COMPARISON_OPERATORS)
            
            value_input = QLineEdit()
            
            element_layout = QHBoxLayout()
            element_layout.setContentsMargins(0, 0, 0, 0)
            element_layout.addWidget(QLabel("Element:"))
            element_layout.addWidget(element_input)
            element_layout.addSpacing(20)
            element_layout.addWidget(QLabel("Filter by Value:"))
            element_layout.addWidget(operator_input)
            element_layout.addWidget(value_input)
            element_layout.addStretch()
            controls_layout.addRow(element_layout)
            
            widgets.update({
                'element_input': element_input,
                'operator_input': operator_input,
                'value_input': value_input
            })
            
            # Record count controls
            count_input = QLineEdit("100")
            fetch_all_checkbox = QCheckBox("Fetch all records")
            fetch_all_checkbox.toggled.connect(count_input.setDisabled)
            
            records_layout = QHBoxLayout()
            records_layout.addWidget(count_input)
            records_layout.addWidget(fetch_all_checkbox)
            records_layout.addStretch()
            controls_layout.addRow("No. of Records:", records_layout)
            
            widgets.update({
                'count_input': count_input,
                'fetch_all_checkbox': fetch_all_checkbox
            })
            
            # Fetch button
            fetch_button = QPushButton("Fetch Assay Data")
            fetch_button.setDefault(False)
            fetch_button.setAutoDefault(False)
            controls_layout.addRow("", fetch_button)
            widgets['fetch_button'] = fetch_button
        
        layout.addLayout(controls_layout)
        
        # Content area
        content_stack = QStackedLayout()
        
        # Data table
        table = QTableWidget()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Loading label
        loading_label = QLabel("Waiting for data...")
        loading_label.setAlignment(Qt.AlignCenter)
        font = loading_label.font()
        font.setPointSize(12)
        loading_label.setFont(font)
        
        content_stack.addWidget(table)
        content_stack.addWidget(loading_label)
        content_stack.setCurrentWidget(loading_label)
        
        layout.addLayout(content_stack)
        
        widgets.update({
            'table': table,
            'loading_label': loading_label,
            'content_stack': content_stack
        })
        
        # Pagination (placeholder for future implementation)
        pagination_layout = QHBoxLayout()
        prev_button = QPushButton("<< Previous")
        prev_button.setEnabled(False)
        page_label = QLabel("Page 0 of 0")
        next_button = QPushButton("Next >>")
        next_button.setEnabled(False)
        
        pagination_layout.addStretch()
        pagination_layout.addWidget(prev_button)
        pagination_layout.addWidget(page_label)
        pagination_layout.addWidget(next_button)
        pagination_layout.addStretch()
        layout.addLayout(pagination_layout)
        
        widgets.update({
            'prev_button': prev_button,
            'page_label': page_label,
            'next_button': next_button
        })
        
        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        clear_button = QPushButton("Clear Filters & Data")
        clear_button.setDefault(False)
        clear_button.setAutoDefault(False)
        
        import_button = QPushButton("Import All Data to QGIS")
        import_button.setDefault(False)
        import_button.setAutoDefault(False)
        import_button.setVisible(False)  # Hidden until data is available
        
        action_layout.addWidget(clear_button)
        action_layout.addWidget(import_button)
        layout.addLayout(action_layout)
        
        widgets.update({
            'clear_button': clear_button,
            'import_button': import_button
        })
        
        return widgets
    
    def _create_status_bar(self):
        """Create the status bar."""
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel(UI_CONFIG['status_messages']['ready'])
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        
        self.main_layout.addLayout(status_layout)
    
    def _connect_signals(self):
        """Connect UI signals."""
        # Header buttons
        self.login_button.clicked.connect(self._handle_login_button)
        self.reset_all_button.clicked.connect(self._handle_reset_all)
        
        # Fetch buttons
        self.holes_tab['fetch_button'].clicked.connect(lambda: self._handle_fetch_request("Holes"))
        self.assays_tab['fetch_button'].clicked.connect(lambda: self._handle_fetch_request("Assays"))
        
        # Clear buttons
        self.holes_tab['clear_button'].clicked.connect(lambda: self._handle_clear_request("Holes"))
        self.assays_tab['clear_button'].clicked.connect(lambda: self._handle_clear_request("Assays"))
        
        # Import buttons
        self.holes_tab['import_button'].clicked.connect(lambda: self._handle_import_request("Holes"))
        self.assays_tab['import_button'].clicked.connect(lambda: self._handle_import_request("Assays"))
    
    def _handle_login_button(self):
        """Handle login/logout button click."""
        if self.login_button.text() == "Login":
            self.login_requested.emit()
        else:
            self.logout_requested.emit()
    
    def _handle_reset_all(self):
        """Handle reset all button click."""
        self._handle_clear_request("Holes")
        self._handle_clear_request("Assays")
    
    def _handle_fetch_request(self, tab_name: str):
        """Handle data fetch request."""
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
        
        # Build filter parameters
        params = {}
        
        # Handle states - convert to comma-separated string, exclude empty values
        selected_states = tab_widgets['state_filter'].currentData()
        # Filter out empty values (which represent "All States")
        valid_states = [state for state in selected_states if state and state.strip()]
        if valid_states:
            params['states'] = ",".join(valid_states)
        
        if tab_name == "Holes":
            companies = tab_widgets['company_filter'].currentData()
            if companies:
                params['companies'] = ",".join(companies)
        else:  # Assays
            params['element'] = tab_widgets['element_input'].currentData()
            params['operator'] = tab_widgets['operator_input'].currentText()
            value = tab_widgets['value_input'].text().strip()
            if value:
                params['value'] = value
        
        # Check if fetch_all is requested
        fetch_all = tab_widgets['fetch_all_checkbox'].isChecked()
        
        # Emit request signal
        self.data_fetch_requested.emit(tab_name, params, fetch_all)
    
    def _handle_clear_request(self, tab_name: str):
        """Handle data clear request."""
        self.data_clear_requested.emit(tab_name)
    
    def _handle_import_request(self, tab_name: str):
        """Handle data import request."""
        # Show layer options dialog
        default_name = f"Mining {tab_name} Data"
        options_dialog = LayerOptionsDialog(default_name, self)
        
        if options_dialog.exec_() == QDialog.Accepted:
            layer_name, color = options_dialog.get_options()
            self.data_import_requested.emit(tab_name, layer_name, color)
    
    def update_login_status(self, is_logged_in: bool, user_info: str = ""):
        """Update UI based on login status."""
        if is_logged_in:
            self.login_button.setText("Logout")
            self.reset_all_button.setVisible(True)
            status = UI_CONFIG['status_messages']['authenticated']
            if user_info:
                status = f"Ready to fetch data. Logged in as {user_info}"
            self.status_label.setText(status)
        else:
            self.login_button.setText("Login") 
            self.reset_all_button.setVisible(False)
            self.status_label.setText(UI_CONFIG['status_messages']['ready'])
    
    def update_status(self, message: str):
        """Update status message."""
        self.status_label.setText(message)
    
    def update_progress(self, value: int):
        """Update progress bar."""
        if value > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(value)
        else:
            self.progress_bar.setVisible(False)
    
    def show_data(self, tab_name: str, data: list, headers: list):
        """Show data in the specified tab."""
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
        
        table = tab_widgets['table']
        loading_label = tab_widgets['loading_label']
        content_stack = tab_widgets['content_stack']
        import_button = tab_widgets['import_button']
        
        if data:
            # Setup table
            table.setRowCount(len(data))
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            
            # Populate table
            for row_idx, record in enumerate(data):
                for col_idx, header in enumerate(headers):
                    value = record.get(header, '')
                    item = QTableWidgetItem(str(value) if value is not None else '')
                    table.setItem(row_idx, col_idx, item)
            
            table.resizeColumnsToContents()
            content_stack.setCurrentWidget(table)
            import_button.setVisible(True)
        else:
            loading_label.setText("No data to display.")
            content_stack.setCurrentWidget(loading_label)
            import_button.setVisible(False)
    
    def show_error(self, message: str):
        """Show error message."""
        QMessageBox.critical(self, "Error", message)
    
    def show_info(self, message: str):
        """Show information message."""
        QMessageBox.information(self, "Information", message)