# Obscura Telegram File Downloader

A powerful and efficient Telegram file downloader that can monitor and download files from multiple channels automatically.

## Features

- Download files from multiple Telegram channels simultaneously
- Support for both public and private channels
- Automatic file organization by channel
- Duplicate file detection
- Progress tracking with beautiful UI
- Comprehensive logging system
- Configurable file type filtering
- Automatic reconnection handling
- File sanitization for safe filenames

## Requirements

- Python 3.7+
- Telegram API credentials (API_ID and API_HASH)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/frankiejav/obscura-backend.git
cd obscura-backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with your Telegram API credentials:
```
API_ID=your_api_id
API_HASH=your_api_hash
```

## Configuration

Edit `config.py` to configure:
- Target channels (public usernames or private channel IDs)
- Allowed file extensions
- Download settings
- Monitoring intervals
- Logging preferences

## Usage

Run the script:
```bash
python main.py
```

The script will:
1. Connect to Telegram
2. Download existing files from configured channels
3. Monitor for new files
4. Save files in organized channel-specific folders

## Directory Structure

- `downloads/` - Downloaded files organized by channel
- `logs/` - Application logs
- `main.py` - Main application code
- `config.py` - Configuration settings
- `requirements.txt` - Python dependencies

## Security

- API credentials are stored in environment variables
- File size limits prevent abuse
- Proper error handling and connection management

## License

MIT License 