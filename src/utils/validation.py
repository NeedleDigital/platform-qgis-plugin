"""
Validation utilities for the ND Data Importer plugin.
"""

import re
from typing import List, Optional, Tuple, Any, Dict
from ..config.constants import VALIDATION_MESSAGES

def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email is valid, False otherwise
    """
    if not email:
        return False
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

def validate_fetch_all_request(selected_states: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate fetch all records request.
    
    Args:
        selected_states: List of selected state codes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(selected_states) == 0:
        # No states selected is not allowed for fetch all
        return False, VALIDATION_MESSAGES['fetch_all_no_state']
    elif len(selected_states) == 1:
        # Single state is allowed
        return True, None
    else:
        # Multiple states not allowed for fetch all
        return False, VALIDATION_MESSAGES['fetch_all_multiple_states']

def validate_assay_filter(element: str, operator: str, value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate assay filter parameters.
    
    Args:
        element: Selected element symbol
        operator: Comparison operator
        value: Filter value
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not element:
        return False, "Please select an element for filtering."
    
    if not operator:
        return False, "Please select a comparison operator."
    
    if value and not _is_numeric(value):
        return False, "Filter value must be a number."
    
    return True, None

def validate_layer_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate layer name.
    
    Args:
        name: Layer name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Layer name cannot be empty."
    
    # Check for invalid characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\\\']
    for char in invalid_chars:
        if char in name:
            return False, f"Layer name cannot contain '{char}' character."
    
    return True, None

def validate_api_response(response_data: Any) -> Tuple[bool, Optional[str]]:
    """
    Validate API response structure.
    
    Args:
        response_data: Response data to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(response_data, dict):
        return False, "Invalid response format."
    
    if 'error' in response_data:
        error_msg = response_data.get('error', 'Unknown API error')
        return False, str(error_msg)
    
    return True, None

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\\\']
    sanitized = filename
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Remove extra spaces and trim
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    return sanitized

def _is_numeric(value: str) -> bool:
    """Check if string value is numeric."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False