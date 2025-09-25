"""
ND Data Importer - Main Plugin Class

A QGIS plugin for importing Australian mining drill hole and assay data.
This plugin provides seamless access to Australia's comprehensive mining database,
allowing geologists, mining engineers, and researchers to import drill hole and
assay data directly into QGIS for spatial analysis and visualization.

Main Features:
    - State-wise data filtering for Australian territories
    - Company-specific data search and filtering
    - Chemical element analysis for assay data
    - Large dataset optimization (supports 1M+ records)
    - Automatic OpenStreetMap base layer integration
    - Chunked processing with progress tracking
    - Memory management for performance

Author: Needle Digital
Contact: divyansh@needle-digital.com
License: GPL-3.0+
"""

import os
from qgis.PyQt.QtCore import QTranslator, QCoreApplication, qVersion
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import Qgis

# Import modular components for clean architecture
from .src.core.data_manager import DataManager  # Core business logic and API communication
from .src.ui.main_dialog import DataImporterDialog  # Main UI dialog window
from .src.ui.components import (  # Reusable UI components and dialogs
    LoginDialog, LayerOptionsDialog, LargeImportWarningDialog, ImportProgressDialog
)
from .src.utils.qgis_helpers import QGISLayerManager  # QGIS integration utilities
from .src.utils.logging import log_error, log_warning  # Centralized logging system
from .src.config.constants import (  # Configuration constants and thresholds
    PLUGIN_NAME, PLUGIN_VERSION, LARGE_IMPORT_WARNING_THRESHOLD,
    LARGE_IMPORT_WARNING_THRESHOLD_LOCATION_ONLY, PARTIAL_IMPORT_LIMIT,
    PARTIAL_IMPORT_LIMIT_LOCATION_ONLY, CHUNKED_IMPORT_THRESHOLD
)


