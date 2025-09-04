"""
Needle Digital Mining Data Importer - Main Plugin Class
A QGIS plugin for importing Australian mining drill hole and assay data.
"""

import os
from qgis.PyQt.QtCore import QTranslator, QCoreApplication, qVersion
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import Qgis

# Import modular components
from .src.core.data_manager import DataManager
from .src.ui.main_dialog import DataImporterDialog
from .src.ui.components import LoginDialog, LayerOptionsDialog
from .src.utils.qgis_helpers import QGISLayerManager
from .src.utils.logging import get_logger
from .src.config.constants import PLUGIN_NAME, PLUGIN_VERSION

logger = get_logger(__name__)

class DataImporter:
    """Main plugin class for Needle Digital Mining Data Importer."""

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
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'DataImporter_{locale}.ts'
        )
        
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Initialize components
        self.actions = []
        self.menu = self.tr(u'&Needle Digital Tools')
        
        # Core components
        self.data_manager = None
        self.layer_manager = None
        self.dlg = None
        self.login_dlg = None
        
        logger.info(f"Plugin initialized: {PLUGIN_NAME} v{PLUGIN_VERSION}")

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
        
        logger.info("Plugin unloaded")

    def run(self):
        """Run method that loads and shows the plugin dialog."""
        try:
            # Initialize components if not already done
            self._initialize_components()
            
            # Show the dialog
            self.dlg.show()
            
            # Update UI based on authentication status
            is_authenticated = self.data_manager.is_authenticated()
            self.dlg.update_login_status(is_authenticated)
            
            logger.info("Plugin dialog opened")
            
        except Exception as e:
            error_msg = f"Failed to open plugin: {str(e)}"
            logger.error(error_msg)
            if self.iface:
                self.iface.messageBar().pushMessage(
                    "Error", error_msg, level=Qgis.Critical, duration=5
                )

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
            
            logger.info("Plugin components initialized")

    def _connect_dialog_signals(self):
        """Connect dialog signals to handlers."""
        # Authentication
        self.dlg.login_requested.connect(self._handle_login_request)
        self.dlg.logout_requested.connect(self._handle_logout_request)
        
        # Data operations
        self.dlg.data_fetch_requested.connect(self._handle_data_fetch_request)
        self.dlg.data_clear_requested.connect(self._handle_data_clear_request)
        self.dlg.data_import_requested.connect(self._handle_data_import_request)
        
        # Data manager signals
        self.data_manager.status_changed.connect(self.dlg.update_status)
        self.data_manager.progress_changed.connect(self.dlg.update_progress)
        self.data_manager.data_ready.connect(self.dlg.show_data)
        self.data_manager.error_occurred.connect(self.dlg.show_error)
        
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
                logger.info("Login dialog accepted")
            else:
                logger.info("Login dialog cancelled")
                
        except Exception as e:
            error_msg = f"Login dialog error: {str(e)}"
            logger.error(error_msg)
            self.dlg.show_error(error_msg)

    def _handle_logout_request(self):
        """Handle logout request from dialog."""
        try:
            self.data_manager.api_client.logout()
            self.dlg.update_login_status(False)
            
            # Clear any existing data
            self.dlg.show_data("Holes", [], [])
            self.dlg.show_data("Assays", [], [])
            
            if self.iface:
                self.iface.messageBar().pushMessage(
                    "Needle Digital", "Logged out successfully", 
                    level=Qgis.Info, duration=3
                )
            
            logger.info("User logged out")
            
        except Exception as e:
            error_msg = f"Logout error: {str(e)}"
            logger.error(error_msg)
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
            logger.error(error_msg)
            if self.login_dlg:
                self.login_dlg.on_login_result(False, error_msg)

    def _handle_login_success(self):
        """Handle successful login."""
        try:
            self.dlg.update_progress(100)
            
            if self.login_dlg:
                self.login_dlg.on_login_result(True, None)
            
            self.dlg.update_login_status(True)
            
            if self.iface:
                self.iface.messageBar().pushMessage(
                    "Success", "Login successful!", 
                    level=Qgis.Success, duration=3
                )
            
            logger.info("Login successful")
            
        except Exception as e:
            logger.error(f"Login success handler error: {str(e)}")

    def _handle_login_failed(self, error_message):
        """Handle failed login."""
        try:
            self.dlg.update_progress(0)
            self.dlg.update_status("Authentication failed.")
            
            if self.login_dlg:
                self.login_dlg.on_login_result(False, f"Login Failed: {error_message}")
            
            logger.warning(f"Login failed: {error_message}")
            
        except Exception as e:
            logger.error(f"Login failure handler error: {str(e)}")

    def _update_ui_on_auth_change(self):
        """Update UI when authentication status changes (including silent login)."""
        try:
            if self.dlg:
                is_authenticated = self.data_manager.is_authenticated()
                self.dlg.update_login_status(is_authenticated)
                logger.info(f"UI updated - Authentication status: {is_authenticated}")
        except Exception as e:
            logger.error(f"UI update error: {str(e)}")

    def _handle_data_fetch_request(self, tab_name, params, fetch_all):
        """Handle data fetch request."""
        try:
            logger.info(f"Data fetch requested for {tab_name}: {params}, fetch_all={fetch_all}")
            self.data_manager.fetch_data(tab_name, params, fetch_all)
            
        except Exception as e:
            error_msg = f"Data fetch error: {str(e)}"
            logger.error(error_msg)
            self.dlg.show_error(error_msg)

    def _handle_data_clear_request(self, tab_name):
        """Handle data clear request."""
        try:
            logger.info(f"Data clear requested for {tab_name}")
            self.data_manager.clear_tab_data(tab_name)
            
        except Exception as e:
            error_msg = f"Data clear error: {str(e)}"
            logger.error(error_msg)
            self.dlg.show_error(error_msg)

    def _handle_data_import_request(self, tab_name, layer_name, color):
        """Handle data import request."""
        try:
            # Get data from data manager
            data, headers = self.data_manager.get_tab_data(tab_name)
            
            if not data:
                self.dlg.show_error("No data available to import.")
                return
            
            logger.info(f"Importing {len(data)} records to layer '{layer_name}'")
            
            # Import to QGIS
            success, message = self.layer_manager.create_point_layer(layer_name, data, color)
            
            if success:
                self.dlg.show_info(message)
                if self.iface:
                    self.iface.messageBar().pushMessage(
                        "Success", message, level=Qgis.Success, duration=5
                    )
            else:
                self.dlg.show_error(message)
            
        except Exception as e:
            error_msg = f"Data import error: {str(e)}"
            logger.error(error_msg)
            self.dlg.show_error(error_msg)