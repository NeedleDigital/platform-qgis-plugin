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
    data_ready = pyqtSignal(str, list, list)  # tab_name, data, headers
    error_occurred = pyqtSignal(str)  # Error message
    
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
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.api_client.is_authenticated()
    
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
        
        # Validate fetch_all request
        if fetch_all:
            # Convert states parameter to list for validation
            states_param = filter_params.get('states', "")
            if states_param:
                selected_states = [state.strip() for state in states_param.split(",")]
            else:
                selected_states = []  # "All States" case
            
            is_valid, error_msg = validate_fetch_all_request(selected_states)
            if not is_valid:
                self.error_occurred.emit(error_msg)
                return
        
        # Store filter parameters
        self.tab_states[tab_name]['filter_params'] = filter_params.copy()
        
        # Clear existing data
        self._clear_tab_data(tab_name)
        
        # Start timing
        self.fetch_start_time = time.time()
        
        # Get total record count first
        count_endpoint = API_ENDPOINTS['holes_count'] if tab_name == 'Holes' else API_ENDPOINTS['assays_count']
        
        log_api_request(count_endpoint, filter_params, logger)
        self.status_changed.emit("Calculating total available records...")
        self.progress_changed.emit(5)
        
        self.api_client.make_api_request(
            count_endpoint,
            filter_params,
            lambda data: self._handle_count_response(tab_name, data, fetch_all)
        )
    
    def _handle_count_response(self, tab_name: str, response_data: Dict[str, Any], 
                              fetch_all: bool) -> None:
        """Handle the response from count API."""
        try:
            logger.info(f"Count response structure: keys={list(response_data.keys())}")
            logger.info(f"Full count response: {response_data}")
            
            total_count = int(response_data.get('count', 0))
            self.tab_states[tab_name]['total_records'] = total_count
            
            log_api_response(f"{tab_name.lower()}_count", True, total_count, logger)
            
            if total_count == 0:
                self.progress_changed.emit(0)  # Reset progress bar
                self.status_changed.emit("No records found matching your criteria.")
                self.data_ready.emit(tab_name, [], [])
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
        
        # Update progress
        progress = int((chunk_index / status['total_chunks']) * 95)  # Leave 5% for processing
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
            
            # Extract data
            chunk_data = response_data.get('data', [])
            headers = response_data.get('headers', [])
            
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
            
            # Check if we're done
            if (status['next_chunk_index'] >= status['total_chunks'] or 
                len(status['all_data']) >= status['records_to_fetch']):
                self._finalize_data_fetch()
            else:
                # Fetch next chunk
                self._fetch_next_chunk()
                
        except Exception as e:
            error_msg = f"Failed to process chunk response: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            self.batch_fetch_status = None
    
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
            
            # Emit data ready signal
            self.data_ready.emit(
                tab_name,
                self.tab_states[tab_name]['data'],
                self.tab_states[tab_name]['headers']
            )
            
            logger.info(f"Data fetch completed: {record_count} records for {tab_name} in {fetch_time:.1f}s")
            
        except Exception as e:
            error_msg = f"Failed to finalize data fetch: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
        finally:
            self.batch_fetch_status = None
    
    def get_tab_data(self, tab_name: str) -> tuple:
        """Get data and headers for a tab."""
        state = self.tab_states[tab_name]
        return state['data'], state['headers']
    
    def clear_tab_data(self, tab_name: str) -> None:
        """Clear data for a tab."""
        self._clear_tab_data(tab_name)
        # Reset UI state
        self.progress_changed.emit(0)
        self.status_changed.emit("Ready to fetch data.")
        self.data_ready.emit(tab_name, [], [])
    
    def _clear_tab_data(self, tab_name: str) -> None:
        """Internal method to clear tab data."""
        self.tab_states[tab_name].update({
            'data': [],
            'headers': [],
            'total_records': 0,
            'current_page': 0
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
        
        self.progress_changed.emit(0)
        self.status_changed.emit("Ready for next request.")