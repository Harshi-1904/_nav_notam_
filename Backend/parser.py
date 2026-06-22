"""
Parser module for NAVAREA warnings
Extracts coordinates, warning types, and metadata from raw text
"""

import re
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from loguru import logger
from config import (
    WARNING_TYPES,
    DEFAULT_WARNING_TYPE,
    COORDINATE_PATTERNS,
    NAVAREA_REDZONE_BOUNDS,
    NAVAREA_REDZONE_CENTER_LAT,
    NAVAREA_REDZONE_CENTER_LON,
    NAVAREA_REDZONE_NAME,
    validate_coordinate,
)


class CoordinateExtractor:
    """
    Extracts coordinates from NAVAREA warning text
    Supports multiple coordinate formats (DMS, DD, etc.)
    """
    
    def __init__(self):
        self.patterns = COORDINATE_PATTERNS
        logger.info("CoordinateExtractor initialized")
    
    def extract_coordinates(self, text: str) -> List[Tuple[float, float, float, str]]:
        """
        Extract all coordinates from text
        
        Args:
            text: Warning message text
        
        Returns:
            List of (latitude, longitude, confidence, method) tuples
        """
        coordinates = self._extract_coordinate_candidates(text)
        
        # Try each pattern
        for method, pattern in self.patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                coord = self._parse_coordinate_by_method(method, match)
                if coord:
                    lat, lon, confidence = coord
                    # Validate coordinate
                    if validate_coordinate(lat, lon, strict=False):
                        coordinates.append((lat, lon, confidence, method))
                        logger.debug(f"Extracted coordinate: {lat}, {lon} ({method})")
        
        # Remove duplicates (same location)
        unique_coords = []
        for coord in coordinates:
            if not any(self._coords_close(coord[:2], uc[:2]) for uc in unique_coords):
                unique_coords.append(coord)
        
        return unique_coords

    def _extract_coordinate_candidates(self, text: str) -> List[Tuple[float, float, float, str]]:
        """Extract common maritime coordinate formats before the generic regex pass."""
        candidates: List[Tuple[float, float, float, str]] = []

        dms_pattern = re.compile(
            r"(?P<lat_deg>\d{1,2})\s*[°º˚]\s*(?P<lat_min>\d{1,2})\s*['’′`´]\s*(?P<lat_sec>\d{1,2}(?:\.\d+)?)\s*['”\"]?\s*(?P<lat_dir>[NS])"
            r"[^0-9A-Z]{0,10}"
            r"(?P<lon_deg>\d{1,3})\s*[°º˚]\s*(?P<lon_min>\d{1,2})\s*['’′`´]\s*(?P<lon_sec>\d{1,2}(?:\.\d+)?)\s*['”\"]?\s*(?P<lon_dir>[EW])",
            re.IGNORECASE,
        )
        dm_pattern = re.compile(
            r"(?P<lat_deg>\d{1,2})\s*[°º˚]\s*(?P<lat_min>\d{1,2}(?:\.\d+)?)\s*['’′`´]?\s*(?P<lat_dir>[NS])"
            r"[^0-9A-Z]{0,10}"
            r"(?P<lon_deg>\d{1,3})\s*[°º˚]\s*(?P<lon_min>\d{1,2}(?:\.\d+)?)\s*['’′`´]?\s*(?P<lon_dir>[EW])",
            re.IGNORECASE,
        )
        dd_pattern = re.compile(
            r"(?P<lat>\d{1,2}(?:\.\d+)?)\s*(?P<lat_dir>[NS])"
            r"[^0-9A-Z]{0,10}"
            r"(?P<lon>\d{1,3}(?:\.\d+)?)\s*(?P<lon_dir>[EW])",
            re.IGNORECASE,
        )

        for match in dms_pattern.finditer(text):
            try:
                lat = int(match.group("lat_deg")) + int(match.group("lat_min")) / 60.0 + float(match.group("lat_sec")) / 3600.0
                lon = int(match.group("lon_deg")) + int(match.group("lon_min")) / 60.0 + float(match.group("lon_sec")) / 3600.0
                if match.group("lat_dir").upper() == "S":
                    lat = -lat
                if match.group("lon_dir").upper() == "W":
                    lon = -lon
                if validate_coordinate(lat, lon, strict=False):
                    candidates.append((lat, lon, 0.97, "dms"))
            except Exception:
                continue

        for match in dm_pattern.finditer(text):
            try:
                lat = int(match.group("lat_deg")) + float(match.group("lat_min")) / 60.0
                lon = int(match.group("lon_deg")) + float(match.group("lon_min")) / 60.0
                if match.group("lat_dir").upper() == "S":
                    lat = -lat
                if match.group("lon_dir").upper() == "W":
                    lon = -lon
                if validate_coordinate(lat, lon, strict=False):
                    candidates.append((lat, lon, 0.9, "dm"))
            except Exception:
                continue

        for match in dd_pattern.finditer(text):
            try:
                lat = float(match.group("lat"))
                lon = float(match.group("lon"))
                if match.group("lat_dir").upper() == "S":
                    lat = -lat
                if match.group("lon_dir").upper() == "W":
                    lon = -lon
                if validate_coordinate(lat, lon, strict=False):
                    candidates.append((lat, lon, 0.85, "latlon"))
            except Exception:
                continue

        return candidates
    
    def _parse_coordinate_by_method(self, method: str, match) -> Optional[Tuple[float, float, float]]:
        """
        Parse coordinate based on extraction method
        
        Args:
            method: Extraction method (dms, dd, latlon, etc.)
            match: Regex match object
        
        Returns:
            (latitude, longitude, confidence) or None
        """
        try:
            if method == "dms":
                # Degrees Minutes Seconds format
                # Pattern: (degrees)(minutes)(seconds)(N/S) (degrees)(minutes)(seconds)(E/W)
                groups = match.groups()
                lat_deg, lat_min, lat_sec, lat_dir = int(groups[0]), int(groups[1]), float(groups[2]), groups[3]
                lon_deg, lon_min, lon_sec, lon_dir = int(groups[4]), int(groups[5]), float(groups[6]), groups[7]
                
                lat = lat_deg + lat_min / 60.0 + lat_sec / 3600.0
                lon = lon_deg + lon_min / 60.0 + lon_sec / 3600.0
                
                if lat_dir.upper() == 'S':
                    lat = -lat
                if lon_dir.upper() == 'W':
                    lon = -lon
                
                return (lat, lon, 0.95)  # High confidence for explicit format
            
            elif method == "dd":
                # Decimal degrees format
                lat, lon = float(match.group(1)), float(match.group(2))
                return (lat, lon, 0.90)
            
            elif method == "latlon":
                # Lat/Lon format with hemisphere markers
                lat_str, lat_dir, lon_str, lon_dir = match.groups()
                lat = float(lat_str)
                lon = float(lon_str)
                if lat_dir.upper() == "S":
                    lat = -lat
                if lon_dir.upper() == "W":
                    lon = -lon
                return (lat, lon, 0.85)
            
            elif method == "zone":
                # Zone notation - extract approximate center
                zone = match.group(1)
                return self._zone_to_coordinates(zone)
        
        except (ValueError, IndexError) as e:
            logger.debug(f"Error parsing {method} coordinate: {str(e)}")
            return None
    
    def _zone_to_coordinates(self, zone: str) -> Optional[Tuple[float, float, float]]:
        """
        Convert zone notation to approximate coordinates
        
        Args:
            zone: Zone notation (e.g., "NAVAREA_IX")
        
        Returns:
            Approximate (latitude, longitude, confidence) or None
        """
        # NAVAREA IX approximation (Arabian Sea region)
        zone_centers = {
            "IX": (20.0, 65.0),
            "VIII": (15.0, 60.0),
            "ARABIAN": (20.0, 65.0),
            "INDIAN": (15.0, 75.0),
        }
        
        for key, (lat, lon) in zone_centers.items():
            if key.upper() in zone.upper():
                return (lat, lon, 0.5)  # Low confidence for zone approximation
        
        return None
    
    def _coords_close(self, coord1: Tuple[float, float], coord2: Tuple[float, float], 
                      tolerance: float = 0.01) -> bool:
        """Check if two coordinates are close (within tolerance)"""
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        return abs(lat1 - lat2) < tolerance and abs(lon1 - lon2) < tolerance


