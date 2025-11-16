# Obscura Labs Telegram Infostealer Data Scraper

A comprehensive data pipeline for scraping, processing, and storing infostealer data from Telegram channels. This system automates the collection, extraction, parsing, and database ingestion of credential data, cookies, and other sensitive information from infostealer logs.

# ⚠️ IMPORTANT DISCLAIMER

**This software is intended for threat intelligence and security research purposes only.**

## Prohibited Uses

**DO NOT use this software or any data processed by it to:**

- Access accounts, applications, websites, or systems without authorization
- Perform any unauthorized access or authentication attempts
- Engage in any illegal activities or violations of terms of service

## Legal and Ethical Use

- This tool is designed for security researchers, threat intelligence analysts, and cybersecurity professionals
- Use only for legitimate security research, threat analysis, and defensive security purposes
- Ensure you have proper authorization and comply with all applicable laws and regulations
- Respect privacy rights and data protection regulations
- Report discovered vulnerabilities responsibly through proper channels

## User Agreement

**By using this software, you agree to:**

- Use it solely for authorized security research and threat intelligence purposes
- Not use any extracted credentials or data for unauthorized access
- Comply with all applicable local, state, and federal laws
- Accept full responsibility for your use of this software

---

**The authors and contributors of this project are not responsible for any misuse of this software or any consequences resulting from unauthorized use of the data it processes.**

## Overview

This project consists of four interconnected components that work together to create a complete data processing pipeline:

1. **Downloader** - Monitors Telegram channels and downloads infostealer log files
2. **Decompressor** - Extracts compressed archives (ZIP, RAR) containing victim data
3. **Parser** - Extracts and structures sensitive data from raw files into JSON profiles
4. **DB Uploader** - Ingests parsed data into ClickHouse for fast querying at scale

## Architecture

```
Telegram Channels
       ↓
  [Downloader] → Downloads files to /storage/obscura/raw
       ↓
  [Decompressor] → Extracts archives to /storage/obscura/processed
       ↓
  [Parser] → Extracts credentials/cookies/data → /storage/obscura/parsed
       ↓
  [DB Uploader] → Ingests into ClickHouse vault.creds & vault.cookies
```

## Components

### 1. Downloader (`downloader/`)

Monitors Telegram channels for new infostealer log files and downloads them automatically.

**Features:**
- Multi-channel monitoring (public and private channels)
- Automatic file organization by channel and date
- Duplicate file detection using hash-based deduplication
- Parallel downloads with configurable concurrency
- Real-time monitoring with configurable polling intervals
- Progress tracking with rich console UI
- Comprehensive logging and error handling
- File type filtering (ZIP, RAR, TXT, SQL, etc.)

**Key Configuration:**
- Telegram API credentials (API_ID, API_HASH)
- Target channels (configured in `config.py`)
- Download path: `/storage/obscura/raw`
- File size limits and timeout settings
- Rate limiting and connection management

### 2. Decompressor (`decompressor/`)

Extracts compressed archives (ZIP, RAR) downloaded by the downloader.

**Features:**
- Supports ZIP and RAR file formats
- Automatic extraction to organized directory structure
- Resource monitoring to prevent system overload
- Process timeout management (5-minute default)
- Concurrent extraction with configurable limits
- Failed extraction handling with quarantine
- Progress tracking with rich console UI
- Detailed logging

**Key Configuration:**
- Source directory: `../downloader/downloads` (or `/storage/obscura/raw`)
- Output directory: `data/` (or `/storage/obscura/processed`)
- Maximum concurrent extractions: 2
- Process timeout: 300 seconds
- Memory/CPU thresholds for throttling

### 3. Parser (`parser/`)

Extracts sensitive information from raw victim data files and creates structured JSON profiles.

**Features:**
- Continuous monitoring of processed data directory
- Extracts multiple data types:
  - **Credentials**: URL, username, password combinations
  - **Cookies**: Browser cookies with classification (authentication, tracking, preferences)
  - **Addresses**: Street, city, state, ZIP code
  - **Credit Cards**: Number, expiration, CVV
  - **System Info**: OS version, hardware specs, IP addresses, hostnames
- Per-victim aggregation into Profile Objects
- Risk assessment and classification:
  - Account type classification (personal, corporate, educational, government)
  - Risk scoring (0-100)
  - Risk category (low, medium, high, critical)
  - Privileged account detection
- Rate limiting and resource management
- File existence caching for performance
- Detailed logging with timestamps

