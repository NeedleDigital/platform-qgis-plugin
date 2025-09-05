"""
Logging utilities for the ND Data Importer plugin.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Set level
        log_level = getattr(logging, (level or 'INFO').upper(), logging.INFO)
        logger.setLevel(log_level)
    
    return logger

def log_api_request(endpoint: str, params: dict, logger: logging.Logger) -> None:
    """Log API request details."""
    logger.info(f"API Request - Endpoint: {endpoint}, Params: {params}")

def log_api_response(endpoint: str, success: bool, data_count: int, logger: logging.Logger) -> None:
    """Log API response details."""
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"API Response - Endpoint: {endpoint}, Status: {status}, Records: {data_count}")

def log_user_action(action: str, details: str, logger: logging.Logger) -> None:
    """Log user actions."""
    logger.info(f"User Action - {action}: {details}")