# Needle Digital Mining Data Importer

A QGIS plugin for importing Australian mining drill hole and assay data from the Needle Digital platform.

## Features

- **Secure Authentication**: Firebase-based user authentication with automatic token refresh
- **Drill Hole Data Import**: Search and import drill hole data by state and company
- **Assay Data Import**: Filter assay data by chemical element, comparison operator, and values
- **Comprehensive Element Support**: 80+ chemical elements with proper display names (e.g., "Copper - Cu")
- **Bulk Data Handling**: Fetch all records or specify record limits
- **QGIS Integration**: Direct import to QGIS with customizable styling
- **Production Ready**: Modular architecture with secure configuration management

## Installation

### Prerequisites

- QGIS 3.0 or higher
- Python 3.6+
- Active internet connection for API access

### Manual Installation

1. Download or clone this repository
2. Copy the entire plugin folder to your QGIS plugins directory:
   - **Windows**: `C:\Users\{username}\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

3. Set up configuration (see Configuration section below)
4. Restart QGIS
5. Enable the plugin in QGIS Plugin Manager

## Configuration

### Environment Variables (Recommended for Production)

Set the following environment variables:

```bash
export NEEDLE_FIREBASE_API_KEY="your_firebase_api_key"
export NEEDLE_BASE_API_URL="https://master.api.drh.needle-digital.com"
```

### Configuration File (Development)

```bash
NEEDLE_FIREBASE_API_KEY=your_firebase_api_key_here
NEEDLE_BASE_API_URL=https://master.api.agni.needle-digital.com
```

**Important**: Never commit the `secrets.env` file to version control.

## Usage

1. **Open the Plugin**: Go to Plugins → Needle Digital Tools → Mining Data Importer
2. **Login**: Click "Login" and enter your Needle Digital credentials
3. **Select Data Type**: Choose between "Holes" and "Assays" tabs
4. **Configure Filters**:
   - Select Australian state(s)
   - For Holes: Optional company name search
   - For Assays: Select element, comparison operator, and value
5. **Fetch Data**: 
   - Specify record count or check "Fetch all records"
   - Click "Fetch" button
6. **Import to QGIS**: Click "Import All Data to QGIS" to create a new layer

## Architecture

The plugin follows a modular architecture for maintainability and extensibility:

```
├── src/
│   ├── api/           # API client and authentication
│   ├── config/        # Configuration and constants
│   ├── core/          # Core business logic
│   ├── ui/            # User interface components
│   └── utils/         # Utilities and helpers
├── backup/            # Original files backup
├── help/              # Documentation
└── test/              # Unit tests
```

### Key Components

- **ApiClient**: Handles authentication and API requests
- **DataManager**: Core data fetching and processing logic
- **QGISLayerManager**: QGIS integration and layer creation
- **MainDialog**: Primary user interface
- **Components**: Reusable UI widgets (chips, filters, etc.)

## Development

### Setting Up Development Environment

1. Clone the repository
2. Install development dependencies (if any)
3. Set up configuration as described above
4. Use QGIS Plugin Reloader for development

### Code Style

- Follow PEP 8 standards
- Use type hints where appropriate
- Document all public methods and classes
- Include comprehensive logging

### Testing

Run tests using:

```bash
python -m pytest test/
```

## Security

- **Secrets Management**: API keys stored in environment variables or secure config files
- **No Hardcoded Credentials**: All sensitive information externalized
- **Secure Authentication**: Firebase JWT token-based authentication
- **Input Validation**: All user inputs validated and sanitized

## Troubleshooting

### Configuration Issues

- **"Firebase API Key not found"**: Ensure environment variables or config file is properly set
- **Import errors**: Check that all dependencies are available in QGIS Python environment

### Authentication Issues

- **Login fails**: Verify API key and network connectivity
- **Token expired**: Plugin automatically refreshes tokens; check logs for details

### Data Issues

- **No data returned**: Check filter criteria and available data for selected parameters
- **Import fails**: Ensure data contains valid coordinates (latitude/longitude)

## Support

For support and issues:

1. Check the troubleshooting section above
2. Review plugin logs in QGIS
3. Contact Needle Digital support

## Version History

### 1.0.0
- Initial modular release
- Secure configuration management
- Enhanced UI with custom components
- Comprehensive element support
- Production-ready architecture

## License

© 2025 Needle Digital. All rights reserved.