class WarningTypeClassifier:
    """
    Classifies warning type based on message content
    """
    
    def __init__(self):
        self.type_keywords = {
            "weapon_firing": ["weapon", "firing", "shooting", "fire", "live firing", "exercise firing"],
            "exercise": ["exercise", "drill", "training", "maneuver", "naval exercise"],
            "dredging": ["dredge", "dredging", "excavation", "sand mining", "spoil"],
            "buoy_missing": ["buoy", "missing", "adrift", "off station", "displaced"],
            "search_rescue": ["search", "rescue", "sar", "missing", "distress"],
            "hazard": ["hazard", "danger", "wreck", "sunken", "obstruction", "debris"],
            "navigation_hazard": ["navigation", "hazard", "shallow", "shoal", "reef"],
            "construction": ["construction", "pipeline", "cable", "offshore", "platform"],
        }
        logger.info("WarningTypeClassifier initialized")
    
    def classify(self, message: str) -> Tuple[str, float]:
        """
        Classify warning type from message
        
        Args:
            message: Warning message text
        
        Returns:
            (warning_type, confidence) tuple
        """
        message_lower = message.lower()
        scores = {}
        
        for warning_type, keywords in self.type_keywords.items():
            score = 0
            matches = 0
            
            for keyword in keywords:
                if keyword in message_lower:
                    matches += 1
                    # Score based on keyword position and frequency
                    count = message_lower.count(keyword)
                    score += count
            
            if matches > 0:
                # Normalize score by number of keywords
                scores[warning_type] = (score / len(keywords)) * (matches / len(keywords))
        
        if not scores:
            return (DEFAULT_WARNING_TYPE, 0.5)
        
        # Get top match
        best_type = max(scores.items(), key=lambda x: x[1])
        return (best_type[0], min(best_type[1], 1.0))


