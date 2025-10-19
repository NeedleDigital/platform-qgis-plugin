"""
Configuration Constants for ND Data Importer

This module contains all configuration constants, thresholds, and static data
used throughout the plugin. Centralizing these values makes the codebase
more maintainable and allows for easy customization.

Configuration Categories:
    - Plugin metadata and version information
    - API configuration and endpoints
    - Performance thresholds and limits
    - UI configuration and styling
    - Australian states and territories data
    - Chemical elements for mining analysis
    - Validation messages and error handling

Contributors Guide:
    When modifying these constants, consider the impact on:
    - Plugin performance and memory usage
    - User experience and interface behavior
    - API rate limits and server capacity
    - Large dataset handling capabilities

Author: Needle Digital
Contact: divyansh@needle-digital.com
"""

from typing import List, Tuple

# Plugin metadata and version information
PLUGIN_NAME = "Needle Digital DH Importer"
PLUGIN_VERSION = "1.0.0"
PLUGIN_AUTHOR = "Needle Digital"
PLUGIN_DESCRIPTION = "Import Australian mining drill hole data into QGIS"

# User Role Configuration
ROLE_DISPLAY_NAMES = {
    "tier_1": "Free Trial",
    "tier_2": "Premium",
    "admin": "Admin"
}

ROLE_DESCRIPTIONS = {
    "tier_1": (
        "Free Trial Plan\n\n"
        "Features:\n"
        "• Access to Australian mining data\n"
        "• Filter by state, company, and elements\n"
        "• Up to 1,000 records per fetch\n\n"
        "Limitations:\n"
        "• Cannot use 'Fetch all records' feature\n"
        "• Limited to 1,000 records at a time\n\n"
        "Contact Needle Digital for upgrade to Premium for unlimited access!"
    ),
    "tier_2": (
        "Premium Plan\n\n"
        "Features:\n"
        "• All Free Trial features\n"
        "• Unlimited record fetching\n"
        "• 'Fetch all records' capability\n"
        "• Advanced filtering options\n"
        "• Priority support\n\n"
        "Thank you for being a Premium member!"
    ),
    "admin": (
        "Administrator Access\n\n"
        "Full access to all features:\n"
        "• Unlimited data access\n"
        "• All premium features\n"
        "• Administrative privileges\n"
        "• Complete system access\n\n"
        "Administrator privileges active."
    )
}

# API Configuration
NEEDLE_FIREBASE_API_KEY = "AIzaSyCuX5I0TaQCVmIUVdo1uM_aOQ3zVkrUV8Y"
NEEDLE_BASE_API_URL = "https://master.api.agni.needle-digital.com"

# Streaming Configuration
# Used in: src/ui/main_dialog.py for limiting table display
MAX_DISPLAY_RECORDS = 1000  # Only show first 1K records in table for performance
STREAMING_BUFFER_SIZE = 8192  # Bytes for SSE parsing buffer

# Large Dataset Warning Thresholds
# Used in: data_importer.py to show warning dialog before importing large datasets
LARGE_IMPORT_WARNING_THRESHOLD = 50000  # Show warning above this count

# Import Safety Limits
# Used in: src/ui/components.py (LargeImportWarningDialog) for button styling and recommendations
MAX_SAFE_IMPORT = 100000  # Mark "Import All" as not recommended above this count

# Partial Import Limits
# Used in: data_importer.py for "Import First X Records" functionality
PARTIAL_IMPORT_LIMIT = 50000  # Maximum records for partial import

# Performance Configuration
# Used in: src/utils/qgis_helpers.py for chunked imports and performance optimization
IMPORT_CHUNK_SIZE = 10000  # Records per import chunk to prevent memory issues
CHUNKED_IMPORT_THRESHOLD = 5000  # Use chunked import above this count for better performance

# OpenStreetMap base layer configuration
OSM_LAYER_NAME = "OpenStreetMap"
OSM_LAYER_URL = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0&crs=EPSG3857"

# UI Performance Configuration
# Used in: src/utils/qgis_helpers.py to skip auto-zoom for large datasets (prevents UI freezing)
AUTO_ZOOM_THRESHOLD = 50000  # Don't auto-zoom for datasets larger than this

