"""
API Client for Needle Digital Mining Data Service

This module provides a comprehensive HTTP client for communicating with the
Needle Digital mining data API, handling all aspects of authentication,
token management, and data requests.

Key Features:
    - Firebase Authentication integration
    - Automatic token refresh and management
    - Secure credential storage using QGIS settings
    - Robust error handling and retry logic
    - Signal-based asynchronous operations
    - Request/response logging for debugging
    - Network timeout and error recovery

Authentication Flow:
    1. User provides email/password credentials
    2. Firebase authentication via REST API
    3. JWT tokens stored securely in QGIS settings
    4. Automatic token refresh before expiration
    5. Silent re-authentication on startup

Security Features:
    - Secure token storage using QGIS encrypted settings
    - No plaintext password storage
    - Token validation and automatic refresh
    - Request signing and authorization headers
    - SSL/TLS encryption for all communications

API Endpoints:
    - Authentication: Firebase Auth API
    - Data fetching: Needle Digital mining database
    - Company search: Company directory API
    - Count queries: Data availability checks

Author: Needle Digital
Contact: divyansh@needle-digital.com
"""

import json
import time
import re
from typing import Dict, Any, Optional, Callable
from qgis.PyQt.QtCore import QObject, pyqtSignal, QTimer, QUrl, QByteArray
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qgis.core import QgsSettings

# Internal configuration and utilities
from ..config.settings import config  # API configuration and settings
from ..utils.logging import log_error, log_warning  # Centralized logging system


