"""
Configuration settings for the Needle Digital Mining Data Importer plugin.
This module handles configuration loading from environment variables and config files.
"""

import os
from pathlib import Path
from typing import Optional
from qgis.PyQt.QtCore import QSettings

class Config:
    """Central configuration class for the plugin."""
    
    def __init__(self):
        self._config_file = Path(__file__).parent / "secrets.env"
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment variables or config file."""
        # Try to load from environment variables first (for production)
        self.FIREBASE_API_KEY = os.getenv("NEEDLE_FIREBASE_API_KEY")
        self.BASE_API_URL = os.getenv("NEEDLE_BASE_API_URL")
        
        # If not found in env vars, try to load from config file (for development)
        if not self.FIREBASE_API_KEY and self._config_file.exists():
            self._load_from_file()
        
        # Validate required configuration
        if not self.FIREBASE_API_KEY:
            raise ValueError(
                "Firebase API Key not found. Please set NEEDLE_FIREBASE_API_KEY environment variable "
                "or create secrets.env file in src/config/ directory"
            )
    
    def _load_from_file(self):
        """Load configuration from secrets.env file."""
        try:
            with open(self._config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        if key.strip() == "NEEDLE_FIREBASE_API_KEY":
                            self.FIREBASE_API_KEY = value.strip().strip('"\'')
                        elif key.strip() == "NEEDLE_BASE_API_URL":
                            self.BASE_API_URL = value.strip().strip('"\'')
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
    
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