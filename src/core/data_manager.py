"""
Data management core logic for the Needle Digital Mining Data Importer plugin.
Handles data fetching, processing, and state management.
"""

import time
from math import ceil
from typing import Dict, List, Any, Optional, Callable
from qgis.PyQt.QtCore import QObject, pyqtSignal

from ..api.client import ApiClient
from ..config.constants import API_ENDPOINTS, API_FETCH_LIMIT, VALIDATION_MESSAGES
from ..config.settings import config
from ..utils.validation import validate_fetch_all_request
from ..utils.logging import get_logger, log_api_request, log_api_response

logger = get_logger(__name__)

class DataManager(QObject):
    """Core data management class for handling API requests and data processing."""
    
    # Signals
    status_changed = pyqtSignal(str)  # Status message
    progress_changed = pyqtSignal(int)  # Progress percentage
    data_ready = pyqtSignal(str, list, list, dict)  # tab_name, data, headers, pagination_info
    error_occurred = pyqtSignal(str)  # Error message
    loading_started = pyqtSignal(str)  # tab_name - Emitted when loading starts
    loading_finished = pyqtSignal(str)  # tab_name - Emitted when loading ends
    
    def __init__(self):
        super().__init__()
        
        # Initialize API client
        self.api_client = ApiClient()
        self.api_client.api_response_received.connect(self._handle_api_response)
        self.api_client.api_error_occurred.connect(self._handle_api_error)
        
        # State management
        self.tab_states = {
            'Holes': {
                'data': [],
                'headers': [],
                'total_records': 0,
                'current_page': 0,
                'records_per_page': 100,
                'filter_params': {}
            },
            'Assays': {
                'data': [],
                'headers': [],
                'total_records': 0,
                'current_page': 0,
                'records_per_page': 100,
                'filter_params': {}
            }
        }
        
        # Batch fetching state
        self.batch_fetch_status = None
        self.fetch_start_time = 0
        self._is_fetching = False  # Track if currently fetching data
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.api_client.is_authenticated()
    
    def cancel_request(self) -> None:
        """Cancel any ongoing API requests and reset state."""
        if not self._is_fetching:
            return
        
        logger.info("Cancelling API requests...")
        
        # Cancel all active network requests
        self.api_client.cancel_all_requests()
        
        # Reset batch fetching state
        self.batch_fetch_status = None
        self._is_fetching = False
        
        # Reset progress and status
        self.progress_changed.emit(-1)  # Hide progress bar on cancel
        self.status_changed.emit("Request cancelled by user.")
        
        # Emit loading finished signal for both tabs since we cancelled all requests
        self.loading_finished.emit("Holes")
        self.loading_finished.emit("Assays")
        
        logger.info("API requests cancelled successfully")
    
    def fetch_data(self, tab_name: str, filter_params: Dict[str, Any], 
                   fetch_all: bool = False) -> None:
        """
        Fetch data for specified tab.
        
        Args:
            tab_name: 'Holes' or 'Assays'
            filter_params: Dictionary of filter parameters
            fetch_all: Whether to fetch all available records
        """
        if not self.is_authenticated():
            self.error_occurred.emit(VALIDATION_MESSAGES['auth_required'])
            return
        
        # Emit loading started signal
        self.loading_started.emit(tab_name)
        
        # Clear existing data but preserve filter_params
        self._clear_tab_data_only(tab_name)
        
        # Store filter parameters after clearing data
        self.tab_states[tab_name]['filter_params'] = filter_params.copy()
        
        # Set fetching state
        self._is_fetching = True
        
        # Start timing
        self.fetch_start_time = time.time()
        
        if fetch_all:
            # Validate fetch_all request
            states_param = filter_params.get('states', "")
            if states_param:
                selected_states = [state.strip() for state in states_param.split(",")]
            else:
                selected_states = []  # "All States" case
            
            is_valid, error_msg = validate_fetch_all_request(selected_states)
            if not is_valid:
                self._is_fetching = False
                self.loading_finished.emit(tab_name)
                self.error_occurred.emit(error_msg)
                return
            
            # For fetch_all: First get count, then fetch data
            count_endpoint = API_ENDPOINTS['holes_count'] if tab_name == 'Holes' else API_ENDPOINTS['assays_count']
            
            log_api_request(count_endpoint, filter_params, logger)
            self.status_changed.emit("Calculating total available records...")
            self.progress_changed.emit(1)
            
            self.api_client.make_api_request(
                count_endpoint,
                filter_params,
                lambda data: self._handle_count_response(tab_name, data, fetch_all)
            )
        else:
            # For specific count: Skip count API, directly calculate and fetch
            requested_records = filter_params.get('requested_count', 100)
            
            # Set total_records to requested_records for pagination calculation
            self.tab_states[tab_name]['total_records'] = requested_records
            
            self.status_changed.emit(f"Preparing to fetch {requested_records} records...")
            self.progress_changed.emit(1)
            
            # Start direct fetch without count API
            self._start_sequential_fetch(tab_name, requested_records)
    
    def _handle_count_response(self, tab_name: str, response_data: Dict[str, Any], 
                              fetch_all: bool) -> None:
        """Handle the response from count API."""
        try:
            print(f"[DEBUG] Count response structure: keys={list(response_data.keys())}")
            print(f"[DEBUG] Full count response: {response_data}")
            
            logger.info(f"Count response structure: keys={list(response_data.keys())}")
            logger.info(f"Full count response: {response_data}")
            
            total_count = int(response_data.get('total_count', 0))
            self.tab_states[tab_name]['total_records'] = total_count
            
            log_api_response(f"{tab_name.lower()}_count", True, total_count, logger)
            
            if total_count == 0:
                self.progress_changed.emit(-1)  # Hide progress bar
                self.status_changed.emit("No records found matching your criteria.")
                pagination_info = self._get_pagination_info(tab_name)
                self.data_ready.emit(tab_name, [], [], pagination_info)
                self._is_fetching = False
                self.loading_finished.emit(tab_name)
                return
            
            # Determine how many records to fetch
            if fetch_all:
                records_to_fetch = total_count
                self.status_changed.emit(f"Preparing to fetch all {total_count} records...")
            else:
                state = self.tab_states[tab_name]
                records_to_fetch = min(total_count, state['records_per_page'])
                self.status_changed.emit(f"Preparing to fetch {records_to_fetch} records...")
            
            # Start sequential fetch process
            self._start_sequential_fetch(tab_name, records_to_fetch)
            
        except Exception as e:
            error_msg = f"Failed to process count response: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            self._is_fetching = False
            self.loading_finished.emit(tab_name)
    
    def _start_sequential_fetch(self, tab_name: str, records_to_fetch: int) -> None:
        """Start the sequential data fetching process."""
        num_chunks = ceil(records_to_fetch / API_FETCH_LIMIT)
        
        self.batch_fetch_status = {
            "tab_name": tab_name,
            "total_chunks": num_chunks,
            "records_to_fetch": records_to_fetch,
            "next_chunk_index": 0,
            "all_data": [],
            "base_params": self.tab_states[tab_name]['filter_params'].copy()
        }
        
        self.status_changed.emit(f"Fetching data in {num_chunks} chunks...")
        self._fetch_next_chunk()
    
    def _fetch_next_chunk(self) -> None:
        """Fetch the next chunk of data."""
        if not self.batch_fetch_status:
            return
        
        status = self.batch_fetch_status
        chunk_index = status['next_chunk_index']
        tab_name = status['tab_name']
        
        # Prepare chunk parameters
        data_endpoint = API_ENDPOINTS['holes_data'] if tab_name == 'Holes' else API_ENDPOINTS['assays_data']
        chunk_params = status['base_params'].copy()
        
        remaining_records = status['records_to_fetch'] - len(status['all_data'])
        chunk_params['limit'] = min(API_FETCH_LIMIT, remaining_records)
        chunk_params['skip'] = chunk_index * API_FETCH_LIMIT
        
        # Update progress from 1% to 98% (leave 2% for final processing)
        progress = 1 + int((chunk_index / status['total_chunks']) * 97)
        self.progress_changed.emit(progress)
        self.status_changed.emit(f"Fetching chunk {chunk_index + 1} of {status['total_chunks']}...")
        
        log_api_request(data_endpoint, chunk_params, logger)
        
        self.api_client.make_api_request(
            data_endpoint,
            chunk_params,
            lambda data: self._handle_chunk_response(data)
        )
    
    def _handle_chunk_response(self, response_data: Dict[str, Any]) -> None:
        """Handle response from data chunk API."""
        if not self.batch_fetch_status:
            return
        
        try:
            status = self.batch_fetch_status
            tab_name = status['tab_name']
            
            # Extract data based on tab_name
            if tab_name == "Holes":
                chunk_data = response_data.get('holes', [])
            else:  # Assays
                chunk_data = response_data.get('assays', [])
            
            # Generate headers from first record if we don't have them yet
            headers = []
            if chunk_data and not self.tab_states[tab_name]['headers']:
                headers = list(chunk_data[0].keys())
            else:
                headers = self.tab_states[tab_name]['headers']
            
            print(f"[DEBUG] Chunk response structure: keys={list(response_data.keys())}")
            print(f"[DEBUG] Full response: {response_data}")
            print(f"[DEBUG] Chunk data length: {len(chunk_data)}")
            print(f"[DEBUG] Headers: {headers}")
            if chunk_data:
                print(f"[DEBUG] First chunk record: {chunk_data[0]}")
            
            logger.info(f"Chunk response structure: keys={list(response_data.keys())}")
            logger.info(f"Chunk data length: {len(chunk_data)}")
            logger.info(f"Headers: {headers}")
            
            # Store headers (from first chunk)
            if not self.tab_states[tab_name]['headers']:
                self.tab_states[tab_name]['headers'] = headers
            
            # Append chunk data
            status['all_data'].extend(chunk_data)
            status['next_chunk_index'] += 1
            
            log_api_response(f"{tab_name.lower()}_data_chunk", True, len(chunk_data), logger)
            
            # Check if we're done or if API returned empty results (no more data available)
            if (len(chunk_data) == 0 or  # Empty response - no more data available
                status['next_chunk_index'] >= status['total_chunks'] or 
                len(status['all_data']) >= status['records_to_fetch']):
                
                if len(chunk_data) == 0:
                    logger.info(f"API returned empty results - stopping fetch for {tab_name}")
                    self.status_changed.emit(f"No more data available. Fetched {len(status['all_data'])} records.")
                
                self._finalize_data_fetch()
            else:
                # Fetch next chunk
                self._fetch_next_chunk()
                
        except Exception as e:
            error_msg = f"Failed to process chunk response: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            
            # Get tab_name before clearing batch_fetch_status
            tab_name = self.batch_fetch_status['tab_name'] if self.batch_fetch_status else None
            
            self.batch_fetch_status = None
            self._is_fetching = False
            
            if tab_name:
                self.loading_finished.emit(tab_name)
            else:
                # Emit for both tabs as fallback
                self.loading_finished.emit("Holes")
                self.loading_finished.emit("Assays")
    
    def _finalize_data_fetch(self) -> None:
        """Finalize the data fetching process."""
        if not self.batch_fetch_status:
            return
        
        try:
            status = self.batch_fetch_status
            tab_name = status['tab_name']
            
            # Store final data
            self.tab_states[tab_name]['data'] = status['all_data']
            
            # Calculate fetch time
            fetch_time = time.time() - self.fetch_start_time
            record_count = len(status['all_data'])
            
            # Update UI
            self.progress_changed.emit(100)
            self.status_changed.emit(f"Data fetch complete. {record_count} records in {fetch_time:.1f}s")
            
            # Emit data ready signal with pagination info
            pagination_info = self._get_pagination_info(tab_name)
            self.data_ready.emit(
                tab_name,
                self.tab_states[tab_name]['data'],
                self.tab_states[tab_name]['headers'],
                pagination_info
            )
            
            logger.info(f"Data fetch completed: {record_count} records for {tab_name} in {fetch_time:.1f}s")
            
        except Exception as e:
            error_msg = f"Failed to finalize data fetch: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
        finally:
            self.batch_fetch_status = None
            self._is_fetching = False
            # Emit loading finished signal
            self.loading_finished.emit(tab_name)
    
    def get_tab_data(self, tab_name: str) -> tuple:
        """Get data and headers for a tab."""
        state = self.tab_states[tab_name]
        return state['data'], state['headers']
    
    def clear_tab_data(self, tab_name: str) -> None:
        """Clear data for a tab."""
        self._clear_tab_data(tab_name)
        # Reset UI state
        self.progress_changed.emit(-1)  # Hide progress bar when clearing data
        self.status_changed.emit("Ready to fetch data.")
        pagination_info = self._get_pagination_info(tab_name)
        self.data_ready.emit(tab_name, [], [], pagination_info)
    
    def _clear_tab_data(self, tab_name: str) -> None:
        """Internal method to clear tab data."""
        self.tab_states[tab_name].update({
            'data': [],
            'headers': [],
            'total_records': 0,
            'current_page': 0,
            'filter_params': {}
        })
    
    def _clear_tab_data_only(self, tab_name: str) -> None:
        """Internal method to clear tab data but preserve filter_params."""
        self.tab_states[tab_name].update({
            'data': [],
            'headers': [],
            'total_records': 0,
            'current_page': 0
            # filter_params preserved
        })
    
    def _handle_api_response(self, endpoint: str, response_data: Dict[str, Any]) -> None:
        """Handle API response signals."""
        # This is handled by specific response handlers above
        pass
    
    def _handle_api_error(self, endpoint: str, error_message: str) -> None:
        """Handle API error signals."""
        logger.error(f"API Error for {endpoint}: {error_message}")
        self.error_occurred.emit(f"API request failed: {error_message}")
        
        # Reset batch fetch status on error
        if self.batch_fetch_status:
            self.batch_fetch_status = None
        
        self._is_fetching = False
        self.progress_changed.emit(-1)  # Hide progress bar on error
        self.status_changed.emit("Ready for next request.")
        
        # Emit loading finished signal for both tabs since we don't know which one failed
        self.loading_finished.emit("Holes")
        self.loading_finished.emit("Assays")
    
    def _get_pagination_info(self, tab_name: str) -> dict:
        """Calculate pagination information for a tab (table-based pagination, 100 records per page)."""
        state = self.tab_states[tab_name]
        data_count = len(state['data'])
        
        if data_count == 0:
            return {
                'current_page': 0,
                'total_pages': 0,
                'records_per_table_page': 100,  # Table displays 100 records per page
                'total_records': data_count,
                'showing_records': 0,
                'has_data': False
            }
        
        # Table-based pagination: 100 records per page in the table display
        records_per_table_page = 100
        total_pages = max(1, (data_count + records_per_table_page - 1) // records_per_table_page)
        current_page = state['current_page'] + 1  # Convert from 0-based to 1-based
        
        return {
            'current_page': current_page,
            'total_pages': total_pages,
            'records_per_table_page': records_per_table_page,
            'total_records': data_count,
            'showing_records': min(records_per_table_page, data_count - (current_page - 1) * records_per_table_page),
            'has_data': True
        }
    
    def navigate_to_page(self, tab_name: str, page_number: int) -> None:
        """Navigate to a specific page in the table display."""
        state = self.tab_states[tab_name]
        data_count = len(state['data'])
        
        if data_count == 0:
            return
        
        records_per_table_page = 100
        max_page = max(1, (data_count + records_per_table_page - 1) // records_per_table_page)
        
        # Validate page number
        page_number = max(1, min(page_number, max_page))
        state['current_page'] = page_number - 1  # Convert to 0-based
        
        # Emit updated data for current page
        pagination_info = self._get_pagination_info(tab_name)
        self.data_ready.emit(tab_name, state['data'], state['headers'], pagination_info)
    
    def next_page(self, tab_name: str) -> None:
        """Navigate to next page."""
        state = self.tab_states[tab_name]
        current_page = state['current_page'] + 1  # Convert to 1-based
        self.navigate_to_page(tab_name, current_page + 1)
    
    def previous_page(self, tab_name: str) -> None:
        """Navigate to previous page."""
        state = self.tab_states[tab_name]
        current_page = state['current_page'] + 1  # Convert to 1-based
        self.navigate_to_page(tab_name, current_page - 1)