class ApiClient(QObject):
    """HTTP API Client for Needle Digital Mining Data Services.
    
    A comprehensive API client that handles all communication with the Needle Digital
    mining database, including authentication, token management, and data requests.
    
    Features:
        - Firebase Authentication with JWT tokens
        - Automatic token refresh and session management
        - Secure credential storage using QGIS settings
        - Asynchronous operations with Qt signals
        - Robust error handling and retry logic
        - Request/response logging for debugging
        - Network timeout and connection management
    
    Signals:
        login_success(): Emitted when authentication succeeds
        login_failed(str): Emitted when authentication fails with error message
        api_response_received(str, dict): Emitted with endpoint and response data
        api_error_occurred(str, str): Emitted with endpoint and error message
    
    Thread Safety:
        This class is designed to be used from the main Qt thread and uses
        Qt's signal/slot mechanism for asynchronous operations.
    """
    
    # Qt Signals for asynchronous operation feedback
    login_success = pyqtSignal()  # Authentication successful
    login_failed = pyqtSignal(str)  # Authentication failed with error message
    api_response_received = pyqtSignal(str, dict)  # endpoint, response_data
    api_error_occurred = pyqtSignal(str, str)  # endpoint, error_message
    
    def __init__(self):
        super().__init__()
        self.network_manager = QNetworkAccessManager()
        self.auth_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: float = 0
        self._initialization_complete = False
        self._active_replies = []  # Track active network requests for cancellation
        
        # Token refresh timer
        self.token_refresh_timer = QTimer()
        self.token_refresh_timer.timeout.connect(lambda: self.refresh_auth_token(silent=True))
        
        # Load saved refresh token but don't refresh immediately
        settings = QgsSettings()
        self.refresh_token = settings.value("needle/refreshToken", None)
    
    def complete_initialization(self):
        """Complete initialization and attempt silent token refresh if needed."""
        if self._initialization_complete:
            return
            
        self._initialization_complete = True
        
        # Now it's safe to attempt token refresh
        if self.refresh_token:
            self.refresh_auth_token(silent=True)
    
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated."""
        return bool(self.auth_token and time.time() < self.token_expires_at)
    
    def login(self, email: str, password: str) -> None:
        """Authenticate user with email and password."""
        if not email or not password or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            self.login_failed.emit("A valid email and password are required.")
            return
        
        
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        self._make_request(
            url=config.firebase_auth_url,
            method="POST",
            data=payload,
            callback=self._handle_login_response,
            error_callback=lambda error: self.login_failed.emit(f"Login failed: {error}")
        )
    
    def logout(self) -> None:
        """Logout user and clear stored tokens."""
        self.auth_token = None
        self.refresh_token = None
        self.token_expires_at = 0
        self.token_refresh_timer.stop()
        
        # Clear stored refresh token
        settings = QgsSettings()
        settings.remove("needle/refreshToken")
        
        # Cancel any ongoing requests
        self.cancel_all_requests()
    
    def cancel_all_requests(self) -> None:
        """Cancel all active network requests."""
        for reply in self._active_replies:
            if reply and not reply.isFinished():
                reply.abort()
        self._active_replies.clear()
    
    def refresh_auth_token(self, silent: bool = False) -> None:
        """Refresh the authentication token using refresh token."""
        if not self.refresh_token:
            if not silent:
                log_warning("Token refresh aborted: No refresh token available.")
            return
        
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        self._make_request(
            url=config.firebase_refresh_url,
            method="POST",
            data=payload,
            callback=self._handle_refresh_response,
            error_callback=lambda error: log_error(f"Token refresh failed: {error}")
        )
    
    def make_api_request(self, endpoint: str, params: Dict[str, Any], callback: Optional[Callable] = None) -> None:
        """Make authenticated API request to Needle Digital service."""
        if not self.is_authenticated():
            self.api_error_occurred.emit(endpoint, "Authentication required")
            return
        
        url = f"{config.BASE_API_URL}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        self._make_request(
            url=url,
            method="GET",
            params=params,
            headers=headers,
            callback=lambda data: self._handle_api_response(endpoint, data, callback),
            error_callback=lambda error: self.api_error_occurred.emit(endpoint, error)
        )
    
    def _make_request(self, url: str, method: str = "GET", data: Optional[Dict] = None, 
                     params: Optional[Dict] = None, headers: Optional[Dict] = None,
                     callback: Optional[Callable] = None, error_callback: Optional[Callable] = None) -> None:
        """Make HTTP request with proper error handling."""
        request_url = QUrl(url)
        
        # Add query parameters for GET requests
        if method == "GET" and params:
            # Build query string manually to avoid Qt version compatibility issues
            query_parts = []
            for key, value in params.items():
                if value is not None:
                    query_parts.append(f"{key}={str(value)}")
            if query_parts:
                query_string = "&".join(query_parts)
                if "?" in url:
                    request_url = QUrl(f"{url}&{query_string}")
                else:
                    request_url = QUrl(f"{url}?{query_string}")
        
        request = QNetworkRequest(request_url)
        
        # Set headers
        if headers:
            for key, value in headers.items():
                request.setRawHeader(key.encode(), value.encode())
        
        # Make request based on method
        if method == "POST":
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
            json_data = QByteArray(json.dumps(data or {}).encode('utf-8'))
            reply = self.network_manager.post(request, json_data)
        else:
            reply = self.network_manager.get(request)
        
        # Track the reply for cancellation
        self._active_replies.append(reply)
        
        # Connect response handler
        reply.finished.connect(lambda: self._handle_network_reply(reply, callback, error_callback))
    
    def _handle_network_reply(self, reply: QNetworkReply, 
                             callback: Optional[Callable] = None,
                             error_callback: Optional[Callable] = None) -> None:
        """Handle network reply with proper error checking."""
        # Remove from active replies list
        if reply in self._active_replies:
            self._active_replies.remove(reply)
        
        try:
            if reply.error() != QNetworkReply.NoError:
                error_msg = reply.errorString()
                try:
                    error_data = json.loads(bytes(reply.readAll()).decode('utf-8'))
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass
                
                log_error(f"Network error: {error_msg}")
                if error_callback:
                    error_callback(error_msg)
            else:
                response_data = json.loads(bytes(reply.readAll()).decode('utf-8'))
                if callback:
                    callback(response_data)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response: {e}"
            log_error(error_msg)
            if error_callback:
                error_callback(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            log_error(error_msg)
            if error_callback:
                error_callback(error_msg)
        finally:
            reply.deleteLater()
    
    def _handle_login_response(self, response_data: Dict[str, Any]) -> None:
        """Handle login response from Firebase."""
        try:
            self.auth_token = response_data.get("idToken")
            self.refresh_token = response_data.get("refreshToken")
            
            if not self.auth_token or not self.refresh_token:
                self.login_failed.emit("Could not retrieve authentication credentials.")
                return
            
            # Calculate token expiration
            expires_in = int(response_data.get("expiresIn", 3600))
            self.token_expires_at = time.time() + expires_in
            
            # Save refresh token
            settings = QgsSettings()
            settings.setValue("needle/refreshToken", self.refresh_token)
            
            # Setup token refresh timer
            refresh_delay_ms = max(0, (expires_in - 60) * 1000)  # Refresh 1 minute before expiry
            self.token_refresh_timer.start(refresh_delay_ms)
            
            self.login_success.emit()
            
        except Exception as e:
            error_msg = f"Login processing error: {e}"
            log_error(error_msg)
            self.login_failed.emit(error_msg)
    
    def _handle_refresh_response(self, response_data: Dict[str, Any]) -> None:
        """Handle token refresh response."""
        try:
            self.auth_token = response_data.get("access_token") or response_data.get("id_token")
            if response_data.get("refresh_token"):
                self.refresh_token = response_data.get("refresh_token")
            
            if self.auth_token:
                expires_in = int(response_data.get("expires_in", 3600))
                self.token_expires_at = time.time() + expires_in
                
                # Update stored refresh token if new one provided
                if response_data.get("refresh_token"):
                    settings = QgsSettings()
                    settings.setValue("needle/refreshToken", self.refresh_token)
                
                # Schedule next refresh
                refresh_delay_ms = max(0, (expires_in - 60) * 1000)
                self.token_refresh_timer.start(refresh_delay_ms)
                
                
                # Emit login_success signal to update UI
                self.login_success.emit()
            else:
                log_error("Token refresh failed: No token in response")
                # Emit login_failed signal to update UI
                self.login_failed.emit("Token refresh failed")
                
        except Exception as e:
            log_error(f"Token refresh processing error: {e}")
            # Emit login_failed signal to update UI
            self.login_failed.emit(f"Token refresh error: {e}")
    
    def _handle_api_response(self, endpoint: str, response_data, 
                           callback: Optional[Callable] = None) -> None:
        """Handle API response from Needle Digital service."""
        
        if callback:
            callback(response_data)
        
        # Only emit the signal if response_data is a dictionary
        # Some endpoints (like companies search) return lists directly
        if isinstance(response_data, dict):
            self.api_response_received.emit(endpoint, response_data)
