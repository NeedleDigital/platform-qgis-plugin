"""
API client for Needle Digital mining data service.
Handles authentication, token management, and API requests.
"""

import json
import time
import re
from typing import Dict, Any, Optional, Callable
from qgis.PyQt.QtCore import QObject, pyqtSignal, QTimer, QUrl, QByteArray
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qgis.core import QgsSettings

from ..config.settings import config
from ..utils.logging import get_logger

logger = get_logger(__name__)

class ApiClient(QObject):
    """API client for Needle Digital services."""
    
    # Signals
    login_success = pyqtSignal()
    login_failed = pyqtSignal(str)
    api_response_received = pyqtSignal(str, dict)  # endpoint, data
    api_error_occurred = pyqtSignal(str, str)      # endpoint, error_message
    
    def __init__(self):
        super().__init__()
        self.network_manager = QNetworkAccessManager()
        self.auth_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: float = 0
        
        # Token refresh timer
        self.token_refresh_timer = QTimer()
        self.token_refresh_timer.timeout.connect(lambda: self.refresh_auth_token(silent=True))
        
        # Load saved refresh token
        settings = QgsSettings()
        self.refresh_token = settings.value("needle/refreshToken", None)
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
        
        logger.info(f"Attempting login for user: {email}")
        
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
        logger.info("User logged out")
        self.auth_token = None
        self.refresh_token = None
        self.token_expires_at = 0
        self.token_refresh_timer.stop()
        
        # Clear stored refresh token
        settings = QgsSettings()
        settings.remove("needle/refreshToken")
    
    def refresh_auth_token(self, silent: bool = False) -> None:
        """Refresh the authentication token using refresh token."""
        if not self.refresh_token:
            if not silent:
                logger.warning("Token refresh aborted: No refresh token available.")
            return
        
        logger.info("Refreshing authentication token")
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        self._make_request(
            url=config.firebase_refresh_url,
            method="POST",
            data=payload,
            callback=self._handle_refresh_response,
            error_callback=lambda error: logger.error(f"Token refresh failed: {error}")
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
        
        # Connect response handler
        reply.finished.connect(lambda: self._handle_network_reply(reply, callback, error_callback))
    
    def _handle_network_reply(self, reply: QNetworkReply, 
                             callback: Optional[Callable] = None,
                             error_callback: Optional[Callable] = None) -> None:
        """Handle network reply with proper error checking."""
        try:
            if reply.error() != QNetworkReply.NoError:
                error_msg = reply.errorString()
                try:
                    error_data = json.loads(bytes(reply.readAll()).decode('utf-8'))
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass
                
                logger.error(f"Network error: {error_msg}")
                if error_callback:
                    error_callback(error_msg)
            else:
                response_data = json.loads(bytes(reply.readAll()).decode('utf-8'))
                if callback:
                    callback(response_data)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response: {e}"
            logger.error(error_msg)
            if error_callback:
                error_callback(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg)
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
            
            logger.info("Login successful")
            self.login_success.emit()
            
        except Exception as e:
            error_msg = f"Login processing error: {e}"
            logger.error(error_msg)
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
                
                logger.info("Token refreshed successfully")
                
                # Emit login_success signal to update UI
                self.login_success.emit()
            else:
                logger.error("Token refresh failed: No token in response")
                # Emit login_failed signal to update UI
                self.login_failed.emit("Token refresh failed")
                
        except Exception as e:
            logger.error(f"Token refresh processing error: {e}")
            # Emit login_failed signal to update UI
            self.login_failed.emit(f"Token refresh error: {e}")
    
    def _handle_api_response(self, endpoint: str, response_data: Dict[str, Any], 
                           callback: Optional[Callable] = None) -> None:
        """Handle API response from Needle Digital service."""
        logger.info(f"API response received for endpoint: {endpoint}")
        
        if callback:
            callback(response_data)
        
        self.api_response_received.emit(endpoint, response_data)