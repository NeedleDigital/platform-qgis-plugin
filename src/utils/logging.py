"""
Logging utilities for the ND Data Importer plugin.
Uses New Relic cloud logging API with crash-safe initialization.
"""

import json
import logging
import ssl
import sys
import threading
import urllib.request
import urllib.parse
from typing import Optional


# Global variables - no Qt objects created during import
_newrelic_logger = None
_logging_enabled = True  # Thread-safe implementation, safe to enable by default


class SafeNewRelicLogger:
    """New Relic cloud logger with thread-safe HTTP implementation."""

    def __init__(self):
        import os
        from pathlib import Path

        self.api_url = "https://log-api.eu.newrelic.com/log/v1"
        self.api_key = ""
        self._env_loaded = False

        # Don't load anything during init to prevent crashes
        # Everything will be loaded on first use

    def _ensure_env_loaded(self):
        """Load environment variables from .env file if not already loaded."""
        if self._env_loaded:
            return

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
                            key = key.strip()
                            value = value.strip()
                            os.environ[key] = value

            # Load API key
            self.api_key = os.getenv("NEW_RELIC_API_KEY", "")
            self._env_loaded = True

        except Exception as e:
            # Silent fail to prevent crashes
            self._env_loaded = True

    def _send_log_async(self, message: str, logtype: str):
        """Send log message to New Relic asynchronously in a separate thread."""
        def send_request():
            try:
                payload = {
                    "message": message,
                    "logtype": logtype
                }

                data = json.dumps(payload).encode('utf-8')

                req = urllib.request.Request(
                    self.api_url,
                    data=data,
                    headers={
                        'Api-Key': self.api_key,
                        'Content-Type': 'application/json'
                    }
                )

                # Create SSL context that doesn't verify certificates (for development)
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                    status_code = response.getcode()
                    # Silent success for production - no console output needed
                    if status_code not in (200, 202):
                        # Only log actual errors to stderr, not success
                        sys.stderr.write(f"New Relic API error: HTTP {status_code}\n")

            except urllib.error.HTTPError as e:
                # Log errors to stderr for debugging without cluttering console
                if e.code == 401:
                    sys.stderr.write("New Relic API error: 401 Unauthorized - Invalid or missing API key\n")
                elif e.code == 403:
                    sys.stderr.write("New Relic API error: 403 Forbidden - API key lacks required permissions\n")
                else:
                    sys.stderr.write(f"New Relic API error: HTTP {e.code} - {e.reason}\n")
            except Exception as e:
                # Silent failure for network issues - don't spam console
                pass

        # Run in background thread to avoid blocking QGIS
        thread = threading.Thread(target=send_request, daemon=True)
        thread.start()

    def send_log(self, message: str, logtype: str = "info"):
        """Send log message to New Relic."""
        global _logging_enabled

        if not _logging_enabled:
            return

        try:
            # Load environment variables if not loaded
            self._ensure_env_loaded()

            if not self.api_key:
                return

            # Send log asynchronously to avoid blocking QGIS
            self._send_log_async(message, logtype)

        except Exception:
            # Silent fail to prevent crashes
            pass



def enable_safe_logging():
    """Enable New Relic logging - now thread-safe without Qt dependencies."""
    global _logging_enabled
    _logging_enabled = True


def disable_logging():
    """Disable New Relic logging."""
    global _logging_enabled
    _logging_enabled = False




def get_newrelic_logger():
    """Get the global New Relic logger instance."""
    global _newrelic_logger
    if _newrelic_logger is None:
        try:
            _newrelic_logger = SafeNewRelicLogger()
        except Exception:
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
        log_level = getattr(logging, (level or 'INFO').upper(), logging.INFO)
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
            # Use stderr for debugging output to avoid cluttering stdout
            sys.stderr.write(f"DEBUG: {message}\n")
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


