# -*- coding: utf-8 -*-
# Final, stabilized version with all features and crash-prevention fixes.

import os
import json
import re
from math import ceil
import time

# --- QGIS Imports ---
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QVariant, QTimer
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QDialog
from qgis.core import (
    Qgis, QgsApplication, QgsProject, QgsPointXY, QgsGeometry, QgsFeature,
    QgsVectorLayer, QgsRasterLayer, QgsField, QgsFields, QgsWkbTypes,
    QgsNetworkAccessManager, QgsCoordinateReferenceSystem,
)
from PyQt5.QtCore import QUrl, QByteArray
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply, QNetworkAccessManager

from .data_importer_dialog import DataImporterDialog, LoginDialog, LayerOptionsDialog

class DataImporter:
    """QGIS Plugin Implementation with Firebase Authentication and advanced filters."""

    PAGE_SIZE = 100
    DISPLAY_PAGE_SIZE = 100 
    API_FETCH_LIMIT = 50000 

    FIREBASE_API_KEY = "AIzaSyCuX5I0TaQCVmIUVdo1uM_aOQ3zVkrUV8Y"
    FIREBASE_REFRESH_URL = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    API_BASE_URL = "https://master.api.agni.needle-digital.com/"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr(u'&Needle Digital Tools')
        self.toolbar = self.iface.addToolBar(u'DataImporter')
        self.toolbar.setObjectName(u'DataImporter')
        
        self.dlg = None
        self.login_dlg = None
        self.network_manager = QNetworkAccessManager()

        self.auth_token = None
        self.refresh_token = None
        self.token_expires_at = 0
        self.token_refresh_timer = QTimer()
        self.token_refresh_timer.setSingleShot(True)
        self.token_refresh_timer.timeout.connect(self.refresh_auth_token)
        
        self.silent_login_attempted = False
        self.batch_fetch_status = {}
        self.fetch_start_time = 0
        
        self.company_search_timer = QTimer()
        self.company_search_timer.setSingleShot(True)
        self.company_search_timer.timeout.connect(self.search_companies_timeout)

        self.tab_states = {
            'Holes': self._get_new_tab_state(),
            'Assays': self._get_new_tab_state()
        }
        
        print("DataImporter Plugin: Initialized.")

    def _get_new_tab_state(self):
        return {
            'full_cache': [], 'headers': [], 'page_size': self.PAGE_SIZE, 'current_page': 1,
            'total_pages': 0, 'total_records': 0, 'element': 'Cu', 'operator': '>', 'value': '',
            'companies': [], 'states': [], 'ui_widgets': {}
        }

    def tr(self, message):
        return QCoreApplication.translate('DataImporter', message)

    def add_action(self, icon_path, text, callback, parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'Import Mining Data'),
            callback=self.run,
            parent=self.iface.mainWindow())
        print("DataImporter Plugin: GUI Initialized.")

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&Needle Digital Tools'), action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar
        if self.dlg:
            self.dlg.close()
        self.token_refresh_timer.stop()
        print("DataImporter Plugin: Unloaded.")

    def run(self):
        if not self.silent_login_attempted:
            self.attempt_silent_login()
            self.silent_login_attempted = True

        if self.dlg is None:
            self.dlg = DataImporterDialog()
            self.dlg.setAttribute(Qt.WA_DeleteOnClose)
            self.tab_states['Holes']['ui_widgets'] = {
                'count_input': self.dlg.holes_count_input,
                'fetch_all_checkbox': self.dlg.holes_fetch_all_checkbox,
                'fetch_button': self.dlg.fetch_holes_button,
                'company_filter': self.dlg.holes_company_filter,
                'state_filter': self.dlg.holes_state_filter,
                **self.dlg.holes_widgets
            }
            self.tab_states['Assays']['ui_widgets'] = {
                'element_input': self.dlg.assay_element_input,
                'operator_input': self.dlg.assay_operator_input,
                'value_input': self.dlg.assay_value_input,
                'count_input': self.dlg.assay_count_input,
                'fetch_all_checkbox': self.dlg.assay_fetch_all_checkbox,
                'fetch_button': self.dlg.fetch_assay_button,
                'state_filter': self.dlg.assays_state_filter,
                **self.dlg.assays_widgets
            }
            self.dlg.login_button.clicked.connect(self.handle_login_logout)
            self.dlg.reset_all_button.clicked.connect(self.reset_all_data)
            self.dlg.fetch_holes_button.clicked.connect(lambda: self.fetch_new_data('Holes'))
            self.dlg.fetch_assay_button.clicked.connect(lambda: self.fetch_new_data('Assays'))
            self.dlg.holes_widgets['import_button'].clicked.connect(lambda: self.import_to_qgis('Holes'))
            self.dlg.assays_widgets['import_button'].clicked.connect(lambda: self.import_to_qgis('Assays'))
            self.dlg.holes_widgets['clear_button'].clicked.connect(lambda: self.clear_tab_data('Holes'))
            self.dlg.assays_widgets['clear_button'].clicked.connect(lambda: self.clear_tab_data('Assays'))
            self.dlg.holes_widgets['prev_button'].clicked.connect(lambda: self.navigate_page('Holes', -1))
            self.dlg.holes_widgets['next_button'].clicked.connect(lambda: self.navigate_page('Holes', 1))
            self.dlg.assays_widgets['prev_button'].clicked.connect(lambda: self.navigate_page('Assays', -1))
            self.dlg.assays_widgets['next_button'].clicked.connect(lambda: self.navigate_page('Assays', 1))
            self.dlg.holes_company_filter.textChanged.connect(self.on_company_search_text_changed)
            self.dlg.finished.connect(self.on_dialog_close)
            self.update_dialog_ui()

        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()
        
    def attempt_silent_login(self):
        if self.auth_token: return
        settings = QSettings()
        saved_token = settings.value("needle/refreshToken", None)
        if saved_token:
            print("Found saved refresh token. Attempting silent login...")
            self.refresh_token = saved_token
            self.refresh_auth_token(silent=True)

    def on_company_search_text_changed(self, text):
        if len(text) < 3:
            self.company_search_timer.stop()
            if self.dlg:
                self.dlg.holes_company_filter.popup.hide()
            return
        self.company_search_timer.start(500)

    def search_companies_timeout(self):
        if not self.auth_token:
            if self.dlg: self.dlg.show_error("You must be logged in to search for companies.")
            return
        if not self.dlg: return
        search_text = self.tab_states['Holes']['ui_widgets']['company_filter'].search_box.text()
        if search_text:
            endpoint = "companies/search"
            params = {'company_name': search_text}
            self.make_api_request(endpoint, params, 'Holes', purpose='company_search')

    def handle_login_logout(self):
        if self.auth_token:
            settings = QSettings()
            settings.remove("needle/refreshToken")
            print("Cleared saved refresh token on logout.")
            self.auth_token = None
            self.refresh_token = None
            self.token_expires_at = 0
            self.token_refresh_timer.stop()
            self.reset_all_data()
            if self.iface: self.iface.messageBar().pushMessage("Success", "You have been logged out.", level=Qgis.Info, duration=3)
        else:
            self.show_login_dialog()
        if self.dlg: self.update_dialog_ui()

    def show_login_dialog(self):
        # Store a reference to the login dialog to avoid brittle sender() logic
        self.login_dlg = LoginDialog(self.dlg)
        self.login_dlg.login_attempt.connect(self.process_login_attempt)
        self.login_dlg.exec_()
        self.login_dlg = None # Clear reference after it's closed

    def process_login_attempt(self, email, password):
        if not self.login_dlg: return
        if not email or not password or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            self.login_dlg.on_login_result(False, "A valid email and password are required.")
            return
        if self.dlg:
            self.dlg.status_label.setText(f"Authenticating {email}...")
            self.dlg.progress_bar.setValue(50)
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        data = QByteArray(json.dumps(payload).encode('utf-8'))
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        reply = self.network_manager.post(request, data)
        reply.finished.connect(lambda: self.handle_firebase_login_reply(reply))

    def handle_firebase_login_reply(self, reply):
        if self.dlg: self.dlg.progress_bar.setValue(100)
        
        if reply.error() != QNetworkReply.NoError:
            try: err_msg = json.loads(bytes(reply.readAll()).decode('utf-8')).get("error",{}).get("message","Unknown auth error.")
            except Exception: err_msg = reply.errorString()
            if self.login_dlg: self.login_dlg.on_login_result(False, f"Login Failed: {err_msg}")
            if self.dlg: self.dlg.status_label.setText("Authentication failed.")
        else:
            response_data = json.loads(bytes(reply.readAll()).decode('utf-8'))
            self.auth_token = response_data.get("idToken")
            self.refresh_token = response_data.get("refreshToken")
            try: expires_in = int(response_data.get("expiresIn", 3600))
            except (ValueError, TypeError): expires_in = 3600
            if self.auth_token and self.refresh_token:
                settings = QSettings(); settings.setValue("needle/refreshToken", self.refresh_token)
                self.token_expires_at = time.time() + expires_in
                refresh_delay_ms = max(0, (expires_in - 60) * 1000)
                self.token_refresh_timer.start(refresh_delay_ms)
                if self.iface: self.iface.messageBar().pushMessage("Success", "Login successful!", level=Qgis.Success, duration=3)
                if self.login_dlg: self.login_dlg.on_login_result(True, None)
                self.update_dialog_ui()
            else:
                err_msg = "Could not retrieve full authentication credentials."
                if self.login_dlg: self.login_dlg.on_login_result(False, f"Login Failed: {err_msg}")
                if self.dlg: self.dlg.status_label.setText("Authentication failed.")
        reply.deleteLater()

    def refresh_auth_token(self, silent=False):
        if not self.refresh_token:
            if not silent: print("Token refresh aborted: No refresh token available.")
            return
        if not silent: print("Attempting to refresh authentication token...")
        payload = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        data = QByteArray(json.dumps(payload).encode('utf-8'))
        request = QNetworkRequest(QUrl(self.FIREBASE_REFRESH_URL))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        reply = self.network_manager.post(request, data)
        reply.finished.connect(lambda: self.handle_token_refresh_reply(reply, silent))

    def handle_token_refresh_reply(self, reply, silent=False):
        settings = QSettings()
        if reply.error() != QNetworkReply.NoError:
            settings.remove("needle/refreshToken")
            if not silent and self.iface: self.iface.messageBar().pushMessage("Error", "Your session has expired. Please log in again.", level=Qgis.Critical, duration=5)
            self.auth_token = None; self.refresh_token = None
            if self.dlg: self.update_dialog_ui()
        else:
            response_data = json.loads(bytes(reply.readAll()).decode('utf-8'))
            self.auth_token = response_data.get("id_token")
            self.refresh_token = response_data.get("refresh_token")
            try: expires_in = int(response_data.get("expires_in", 3600))
            except (ValueError, TypeError): expires_in = 3600
            if self.auth_token and self.refresh_token:
                settings.setValue("needle/refreshToken", self.refresh_token)
                self.token_expires_at = time.time() + expires_in
                refresh_delay_ms = max(0, (expires_in - 60) * 1000)
                self.token_refresh_timer.start(refresh_delay_ms)
                if silent: print("Silent login successful.")
                elif self.iface: self.iface.messageBar().pushMessage("Info", "Session renewed.", level=Qgis.Info, duration=3)
            else:
                settings.remove("needle/refreshToken")
                if not silent and self.iface: self.iface.messageBar().pushMessage("Warning", "Could not renew session.", level=Qgis.Warning, duration=5)
                self.auth_token = None; self.refresh_token = None
            if self.dlg: self.update_dialog_ui()
        reply.deleteLater()
        
    def make_api_request(self, endpoint, params, tab_name, purpose=None):
        if not self.auth_token:
            if self.dlg: self.dlg.show_error("You must be logged in to make this request.")
            return
        query_string = "&".join([f"{key}={value}" for key, value in params.items()])
        request_url = f"{self.API_BASE_URL}{endpoint}?{query_string}"
        request = QNetworkRequest(QUrl(request_url))
        request.setRawHeader(b"Authorization", f"Bearer {self.auth_token}".encode('utf-8'))
        reply = QgsNetworkAccessManager.instance().get(request)
        reply.setProperty("purpose", purpose)
        reply.setProperty("tab_name", tab_name)
        reply.finished.connect(lambda: self.handle_api_reply(reply))

    def handle_api_reply(self, reply):
        purpose = reply.property("purpose")
        tab_name = reply.property("tab_name")
        
        # Safety check for tab_name
        if not tab_name:
            reply.deleteLater()
            return
            
        if reply.error() != QNetworkReply.NoError:
            self._handle_api_error(reply)
            return

        try:
            response_data = json.loads(bytes(reply.readAll()).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            if self.dlg: self.dlg.show_error(f"Failed to parse server response: {e}")
            self._reset_ui_for_tab(tab_name)
            return
            
        # Route response based on purpose
        if purpose == 'company_search':
            if self.dlg: self.tab_states['Holes']['ui_widgets']['company_filter'].showPopup([(name, name) for name in response_data])
        elif purpose == "get_total_count":
            state = self.tab_states[tab_name]
            total_available = int(response_data.get('total_count', 0))
            state['total_records'] = total_available
            fetch_all = state['ui_widgets']['fetch_all_checkbox'].isChecked()
            records_to_fetch = total_available if fetch_all else int(state['ui_widgets']['count_input'].text() or 0)
            if records_to_fetch > 0:
                self._start_sequential_fetch(tab_name, records_to_fetch)
            else:
                self._finalize_data_fetch([], tab_name)
        elif purpose == "get_data_chunk":
            self._process_sequential_chunk(response_data, tab_name)
        
        reply.deleteLater()

    def fetch_new_data(self, tab_name):
        if not self.auth_token:
            if self.dlg: self.dlg.show_error("You must be logged in to fetch data.")
            return
        
        # Check state selection for "fetch all" functionality
        state = self.tab_states[tab_name]; ui = state['ui_widgets']
        fetch_all = ui['fetch_all_checkbox'].isChecked()
        selected_states = ui['state_filter'].currentData()
        
        if fetch_all:
            if len(selected_states) != 1:
                if len(selected_states) == 0:
                    self.dlg.show_error("To fetch all records, you must select exactly one state. Please select a state first.")
                else:
                    self.dlg.show_error("To fetch all records, you must select exactly one state. Please select only one state.")
                return
        
        self.fetch_start_time = time.time()
        self.clear_tab_data(tab_name)
        endpoint = "plugin/fetch_dh_count" if tab_name == 'Holes' else "plugin/fetch_assay_count"
        params = self._build_filter_params(tab_name)
        ui['loading_label'].setText("Calculating total available records...")
        ui['content_stack'].setCurrentWidget(ui['loading_label'])
        self.dlg.status_label.setText("Calculating total records..."); self.dlg.progress_bar.setValue(5)
        self.make_api_request(endpoint, params, tab_name, purpose="get_total_count")
            
    def _start_sequential_fetch(self, tab_name, records_to_fetch):
        self.dlg.status_label.setText(f"Preparing to fetch {records_to_fetch} records...")
        num_chunks = ceil(records_to_fetch / self.API_FETCH_LIMIT)
        self.batch_fetch_status = {
            "tab_name": tab_name, "total_chunks": num_chunks,
            "records_to_fetch": records_to_fetch, "next_chunk_index": 0,
            "all_data": [], "base_params": self._build_filter_params(tab_name)
        }
        self._fetch_next_chunk()

    def _fetch_next_chunk(self):
        status = self.batch_fetch_status; i = status['next_chunk_index']
        tab_name = status['tab_name']
        endpoint = "plugin/fetch_drill_holes" if tab_name == 'Holes' else "plugin/fetch_assay_samples"
        chunk_params = status['base_params'].copy()
        remaining_records = status['records_to_fetch'] - len(status['all_data'])
        chunk_params['limit'] = min(self.API_FETCH_LIMIT, remaining_records)
        chunk_params['skip'] = i * self.API_FETCH_LIMIT
        progress = (i / status['total_chunks']) * 100
        self.dlg.progress_bar.setValue(int(progress))
        self.dlg.status_label.setText(f"Fetching chunk {i + 1} of {status['total_chunks']}...")
        self.make_api_request(endpoint, chunk_params, tab_name, purpose="get_data_chunk")
        
    def _process_sequential_chunk(self, response_data, tab_name):
        data_key = 'holes' if tab_name == 'Holes' else 'assays'
        records = response_data.get(data_key, [])
        self.batch_fetch_status["all_data"].extend(records)
        self.batch_fetch_status["next_chunk_index"] += 1
        if self.batch_fetch_status["next_chunk_index"] < self.batch_fetch_status["total_chunks"]:
            self._fetch_next_chunk()
        else:
            self.dlg.status_label.setText("All records fetched. Finalizing...")
            self._finalize_data_fetch(self.batch_fetch_status["all_data"], tab_name)
            self.batch_fetch_status = {}

    def _finalize_data_fetch(self, records, tab_name):
        state = self.tab_states[tab_name]
        duration = time.time() - self.fetch_start_time
        if not records:
            if self.iface: self.iface.messageBar().pushMessage("Info", "No records were found for the selected criteria.", level=Qgis.Info, duration=3)
            self._reset_ui_for_tab(tab_name)
            return
        state['full_cache'] = records
        state['headers'] = list(records[0].keys()) if records else []
        downloaded_count = len(records)
        state['total_pages'] = ceil(downloaded_count / self.DISPLAY_PAGE_SIZE)
        state['current_page'] = 1
        page_data = self.get_page_data(tab_name)
        if self.dlg:
            self.dlg.show_table_for_tab(state['ui_widgets'], page_data, state['headers'])
            self.update_pagination_controls(tab_name)
            self.dlg.status_label.setText(f"{downloaded_count} records downloaded in {duration:.2f} seconds.")
            self.dlg.progress_bar.setValue(100)

    def get_page_data(self, tab_name):
        state = self.tab_states[tab_name]
        if not state['full_cache']: return []
        start_index = (state['current_page'] - 1) * self.DISPLAY_PAGE_SIZE
        end_index = start_index + self.DISPLAY_PAGE_SIZE
        return state['full_cache'][start_index:end_index]

    def navigate_page(self, tab_name, direction):
        state = self.tab_states[tab_name]
        new_page = state['current_page'] + direction
        if 1 <= new_page <= state['total_pages']:
            state['current_page'] = new_page
            page_data = self.get_page_data(tab_name)
            if self.dlg:
                self.dlg.show_table_for_tab(state['ui_widgets'], page_data, state['headers'])
                self.update_pagination_controls(tab_name)

    def update_pagination_controls(self, tab_name):
        if not self.dlg: return
        state = self.tab_states[tab_name]; ui = state['ui_widgets']
        has_data = len(state['full_cache']) > 0
        has_pages = state['total_pages'] > 1
        ui['page_label'].setVisible(has_pages); ui['prev_button'].setVisible(has_pages); ui['next_button'].setVisible(has_pages)
        if has_data:
            ui['page_label'].setText(f"Page {state['current_page']} of {state['total_pages']} ({len(state['full_cache'])} records)")
            ui['prev_button'].setEnabled(state['current_page'] > 1)
            ui['next_button'].setEnabled(state['current_page'] < state['total_pages'])
        else:
            ui['page_label'].setText("")

    def clear_tab_data(self, tab_name):
        state = self.tab_states[tab_name]; ui = state.get('ui_widgets', {})
        state['full_cache'] = []; state['headers'] = []
        state['total_records'] = 0; state['current_page'] = 1; state['total_pages'] = 0
        if ui and self.dlg:
            ui['loading_label'].setText("Waiting for data...")
            ui['content_stack'].setCurrentWidget(ui['loading_label'])
            self.update_pagination_controls(tab_name)
            ui['import_button'].setVisible(False)
            self.dlg.status_label.setText("Ready.")
            self.dlg.progress_bar.setValue(0)
        
    def _build_filter_params(self, tab_name):
        state = self.tab_states[tab_name]; ui = state['ui_widgets']; params = {}
        state['states'] = ui['state_filter'].currentData()
        if state['states']: params['states'] = ",".join(state['states'])
        if tab_name == 'Holes':
            state['companies'] = ui['company_filter'].currentData()
            if state['companies']: params['companies'] = ",".join(state['companies'])
        else:
            state['element'] = ui['element_input'].currentData()
            state['operator'] = ui['operator_input'].currentText()
            state['value'] = ui['value_input'].text()
            params['element'] = state['element']
            if state['value']: params['operator'] = state['operator']; params['value'] = state['value']
        return params
        
    def _handle_api_error(self, reply):
        if reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 401:
            if self.iface: self.iface.messageBar().pushMessage("Info", "Your session has expired. Please log in again.", level=Qgis.Info, duration=5)
            self.handle_login_logout()
            self.show_login_dialog()
        else:
            error_msg = reply.errorString()
            if self.dlg: self.dlg.show_error(f"API Error: {error_msg}")
            tab_name = reply.property("tab_name")
            if tab_name: self._reset_ui_for_tab(tab_name)

    def _reset_ui_for_tab(self, tab_name):
        if self.dlg:
            self.clear_tab_data(tab_name)
            ui = self.tab_states[tab_name].get('ui_widgets', {})
            if ui: ui['loading_label'].setText("An error occurred. Please try your search again.")
            if self.fetch_start_time > 0:
                duration = time.time() - self.fetch_start_time
                self.dlg.status_label.setText(f"Error after {duration:.2f} seconds.")
            else:
                self.dlg.status_label.setText("Error fetching data.")
            self.dlg.progress_bar.setValue(0)
            
    def reset_all_data(self):
        self.clear_tab_data('Holes'); self.clear_tab_data('Assays')
        if self.iface: self.iface.messageBar().pushMessage("Info", "All data and filters have been cleared.", level=Qgis.Info, duration=3)

    def on_dialog_close(self):
        self.dlg = None

    def update_dialog_ui(self):
        if not self.dlg: return
        if self.auth_token:
            self.dlg.login_button.setText("Logout"); self.dlg.reset_all_button.setVisible(True)
            self.dlg.status_label.setText("Ready (Logged In)")
        else:
            self.dlg.login_button.setText("Login"); self.dlg.reset_all_button.setVisible(False)
            self.dlg.status_label.setText("Ready. Please log in.")
        for tab_name, state in self.tab_states.items():
            ui = state['ui_widgets']
            if not ui: continue
            if 'count_input' in ui: ui['count_input'].setText(str(state.get('page_size', self.PAGE_SIZE)))
            if 'state_filter' in ui: ui['state_filter'].setCurrentData(state.get('states', []))
            if tab_name == 'Holes':
                if 'company_filter' in ui: ui['company_filter'].setCurrentData(state.get('companies', []))
            else:
                if 'element_input' in ui:
                    element_value = state.get('element', 'cu')
                    # Find index by data value (lowercase symbol)
                    for i in range(ui['element_input'].count()):
                        if ui['element_input'].itemData(i) == element_value:
                            ui['element_input'].setCurrentIndex(i)
                            break
                if 'operator_input' in ui: ui['operator_input'].setCurrentText(state.get('operator', '>'))
                if 'value_input' in ui: ui['value_input'].setText(state.get('value', ''))
            page_data = self.get_page_data(tab_name)
            self.dlg.show_table_for_tab(ui, page_data, state['headers'])
            self.update_pagination_controls(tab_name)

    def import_to_qgis(self, tab_name):
        if not self.iface: return
        self.iface.messageBar().pushMessage("Info", f"Starting import for {tab_name}...", level=Qgis.Info, duration=2)
        state = self.tab_states[tab_name]
        if not state['full_cache'] or not state['headers']:
            if self.dlg: self.dlg.show_error("No data to import. Please fetch data first.")
            return
        is_spatial = 'longitude' in state['headers'] and 'latitude' in state['headers']
        downloaded_count = len(state['full_cache'])
        default_layer_name = f"{tab_name} Layer ({downloaded_count} records)"
        options_dialog = LayerOptionsDialog(default_name=default_layer_name, parent=self.dlg)
        if not options_dialog.exec_() == QDialog.Accepted: return
        layer_name, point_color = options_dialog.get_options()
        layer_name = layer_name or default_layer_name
        uri = "Point?crs=epsg:4326" if is_spatial else "NoGeometry"
        layer = QgsVectorLayer(uri, layer_name, "memory")
        if not layer.isValid():
            if self.dlg: self.dlg.show_error(f"Failed to create layer '{layer_name}'.")
            return
        prov = layer.dataProvider()
        numeric_fields = {'latitude', 'longitude', 'dip', 'azimuth', 'final_depth', 'from_depth', 'to_depth', 'value'}
        fields = QgsFields()
        for hdr in state['headers']:
            fields.append(QgsField(hdr, QVariant.Double if hdr in numeric_fields else QVariant.String))
        prov.addAttributes(fields)
        layer.updateFields()
        feats = []
        for rec in state['full_cache']:
            feat = QgsFeature(fields)
            if is_spatial:
                try: feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(rec.get('longitude',0)), float(rec.get('latitude',0)))))
                except (ValueError, TypeError): continue
            attributes = []
            for h in state['headers']:
                val = rec.get(h)
                if h in numeric_fields:
                    try: attributes.append(float(val) if val not in [None, ''] else None)
                    except (ValueError, TypeError): attributes.append(None)
                else:
                    attributes.append(str(val) if val is not None else '')
            feat.setAttributes(attributes)
            feats.append(feat)
        prov.addFeatures(feats)
        layer.updateExtents()
        if is_spatial and layer.renderer():
            symbol = layer.renderer().symbol()
            symbol.setColor(point_color)
            symbol.setSize(3)
            layer.triggerRepaint()
        project = QgsProject.instance()
        if is_spatial and not project.mapLayersByName("OpenStreetMap"):
            basemap_uri = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmin=0&zmax=19"
            basemap = QgsRasterLayer(basemap_uri, "OpenStreetMap", "wms")
            if basemap.isValid():
                basemap.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
                project.addMapLayer(basemap, False)
                root = project.layerTreeRoot()
                root.insertLayer(0, basemap)
        project.addMapLayer(layer)
        self.iface.setActiveLayer(layer)
        self.iface.actionIdentify().trigger()
        self.iface.messageBar().pushMessage("Success", f"Layer '{layer_name}' added.", level=Qgis.Success, duration=7)