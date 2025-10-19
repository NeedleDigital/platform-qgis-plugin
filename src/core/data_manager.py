"""
Data Management Core Logic

This module contains the core business logic for the Needle Digital Mining Data
Importer plugin. It handles all data operations including:

- API communication with the Needle Digital backend
- Data fetching with pagination support
- Request validation and parameter management
- Progress tracking and user feedback
- Large dataset optimization and chunked processing
- Company search functionality
- Tab-based data state management

The DataManager class acts as the central coordinator between the UI layer
and the API client, implementing the business rules and data flow logic.

Key Features:
    - Signal-based architecture for loose coupling with UI
    - Robust error handling and logging
    - Memory-efficient data processing
    - Support for large datasets (1M+ records)
    - Real-time progress tracking
    - User cancellation support

Author: Needle Digital
Contact: divyansh@needle-digital.com
"""

import time
from math import ceil
from typing import Dict, List, Any, Optional, Callable
from qgis.PyQt.QtCore import QObject, pyqtSignal

# Internal imports for modular architecture
from ..api.client import ApiClient  # HTTP client for API communication
from ..config.constants import (
    API_ENDPOINTS,
    VALIDATION_MESSAGES, DEFAULT_HOLE_TYPES,
    MAX_DISPLAY_RECORDS
)  # Configuration
from ..config.settings import config  # Application settings
from ..utils.logging import log_api_request, log_api_response, log_error, log_info  # Logging utilities
from ..utils.validation import format_column_name  # Column formatting utility