class WarningParser:
    """
    Main parser for NAVAREA warnings
    Combines coordinate extraction, type classification, and metadata parsing
    """
    
    def __init__(self):
        self.coord_extractor = CoordinateExtractor()
        self.type_classifier = WarningTypeClassifier()
        logger.info("WarningParser initialized")
    
    def parse_warning(self, warning: dict) -> dict:
        """
        Parse a raw warning into structured data
        
        Args:
            warning: Raw warning dictionary from scraper
        
        Returns:
            Parsed warning dictionary with extracted data
        """
        message = warning.get("message", "")
        
        # Extract coordinates
        coordinates = self.coord_extractor.extract_coordinates(message)
        
        # Classify warning type
        warning_type, type_confidence = self.type_classifier.classify(message)
        
        # Get priority from warning type
        priority = WARNING_TYPES.get(warning_type, {}).get("priority", "medium")
        
        # Parse additional metadata
        metadata = self._extract_metadata(message)
        fallback_location = None

        if not coordinates and self._should_use_redzone_fallback(warning):
            coordinates = [
                (
                    NAVAREA_REDZONE_CENTER_LAT,
                    NAVAREA_REDZONE_CENTER_LON,
                    0.35,
                    "navarea_redzone",
                )
            ]
            fallback_location = {
                "name": NAVAREA_REDZONE_NAME,
                "type": "navarea_redzone",
                "center": {
                    "latitude": NAVAREA_REDZONE_CENTER_LAT,
                    "longitude": NAVAREA_REDZONE_CENTER_LON,
                },
                "bounds": NAVAREA_REDZONE_BOUNDS,
                "synthetic": True,
            }
            metadata["fallback_location"] = fallback_location
            metadata["fallback_used"] = True
            metadata["fallback_reason"] = "no_explicit_coordinates"
        
        parsed = {
            **warning,
            "warning_type": warning_type,
            "priority": priority,
            "coordinates": [
                {
                    "latitude": lat,
                    "longitude": lon,
                    "extraction_method": method,
                    "confidence": conf,
                }
                for lat, lon, conf, method in coordinates
            ],
            "metadata": {
                "type_confidence": type_confidence,
                "coordinate_count": len(coordinates),
                "extraction_metadata": metadata,
                "source_type": warning.get("source_type"),
                "fallback_location": fallback_location,
            }
        }
        
        return parsed

    def _should_use_redzone_fallback(self, warning: dict) -> bool:
        """Decide whether a NAVAREA IX warning should use the red-zone fallback location."""
        source_type = (warning.get("source_type") or "").lower()
        area = (warning.get("area") or "").upper()
        message = (warning.get("message") or "").upper()

        if source_type == "navarea":
            return True

        if "NAVAREA IX" in message or "NAVAREA_IX" in area:
            return True

        return False
    
    def _extract_metadata(self, message: str) -> dict:
        """Extract additional metadata from message"""
        metadata = {
            "has_coordinates": bool(re.search(r'\d+[°]', message)),
            "has_date": bool(re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', message)),
            "message_length": len(message),
            "keyword_count": len(re.findall(r'\b\w+\b', message)),
        }
        
        # Extract specific patterns
        if re.search(r'(\d{1,2}:\d{2})', message):
            metadata["has_time"] = True
        
        if re.search(r'depth|meter|km', message, re.IGNORECASE):
            metadata["has_depth_info"] = True
        
        return metadata
    
    def parse_batch(self, warnings: List[dict]) -> List[dict]:
        """
        Parse multiple warnings in batch
        
        Args:
            warnings: List of raw warnings
        
        Returns:
            List of parsed warnings
        """
        parsed_warnings = []
        
        for i, warning in enumerate(warnings):
            try:
                parsed = self.parse_warning(warning)
                parsed_warnings.append(parsed)
            except Exception as e:
                logger.error(f"Error parsing warning {i}: {str(e)}")
                continue
        
        logger.info(f"✓ Parsed {len(parsed_warnings)}/{len(warnings)} warnings")
        return parsed_warnings


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def parse_navarea_warnings(warnings: List[dict]) -> List[dict]:
    """
    Parse list of raw warnings
    
    Args:
        warnings: List of raw warning dictionaries
    
    Returns:
        List of parsed warnings
    """
    parser = WarningParser()
    return parser.parse_batch(warnings)


def extract_warning_coordinates(message: str) -> List[Tuple[float, float]]:
    """
    Extract coordinates from warning message
    
    Args:
        message: Warning message text
    
    Returns:
        List of (latitude, longitude) tuples
    """
    extractor = CoordinateExtractor()
    coords = extractor.extract_coordinates(message)
    return [(lat, lon) for lat, lon, _, _ in coords]


def classify_warning_type(message: str) -> str:
    """
    Classify warning type from message
    
    Args:
        message: Warning message text
    
    Returns:
        Warning type string
    """
    classifier = WarningTypeClassifier()
    warning_type, _ = classifier.classify(message)
    return warning_type
