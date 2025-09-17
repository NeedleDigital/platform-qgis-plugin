"""
Configuration settings for the ND Data Importer plugin.
This module handles configuration loading from environment variables and config files.
"""

import os
from pathlib import Path
from typing import Optional
from qgis.PyQt.QtCore import QSettings
from .constants import NEEDLE_FIREBASE_API_KEY, NEEDLE_BASE_API_URL

class Config:
    """Central configuration class for the plugin."""

    def __init__(self):
        self._load_config()

    def _load_config(self):
        """Load configuration from environment variables or constants."""
        # Try to load from environment variables first (for production)
        self.FIREBASE_API_KEY = os.getenv("NEEDLE_FIREBASE_API_KEY") or NEEDLE_FIREBASE_API_KEY
        self.BASE_API_URL = os.getenv("NEEDLE_BASE_API_URL") or NEEDLE_BASE_API_URL

        # Validate required configuration
        if not self.FIREBASE_API_KEY:
            raise ValueError(
                "Firebase API Key not found. Please set NEEDLE_FIREBASE_API_KEY environment variable"
            )


    @property
    def firebase_auth_url(self) -> str:
        """Get the Firebase authentication URL."""
        return f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.FIREBASE_API_KEY}"

    @property
    def firebase_refresh_url(self) -> str:
        """Get the Firebase token refresh URL."""
        return f"https://securetoken.googleapis.com/v1/token?key={self.FIREBASE_API_KEY}"

# Global configuration instance
config = Config()