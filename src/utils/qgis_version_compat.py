"""
QGIS Version Compatibility Utilities

This module provides version detection and compatibility helpers to ensure
the plugin works across different QGIS versions (3.0 onwards).

Key Compatibility Issues Addressed:
    - QgsField constructor changed in QGIS 3.38 from QVariant to QMetaType
    - Different API requirements for older vs newer QGIS versions
    - Automatic fallback strategies for maximum compatibility

Version Detection:
    Uses Qgis.QGIS_VERSION_INT to determine the running QGIS version
    and selects appropriate API methods automatically.

Supported QGIS Versions:
    - QGIS 3.0 - 3.37: Uses QVariant.Type for field types
    - QGIS 3.38+: Uses QMetaType.Type for field types

Author: Needle Digital
Contact: divyansh@needle-digital.com
"""

from qgis.core import Qgis, QgsField
from qgis.PyQt.QtCore import QVariant

# Try to import QMetaType (available in QGIS 3.x, fully utilized in 3.38+)
try:
    from qgis.PyQt.QtCore import QMetaType
    HAS_QMETATYPE = True
except ImportError:
    HAS_QMETATYPE = False

from .logging import log_info, log_warning, log_error


# ============================================================================
# Version Detection
# ============================================================================

# Get QGIS version as integer (e.g., 30000 for 3.0.0, 33800 for 3.38.0)
QGIS_VERSION_INT = Qgis.QGIS_VERSION_INT
QGIS_VERSION_STR = Qgis.QGIS_VERSION

# Version 3.38.0 introduced QMetaType.Type as the recommended way
SUPPORTS_QMETATYPE = QGIS_VERSION_INT >= 33800  # 3.38.0+


def get_qgis_version_int():
    """
    Get QGIS version as integer for easy comparison.

    Returns:
        int: Version as integer (e.g., 30000 for 3.0.0, 33800 for 3.38.0)

    Example:
        >>> version = get_qgis_version_int()
        >>> if version >= 33800:
        >>>     print("QGIS 3.38 or newer")
    """
    return QGIS_VERSION_INT


def get_qgis_version_string():
    """
    Get QGIS version as string.

    Returns:
        str: Version string (e.g., "3.38.0-Grenoble")
    """
    return QGIS_VERSION_STR


def is_qgis_version_at_least(major, minor=0, patch=0):
    """
    Check if current QGIS version is at least the specified version.

    Args:
        major (int): Major version number (e.g., 3)
        minor (int): Minor version number (e.g., 38)
        patch (int): Patch version number (e.g., 0)

    Returns:
        bool: True if current version >= specified version

    Example:
        >>> if is_qgis_version_at_least(3, 38):
        >>>     # Use modern API
    """
    target_version = (major * 10000) + (minor * 100) + patch
    return QGIS_VERSION_INT >= target_version


# ============================================================================
# Field Type Mapping
# ============================================================================

def get_field_type_for_python_value(value):
    """
    Get appropriate QgsField type constant based on QGIS version and Python value type.

    This function automatically selects between QVariant.Type (QGIS 3.0-3.37)
    and QMetaType.Type (QGIS 3.38+) based on the running QGIS version.

    Args:
        value: Python value to determine field type for (int, float, bool, str, etc.)

    Returns:
        Field type constant appropriate for current QGIS version:
        - QMetaType.Type.* for QGIS 3.38+
        - QVariant.* for QGIS 3.0-3.37

    Example:
        >>> field_type = get_field_type_for_python_value(42)
        >>> # Returns QMetaType.Type.Int on QGIS 3.38+
        >>> # Returns QVariant.Int on QGIS 3.0-3.37
    """

    # Determine the Python type
    is_bool = isinstance(value, bool)  # Check bool before int (bool is subclass of int)
    is_int = isinstance(value, int) and not is_bool
    is_float = isinstance(value, float)

    # Use QMetaType for QGIS 3.38+ (modern API)
    if SUPPORTS_QMETATYPE and HAS_QMETATYPE:
        if is_bool:
            return QMetaType.Type.Bool
        elif is_int:
            return QMetaType.Type.Int
        elif is_float:
            return QMetaType.Type.Double
        else:
            return QMetaType.Type.QString

    # Use QVariant for QGIS 3.0-3.37 (legacy API)
    else:
        if is_bool:
            return QVariant.Bool
        elif is_int:
            return QVariant.Int
        elif is_float:
            return QVariant.Double
        else:
            return QVariant.String