# Drill Hole Trace Visualization Configuration
# Used in: src/utils/qgis_helpers.py for assay data trace line visualization
TRACE_SCALE_THRESHOLD = 50000  # Map scale at which trace lines become visible (1:50,000)
TRACE_DEFAULT_OFFSET_SCALE = 10.0  # Depth/offset ratio when max_depth is unavailable (lower = longer lines)
TRACE_LINE_WIDTH = 3.0  # Default trace line width in pixels
COLLAR_POINT_SIZE = 6.0  # Default collar point size in pixels
TRACE_ELEMENT_STACK_OFFSET = 0.00005  # Horizontal offset between multiple element trace layers

# Trace Range Configuration
# Used in: src/ui/components.py (TraceRangeConfigDialog) for validation
MIN_TRACE_RANGES = 2  # Minimum number of ranges required
MAX_TRACE_RANGES = 10  # Maximum number of ranges allowed
DEFAULT_TRACE_RANGE_PRESET = "Industry Standard"  # Default preset to use

# Australian states and territories
AUSTRALIAN_STATES: List[Tuple[str, str]] = [
    ("New South Wales", "NSW"),
    ("Queensland", "QLD"), 
    ("South Australia", "SA"),
    ("Tasmania", "TAS"),
    ("Victoria", "VIC"),
    ("Western Australia", "WA"),
    ("Northern Territory", "NT")
]

# Chemical elements for assay filtering
# Format: (Display Name, Symbol)
# Sorted alphabetically by element name (not symbol)
CHEMICAL_ELEMENTS: List[Tuple[str, str]] = [
    ('Aluminum - Al', 'al'), ('Antimony - Sb', 'sb'), 
    ('Arsenic - As', 'as'), ('Barium - Ba', 'ba'), 
    ('Beryllium - Be', 'be'), ('Boron - B', 'b'), ('Bromine - Br', 'br'), ('Cadmium - Cd', 'cd'),
    ('Calcium - Ca', 'ca'), ('Carbon - C', 'c'), ('Cerium - Ce', 'ce'),
    ('Cesium - Cs', 'cs'), ('Chlorine - Cl', 'cl'), ('Chromium - Cr', 'cr'), ('Cobalt - Co', 'co'),
    ('Copper - Cu', 'cu'), ('Dysprosium - Dy', 'dy'), 
    ('Erbium - Er', 'er'), ('Europium - Eu', 'eu'), ('Fluorine - F', 'f'),
    ('Gadolinium - Gd', 'gd'), ('Gallium - Ga', 'ga'), ('Germanium - Ge', 'ge'),
    ('Gold - Au', 'au'), ('Hafnium - Hf', 'hf'), ('Holmium - Ho', 'ho'), 
    ('Indium - In', 'in'), ('Iodine - I', 'i'), ('Iridium - Ir', 'ir'), ('Iron - Fe', 'fe'), ('Lanthanum - La', 'la'), ('Lead - Pb', 'pb'),
    ('Lithium - Li', 'li'), ('Lutetium - Lu', 'lu'), ('Magnesium - Mg', 'mg'), ('Manganese - Mn', 'mn'), ('Mercury - Hg', 'hg'), ('Molybdenum - Mo', 'mo'), ('Neodymium - Nd', 'nd'), ('Nickel - Ni', 'ni'), ('Niobium - Nb', 'nb'), ('Osmium - Os', 'os'), ('Palladium - Pd', 'pd'), ('Phosphorus - P', 'p'), ('Platinum - Pt', 'pt'), ('Potassium - K', 'k'), ('Praseodymium - Pr', 'pr'), ('Rhenium - Re', 're'),
    ('Rhodium - Rh', 'rh'), ('Rubidium - Rb', 'rb'), ('Ruthenium - Ru', 'ru'),
    ('Samarium - Sm', 'sm'), ('Scandium - Sc', 'sc'), ('Selenium - Se', 'se'), ('Silicon - Si', 'si'),
    ('Silver - Ag', 'ag'), ('Sodium - Na', 'na'), ('Strontium - Sr', 'sr'), ('Sulfur - S', 's'),
    ('Tantalum - Ta', 'ta'),  ('Tellurium - Te', 'te'), ('Terbium - Tb', 'tb'),
    ('Thallium - Tl', 'tl'), ('Thorium - Th', 'th'), ('Thulium - Tm', 'tm'), ('Tin - Sn', 'sn'),
    ('Titanium - Ti', 'ti'), ('Tungsten - W', 'w'), ('Uranium - U', 'u'), ('Vanadium - V', 'v'), ('Ytterbium - Yb', 'yb'), ('Yttrium - Y', 'y'), ('Zinc - Zn', 'zn'),
    ('Zirconium - Zr', 'zr')
]