class DataManager(QObject):
    """Core data management class for handling API requests and data processing.
    
    This class serves as the central business logic coordinator for the plugin,
    managing all data operations between the UI and API layers. It implements
    a signal-based architecture for loose coupling and real-time updates.
    
    Responsibilities:
        - Coordinate API requests for drill hole and assay data
        - Manage pagination for large datasets
        - Validate user requests and filter parameters
        - Track progress and provide status updates
        - Handle errors and provide user feedback
        - Manage tab-based data states
        - Optimize memory usage for large imports
    
    Architecture Pattern:
        Uses Qt's signal/slot pattern for communication with UI components,
        allowing for asynchronous operations and real-time user feedback
        without blocking the interface.
    
    Signals:
        status_changed (str): Emitted when operation status changes
        progress_changed (int): Emitted with progress percentage (0-100)
        data_ready (str, list, list, dict): Emitted when data is successfully fetched
        error_occurred (str): Emitted when an error occurs during operations
        loading_started (str): Emitted when data loading begins for a tab
        loading_finished (str): Emitted when data loading completes for a tab
        companies_search_results (list): Emitted with company search results
    """
    
    # Qt Signals for UI communication - enable asynchronous operations
    status_changed = pyqtSignal(str)  # Status message for user feedback
    progress_changed = pyqtSignal(int)  # Progress percentage (0-100)
    data_ready = pyqtSignal(str, list, list, dict)  # tab_name, data, headers, pagination_info
    error_occurred = pyqtSignal(str)  # Error message for user notification
    loading_started = pyqtSignal(str)  # tab_name - Loading state begins
    loading_finished = pyqtSignal(str)  # tab_name - Loading state ends
    companies_search_results = pyqtSignal(list)  # Company search results
    login_required = pyqtSignal()  # Authentication required - show login dialog
    
    def __init__(self):
        super().__init__()
        
        # Initialize API client
        self.api_client = ApiClient()
        self.api_client.api_response_received.connect(self._handle_api_response)
        self.api_client.api_error_occurred.connect(self._handle_api_error)
        
        # State management
        self.tab_states = {
            'Holes': {
                'data': [],  # Full dataset (for QGIS import)
                'display_data': [],  # First 1K records only (for fast table pagination)
                'headers': [],
                'total_records': 0,
                'current_page': 0,
                'records_per_page': 100,
                'filter_params': {},
                'fetch_details': {}  # Store last fetch details for "View Details" dialog
            },
            'Assays': {
                'data': [],  # Full dataset (for QGIS import)
                'display_data': [],  # First 1K records only (for fast table pagination)
                'headers': [],
                'total_records': 0,
                'current_page': 0,
                'records_per_page': 100,
                'filter_params': {},
                'fetch_details': {}  # Store last fetch details for "View Details" dialog
            }
        }

        # Streaming state (replaces batch_fetch_status)
        self.streaming_state = None
        self.fetch_start_time = 0
        self._is_fetching = False  # Track if currently fetching data
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.api_client.is_authenticated()
    
    def cancel_request(self) -> None:
        """Cancel any ongoing API requests and reset state."""
        if not self._is_fetching:
            return
        
        
        # Cancel streaming request if active
        if self.streaming_state and self.streaming_state.get('reply'):
            reply = self.streaming_state['reply']
            tab_name = self.streaming_state.get('tab_name', 'Holes')

            # Abort the network request
            self.api_client.cancel_streaming_request(reply)

            # Clear state
            self.streaming_state = None
            self._is_fetching = False

            # Update UI
            self.progress_changed.emit(-1)  # Hide progress bar
            self.status_changed.emit("Fetch cancelled by user")
            self.loading_finished.emit(tab_name)
        else:
            # Fallback: cancel any active requests and clear states
            self.api_client.cancel_all_requests()
            self._is_fetching = False
            self.streaming_state = None

            self.progress_changed.emit(-1)  # Hide progress bar
            self.status_changed.emit("Request cancelled by user.")

            # Emit loading finished signal for both tabs
            self.loading_finished.emit("Holes")
            self.loading_finished.emit("Assays")
        
    
    def fetch_data(self, tab_name: str, filter_params: Dict[str, Any],
                   fetch_all: bool = False) -> None:
        """
        Fetch data for specified tab.

        Args:
            tab_name: 'Holes' or 'Assays'
            filter_params: Dictionary of filter parameters
            fetch_all: Whether to fetch all available records (always False now)
        """
        if not self.is_authenticated():
            # Instead of showing error message, trigger direct login dialog
            self.login_required.emit()
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

        # Get requested count
        requested_records = filter_params.get('requested_count', 100)

        # Set total_records to requested_records for pagination calculation
        self.tab_states[tab_name]['total_records'] = requested_records

        self.status_changed.emit(f"Preparing to stream {requested_records:,} records...")
        self.progress_changed.emit(1)

        # Start streaming fetch
        self._start_streaming_fetch(tab_name, requested_records)
    
    def _start_streaming_fetch(self, tab_name: str, requested_count: int) -> None:
        """Initiate SSE streaming request for data."""
        # Cancel any existing streaming request first
        if self.streaming_state and self.streaming_state.get('reply'):
            old_reply = self.streaming_state['reply']
            self.api_client.cancel_streaming_request(old_reply)
            self.streaming_state = None

        # Prepare parameters for new streaming API
        base_params = self.tab_states[tab_name]['filter_params'].copy()

        # Add required total_count parameter
        base_params['total_count'] = requested_count

        # Remove old pagination params that don't exist in streaming API
        base_params.pop('limit', None)
        base_params.pop('skip', None)
        base_params.pop('requested_count', None)
        base_params.pop('fetch_all_records', None)
        base_params.pop('fetch_only_location', None)

        # Select appropriate endpoint
        endpoint = API_ENDPOINTS['holes_data'] if tab_name == 'Holes' else API_ENDPOINTS['assays_data']

        # Log request parameters for debugging
        print(f"\n=== Starting Streaming Request ===")
        print(f"Endpoint: {endpoint}")
        print(f"Parameters: {base_params}")
        log_info(f"Starting streaming fetch for {tab_name}: {requested_count:,} records")
        log_info(f"Request params: {base_params}")

        # Initialize streaming state
        self.streaming_state = {
            'tab_name': tab_name,
            'all_data': [],
            'total_target': requested_count,
            'columns': None,  # Will be set from complete event
            'reply': None
        }

        # Start streaming
        reply = self.api_client.make_streaming_request(
            endpoint=endpoint,
            params=base_params,
            data_callback=self._handle_streaming_data,
            progress_callback=self._handle_streaming_progress,
            complete_callback=self._handle_streaming_complete,
            error_callback=self._handle_streaming_error
        )

        self.streaming_state['reply'] = reply
    
    def _handle_streaming_data(self, event_data: dict) -> None:
        """Process incoming data batch from SSE stream."""
        # Silently ignore if no active streaming state (happens when request cancelled or new request started)
        if not self.streaming_state:
            return

        tab_name = self.streaming_state['tab_name']

        # Extract records based on tab
        if tab_name == 'Holes':
            records = event_data.get('holes', [])
        else:  # Assays
            records = event_data.get('assays', [])  # API sends 'assays', not 'samples'

        # Accumulate all data
        self.streaming_state['all_data'].extend(records)

        # Log receipt
        total_accumulated = len(self.streaming_state['all_data'])
        log_info(f"Received {len(records)} records via stream (total accumulated: {total_accumulated:,})")

    def _handle_streaming_progress(self, progress_data: dict) -> None:
        """Update UI with real-time progress from SSE stream."""
        # Silently ignore if no active streaming state
        if not self.streaming_state:
            return

        # API sends 'total_fetched', 'target', and 'progress_percentage'
        fetched = progress_data.get('total_fetched', 0)
        target = progress_data.get('target', 1)
        percentage = progress_data.get('progress_percentage', 0)

        # Emit progress (0-100)
        self.progress_changed.emit(int(percentage))

        # Update status with streaming icon
        self.status_changed.emit(f"📡 Streaming data: {fetched:,} / {target:,} records ({percentage:.1f}%)")

    def _handle_streaming_complete(self, complete_data: dict) -> None:
        """Finalize streaming and prepare data for display."""
        # Silently ignore if no active streaming state
        if not self.streaming_state:
            return

        try:
            tab_name = self.streaming_state['tab_name']
            all_data = self.streaming_state['all_data']

            # CRITICAL: Get columns from complete event (not from data records)
            columns = complete_data.get('columns', [])
            total_fetched = complete_data.get('total_fetched', len(all_data))
            state_contributions = complete_data.get('state_contributions', {})

            # Format column names for display (hole_id -> Hole Id, etc.)
            formatted_headers = [format_column_name(col) for col in columns]

            # Store full data (for QGIS import) and display data (first 1K for fast table pagination)
            self.tab_states[tab_name]['data'] = all_data
            self.tab_states[tab_name]['display_data'] = all_data[:MAX_DISPLAY_RECORDS]  # First 1K only
            self.tab_states[tab_name]['headers'] = formatted_headers
            self.tab_states[tab_name]['original_headers'] = columns  # Keep original for data access
            self.tab_states[tab_name]['total_records'] = total_fetched

            # Calculate fetch time
            fetch_time = time.time() - self.fetch_start_time

            # Store fetch details for "View Details" dialog
            # Use the original requested count from streaming_state (before clearing it)
            requested_count = self.streaming_state.get('total_target', total_fetched)
            self.tab_states[tab_name]['fetch_details'] = {
                'total_fetched': total_fetched,
                'requested_count': requested_count,
                'fetch_time': fetch_time,
                'state_contributions': state_contributions,
                'data_type': tab_name
            }

            # Log completion with state breakdown
            log_info(f"Streaming complete: {total_fetched:,} records fetched in {fetch_time:.1f}s")
            log_info(f"State contributions: {state_contributions}")

            # Clear streaming state
            self.streaming_state = None
            self._is_fetching = False

            # Emit completion
            self.progress_changed.emit(100)
            self.status_changed.emit(f"✓ Successfully fetched {total_fetched:,} records in {fetch_time:.1f}s")

            # Send display_data to UI (not all_data) for fast rendering
            pagination_info = self._get_pagination_info(tab_name)
            display_data = self.tab_states[tab_name]['display_data']
            self.data_ready.emit(tab_name, display_data, formatted_headers, pagination_info)
            self.loading_finished.emit(tab_name)

        except Exception as e:
            error_msg = f"Failed to finalize streaming: {e}"
            print(f"\n=== ERROR IN COMPLETE HANDLER ===")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            log_error(error_msg)
            log_error(traceback.format_exc())

            # Emergency cleanup
            tab_name = 'Unknown'
            if self.streaming_state:
                tab_name = self.streaming_state.get('tab_name', 'Unknown')
                self.streaming_state = None

            self._is_fetching = False
            self.progress_changed.emit(-1)
            self.error_occurred.emit(error_msg)
            self.loading_finished.emit(tab_name)

    def _handle_streaming_error(self, error_data: dict) -> None:
        """
        Handle error events from SSE stream.

        IMPORTANT: Error events are just informational events in the stream,
        NOT fatal errors. The stream continues and we wait for the 'complete' event.
        Do NOT close the stream or cleanup state here.
        """
        try:
            print(f"\n=== STREAMING ERROR EVENT (non-fatal) ===")
            print(f"Error data: {error_data}")
            log_error(f"SSE error event received (stream continues): {error_data}")

            # Silently ignore if no active streaming state
            if not self.streaming_state:
                return

            # Extract error message safely
            if isinstance(error_data, dict):
                error_msg = error_data.get('error', 'Unknown error')
                # Check for API error details
                if 'message' in error_data:
                    error_msg = error_data.get('message', error_msg)
            elif isinstance(error_data, str):
                error_msg = error_data
            else:
                error_msg = str(error_data)

            print(f"Error message: {error_msg}")
            print(f"Stream continues... waiting for more events")

            # Just log the error - DO NOT close stream or cleanup state
            # The stream will continue and we'll get more data/progress/complete events
            log_error(f"Non-fatal stream error: {error_msg}")

        except Exception as e:
            print(f"CRITICAL ERROR in _handle_streaming_error: {e}")
            import traceback
            traceback.print_exc()
            log_error(f"Critical error in error handler: {e}")
    
    def get_tab_data(self, tab_name: str) -> tuple:
        """Get data and headers for a tab."""
        state = self.tab_states[tab_name]
        return state['data'], state['headers']

    def get_fetch_details(self, tab_name: str) -> dict:
        """Get fetch details for a tab (for View Details dialog)."""
        return self.tab_states[tab_name].get('fetch_details', {})

    def clear_tab_data(self, tab_name: str) -> None:
        """Clear data for a tab."""
        self._clear_tab_data(tab_name)
        # Reset UI state
        self.progress_changed.emit(-1)  # Hide progress bar when clearing data
        self.status_changed.emit("Ready to fetch data.")
        pagination_info = self._get_pagination_info(tab_name)
        # Add flag to indicate this is a reset/clear operation, not an API response
        pagination_info['is_reset_operation'] = True
        self.data_ready.emit(tab_name, [], [], pagination_info)
    
    def _clear_tab_data(self, tab_name: str) -> None:
        """Internal method to clear tab data."""
        self.tab_states[tab_name].update({
            'data': [],
            'display_data': [],
            'headers': [],
            'total_records': 0,
            'current_page': 0,
            'filter_params': {},
            'fetch_details': {}
        })

    def _clear_tab_data_only(self, tab_name: str) -> None:
        """Internal method to clear tab data but preserve filter_params."""
        self.tab_states[tab_name].update({
            'data': [],
            'display_data': [],
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
        log_error(f"API Error for {endpoint}: {error_message}")
        self.error_occurred.emit(f"API request failed: {error_message}")

        # Reset streaming state on error
        if self.streaming_state:
            tab_name = self.streaming_state.get('tab_name', 'Holes')
            self.streaming_state = None
            self.loading_finished.emit(tab_name)

        self._is_fetching = False
        self.progress_changed.emit(-1)  # Hide progress bar on error
        self.status_changed.emit("Ready for next request.")
    
    def _get_pagination_info(self, tab_name: str) -> dict:
        """Calculate pagination information for a tab (table-based pagination, 100 records per page)."""
        state = self.tab_states[tab_name]
        total_records = len(state['data'])  # Full dataset count
        display_count = len(state['display_data'])  # Display dataset count (max 1K)

        if total_records == 0:
            return {
                'current_page': 0,
                'total_pages': 0,
                'records_per_table_page': 100,  # Table displays 100 records per page
                'total_records': total_records,
                'showing_records': 0,
                'has_data': False
            }

        # Table-based pagination: 100 records per page in the table display
        # Calculate pages based on display_data (not full data)
        records_per_table_page = 100
        total_pages = max(1, (display_count + records_per_table_page - 1) // records_per_table_page)
        current_page = state['current_page'] + 1  # Convert from 0-based to 1-based

        return {
            'current_page': current_page,
            'total_pages': total_pages,
            'records_per_table_page': records_per_table_page,
            'total_records': total_records,  # Actual total (may be > 1000)
            'display_count': display_count,  # What's shown in table (max 1000)
            'showing_records': min(records_per_table_page, display_count - (current_page - 1) * records_per_table_page),
            'has_data': True
        }
    
    def navigate_to_page(self, tab_name: str, page_number: int) -> None:
        """Navigate to a specific page in the table display."""
        state = self.tab_states[tab_name]
        display_count = len(state['display_data'])

        if display_count == 0:
            return

        records_per_table_page = 100
        max_page = max(1, (display_count + records_per_table_page - 1) // records_per_table_page)

        # Validate page number
        page_number = max(1, min(page_number, max_page))
        state['current_page'] = page_number - 1  # Convert to 0-based

        # Emit updated data for current page (use display_data, not full data)
        pagination_info = self._get_pagination_info(tab_name)
        self.data_ready.emit(tab_name, state['display_data'], state['headers'], pagination_info)
    
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
    
    def search_companies(self, company_name: str) -> None:
        """
        Search for companies by name.
        
        Args:
            company_name: Company name search query (minimum 3 characters)
        """
        if not self.is_authenticated():
            # Show login dialog instead of failing silently for company search
            self.login_required.emit()
            return
        
        if not company_name or len(company_name.strip()) < 3:
            # Clear search results for short queries
            self.companies_search_results.emit([])
            return
        
        search_params = {'company_name': company_name.strip()}
        
        
        self.api_client.make_api_request(
            API_ENDPOINTS['companies_search'],
            search_params,
            self._handle_companies_search_response
        )
    
    def _handle_companies_search_response(self, response_data) -> None:
        """Handle the response from companies search API."""
        try:
            # Handle both dict and list responses
            if isinstance(response_data, list):
                # Direct list response (most common case)
                companies = response_data
            elif isinstance(response_data, dict):
                # Dict response with companies key
                companies = response_data.get('companies', [])
            else:
                companies = []
            
            # Convert to list of (display_name, value) tuples expected by DynamicSearchFilterWidget
            company_results = []
            for company in companies:
                if isinstance(company, dict):
                    # If company is a dict with name field
                    company_name = company.get('name', str(company))
                else:
                    # If company is just a string
                    company_name = str(company)
                
                company_results.append((company_name, company_name))
            
            self.companies_search_results.emit(company_results)

        except Exception as e:
            error_msg = f"Failed to process companies search response: {e}"
            log_error(error_msg)
            # Emit empty results on error
            self.companies_search_results.emit([])

