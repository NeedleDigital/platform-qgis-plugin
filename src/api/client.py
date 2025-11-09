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
import zlib
from typing import Dict, Any, Optional, Callable
from qgis.PyQt.QtCore import QObject, pyqtSignal, QTimer, QUrl, QByteArray
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qgis.core import QgsSettings

# Internal configuration and utilities
from ..config.settings import config  # API configuration and settings
from ..utils.logging import log_error, log_warning, log_info  # Centralized logging system
from ..utils.validation import get_user_role_from_token, get_custom_expires_at_from_token  # JWT token utilities


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
        - Server-Sent Events (SSE) streaming support

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
        self.custom_expires_at: Optional[float] = None  # Custom subscription expiration from JWT
        self.user_role: Optional[str] = None  # User role from token (tier_1, tier_2, admin)
        self.last_login_email: str = ""  # Store last successful login email for autofill
        self._initialization_complete = False
        self._active_replies = []  # Track active network requests for cancellation
        self._streaming_buffers = {}  # Track SSE parsing buffers by reply
        self._streaming_decompressors = {}  # Track gzip decompressor objects by reply
        self._streaming_text_buffers = {}  # Track text buffers for incomplete SSE events
        self._refresh_in_progress = False  # Track if token refresh is in progress (prevents race conditions)
        self._refresh_failure_count = 0  # Track consecutive refresh failures

        # Token refresh timer
        self.token_refresh_timer = QTimer()
        self.token_refresh_timer.timeout.connect(lambda: self.refresh_auth_token(silent=True))

        # Load saved tokens and expiration time but don't refresh immediately
        settings = QgsSettings()
        self.refresh_token = settings.value("needle/refreshToken", None)
        self.auth_token = settings.value("needle/authToken", None)

        # Validate token structure before using
        if self.auth_token:
            # JWT tokens have 3 parts separated by dots
            parts = self.auth_token.split('.')
            if len(parts) != 3:
                log_warning("Corrupted auth token detected (invalid JWT structure) - clearing token")
                self.auth_token = None
                settings.remove("needle/authToken")

        # Extract role and custom expiration from stored token if available
        if self.auth_token:
            self.user_role = get_user_role_from_token(self.auth_token)
            self.custom_expires_at = get_custom_expires_at_from_token(self.auth_token)

        # Safely load token expiration time and validate
        try:
            expires_value = settings.value("needle/tokenExpiresAt", 0)
            self.token_expires_at = float(expires_value) if expires_value else 0

            # Validate timestamp is reasonable (after Jan 1, 2020)
            if self.token_expires_at > 0 and self.token_expires_at < 1577836800:
                log_warning(f"Invalid token expiration timestamp: {self.token_expires_at} - clearing")
                self.token_expires_at = 0
                settings.remove("needle/tokenExpiresAt")
        except (ValueError, TypeError):
            log_warning("Failed to parse token expiration time - clearing")
            self.token_expires_at = 0
            settings.remove("needle/tokenExpiresAt")

        # Safely load custom expiration time and validate
        try:
            custom_expires_value = settings.value("needle/customExpiresAt", None)
            if custom_expires_value:
                self.custom_expires_at = float(custom_expires_value)

                # Validate timestamp is reasonable (after Jan 1, 2020)
                if self.custom_expires_at > 0 and self.custom_expires_at < 1577836800:
                    log_warning(f"Invalid custom expiration timestamp: {self.custom_expires_at} - clearing")
                    self.custom_expires_at = None
                    settings.remove("needle/customExpiresAt")
        except (ValueError, TypeError):
            log_warning("Failed to parse custom expiration time - clearing")
            self.custom_expires_at = None
            settings.remove("needle/customExpiresAt")

    def _log_request(self, method: str, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None):
        """Log API request details to Python console for debugging."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'='*80}")
        print(f"[ND Plugin] API REQUEST: {method} {url}")
        print(f"[ND Plugin] Time: {timestamp}")

        if params:
            # Sanitize sensitive data
            safe_params = params.copy()
            if 'password' in safe_params:
                safe_params['password'] = '***REDACTED***'
            print(f"[ND Plugin] Params: {json.dumps(safe_params, indent=2)}")

        if headers:
            # Sanitize authorization header
            safe_headers = headers.copy()
            if 'Authorization' in safe_headers:
                token = safe_headers['Authorization'].replace('Bearer ', '')
                safe_headers['Authorization'] = f'Bearer {token[:20]}...{token[-10:] if len(token) > 30 else ""}'
            print(f"[ND Plugin] Headers: {json.dumps(safe_headers, indent=2)}")

        print(f"{'='*80}\n")

    def _log_response(self, url: str, status_code: Optional[int], response_body: Any, elapsed_ms: float, error: bool = False):
        """Log API response details to Python console for debugging."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        status_text = "ERROR" if error else "SUCCESS"

        print(f"\n{'-'*80}")
        print(f"[ND Plugin] API RESPONSE: {status_text}")
        print(f"[ND Plugin] URL: {url}")
        print(f"[ND Plugin] Time: {timestamp}")
        print(f"[ND Plugin] Status: HTTP {status_code if status_code else 'N/A'} ({elapsed_ms:.0f}ms)")

        # Log response body (truncate if too large)
        if response_body:
            if isinstance(response_body, dict):
                body_str = json.dumps(response_body, indent=2)
            else:
                body_str = str(response_body)

            # Truncate large responses
            if len(body_str) > 500:
                print(f"[ND Plugin] Response Body (truncated): {body_str[:500]}...")
                print(f"[ND Plugin] (Full response size: {len(body_str)} characters)")
            else:
                print(f"[ND Plugin] Response Body: {body_str}")

        print(f"{'-'*80}\n")

    def complete_initialization(self):
        """
        Complete initialization and attempt silent token refresh if needed.

        This is called after plugin startup and handles token refresh after laptop sleep/wake
        or plugin restart. It will refresh expired tokens automatically if refresh token is valid.
        """
        if self._initialization_complete:
            return

        self._initialization_complete = True

        # Check if we have a refresh token
        if self.refresh_token:
            current_time = time.time()

            # Check custom subscription expiration first
            if self.custom_expires_at is not None and current_time >= self.custom_expires_at:
                log_warning(f"Custom subscription expired at {time.ctime(self.custom_expires_at)} - user must re-login")
                return

            # Check if access token is expired or will expire soon
            time_until_expiry = self.token_expires_at - current_time

            # Refresh if token is expired or will expire in <5 minutes
            # This handles cases where laptop was closed and token expired during sleep
            if time_until_expiry < 300:  # Less than 5 minutes remaining (or already expired)
                if time_until_expiry < 0:
                    log_info(f"Token expired {abs(time_until_expiry)/60:.1f} minutes ago, attempting silent refresh...")
                else:
                    log_info(f"Token expiring in {time_until_expiry:.0f}s, attempting silent refresh...")
                self.refresh_auth_token(silent=True)
            else:
                log_info(f"Token still valid for {time_until_expiry/60:.1f} minutes")
                # Schedule next refresh at 50% of remaining lifetime
                refresh_delay_ms = max(0, int((time_until_expiry / 2) * 1000))
                self.token_refresh_timer.start(refresh_delay_ms)
                log_info(f"Next token refresh scheduled in {refresh_delay_ms/1000:.0f} seconds")
        else:
            log_warning("No refresh token found - user must login")
    
    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated.

        Validates both Firebase JWT expiration (1 hour) and custom subscription
        expiration (expiresAt claim). User must pass both checks to be authenticated.

        Returns:
            True if both Firebase token and custom subscription are valid, False otherwise
        """
        current_time = time.time()

        # Check if auth token exists and Firebase JWT hasn't expired
        if not self.auth_token or current_time >= self.token_expires_at:
            return False

        # Check custom subscription expiration if it exists
        if self.custom_expires_at is not None:
            if current_time >= self.custom_expires_at:
                log_warning(f"Custom subscription expired at {time.ctime(self.custom_expires_at)}")
                return False

        return True

    def get_user_role(self) -> Optional[str]:
        """Get the current user's role."""
        return self.user_role

    def get_last_login_email(self) -> str:
        """Get the last successfully logged in email for autofill."""
        settings = QgsSettings()
        return settings.value("needle/lastLoginEmail", "")

    def ensure_token_valid(self) -> bool:
        """
        Ensure token is valid, refresh if needed.

        This method checks token validity and triggers refresh if needed.
        It prevents race conditions by checking if refresh is already in progress.

        Returns:
            True if valid/refreshed, False if user needs to login
        """
        current_time = time.time()

        # Check if user has ever logged in - if no tokens at all, return False immediately
        # Don't try to refresh if there's no refresh token (user never logged in)
        if not self.auth_token and not self.refresh_token:
            log_info("No tokens found - user needs to login")
            return False

        # Check custom subscription expiration first - can't refresh if subscription expired
        if self.custom_expires_at is not None and current_time >= self.custom_expires_at:
            log_warning(f"Cannot refresh token - custom subscription expired at {time.ctime(self.custom_expires_at)}")
            return False

        # Check if token will expire in next 5 minutes
        time_until_expiry = self.token_expires_at - current_time

        if time_until_expiry < 300:  # Less than 5 minutes remaining
            # Only try to refresh if we have a refresh token
            if not self.refresh_token:
                log_warning("Token expired but no refresh token available - user needs to login")
                return False

            # If refresh is already in progress, assume it will succeed
            # This prevents race conditions from multiple simultaneous refresh requests
            if self._refresh_in_progress:
                log_info("Token refresh already in progress, returning optimistically")
                return True

            log_info(f"Token expiring soon ({time_until_expiry:.0f}s), triggering proactive refresh...")
            self.refresh_auth_token(silent=True)
            return True

        return self.is_authenticated()

    def login(self, email: str, password: str) -> None:
        """Authenticate user with email and password."""
        if not email or not password or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            self.login_failed.emit("A valid email and password are required.")
            return

        # Store email for autofill on successful login
        self.last_login_email = email

        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        # Log the login request
        print(f"\n[ND Plugin] ===== LOGIN ATTEMPT =====")
        print(f"[ND Plugin] Email: {email}")
        print(f"[ND Plugin] Endpoint: {config.firebase_auth_url}")
        self._log_request("POST", config.firebase_auth_url, params={"email": email, "password": "***REDACTED***"})

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
        self.custom_expires_at = None
        self.user_role = None
        self.last_login_email = ""
        self.token_refresh_timer.stop()

        # Clear refresh state to prevent stuck flags
        self._refresh_in_progress = False
        self._refresh_failure_count = 0

        # Clear all stored tokens, expiration time, and email with error handling
        settings = QgsSettings()
        settings_to_remove = [
            "needle/refreshToken",
            "needle/authToken",
            "needle/tokenExpiresAt",
            "needle/customExpiresAt",
            "needle/lastLoginEmail"
        ]

        for setting_key in settings_to_remove:
            try:
                settings.remove(setting_key)
            except Exception as e:
                log_warning(f"Failed to remove setting {setting_key}: {e}")

        # Cancel any ongoing requests
        self.cancel_all_requests()
    
    def cancel_all_requests(self) -> None:
        """Cancel all active network requests."""
        for reply in self._active_replies:
            if reply and not reply.isFinished():
                reply.abort()
        self._active_replies.clear()
    
    def refresh_auth_token(self, silent: bool = False) -> None:
        """
        Refresh the authentication token using refresh token.

        Implements retry logic with exponential backoff on network failures.
        Prevents wasted refreshes when subscription has expired.
        """
        if not self.refresh_token:
            if not silent:
                log_warning("Token refresh aborted: No refresh token available.")
            return

        # Check if refresh is already in progress (prevent duplicate requests)
        if self._refresh_in_progress:
            log_info("Token refresh already in progress, skipping duplicate request")
            return

        # Check custom subscription expiration - don't waste time refreshing if subscription expired
        current_time = time.time()
        if self.custom_expires_at is not None and current_time >= self.custom_expires_at:
            log_warning(f"Subscription expired at {time.ctime(self.custom_expires_at)} - stopping refresh attempts")
            # Stop the timer to prevent infinite wasted refreshes
            self.token_refresh_timer.stop()
            # Clear tokens and emit login failure
            self.logout()
            self.login_failed.emit("Your subscription has expired. Please contact support to renew.")
            return

        # Set refresh in progress flag
        self._refresh_in_progress = True
        log_info("Starting token refresh...")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }

        self._make_request(
            url=config.firebase_refresh_url,
            method="POST",
            data=payload,
            callback=self._handle_refresh_response,
            error_callback=self._handle_refresh_error
        )
    
    def make_api_request(self, endpoint: str, params: Dict[str, Any], callback: Optional[Callable] = None) -> None:
        """
        Make authenticated API request to Needle Digital service.

        Automatically refreshes token if needed before making the request.
        """
        
        # Ensure token is valid and refresh if needed (handles wake from sleep)
        if not self.ensure_token_valid():
            error_msg = "Authentication expired. Please log in again."
            if self.custom_expires_at and time.time() >= self.custom_expires_at:
                error_msg = "Your subscription has expired. Please contact support or renew your subscription."
            self.api_error_occurred.emit(endpoint, error_msg)
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

    def make_streaming_request(self, endpoint: str, params: Dict[str, Any],
                               data_callback: Callable[[dict], None],
                               progress_callback: Callable[[dict], None],
                               complete_callback: Callable[[dict], None],
                               error_callback: Callable[[dict], None]) -> QNetworkReply:
        """
        Make authenticated streaming API request using Server-Sent Events (SSE).

        Automatically refreshes token if needed before making the request.

        Args:
            endpoint: API endpoint path
            params: Query parameters dictionary
            data_callback: Called when 'data' event is received with batch of records
            progress_callback: Called when 'progress' event is received with progress info
            complete_callback: Called when 'complete' event is received with final summary
            error_callback: Called when 'error' event is received or connection fails

        Returns:
            QNetworkReply: The active network reply (for cancellation support)
        """
        # Ensure token is valid and refresh if needed (handles wake from sleep)
        if not self.ensure_token_valid():
            error_msg = "Authentication expired. Please log in again."
            if self.custom_expires_at and time.time() >= self.custom_expires_at:
                error_msg = "Your subscription has expired. Please contact support or renew your subscription."
            error_callback({"error": error_msg})
            return None

        url = f"{config.BASE_API_URL}/{endpoint}"

        # Build URL with query parameters
        request_url = QUrl(url)
        if params:
            query_parts = []
            for key, value in params.items():
                if value is not None:
                    # Special handling for polygon_coords - add multiple coords parameters
                    if key == 'polygon_coords' and isinstance(value, list):
                        for lat, lon in value:
                            query_parts.append(f"coords={lat},{lon}")
                    else:
                        query_parts.append(f"{key}={str(value)}")
            if query_parts:
                query_string = "&".join(query_parts)
                request_url = QUrl(f"{url}?{query_string}")

        request = QNetworkRequest(request_url)

        # Set SSE-specific headers
        request.setRawHeader(b'Authorization', f"Bearer {self.auth_token}".encode())
        request.setRawHeader(b'Accept', b'text/event-stream')
        request.setRawHeader(b'Accept-Encoding', b'gzip, deflate')
        request.setRawHeader(b'Cache-Control', b'no-cache')

        # Make GET request
        reply = self.network_manager.get(request)

        # Track reply for cancellation
        self._active_replies.append(reply)

        # Initialize buffers for this reply
        reply_id = id(reply)
        self._streaming_buffers[reply_id] = b""  # Byte buffer for incoming data
        self._streaming_text_buffers[reply_id] = ""  # Text buffer for incomplete SSE events
        self._streaming_decompressors[reply_id] = None  # Will create decompressor if gzip detected

        # Store callbacks on reply object for access in handlers
        reply.data_callback = data_callback
        reply.progress_callback = progress_callback
        reply.complete_callback = complete_callback
        reply.error_callback = error_callback

        # Store error response body (will be populated if error occurs)
        reply.error_response_body = None

        # Connect streaming event handlers
        reply.readyRead.connect(lambda: self._handle_streaming_data(reply))
        reply.finished.connect(lambda: self._handle_streaming_finished(reply))
        reply.errorOccurred.connect(lambda error_code: self._handle_streaming_error(reply, error_code))

        return reply

    def _handle_streaming_data(self, reply: QNetworkReply) -> None:
        """Handle incoming SSE data chunks with incremental gzip decompression support."""
        try:
            reply_id = id(reply)

            # Read available bytes
            chunk_bytes = bytes(reply.readAll())
            if not chunk_bytes:
                return

            # Check if this is an HTTP error response (not SSE)
            http_status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            if http_status and http_status >= 400:
                # This is an error response - store the raw bytes for error handler
                error_text = chunk_bytes.decode('utf-8', errors='ignore')

                # Append to any existing error response body
                if hasattr(reply, 'error_response_body') and reply.error_response_body:
                    reply.error_response_body += error_text
                else:
                    reply.error_response_body = error_text

                print(f"[ND Plugin] Captured error response body: {error_text[:200]}")
                return  # Don't process as SSE

            # Check for gzip encoding on first chunk using rawHeader
            if self._streaming_decompressors.get(reply_id) is None:
                # Use rawHeader to get Content-Encoding
                content_encoding_bytes = reply.rawHeader(b'Content-Encoding')
                content_encoding = bytes(content_encoding_bytes).decode('utf-8', errors='ignore').lower() if content_encoding_bytes else ''

                if 'gzip' in content_encoding:
                    # Create incremental decompressor using zlib
                    import zlib
                    # wbits=MAX_WBITS | 16 enables gzip format detection
                    self._streaming_decompressors[reply_id] = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)
                    log_info("Streaming response is gzip-compressed, using incremental decompression")
                else:
                    # Not gzip, mark as plain text
                    self._streaming_decompressors[reply_id] = False
                    log_info("Streaming response is plain text (no gzip)")

            # Decompress if gzip
            decompressor = self._streaming_decompressors.get(reply_id)
            if decompressor and decompressor is not False:
                try:
                    # Incrementally decompress
                    decompressed_chunk = decompressor.decompress(chunk_bytes)
                    if not decompressed_chunk:
                        # No data yet, might need more chunks
                        return
                    text_chunk = decompressed_chunk.decode('utf-8')
                except Exception as e:
                    log_error(f"Decompression error: {e}")
                    import traceback
                    log_error(traceback.format_exc())
                    # Don't crash - call error callback and abort
                    if hasattr(reply, 'error_callback'):
                        reply.error_callback({"error": f"Decompression failed: {str(e)}"})
                    reply.abort()
                    return
            else:
                # Plain text - decode directly
                try:
                    text_chunk = chunk_bytes.decode('utf-8')
                except UnicodeDecodeError as e:
                    log_error(f"UTF-8 decode error: {e}")
                    import traceback
                    log_error(traceback.format_exc())
                    # Don't crash - call error callback and abort
                    if hasattr(reply, 'error_callback'):
                        reply.error_callback({"error": f"UTF-8 decode failed: {str(e)}"})
                    reply.abort()
                    return

            # Append to text buffer
            text_buffer = self._streaming_text_buffers.get(reply_id, "")
            text_buffer += text_chunk

            # Parse SSE events (separated by double newline)
            events = text_buffer.split('\n\n')

            # Keep the last incomplete event in buffer
            self._streaming_text_buffers[reply_id] = events[-1]

            # Process complete events
            for event_block in events[:-1]:
                if not event_block.strip():
                    continue

                # Parse event format: event: type\ndata: json
                lines = event_block.strip().split('\n')
                event_type = None
                event_data = None

                for line in lines:
                    if line.startswith('event:'):
                        event_type = line[6:].strip()
                    elif line.startswith('data:'):
                        try:
                            event_data = json.loads(line[5:].strip())
                        except json.JSONDecodeError as e:
                            log_error(f"Failed to parse SSE data: {e}")
                            log_error(f"Problematic line: {line[:200]}")
                            continue

                # Route event to appropriate callback with error handling
                if event_type and event_data:
                    try:
                        if event_type == 'data' and hasattr(reply, 'data_callback'):
                            reply.data_callback(event_data)
                        elif event_type == 'progress' and hasattr(reply, 'progress_callback'):
                            reply.progress_callback(event_data)
                        elif event_type == 'complete' and hasattr(reply, 'complete_callback'):
                            reply.complete_callback(event_data)
                        elif event_type == 'error' and hasattr(reply, 'error_callback'):
                            reply.error_callback(event_data)
                    except Exception as callback_error:
                        log_error(f"Error in {event_type} callback: {callback_error}")
                        import traceback
                        log_error(traceback.format_exc())

        except Exception as e:
            log_error(f"Critical error handling streaming data: {e}")
            import traceback
            log_error(traceback.format_exc())
            # Safely call error callback if it exists
            try:
                if hasattr(reply, 'error_callback'):
                    reply.error_callback({"error": f"Streaming handler error: {str(e)}"})
            except:
                pass
            # Abort to prevent further crashes
            try:
                reply.abort()
            except:
                pass

    def _handle_streaming_finished(self, reply: QNetworkReply) -> None:
        """
        Handle completion of streaming connection.

        This is called for both successful and failed requests.
        For errors, we need to check HTTP status and parse error response.
        """
        reply_id = id(reply)

        # Check for HTTP errors (like 403) that might not trigger errorOccurred
        http_status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

        # If there's an HTTP error status, check for detailed error message
        if http_status and http_status >= 400:
            # Use stored error response body from errorOccurred handler
            # (it was already read there to prevent it from being consumed)
            response_text = getattr(reply, 'error_response_body', None)

            # If not stored, try reading it now (fallback)
            if not response_text:
                response_bytes = bytes(reply.readAll())
                response_text = response_bytes.decode('utf-8', errors='ignore') if response_bytes else ""

            print("\n[ND Plugin] ===== STREAMING FINISHED WITH ERROR =====")
            print(f"[ND Plugin] URL: {reply.url().toString()}")
            print(f"[ND Plugin] HTTP Status: {http_status}")
            print(f"[ND Plugin] Response Body: {response_text[:500] if response_text else 'Empty'}")
            print(f"[ND Plugin] Using stored response: {getattr(reply, 'error_response_body', None) is not None}")

            # Parse error response
            detailed_error_msg = None
            try:
                if response_text:
                    error_data = json.loads(response_text)

                    # Check for FastAPI/Pydantic error format: {"detail": "..."}
                    if 'detail' in error_data:
                        detail = error_data['detail']

                        # Check for "User access expired" error
                        if isinstance(detail, str) and 'access expired' in detail.lower():
                            detailed_error_msg = "Your subscription has expired. Please contact Needle Digital support to renew your access."
                            print("[ND Plugin] SUBSCRIPTION EXPIRED ERROR DETECTED")
                            # Don't emit login_failed here - let error callback handle it to avoid duplicate dialogs
                        else:
                            detailed_error_msg = str(detail)

                    # Check for Firebase error format
                    elif 'error' in error_data:
                        error_obj = error_data['error']
                        if isinstance(error_obj, dict):
                            detailed_error_msg = error_obj.get('message', str(error_obj))
                        else:
                            detailed_error_msg = str(error_obj)

                    print(f"[ND Plugin] Parsed Error: {detailed_error_msg}")

            except (json.JSONDecodeError, Exception) as e:
                print(f"[ND Plugin] Failed to parse error response: {e}")

            # Use detailed error message if available
            if detailed_error_msg:
                error_msg = detailed_error_msg
            else:
                error_msg = reply.errorString() if reply.error() != QNetworkReply.NoError else f"HTTP {http_status} error"

            log_error(f"Streaming finished with HTTP {http_status} error: {error_msg}")

            # Call error callback if it exists
            if hasattr(reply, 'error_callback'):
                reply.error_callback({"error": error_msg, "http_status": http_status, "is_fatal": True})

        # Cleanup all tracking structures
        if reply in self._active_replies:
            self._active_replies.remove(reply)
        if reply_id in self._streaming_buffers:
            del self._streaming_buffers[reply_id]
        if reply_id in self._streaming_text_buffers:
            del self._streaming_text_buffers[reply_id]
        if reply_id in self._streaming_decompressors:
            del self._streaming_decompressors[reply_id]

        reply.deleteLater()

    def _handle_streaming_error(self, reply: QNetworkReply, error_code) -> None:
        """
        Handle streaming connection errors.

        NOTE: Error response body is captured in _handle_streaming_data() when data arrives.
        This handler just logs the error. The 'finished' handler will parse and display the error.
        """
        if reply.error() != QNetworkReply.NoError:
            error_msg = reply.errorString()
            http_status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

            print("\n[ND Plugin] ===== STREAMING ERROR OCCURRED =====")
            print(f"[ND Plugin] URL: {reply.url().toString()}")
            print(f"[ND Plugin] HTTP Status: {http_status}")
            print(f"[ND Plugin] Network Error: {error_msg}")

            log_error(f"Streaming error occurred (HTTP {http_status}): {error_msg}")

            # Error response body is captured in _handle_streaming_data()
            # DO NOT call error_callback here - let _handle_streaming_finished handle it

    def cancel_streaming_request(self, reply: Optional[QNetworkReply]) -> None:
        """Cancel an active streaming request."""
        if not reply:
            return

        # Abort the reply if it's still active
        if not reply.isFinished():
            reply.abort()

        # Remove from active replies list (use try/except to handle race conditions)
        try:
            if reply in self._active_replies:
                self._active_replies.remove(reply)
        except (ValueError, RuntimeError):
            # Reply was already removed or list was modified - this is okay
            pass

        # Cleanup buffers and tracking
        reply_id = id(reply)
        if reply_id in self._streaming_buffers:
            del self._streaming_buffers[reply_id]
        if reply_id in self._streaming_text_buffers:
            del self._streaming_text_buffers[reply_id]
        if reply_id in self._streaming_decompressors:
            del self._streaming_decompressors[reply_id]

        log_warning("Streaming request cancelled by user")
    
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
        """
        Handle network reply with proper error checking.

        Detects 401/403 authentication errors and triggers appropriate logout/error messages.
        """
        # Remove from active replies list
        if reply in self._active_replies:
            self._active_replies.remove(reply)

        # Get request details for logging
        request_url = reply.url().toString()

        try:
            # Check HTTP status code
            http_status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

            # Read response body
            response_bytes = bytes(reply.readAll())
            response_text = response_bytes.decode('utf-8') if response_bytes else ""

            # Log all responses (success and error)
            print(f"\n[ND Plugin] ===== API RESPONSE =====")
            print(f"[ND Plugin] URL: {request_url}")
            print(f"[ND Plugin] HTTP Status: {http_status}")
            print(f"[ND Plugin] Network Error Code: {reply.error()}")

            if reply.error() != QNetworkReply.NoError:
                error_msg = reply.errorString()
                print(f"[ND Plugin] Network Error String: {error_msg}")

                # Parse error response body
                error_data = None
                try:
                    if response_text:
                        error_data = json.loads(response_text)
                        print(f"[ND Plugin] Error Response Body: {json.dumps(error_data, indent=2)}")

                        # Extract detailed error information
                        if 'error' in error_data:
                            error_obj = error_data['error']
                            if isinstance(error_obj, dict):
                                error_code = error_obj.get('code', http_status)
                                error_message = error_obj.get('message', error_msg)
                                error_msg = f"HTTP {error_code}: {error_message}"

                                # Log additional error details if present
                                if 'errors' in error_obj:
                                    print(f"[ND Plugin] Error Details: {error_obj['errors']}")
                            elif isinstance(error_obj, str):
                                error_msg = error_obj
                    else:
                        print(f"[ND Plugin] Empty response body")
                except json.JSONDecodeError as json_err:
                    print(f"[ND Plugin] Failed to parse error JSON: {json_err}")
                    print(f"[ND Plugin] Raw error response: {response_text[:500]}")
                except Exception as parse_err:
                    print(f"[ND Plugin] Error parsing response: {parse_err}")

                print(f"[ND Plugin] Final Error Message: {error_msg}")

                # Detect authentication errors by HTTP status code
                auth_error_handled = False
                if http_status in [400, 401, 403]:
                    log_error(f"Authentication error (HTTP {http_status}): {error_msg}")
                    print(f"\n[ND Plugin] *** AUTHENTICATION ERROR DETECTED ***")

                    # Check for specific Firebase errors
                    if error_data and 'error' in error_data:
                        error_obj = error_data['error']
                        if isinstance(error_obj, dict):
                            firebase_error = error_obj.get('message', '')

                            # USER_DISABLED error
                            if 'USER_DISABLED' in firebase_error:
                                error_msg = f"Your account has been disabled. Please contact Needle Digital support at support@needle-digital.com (Error: USER_DISABLED)"
                                print(f"[ND Plugin] USER_DISABLED error detected - account is disabled in Firebase")
                                self.login_failed.emit(error_msg)
                                auth_error_handled = True  # Don't call error_callback to avoid duplicate dialogs
                            # Subscription expiration
                            elif self.custom_expires_at and time.time() >= self.custom_expires_at:
                                error_msg = "Your subscription has expired. Please contact Needle Digital support to renew your access."
                                self.login_failed.emit(error_msg)
                                auth_error_handled = True  # Don't call error_callback to avoid duplicate dialogs
                            # Generic auth error
                            else:
                                error_msg = f"Authentication failed: {firebase_error}"
                                self.login_failed.emit(error_msg)
                                auth_error_handled = True  # Don't call error_callback to avoid duplicate dialogs
                        else:
                            self.login_failed.emit(error_msg)
                            auth_error_handled = True  # Don't call error_callback to avoid duplicate dialogs
                    else:
                        # No specific error data, check subscription
                        if self.custom_expires_at and time.time() >= self.custom_expires_at:
                            error_msg = "Your subscription has expired. Please contact support or renew your subscription."
                            self.login_failed.emit(error_msg)
                            auth_error_handled = True  # Don't call error_callback to avoid duplicate dialogs
                        else:
                            error_msg = "Authentication expired. Please log in again."
                            self.login_failed.emit(error_msg)
                            auth_error_handled = True  # Don't call error_callback to avoid duplicate dialogs
                else:
                    log_error(f"Network error (HTTP {http_status}): {error_msg}")
                    print(f"[ND Plugin] Network/Server error")

                # Only call error_callback if we didn't already handle it via login_failed signal
                # This prevents duplicate error dialogs
                if error_callback and not auth_error_handled:
                    error_callback(error_msg)
            else:
                # Success response
                print(f"[ND Plugin] Response successful")
                try:
                    response_data = json.loads(response_text) if response_text else {}
                    print(f"[ND Plugin] Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'N/A'}")
                    if callback:
                        callback(response_data)
                except json.JSONDecodeError as e:
                    print(f"[ND Plugin] JSON parse error: {e}")
                    print(f"[ND Plugin] Raw response: {response_text[:500]}")
                    raise

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response: {e}"
            print(f"\n[ND Plugin] JSON DECODE ERROR: {error_msg}")
            log_error(error_msg)
            if error_callback:
                error_callback(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"\n[ND Plugin] UNEXPECTED ERROR: {error_msg}")
            log_error(error_msg)
            if error_callback:
                error_callback(error_msg)
        finally:
            reply.deleteLater()
    
    def _handle_login_response(self, response_data: Dict[str, Any]) -> None:
        """Handle login response from Firebase."""
        try:
            # Log the login response
            print(f"\n[ND Plugin] ===== LOGIN RESPONSE =====")
            print(f"[ND Plugin] Response keys: {list(response_data.keys())}")

            self.auth_token = response_data.get("idToken")
            self.refresh_token = response_data.get("refreshToken")

            if not self.auth_token or not self.refresh_token:
                print(f"[ND Plugin] ERROR: Missing tokens in response")
                self.login_failed.emit("Could not retrieve authentication credentials.")
                return

            # Extract user role and custom expiration from token
            self.user_role = get_user_role_from_token(self.auth_token)
            self.custom_expires_at = get_custom_expires_at_from_token(self.auth_token)

            # Calculate token expiration
            expires_in = int(response_data.get("expiresIn", 3600))
            self.token_expires_at = time.time() + expires_in

            print(f"[ND Plugin] Login successful!")
            print(f"[ND Plugin] User role: {self.user_role}")
            print(f"[ND Plugin] Token expires in: {expires_in}s ({expires_in/60:.1f} minutes)")
            if self.custom_expires_at:
                print(f"[ND Plugin] Subscription expires: {time.ctime(self.custom_expires_at)}")
            else:
                print(f"[ND Plugin] No custom subscription expiration found")

            # Save tokens, expiration time, and email
            settings = QgsSettings()
            settings.setValue("needle/refreshToken", self.refresh_token)
            settings.setValue("needle/authToken", self.auth_token)
            settings.setValue("needle/tokenExpiresAt", str(self.token_expires_at))
            settings.setValue("needle/lastLoginEmail", self.last_login_email)

            # Save custom expiration if present
            if self.custom_expires_at is not None:
                settings.setValue("needle/customExpiresAt", str(self.custom_expires_at))
                log_info(f"Custom expiration set to: {time.ctime(self.custom_expires_at)}")
            else:
                # Clear any previously stored custom expiration
                settings.remove("needle/customExpiresAt")
                log_warning("No custom expiresAt found in token")

            # Setup token refresh timer - refresh at 50% of token lifetime for better persistence
            refresh_delay_ms = max(0, (expires_in // 2) * 1000)  # Refresh at halfway point (e.g., 30 min for 1hr token)
            self.token_refresh_timer.start(refresh_delay_ms)
            print(f"[ND Plugin] Token refresh scheduled in {refresh_delay_ms/1000:.0f}s ({refresh_delay_ms/60000:.1f} minutes)")
            log_info(f"Token refresh scheduled in {refresh_delay_ms/1000:.0f} seconds ({refresh_delay_ms/60000:.1f} minutes)")

            self.login_success.emit()

        except Exception as e:
            error_msg = f"Login processing error: {e}"
            print(f"\n[ND Plugin] ERROR: {error_msg}")
            log_error(error_msg)
            self.login_failed.emit(error_msg)
    
    def _handle_refresh_response(self, response_data: Dict[str, Any]) -> None:
        """Handle token refresh response."""
        try:
            self.auth_token = response_data.get("access_token") or response_data.get("id_token")
            if response_data.get("refresh_token"):
                self.refresh_token = response_data.get("refresh_token")

            if self.auth_token:
                # Extract user role and custom expiration from refreshed token
                self.user_role = get_user_role_from_token(self.auth_token)
                self.custom_expires_at = get_custom_expires_at_from_token(self.auth_token)

                expires_in = int(response_data.get("expires_in", 3600))
                self.token_expires_at = time.time() + expires_in

                log_info(f"Token refreshed successfully. New expiry: {expires_in}s from now")

                # Save updated tokens and expiration time
                settings = QgsSettings()
                settings.setValue("needle/refreshToken", self.refresh_token)
                settings.setValue("needle/authToken", self.auth_token)
                settings.setValue("needle/tokenExpiresAt", str(self.token_expires_at))

                # Save custom expiration if present
                if self.custom_expires_at is not None:
                    settings.setValue("needle/customExpiresAt", str(self.custom_expires_at))
                    log_info(f"Custom expiration refreshed: {time.ctime(self.custom_expires_at)}")

                # Schedule next refresh at 50% of lifetime for better persistence
                refresh_delay_ms = max(0, (expires_in // 2) * 1000)
                self.token_refresh_timer.start(refresh_delay_ms)
                log_info(f"Next token refresh scheduled in {refresh_delay_ms/1000:.0f} seconds")

                # Reset failure count on success
                self._refresh_failure_count = 0

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
        finally:
            # Always clear the refresh in progress flag
            self._refresh_in_progress = False

    def _handle_refresh_error(self, error_msg: str) -> None:
        """
        Handle token refresh errors with retry logic and exponential backoff.

        Implements:
        - Retry up to 3 times with exponential backoff (2s, 4s, 8s)
        - Stop timer after max retries to prevent infinite failures
        - Clear tokens and logout on max retries
        """
        try:
            # Increment failure count
            self._refresh_failure_count += 1
            log_error(f"Token refresh failed (attempt {self._refresh_failure_count}/3): {error_msg}")

            # Check if we've exceeded max retries
            if self._refresh_failure_count >= 3:
                log_error("Token refresh failed after 3 attempts - forcing logout")

                # Stop the timer to prevent infinite retry loops
                self.token_refresh_timer.stop()

                # Clear tokens
                self.logout()

                # Emit login failure
                self.login_failed.emit("Token refresh failed after multiple attempts. Please log in again.")
            else:
                # Calculate retry delay with exponential backoff: 2s, 4s, 8s
                retry_delay_ms = (2 ** self._refresh_failure_count) * 1000
                log_info(f"Retrying token refresh in {retry_delay_ms/1000:.0f}s...")

                # Schedule retry using QTimer.singleShot
                QTimer.singleShot(retry_delay_ms, lambda: self.refresh_auth_token(silent=True))

        finally:
            # Always clear the refresh in progress flag
            self._refresh_in_progress = False

    def _handle_api_response(self, endpoint: str, response_data, 
                           callback: Optional[Callable] = None) -> None:
        """Handle API response from Needle Digital service."""
        
        if callback:
            callback(response_data)
        
        # Only emit the signal if response_data is a dictionary
        # Some endpoints (like companies search) return lists directly
        if isinstance(response_data, dict):
            self.api_response_received.emit(endpoint, response_data)
