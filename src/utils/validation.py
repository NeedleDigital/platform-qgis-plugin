"""
Validation utilities for the ND Data Importer plugin.
"""

import re
import json
import base64
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

def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token and extract payload without verification.

    Args:
        token: JWT token string

    Returns:
        Dictionary containing token payload, or None if decoding fails
    """
    if not token:
        return None

    try:
        # JWT tokens have 3 parts separated by dots: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None

        # Decode the payload (second part)
        payload = parts[1]

        # Add padding if needed (JWT uses base64url encoding)
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding

        # Decode base64
        decoded_bytes = base64.b64decode(payload)
        decoded_str = decoded_bytes.decode('utf-8')

        # Parse JSON
        payload_data = json.loads(decoded_str)
        return payload_data

    except Exception:
        return None

def get_user_role_from_token(token: str) -> Optional[str]:
    """
    Extract user role from JWT token.

    Args:
        token: JWT token string

    Returns:
        User role string (tier_1, tier_2, admin) or None if not found
    """
    payload = decode_jwt_token(token)
    if not payload:
        return None

    # Try different possible locations for the role claim
    # Firebase custom claims are typically nested
    role = payload.get('role')
    if role:
        return role

    # Check custom claims
    custom_claims = payload.get('custom_claims', {})
    if isinstance(custom_claims, dict):
        role = custom_claims.get('role')
        if role:
            return role

    # Check claims at root level
    claims = payload.get('claims', {})
    if isinstance(claims, dict):
        role = claims.get('role')
        if role:
            return role

    return None