# Comparison operators for assay filtering
COMPARISON_OPERATORS: List[str] = ['>', '<', '=', '!=', '>=', '<=']

# API endpoints
API_ENDPOINTS = {
    # V2 Streaming APIs
    'holes_data': 'plugin/v2/fetch_drill_holes',
    'assays_data': 'plugin/v2/fetch_assay_samples',
    'companies_search': 'companies/search',
}

# UI Configuration
UI_CONFIG = {
    'main_window': {
        'title': 'Needle Digital - Drilling Data Importer',
        'min_width': 850,
        'min_height': 700
    },
    'brand_label': {
        'text': 'Data Importer',
        'font_size': 16,
        'bold': True
    },
    'status_messages': {
        'ready': 'Ready. Please log in.',
        'authenticated': 'Ready to fetch data.',
        'calculating': 'Calculating total available records...',
        'fetching': 'Fetching data...',
        'processing': 'Processing data...',
        'complete': 'Data fetch complete.',
        'error': 'An error occurred.'
    },
    'colors': {
        'error': '#d32f2f',
        'success': '#388e3c',
        'warning': '#f57c00',
        'info': '#1976d2'
    }
}

# Validation messages
VALIDATION_MESSAGES = {
    'auth_required': 'You must be logged in to fetch data.',
    'invalid_credentials': 'A valid email and password are required.',
    'network_error': 'Network error occurred. Please check your connection and try again.',
    'api_error': 'API request failed. Please try again later.',
    'no_data': 'No data found matching your criteria.',
    'import_success': 'Data imported successfully to QGIS.',
    'import_error': 'Failed to import data to QGIS.'
}

# Default layer styling
DEFAULT_LAYER_STYLE = {
    'point_color': '#ff0000',  # Red
    'point_size': 2,
    'point_transparency': 0.8
}