class DataImporter:
    """Main plugin class for ND Data Importer.
    
    This class serves as the entry point for the QGIS plugin and handles:
    - Plugin initialization and lifecycle management
    - QGIS interface integration (toolbar, menus)
    - Coordination between UI components and business logic
    - Signal/slot connections for event handling
    - Dialog management and user interactions
    
    The class follows QGIS plugin architecture patterns and implements
    the standard plugin interface expected by QGIS.
    
    Attributes:
        iface (QgisInterface): Reference to QGIS interface
        plugin_dir (str): Path to plugin directory
        actions (list): List of QAction objects for cleanup
        menu (str): Plugin menu name
        data_manager (DataManager): Core business logic handler
        layer_manager (QGISLayerManager): QGIS layer management utilities
        dlg (DataImporterDialog): Main plugin dialog window
        login_dlg (LoginDialog): Authentication dialog window
    """

    def __init__(self, iface):
        """
        Initialize the plugin.
        
        Args:
            iface: A reference to the QgisInterface
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        # Initialize locale - handle different QGIS versions robustly
        locale = 'en'  # Default fallback
        try:
            # Try QLocale first (most reliable)
            from qgis.PyQt.QtCore import QLocale
            locale = QLocale().name()[:2]
        except (ImportError, AttributeError):
            try:
                # Try QCoreApplication as fallback
                locale = QCoreApplication.locale().name()[:2]
            except (AttributeError, TypeError):
                # Use system locale as last resort
                import locale as sys_locale
                try:
                    locale = sys_locale.getdefaultlocale()[0][:2] if sys_locale.getdefaultlocale()[0] else 'en'
                except:
                    locale = 'en'

        # Initialize components
        self.actions = []
        self.menu = self.tr(u'&Needle Digital Tools')
        
        # Core components
        self.data_manager = None
        self.layer_manager = None
        self.dlg = None
        self.login_dlg = None
        

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('DataImporter', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                  add_to_menu=True, add_to_toolbar=True, status_tip=None,
                  whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Add to plugin toolbar if it exists
            if hasattr(self.iface, 'addPluginToMenu'):
                self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        
        self.add_action(
            icon_path,
            text=self.tr(u'Mining Data Importer'),
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip=self.tr(u'Import Australian mining drill hole data'),
            whats_this=self.tr(u'Import Australian mining drill hole and assay data into QGIS')
        )

    def unload(self):
        """Remove the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&Needle Digital Tools'), action)
            self.iface.removeToolBarIcon(action)
        
        # Clean up
        if self.dlg:
            self.dlg.close()
        if self.login_dlg:
            self.login_dlg.close()
        

    def run(self):
        """Run method that loads and shows the plugin dialog."""
        try:
            # Initialize components if not already done
            self._initialize_components()
            
            # Complete API client initialization (safe to make network calls now)
            self.data_manager.api_client.complete_initialization()
            
            # Show the dialog and bring it to front
            self.dlg.show_and_raise()
            
            # Update UI based on authentication status
            is_authenticated = self.data_manager.is_authenticated()
            self.dlg.update_login_status(is_authenticated)
            
            
        except Exception as e:
            error_msg = f"Failed to open plugin: {str(e)}"
            log_error(error_msg)
            # Show error message in plugin dialog if available
            if self.dlg:
                self.dlg.show_plugin_message(error_msg, "error", 5000)

    def _initialize_components(self):
        """Initialize plugin components."""
        if not self.data_manager:
            # Initialize data manager
            self.data_manager = DataManager()
            
            # Initialize layer manager
            self.layer_manager = QGISLayerManager(self.iface)
            
            # Initialize main dialog
            self.dlg = DataImporterDialog()
            self._connect_dialog_signals()
            

    def _connect_dialog_signals(self):
        """Connect dialog signals to handlers."""
        # Authentication
        self.dlg.login_requested.connect(self._handle_login_request)
        self.dlg.logout_requested.connect(self._handle_logout_request)
        
        # Data operations
        self.dlg.data_fetch_requested.connect(self._handle_data_fetch_request)
        self.dlg.data_clear_requested.connect(self._handle_data_clear_request)
        self.dlg.data_import_requested.connect(self._handle_data_import_request)
        self.dlg.cancel_request_requested.connect(self._handle_cancel_request)
        
        # Pagination operations
        self.dlg.page_next_requested.connect(self._handle_page_next)
        self.dlg.page_previous_requested.connect(self._handle_page_previous)
        
        # Company search operations
        self.dlg.company_search_requested.connect(self._handle_company_search_request)
        
        # Data manager signals
        self.data_manager.status_changed.connect(self.dlg.update_status)
        self.data_manager.progress_changed.connect(self.dlg.update_progress)
        self.data_manager.data_ready.connect(self.dlg.show_data)
        self.data_manager.data_ready.connect(self.dlg.hide_cancel_button)  # Hide cancel button when data ready
        self.data_manager.error_occurred.connect(self.dlg.show_error)
        self.data_manager.error_occurred.connect(self.dlg.hide_cancel_button)  # Hide cancel button on error
        self.data_manager.loading_started.connect(self.dlg.show_loading)  # Show loading state
        self.data_manager.loading_finished.connect(self.dlg.hide_loading)  # Hide loading state
        self.data_manager.companies_search_results.connect(self.dlg.handle_company_search_results)  # Company search results
        
        # API client signals
        self.data_manager.api_client.login_success.connect(self._handle_login_success)
        self.data_manager.api_client.login_failed.connect(self._handle_login_failed)
        
        # Connect to silent login completion for UI updates
        self.data_manager.api_client.login_success.connect(self._update_ui_on_auth_change)
        self.data_manager.api_client.login_failed.connect(self._update_ui_on_auth_change)

    def _handle_login_request(self):
        """Handle login request from dialog."""
        try:
            if not self.login_dlg:
                self.login_dlg = LoginDialog(self.dlg)
                self.login_dlg.login_attempt.connect(self._handle_login_attempt)
            
            # Show login dialog
            if self.login_dlg.exec_() == LoginDialog.Accepted:
                pass
            else:
                pass
                
        except Exception as e:
            error_msg = f"Login dialog error: {str(e)}"
            log_error(error_msg)
            self.dlg.show_error(error_msg)

    def _handle_logout_request(self):
        """Handle logout request from dialog."""
        try:
            self.data_manager.api_client.logout()
            self.dlg.update_login_status(False)
            
            # Clear any existing data
            self.dlg.show_data("Holes", [], [], {'has_data': False, 'current_page': 0, 'total_pages': 0, 'showing_records': 0, 'total_records': 0, 'records_per_page': 100})
            self.dlg.show_data("Assays", [], [], {'has_data': False, 'current_page': 0, 'total_pages': 0, 'showing_records': 0, 'total_records': 0, 'records_per_page': 100})
            
            # Show logout success message in plugin dialog
            if self.dlg:
                self.dlg.show_plugin_message("Logged out successfully", "info", 3000)
            
            
        except Exception as e:
            error_msg = f"Logout error: {str(e)}"
            log_error(error_msg)
            self.dlg.show_error(error_msg)

    def _handle_login_attempt(self, email, password):
        """Handle login attempt."""
        try:
            if not self.login_dlg:
                return
            
            # Update status
            self.dlg.update_status(f"Authenticating {email}...")
            self.dlg.update_progress(50)
            
            # Attempt login
            self.data_manager.api_client.login(email, password)
            
        except Exception as e:
            error_msg = f"Login attempt error: {str(e)}"
            log_error(error_msg)
            if self.login_dlg:
                self.login_dlg.on_login_result(False, error_msg)

    def _handle_login_success(self):
        """Handle successful login."""
        try:
            self.dlg.update_progress(100)
            
            if self.login_dlg:
                self.login_dlg.on_login_result(True, None)
            
            self.dlg.update_login_status(True)
            
            # Show login success message in plugin dialog
            if self.dlg:
                self.dlg.show_plugin_message("Login successful!", "success", 3000)


            
        except Exception as e:
            log_error(f"Login success handler error: {str(e)}")

    def _handle_login_failed(self, error_message):
        """Handle failed login."""
        try:
            self.dlg.update_progress(0)
            self.dlg.update_status("Authentication failed.")
            
            if self.login_dlg:
                self.login_dlg.on_login_result(False, f"Login Failed: {error_message}")
            
            log_warning(f"Login failed: {error_message}")
            
        except Exception as e:
            log_error(f"Login failure handler error: {str(e)}")

    def _update_ui_on_auth_change(self):
        """Update UI when authentication status changes (including silent login)."""
        try:
            if self.dlg:
                is_authenticated = self.data_manager.is_authenticated()
                self.dlg.update_login_status(is_authenticated)
        except Exception as e:
            log_error(f"UI update error: {str(e)}")

    def _handle_data_fetch_request(self, tab_name, params, fetch_all):
        """Handle data fetch request."""
        try:
            self.dlg.show_cancel_button()  # Show cancel button when starting fetch
            self.data_manager.fetch_data(tab_name, params, fetch_all)
            
        except Exception as e:
            error_msg = f"Data fetch error: {str(e)}"
            log_error(error_msg)
            self.dlg.hide_cancel_button()  # Hide cancel button on error
            self.dlg.hide_loading(tab_name)  # Hide loading state on error
            self.dlg.show_error(error_msg)

    def _handle_data_clear_request(self, tab_name):
        """Handle data clear request."""
        try:
            self.data_manager.clear_tab_data(tab_name)
            
        except Exception as e:
            error_msg = f"Data clear error: {str(e)}"
            log_error(error_msg)
            self.dlg.show_error(error_msg)

    def _handle_data_import_request(self, tab_name, layer_name, color):
        """Handle data import request with intelligent large dataset optimization.
        
        This method manages the complete data import workflow including:
        1. Data validation and retrieval
        2. Automatic OpenStreetMap base layer addition
        3. Large dataset detection and user warnings
        4. Performance optimization through chunked processing
        5. Memory management for large imports
        
        Args:
            tab_name (str): Source tab name ('Holes' or 'Assays')
            layer_name (str): Name for the new QGIS layer
            color (QColor): Color for point styling in the layer
            
        The method automatically handles:
        - Small datasets (<5000 records): Direct import
        - Medium datasets (5000-50000 records): Chunked import with progress
        - Large datasets (50000+ records): User warning with import options
        """
        try:
            # Get data from data manager - includes both data rows and column headers
            data, headers = self.data_manager.get_tab_data(tab_name)

            # Check if this is location-only data
            is_location_only = self.data_manager.is_tab_location_only(tab_name)

            # Validate that we have data to import
            if not data:
                self.dlg.show_error("No data available to import.")
                return

            record_count = len(data)

            # Add OpenStreetMap base layer for geographical context
            # This provides users with a reference map to visualize their mining data
            osm_success, osm_message = self.layer_manager.add_osm_base_layer()
            if osm_success:
                pass
            else:
                pass

            # Large dataset detection - warn users about potential performance impact
            # Use appropriate threshold based on data type (location-only has 4x higher threshold)
            warning_threshold = LARGE_IMPORT_WARNING_THRESHOLD_LOCATION_ONLY if is_location_only else LARGE_IMPORT_WARNING_THRESHOLD
            warning_dialog_shown = False
            if record_count >= warning_threshold:
                # Show warning dialog with location-only flag
                warning_dialog = LargeImportWarningDialog(record_count, is_location_only, self.dlg)
                result = warning_dialog.exec_()
                warning_dialog_shown = True

                if result != warning_dialog.Accepted:
                    return

                user_choice = warning_dialog.get_user_choice()

                if user_choice == LargeImportWarningDialog.CANCEL:
                    return
                elif user_choice == LargeImportWarningDialog.IMPORT_PARTIAL:
                    # Import only first records using appropriate limit for data type
                    partial_limit = PARTIAL_IMPORT_LIMIT_LOCATION_ONLY if is_location_only else PARTIAL_IMPORT_LIMIT
                    data = data[:partial_limit]
                    record_count = len(data)
                # If IMPORT_ALL, continue with full dataset

            # Use chunked import for datasets > CHUNKED_IMPORT_THRESHOLD records
            if record_count > CHUNKED_IMPORT_THRESHOLD:
                self._perform_chunked_import(data, layer_name, color, record_count, warning_dialog_shown, is_location_only)
            else:
                # Use regular import for small datasets
                success, message = self.layer_manager.create_point_layer(layer_name, data, color, is_location_only)
                self._handle_import_result(success, message, warning_dialog_shown)
            
        except Exception as e:
            error_msg = f"Data import error: {str(e)}"
            log_error(error_msg)
            self.dlg.show_error(error_msg)
    
    def _perform_chunked_import(self, data, layer_name, color, record_count, warning_dialog_shown=False, is_location_only=False):
        """Perform chunked import with progress dialog."""
        # Create progress dialog
        progress_dialog = ImportProgressDialog(record_count, self.dlg)
        progress_dialog.show()
        
        # Define progress callback
        def progress_callback(processed_count, chunk_info):
            if progress_dialog.wasCanceled():
                raise InterruptedError("Import cancelled by user")
            progress_dialog.update_progress(processed_count, chunk_info)
        
        try:
            # Perform chunked import
            success, message = self.layer_manager.create_point_layer_chunked(
                layer_name, data, color, progress_callback, is_location_only
            )
            
            # Update final progress
            progress_dialog.finish_import(success, len(data) if success else 0, message)
            
            # Show result message (suppress popup if warning dialog was shown)
            self._handle_import_result(success, message, warning_dialog_shown)
            
        except InterruptedError:
            # User cancelled import
            progress_dialog.finish_import(False, 0, "Import was cancelled by user.")
            self.dlg.show_info("Import was cancelled.")
            
        except Exception as e:
            # Import failed
            error_msg = f"Chunked import failed: {str(e)}"
            progress_dialog.finish_import(False, 0, error_msg)
            self.dlg.show_error(error_msg)
    
    def _handle_import_result(self, success, message, warning_dialog_shown=False):
        """Handle the result of an import operation."""
        if success:
            # Only show popup dialog if no warning dialog was shown
            # (progress dialog already shows success message when warning dialog was used)
            # if not warning_dialog_shown:
            #     self.dlg.show_info(message)
            # Show import success message in plugin dialog
            if self.dlg:
                self.dlg.show_plugin_message(message, "success", 5000)
        else:
            self.dlg.show_error(message)
    
    def _handle_cancel_request(self):
        """Handle cancel request."""
        try:
            self.data_manager.cancel_request()
            self.dlg.hide_cancel_button()
            
        except Exception as e:
            error_msg = f"Cancel request error: {str(e)}"
            log_error(error_msg)
            self.dlg.show_error(error_msg)

    def _handle_page_next(self, tab_name: str):
        """Handle next page request."""
        try:
            self.data_manager.next_page(tab_name)
        except Exception as e:
            error_msg = f"Page navigation error: {str(e)}"
            log_error(error_msg)
            self.dlg.show_error(error_msg)

    def _handle_page_previous(self, tab_name: str):
        """Handle previous page request."""
        try:
            self.data_manager.previous_page(tab_name)
        except Exception as e:
            error_msg = f"Page navigation error: {str(e)}"
            log_error(error_msg)
            self.dlg.show_error(error_msg)
    
    def _handle_company_search_request(self, query: str):
        """Handle company search request."""
        try:
            self.data_manager.search_companies(query)
        except Exception as e:
            error_msg = f"Company search error: {str(e)}"
            log_error(error_msg)
            # Don't show error to user for search failures, just log them