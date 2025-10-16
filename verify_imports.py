#!/usr/bin/env python3
"""
Verification script to check if all imports are correct
Run this before deploying to QGIS
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("Verifying plugin imports...")
print("=" * 70)

try:
    print("\n1. Checking constants...")
    from src.config.constants import (
        PLUGIN_NAME, PLUGIN_VERSION, LARGE_IMPORT_WARNING_THRESHOLD,
        PARTIAL_IMPORT_LIMIT, CHUNKED_IMPORT_THRESHOLD,
        MAX_SAFE_IMPORT, API_FETCH_LIMIT, AUSTRALIAN_STATES,
        CHEMICAL_ELEMENTS, UI_CONFIG, DEFAULT_HOLE_TYPES
    )
    print("   ✓ All constants imported successfully")

    print("\n2. Checking removed constants are not present...")
    try:
        from src.config.constants import API_FETCH_LIMIT_LOCATION_ONLY
        print("   ✗ ERROR: API_FETCH_LIMIT_LOCATION_ONLY should not exist!")
        sys.exit(1)
    except ImportError:
        print("   ✓ API_FETCH_LIMIT_LOCATION_ONLY correctly removed")

    try:
        from src.config.constants import LARGE_IMPORT_WARNING_THRESHOLD_LOCATION_ONLY
        print("   ✗ ERROR: LARGE_IMPORT_WARNING_THRESHOLD_LOCATION_ONLY should not exist!")
        sys.exit(1)
    except ImportError:
        print("   ✓ LARGE_IMPORT_WARNING_THRESHOLD_LOCATION_ONLY correctly removed")

    print("\n3. Checking components imports...")
    from src.ui.components import (
        DynamicSearchFilterWidget, StaticFilterWidget,
        LargeImportWarningDialog, MAX_SAFE_IMPORT, PARTIAL_IMPORT_LIMIT
    )
    print("   ✓ Components imported successfully")

    print("\n4. Checking data_manager imports...")
    from src.core.data_manager import DataManager
    print("   ✓ DataManager imported successfully")

    print("\n5. Checking validation imports...")
    from src.utils.validation import validate_email, validate_assay_filter
    print("   ✓ Validation functions imported successfully")

    print("\n6. Checking removed validation function...")
    try:
        from src.utils.validation import validate_fetch_all_request
        print("   ✗ ERROR: validate_fetch_all_request should not exist!")
        sys.exit(1)
    except ImportError:
        print("   ✓ validate_fetch_all_request correctly removed")

    print("\n" + "=" * 70)
    print("✓ ALL VERIFICATION CHECKS PASSED!")
    print("=" * 70)
    print("\nThe plugin is ready to be deployed to QGIS.")
    print("\nNext steps:")
    print("1. Close QGIS completely")
    print("2. Delete the old plugin folder:")
    print("   rm -rf ~/Library/Application\\ Support/QGIS/QGIS3/profiles/default/python/plugins/data_importer")
    print("3. Copy this folder to the plugins directory:")
    print("   cp -r . ~/Library/Application\\ Support/QGIS/QGIS3/profiles/default/python/plugins/data_importer")
    print("4. Start QGIS and enable the plugin")

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