DEFAULT_HOLE_TYPES: List[str] = [
    "ROTARY",
    "AC",
    "ACD",
    "ACORE",
    "AIR TRACK",
    "AIRCORE",
    "AIRCORE (SEE ALSO RCA)",
    "AIRCORE (SEE ALSO RCA), BLADE",
    "AIRCORE (SEE ALSO RCA), DIAMOND BIT - CORING",
    "AIRCORE (SEE ALSO RCA), DIAMOND BIT - CORING, OPEN HOLE PERCUSSION",
    "AIRCORE (SEE ALSO RCA), REVERSE CIRCULATION",
    "AIRCORE (SEE ALSO RCA), ROTARY",
    "AIRCORE (SEE ALSO RCA), ROTARY - AIR",
    "AIRCORE (SEE ALSO RCA), ROTARY - PERCUSSION",
    "AIRCORE (SEE ALSO RCA), ROTARY - PERCUSSION, REVERSE CIRCULATION PERCUSSION",
    "AIRCORE (SEE ALSO RCA), ROTARY - PERCUSSION, ROTARY",
    "AIRCORE (SEE ALSO RCA), ROTARY - PERCUSSION, ROTARY AIR BLAST (SEE ALSO RTA)",
    "AIRCORE (SEE ALSO RCA), ROTARY AIR BLAST (SEE ALSO RTA)",
    "AIRCORE (SEE ALSO RCA), ROTARY AIR BLAST (SEE ALSO RTA), REVERSE CIRCULATION PERCUSSION",
    "AIRCORE, CABLE TOOL, PERCUSSION, ROTARY",
    "AIRCORE, PERCUSSION",
    "AIRCORE, REVERSE CIRCULATION",
    "AIRCORE, ROTARY",
    "ALLUV",
    "AUG",
    "AUGER",
    "AUGER (DETAILS UNSPECIFIED)",
    "AUGER (DETAILS UNSPECIFIED), AUGER (HAND)",
    "AUGER (DETAILS UNSPECIFIED), AUGER (MECHANISED)",
    "AUGER (DETAILS UNSPECIFIED), AUGER (MECHANISED), PUSH TUBE",
    "AUGER (DETAILS UNSPECIFIED), CABLE TOOL",
    "AUGER (DETAILS UNSPECIFIED), DIAMOND BIT - CORING",
    "AUGER (DETAILS UNSPECIFIED), ROTARY - AIR",
    "AUGER (DETAILS UNSPECIFIED), ROTARY - AIR , ROTARY - MUD",
    "AUGER (DETAILS UNSPECIFIED), ROTARY - MUD",
    "AUGER (HAND)",
    "AUGER (HAND) , HAND DUG",
    "AUGER (HAND) , HAND DUG, UNKNOWN",
    "AUGER (HAND) , PUSH TUBE, ROTARY - AIR",
    "AUGER (HAND) , ROTARY - AIR",
    "AUGER (HAND) , UNKNOWN",
    "AUGER (MECHANISED)",
    "AUGER (MECHANISED) - CORING",
    "AUGER (MECHANISED) - CORING, AUGER (MECHANISED)",
    "AUGER (MECHANISED) - CORING, AUGER (MECHANISED), PUSH TUBE",
    "AUGER (MECHANISED) - CORING, CABLE TOOL",
    "AUGER (MECHANISED) - CORING, DIAMOND BIT - CORING",
    "AUGER (MECHANISED) - CORING, ROTARY",
    "AUGER (MECHANISED) - CORING, ROTARY - MUD, UNKNOWN",
    "AUGER (MECHANISED), AUGER (HAND)",
    "AUGER (MECHANISED), AUGER (HAND) , PUSH TUBE",
    "AUGER (MECHANISED), AUGER (HAND) , UNKNOWN",
    "AUGER (MECHANISED), BLADE",
    "AUGER (MECHANISED), BLADE, PUSH TUBE",
    "AUGER (MECHANISED), BLADE, ROTARY - MUD",
    "AUGER (MECHANISED), BLADE, ROTARY - PERCUSSION",
    "AUGER (MECHANISED), BLADE, UNKNOWN",
    "AUGER (MECHANISED), CABLE TOOL",
    "AUGER (MECHANISED), CABLE TOOL , ROTARY",
    "AUGER (MECHANISED), CABLE TOOL , ROTARY - WATER",
    "AUGER (MECHANISED), DIAMOND BIT - CORING",
    "AUGER (MECHANISED), DIAMOND BIT - CORING, ROTARY - AIR",
    "AUGER (MECHANISED), DIAMOND BIT - CORING, ROTARY - MUD",
    "AUGER (MECHANISED), DIAMOND BIT - CORING, ROTARY - PERCUSSION",
    "AUGER (MECHANISED), HAND DUG",
    "AUGER (MECHANISED), PUSH TUBE",
    "AUGER (MECHANISED), PUSH TUBE, ROTARY - AIR",
    "AUGER (MECHANISED), REVERSE CIRCULATION",
    "AUGER (MECHANISED), ROTARY",
    "AUGER (MECHANISED), ROTARY , ROTARY - MUD",
    "AUGER (MECHANISED), ROTARY - AIR",
    "AUGER (MECHANISED), ROTARY - AIR , ROTARY - MUD",
    "AUGER (MECHANISED), ROTARY - AIR , ROTARY - WATER",
    "AUGER (MECHANISED), ROTARY - AIR , UNKNOWN",
    "AUGER (MECHANISED), ROTARY - MUD",
    "AUGER (MECHANISED), ROTARY - MUD, ROTARY - WATER",
    "AUGER (MECHANISED), ROTARY - PERCUSSION",
    "AUGER (MECHANISED), ROTARY - PERCUSSION, PUSH TUBE",
    "AUGER (MECHANISED), ROTARY - PERCUSSION, ROTARY",
    "AUGER (MECHANISED), ROTARY - PERCUSSION, ROTARY - AIR",
    "AUGER (MECHANISED), ROTARY - PERCUSSION, ROTARY - MUD",
    "AUGER (MECHANISED), ROTARY - PERCUSSION, UNKNOWN",
    "AUGER (MECHANISED), ROTARY - WATER",
    "AUGER (MECHANISED), ROTARY AIR BLAST (SEE ALSO RTA)",
    "AUGER (MECHANISED), SPEARPOINT",
    "AUGER (MECHANISED), UNKNOWN",
    "AUGERS",
    "AUGERS, DIAMOND",
    "AUGERS, DIAMOND, PUSH TUBE",
    "AUGERS, DIAMOND, ROTARY",
    "AUGERS, PERCUSSION",
    "AUGERS, PUSH TUBE",
    "AUGERS, ROTARY",
    "AUGERS, ROTARY_PERCUSSION",
    "BACKHOE",
    "BACKHOE, CABLE TOOL",
    "BACKHOE, DIAMOND BIT - CORING",
    "BACKHOE, HAND DUG",
    "BEDRK",
    "BLADE",
    "BLADE, AUGER (HAND) , ROTARY - PERCUSSION",
    "BLADE, CABLE TOOL , ROTARY - AIR",
    "BLADE, CABLE TOOL , ROTARY - PERCUSSION",
    "BLADE, DIAMOND BIT - CORING",
    "BLADE, DIAMOND BIT - CORING, ROTARY - MUD",
    "BLADE, OPEN HOLE PERCUSSION",
    "BLADE, PUSH TUBE",
    "BLADE, ROTARY",
    "BLADE, ROTARY - AIR",
    "BLADE, ROTARY - AIR , ROTARY - FOAM",
    "BLADE, ROTARY - AIR , ROTARY - MUD",
    "BLADE, ROTARY - FOAM",
    "BLADE, ROTARY - MUD",
    "BLADE, ROTARY - MUD, UNKNOWN",
    "BLADE, ROTARY - PERCUSSION",
    "BLADE, ROTARY - PERCUSSION, REVERSE CIRCULATION",
    "BLADE, ROTARY - PERCUSSION, ROTARY",
    "BLADE, ROTARY - PERCUSSION, ROTARY - AIR",
    "BLADE, ROTARY - PERCUSSION, ROTARY - FOAM",
    "BLADE, ROTARY - PERCUSSION, ROTARY - MUD",
    "BLADE, ROTARY - PERCUSSION, ROTARY AIR BLAST (SEE ALSO RTA)",
    "BLADE, ROTARY - PERCUSSION, UNKNOWN",
    "BLADE, ROTARY - WATER",
    "BLADE, UNKNOWN",
    "BORE",
    "BUCKET",
    "CABLE TOOL",
    "CABLE TOOL , AUGER (HAND)",
    "CABLE TOOL , DIAMOND BIT - CORING",
    "CABLE TOOL , DIAMOND BIT - CORING, ROTARY",
    "CABLE TOOL , DIAMOND BIT - CORING, ROTARY - MUD",
    "CABLE TOOL , HAND DUG",
    "CABLE TOOL , HAND DUG, ROTARY - PERCUSSION",
    "CABLE TOOL , PUSH TUBE",
    "CABLE TOOL , REVERSE CIRCULATION - AIR , ROTARY - AIR",
    "CABLE TOOL , ROTARY",
    "CABLE TOOL , ROTARY , ROTARY - AIR",
    "CABLE TOOL , ROTARY , ROTARY - MUD",
    "CABLE TOOL , ROTARY , TUNGSTEN CARBIDE BIT - CORING",
    "CABLE TOOL , ROTARY - AIR",
    "CABLE TOOL , ROTARY - AIR , ROTARY - FOAM",
    "CABLE TOOL , ROTARY - AIR , ROTARY - MUD",
    "CABLE TOOL , ROTARY - AIR , ROTARY - WATER",
    "CABLE TOOL , ROTARY - AIR , UNKNOWN",
    "CABLE TOOL , ROTARY - FOAM",
    "CABLE TOOL , ROTARY - MUD",
    "CABLE TOOL , ROTARY - PERCUSSION",
    "CABLE TOOL , ROTARY - PERCUSSION, ROTARY - AIR",
    "CABLE TOOL , ROTARY - PERCUSSION, UNKNOWN",
    "CABLE TOOL , ROTARY - WATER",
    "CABLE TOOL , TUNGSTEN CARBIDE BIT - CORING",
    "CABLE TOOL , UNKNOWN",
    "CALW",
    "CALWELD",
    "CBLT",
    "CHURN",
    "CONE PENETRATION TEST",
    "COST",
    "COSTEAN",
    "DD",
    "DIAMOND",
    "DIAMOND BIT - CORING",
    "DIAMOND BIT - CORING, AUGER (HAND) , ROTARY",
    "DIAMOND BIT - CORING, HAND DUG",
    "DIAMOND BIT - CORING, OPEN HOLE PERCUSSION",
    "DIAMOND BIT - CORING, OPEN HOLE PERCUSSION, ROTARY",
    "DIAMOND BIT - CORING, OPEN HOLE PERCUSSION, ROTARY - PERCUSSION",
    "DIAMOND BIT - CORING, PUSH TUBE",
    "DIAMOND BIT - CORING, REVERSE CIRCULATION",
    "DIAMOND BIT - CORING, REVERSE CIRCULATION - AIR",
    "DIAMOND BIT - CORING, REVERSE CIRCULATION - AIR , ROTARY",
    "DIAMOND BIT - CORING, REVERSE CIRCULATION - MUD",
    "DIAMOND BIT - CORING, REVERSE CIRCULATION - MUD , ROTARY - MUD",
    "DIAMOND BIT - CORING, REVERSE CIRCULATION PERCUSSION",
    "DIAMOND BIT - CORING, REVERSE CIRCULATION PERCUSSION, ROTARY",
    "DIAMOND BIT - CORING, ROTARY",
    "DIAMOND BIT - CORING, ROTARY , ROTARY - MUD",
    "DIAMOND BIT - CORING, ROTARY , TUNGSTEN CARBIDE BIT - CORING",
    "DIAMOND BIT - CORING, ROTARY - AIR",
    "DIAMOND BIT - CORING, ROTARY - AIR , ROTARY - MUD",
    "DIAMOND BIT - CORING, ROTARY - AIR , ROTARY - WATER",
    "DIAMOND BIT - CORING, ROTARY - MUD",
    "DIAMOND BIT - CORING, ROTARY - MUD, TUNGSTEN CARBIDE BIT - CORING",
    "DIAMOND BIT - CORING, ROTARY - PERCUSSION",
    "DIAMOND BIT - CORING, ROTARY - PERCUSSION, REVERSE CIRCULATION",
    "DIAMOND BIT - CORING, ROTARY - PERCUSSION, REVERSE CIRCULATION - AIR",
    "DIAMOND BIT - CORING, ROTARY - PERCUSSION, ROTARY",
    "DIAMOND BIT - CORING, ROTARY - PERCUSSION, ROTARY - AIR",
    "DIAMOND BIT - CORING, ROTARY - PERCUSSION, ROTARY - MUD",
    "DIAMOND BIT - CORING, ROTARY - PERCUSSION, ROTARY AIR BLAST (SEE ALSO RTA)",
    "DIAMOND BIT - CORING, ROTARY - PERCUSSION, UNKNOWN",
    "DIAMOND BIT - CORING, ROTARY - WATER",
    "DIAMOND BIT - CORING, ROTARY AIR BLAST (SEE ALSO RTA)",
    "DIAMOND BIT - CORING, SONIC",
    "DIAMOND BIT - CORING, UNKNOWN",
    "DIAMOND DRILL",
    "DIAMOND, HOLLOW FLIGHT AUGER",
    "DIAMOND, HOLLOW FLIGHT AUGER, PUSH TUBE",
    "DIAMOND, OTHER",
    "DIAMOND, PERCUSSION",
    "DIAMOND, PUSH TUBE",
    "DIAMOND, PUSH TUBE, ROTARY",
    "DIAMOND, REVERSE CIRCULATION",
    "DIAMOND, ROTARY",
    "DIAMOND, ROTARY_PERCUSSION",
    "HAND DUG",
    "HAND DUG, ROTARY",
    "HAND DUG, ROTARY - AIR",
    "HAND DUG, ROTARY - PERCUSSION",
    "HAND DUG, SONIC",
    "HAND DUG, SPEARPOINT",
    "HAND DUG, UNKNOWN",
    "HAND DUG, VIBROCORE",
    "HOLLOW FLIGHT AUGER",
    "HOLLOW FLIGHT AUGER, PERCUSSION",
    "HOLLOW FLIGHT AUGER, PUSH TUBE",
    "HOLLOW FLIGHT AUGER, ROTARY_DIAMOND",
    "HYDRAULIC JET",
    "HYDRAULIC JET, ROTARY - AIR",
    "LD",
    "MET",
    "MT",
    "NOT RECORDED",
    "OPEN HOLE PERCUSSION",
    "OPEN HOLE PERCUSSION, ROTARY - MUD",
    "OTHER",
    "OTHER, ROTARY_DIAMOND",
    "PCDD",
    "PCOHDD",
    "PCRCDD",
    "PCRDD",
    "PERC",
    "PERCUSSION",
    "PERCUSSION, REVERSE CIRCULATION",
    "PERCUSSION, ROTARY",
    "PERCUSSION_DIAMOND",
    "PERCUSSION_DIAMOND, ROTARY",
    "PIT",
    "PTW",
    "PUSH TUBE",
    "PUSH TUBE, ROTARY",
    "PUSH TUBE, ROTARY - AIR",
    "RAB",
    "RC",
    "RC PRECOLLAR",
    "RCD",
    "RCOH",
    "REVC",
    "REVERSE CIRCULATION",
    "REVERSE CIRCULATION , REVERSE CIRCULATION - AIR",
    "REVERSE CIRCULATION , REVERSE CIRCULATION - AIR , REVERSE CIRCULATION - MUD",
    "REVERSE CIRCULATION , REVERSE CIRCULATION PERCUSSION",
    "REVERSE CIRCULATION , ROTARY",
    "REVERSE CIRCULATION , ROTARY - AIR",
    "REVERSE CIRCULATION , ROTARY - MUD",
    "REVERSE CIRCULATION - AIR",
    "REVERSE CIRCULATION - AIR , REVERSE CIRCULATION PERCUSSION",
    "REVERSE CIRCULATION - AIR , ROTARY - AIR",
    "REVERSE CIRCULATION - AIR , UNKNOWN",
    "REVERSE CIRCULATION - MUD",
    "REVERSE CIRCULATION DIAMOND",
    "REVERSE CIRCULATION PERCUSSION",
    "REVERSE CIRCULATION PERCUSSION, ROTARY",
    "REVERSE CIRCULATION PERCUSSION, ROTARY - MUD",
    "REVERSE CIRCULATION, ROTARY",
    "REVERSE CIRCULATION_DIAMOND",
    "RM",
    "ROTARY",
    "ROTARY , ROTARY - AIR",
    "ROTARY , ROTARY - AIR , ROTARY - FOAM",
    "ROTARY , ROTARY - AIR , ROTARY - MUD",
    "ROTARY , ROTARY - AIR , ROTARY - WATER",
    "ROTARY , ROTARY - FOAM",
    "ROTARY , ROTARY - FOAM, ROTARY - MUD",
    "ROTARY , ROTARY - FOAM, ROTARY - WATER",
    "ROTARY , ROTARY - MUD",
    "ROTARY , ROTARY - MUD, TUNGSTEN CARBIDE BIT - CORING",
    "ROTARY , ROTARY - MUD, UNKNOWN",
    "ROTARY , ROTARY - WATER",
    "ROTARY , TUNGSTEN CARBIDE BIT - CORING",
    "ROTARY , UNKNOWN",
    "ROTARY - AIR",
    "ROTARY - AIR , ROTARY - FOAM",
    "ROTARY - AIR , ROTARY - FOAM, ROTARY - MUD",
    "ROTARY - AIR , ROTARY - FOAM, ROTARY - WATER",
    "ROTARY - AIR , ROTARY - MUD",
    "ROTARY - AIR , ROTARY - MUD, ROTARY - WATER",
    "ROTARY - AIR , ROTARY - MUD, TUNGSTEN CARBIDE BIT - CORING",
    "ROTARY - AIR , ROTARY - WATER",
    "ROTARY - AIR , ROTARY - WATER, UNKNOWN",
    "ROTARY - AIR , SONIC",
    "ROTARY - AIR , UNKNOWN",
    "ROTARY - FOAM",
    "ROTARY - FOAM, ROTARY - MUD",
    "ROTARY - FOAM, ROTARY - MUD, ROTARY - WATER",
    "ROTARY - FOAM, ROTARY - WATER",
    "ROTARY - FOAM, ROTARY - WATER, UNKNOWN",
    "ROTARY - FOAM, UNKNOWN",
    "ROTARY - MUD",
    "ROTARY - MUD, ROTARY - WATER",
    "ROTARY - MUD, TUNGSTEN CARBIDE BIT - CORING",
    "ROTARY - MUD, UNKNOWN",
    "ROTARY - PERCUSSION",
    "ROTARY - PERCUSSION, PUSH TUBE",
    "ROTARY - PERCUSSION, REVERSE CIRCULATION",
    "ROTARY - PERCUSSION, REVERSE CIRCULATION - AIR",
    "ROTARY - PERCUSSION, REVERSE CIRCULATION - AIR , ROTARY - AIR",
    "ROTARY - PERCUSSION, REVERSE CIRCULATION PERCUSSION",
    "ROTARY - PERCUSSION, REVERSE CIRCULATION PERCUSSION, ROTARY",
    "ROTARY - PERCUSSION, ROTARY",
    "ROTARY - PERCUSSION, ROTARY , ROTARY - AIR",
    "ROTARY - PERCUSSION, ROTARY , ROTARY - MUD",
    "ROTARY - PERCUSSION, ROTARY , TUNGSTEN CARBIDE BIT - CORING",
    "ROTARY - PERCUSSION, ROTARY - AIR",
    "ROTARY - PERCUSSION, ROTARY - AIR , ROTARY - FOAM",
    "ROTARY - PERCUSSION, ROTARY - AIR , ROTARY - MUD",
    "ROTARY - PERCUSSION, ROTARY - AIR , ROTARY - WATER",
    "ROTARY - PERCUSSION, ROTARY - AIR , UNKNOWN",
    "ROTARY - PERCUSSION, ROTARY - FOAM",
    "ROTARY - PERCUSSION, ROTARY - MUD",
    "ROTARY - PERCUSSION, ROTARY - MUD, ROTARY - WATER",
    "ROTARY - PERCUSSION, ROTARY - WATER",
    "ROTARY - PERCUSSION, ROTARY AIR BLAST (SEE ALSO RTA)",
    "ROTARY - PERCUSSION, TUNGSTEN CARBIDE BIT - CORING",
    "ROTARY - PERCUSSION, UNKNOWN",
    "ROTARY - WATER",
    "ROTARY - WATER, UNKNOWN",
    "ROTARY AIR BLAST (SEE ALSO RTA)",
    "ROTARY AIR BLAST (SEE ALSO RTA), REVERSE CIRCULATION",
    "ROTARY AIR BLAST (SEE ALSO RTA), REVERSE CIRCULATION PERCUSSION, UNKNOWN",
    "ROTARY AIR BLAST (SEE ALSO RTA), ROTARY - MUD",
    "ROTARY AIR BLAST (SEE ALSO RTA), UNKNOWN",
    "ROTARY MUD",
    "ROTARY_DIAMOND",
    "ROTARY_PERCUSSION",
    "RTA",
    "RTM",
    "SHAFT",
    "SON",
    "SONIC",
    "SONIC, UNKNOWN",
    "SPEARPOINT",
    "TCH",
    "TRENCH",
    "TUNGSTEN CARBIDE BIT - CORING",
    "TUNNEL",
    "UNK",
    "UNKN",
    "UNKNOWN",
    "UNKNOWN, VIBROCORE",
    "VAC",
    "VACUUM",
    "VIB",
    "VIBROCORE",
    "WACK",
    "WAT",
    "WB"
]
