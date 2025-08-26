# Needle Digital Mining Data Importer

A QGIS plugin for importing Australian drill hole and assay data directly into your QGIS projects. This plugin provides seamless access to geochemical mining data through an authenticated API, allowing geologists and mining professionals to analyze and visualize exploration data efficiently.

![QGIS Plugin](https://img.shields.io/badge/QGIS-Plugin-green)
![Python](https://img.shields.io/badge/Python-3.x-blue)
![License](https://img.shields.io/badge/License-GPL--2.0-blue)

## 🔍 Overview

The Needle Digital Mining Data Importer connects to a comprehensive database of Australian mining exploration data, providing access to:

- **Drill Hole Data**: Location coordinates, depths, orientations, and metadata
- **Assay Data**: Geochemical analysis results with customizable filtering options
- **Company & State Filtering**: Search by mining company or Australian state
- **Real-time Data Access**: Live connection to updated mining datasets

## ✨ Features

### 🔐 Secure Authentication
- Firebase-based authentication system
- Automatic token refresh for uninterrupted access
- Session persistence across QGIS restarts

### 📊 Advanced Data Filtering
- **Company Search**: Dynamic search with autocomplete for mining companies
- **Geographic Filtering**: Filter data by Australian states (NSW, QLD, SA, TAS, VIC, WA, NT)
- **Element-based Filtering**: Search assay data by specific elements (Cu, Au, Pb, Zn, Mn, Al)
- **Value Filtering**: Apply mathematical operators (>, <, =, !=, >=, <=) for precise data selection

### 🗺️ Intelligent Data Import
- **Spatial Data Support**: Automatically creates point geometries from latitude/longitude coordinates
- **Attribute Management**: Preserves all data fields with appropriate data types
- **Layer Customization**: Configure layer names and point styling during import
- **Basemap Integration**: Automatically adds OpenStreetMap basemap for spatial context

### 🚀 Performance Optimized
- **Chunked Data Fetching**: Handles large datasets efficiently with configurable batch sizes
- **Pagination Support**: Navigate through results with built-in pagination controls
- **Progress Tracking**: Real-time progress indicators for data operations
- **Memory Management**: Efficient caching system for smooth user experience

## 🛠️ Installation

### Prerequisites
- QGIS 3.0 or higher
- Internet connection for data access
- Valid Needle Digital account credentials

### Installation Steps

1. **Download the Plugin**
   ```bash
   git clone https://github.com/NeedleDigital/platform-qgis-plugin.git
   ```

2. **Copy to QGIS Plugin Directory**
   ```
   # On Windows
   C:\Users\[username]\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\

   # On macOS
   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/

   # On Linux
   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
   ```

3. **Enable the Plugin**
   - Open QGIS
   - Go to `Plugins` → `Manage and Install Plugins`
   - Search for "Needle Digital" or "Data Importer"
   - Check the box to enable the plugin

## 🚀 Quick Start

### 1. Authentication
1. Launch the plugin from the toolbar or `Plugins` menu
2. Click the "Login" button
3. Enter your Needle Digital credentials
4. The plugin will automatically save your session for future use

### 2. Fetching Drill Hole Data
1. Navigate to the "Holes" tab
2. **Optional Filtering**:
   - Type company names in the search box for autocomplete suggestions
   - Select one or more Australian states
   - Set the number of records to fetch (or check "Fetch all records")
3. Click "Fetch Holes" to retrieve data
4. Browse results using pagination controls

### 3. Fetching Assay Data
1. Navigate to the "Assays" tab
2. **Configure Filters**:
   - Select target element (Cu, Au, Pb, Zn, Mn, Al)
   - Choose comparison operator (>, <, =, etc.)
   - Enter threshold value for filtering
   - Select Australian states if needed
3. Click "Fetch Assay Data" to retrieve filtered results

### 4. Importing to QGIS
1. After fetching data, click "Import All Data to QGIS"
2. **Customize Import Settings**:
   - Modify layer name
   - Choose point color for spatial data
3. Click "OK" to create the layer in your QGIS project

## 🖥️ User Interface

### Main Dialog Components

- **Authentication Panel**: Login/logout functionality with session status
- **Tabbed Interface**: Separate tabs for Holes and Assays data
- **Filter Controls**: Dynamic search widgets and dropdown filters
- **Data Table**: Paginated display of fetched records
- **Progress Tracking**: Status bar and progress indicator
- **Action Buttons**: Clear data, reset filters, and import functions

### Filter Widgets

- **Dynamic Company Search**: Real-time search with popup suggestions
- **State Multi-Select**: Checkbox-based state selection with visual chips
- **Element & Value Filters**: Dropdown and text input combinations
- **Record Limit Controls**: Input field with "fetch all" option

## 🔧 Technical Details

### Architecture
- **Plugin Framework**: PyQt5-based QGIS plugin architecture
- **Authentication**: Firebase Authentication with JWT tokens
- **API Communication**: REST API with automatic retry and error handling
- **Data Management**: In-memory caching with paginated display
- **Spatial Processing**: QGIS geometry and coordinate reference system integration

### API Endpoints
- `companies/search`: Company name autocomplete
- `plugin/fetch_dh_count`: Drill hole record count
- `plugin/fetch_drill_holes`: Drill hole data retrieval
- `plugin/fetch_assay_count`: Assay record count  
- `plugin/fetch_assay_samples`: Assay data retrieval

### Data Fields

#### Drill Holes
- Geographic coordinates (latitude, longitude)
- Drill hole metadata (depth, dip, azimuth)
- Company and location information
- Drilling parameters and specifications

#### Assays
- Sample identification and location
- Element concentrations and values
- Sampling depth intervals (from_depth, to_depth)
- Laboratory and analysis metadata

## 🧪 Development & Testing

### Running Tests
```bash
cd data_importer
make test
```

### Development Setup
```bash
# Compile resources
pyrcc5 -o resources.py resources.qrc

# Update translations
scripts/update-strings.sh

# Compile translations
scripts/compile-strings.sh
```

## 🤝 Contributing

We welcome contributions to improve the plugin! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

### Development Guidelines
- Follow Python PEP 8 style guidelines
- Add tests for new functionality
- Update documentation for API changes
- Ensure compatibility with QGIS 3.x versions

## 🐛 Troubleshooting

### Common Issues

**Authentication Errors**
- Verify internet connection
- Check credentials are correct
- Clear saved tokens: Settings → Reset All

**No Data Returned**
- Adjust filter criteria (try broader search terms)
- Check selected states/companies are valid
- Verify element and value filters are reasonable

**Import Failures**
- Ensure data contains latitude/longitude for spatial layers
- Check QGIS project coordinate reference system
- Verify sufficient memory for large datasets

**Performance Issues**
- Reduce record count for initial testing
- Use pagination to browse large datasets
- Clear cache periodically: Reset All button

### Error Reporting
If you encounter bugs or issues:
1. Check the QGIS Python console for error messages
2. Report issues at: https://github.com/NeedleDigital/platform-qgis-plugin/issues
3. Include QGIS version, plugin version, and error details

## 📄 License

This project is licensed under the GNU General Public License v2.0 - see the [LICENSE](LICENSE) file for details.

## 🏢 About Needle Digital

Needle Digital specializes in providing comprehensive mining and exploration data solutions. Our platform aggregates and standardizes geological data from across Australia, making it accessible to researchers, consultants, and mining companies.

**Contact Information:**
- Website: https://needle-digital.com
- Repository: https://github.com/NeedleDigital/platform-qgis-plugin
- Issues: https://github.com/NeedleDigital/platform-qgis-plugin/issues

---

*Built with ❤️ for the mining and geological community*