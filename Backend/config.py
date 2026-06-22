"""
Configuration module for Pakistan NAVAREA IX GIS Real-Time Agent
Handles all configuration parameters, database paths, and API settings
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# PROJECT PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGS_DIR = PROJECT_ROOT / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

DATABASE_PATH = DATA_DIR / "navarea_master.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
BACKUP_CSV_PATH = OUTPUT_DIR / "navarea_backup.csv"

# ============================================================================
# SCRAPER CONFIGURATION
# ============================================================================

PAKISTAN_NAVAREA_URL = "https://hydrography.paknavy.gov.pk/navarea-ix-warnings/"
COASTAL_WARNINGS_URL = "https://hydrography.paknavy.gov.pk/coastal-warnings-uploaded/"
SCRAPER_TIMEOUT = 30  # seconds
SCRAPER_RETRIES = 3
SCRAPER_BACKOFF = 2  # exponential backoff multiplier

# User agent to avoid blocking
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ============================================================================
# LIVE MONITORING CONFIGURATION
# ============================================================================

LIVE_MONITOR_INTERVAL = 60  # seconds
HISTORICAL_BACKFILL_ENABLED = True
APPEND_ONLY_MODE = True
NO_DUPLICATES_MODE = True

# ============================================================================
# COORDINATE EXTRACTION CONFIGURATION
# ============================================================================

# Patterns for extracting coordinates from NAVAREA text
COORDINATE_PATTERNS = {
    "dms": r"(\d+)°(\d+)'([\d.]+)\"([NS])\s+(\d+)°(\d+)'([\d.]+)\"([EW])",  # DMS format
    "dd": r"(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)",  # Decimal degrees
    "latlon": r"(\d{1,2}(?:\.\d+)?)\s*([NS])\s+(\d{1,3}(?:\.\d+)?)\s*([EW])",  # Lat/Lon with hemisphere
    "zone": r"ZONE\s+([A-Z0-9]+)",  # Zone notation
}

# ============================================================================
# GIS CONFIGURATION
# ============================================================================

DEFAULT_CRS = "EPSG:4326"  # WGS 84
GIS_BUFFER_DISTANCE = 0.1  # degrees
GEOMETRY_SIMPLIFICATION_TOLERANCE = 0.01

# ============================================================================
# WARNING CLASSIFICATION
# ============================================================================

WARNING_TYPES = {
    "weapon_firing": {"priority": "high", "color": "red"},
    "exercise": {"priority": "medium", "color": "orange"},
    "dredging": {"priority": "low", "color": "yellow"},
    "buoy_missing": {"priority": "medium", "color": "orange"},
    "hazard": {"priority": "high", "color": "red"},
    "search_rescue": {"priority": "high", "color": "red"},
    "navigation_hazard": {"priority": "medium", "color": "orange"},
    "construction": {"priority": "low", "color": "yellow"},
    "unknown": {"priority": "medium", "color": "orange"},
}

DEFAULT_WARNING_TYPE = "unknown"

# ============================================================================
# QUERY ENGINE CONFIGURATION
# ============================================================================

DEFAULT_QUERY_RANGE = 24  # hours
AVAILABLE_QUERY_RANGES = {
    "last_24h": 24,
    "last_4d": 96,
    "last_week": 168,
    "last_month": 720,
}

# ============================================================================
# API CONFIGURATION
# ============================================================================

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", 8000))
API_RELOAD = os.getenv("API_RELOAD", "False").lower() == "true"
API_WORKERS = int(os.getenv("API_WORKERS", 2))

# Allowed origins for CORS
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# ============================================================================
# WEBSOCKET CONFIGURATION
# ============================================================================

WEBSOCKET_ENABLED = True
WEBSOCKET_PING_INTERVAL = 30  # seconds
WEBSOCKET_PING_TIMEOUT = 10  # seconds

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
LOG_FILE = LOGS_DIR / f"navarea_{datetime.now().strftime('%Y%m%d')}.log"

# ============================================================================
# SCHEDULER CONFIGURATION
# ============================================================================

SCHEDULER_ENABLED = True
SCHEDULER_TIMEZONE = "UTC"

# ============================================================================
# VALIDATION CONFIGURATION
# ============================================================================

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0

# Pakistan NAVAREA IX specific bounds (approximate)
NAVAREA_MIN_LAT = 15.0
NAVAREA_MAX_LAT = 30.0
NAVAREA_MIN_LON = 55.0
NAVAREA_MAX_LON = 75.0

# NAVAREA IX red-zone fallback used when a warning has no explicit coordinates
NAVAREA_REDZONE_NAME = "NAVAREA IX Red Zone"
NAVAREA_REDZONE_CENTER_LAT = 20.0
NAVAREA_REDZONE_CENTER_LON = 65.0
NAVAREA_REDZONE_BOUNDS = {
    "min_lat": NAVAREA_MIN_LAT,
    "max_lat": NAVAREA_MAX_LAT,
    "min_lon": NAVAREA_MIN_LON,
    "max_lon": NAVAREA_MAX_LON,
}

# ============================================================================
# FEATURE FLAGS
# ============================================================================

ENABLE_HISTORICAL_BACKFILL = True
ENABLE_LIVE_MONITORING = True
ENABLE_COORDINATE_EXTRACTION = True
ENABLE_GIS_PROCESSING = True
ENABLE_DATABASE_STORAGE = True
ENABLE_API = True
ENABLE_WEBSOCKET = True
ENABLE_SCHEDULER = True

# ============================================================================
# PERFORMANCE CONFIGURATION
# ============================================================================

BATCH_INSERT_SIZE = 100
DATABASE_POOL_SIZE = 5
DATABASE_POOL_RECYCLE = 3600  # 1 hour
MAX_WORKERS_THREAD_POOL = 4

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_database_path() -> Path:
    """Get the database path"""
    return DATABASE_PATH


def get_output_dir() -> Path:
    """Get the output directory"""
    return OUTPUT_DIR


def get_logs_dir() -> Path:
    """Get the logs directory"""
    return LOGS_DIR


def validate_coordinate(lat: float, lon: float, strict: bool = False) -> bool:
    """
    Validate if coordinates are within valid ranges
    
    Args:
        lat: Latitude
        lon: Longitude
        strict: If True, use NAVAREA bounds; if False, use global bounds
    
    Returns:
        True if valid, False otherwise
    """
    if strict:
        return (
            NAVAREA_MIN_LAT <= lat <= NAVAREA_MAX_LAT
            and NAVAREA_MIN_LON <= lon <= NAVAREA_MAX_LON
        )
    else:
        return (
            MIN_LATITUDE <= lat <= MAX_LATITUDE
            and MIN_LONGITUDE <= lon <= MAX_LONGITUDE
        )