**Key Configuration:**
- Data directory: `/storage/obscura/processed/`
- Output directory: `/storage/obscura/parsed/`
- Rate limiting: 30 files/minute (configurable)
- Max concurrent processing: 3 files
- CPU/Memory thresholds for throttling

**Output Format:**
Each victim folder generates a Profile Object JSON file containing:
- Victim metadata (ID, source, timestamps)
- Credentials array with risk assessment
- Cookies array with classification
- Addresses array
- Credit cards array
- System information

### 4. DB Uploader (`db-uploader/`)

Watches for parsed JSON files and ingests them into ClickHouse database.

**Features:**
- File system monitoring for new Profile Object JSON files
- Batch insertion for optimal performance (20,000 rows default)
- Data normalization and deduplication
- Account type classification
- Risk scoring and categorization
- Separate tables for credentials and cookies
- Automatic schema management
- Idempotent processing with file movement

**Key Configuration:**
- Watch directory: `../parser/parsed-data` (or `/storage/obscura/parsed`)
- ClickHouse connection settings (host, port, credentials)
- Database: `vault`
- Tables: `creds`, `cookies`
- Batch size: 20,000 rows

**Database Schema:**
- **vault.creds**: Credentials with domain, email, username, password, system info, risk assessment
- **vault.cookies**: Browser cookies with domain, name, value, type, risk level

## Installation

### Prerequisites

- Python 3.7+
- ClickHouse Server (for DB uploader)
- unrar and 7zip (for decompressor)
- Telegram API credentials (API_ID, API_HASH)

### System Requirements

- **Minimum**: 32-64 GB RAM recommended for ClickHouse
- **Storage**: Fast NVMe storage recommended for large datasets
- **Network**: Stable connection for Telegram API

### Setup Steps

1. **Clone the repository:**
```bash
cd /Volumes/priv-usb/obscuralabs/scripts
```

2. **Set up Python virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install system dependencies (for decompressor):**
```bash
sudo apt install unrar 7zip
```

4. **Install ClickHouse (for DB uploader):**
```bash
# See db-uploader/README.md for detailed instructions
sudo apt-get update
sudo apt-get install -y clickhouse-server clickhouse-client
sudo systemctl enable --now clickhouse-server
```

5. **Install Python dependencies for each component:**
```bash
# Downloader
cd downloader
pip install -r requirements.txt

# Decompressor
cd ../decompressor
pip install -r requirements.txt

# Parser
cd ../parser
pip install -r requirements.txt

# DB Uploader
cd ../db-uploader
pip install -r requirements.txt
```

6. **Configure environment variables:**

Create `.env` files in each component directory:

**downloader/.env:**
```
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
```

**db-uploader/.env:**
```
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your_password
CLICKHOUSE_DATABASE=vault
WATCH_DIR=/storage/obscura/parsed
BATCH_SIZE=20000
```

7. **Initialize ClickHouse database:**
```bash
cd db-uploader
clickhouse-client < clickhouse_schema.sql
```

## Usage

### Running the Pipeline

The components can be run independently or together. For a complete pipeline, run all four components:

1. **Start the Downloader:**
```bash
cd downloader
python downloader.py
```

2. **Start the Decompressor:**
```bash
cd decompressor
python decompressor.py
```

3. **Start the Parser:**
```bash
cd parser
python parser.py
```

4. **Start the DB Uploader:**
```bash
cd db-uploader
python db-uploader.py
```

### Running Components Independently

Each component can process existing data:

**Process a specific victim folder:**
```bash
cd parser
python parser.py /path/to/victim/folder
```

**Reprocess existing data:**
The parser automatically detects and processes unprocessed victim folders on startup.

### Configuration

Each component has its own configuration:

- **Downloader**: Edit `downloader/config.py` for channels, file types, download settings
- **Decompressor**: Configuration in `decompressor/decompressor.py` (source/output directories)
- **Parser**: Command-line arguments or defaults in `parser/parser.py`
- **DB Uploader**: Environment variables in `db-uploader/.env`

See individual component README files for detailed configuration options.

## Data Flow

1. **Download Phase**: Downloader monitors Telegram channels → downloads files to `/storage/obscura/raw`
2. **Extraction Phase**: Decompressor finds archives → extracts to `/storage/obscura/processed/{victim_id}/`
3. **Parsing Phase**: Parser scans victim folders → extracts data → creates Profile Objects in `/storage/obscura/parsed/`
4. **Ingestion Phase**: DB Uploader watches parsed directory → batches and inserts into ClickHouse

