# Environment Setup

## Setting up API Keys

This plugin uses external APIs that require authentication keys. These keys should NOT be committed to the repository.

### 1. Copy the environment template:
```bash
cp .env.example .env
```

### 2. Edit the `.env` file with your actual API keys:
```
NEW_RELIC_API_KEY=your_actual_newrelic_api_key_here
NEEDLE_FIREBASE_API_KEY=your_actual_firebase_key_here
NEEDLE_BASE_API_URL=your_actual_api_url_here
```

### 3. The `.env` file is already in `.gitignore` and will not be committed to Git.

## For Contributors

If you're contributing to this project:

1. Copy `.env.example` to `.env`
2. Contact the project maintainers for the actual API keys
3. Never commit actual API keys to the repository
4. Always use environment variables for sensitive data

## For Deployment

In production environments, set these environment variables:
- `NEW_RELIC_API_KEY` - For logging
- `NEEDLE_FIREBASE_API_KEY` - For authentication
- `NEEDLE_BASE_API_URL` - For API endpoints

The plugin will automatically use environment variables if available, falling back to configuration files.