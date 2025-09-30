"""
Main Dialog UI for the ND Data Importer Plugin

This module contains the primary user interface for the mining data importer,
providing a comprehensive tabbed interface for data exploration and import.

Key UI Features:
    - Tabbed interface for Holes and Assays data
    - Dynamic filtering with real-time search
    - Company search with auto-complete
    - Large dataset visualization with pagination
    - Progress tracking and user feedback
    - Import options with layer customization
    - Professional styling and responsive design

Architecture:
    - Signal-based communication with backend
    - Component-based UI design for reusability
    - Responsive layout with proper sizing
    - Error handling with user-friendly messages
    - Performance optimized for large datasets

User Workflow:
    1. Authentication via login dialog
    2. Data filtering and search
    3. Data preview with pagination
    4. Import configuration (layer name, styling)
    5. QGIS layer creation with progress tracking

Author: Needle Digital
Contact: divyansh@needle-digital.com
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QProgressBar, QWidget,
    QFormLayout, QSpacerItem, QSizePolicy, QHeaderView, QMessageBox,
    QStackedLayout, QComboBox, QCheckBox, QApplication, QFrame
)
from qgis.PyQt.QtGui import QFont, QCursor, QDoubleValidator, QColor, QIntValidator
from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer

from .components import (
    DynamicSearchFilterWidget, StaticFilterWidget, SearchableStaticFilterWidget,
    LoginDialog, LayerOptionsDialog, LargeImportWarningDialog, ImportProgressDialog, MessageBar
)
from ..config.constants import (
    AUSTRALIAN_STATES, CHEMICAL_ELEMENTS, COMPARISON_OPERATORS, UI_CONFIG,
    LARGE_IMPORT_WARNING_THRESHOLD_LOCATION_ONLY, MAX_SAFE_IMPORT_LOCATION_ONLY,
    PARTIAL_IMPORT_LIMIT_LOCATION_ONLY, DEFAULT_HOLE_TYPES, ROLE_DISPLAY_NAMES,
    ROLE_DESCRIPTIONS
)
from ..utils.logging import log_warning, log_error


class DataImporterDialog(QDialog):
    """Main plugin dialog."""
    
    # Signals
    login_requested = pyqtSignal()
    logout_requested = pyqtSignal()
    data_fetch_requested = pyqtSignal(str, dict, bool)  # tab_name, params, fetch_all
    data_clear_requested = pyqtSignal(str)  # tab_name
    data_import_requested = pyqtSignal(str, str, object)  # tab_name, layer_name, color
    page_next_requested = pyqtSignal(str)  # tab_name
    page_previous_requested = pyqtSignal(str)  # tab_name
    cancel_request_requested = pyqtSignal()  # Cancel API request
    company_search_requested = pyqtSignal(str)  # company search query
    
    def __init__(self, parent=None):
        super(DataImporterDialog, self).__init__(parent)
        self._setup_ui()
        self._connect_signals()

        # Apply theme-aware styling for buttons
        self._apply_theme_aware_styling()

        # Track loading state for each tab
        self._loading_states = {'Holes': False, 'Assays': False}

        # Company search timer for debouncing
        self.company_search_timer = QTimer()
        self.company_search_timer.setSingleShot(True)
        self.company_search_timer.timeout.connect(self._perform_company_search)
        self._current_company_query = ""

        # Reference to data manager (will be set by plugin)
        self.data_manager = None
    
    def _setup_ui(self):
        """Setup the main UI."""
        config = UI_CONFIG['main_window']
        self.setWindowTitle(config['title'])
        self.setMinimumSize(config['min_width'], config['min_height'])
        
        # Set window flags to include minimize button and proper window management
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint |
            Qt.WindowSystemMenuHint
        )

        # Set window size to 75% width and full height, centered to QGIS
        self._setup_window_geometry()

        self.main_layout = QVBoxLayout(self)

        # Header
        self._create_header()

        # Message bar (initially hidden) - with error handling
        try:
            self.message_bar = MessageBar(self)
            self.main_layout.addWidget(self.message_bar)
        except Exception as e:
            # If MessageBar fails to create, create a fallback QLabel
            self.message_bar = QLabel("")
            self.message_bar.setVisible(False)
            self.message_bar.setStyleSheet("background-color: #2196F3; color: white; padding: 8px; border-radius: 4px;")
            self.main_layout.addWidget(self.message_bar)

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

        # Add small spacing between brand label and role badge
        header_layout.addSpacing(12)

        # Role badge (initially hidden, shown after login) - positioned next to brand label
        self.role_badge = QPushButton()
        self.role_badge.setVisible(False)
        self.role_badge.setCursor(QCursor(Qt.PointingHandCursor))
        self.role_badge.setDefault(False)
        self.role_badge.setAutoDefault(False)
        self.role_badge.clicked.connect(self._show_role_info)
        self.role_badge.setToolTip("Click to view your plan details")
        # Style will be applied by _update_role_badge()
        header_layout.addWidget(self.role_badge)

        # Expand the space to push action buttons to the right
        header_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Action buttons on the right
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

        # Hole Type filter (will be positioned differently for each tab)
        hole_type_filter = SearchableStaticFilterWidget()
        hole_type_filter.search_box.setPlaceholderText("Type to search hole types...")
        # Set static data for searching (exclude "All" from search since it's not a real hole type)
        hole_type_data = [(hole_type, hole_type) for hole_type in DEFAULT_HOLE_TYPES]
        hole_type_filter.setStaticData(hole_type_data)

        widgets = {
            'widget': tab_widget,
            'state_filter': state_filter,
            'hole_type_filter': hole_type_filter
        }
        
        if tab_type == "Holes":
            # Company filter
            company_filter = DynamicSearchFilterWidget()
            company_filter.search_box.setPlaceholderText("Type to search companies...")
            controls_layout.addRow("Company Name(s):", company_filter)
            widgets['company_filter'] = company_filter

            # Hole Type and Max Depth in same row
            hole_depth_layout = QHBoxLayout()
            hole_depth_layout.setContentsMargins(0, 0, 0, 0)
            hole_depth_layout.setAlignment(Qt.AlignTop)  # Align contents to top

            # Hole Type filter container (2 parts of 2:1 ratio)
            hole_type_container = QWidget()
            hole_type_container_layout = QVBoxLayout(hole_type_container)
            hole_type_container_layout.setContentsMargins(0, 0, 0, 0)
            hole_type_container_layout.setAlignment(Qt.AlignTop)

            hole_type_filter.setMaximumWidth(9999)  # Remove width constraint
            hole_type_filter.setMinimumWidth(200)  # Set reasonable minimum
            hole_type_container_layout.addWidget(hole_type_filter)
            hole_depth_layout.addWidget(hole_type_container, 2)  # 2 parts of the ratio

            hole_depth_layout.addSpacing(10)  # Small spacing between components

            # Max Depth filter container (1 part of 2:1 ratio)
            max_depth_container = QWidget()
            max_depth_container_layout = QVBoxLayout(max_depth_container)
            max_depth_container_layout.setContentsMargins(0, 0, 0, 0)
            max_depth_container_layout.setAlignment(Qt.AlignTop)

            max_depth_input = QLineEdit()
            max_depth_input.setPlaceholderText("Enter max depth (m)")
            max_depth_input.setMinimumWidth(100)  # Minimum width for usability
            max_depth_container_layout.addWidget(max_depth_input)
            # Add numeric validator - only allow positive numbers including decimals
            depth_validator = QDoubleValidator()
            depth_validator.setBottom(0.0)  # Cannot be less than 0
            depth_validator.setDecimals(2)  # Allow up to 2 decimal places
            depth_validator.setNotation(QDoubleValidator.StandardNotation)
            max_depth_input.setValidator(depth_validator)

            # Add validation feedback
            def on_depth_text_changed(text):
                if not text:  # Empty text is valid
                    max_depth_input.setStyleSheet("")
                    max_depth_input.setToolTip("")
                    return
                try:
                    value = float(text)
                    if value < 0:
                        max_depth_input.setStyleSheet("border: 1px solid red; background-color: #ffe6e6;")
                        max_depth_input.setToolTip("Depth cannot be negative")
                    else:
                        max_depth_input.setStyleSheet("")
                        max_depth_input.setToolTip("")
                except ValueError:
                    max_depth_input.setStyleSheet("border: 1px solid red; background-color: #ffe6e6;")
                    max_depth_input.setToolTip("Please enter a valid numeric value")

            max_depth_input.textChanged.connect(on_depth_text_changed)

            # Add max depth input to its container
            max_depth_container_layout.addWidget(max_depth_input)

            # Add the container to the main layout with 1 part of the ratio
            hole_depth_layout.addWidget(max_depth_container, 1)

            controls_layout.addRow("Hole Type & Depth:", hole_depth_layout)
            widgets['max_depth_input'] = max_depth_input

            # Record count controls
            count_input = QLineEdit("100")
            # Add validator for positive integers only
            count_input.setValidator(QIntValidator(1, 999999999, count_input))
            # Connect to role-based validation
            count_input.textChanged.connect(lambda: self._validate_record_count(count_input, "Holes"))

            fetch_all_checkbox = QCheckBox("Fetch all records")
            fetch_all_checkbox.toggled.connect(count_input.setDisabled)
            # Connect to custom handler for role-based restrictions
            fetch_all_checkbox.toggled.connect(lambda checked: self._handle_fetch_all_toggled(checked, "Holes"))

            # Fetch location only checkbox with info icon
            fetch_location_only_checkbox = QCheckBox("Fetch Location Only")

            # Create info icon button for holes section
            holes_location_info_button = QPushButton("ℹ")
            holes_location_info_button.setFixedSize(16, 16)
            holes_location_info_button.setToolTip("Click for information about Fetch Location Only")
            holes_location_info_button.setStyleSheet("""
                QPushButton {
                    border: 1px solid #999;
                    border-radius: 10px;
                    background-color: #e8f4f8;
                    color: #2196F3;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #d1e7dd;
                    border-color: #2196F3;
                }
            """)
            holes_location_info_button.clicked.connect(self.show_location_only_info)

            records_layout = QHBoxLayout()
            records_layout.addWidget(count_input)
            records_layout.addWidget(fetch_all_checkbox)
            records_layout.addWidget(fetch_location_only_checkbox)
            records_layout.addWidget(holes_location_info_button)
            records_layout.addStretch()
            controls_layout.addRow("No. of Records:", records_layout)

            widgets.update({
                'count_input': count_input,
                'fetch_all_checkbox': fetch_all_checkbox,
                'fetch_location_only_checkbox': fetch_location_only_checkbox
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
            operator_input.addItem("None")  # Add None as first option
            operator_input.addItems(COMPARISON_OPERATORS)
            operator_input.setCurrentIndex(0)  # Set None as default
            
            value_input = QLineEdit()
            value_input.setEnabled(False)  # Initially disabled since "None" is default
            value_input.setPlaceholderText("Select an operator first")

            # Add numeric validator - allows positive and negative numbers with decimals
            validator = QDoubleValidator()
            validator.setDecimals(10)  # Allow up to 10 decimal places
            validator.setNotation(QDoubleValidator.StandardNotation)
            value_input.setValidator(validator)

            # Add validation feedback on text change
            def on_value_text_changed(text):
                if not text:  # Empty text is valid
                    return
                # Check if the text is a valid number
                try:
                    float(text)
                    value_input.setStyleSheet("")  # Clear any error styling
                except ValueError:
                    # Invalid number - show error styling
                    value_input.setStyleSheet("border: 1px solid red; background-color: #ffe6e6;")
                    value_input.setToolTip("Please enter a valid numeric value (e.g., 1.5, -2.0, 100)")

            value_input.textChanged.connect(on_value_text_changed)

            # Create value input with ppm suffix
            value_container = QWidget()
            value_container_layout = QHBoxLayout(value_container)
            value_container_layout.setContentsMargins(0, 0, 0, 0)
            value_container_layout.setSpacing(2)
            value_container_layout.addWidget(value_input)

            ppm_label = QLabel("ppm")
            ppm_label.setStyleSheet("color: #666; font-style: italic;")
            ppm_label.mousePressEvent = lambda _: self.show_ppm_info()
            ppm_label.setCursor(QCursor(Qt.PointingHandCursor))
            ppm_label.setToolTip("Click for more information about supported units")
            value_container_layout.addWidget(ppm_label)
            
            # Connect operator change to enable/disable value field
            def on_operator_changed():
                is_none_selected = operator_input.currentText() == "None"
                # Enable/disable the actual input field, not the container
                value_input.setEnabled(not is_none_selected)
                if is_none_selected:
                    value_input.clear()
                    value_input.setPlaceholderText("Select an operator first")
                    value_input.setStyleSheet("")  # Clear any error styling
                    value_input.setToolTip("")  # Clear error tooltip
                else:
                    value_input.setPlaceholderText("Enter numeric value")
                    value_input.setStyleSheet("")  # Clear any error styling
                    value_input.setToolTip("")  # Clear error tooltip

            operator_input.currentTextChanged.connect(on_operator_changed)

            element_layout = QHBoxLayout()
            element_layout.setContentsMargins(0, 0, 0, 0)
            # element_layout.addWidget(QLabel("Element:"))
            element_layout.addWidget(element_input)
            element_layout.addSpacing(20)
            element_layout.addWidget(QLabel("Filter by Value:"))
            element_layout.addWidget(operator_input)
            element_layout.addWidget(value_container)
            element_layout.addStretch()
            controls_layout.addRow("Assay Filter:", element_layout)
            
            widgets.update({
                'element_input': element_input,
                'operator_input': operator_input,
                'value_input': value_input,
                'value_container': value_container
            })

            # Hole Type filter (separate row with container for proper alignment)
            hole_type_container_assays = QWidget()
            hole_type_container_layout_assays = QVBoxLayout(hole_type_container_assays)
            hole_type_container_layout_assays.setContentsMargins(0, 0, 0, 0)
            hole_type_container_layout_assays.setAlignment(Qt.AlignTop)
            hole_type_container_layout_assays.addWidget(hole_type_filter)
            controls_layout.addRow("Hole Type(s):", hole_type_container_assays)

            # Company filter (separate row with container for proper alignment)
            company_filter = DynamicSearchFilterWidget()
            company_filter.search_box.setPlaceholderText("Type to search companies...")
            company_filter_container = QWidget()
            company_filter_container_layout = QVBoxLayout(company_filter_container)
            company_filter_container_layout.setContentsMargins(0, 0, 0, 0)
            company_filter_container_layout.setAlignment(Qt.AlignTop)
            company_filter_container_layout.addWidget(company_filter)
            controls_layout.addRow("Company Name(s):", company_filter_container)
            widgets['company_filter'] = company_filter

            # Record count controls
            count_input = QLineEdit("100")
            # Add validator for positive integers only
            count_input.setValidator(QIntValidator(1, 999999999, count_input))
            # Connect to role-based validation
            count_input.textChanged.connect(lambda: self._validate_record_count(count_input, "Assays"))

            fetch_all_checkbox = QCheckBox("Fetch all records")
            fetch_all_checkbox.toggled.connect(count_input.setDisabled)
            # Connect to custom handler for role-based restrictions
            fetch_all_checkbox.toggled.connect(lambda checked: self._handle_fetch_all_toggled(checked, "Assays"))

            # Fetch location only checkbox with info icon
            fetch_location_only_checkbox = QCheckBox("Fetch Location Only")

            # Create info icon button for assays section
            assays_location_info_button = QPushButton("ℹ")
            assays_location_info_button.setFixedSize(20, 20)
            assays_location_info_button.setToolTip("Click for information about Fetch Location Only")
            assays_location_info_button.setStyleSheet("""
                QPushButton {
                    border: 1px solid #999;
                    border-radius: 10px;
                    background-color: #e8f4f8;
                    color: #2196F3;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #d1e7dd;
                    border-color: #2196F3;
                }
            """)
            assays_location_info_button.clicked.connect(self.show_location_only_info)

            records_layout = QHBoxLayout()
            records_layout.addWidget(count_input)
            records_layout.addWidget(fetch_all_checkbox)
            records_layout.addWidget(fetch_location_only_checkbox)
            records_layout.addWidget(assays_location_info_button)
            records_layout.addStretch()
            controls_layout.addRow("No. of Records:", records_layout)

            widgets.update({
                'count_input': count_input,
                'fetch_all_checkbox': fetch_all_checkbox,
                'fetch_location_only_checkbox': fetch_location_only_checkbox
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
        # Make columns resizable - users can adjust width by dragging column borders
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # Set minimum column width for better usability
        table.horizontalHeader().setMinimumSectionSize(50)
        # Make table read-only
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Loading label
        loading_label = QLabel("Waiting for data...")
        loading_label.setAlignment(Qt.AlignCenter)
        font = loading_label.font()
        font.setPointSize(12)
        loading_label.setFont(font)
        
        # No data label
        no_data_label = QLabel("No data present with given filters.")
        no_data_label.setAlignment(Qt.AlignCenter)
        no_data_font = no_data_label.font()
        no_data_font.setPointSize(13)
        no_data_label.setFont(no_data_font)
        no_data_label.setStyleSheet("color: #ffffff; font-style: italic;")

        # Location-only data widget (for coordinate data)
        location_widget = QWidget()
        location_layout = QVBoxLayout(location_widget)
        location_layout.setAlignment(Qt.AlignCenter)

        location_info_label = QLabel()
        location_info_label.setAlignment(Qt.AlignCenter)
        location_info_font = location_info_label.font()
        location_info_font.setPointSize(14)
        location_info_font.setBold(True)
        location_info_label.setFont(location_info_font)

        location_import_button = QPushButton("Import to QGIS")
        location_import_button.setMinimumHeight(40)
        location_import_button.setMaximumWidth(200)
        location_import_button.setDefault(False)
        location_import_button.setAutoDefault(False)
        # Style will be applied by _apply_theme_aware_styling() method

        location_layout.addWidget(location_info_label)
        location_layout.addSpacing(20)
        location_layout.addWidget(location_import_button, alignment=Qt.AlignCenter)

        content_stack.addWidget(table)
        content_stack.addWidget(loading_label)
        content_stack.addWidget(no_data_label)
        content_stack.addWidget(location_widget)
        content_stack.setCurrentWidget(loading_label)
        
        layout.addLayout(content_stack)
        
        widgets.update({
            'table': table,
            'loading_label': loading_label,
            'no_data_label': no_data_label,
            'location_widget': location_widget,
            'location_info_label': location_info_label,
            'location_import_button': location_import_button,
            'content_stack': content_stack
        })
        
        # Pagination
        pagination_widget = QWidget()
        pagination_layout = QHBoxLayout(pagination_widget)
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        pagination_widget.setVisible(False)  # Hidden by default
        layout.addWidget(pagination_widget)
        
        widgets.update({
            'prev_button': prev_button,
            'page_label': page_label,
            'next_button': next_button,
            'pagination_widget': pagination_widget
        })
        
        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        import_button = QPushButton("Import to QGIS")
        import_button.setDefault(False)
        import_button.setAutoDefault(False)
        import_button.setVisible(False)  # Hidden until data is available
        
        action_layout.addWidget(import_button)
        layout.addLayout(action_layout)
        
        widgets.update({
            'import_button': import_button
        })
        
        return widgets
    
    def _create_status_bar(self):
        """Create the status bar with cancel button."""
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel(UI_CONFIG['status_messages']['ready'])
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Create cancel button
        self.cancel_button = QPushButton("Cancel Request")
        self.cancel_button.setDefault(False)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.setVisible(False)  # Hidden by default
        
        # Style will be applied by _apply_theme_aware_styling() method
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.cancel_button)
        
        self.main_layout.addLayout(status_layout)
    
    def _connect_signals(self):
        """Connect UI signals."""
        # Header buttons
        self.login_button.clicked.connect(self._handle_login_button)
        self.reset_all_button.clicked.connect(self._handle_reset_all)
        
        # Cancel button
        self.cancel_button.clicked.connect(self.cancel_request_requested.emit)
        
        # Fetch buttons
        self.holes_tab['fetch_button'].clicked.connect(lambda: self._handle_fetch_request("Holes"))
        self.assays_tab['fetch_button'].clicked.connect(lambda: self._handle_fetch_request("Assays"))
        
        
        # Import buttons
        self.holes_tab['import_button'].clicked.connect(lambda: self._handle_import_request("Holes"))
        self.assays_tab['import_button'].clicked.connect(lambda: self._handle_import_request("Assays"))

        # Location import buttons
        self.holes_tab['location_import_button'].clicked.connect(lambda: self._handle_import_request("Holes"))
        self.assays_tab['location_import_button'].clicked.connect(lambda: self._handle_import_request("Assays"))
        
        # Pagination buttons
        self.holes_tab['prev_button'].clicked.connect(lambda: self.page_previous_requested.emit("Holes"))
        self.holes_tab['next_button'].clicked.connect(lambda: self.page_next_requested.emit("Holes"))
        self.assays_tab['prev_button'].clicked.connect(lambda: self.page_previous_requested.emit("Assays"))
        self.assays_tab['next_button'].clicked.connect(lambda: self.page_next_requested.emit("Assays"))
        
        # Company search
        self.holes_tab['company_filter'].textChanged.connect(self._on_company_search_text_changed)
        self.assays_tab['company_filter'].textChanged.connect(self._on_company_search_text_changed)
    
    def _handle_login_button(self):
        """Handle login/logout button click."""
        if self.login_button.text() == "Login":
            self.login_requested.emit()
        else:
            self.logout_requested.emit()
    
    def _handle_reset_all(self):
        """Handle reset all button click - clear all data and filters."""
        # Clear all data from memory via DataManager
        self.data_clear_requested.emit("Holes")
        self.data_clear_requested.emit("Assays")
        
        # Reset all filter inputs to default values
        self._reset_all_filters()
    
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

        # Handle hole types - convert to comma-separated string, exclude empty values
        selected_hole_types = tab_widgets['hole_type_filter'].currentData()
        # Filter out empty values (which represent "All Hole Types")
        valid_hole_types = [hole_type for hole_type in selected_hole_types if hole_type and hole_type.strip()]
        if valid_hole_types:
            params['hole_type'] = ",".join(valid_hole_types)
        
        if tab_name == "Holes":
            companies = tab_widgets['company_filter'].currentData()
            if companies:
                params['companies'] = ",".join(companies)

            # Add max_depth parameter if specified
            max_depth_text = tab_widgets['max_depth_input'].text().strip()
            if max_depth_text:
                try:
                    max_depth_value = float(max_depth_text)
                    if max_depth_value >= 0:  # Ensure non-negative
                        params['max_depth'] = max_depth_value
                except ValueError:
                    # Invalid depth value - skip parameter (UI validation should prevent this)
                    pass
        else:  # Assays
            element = tab_widgets['element_input'].currentData()
            operator = tab_widgets['operator_input'].currentText()
            value = tab_widgets['value_input'].text().strip()

            # Element is required for assays API
            params['element'] = element

            # Only add operator and value if operator is not "None"
            if operator != "None":
                params['operator'] = operator
                if value:
                    params['value'] = value

            # Add companies parameter if specified (same as Holes section)
            companies = tab_widgets['company_filter'].currentData()
            if companies:
                params['companies'] = ",".join(companies)
        
        # Check if fetch_all is requested
        fetch_all = tab_widgets['fetch_all_checkbox'].isChecked()

        # Add fetch_all_records parameter when fetch all checkbox is checked
        if fetch_all:
            params['fetch_all_records'] = True

        # Check if fetch_only_location is requested
        fetch_location_only_checkbox = tab_widgets.get('fetch_location_only_checkbox')
        fetch_location_only = fetch_location_only_checkbox.isChecked() if fetch_location_only_checkbox else False

        if fetch_location_only:
            params['fetch_only_location'] = True

        # Get requested record count
        if not fetch_all:
            try:
                requested_count = int(tab_widgets['count_input'].text() or "100")
                params['requested_count'] = requested_count
            except ValueError:
                requested_count = 100
                params['requested_count'] = requested_count

        # Emit request signal
        self.data_fetch_requested.emit(tab_name, params, fetch_all)
    
    
    def _generate_dynamic_layer_name(self, tab_name: str) -> str:
        """Generate a dynamic layer name based on current filter selections."""
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab

        # Base name
        name_parts = [tab_name]

        # Add state information
        selected_states = tab_widgets['state_filter'].currentData()
        valid_states = [state for state in selected_states if state and state.strip()]
        if valid_states and len(valid_states) <= 3:  # Don't include if too many states
            name_parts.extend(valid_states)
        elif len(valid_states) > 3:
            name_parts.append(f"{len(valid_states)}States")

        # Tab-specific filters
        if tab_name == "Holes":
            # Add company information
            companies = tab_widgets['company_filter'].currentData()
            if companies and len(companies) <= 2:  # Limit to avoid long names
                # Use first 10 characters of each company name
                company_abbrevs = [company[:10] for company in companies]
                name_parts.extend(company_abbrevs)
            elif len(companies) > 2:
                name_parts.append(f"{len(companies)}Cos")

        else:  # Assays
            # Add element information
            element = tab_widgets['element_input'].currentData()
            if element:
                name_parts.append(element)

            # Add operator and value if present
            operator = tab_widgets['operator_input'].currentText()
            if operator and operator != "None":
                value = tab_widgets['value_input'].text().strip()
                if value:
                    name_parts.append(f"{operator}{value}ppm")
                else:
                    name_parts.append(operator)

        # Add record count information
        fetch_all = tab_widgets['fetch_all_checkbox'].isChecked()
        fetch_location_only_checkbox = tab_widgets.get('fetch_location_only_checkbox')
        fetch_location_only = fetch_location_only_checkbox.isChecked() if fetch_location_only_checkbox else False

        if fetch_location_only:
            name_parts.append("LocationOnly")
            # Also add record count for location only if not fetch all
            if not fetch_all:
                try:
                    requested_count = int(tab_widgets['count_input'].text() or "100")
                    name_parts.append(f"{requested_count}rec")
                except ValueError:
                    name_parts.append("100rec")
        elif not fetch_all:
            try:
                requested_count = int(tab_widgets['count_input'].text() or "100")
                name_parts.append(f"{requested_count}rec")
            except ValueError:
                name_parts.append("100rec")
        # For fetch_all, don't add anything as per requirements

        # Join parts with underscores and limit total length
        layer_name = "_".join(name_parts)

        # Limit total length to avoid overly long names
        if len(layer_name) > 50:
            layer_name = layer_name[:47] + "..."

        return layer_name

    def _handle_import_request(self, tab_name: str):
        """Handle data import request."""
        # Show layer options dialog with dynamic default name
        default_name = self._generate_dynamic_layer_name(tab_name)
        options_dialog = LayerOptionsDialog(default_name, self)
        
        if options_dialog.exec_() == QDialog.Accepted:
            layer_name, color = options_dialog.get_options()
            self.data_import_requested.emit(tab_name, layer_name, color)
    
    def _show_role_info(self):
        """Show detailed information about the user's current role/plan."""
        if not self.data_manager or not self.data_manager.is_authenticated():
            return

        role = self.data_manager.api_client.get_user_role()
        if not role or role not in ROLE_DESCRIPTIONS:
            self.show_info("Your account information is being loaded...")
            return

        # Get role description
        description = ROLE_DESCRIPTIONS[role]
        display_name = ROLE_DISPLAY_NAMES.get(role, role)

        # Show in a dialog
        QMessageBox.information(self, f"Your Plan: {display_name}", description)

    def _update_role_badge(self):
        """Update the role badge display based on current user role."""
        if not self.data_manager or not self.data_manager.is_authenticated():
            self.role_badge.setVisible(False)
            return

        role = self.data_manager.api_client.get_user_role()
        if not role or role not in ROLE_DISPLAY_NAMES:
            self.role_badge.setVisible(False)
            return

        # Get display name
        display_name = ROLE_DISPLAY_NAMES[role]
        self.role_badge.setText(display_name)
        self.role_badge.setVisible(True)

        # Apply role-specific styling (smaller, compact design)
        if role == "tier_1":
            # Free Trial - Light blue/gray style
            self.role_badge.setStyleSheet("""
                QPushButton {
                    background-color: #E3F2FD;
                    color: #1976D2;
                    border: 1px solid #64B5F6;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-weight: bold;
                    font-size: 10px;
                    max-height: 18px;
                }
                QPushButton:hover {
                    background-color: #BBDEFB;
                    border-color: #1976D2;
                }
                QPushButton:pressed {
                    background-color: #90CAF9;
                }
            """)
        elif role == "tier_2":
            # Premium - Gold/amber style
            self.role_badge.setStyleSheet("""
                QPushButton {
                    background-color: #FFF3E0;
                    color: #E65100;
                    border: 1px solid #FFB74D;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-weight: bold;
                    font-size: 10px;
                    max-height: 18px;
                }
                QPushButton:hover {
                    background-color: #FFE0B2;
                    border-color: #E65100;
                }
                QPushButton:pressed {
                    background-color: #FFCC80;
                }
            """)
        elif role == "admin":
            # Admin - Purple style
            self.role_badge.setStyleSheet("""
                QPushButton {
                    background-color: #F3E5F5;
                    color: #6A1B9A;
                    border: 1px solid #BA68C8;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-weight: bold;
                    font-size: 10px;
                    max-height: 18px;
                }
                QPushButton:hover {
                    background-color: #E1BEE7;
                    border-color: #6A1B9A;
                }
                QPushButton:pressed {
                    background-color: #CE93D8;
                }
            """)

    def _validate_record_count(self, count_input: QLineEdit, tab_name: str):
        """Validate record count input for tier_1 users (max 1000 records)."""
        # Get the current text
        text = count_input.text().strip()

        # If empty or being edited, allow it
        if not text:
            count_input.setStyleSheet("")
            return

        # Try to parse the value
        try:
            value = int(text)

            # Check if user is tier_1 and exceeds limit
            if self.data_manager and self.data_manager.is_authenticated():
                role = self.data_manager.api_client.get_user_role()

                if role == "tier_1" and value > 1000:
                    # Show error styling
                    count_input.setStyleSheet("border: 2px solid #f44336; background-color: #ffebee;")

                    # Reset to 1000
                    count_input.blockSignals(True)
                    count_input.setText("1000")
                    count_input.blockSignals(False)

                    # Show message (this blocks until user clicks OK)
                    self.show_info(
                        "Free Trial Record Limit Exceeded\n\n"
                        "As a Free Trial user, you can fetch a maximum of 1,000 records at a time.\n\n"
                        "Your entry has been adjusted to 1,000 records.\n\n"
                        "Upgrade to Premium for unlimited record fetching!"
                    )

                    # Clear error styling immediately after user dismisses the popup
                    count_input.setStyleSheet("")
                else:
                    # Valid input, clear any error styling
                    count_input.setStyleSheet("")
            else:
                # Not logged in or not tier_1, clear any error styling
                count_input.setStyleSheet("")

        except ValueError:
            # Invalid number, but let the QIntValidator handle it
            pass

    def _handle_fetch_all_toggled(self, checked: bool, tab_name: str):
        """Handle fetch all checkbox toggle with role-based validation."""
        if not checked:
            return  # Allow unchecking

        # Get the widgets
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
        fetch_all_checkbox = tab_widgets['fetch_all_checkbox']
        count_input = tab_widgets['count_input']

        # Check if user is logged in
        if not self.data_manager or not self.data_manager.is_authenticated():
            # Block the check and show message
            fetch_all_checkbox.blockSignals(True)
            fetch_all_checkbox.setChecked(False)
            fetch_all_checkbox.blockSignals(False)
            # Re-enable the count input field
            count_input.setEnabled(True)
            self.show_info("Please login before using 'Fetch all records'")
            return

        # Check if user has permission based on role
        if not self.data_manager.api_client.can_fetch_all_records():
            role = self.data_manager.api_client.get_user_role()
            # Block the check and show message
            fetch_all_checkbox.blockSignals(True)
            fetch_all_checkbox.setChecked(False)
            fetch_all_checkbox.blockSignals(False)
            # Re-enable the count input field
            count_input.setEnabled(True)

            if role == "tier_1":
                self.show_info(
                    "Fetch All Records - Free Trial Limitation\n\n"
                    "You are currently on Free Trial. On this tier, you can fetch a maximum of 1000 records at a time.\n\n"
                    "To unlock unlimited record fetching, please upgrade to Premium by contacting Needle Digital."
                )
            else:
                self.show_info("You don't have permission to fetch all records.")

    def set_data_manager(self, data_manager):
        """Set the data manager reference for role checks."""
        self.data_manager = data_manager
        # Update fetch all checkbox state based on role
        self.update_fetch_all_permissions()

    def update_fetch_all_permissions(self):
        """Update fetch all checkbox state based on user role."""
        # Check both tabs
        for tab_name in ['Holes', 'Assays']:
            tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
            fetch_all_checkbox = tab_widgets['fetch_all_checkbox']

            # Reset to unchecked and enabled by default
            fetch_all_checkbox.setChecked(False)
            fetch_all_checkbox.setEnabled(True)
            fetch_all_checkbox.setToolTip("")

            # If not logged in, keep enabled but show tooltip
            if not self.data_manager or not self.data_manager.is_authenticated():
                fetch_all_checkbox.setToolTip("Login required to fetch all records")
                continue

            # Check role-based permissions
            role = self.data_manager.api_client.get_user_role()
            can_fetch_all = self.data_manager.api_client.can_fetch_all_records()

            if not can_fetch_all and role == "tier_1":
                # Keep enabled but show tooltip - validation happens on click
                fetch_all_checkbox.setToolTip(
                    "Tier 1 (Trial): Limited to 1000 records per fetch. Upgrade to Tier 2 for unlimited fetching."
                )
            else:
                fetch_all_checkbox.setToolTip("Fetch all available records matching the filters")

    def update_login_status(self, is_logged_in: bool, user_info: str = ""):
        """Update UI based on login status."""
        if is_logged_in:
            self.login_button.setText("Logout")
            self.reset_all_button.setVisible(True)
            status = UI_CONFIG['status_messages']['authenticated']
            if user_info:
                status = f"Ready to fetch data. Logged in as {user_info}"
            self.status_label.setText(status)

            # Update role badge after login
            self._update_role_badge()

            # Update fetch all checkbox permissions after login
            self.update_fetch_all_permissions()
        else:
            self.login_button.setText("Login")
            self.reset_all_button.setVisible(False)
            self.status_label.setText(UI_CONFIG['status_messages']['ready'])

            # Hide role badge after logout
            self.role_badge.setVisible(False)

            # Update fetch all checkbox permissions after logout
            self.update_fetch_all_permissions()
    
    def update_status(self, message: str):
        """Update status message."""
        self.status_label.setText(message)
    
    def update_progress(self, value: int):
        """Update progress bar."""
        if value >= 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(value)
        else:
            self.progress_bar.setVisible(False)
    
    def show_data(self, tab_name: str, data: list, headers: list, pagination_info: dict):
        """Show data in the specified tab with pagination info."""
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
        
        # Check if we're currently in loading state
        # If so, don't switch away from loading view unless we have data or this is a successful empty response
        # A successful empty response is indicated by pagination_info having has_data = False AND not being a reset operation
        is_successful_empty_response = (not data and
                                       pagination_info.get('has_data') == False and
                                       not pagination_info.get('is_reset_operation', False))
        if self._loading_states[tab_name] and not data and not is_successful_empty_response:
            return
        
        table = tab_widgets['table']
        loading_label = tab_widgets['loading_label']
        no_data_label = tab_widgets['no_data_label']
        content_stack = tab_widgets['content_stack']
        import_button = tab_widgets['import_button']
        pagination_widget = tab_widgets['pagination_widget']
        page_label = tab_widgets['page_label']
        
        # Debug logging for troubleshooting

        # Check if this is location-only data (based on headers)
        is_location_only = (
            len(headers) == 3 and
            set(headers) == {'latitude', 'longitude', 'location_string'}
        )

        if data:
            # Check if we should display location-only view
            if is_location_only:
                # For location-only, remove location_string column and show only lat/lon
                headers = ['latitude', 'longitude']  # Only show these 2 columns
                # Filter data to only include lat/lon columns
                filtered_data = []
                for record in data:
                    filtered_record = {
                        'latitude': record.get('latitude', ''),
                        'longitude': record.get('longitude', '')
                    }
                    filtered_data.append(filtered_record)
                data = filtered_data

                content_stack = tab_widgets['content_stack']
                import_button = tab_widgets['import_button']
                pagination_widget = tab_widgets['pagination_widget']

                # Show the table with location data
                content_stack.setCurrentWidget(table)
                import_button.setVisible(True)
                import_button.setEnabled(True)
                pagination_widget.setVisible(False)
                # Continue with normal table display logic below

            # Calculate which data to show for current page (100 records max per page)
            records_per_page = 100
            current_page = pagination_info.get('current_page', 1)
            start_idx = (current_page - 1) * records_per_page
            end_idx = min(start_idx + records_per_page, len(data))
            page_data = data[start_idx:end_idx]
            
            # Enhanced table display with better UX
            table.setRowCount(len(page_data))
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)

            # Enhanced population with N/A for nulls and tooltips
            for row_idx, record in enumerate(page_data):
                for col_idx, header in enumerate(headers):
                    value = record.get(header, '')

                    # Handle null/empty values
                    if value is None or value == '' or (isinstance(value, str) and value.strip() == ''):
                        display_value = 'N/A'
                        tooltip_value = 'No data available'
                        item = QTableWidgetItem(display_value)
                        # Style N/A cells with italics and muted color
                        font = item.font()
                        font.setItalic(True)
                        item.setFont(font)
                        # Set a muted text color for N/A values
                        item.setForeground(QColor(128, 128, 128))  # Gray color
                    else:
                        display_value = str(value)
                        tooltip_value = str(value)
                        item = QTableWidgetItem(display_value)

                    # Set tooltip to show the cell value on hover
                    item.setToolTip(f"{header}: {tooltip_value}")
                    table.setItem(row_idx, col_idx, item)

            # Auto-resize columns to fit content initially, but keep them user-resizable
            table.resizeColumnsToContents()

            # Ensure no column is too narrow or too wide
            for col in range(table.columnCount()):
                width = table.columnWidth(col)
                # Set minimum width of 80px and maximum of 300px for better readability
                if width < 80:
                    table.setColumnWidth(col, 80)
                elif width > 300:
                    table.setColumnWidth(col, 300)

            content_stack.setCurrentWidget(table)
            import_button.setVisible(True)
            import_button.setEnabled(True)
            
            # Update pagination
            prev_button = tab_widgets['prev_button']
            next_button = tab_widgets['next_button']
            
            if pagination_info['has_data'] and pagination_info['total_pages'] > 1:
                pagination_widget.setVisible(True)
                page_text = f"Page {pagination_info['current_page']} of {pagination_info['total_pages']}"
                page_text += f" (showing {pagination_info['total_records']} records)"
                page_label.setText(page_text)
                
                # Enable/disable navigation buttons
                prev_button.setEnabled(pagination_info['current_page'] > 1)
                next_button.setEnabled(pagination_info['current_page'] < pagination_info['total_pages'])
            else:
                pagination_widget.setVisible(False)
                prev_button.setEnabled(False)
                next_button.setEnabled(False)
        else:
            # Handle empty data case - either reset operation or API call with 0 results
            is_reset_operation = pagination_info.get('is_reset_operation', False)

            if is_reset_operation:
                # Reset operation - show "Waiting for data..." message
                content_stack.setCurrentWidget(loading_label)
                import_button.setVisible(False)
                pagination_widget.setVisible(False)
            elif is_location_only:
                # Even with no data, if it's a location-only request, show the location view with 0 records
                self._show_location_only_data(tab_widgets, 0)
            else:
                # API call returned 0 results - show "No data present with given filters"
                content_stack.setCurrentWidget(no_data_label)
                import_button.setVisible(False)
                pagination_widget.setVisible(False)


    
    def show_error(self, message: str):
        """Show error message."""
        QMessageBox.critical(self, "Error", message)
    
    def show_info(self, message: str):
        """Show information message."""
        QMessageBox.information(self, "Information", message)

    def show_plugin_message(self, message: str, message_type: str = "info", duration: int = 3000):
        """Show a message in the plugin's message bar."""
        try:
            if hasattr(self.message_bar, 'show_message'):
                self.message_bar.show_message(message, message_type, duration)
            else:
                # Fallback for QLabel
                self.message_bar.setText(f"[{message_type.upper()}] {message}")
                self.message_bar.setVisible(True)
                # Create a timer to hide the fallback message
                QTimer.singleShot(duration, lambda: self.message_bar.setVisible(False))
        except Exception as e:
            # If all else fails, just log the message
            log_error(f"Failed to show plugin message: {message} (Error: {e})")

    def validate_token_on_show(self):
        """Validate token when dialog is shown and logout if expired."""
        try:
            # This method will be called from data_importer, so we need to emit a signal
            # or call the parent's validation method
            self.validate_token_requested.emit()
        except Exception as e:
            log_error(f"Token validation error: {e}")

    # Add signal for token validation requests
    validate_token_requested = pyqtSignal()

    def show_ppm_info(self):
        """Show information about supported measurement units."""
        QMessageBox.information(
            self,
            "Measurement Units",
            "Currently our system only serves ppm (parts per million) values.\n"
            "We will be adding more measurement units in the future."
        )

    def show_location_only_info(self):
        """Show information about Fetch Location Only feature."""
        QMessageBox.information(
            self, "Fetch Location Only Info",
            "Enable this option for faster loading of large datasets.\n\n"
            "When enabled:\n"
            "• Only coordinates are fetched\n"
            "• Significantly faster data retrieval and processing\n"
            "• Reduced memory usage for large datasets\n"
            "• Ideal for viewing drill hole locations on the map\n\n"
            "When disabled:\n"
            "• Full dataset with all attributes is fetched\n"
            "• Slower for large datasets but includes complete data\n"
            "• Better for detailed analysis and attribute queries\n\n"
        )

    def show_cancel_button(self):
        """Show the cancel request button during API calls."""
        self.cancel_button.setVisible(True)
    
    def hide_cancel_button(self):
        """Hide the cancel request button when not making API calls."""
        self.cancel_button.setVisible(False)
    
    def show_and_raise(self):
        """Show the dialog and bring it to front."""
        # Show the dialog
        self.show()

        # Bring to front and activate
        self.raise_()
        self.activateWindow()

        # For additional assurance on some systems
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)

        # Check token validity when dialog is shown/brought to front
        self.validate_token_on_show()
    
    def show_loading(self, tab_name: str):
        """Show loading state for the specified tab."""
        self._loading_states[tab_name] = True
        
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
        
        loading_label = tab_widgets['loading_label']
        content_stack = tab_widgets['content_stack']
        import_button = tab_widgets['import_button']
        pagination_widget = tab_widgets['pagination_widget']
        fetch_button = tab_widgets['fetch_button']
        
        # Clear any previous data from memory and UI efficiently
        table = tab_widgets['table']
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(0)
            table.setColumnCount(0)
        finally:
            table.setUpdatesEnabled(True)
        
        # Show loading state
        loading_label.setText("Loading data...")
        content_stack.setCurrentWidget(loading_label)
        
        # Show progress bar immediately when loading starts at 1%
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(1)
        
        # Hide other components during loading
        import_button.setVisible(False)
        pagination_widget.setVisible(False)
        
        # Disable fetch button to prevent multiple requests
        fetch_button.setEnabled(False)
        
        # Disable all UI controls during loading
        self._disable_all_controls()
    
    def hide_loading(self, tab_name: str):
        """Hide loading state and re-enable fetch button for the specified tab."""
        self._loading_states[tab_name] = False
        
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
        fetch_button = tab_widgets['fetch_button']
        loading_label = tab_widgets['loading_label']
        content_stack = tab_widgets['content_stack']
        
        # Re-enable fetch button
        fetch_button.setEnabled(True)
        
        # Hide progress bar when loading is complete
        self.progress_bar.setVisible(False)
        
        # Restore original waiting message
        loading_label.setText("Waiting for data...")
        
        # Only show waiting message if there's no data in the table AND no data has been fetched yet
        # If show_data has been called with empty results, it will have set the appropriate view
        table = tab_widgets['table']
        if table.rowCount() == 0:
            # Check if we're currently showing the no_data_label, if so don't override it
            current_widget = content_stack.currentWidget()
            no_data_label = tab_widgets['no_data_label']
            if current_widget != no_data_label:
                content_stack.setCurrentWidget(loading_label)
        
        # Re-enable all UI controls after loading
        self._enable_all_controls()
    
    def _disable_all_controls(self):
        """Disable all UI controls during API requests except cancel button."""
        # Disable tab switching
        self.tabs.setEnabled(False)
        
        # Disable header buttons
        self.login_button.setEnabled(False)
        self.reset_all_button.setEnabled(False)
        
        # Disable all controls in both tabs
        for tab_name in ['Holes', 'Assays']:
            tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
            
            # Disable filter controls
            tab_widgets['state_filter'].setEnabled(False)
            tab_widgets['hole_type_filter'].setEnabled(False)
            
            if tab_name == "Holes":
                tab_widgets['company_filter'].setEnabled(False)
                tab_widgets['max_depth_input'].setEnabled(False)
                tab_widgets['count_input'].setEnabled(False)
                tab_widgets['fetch_all_checkbox'].setEnabled(False)
                tab_widgets['fetch_location_only_checkbox'].setEnabled(False)
            else:  # Assays
                tab_widgets['element_input'].setEnabled(False)
                tab_widgets['operator_input'].setEnabled(False)
                tab_widgets['value_input'].setEnabled(False)
                tab_widgets['company_filter'].setEnabled(False)
                tab_widgets['count_input'].setEnabled(False)
                tab_widgets['fetch_all_checkbox'].setEnabled(False)
                tab_widgets['fetch_location_only_checkbox'].setEnabled(False)
            
            # Disable pagination and import buttons
            tab_widgets['prev_button'].setEnabled(False)
            tab_widgets['next_button'].setEnabled(False)
            tab_widgets['import_button'].setEnabled(False)
    
    def _enable_all_controls(self):
        """Re-enable all UI controls after API requests complete."""
        # Re-enable tab switching
        self.tabs.setEnabled(True)
        
        # Re-enable header buttons
        self.login_button.setEnabled(True)
        self.reset_all_button.setEnabled(True)
        
        # Re-enable all controls in both tabs
        for tab_name in ['Holes', 'Assays']:
            tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab
            
            # Re-enable filter controls
            tab_widgets['state_filter'].setEnabled(True)
            tab_widgets['hole_type_filter'].setEnabled(True)
            
            if tab_name == "Holes":
                tab_widgets['company_filter'].setEnabled(True)
                tab_widgets['max_depth_input'].setEnabled(True)
                # Only enable count input if fetch all checkbox is not checked
                fetch_all_checked = tab_widgets['fetch_all_checkbox'].isChecked()
                tab_widgets['count_input'].setEnabled(not fetch_all_checked)
                tab_widgets['fetch_all_checkbox'].setEnabled(True)
                tab_widgets['fetch_location_only_checkbox'].setEnabled(True)
            else:  # Assays
                tab_widgets['element_input'].setEnabled(True)
                tab_widgets['operator_input'].setEnabled(True)
                # Check if value input should be enabled based on operator
                operator_text = tab_widgets['operator_input'].currentText()
                tab_widgets['value_input'].setEnabled(operator_text != "None")
                tab_widgets['company_filter'].setEnabled(True)
                # Only enable count input if fetch all checkbox is not checked
                fetch_all_checked = tab_widgets['fetch_all_checkbox'].isChecked()
                tab_widgets['count_input'].setEnabled(not fetch_all_checked)
                tab_widgets['fetch_all_checkbox'].setEnabled(True)
                tab_widgets['fetch_location_only_checkbox'].setEnabled(True)
            
            # Note: fetch buttons are handled individually in hide_loading()
            # Note: pagination and import buttons are handled by show_data() based on data availability
    
    def _reset_all_filters(self):
        """Reset all filter inputs to their default values."""
        # Reset Holes tab filters
        holes_tab = self.holes_tab
        
        # Reset state filter to "All States" (first item, empty value)
        holes_tab['state_filter'].setCurrentData([""])

        # Reset hole type filter - clear all selections and search box
        holes_tab['hole_type_filter'].setCurrentData([])
        holes_tab['hole_type_filter'].search_box.clear()
        
        # Reset company filter
        holes_tab['company_filter'].setCurrentData([])
        holes_tab['company_filter'].search_box.clear()

        # Reset max depth filter
        holes_tab['max_depth_input'].clear()
        holes_tab['max_depth_input'].setStyleSheet("")  # Clear any error styling
        holes_tab['max_depth_input'].setToolTip("")  # Clear error tooltip

        # Reset record count and fetch all checkbox
        holes_tab['count_input'].setText("100")
        holes_tab['fetch_all_checkbox'].setChecked(False)
        holes_tab['count_input'].setEnabled(True)  # Ensure count input is enabled
        holes_tab['fetch_location_only_checkbox'].setChecked(False)
        
        # Reset Assays tab filters  
        assays_tab = self.assays_tab
        
        # Reset state filter to "All States" (first item, empty value)
        assays_tab['state_filter'].setCurrentData([""])

        # Reset hole type filter - clear all selections and search box
        assays_tab['hole_type_filter'].setCurrentData([])
        assays_tab['hole_type_filter'].search_box.clear()
        
        # Reset element to first item (index 0)
        assays_tab['element_input'].setCurrentIndex(0)
        
        # Reset operator to "None" (index 0)
        assays_tab['operator_input'].setCurrentIndex(0)
        
        # Clear and disable value input
        assays_tab['value_input'].clear()
        assays_tab['value_input'].setEnabled(False)
        assays_tab['value_input'].setPlaceholderText("Select an operator first")
        assays_tab['value_input'].setStyleSheet("")  # Clear any error styling
        assays_tab['value_input'].setToolTip("")  # Clear error tooltip

        # Reset company filter (same as in Holes section)
        assays_tab['company_filter'].setCurrentData([])
        assays_tab['company_filter'].search_box.clear()

        # Reset record count and fetch all checkbox
        assays_tab['count_input'].setText("100")
        assays_tab['fetch_all_checkbox'].setChecked(False)
        assays_tab['count_input'].setEnabled(True)  # Ensure count input is enabled
        assays_tab['fetch_location_only_checkbox'].setChecked(False)
    
    def _on_company_search_text_changed(self, text: str):
        """Handle company search text changes with debouncing."""
        self._current_company_query = text
        # Restart the timer on each text change (debouncing)
        self.company_search_timer.stop()
        self.company_search_timer.start(500)  # 500ms delay
    
    def _perform_company_search(self):
        """Perform the actual company search."""
        query = self._current_company_query.strip()
        self.company_search_requested.emit(query)
    
    def handle_company_search_results(self, results: list):
        """Handle company search results from the API."""
        # Only show results in the currently active tab's company filter
        current_tab_index = self.tabs.currentIndex()
        current_tab_name = "Holes" if current_tab_index == 0 else "Assays"

        if current_tab_name == "Holes":
            if hasattr(self.holes_tab['company_filter'], 'showPopup'):
                self.holes_tab['company_filter'].showPopup(results)
        else:  # Assays
            if hasattr(self.assays_tab['company_filter'], 'showPopup'):
                self.assays_tab['company_filter'].showPopup(results)


    def _apply_theme_aware_styling(self):
        """Apply theme-aware styling to buttons for visibility in both light and dark themes."""
        try:
            # Get the current palette to detect theme
            palette = QApplication.palette()

            # Determine if we're in dark theme by checking window background
            window_color = palette.color(palette.Window)
            is_dark_theme = window_color.lightness() < 128

            # Define colors based on theme - softer, more soothing colors
            if is_dark_theme:
                # Dark theme colors - muted and easy on eyes
                primary_bg = "#303131"      # Soft sage green
                primary_text = "#FFFFFF"    # White text
                secondary_bg = "#6B8CAE"    # Muted blue-gray
                secondary_text = "#FFFFFF"  # White text
                danger_bg = "#D75A5A"       # Muted rose/dusty red
                danger_text = "#FFFFFF"     # White text
                border_color = "#666666"    # Gray border
            else:
                # Light theme colors - soft pastels
                primary_bg = "#2C2C2C"      # Light sage green
                primary_text = "#FFFFFF"    # White text
                secondary_bg = "#6B8CAE"    # Soft periwinkle blue
                secondary_text = "#FFFFFF"  # White text
                danger_bg = "#D4A5A5"       # Soft dusty rose
                danger_text = "#FFFFFF"     # White text
                border_color = "#CCCCCC"    # Light gray border

            # Common button style template
            button_style_template = """
                QPushButton {{
                    background-color: {bg_color};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    min-height: 24px;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                    border: 1px solid {hover_border};
                }}
                QPushButton:pressed {{
                    background-color: {pressed_bg};
                }}
                QPushButton:disabled {{
                    background-color: #CCCCCC;
                    color: #666666;
                    border: 1px solid #BBBBBB;
                }}
            """

            # Calculate hover and pressed colors
            def adjust_color_brightness(color_hex, factor):
                """Adjust color brightness by factor (0.0 = black, 1.0 = original, 2.0 = white)."""
                color = QColor(color_hex)
                h, s, l, a = color.getHsl()
                l = min(255, int(l * factor))
                color.setHsl(h, s, l, a)
                return color.name()

            # Style for primary buttons (Login/Logout, Fetch buttons)
            primary_style = button_style_template.format(
                bg_color=primary_bg,
                text_color=primary_text,
                border_color=border_color,
                hover_bg=adjust_color_brightness(primary_bg, 1.2),
                hover_border=adjust_color_brightness(border_color, 1.3),
                pressed_bg=adjust_color_brightness(primary_bg, 0.8)
            )

            # Style for secondary buttons (Import to QGIS)
            secondary_style = button_style_template.format(
                bg_color=secondary_bg,
                text_color=secondary_text,
                border_color=border_color,
                hover_bg=adjust_color_brightness(secondary_bg, 1.2),
                hover_border=adjust_color_brightness(border_color, 1.3),
                pressed_bg=adjust_color_brightness(secondary_bg, 0.8)
            )

            # Style for danger buttons (Reset All, Cancel)
            danger_style = button_style_template.format(
                bg_color=danger_bg,
                text_color=danger_text,
                border_color=border_color,
                hover_bg=adjust_color_brightness(danger_bg, 1.2),
                hover_border=adjust_color_brightness(border_color, 1.3),
                pressed_bg=adjust_color_brightness(danger_bg, 0.8)
            )

            # Apply styles to buttons
            # Header buttons
            self.login_button.setStyleSheet(primary_style)
            self.reset_all_button.setStyleSheet(danger_style)

            # Fetch buttons
            self.holes_tab['fetch_button'].setStyleSheet(primary_style)
            self.assays_tab['fetch_button'].setStyleSheet(primary_style)

            # Import buttons
            self.holes_tab['import_button'].setStyleSheet(secondary_style)
            self.assays_tab['import_button'].setStyleSheet(secondary_style)

            # Location import buttons (override the existing hardcoded style)
            self.holes_tab['location_import_button'].setStyleSheet(secondary_style)
            self.assays_tab['location_import_button'].setStyleSheet(secondary_style)

            # Cancel button (already has some styling, but make it theme-aware)
            self.cancel_button.setStyleSheet(danger_style + """
                QPushButton {
                    font-size: 12px;
                    padding: 4px 8px;
                    min-height: 20px;
                }
            """)


        except Exception as e:
            log_warning(f"Failed to apply theme-aware styling: {e}")
            # Fallback to basic styling that should work in any theme
            basic_style = """
                QPushButton {
                    background-color: #8DB5A2;
                    color: white;
                    border: 1px solid #7AA394;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    min-height: 24px;
                }
                QPushButton:hover {
                    background-color: #7AA394;
                }
                QPushButton:pressed {
                    background-color: #6B9486;
                }
            """

            # Apply basic style to all buttons as fallback
            for button in [self.login_button, self.reset_all_button,
                          self.holes_tab['fetch_button'], self.assays_tab['fetch_button'],
                          self.holes_tab['import_button'], self.assays_tab['import_button'],
                          self.holes_tab['location_import_button'], self.assays_tab['location_import_button'],
                          self.cancel_button]:
                button.setStyleSheet(basic_style)

    def _setup_window_geometry(self):
        """Setup window size to 75% width and full height, centered to QGIS."""
        try:
            # Get the main QGIS window
            qgis_main_window = None
            for widget in QApplication.topLevelWidgets():
                if widget.objectName() == "QgisApp":
                    qgis_main_window = widget
                    break

            if qgis_main_window:
                # Get QGIS window geometry
                qgis_geometry = qgis_main_window.geometry()
                qgis_screen = qgis_main_window.screen()
            else:
                # Fallback to primary screen if QGIS window not found
                qgis_screen = QApplication.primaryScreen()
                qgis_geometry = qgis_screen.availableGeometry()

            # Calculate window size: 75% width, full available height
            available_rect = qgis_screen.availableGeometry()
            window_width = int(available_rect.width() * 0.75)
            window_height = available_rect.height()

            # Calculate center position
            x = available_rect.x() + (available_rect.width() - window_width) // 2
            y = available_rect.y()

            # Set window geometry
            self.setGeometry(x, y, window_width, window_height)


        except Exception as e:
            log_warning(f"Failed to setup window geometry: {e}")
            # Fallback to default behavior
            pass