## Directory Structure

```
scripts/
├── downloader/
│   ├── downloads/          # Downloaded files organized by channel
│   ├── logs/               # Download logs
│   ├── downloader.py       # Main downloader script
│   ├── config.py           # Configuration
│   └── requirements.txt
├── decompressor/
│   ├── data/               # Extracted files (or /storage/obscura/processed)
│   ├── failed_extractions/ # Failed extractions
│   ├── decompressor.py     # Main decompressor script
│   └── requirements.txt
├── parser/
│   ├── logs/               # Parser logs
│   ├── parsed-data/         # Profile Object JSON files (or /storage/obscura/parsed)
│   ├── parser.py            # Main parser script
│   └── requirements.txt
├── db-uploader/
│   ├── db-uploader.py      # Main uploader script
│   ├── clickhouse_schema.sql # Database schema
│   └── requirements.txt
└── venv/                   # Python virtual environment
```

## Data Structures

### Profile Object (Parser Output)

```json
{
  "victim_id": "unique_victim_identifier",
  "source_name": "channel_name",
  "timestamp": "2024-01-01T00:00:00",
  "credentials": [
    {
      "url": "https://example.com",
      "domain": "example.com",
      "email": "user@example.com",
      "username": "username",
      "password": "password",
      "account_type": "personal",
      "risk_score": 50,
      "risk_category": "medium"
    }
  ],
  "cookies": [...],
  "addresses": [...],
  "credit_cards": [...],
  "system_info": {...}
}
```

### ClickHouse Tables

**vault.creds**: Stores credential data with indexes for fast lookups
**vault.cookies**: Stores cookie data with classification and risk assessment

See `db-uploader/clickhouse_schema.sql` for complete schema definitions.

## Querying Data

### Example ClickHouse Queries

**Count credentials by domain:**
```sql
SELECT domain, count() FROM vault.creds 
WHERE domain = 'example.com' 
GROUP BY domain;
```

**Find credentials by email:**
```sql
SELECT * FROM vault.creds 
WHERE email = 'user@example.com' 
LIMIT 100;
```

**High-risk educational accounts:**
```sql
SELECT domain, email, username, risk_score 
FROM vault.creds 
WHERE account_type = 'educational' AND risk_score > 50 
ORDER BY risk_score DESC 
LIMIT 100;
```

**Recent data ingestion:**
```sql
SELECT 
    toDate(ts) as date,
    count() as records,
    uniqExact(victim_id) as victims,
    uniqExact(domain) as domains
FROM vault.creds 
WHERE ts >= today() - 7
GROUP BY date 
ORDER BY date DESC;
```

See `db-uploader/README.md` for more query examples.

## Performance Considerations

- **Parser**: Rate limiting prevents system overload (30 files/min default)
- **DB Uploader**: Batch insertion (20k rows) for optimal ClickHouse performance
- **Decompressor**: Concurrent extraction limits (2 processes) with resource monitoring
- **Downloader**: Parallel downloads (3 concurrent) with rate limiting

## Logging

Each component maintains detailed logs:

- **Downloader**: `downloader/logs/telegram_scraper_*.log`
- **Decompressor**: `decompressor/decompressor.log`
- **Parser**: `parser/logs/parser_YYYYMMDD_HHMMSS.log`
- **DB Uploader**: `db-uploader/clickhouse-uploader.log`

## Security Notes

- Telegram API credentials stored in environment variables
- File size limits prevent abuse
- Proper error handling and connection management
- Database credentials in environment variables
- Process isolation and resource limits

## Troubleshooting

### Common Issues

1. **Downloader not connecting**: Check API_ID and API_HASH in `.env`
2. **Decompressor failing**: Ensure unrar and 7zip are installed
3. **Parser not processing**: Check data directory path and permissions
4. **DB Uploader errors**: Verify ClickHouse is running and credentials are correct

### Debug Mode

Enable debug logging in component configurations:
- Downloader: Set `LOG_LEVEL = "DEBUG"` in `config.py`
- Parser: Use `--disable-rate-limiting` flag for debugging
- Check individual component logs for detailed error messages

## License

MIT License

## Support

For component-specific documentation, see:
- `downloader/README.md`
- `decompressor/README.md`
- `parser/README.md`
- `db-uploader/README.md`

