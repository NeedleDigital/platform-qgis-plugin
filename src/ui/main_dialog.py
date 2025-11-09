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
    DynamicSearchFilterWidget, SearchableStaticFilterWidget,
    LoginDialog, LayerOptionsDialog, LargeImportWarningDialog, ImportProgressDialog, MessageBar,
    FetchDetailsDialog, PolygonSelectionDialog
)
from ..config.constants import (
    AUSTRALIAN_STATES, CHEMICAL_ELEMENTS, COMPARISON_OPERATORS, UI_CONFIG, DEFAULT_HOLE_TYPES, ROLE_DISPLAY_NAMES,
    ROLE_DESCRIPTIONS, MAX_DISPLAY_RECORDS
)
from ..utils.logging import log_warning, log_error


class DataImporterDialog(QDialog):
    """Main plugin dialog."""
    
    # Signals
    login_requested = pyqtSignal()
    logout_requested = pyqtSignal()
    data_fetch_requested = pyqtSignal(str, dict, bool)  # tab_name, params, fetch_all
    data_clear_requested = pyqtSignal(str)  # tab_name
    data_import_requested = pyqtSignal(str, str, object, object, float, object, object, object)  # tab_name, layer_name, color, trace_config, point_size, collar_name, trace_name, trace_scale
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
        
        # State filter (common to both tabs) - using SearchableStaticFilterWidget for better UX
        state_filter = SearchableStaticFilterWidget(show_all_chips=True, show_search_icon=False, read_only=True)
        # Set static data for searching (list of Australian states)
        state_data = list(AUSTRALIAN_STATES)
        state_filter.setStaticData(state_data)
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
            company_filter.search_box.setPlaceholderText("Type to search companies like BHP, Rio Tinto, Fortescue Metals etc.")
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
            max_depth_input.setTextMargins(4,2,4,2)
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
                        max_depth_input.setStyleSheet(self._get_error_styling())
                        max_depth_input.setToolTip("Depth cannot be negative")
                    else:
                        max_depth_input.setStyleSheet("")
                        max_depth_input.setToolTip("")
                except ValueError:
                    max_depth_input.setStyleSheet(self._get_error_styling())
                    max_depth_input.setToolTip("Please enter a valid numeric value")

            max_depth_input.textChanged.connect(on_depth_text_changed)

            # Add max depth input to its container
            max_depth_container_layout.addWidget(max_depth_input)

            # Add the container to the main layout with 1 part of the ratio
            hole_depth_layout.addWidget(max_depth_container, 1)


            controls_layout.addRow("Hole Type & Depth:", hole_depth_layout)
            widgets['max_depth_input'] = max_depth_input

            # Record count controls with bounding box
            count_input = QLineEdit("100")
            count_input.setTextMargins(4,1,4,1)
            # Add validator for positive integers only
            count_input.setValidator(QIntValidator(1, 999999999, count_input))
            # Connect to role-based validation
            count_input.textChanged.connect(lambda: self._validate_record_count(count_input, "Holes"))

            # Bounding box button
            bbox_button = QPushButton("📍 Select Area ")
            bbox_button.setToolTip("Draw a bounding box on the map to filter by geographic area")
            bbox_button.setMaximumWidth(110)
            # Theme-aware styling applied in _apply_theme_aware_styling()
            bbox_button.clicked.connect(lambda: self._handle_bbox_selection("Holes"))

            # Bounding box indicator/clear button
            bbox_indicator = QLabel("")
            bbox_indicator.setVisible(False)
            # Theme-aware styling applied in _apply_theme_aware_styling()

            bbox_clear_button = QPushButton("✕")
            bbox_clear_button.setToolTip("Clear bounding box selection")
            bbox_clear_button.setMaximumWidth(25)
            bbox_clear_button.setMaximumHeight(25)
            # Theme-aware styling applied in _apply_theme_aware_styling()
            bbox_clear_button.setVisible(False)
            bbox_clear_button.clicked.connect(lambda: self._clear_bbox_selection("Holes"))

            records_layout = QHBoxLayout()
            records_layout.addWidget(count_input)
            records_layout.addSpacing(10)
            records_layout.addWidget(bbox_button)
            records_layout.addSpacing(10)
            records_layout.addWidget(bbox_indicator)
            records_layout.addWidget(bbox_clear_button)
            records_layout.addStretch()
            controls_layout.addRow("No. of Records:", records_layout)

            widgets.update({
                'count_input': count_input,
                'bbox_button': bbox_button,
                'bbox_indicator': bbox_indicator,
                'bbox_clear_button': bbox_clear_button,
                'selected_bbox': None  # Store selected bounding box
            })

            # Fetch button
            fetch_button = QPushButton("Fetch Holes Data")
            fetch_button.setDefault(False)
            fetch_button.setAutoDefault(False)
            fetch_button.setContentsMargins(0, 4, 0, 0)
            controls_layout.addRow("", fetch_button)
            widgets['fetch_button'] = fetch_button
            
        elif tab_type == "Assays":
            # Element filter
            element_input = QComboBox()
            for display_name, symbol in CHEMICAL_ELEMENTS:
                element_input.addItem(display_name, symbol)

            # Set Copper as default selected element
            copper_index = next((i for i, (name, symbol) in enumerate(CHEMICAL_ELEMENTS) if symbol == 'cu'), 0)
            element_input.setCurrentIndex(copper_index)

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
                    value_input.setStyleSheet(self._get_error_styling())
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

            # Hole Type filter with From Depth and To Depth (in same row)
            hole_depth_assays_layout = QHBoxLayout()
            hole_depth_assays_layout.setSpacing(10)
            
            hole_depth_assays_layout.setAlignment(Qt.AlignTop)
            
            # Hole Type container (takes 2/3 of space)
            hole_type_container_assays = QWidget()
            hole_type_container_layout_assays = QVBoxLayout(hole_type_container_assays)
            hole_type_container_layout_assays.setContentsMargins(0, 0, 0, 0)
            hole_type_container_layout_assays.setAlignment(Qt.AlignTop)
            hole_type_container_layout_assays.addWidget(hole_type_filter)
            hole_depth_assays_layout.addWidget(hole_type_container_assays, 2)

            # From Depth input (takes 1/6 of space)
            from_depth_container = QWidget()
            from_depth_container_layout = QVBoxLayout(from_depth_container)
            from_depth_container_layout.setContentsMargins(0, 0, 0, 0)
            from_depth_container_layout.setSpacing(2)
            from_depth_container_layout.setAlignment(Qt.AlignTop)
            from_depth_input = QLineEdit()
            from_depth_input.setPlaceholderText("From Depth (m):")
            from_depth_input.setTextMargins(4,2,4,2)
            from_depth_input.setValidator(QIntValidator(0, 999999, from_depth_input))
            from_depth_container_layout.addWidget(from_depth_input)
            hole_depth_assays_layout.addWidget(from_depth_container, 1)

            # To Depth input (takes 1/6 of space)
            to_depth_container = QWidget()
            to_depth_container_layout = QVBoxLayout(to_depth_container)
            to_depth_container_layout.setContentsMargins(0, 0, 0, 0)
            to_depth_container_layout.setSpacing(2)
            to_depth_container_layout.setAlignment(Qt.AlignTop)

            to_depth_input = QLineEdit()
            to_depth_input.setTextMargins(4,2,4,2)
            to_depth_input.setPlaceholderText("To Depth (m):")
            to_depth_input.setValidator(QIntValidator(0, 999999, to_depth_input))
            to_depth_container_layout.addWidget(to_depth_input)
            hole_depth_assays_layout.addWidget(to_depth_container, 1)

            controls_layout.addRow("Hole Type & Depth:", hole_depth_assays_layout)
            widgets['from_depth_input'] = from_depth_input
            widgets['to_depth_input'] = to_depth_input

            # Company filter (separate row with container for proper alignment)
            company_filter = DynamicSearchFilterWidget()
            company_filter.search_box.setPlaceholderText("Type to search companies like BHP, Rio Tinto, Fortescue Metals etc.")
            company_filter_container = QWidget()
            company_filter_container_layout = QVBoxLayout(company_filter_container)
            company_filter_container_layout.setContentsMargins(0, 0, 0, 0)
            company_filter_container_layout.setAlignment(Qt.AlignTop)
            company_filter_container_layout.addWidget(company_filter)
            controls_layout.addRow("Company Name(s):", company_filter_container)
            widgets['company_filter'] = company_filter

            # Record count controls with bounding box
            count_input = QLineEdit("100")
            count_input.setTextMargins(4,1,4,1)
            # Add validator for positive integers only
            count_input.setValidator(QIntValidator(1, 999999999, count_input))
            # Connect to role-based validation
            count_input.textChanged.connect(lambda: self._validate_record_count(count_input, "Assays"))

            # Bounding box button
            bbox_button = QPushButton("📍 Select Area ")
            bbox_button.setToolTip("Draw a bounding box on the map to filter by geographic area")
            bbox_button.setMaximumWidth(110)
            # Theme-aware styling applied in _apply_theme_aware_styling()
            bbox_button.clicked.connect(lambda: self._handle_bbox_selection("Assays"))

            # Bounding box indicator/clear button
            bbox_indicator = QLabel("")
            bbox_indicator.setVisible(False)
            # Theme-aware styling applied in _apply_theme_aware_styling()

            bbox_clear_button = QPushButton("✕")
            bbox_clear_button.setToolTip("Clear bounding box selection")
            bbox_clear_button.setMaximumWidth(25)
            bbox_clear_button.setMaximumHeight(25)
            # Theme-aware styling applied in _apply_theme_aware_styling()
            bbox_clear_button.setVisible(False)
            bbox_clear_button.clicked.connect(lambda: self._clear_bbox_selection("Assays"))

            records_layout = QHBoxLayout()
            records_layout.addWidget(count_input)
            records_layout.addSpacing(10)
            records_layout.addWidget(bbox_button)
            records_layout.addSpacing(10)
            records_layout.addWidget(bbox_indicator)
            records_layout.addWidget(bbox_clear_button)
            records_layout.addStretch()
            controls_layout.addRow("No. of Records:", records_layout)

            widgets.update({
                'count_input': count_input,
                'bbox_button': bbox_button,
                'bbox_indicator': bbox_indicator,
                'bbox_clear_button': bbox_clear_button,
                'selected_bbox': None  # Store selected bounding box
            })

            # Fetch button
            fetch_button = QPushButton("Fetch Assay Data")
            fetch_button.setDefault(False)
            fetch_button.setAutoDefault(False)
            fetch_button.setContentsMargins(0, 4, 0, 0)
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
        loading_label = QLabel("Loading data...")
        loading_label.setAlignment(Qt.AlignCenter)
        font = loading_label.font()
        font.setPointSize(12)
        loading_label.setFont(font)

        # No data label - only shown after API call returns 0 results
        no_data_label = QLabel("No data present with given filters.")
        no_data_label.setAlignment(Qt.AlignCenter)
        no_data_font = no_data_label.font()
        no_data_font.setPointSize(13)
        no_data_label.setFont(no_data_font)
        # Theme-aware styling applied in _apply_theme_aware_styling()

        # Empty placeholder - shown initially and after reset (no message)
        empty_placeholder = QLabel("")
        empty_placeholder.setAlignment(Qt.AlignCenter)

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
        content_stack.addWidget(empty_placeholder)
        content_stack.addWidget(location_widget)
        content_stack.setCurrentWidget(empty_placeholder)  # Show empty placeholder initially

        layout.addLayout(content_stack)

        widgets.update({
            'table': table,
            'loading_label': loading_label,
            'no_data_label': no_data_label,
            'empty_placeholder': empty_placeholder,
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

        # Create "View Details" button - small and compact
        self.view_details_button = QPushButton("View Details")
        self.view_details_button.setDefault(False)
        self.view_details_button.setAutoDefault(False)
        self.view_details_button.setVisible(False)  # Hidden by default, shown after successful fetch
        self.view_details_button.setMaximumWidth(90)
        self.view_details_button.setMaximumHeight(22)

        # Create cancel button
        self.cancel_button = QPushButton("Cancel Request")
        self.cancel_button.setDefault(False)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.setVisible(False)  # Hidden by default

        # Style will be applied by _apply_theme_aware_styling() method

        status_layout.addWidget(self.status_label)
        status_layout.addSpacing(12)  # 12px spacing between status and button
        status_layout.addWidget(self.view_details_button)
        status_layout.addStretch()  # Push everything else to the right
        status_layout.addWidget(self.progress_bar, 1)  # Stretch factor 1 - takes available space
        status_layout.addWidget(self.cancel_button)

        self.main_layout.addLayout(status_layout)
    
    def _connect_signals(self):
        """Connect UI signals."""
        # Header buttons
        self.login_button.clicked.connect(self._handle_login_button)
        self.reset_all_button.clicked.connect(self._handle_reset_all)

        # View Details button
        self.view_details_button.clicked.connect(self._handle_view_details)

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

            # Add depth range parameters if specified
            from_depth = tab_widgets['from_depth_input'].text().strip()
            to_depth = tab_widgets['to_depth_input'].text().strip()
            if from_depth:
                try:
                    params['from_depth'] = int(from_depth)
                except ValueError:
                    pass  # Skip if invalid
            if to_depth:
                try:
                    params['to_depth'] = int(to_depth)
                except ValueError:
                    pass  # Skip if invalid

            # Add companies parameter if specified (same as Holes section)
            companies = tab_widgets['company_filter'].currentData()
            if companies:
                params['companies'] = ",".join(companies)
        
        # Get requested record count
        try:
            requested_count = int(tab_widgets['count_input'].text() or "100")
            params['requested_count'] = requested_count
        except ValueError:
            requested_count = 100
            params['requested_count'] = requested_count

        # Add polygon coordinates if selected
        selected_polygon = tab_widgets.get('selected_bbox')  # Still stored as 'selected_bbox' key
        if selected_polygon and 'coords' in selected_polygon:
            # Store polygon coords as list for special handling in API client
            params['polygon_coords'] = selected_polygon['coords']

        # Emit request signal (fetch_all is always False now)
        self.data_fetch_requested.emit(tab_name, params, False)
    
    
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
        try:
            requested_count = int(tab_widgets['count_input'].text() or "100")
            name_parts.append(f"{requested_count}rec")
        except ValueError:
            name_parts.append("100rec")

        # Join parts with underscores and limit total length
        layer_name = "_".join(name_parts)

        # Limit total length to avoid overly long names
        if len(layer_name) > 50:
            layer_name = layer_name[:47] + "..."

        return layer_name

    def _handle_import_request(self, tab_name: str):
        """Handle data import request."""
        # Detect if this is assay data
        is_assay_data = self._is_assay_data(tab_name)

        # Show layer options dialog with dynamic default name
        default_name = self._generate_dynamic_layer_name(tab_name)
        options_dialog = LayerOptionsDialog(default_name, is_assay_data, self)

        if options_dialog.exec_() == QDialog.Accepted:
            options = options_dialog.get_options()

            # Unpack options based on whether it's assay data
            if is_assay_data:
                group_name, collar_name, trace_name, point_size, color, trace_config, trace_scale = options
                # For assay data, use group name as the "layer_name" for compatibility
                layer_name = group_name
            else:
                layer_name, point_size, color = options
                trace_config = None
                trace_scale = None

            # Emit with all parameters (need to update signal to include point_size)
            self.data_import_requested.emit(tab_name, layer_name, color, trace_config, point_size,
                                           collar_name if is_assay_data else None,
                                           trace_name if is_assay_data else None,
                                           trace_scale if is_assay_data else None)

    def _is_assay_data(self, tab_name: str) -> bool:
        """Check if the current tab contains assay data."""
        # Simple check: Assays tab contains assay data
        return tab_name == "Assays"

    def _handle_view_details(self):
        """Handle View Details button click - show fetch details dialog."""
        if not self.data_manager:
            return

        # Get current tab
        current_tab_index = self.tabs.currentIndex()
        tab_name = "Holes" if current_tab_index == 0 else "Assays"

        # Get fetch details from data manager
        fetch_details = self.data_manager.get_fetch_details(tab_name)

        if not fetch_details:
            self.show_info("No fetch details available. Please fetch data first.")
            return

        # Show the fetch details dialog
        details_dialog = FetchDetailsDialog(fetch_details, self)
        details_dialog.exec_()

    def _handle_bbox_selection(self, tab_name: str):
        """Handle polygon selection button click - show map dialog."""
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab

        # Get existing polygon if any
        existing_polygon = tab_widgets.get('selected_bbox')  # Still stored as 'selected_bbox' key for now

        # Show map dialog
        polygon_dialog = PolygonSelectionDialog(self, existing_polygon)

        if polygon_dialog.exec_() == QDialog.Accepted:
            # Get selected polygon
            selected_polygon = polygon_dialog.get_polygon()

            if selected_polygon:
                # Store in tab widgets
                tab_widgets['selected_bbox'] = selected_polygon

                # Update indicator to show polygon is active
                tab_widgets['bbox_indicator'].setText("📍 Bounding Box")
                tab_widgets['bbox_indicator'].setVisible(True)
                tab_widgets['bbox_clear_button'].setVisible(True)

    def _clear_bbox_selection(self, tab_name: str):
        """Clear bounding box selection for a tab."""
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab

        # Clear stored bounding box
        tab_widgets['selected_bbox'] = None

        # Hide indicator and clear button
        tab_widgets['bbox_indicator'].setVisible(False)
        tab_widgets['bbox_clear_button'].setVisible(False)

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

        # Detect theme
        palette = QApplication.palette()
        window_color = palette.color(palette.Window)
        is_dark_theme = window_color.lightness() < 128

        # Apply role-specific styling with theme awareness
        if role == "tier_1":
            # Free Trial - Blue style adapted for theme
            if is_dark_theme:
                self.role_badge.setStyleSheet("""
                    QPushButton {
                        background-color: #1565C0;
                        color: #E3F2FD;
                        border: 1px solid #42A5F5;
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-weight: bold;
                        font-size: 10px;
                        max-height: 18px;
                    }
                    QPushButton:hover {
                        background-color: #1976D2;
                        border-color: #64B5F6;
                    }
                    QPushButton:pressed {
                        background-color: #0D47A1;
                    }
                """)
            else:
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
            # Premium - Gold/amber style adapted for theme
            if is_dark_theme:
                self.role_badge.setStyleSheet("""
                    QPushButton {
                        background-color: #E65100;
                        color: #FFF3E0;
                        border: 1px solid #FF9800;
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-weight: bold;
                        font-size: 10px;
                        max-height: 18px;
                    }
                    QPushButton:hover {
                        background-color: #F57C00;
                        border-color: #FFB74D;
                    }
                    QPushButton:pressed {
                        background-color: #BF360C;
                    }
                """)
            else:
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
            # Admin - Purple style adapted for theme
            if is_dark_theme:
                self.role_badge.setStyleSheet("""
                    QPushButton {
                        background-color: #6A1B9A;
                        color: #F3E5F5;
                        border: 1px solid #AB47BC;
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-weight: bold;
                        font-size: 10px;
                        max-height: 18px;
                    }
                    QPushButton:hover {
                        background-color: #7B1FA2;
                        border-color: #BA68C8;
                    }
                    QPushButton:pressed {
                        background-color: #4A148C;
                    }
                """)
            else:
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
        """Validate record count input - max 1000 for tier_1, max 1M for tier_2/admin."""
        # Get the current text
        text = count_input.text().strip()

        # If empty or being edited, allow it
        if not text:
            count_input.setStyleSheet("")
            return

        # Try to parse the value
        try:
            value = int(text)

            # Check if user is authenticated
            if self.data_manager and self.data_manager.is_authenticated():
                role = self.data_manager.api_client.get_user_role()

                # Check 1M limit for all users
                if value > 1000000:
                    # Show error styling
                    count_input.setStyleSheet(self._get_error_styling())

                    # Reset to 1M
                    count_input.blockSignals(True)
                    count_input.setText("1000000")
                    count_input.blockSignals(False)

                    # Show message
                    self.show_info(
                        "Maximum Record Limit Exceeded\n\n"
                        "1,000,000 is the maximum number of records that can be fetched at once.\n\n"
                        "Your entry has been adjusted to 1,000,000 records."
                    )

                    # Clear error styling
                    count_input.setStyleSheet("")
                # Check tier_1 limit (1000 records)
                elif role == "tier_1" and value > 1000:
                    # Show error styling
                    count_input.setStyleSheet(self._get_error_styling())

                    # Reset to 1000
                    count_input.blockSignals(True)
                    count_input.setText("1000")
                    count_input.blockSignals(False)

                    # Show message
                    self.show_info(
                        "Free Trial Record Limit Exceeded\n\n"
                        "As a Free Trial user, you can fetch a maximum of 1,000 records at a time.\n\n"
                        "Your entry has been adjusted to 1,000 records.\n\n"
                        "Upgrade to Premium for unlimited record fetching!"
                    )

                    # Clear error styling
                    count_input.setStyleSheet("")
                else:
                    # Valid input, clear any error styling
                    count_input.setStyleSheet("")
            else:
                # Not logged in, still enforce 1M limit
                if value > 1000000:
                    count_input.setStyleSheet(self._get_error_styling())
                    count_input.blockSignals(True)
                    count_input.setText("1000000")
                    count_input.blockSignals(False)
                    self.show_info(
                        "Maximum Record Limit Exceeded\n\n"
                        "1,000,000 is the maximum number of records that can be fetched at once.\n\n"
                        "Your entry has been adjusted to 1,000,000 records."
                    )
                    count_input.setStyleSheet("")
                else:
                    count_input.setStyleSheet("")

        except ValueError:
            # Invalid number, but let the QIntValidator handle it
            pass

    def set_data_manager(self, data_manager):
        """Set the data manager reference for role checks."""
        self.data_manager = data_manager

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
        else:
            self.login_button.setText("Login")
            self.reset_all_button.setVisible(False)
            self.status_label.setText(UI_CONFIG['status_messages']['ready'])

            # Hide role badge after logout
            self.role_badge.setVisible(False)
    
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

        if data:
            # Data is already limited to MAX_DISPLAY_RECORDS (1000) from data_manager
            # No need to slice again - just paginate through it
            records_per_page = 100
            current_page = pagination_info.get('current_page', 1)
            start_idx = (current_page - 1) * records_per_page
            end_idx = min(start_idx + records_per_page, len(data))
            page_data = data[start_idx:end_idx]

            # Enhanced table display with better UX
            table.setRowCount(len(page_data))
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)

            # Create mapping from formatted headers back to original column names
            # Formatted: "Hole Id" -> Original: "hole_id"
            header_to_original = {
                header: header.lower().replace(' ', '_')
                for header in headers
            }

            # Enhanced population with N/A for nulls and tooltips
            for row_idx, record in enumerate(page_data):
                for col_idx, header in enumerate(headers):
                    # Use original column name to access data
                    original_key = header_to_original[header]
                    value = record.get(original_key, '')

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

            # Show "View Details" button when data is successfully loaded
            self.view_details_button.setVisible(True)

            # Update pagination
            prev_button = tab_widgets['prev_button']
            next_button = tab_widgets['next_button']
            
            if pagination_info['has_data'] and pagination_info['total_pages'] > 1:
                pagination_widget.setVisible(True)
                page_text = f"Page {pagination_info['current_page']} of {pagination_info['total_pages']}"

                # Add display limit info if applicable
                total_records = pagination_info.get('total_records', 0)
                display_count = pagination_info.get('display_count', 0)
                if total_records > display_count:
                    page_text += f" (showing first {display_count:,} rows)\n    Total rows fetched: {total_records:,}"
                else:
                    page_text += f" (showing {total_records:,} records)"

                page_label.setText(page_text)
                page_label.setAlignment(Qt.AlignCenter)

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

            # Hide "View Details" button when no data
            self.view_details_button.setVisible(False)

            if is_reset_operation:
                # Reset operation - show empty placeholder (no message)
                empty_placeholder = tab_widgets['empty_placeholder']
                content_stack.setCurrentWidget(empty_placeholder)
                import_button.setVisible(False)
                pagination_widget.setVisible(False)
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

        # Hide View Details button during loading/streaming
        self.view_details_button.setVisible(False)

        # Hide other components during loading
        import_button.setVisible(False)
        pagination_widget.setVisible(False)

        # Disable fetch button to prevent multiple requests
        fetch_button.setEnabled(False)

        # Disable all UI controls during loading for this specific tab
        self._disable_all_controls(tab_name)
    
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

        # Restore loading label text for next use
        loading_label.setText("Loading data...")

        # Only show empty placeholder if there's no data in the table AND no data has been fetched yet
        # If show_data has been called with empty results, it will have set the appropriate view
        table = tab_widgets['table']
        if table.rowCount() == 0:
            # Check if we're currently showing the no_data_label, if so don't override it
            current_widget = content_stack.currentWidget()
            no_data_label = tab_widgets['no_data_label']
            empty_placeholder = tab_widgets['empty_placeholder']
            if current_widget != no_data_label:
                # Show empty placeholder (no message) instead of "Waiting for data..."
                content_stack.setCurrentWidget(empty_placeholder)

        # Re-enable all UI controls after loading
        self._enable_all_controls()
    
    def _disable_all_controls(self, tab_name: str):
        """Disable all UI controls during API requests except cancel button for the specified tab."""
        # Disable tab switching
        self.tabs.setEnabled(False)

        # Disable header buttons
        self.login_button.setEnabled(False)
        self.reset_all_button.setEnabled(False)

        # Disable controls only for the specified tab
        tab_widgets = self.holes_tab if tab_name == "Holes" else self.assays_tab

        # Disable filter controls
        tab_widgets['state_filter'].setEnabled(False)
        tab_widgets['hole_type_filter'].setEnabled(False)

        if tab_name == "Holes":
            tab_widgets['company_filter'].setEnabled(False)
            tab_widgets['max_depth_input'].setEnabled(False)
            tab_widgets['count_input'].setEnabled(False)
        else:  # Assays
            tab_widgets['element_input'].setEnabled(False)
            tab_widgets['operator_input'].setEnabled(False)
            tab_widgets['value_input'].setEnabled(False)
            tab_widgets['from_depth_input'].setEnabled(False)
            tab_widgets['to_depth_input'].setEnabled(False)
            tab_widgets['company_filter'].setEnabled(False)
            tab_widgets['count_input'].setEnabled(False)

        # Disable bounding box buttons
        tab_widgets['bbox_button'].setEnabled(False)
        tab_widgets['bbox_clear_button'].setEnabled(False)

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
                tab_widgets['count_input'].setEnabled(True)
            else:  # Assays
                tab_widgets['element_input'].setEnabled(True)
                tab_widgets['operator_input'].setEnabled(True)
                # Check if value input should be enabled based on operator
                operator_text = tab_widgets['operator_input'].currentText()
                tab_widgets['value_input'].setEnabled(operator_text != "None")
                tab_widgets['from_depth_input'].setEnabled(True)
                tab_widgets['to_depth_input'].setEnabled(True)
                tab_widgets['company_filter'].setEnabled(True)
                tab_widgets['count_input'].setEnabled(True)

            # Re-enable bounding box buttons
            tab_widgets['bbox_button'].setEnabled(True)
            tab_widgets['bbox_clear_button'].setEnabled(True)

            # Note: fetch buttons are handled individually in hide_loading()
            # Note: pagination and import buttons are handled by show_data() based on data availability
    
    def _reset_all_filters(self):
        """Reset all filter inputs to their default values."""
        # Reset Holes tab filters
        holes_tab = self.holes_tab
        
        # Reset state filter to "All States" (first item, empty value)
        holes_tab['state_filter'].setCurrentData([""])
        # Clear any leftover text in states filter search box
        if hasattr(holes_tab['state_filter'], 'search_box'):
            holes_tab['state_filter'].search_box.clear()

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

        # Reset record count
        holes_tab['count_input'].setText("100")

        # Clear bounding box selection for Holes
        self._clear_bbox_selection("Holes")

        # Reset Assays tab filters
        assays_tab = self.assays_tab

        # Reset state filter to "All States" (first item, empty value)
        assays_tab['state_filter'].setCurrentData([""])
        # Clear any leftover text in states filter search box
        if hasattr(assays_tab['state_filter'], 'search_box'):
            assays_tab['state_filter'].search_box.clear()

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

        # Reset depth inputs
        assays_tab['from_depth_input'].clear()
        assays_tab['to_depth_input'].clear()

        # Reset record count
        assays_tab['count_input'].setText("100")

        # Clear bounding box selection for Assays
        self._clear_bbox_selection("Assays")

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
            # Hide loading indicator
            if hasattr(self.holes_tab['company_filter'], 'hide_loading'):
                self.holes_tab['company_filter'].hide_loading()
            # Show results popup
            if hasattr(self.holes_tab['company_filter'], 'showPopup'):
                self.holes_tab['company_filter'].showPopup(results)
        else:  # Assays
            # Hide loading indicator
            if hasattr(self.assays_tab['company_filter'], 'hide_loading'):
                self.assays_tab['company_filter'].hide_loading()
            # Show results popup
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
                danger_bg = "#D75A5A"       # Soft dusty rose
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

            # View Details button - small and compact
            self.view_details_button.setStyleSheet(secondary_style + """
                QPushButton {
                    font-size: 10px;
                    padding: 2px 8px;
                    min-height: 20px;
                    max-height: 22px;
                }
            """)

            # Bounding box buttons - Select Area and Clear Box
            disabled_bg = "#2A2A2A" if is_dark_theme else "#CCCCCC"
            disabled_text = "#555555" if is_dark_theme else "#666666"
            disabled_border = "#444444" if is_dark_theme else "#BBBBBB"

            bbox_button_style = """
                QPushButton {{
                    background-color: {bg_color};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: normal;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                    border: 1px solid {hover_border};
                }}
                QPushButton:pressed {{
                    background-color: {pressed_bg};
                }}
                QPushButton:disabled {{
                    background-color: {disabled_bg};
                    color: {disabled_text};
                    border: 1px solid {disabled_border};
                }}
            """.format(
                bg_color=primary_bg,
                text_color=primary_text,
                border_color=border_color,
                hover_bg=adjust_color_brightness(primary_bg, 1.2),
                hover_border=adjust_color_brightness(border_color, 1.3),
                pressed_bg=adjust_color_brightness(primary_bg, 0.8),
                disabled_bg=disabled_bg,
                disabled_text=disabled_text,
                disabled_border=disabled_border
            )

            # Apply to bounding box buttons in both tabs
            self.holes_tab['bbox_button'].setStyleSheet(bbox_button_style)
            self.holes_tab['bbox_clear_button'].setStyleSheet(bbox_button_style)
            self.assays_tab['bbox_button'].setStyleSheet(bbox_button_style)
            self.assays_tab['bbox_clear_button'].setStyleSheet(bbox_button_style)

            # No data labels - use theme-appropriate text color
            label_text_color = "#FFFFFF" if is_dark_theme else "#000000"
            no_data_label_style = f"color: {label_text_color}; font-style: italic;"
            self.holes_tab['no_data_label'].setStyleSheet(no_data_label_style)
            self.assays_tab['no_data_label'].setStyleSheet(no_data_label_style)

            # Loading labels - use theme-appropriate text color
            loading_label_style = f"color: {label_text_color}; font-style: italic;"
            self.holes_tab['loading_label'].setStyleSheet(loading_label_style)
            self.assays_tab['loading_label'].setStyleSheet(loading_label_style)

            # Bounding box indicators - use theme-aware green styling
            bbox_indicator_bg = "#2E7D32" if is_dark_theme else "#4CAF50"
            bbox_indicator_text = "#E8F5E9"
            bbox_indicator_style = (
                f"padding: 4px 8px; background-color: {bbox_indicator_bg}; "
                f"color: {bbox_indicator_text}; border-radius: 3px; "
                f"font-size: 10px; font-weight: bold;"
            )
            self.holes_tab['bbox_indicator'].setStyleSheet(bbox_indicator_style)
            self.assays_tab['bbox_indicator'].setStyleSheet(bbox_indicator_style)

            # QComboBox styling - apply to all combo boxes for consistent theme-aware text
            combobox_style = self._get_combobox_styling()
            # Apply to Assays tab dropdowns
            self.assays_tab['element_input'].setStyleSheet(combobox_style)
            self.assays_tab['operator_input'].setStyleSheet(combobox_style)


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
                          self.cancel_button, self.view_details_button]:
                button.setStyleSheet(basic_style)

    def _get_error_styling(self) -> str:
        """Get theme-aware error styling for input fields."""
        try:
            palette = QApplication.palette()
            window_color = palette.color(palette.Window)
            is_dark_theme = window_color.lightness() < 128

            if is_dark_theme:
                # Dark theme - brighter error colors for visibility
                return "border: 2px solid #f44336; background-color: #5D2424;"
            else:
                # Light theme - lighter error colors
                return "border: 2px solid #f44336; background-color: #ffebee;"
        except Exception as e:
            log_warning(f"Failed to get theme-aware error styling: {e}")
            # Fallback to light theme style
            return "border: 2px solid #f44336; background-color: #ffebee;"

    def _get_combobox_styling(self) -> str:
        """Get theme-aware styling for QComboBox dropdowns."""
        try:
            palette = QApplication.palette()
            window_color = palette.color(palette.Window)
            is_dark_theme = window_color.lightness() < 128

            if is_dark_theme:
                # Dark theme - ensure text is visible with dropdown arrow
                return """
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
                # Light theme - ensure text is visible with dropdown arrow
                return """
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
        except Exception as e:
            log_warning(f"Failed to get theme-aware combobox styling: {e}")
            # Fallback - minimal styling that should work in most themes
            return ""

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