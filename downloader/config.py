import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
DATABASE_ENCRYPTION_KEY = "7f417f906e8a9e9d42dfda19a1b4fbf53e934ef9b3aabe9d6f4bc3eac5e3a4bf"

# Targets will be populated dynamically during channel selection
TARGETS = {}

# File types to download (case-insensitive)
ALLOWED_EXTENSIONS = {
    # Documents
    '.txt', '.doc', '.docx', '.pdf', '.rtf',
    # Data files
    '.csv', '.xls', '.xlsx', '.json', '.xml',
    # Database files
    '.sql', '.db', '.sqlite', '.sqlite3',
    # Log files
    '.log', '.logs',
    # Archive files
    '.zip', '.rar', '.7z', '.tar', '.gz',
    # Config files
    '.cfg', '.conf', '.ini', '.env',
    # Programming files
    '.py', '.js', '.php', '.html', '.css',
    # Empty string to catch files without extensions
    ''
}

# Download settings
DOWNLOAD_PATH = '/storage/obscura/raw'
MAX_FILE_SIZE = 1024 * 1024 * 1024 * 1024 * 1024  # 1 PB (effectively unlimited)
DOWNLOAD_TIMEOUT = 1200 # 20 minutes
ENABLE_PARALLEL_DOWNLOADS = True
MAX_CONCURRENT_DOWNLOADS = 3  # Increased from 6 for better performance
BATCH_SIZE = 12  # Larger batches for efficiency
INTER_BATCH_DELAY = 0.5  # Reduced from 2.0 seconds
MESSAGES_TO_CHECK = 100

# Monitoring Configuration
ENABLE_REAL_TIME_MONITORING = True
POLL_INTERVAL = 15  # Seconds between polling for new messages
MAX_POLL_MESSAGES = 50  # Max messages to check per poll
MONITOR_STARTUP_DELAY = 5  # Seconds to wait before starting monitoring

# Logging Configuration
LOG_PATH = "./logs"
LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR
LOG_ROTATION = "10 MB"
LOG_RETENTION = "1 week"

# Error handling
MAX_CONNECTION_ERRORS = 5
CONNECTION_TIMEOUT = 30  # seconds 

# Security Configuration
DOWNLOAD_QUARANTINE = False  # Set to True to quarantine downloads
QUARANTINE_PATH = "./quarantine"
SCAN_DOWNLOADS = False  # Set to True to enable basic file scanning

# Alert Configuration
ENABLE_ALERTS = True
ALERT_ON_NEW_FILES = True
ALERT_ON_ERRORS = True
ALERT_KEYWORDS = [
    'stealer', 'logs', 'credentials', 'passwords',
    'cookies', 'crypto', 'wallet', 'banking'
]

# Advanced Configuration
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for file operations
PROGRESS_UPDATE_INTERVAL = 0.5  # Seconds between progress updates
ENABLE_COMPRESSION = False  # Compress downloaded files
KEEP_ORIGINALS = True  # Keep original files when compressing

# Rate Limiting
RATE_LIMIT_ENABLED = True
REQUESTS_PER_SECOND = 10
BURST_LIMIT = 20

# File Organization
ORGANIZE_BY_DATE = True  # Create date-based subdirectories
DATE_FORMAT = "%Y-%m-%d"  # YYYY-MM-DD format
ORGANIZE_BY_CHANNEL = True  # Separate folders per channel

# Development/Debug Configuration
DEBUG_MODE = False
SAVE_MESSAGE_JSON = False  # Save raw message JSON for debugging
DRY_RUN = False  # Don't actually download files, just simulate