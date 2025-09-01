# Deployment Guide - Needle Digital Mining Data Importer

This guide covers production deployment of the QGIS plugin.

## Pre-Deployment Checklist

### Security Verification

- [ ] Verify `src/config/secrets.env` is added to `.gitignore`
- [ ] Confirm no hardcoded API keys in source code
- [ ] Test environment variable configuration
- [ ] Validate Firebase API key permissions

### Code Quality

- [ ] All modules have proper docstrings
- [ ] Error handling implemented throughout
- [ ] Logging configured appropriately
- [ ] Input validation in place

### Testing

- [ ] Unit tests pass
- [ ] Integration tests complete
- [ ] Manual testing in QGIS environment
- [ ] Authentication flow tested
- [ ] Data import functionality verified

## Production Configuration

### Environment Variables

Set these environment variables in the production environment:

```bash
# Required
export NEEDLE_FIREBASE_API_KEY="production_firebase_api_key"
export NEEDLE_BASE_API_URL="https://v2-api.needle.digital/api/v2"

# Optional (for logging level)
export NEEDLE_LOG_LEVEL="INFO"
```

## Packaging for Distribution

### Create Distribution Package

```bash
# Remove development files
rm -rf backup/
rm -rf test/
rm -rf .git/

# Create zip package
cd ..
zip -r needle-digital-qgis-plugin.zip platform-qgis-plugin/ -x "*.env" "*.pyc" "__pycache__/*" ".git/*"
```

### File Structure for Distribution

```
needle-digital-qgis-plugin/
├── src/
│   ├── api/
│   ├── config/
│   ├── core/
│   ├── ui/
│   └── utils/
├── help/
├── icon.png
├── metadata.txt
├── __init__.py
├── data_importer.py
├── README.md
├── DEPLOYMENT.md
└── .gitignore
```

## Installation Instructions for End Users

### Method 1: Manual Installation

1. Download the plugin package
2. Extract to QGIS plugins directory
3. Configure authentication (see Configuration section in README)
4. Restart QGIS
5. Enable plugin in Plugin Manager

### Method 2: QGIS Plugin Repository (Future)

When available through official channels:
1. Open QGIS Plugin Manager
2. Search for "Needle Digital Mining Data Importer"
3. Click Install
4. Configure authentication

## Configuration Management

### Production Environment Variables

**Windows (System Environment)**
```cmd
setx NEEDLE_FIREBASE_API_KEY "your_production_key"
setx NEEDLE_BASE_API_URL "https://v2-api.needle.digital/api/v2"
```

**Linux/macOS (Profile)**
```bash
# Add to ~/.bashrc or ~/.zshrc
export NEEDLE_FIREBASE_API_KEY="your_production_key"
export NEEDLE_BASE_API_URL="https://v2-api.needle.digital/api/v2"
```

### Docker Deployment (If Applicable)

```dockerfile
# In Dockerfile
ENV NEEDLE_FIREBASE_API_KEY="your_production_key"
ENV NEEDLE_BASE_API_URL="https://v2-api.needle.digital/api/v2"
```

## Monitoring and Logging

### Log Locations

- **Windows**: Check QGIS message log panel
- **Linux/macOS**: Check QGIS message log panel and system logs
- **Development**: Console output with detailed logging

### Log Levels

Configure logging level via environment variable:
```bash
export NEEDLE_LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Troubleshooting Common Deployment Issues

### Authentication Issues

**Problem**: "Firebase API Key not found"
**Solution**: Verify environment variables or config file setup

**Problem**: "Login failed" errors
**Solution**: Check API key validity and network connectivity

### Import Issues

**Problem**: QGIS import errors
**Solution**: Verify QGIS version compatibility (3.0+)

**Problem**: Module import errors
**Solution**: Check Python path and QGIS plugin installation

### Performance Issues

**Problem**: Slow data fetching
**Solution**: Monitor network connectivity and API response times

**Problem**: UI freezing
**Solution**: Check for Qt event loop issues; ensure async operations

## Security Considerations

### API Key Management

- Never commit API keys to version control
- Use environment variables in production
- Rotate keys regularly
- Monitor API usage for anomalies

### Network Security

- All API calls use HTTPS
- Validate SSL certificates
- Monitor for network interception

### Data Handling

- No sensitive data cached locally
- User credentials handled securely
- Automatic token refresh implemented

## Version Management

### Semantic Versioning

- **Major.Minor.Patch** format
- Update `metadata.txt` version
- Update `PLUGIN_VERSION` in constants
- Tag releases in version control

### Release Process

1. Update version numbers
2. Update changelog
3. Run full test suite
4. Create release package
5. Update documentation
6. Deploy to distribution channels

## Support and Maintenance

### Issue Tracking

- Monitor plugin logs for errors
- Track user feedback and issues
- Maintain issue tracking system

### Updates and Patches

- Regular security updates
- API compatibility maintenance  
- QGIS version compatibility updates
- User-requested features

## Rollback Procedures

If deployment issues occur:

1. **Immediate**: Disable plugin in QGIS
2. **Short-term**: Revert to previous version
3. **Investigation**: Analyze logs and error reports
4. **Fix**: Apply patches and redeploy
5. **Testing**: Verify fix before re-enabling

## Contact Information

**Technical Support**: divyansh@needle-digital.com
**Development Team**: divyansh@needle-digital.com
**Security Issues**: divyansh@needle-digital.com