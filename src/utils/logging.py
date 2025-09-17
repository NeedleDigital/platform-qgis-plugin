"""
Logging utilities for the ND Data Importer plugin.
Uses New Relic cloud logging API with crash-safe initialization.
"""

import json
import logging
import sys
from typing import Optional


# Global variables - no Qt objects created during import
_newrelic_logger = None
_logging_enabled = False  # TEMPORARILY DISABLE ALL LOGGING TO FIX CRASHES


class SafeNewRelicLogger:
    """New Relic cloud logger with delayed Qt initialization."""

    def __init__(self):
        import os
        from pathlib import Path

        self.network_manager = None
        self.api_url = "https://log-api.eu.newrelic.com/log/v1"

        # Load environment variables from .env file if it exists
        self._load_env_file()

        # Try to get API key from environment variable, fallback to empty string
        self.api_key = os.getenv("NEW_RELIC_API_KEY", "")
        self._qt_available = False

    def _load_env_file(self):
        """Load environment variables from .env file if it exists."""
        import os
        from pathlib import Path

        try:
            # Get plugin root directory (go up from utils to root)
            plugin_root = Path(__file__).parent.parent.parent
            env_file = plugin_root / ".env"

            if env_file.exists():
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
        except Exception as e:
            # Silently fail if env file can't be loaded
            print(f"Note: Could not load .env file: {e}")

    def _init_qt_components(self):
        """Initialize Qt components only when needed."""
        if self._qt_available:
            return True

        try:
            # Import Qt classes only when actually needed
            from qgis.PyQt.QtCore import QObject, QUrl, QByteArray
            from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

            # Store Qt classes as instance variables
            self.QObject = QObject
            self.QUrl = QUrl
            self.QByteArray = QByteArray
            self.QNetworkAccessManager = QNetworkAccessManager
            self.QNetworkRequest = QNetworkRequest
            self.QNetworkReply = QNetworkReply

            # Create network manager
            self.network_manager = QNetworkAccessManager()
            self._qt_available = True
            return True

        except Exception as e:
            print(f"Qt components not available for logging: {e}")
            return False

    def send_log(self, message: str, logtype: str = "info"):
        """Send log message to New Relic."""
        global _logging_enabled

        if not _logging_enabled:
            return

        try:
            # Try to initialize Qt components if not already done
            if not self._init_qt_components():
                print(f"📝 New Relic logging unavailable: {message}")
                return

            payload = {
                "message": message,
                "logtype": logtype
            }

            request = self.QNetworkRequest(self.QUrl(self.api_url))
            request.setRawHeader(self.QByteArray(b"Api-Key"), self.QByteArray(self.api_key.encode()))
            request.setRawHeader(self.QByteArray(b"Content-Type"), self.QByteArray(b"application/json"))

            data = self.QByteArray(json.dumps(payload).encode('utf-8'))
            reply = self.network_manager.post(request, data)

            print(f"📤 Sending to New Relic [{logtype.upper()}]: {message}")
            reply.finished.connect(lambda: self._handle_response(reply, message, logtype))

        except Exception as e:
            print(f"❌ New Relic logging failed: {e}")
            # Disable logging to prevent repeated crashes
            _logging_enabled = False

    def _handle_response(self, reply, original_message: str, logtype: str):
        """Handle the response from New Relic API."""
        try:
            if reply.error() == self.QNetworkReply.NoError:
                print(f"✅ New Relic log sent successfully [{logtype.upper()}]: {original_message}")
            else:
                error_msg = reply.errorString()
                print(f"❌ New Relic API error: {error_msg}")
        except Exception as e:
            print(f"❌ Error handling New Relic response: {e}")
        finally:
            reply.deleteLater()


def get_newrelic_logger():
    """Get the global New Relic logger instance."""
    global _newrelic_logger
    if _newrelic_logger is None:
        try:
            _newrelic_logger = SafeNewRelicLogger()
        except Exception as e:
            print(f"Failed to create New Relic logger: {e}")
            return None
    return _newrelic_logger


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a basic Python logger (no New Relic integration for standard logger to avoid crashes).
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Use simple console handler to avoid Qt crashes
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        log_level = getattr(logging, (level or 'DEBUG').upper(), logging.DEBUG)
        logger.setLevel(log_level)
    return logger


# Simple helper functions that don't crash
def log_api_request(endpoint: str, params: dict, logger: logging.Logger = None) -> None:
    """Log API request details - console only to prevent crashes."""
    message = f"API Request - Endpoint: {endpoint}, Params: {params}"
    try:
        if logger:
            logger.info(message)
        else:
            print(message)  # Simple console output, no network calls
    except Exception:
        pass  # Silently fail to prevent crashes


def log_api_response(endpoint: str, success: bool, data_count: int, logger: logging.Logger = None) -> None:
    """Log API response details to New Relic."""
    status = "SUCCESS" if success else "FAILED"
    message = f"API Response - Endpoint: {endpoint}, Status: {status}, Records: {data_count}"
    logtype = "info" if success else "error"

    try:
        if logger:
            if success:
                logger.info(message)
            else:
                logger.error(message)
        nr_logger = get_newrelic_logger()
        if nr_logger:
            nr_logger.send_log(message, logtype)
    except Exception:
        pass  # Silently fail to prevent crashes


def log_user_action(action: str, details: str, logger: logging.Logger = None) -> None:
    """Log user actions to New Relic."""
    message = f"User Action - {action}: {details}"
    try:
        if logger:
            logger.info(message)
        nr_logger = get_newrelic_logger()
        if nr_logger:
            nr_logger.send_log(message, "info")
    except Exception:
        pass  # Silently fail to prevent crashes


def log_error(error_message: str, context: str = "", logger: logging.Logger = None) -> None:
    """Log error messages to New Relic."""
    message = f"Error in {context}: {error_message}" if context else f"Error: {error_message}"
    try:
        if logger:
            logger.error(message)
        nr_logger = get_newrelic_logger()
        if nr_logger:
            nr_logger.send_log(message, "error")
    except Exception:
        pass  # Silently fail to prevent crashes


def log_warning(warning_message: str, context: str = "", logger: logging.Logger = None) -> None:
    """Log warning messages to New Relic."""
    message = f"Warning in {context}: {warning_message}" if context else f"Warning: {warning_message}"
    try:
        if logger:
            logger.warning(message)
        nr_logger = get_newrelic_logger()
        if nr_logger:
            nr_logger.send_log(message, "warning")
    except Exception:
        pass  # Silently fail to prevent crashes