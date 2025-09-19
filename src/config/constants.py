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

# API Configuration
NEEDLE_FIREBASE_API_KEY = "AIzaSyCuX5I0TaQCVmIUVdo1uM_aOQ3zVkrUV8Y"
NEEDLE_BASE_API_URL = "https://master.api.drh.needle-digital.com"

# API Request Limits
# Used in: src/core/data_manager.py for chunking API requests
API_FETCH_LIMIT = 50000  # Maximum records per API request for full data
API_FETCH_LIMIT_LOCATION_ONLY = 200000  # 4x limit for location-only requests (coordinates only)

# Large Dataset Warning Thresholds
# Used in: data_importer.py to show warning dialog before importing large datasets
LARGE_IMPORT_WARNING_THRESHOLD = 50000  # Show warning above this count (full data)
LARGE_IMPORT_WARNING_THRESHOLD_LOCATION_ONLY = 200000  # Warning threshold for location-only data

# Import Safety Limits
# Used in: src/ui/components.py (LargeImportWarningDialog) for button styling and recommendations
MAX_SAFE_IMPORT = 100000  # Mark "Import All" as not recommended above this count (full data)
MAX_SAFE_IMPORT_LOCATION_ONLY = 400000  # Safe import limit for location-only data

# Partial Import Limits
# Used in: data_importer.py for "Import First X Records" functionality
PARTIAL_IMPORT_LIMIT = 50000  # Maximum records for partial import (full data)
PARTIAL_IMPORT_LIMIT_LOCATION_ONLY = 200000  # Maximum records for partial import (location-only)

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
CHEMICAL_ELEMENTS: List[Tuple[str, str]] = [
    ('Silver - Ag', 'ag'), ('Aluminum - Al', 'al'), ('Americium - Am', 'am'), ('Argon - Ar', 'ar'), 
    ('Arsenic - As', 'as'), ('Astatine - At', 'at'), ('Gold - Au', 'au'), ('Boron - B', 'b'), 
    ('Barium - Ba', 'ba'), ('Beryllium - Be', 'be'), ('Berkelium - Bk', 'bk'), ('Bromine - Br', 'br'), 
    ('Carbon - C', 'c'), ('Calcium - Ca', 'ca'), ('Cadmium - Cd', 'cd'), ('Cerium - Ce', 'ce'), 
    ('Californium - Cf', 'cf'), ('Chlorine - Cl', 'cl'), ('Curium - Cm', 'cm'), ('Cobalt - Co', 'co'), 
    ('Chromium - Cr', 'cr'), ('Cesium - Cs', 'cs'), ('Copper - Cu', 'cu'), ('Dysprosium - Dy', 'dy'), 
    ('Erbium - Er', 'er'), ('Einsteinium - Es', 'es'), ('Europium - Eu', 'eu'), ('Fluorine - F', 'f'), 
    ('Iron - Fe', 'fe'), ('Fermium - Fm', 'fm'), ('Francium - Fr', 'fr'), ('Gallium - Ga', 'ga'), 
    ('Gadolinium - Gd', 'gd'), ('Germanium - Ge', 'ge'), ('Hydrogen - H', 'h'), ('Hafnium - Hf', 'hf'), 
    ('Mercury - Hg', 'hg'), ('Holmium - Ho', 'ho'), ('Iodine - I', 'i'), ('Indium - In', 'in'), 
    ('Iridium - Ir', 'ir'), ('Potassium - K', 'k'), ('Krypton - Kr', 'kr'), ('Lanthanum - La', 'la'), 
    ('Lithium - Li', 'li'), ('Lawrencium - Lr', 'lr'), ('Lutetium - Lu', 'lu'), ('Mendelevium - Md', 'md'), 
    ('Magnesium - Mg', 'mg'), ('Manganese - Mn', 'mn'), ('Molybdenum - Mo', 'mo'), ('Nitrogen - N', 'n'), 
    ('Sodium - Na', 'na'), ('Niobium - Nb', 'nb'), ('Neodymium - Nd', 'nd'), ('Neon - Ne', 'ne'), 
    ('Nickel - Ni', 'ni'), ('Nobelium - No', 'no'), ('Neptunium - Np', 'np'), ('Oxygen - O', 'o'), 
    ('Osmium - Os', 'os'), ('Phosphorus - P', 'p'), ('Protactinium - Pa', 'pa'), ('Lead - Pb', 'pb'), 
    ('Palladium - Pd', 'pd'), ('Promethium - Pm', 'pm'), ('Polonium - Po', 'po'), ('Praseodymium - Pr', 'pr'), 
    ('Platinum - Pt', 'pt'), ('Plutonium - Pu', 'pu'), ('Radium - Ra', 'ra'), ('Rubidium - Rb', 'rb'), 
    ('Rhenium - Re', 're'), ('Rutherfordium - Rf', 'rf'), ('Rhodium - Rh', 'rh'), ('Radon - Rn', 'rn'), 
    ('Ruthenium - Ru', 'ru'), ('Sulfur - S', 's'), ('Antimony - Sb', 'sb'), ('Scandium - Sc', 'sc'), 
    ('Selenium - Se', 'se'), ('Silicon - Si', 'si'), ('Samarium - Sm', 'sm'), ('Tin - Sn', 'sn'), 
    ('Strontium - Sr', 'sr'), ('Tantalum - Ta', 'ta'), ('Terbium - Tb', 'tb'), ('Technetium - Tc', 'tc'), 
    ('Tellurium - Te', 'te'), ('Thorium - Th', 'th'), ('Titanium - Ti', 'ti'), ('Thallium - Tl', 'tl'), 
    ('Thulium - Tm', 'tm'), ('Uranium - U', 'u'), ('Vanadium - V', 'v'), ('Tungsten - W', 'w'), 
    ('Xenon - Xe', 'xe'), ('Yttrium - Y', 'y'), ('Ytterbium - Yb', 'yb'), ('Zinc - Zn', 'zn'), 
    ('Zirconium - Zr', 'zr')
]

# Comparison operators for assay filtering
COMPARISON_OPERATORS: List[str] = ['>', '<', '=', '!=', '>=', '<=']

# Default hole types (fallback if API fails)
DEFAULT_HOLE_TYPES: List[str] = ['RAB', 'DIAMOND', 'AC', 'RC']

# API endpoints
API_ENDPOINTS = {
    'holes_count': 'plugin/fetch_dh_count',
    'holes_data': 'plugin/fetch_drill_holes',
    'assays_count': 'plugin/fetch_assay_count',
    'assays_data': 'plugin/fetch_assay_samples',
    'companies_search': 'companies/search',
    'hole_types': 'plugin/fetch_hole_type'
}

# UI Configuration
UI_CONFIG = {
    'main_window': {
        'title': 'Needle Digital - Mining Data Importer',
        'min_width': 850,
        'min_height': 700
    },
    'brand_label': {
        'text': 'Geochemical Data Importer',
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
    'fetch_all_no_state': 'Currenlty our plugin support fetching all data state-wise. Please select 1 state for which you want all data.',
    'fetch_all_multiple_states': 'Currenlty our plugin support fetching all data state-wise. Please select 1 state for which you want all data.',
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