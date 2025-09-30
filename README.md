# ND Data Importer - QGIS Plugin

A comprehensive QGIS plugin for importing and visualizing Australian mining drill hole and assay data directly into your GIS projects.

![Plugin Version](https://img.shields.io/badge/version-1.3.0-blue)
![QGIS Version](https://img.shields.io/badge/QGIS-3.0%2B-green)
![License](https://img.shields.io/badge/license-GPL--3.0-orange)

## 📋 Overview

The ND Data Importer provides seamless access to Australia's comprehensive mining database, allowing geologists, mining engineers, and researchers to import drill hole and assay data directly into QGIS for spatial analysis and visualization.

### Key Features

- 🔍 **State-wise Data Filtering**: Filter data by Australian states and territories
- 🏢 **Company-specific Data**: Search and filter by mining companies with auto-complete
- 🧪 **Chemical Element Analysis**: Filter assay data by specific elements (Au, Cu, Fe, etc.)
- 🎯 **Advanced Hole Type Filtering**: Filter by drilling method (RAB, RC, Diamond, AC)
- 📏 **Depth-based Filtering**: Set maximum depth limits for drill hole data
- 📊 **Large Dataset Support**: Optimized handling of datasets up to 1M+ records
- 🗺️ **Auto Base Layer**: Automatic OpenStreetMap integration for spatial context
- ⚡ **Performance Optimized**: Chunked processing with progress tracking
- 💡 **Smart Hover Tooltips**: Hover over points to see company name, hole ID, or collar ID
- 🏠 **Adaptive Window Layout**: Full-height, 75% width window automatically centered to QGIS
- 🎯 **User-friendly Interface**: Intuitive tabbed interface with real-time feedback
- 👤 **Role-Based Access Control**: Tiered subscription plans (Free Trial, Premium, Admin)
- 🔒 **Free Trial Limitations**: 1,000 record limit per fetch with upgrade prompts
- 🏷️ **User Plan Badge**: Clickable badge showing current tier with detailed plan information
- 📍 **Enhanced Location Data**: Latitude/longitude fields visible in Identify Results for location-only imports
- ✅ **Smart Input Validation**: Real-time validation with visual feedback for record count limits

## 📁 Project Structure

```
platform-qgis-plugin/
├── 📄 README.md                    # This documentation file
├── 📄 LICENSE                      # GPL-3.0 license file
├── 📄 metadata.txt                 # QGIS plugin metadata
├── 📄 data_importer.py              # Main plugin class and entry point
├── 📄 __init__.py                   # Plugin initialization
├── 📄 resources.py                  # UI resources and assets
├── 📄 icon.png                      # Plugin toolbar icon
├── 📁 src/                          # Source code directory
│   ├── 📁 config/                   # Configuration and constants
│   │   ├── 📄 constants.py          # API endpoints, UI settings, limits
│   │   └── 📄 settings.py           # Firebase and authentication settings
│   ├── 📁 core/                     # Core business logic
│   │   └── 📄 data_manager.py       # API communication and data handling
│   ├── 📁 ui/                       # User interface components
│   │   ├── 📄 main_dialog.py        # Main plugin dialog window
│   │   └── 📄 components.py         # Reusable UI widgets and dialogs
│   ├── 📁 utils/                    # Utility functions
│   │   ├── 📄 qgis_helpers.py       # QGIS integration and layer management
│   │   ├── 📄 logging.py            # Logging configuration
│   │   └── 📄 validation.py         # Data validation utilities
│   └── 📁 api/                      # API client implementation
│       └── 📄 client.py             # HTTP client for Needle Digital API
├── 📁 test/                         # Test suite
└── 📁 build-tools/                  # Build and deployment scripts
    ├── 📄 Makefile                  # Build automation
    ├── 📄 pb_tool.cfg               # Plugin builder configuration
    └── 📄 plugin_upload.py          # Plugin repository upload script
```

## 🔧 Installation

### Prerequisites

- QGIS 3.0 or higher
- Python 3.6+
- Internet connection for data fetching
- Valid Needle Digital account credentials

### Installation Methods

#### Method 1: QGIS Plugin Repository (Recommended)

1. Open QGIS
2. Navigate to `Plugins` → `Manage and Install Plugins...`
3. Search for "ND Data Importer"
4. Click `Install Plugin`

#### Method 2: Manual Installation

1. Download the plugin ZIP file
2. Open QGIS
3. Navigate to `Plugins` → `Manage and Install Plugins...`
4. Click `Install from ZIP`
5. Select the downloaded ZIP file

#### Method 3: Development Installation

```bash
# Clone the repository
git clone https://github.com/NeedleDigital/platform-qgis-plugin.git

# Navigate to QGIS plugins directory
# Linux: ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
# Windows: %APPDATA%\\QGIS\\QGIS3\\profiles\\default\\python\\plugins\\
# macOS: ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/

# Copy the plugin directory
cp -r platform-qgis-plugin needle-digital-importer
```

## 🚀 Getting Started

### 1. Account Setup

**Important**: To access the mining data, you need valid login credentials.

📧 **Contact**: divyansh@needle-digital.com

- Request access to the Needle Digital mining database
- Provide your organization details and intended use case
- Receive your login credentials via email

### 2. Plugin Activation

1. Open QGIS
2. Navigate to `Plugins` → `Manage and Install Plugins...`
3. Enable "ND Data Importer"
4. The plugin icon will appear in your toolbar

### 3. First Login

1. Click the Needle Digital plugin icon in the toolbar
2. Click the "Login" button in the dialog
3. Enter your credentials received from Needle Digital
4. Upon successful authentication, you can begin importing data
5. Your subscription tier badge will appear in the top-left of the plugin window

## 💳 Subscription Tiers

The plugin supports three subscription tiers with different capabilities:

### 🆓 Free Trial (Tier 1)
- Access to Australian mining drill hole and assay data
- State, company, and element filtering
- **Maximum 1,000 records per fetch**
- Cannot use "Fetch all records" feature
- Ideal for: Exploration and small-scale projects

### ⭐ Premium (Tier 2)
- All Free Trial features
- **Unlimited record fetching**
- "Fetch all records" capability enabled
- Advanced filtering options
- Priority support
- Ideal for: Professional mining operations and research

### 👑 Admin (Tier 3)
- All Premium features
- Administrative privileges
- Complete system access
- Ideal for: Enterprise deployments and system administrators

**To upgrade your subscription**, contact: divyansh@needle-digital.com

### Role Badge

After login, you'll see a colored badge next to the Needle Digital logo showing your current tier:
- 🔵 **Blue Badge**: Free Trial
- 🟡 **Gold Badge**: Premium
- 🟣 **Purple Badge**: Admin

Click the badge to view detailed information about your plan's features and limitations.

## 📊 Usage Guide

### Main Interface

The plugin features a tabbed interface with two main sections:

#### 🕳️ Holes Tab - Drill Hole Data

- **Purpose**: Import drill hole collar and survey data
- **Data Includes**: Hole ID, coordinates, depth, company, project details
- **Filters Available**:
  - State/Territory selection (NSW, QLD, SA, TAS, VIC, WA, NT)
  - Company name search with auto-complete (3+ character minimum)
  - Hole type filtering (RAB, RC, Diamond, AC)
  - Maximum depth filtering (numeric input ≥0)
  - Record count control (specific number or "fetch all")
  - Location-only mode for performance optimization

#### 🧪 Assays Tab - Chemical Analysis Data

- **Purpose**: Import geochemical assay results
- **Data Includes**: Sample data with chemical element concentrations in ppm
- **Filters Available**:
  - Chemical element selection (112 elements: Au, Cu, Fe, Zn, etc.)
  - Concentration thresholds with operators (>, <, =, !=, >=, <=)
  - State/Territory selection (NSW, QLD, SA, TAS, VIC, WA, NT)
  - Company name search with auto-complete (3+ character minimum)
  - Hole type filtering (RAB, RC, Diamond, AC)
  - Record count control (specific number or "fetch all")
  - Location-only mode for performance optimization

### Data Import Workflow

1. **Select Data Type**: Choose between "Holes" or "Assays" tab
2. **Apply Filters**: Use the filter controls to narrow your dataset
3. **Preview Results**: Click "Fetch Data" to preview available records
4. **Review Data**: Browse the paginated table results
5. **Import to QGIS**: Click "Import to QGIS" to add data as map layers

### Large Dataset Handling

The plugin automatically optimizes performance for large datasets:

- **50,000+ records**: Warning dialog with import options
- **Chunked Processing**: Data processed in 10,000 record batches
- **Progress Tracking**: Real-time progress updates during import
- **Memory Management**: Automatic garbage collection between chunks
- **User Cancellation**: Cancel long-running operations at any time

### Map Visualization

Upon successful import:

- **Point Layers**: Drill holes and assay locations plotted as red points (size 2.0, 80% opacity)
- **Base Map**: OpenStreetMap automatically added for geographical context
- **Smart Hover Tooltips**:
  - **Full Data Mode**: Shows company name and hole ID (or collar ID as fallback)
  - **Location-Only Mode**: Shows latitude and longitude coordinates
  - Tooltips styled with white background and dark text for readability
- **Identify Results**:
  - **Location-Only Mode**: Latitude and longitude fields included in feature attributes
  - **Full Data Mode**: All imported fields accessible via attribute inspection
- **Adaptive Window**: Plugin window automatically sized to 75% width, full height, centered to QGIS
- **Layer Management**: Automatic coordinate system handling (WGS84/EPSG:4326)
- **Performance Optimization**: Auto-zoom disabled for datasets >50,000 records
- **Attribute Data**: Full dataset accessible via attribute tables

### Enhanced User Interface

The plugin now features several UI/UX improvements:

- **Adaptive Layout**: Main window automatically resizes to 75% of QGIS width and full height
- **Centered Positioning**: Plugin window automatically centers relative to QGIS main window
- **Advanced Filtering**: Multi-select dropdowns with chip display for selected items
- **Dynamic Company Search**: Real-time company name suggestions with 3+ character minimum
- **Hole Type Integration**: API-driven hole type options with fallback to defaults
- **Improved Alignment**: Proper widget alignment preventing layout shifts when chips appear
- **Visual Feedback**: Clear status messages and error handling throughout the interface

## ⚙️ Configuration

### Constants Configuration (`src/config/constants.py`)

Key configuration parameters:

```python
# Import Performance Settings
IMPORT_CHUNK_SIZE = 10000                    # Records per processing chunk
LARGE_IMPORT_WARNING_THRESHOLD = 50000       # Warn above this count
MAX_SAFE_IMPORT = 100000                     # Recommend alternatives above
PARTIAL_IMPORT_LIMIT = 50000                 # Maximum partial import
CHUNKED_IMPORT_THRESHOLD = 5000              # Use chunking above this count
AUTO_ZOOM_THRESHOLD = 50000                  # Disable auto-zoom above this count

# API Configuration
API_FETCH_LIMIT = 50000                      # Maximum records per API request
NEEDLE_BASE_API_URL = "https://master.api.drh.needle-digital.com"

```

### Layer Styling (`src/config/constants.py`)

```python
DEFAULT_LAYER_STYLE = {
    'point_color': '#ff0000',      # Red points
    'point_size': 2,               # Point size in pixels
    'point_transparency': 0.8      # 80% opacity
}
```

## 🏗️ Architecture

### Component Overview

#### Core Components

1. **DataImporter** (`data_importer.py`)

   - Main plugin class and QGIS integration
   - Handles toolbar actions and plugin lifecycle
   - Coordinates between UI and business logic

2. **DataManager** (`src/core/data_manager.py`)

   - API communication and data processing
   - Pagination and chunked data fetching
   - Signal-based communication with UI

3. **Main Dialog** (`src/ui/main_dialog.py`)
   - Primary user interface
   - Tabbed layout for different data types
   - Real-time feedback and progress tracking

#### Supporting Components

4. **QGIS Helpers** (`src/utils/qgis_helpers.py`)

   - QGIS layer creation and management
   - Spatial data processing
   - Map styling and visualization

5. **API Client** (`src/api/client.py`)

   - HTTP communication with Needle Digital API
   - Authentication and session management
   - Error handling and retry logic

6. **UI Components** (`src/ui/components.py`)
   - Reusable dialog components
   - Filter widgets and input controls
   - Progress and warning dialogs

### Data Flow

```
User Input → Main Dialog → Data Manager → API Client → Needle Digital API
                                    ↓
QGIS Layers ← QGIS Helpers ← Data Processing ← API Response
```

## 🧪 Testing

### Running Tests

```bash
# Navigate to project directory
cd platform-qgis-plugin

# Run all tests
python -m pytest test/

# Run specific test file
python -m pytest test/test_data_manager.py

# Run with coverage
python -m pytest --cov=src test/
```

### Test Structure

- `test/test_qgis_environment.py` - QGIS integration tests
- `test/test_data_manager.py` - API and data processing tests
- `test/test_ui_components.py` - UI widget tests
- `test/test_validation.py` - Data validation tests

## 🔧 Development

### Development Setup

```bash
# Clone repository
git clone https://github.com/NeedleDigital/platform-qgis-plugin.git
cd platform-qgis-plugin

# Install development dependencies
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install

# Run linting
make lint

# Run tests
make test
```

### Building for Distribution

```bash
# Create plugin package
make package

# Upload to QGIS repository (requires credentials)
make deploy
```

### Code Style

The project follows PEP 8 standards with:

- Line length: 100 characters
- Indentation: 4 spaces
- Import sorting with isort
- Code formatting with black
- Linting with pylint

## 🐛 Troubleshooting

### Common Issues

#### Authentication Problems

- **Symptom**: Login fails with valid credentials
- **Solution**: Check internet connection and contact divyansh@needle-digital.com

#### Large Dataset Timeouts

- **Symptom**: Import fails on large datasets
- **Solution**: Use partial import option or filter data further

#### Memory Issues

- **Symptom**: QGIS becomes unresponsive during import
- **Solution**: Enable chunked processing for datasets >50,000 records

#### Missing Base Layer

- **Symptom**: No background map visible
- **Solution**: Check internet connection for OpenStreetMap tiles

### Debug Mode

Enable debug logging by setting:

```python
# In src/utils/logging.py
LOG_LEVEL = logging.DEBUG
```

### Getting Help

1. **Check the logs**: View QGIS message log for error details
2. **Report issues**: Create detailed bug reports on GitHub
3. **Contact support**: Email divyansh@needle-digital.com for technical issues

## 📄 License

This project is licensed under the GNU General Public License v3.0 or later (GPL-3.0+).

See the [LICENSE](LICENSE) file for full license text.

### License Summary

- ✅ **Use**: Free to use for any purpose
- ✅ **Modify**: Modify the source code
- ✅ **Distribute**: Distribute original and modified versions
- ⚠️ **Share-alike**: Derivative works must use same license
- ⚠️ **Source code**: Must provide source code with distributions

## 🤝 Contributing

We welcome contributions from the community!

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Contribution Guidelines

- Follow the existing code style and conventions
- Add tests for new functionality
- Update documentation for significant changes
- Ensure all tests pass before submitting

## 📞 Support & Contact

### Technical Support

- **Email**: divyansh@needle-digital.com
- **GitHub Issues**: [Report bugs and feature requests](https://github.com/NeedleDigital/platform-qgis-plugin/issues)

### Account & Access

- **Data Access**: divyansh@needle-digital.com
- **Enterprise Support**: Contact for custom integrations and support plans

### Community

- **Documentation**: [GitHub Wiki](https://github.com/NeedleDigital/platform-qgis-plugin/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/NeedleDigital/platform-qgis-plugin/discussions)

## 🔄 Version History

### v1.3.0 (Current) - Role-Based Access Control Edition

**New Role-Based Features:**
- ✅ **Subscription Tiers**: Free Trial, Premium, and Admin tiers with different capabilities
- ✅ **JWT Token Authentication**: Automatic role extraction from Firebase auth tokens
- ✅ **Free Trial Limits**: 1,000 record maximum per fetch with real-time validation
- ✅ **Role Badge Display**: Clickable badge showing user tier (Blue/Gold/Purple)
- ✅ **Plan Information**: Detailed popup showing tier features and limitations
- ✅ **Smart Restrictions**: Disabled "Fetch all records" for Free Trial with helpful messaging
- ✅ **Input Validation**: Real-time record count validation with visual feedback

**Enhanced Data Visualization:**
- ✅ **Location-Only Improvements**: Latitude/longitude fields now visible in Identify Results
- ✅ **Tooltip Styling**: Fixed location-only tooltips with white background and dark text
- ✅ **Fallback Support**: Hover tooltips show collar_id when hole_id is empty/null
- ✅ **QGIS Compatibility**: Fixed QgsField deprecation warnings (migrated to QMetaType.Type)

**UI/UX Improvements:**
- ✅ **Reset All Enhancement**: Properly re-enables record count field when resetting
- ✅ **Checkbox Behavior**: Fixed text field staying disabled after blocking fetch all
- ✅ **Error Messages**: User-friendly messages for all tier restrictions
- ✅ **Visual Feedback**: Red field styling clears immediately after popup dismissal

### v1.2.0 - Major UI/UX Enhancements and Authentication Improvements

**UI/UX Features:**
- ✅ Fixed critical dropdown focus issues with proper keyboard input handling
- ✅ Implemented chip display limitations (max 4 + "view all" button)
- ✅ Added searchable hole types dropdown with static data
- ✅ Enhanced multi-selection with persistent popup behavior
- ✅ Improved table display with N/A for null values and hover tooltips

**Authentication Features:**
- ✅ Fixed authentication token persistence across plugin sessions
- ✅ Added automatic token validation on plugin open/focus
- ✅ Implemented direct login dialog flow
- ✅ Fixed incorrect logout messages

### v1.1.0 - Enhanced UI/UX with Theme-Aware Styling

- ✅ Comprehensive theme-aware button styling system
- ✅ Automatic light/dark theme detection
- ✅ Professional color scheme with improved readability

### v1.0.0 - Initial Release

**Core Features:**
- ✅ Complete drill hole and assay data import functionality
- ✅ State-wise and company-based filtering with auto-complete
- ✅ Chemical element filtering for assays (112 elements supported)
- ✅ Large dataset optimization (1M+ records with chunked processing)
- ✅ Automatic OpenStreetMap base layer integration
- ✅ Advanced filtering (hole types, depth limits)
- ✅ Smart hover tooltips and adaptive UI

### Planned Features

- 🔄 **v1.4.0**: Advanced visualization modes (heatmaps, graduated symbols, categorized rendering)
- 🔄 **v1.5.0**: Statistical analysis tools and multi-element analysis
- 🔄 **v1.6.0**: 3D visualization and drill hole profiles
- 🔄 **v1.7.0**: Enhanced data export capabilities and reporting tools

---

**Developed by Needle Digital**  
Empowering mining professionals with comprehensive geospatial data solutions.

For questions, support, or data access requests, contact: divyansh@needle-digital.com