def get_type_name_for_python_value(value):
    """
    Get type name string for a Python value.

    Args:
        value: Python value to determine type name for

    Returns:
        str: Type name ("integer", "double", "boolean", "string")
    """
    is_bool = isinstance(value, bool)
    is_int = isinstance(value, int) and not is_bool
    is_float = isinstance(value, float)

    if is_bool:
        return "boolean"
    elif is_int:
        return "integer"
    elif is_float:
        return "double"
    else:
        return "string"


# ============================================================================
# QgsField Creation
# ============================================================================

def create_qgs_field_compatible(field_name, sample_value):
    """
    Create a QgsField with automatic version compatibility.

    This function handles the API differences between QGIS versions:
    - QGIS 3.0-3.37: Uses QVariant.Type
    - QGIS 3.38+: Uses QMetaType.Type

    The function tries multiple approaches with fallbacks to ensure
    maximum compatibility across all QGIS 3.x versions.

    Args:
        field_name (str): Name of the field
        sample_value: Sample Python value to determine field type

    Returns:
        QgsField: Field object compatible with current QGIS version

    Raises:
        Exception: If field creation fails with all attempted methods

    Example:
        >>> field = create_qgs_field_compatible("elevation", 123.45)
        >>> # Creates field with appropriate type for current QGIS version
    """

    # Get appropriate field type and type name
    field_type = get_field_type_for_python_value(sample_value)
    type_name = get_type_name_for_python_value(sample_value)

    # Try creating the field with multiple fallback strategies

    # Strategy 1: Try with type and type_name (standard approach)
    try:
        field = QgsField(field_name, field_type, type_name)
        return field
    except Exception as e1:
        log_warning(f"Failed to create field '{field_name}' with type and type_name: {e1}")

    # Strategy 2: Try with just field name and type (minimal approach)
    try:
        field = QgsField(field_name, field_type)
        return field
    except Exception as e2:
        log_warning(f"Failed to create field '{field_name}' with just type: {e2}")

    # Strategy 3: Try forcing QVariant type (for edge cases)
    try:
        # Force QVariant type regardless of version
        if isinstance(sample_value, bool):
            fallback_type = QVariant.Bool
        elif isinstance(sample_value, int):
            fallback_type = QVariant.Int
        elif isinstance(sample_value, float):
            fallback_type = QVariant.Double
        else:
            fallback_type = QVariant.String

        field = QgsField(field_name, fallback_type, type_name)
        return field
    except Exception as e3:
        log_warning(f"Failed to create field '{field_name}' with QVariant fallback: {e3}")

    # Strategy 4: Final fallback - create as string field
    try:
        log_warning(f"Creating field '{field_name}' as string (last resort fallback)")
        field = QgsField(field_name, QVariant.String, "string")
        return field
    except Exception as e4:
        # This should never happen, but if it does, we have a serious problem
        error_msg = f"All strategies failed to create field '{field_name}': {e4}"
        log_error(error_msg)
        raise Exception(error_msg)


# ============================================================================
# Version Information Logging
# ============================================================================

def log_qgis_version_info():
    """
    Log QGIS version information for debugging purposes.

    This helps diagnose compatibility issues by showing which QGIS version
    is running and which API will be used.
    """
    log_info("=" * 60)
    log_info("QGIS Version Compatibility Information")
    log_info("=" * 60)
    log_info(f"QGIS Version: {QGIS_VERSION_STR}")
    log_info(f"QGIS Version Int: {QGIS_VERSION_INT}")
    log_info(f"QMetaType Available: {HAS_QMETATYPE}")
    log_info(f"Using QMetaType API: {SUPPORTS_QMETATYPE}")

    if SUPPORTS_QMETATYPE:
        log_info("Field Type API: QMetaType.Type (QGIS 3.38+ modern API)")
    else:
        log_info("Field Type API: QVariant.Type (QGIS 3.0-3.37 legacy API)")

    log_info("=" * 60)


# Log version info when module is imported
log_qgis_version_info()
