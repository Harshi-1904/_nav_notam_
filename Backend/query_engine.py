"""
Query engine for NAVAREA warnings
Handles advanced filtering, spatial queries, and result formatting
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from dateutil import parser as dateutil_parser
from sqlalchemy.orm import selectinload
import re

from database import get_database
from models import NavAreaWarning, NavAreaWarningSchema
from config import (
    DEFAULT_QUERY_RANGE,
    AVAILABLE_QUERY_RANGES,
    WARNING_TYPES,
)


class QueryEngine:
    """
    Advanced query engine for NAVAREA warnings
    Supports time range queries, filters, and spatial operations
    """
    
    def __init__(self):
        self.db = get_database()
        self.available_ranges = AVAILABLE_QUERY_RANGES
        logger.info("QueryEngine initialized")
    
    # ========================================================================
    # TIME RANGE QUERIES
    # ========================================================================
    
    def query_last_hours(self, hours: int = 24) -> List[NavAreaWarning]:
        """
        Query warnings from last N hours
        
        Args:
            hours: Number of hours
        
        Returns:
            List of warnings
        """
        logger.debug(f"Querying warnings from last {hours} hours")
        return self.db.get_warnings_by_time_range(hours_back=hours)
    
    def query_time_range(self, start: datetime, end: datetime) -> List[NavAreaWarning]:
        """
        Query warnings between two dates
        
        Args:
            start: Start datetime
            end: End datetime
        
        Returns:
            List of warnings
        """
        from sqlalchemy.orm import Session
        from sqlalchemy import and_
        
        session = self.db.get_session()
        
        try:
            warnings = session.query(NavAreaWarning).filter(
                and_(
                    NavAreaWarning.date >= start,
                    NavAreaWarning.date <= end,
                )
            ).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            ).order_by(NavAreaWarning.date.desc()).all()
            
            logger.info(f"✓ Found {len(warnings)} warnings between {start} and {end}")
            return warnings
        
        finally:
            session.close()
    
    def query_by_natural_language(self, query_str: str) -> List[NavAreaWarning]:
        """
        Parse natural language query and execute
        
        Examples:
            - "last 24 hours"
            - "last 4 days"
            - "since yesterday"
            - "from monday"
        
        Args:
            query_str: Natural language query

        Returns:
            List of warnings
        """
        query_lower = query_str.lower().strip()

        if self._looks_like_all_question(query_lower) or self._looks_like_count_question(query_lower):
            return self.advanced_search(search_text=None, hours_back=None)

        if self._looks_like_time_question(query_lower):
            hours = self._extract_hours_from_question(query_lower, default=DEFAULT_QUERY_RANGE)
            return self.advanced_search(search_text=None, hours_back=hours)

        # Parse specific patterns
        if "last" in query_lower:
            return self._parse_last_query(query_lower)
        
        elif "since" in query_lower:
            return self._parse_since_query(query_lower)
        
        elif "from" in query_lower:
            return self._parse_from_query(query_lower)
        
        elif "today" in query_lower:
            return self.query_last_hours(24)
        
        elif "yesterday" in query_lower:
            return self._query_yesterday()
        
        else:
            logger.info(f"Treating query as database text search: {query_str}")
            return self.search_warnings(query_str, hours_back=DEFAULT_QUERY_RANGE)
    
    def _parse_last_query(self, query: str) -> List[NavAreaWarning]:
        """Parse 'last N hours/days' queries"""
        import re
        
        # Extract number and unit
        match = re.search(r'(\d+)\s*(hour|day|week|month)s?', query)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            hours_map = {
                'hour': 1,
                'day': 24,
                'week': 168,
                'month': 720,
            }
            
            hours = value * hours_map.get(unit, 24)
            return self.query_last_hours(hours)
        
        return self.query_last_hours(DEFAULT_QUERY_RANGE)
    
    def _parse_since_query(self, query: str) -> List[NavAreaWarning]:
        """Parse 'since DATE' queries"""
        import re
        
        # Try to extract date
        match = re.search(r'since\s+(.+?)(?:\s+|$)', query)
        if match:
            date_str = match.group(1)
            try:
                since_date = dateutil_parser.parse(date_str)
                return self.query_time_range(since_date, datetime.utcnow())
            except:
                pass
        
        return self.query_last_hours(DEFAULT_QUERY_RANGE)
    
    def _parse_from_query(self, query: str) -> List[NavAreaWarning]:
        """Parse 'from DATE to DATE' queries"""
        # Similar to _parse_since_query
        return self._parse_since_query(query.replace('from', 'since'))
    
    def _query_yesterday(self) -> List[NavAreaWarning]:
        """Query warnings from yesterday"""
        now = datetime.utcnow()
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.query_time_range(start, end)
    
    # ========================================================================
    # FILTER QUERIES
    # ========================================================================
    
    def query_by_type(self, warning_type: str, hours_back: int = None) -> List[NavAreaWarning]:
        """
        Query by warning type
        
        Args:
            warning_type: Type of warning
            hours_back: Optional time range
        
        Returns:
            List of warnings
        """
        if hours_back is None:
            hours_back = DEFAULT_QUERY_RANGE
        
        logger.debug(f"Querying warnings of type: {warning_type}")
        return self.db.get_warnings_by_time_range(
            hours_back=hours_back,
            warning_type=warning_type
        )
    
    def query_by_priority(self, priority: str, hours_back: int = None) -> List[NavAreaWarning]:
        """
        Query by priority level
        
        Args:
            priority: Priority level (low, medium, high)
            hours_back: Optional time range
        
        Returns:
            List of warnings
        """
        if hours_back is None:
            hours_back = DEFAULT_QUERY_RANGE
        
        logger.debug(f"Querying warnings with priority: {priority}")
        return self.db.get_warnings_by_time_range(
            hours_back=hours_back,
            priority=priority
        )
    
    def query_by_area(self, area: str, hours_back: int = None) -> List[NavAreaWarning]:
        """
        Query by area
        
        Args:
            area: Area code or name
            hours_back: Optional time range
        
        Returns:
            List of warnings
        """
        if hours_back is None:
            hours_back = DEFAULT_QUERY_RANGE
        
        logger.debug(f"Querying warnings in area: {area}")
        return self.db.get_warnings_by_time_range(
            hours_back=hours_back,
            area=area
        )

    def search_warnings(
        self,
        search_text: str,
        hours_back: int = None,
        limit: int = 100,
    ) -> List[NavAreaWarning]:
        """
        Search warnings by keyword across message, area, type, and source.
        """
        if hours_back is None:
            hours_back = DEFAULT_QUERY_RANGE

        logger.debug(f"Searching warnings with text: {search_text}")
        return self.db.search_warnings(
            search_text=search_text,
            hours_back=hours_back,
            limit=limit,
        )

    def advanced_search(
        self,
        search_text: Optional[str] = None,
        hours_back: int = None,
        warning_type: Optional[str] = None,
        priority: Optional[str] = None,
        area: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NavAreaWarning]:
        """
        Advanced database-backed search with optional source filtering.
        """
        source_keyword = None
        if source == "coastal":
            source_keyword = "coastal-warnings-uploaded"
        elif source == "navarea":
            source_keyword = "navarea-ix-warnings"

        return self.db.advanced_search_warnings(
            search_text=search_text,
            hours_back=hours_back,
            warning_type=warning_type,
            priority=priority,
            area=area,
            source_keyword=source_keyword,
            limit=limit,
            offset=offset,
        )

    def query_by_source(self, source_keyword: str, hours_back: int = None, limit: int = 100) -> List[NavAreaWarning]:
        """
        Query warnings by source URL keyword.

        Args:
            source_keyword: Keyword to match in source URL
            hours_back: Optional time range
            limit: Maximum results

        Returns:
            List of warnings
        """
        logger.debug(f"Querying warnings by source keyword: {source_keyword}")
        return self.db.get_warnings_by_source(
            source_keyword=source_keyword,
            hours_back=hours_back,
            limit=limit,
        )

    def query_coastal_warnings(self, hours_back: int = None, limit: int = 100) -> List[NavAreaWarning]:
        """
        Query coastal warnings.
        """
        return self.query_by_source(
            source_keyword="coastal-warnings-uploaded",
            hours_back=hours_back,
            limit=limit,
        )

    def query_navarea_warnings(self, hours_back: int = None, limit: int = 100) -> List[NavAreaWarning]:
        """
        Query NAVAREA warnings.
        """
        return self.query_by_source(
            source_keyword="navarea-ix-warnings",
            hours_back=hours_back,
            limit=limit,
        )
    
    def query_combined(
        self,
        hours_back: int = None,
        warning_type: Optional[str] = None,
        priority: Optional[str] = None,
        area: Optional[str] = None,
    ) -> List[NavAreaWarning]:
        """
        Query with multiple filters
        
        Args:
            hours_back: Hours to look back
            warning_type: Warning type filter
            priority: Priority filter
            area: Area filter
        
        Returns:
            List of warnings
        """
        if hours_back is None:
            hours_back = DEFAULT_QUERY_RANGE
        
        logger.debug(f"Combined query: {hours_back}h, type={warning_type}, priority={priority}, area={area}")
        return self.db.get_warnings_by_time_range(
            hours_back=hours_back,
            warning_type=warning_type,
            priority=priority,
            area=area
        )
    
    # ========================================================================
    # SPATIAL QUERIES
    # ========================================================================
    
    def query_by_geometry_type(self, geometry_type: str) -> List[NavAreaWarning]:
        """
        Query warnings by geometry type
        
        Args:
            geometry_type: POINT or POLYGON
        
        Returns:
            List of warnings
        """
        logger.debug(f"Querying warnings with geometry type: {geometry_type}")
        return self.db.get_warnings_by_geometry_type(geometry_type)
    
    def query_by_coordinates(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float = 100,
    ) -> List[NavAreaWarning]:
        """
        Query warnings within a radius of coordinates
        
        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Search radius in kilometers
        
        Returns:
            List of warnings
        """
        from sqlalchemy.orm import Session
        from sqlalchemy import func
        from math import sin, cos, radians, sqrt, atan2
        
        logger.debug(f"Spatial query: {center_lat}, {center_lon}, radius {radius_km}km")
        
        # Using simple distance calculation (not perfect but good for most uses)
        session = self.db.get_session()
        
        try:
            # Approximate conversion: 1 degree ≈ 111 km
            radius_degrees = radius_km / 111.0
            
            from models import Coordinate
            
            # Find warnings with coordinates within radius
            warnings = session.query(NavAreaWarning).join(
                Coordinate
            ).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            ).filter(
                func.abs(Coordinate.latitude - center_lat) <= radius_degrees,
                func.abs(Coordinate.longitude - center_lon) <= radius_degrees,
            ).distinct().all()
            
            # Filter by actual distance
            filtered = []
            for warning in warnings:
                for coord in warning.coordinates:
                    dist = self._calculate_distance(
                        center_lat, center_lon,
                        coord.latitude, coord.longitude
                    )
                    if dist <= radius_km:
                        filtered.append(warning)
                        break
            
            logger.info(f"✓ Found {len(filtered)} warnings within {radius_km}km")
            return filtered
        
        finally:
            session.close()

    # ========================================================================
    # SMART Q&A
    # ========================================================================

    def answer_question(
        self,
        question: Optional[str] = None,
        hours_back: Optional[int] = None,
        warning_type: Optional[str] = None,
        priority: Optional[str] = None,
        area: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Interpret a plain-language question and return both an answer and the
        matching warnings.

        This is intentionally lightweight: it understands count/all/time phrases
        directly and falls back to keyword search for everything else.
        """
        normalized = " ".join((question or "").split()).strip()
        lowered = normalized.lower()

        intent = "search"
        parsed_hours = hours_back
        has_time_phrase = self._looks_like_time_question(lowered)

        if not lowered and not any([warning_type, priority, area, source]):
            intent = "all"
        elif self._looks_like_count_question(lowered):
            intent = "count"
        elif self._looks_like_all_question(lowered):
            intent = "all"
        elif has_time_phrase:
            parsed_hours = self._extract_hours_from_question(lowered, default=parsed_hours)
            intent = "time"

        # Explicit "all warnings" or "total warnings" requests should not be
        # restricted to the time slider unless the user also asked for a time
        # window in the same sentence.
        if lowered and intent in {"all", "count"} and not has_time_phrase:
            parsed_hours = None
        elif parsed_hours is None:
            parsed_hours = DEFAULT_QUERY_RANGE

        if intent == "all":
            warnings = self.advanced_search(
                search_text=None,
                hours_back=parsed_hours,
                warning_type=warning_type,
                priority=priority,
                area=area,
                source=source,
                limit=limit,
                offset=offset,
            ) or []
            answer = f"Showing {len(warnings)} warnings."
        elif intent == "count":
            warnings = self.advanced_search(
                search_text=None if self._looks_like_count_question(lowered) else normalized,
                hours_back=parsed_hours,
                warning_type=warning_type,
                priority=priority,
                area=area,
                source=source,
                limit=limit,
                offset=offset,
            ) or []
            answer = f"Found {len(warnings)} warnings matching your request."
        elif intent == "time":
            warnings = self.advanced_search(
                search_text=None,
                hours_back=parsed_hours,
                warning_type=warning_type,
                priority=priority,
                area=area,
                source=source,
                limit=limit,
                offset=offset,
            ) or []
            answer = f"Showing {len(warnings)} warnings from the last {parsed_hours} hours."
        else:
            warnings = self.advanced_search(
                search_text=normalized or None,
                hours_back=parsed_hours,
                warning_type=warning_type,
                priority=priority,
                area=area,
                source=source,
                limit=limit,
                offset=offset,
            ) or []
            answer = f"Found {len(warnings)} warnings for '{normalized or 'current filters'}'."

        results = self.format_results(warnings)
        geojson = self.format_as_geojson(warnings)
        summary = self._summarize_warning_objects(warnings)

        return {
            "answer": answer,
            "intent": intent,
            "query": normalized,
            "filters": {
                "hours_back": parsed_hours,
                "warning_type": warning_type,
                "priority": priority,
                "area": area,
                "source": source,
                "offset": offset,
                "limit": limit,
            },
            "count": len(results),
            "summary": summary,
            "data": results,
            "geojson": geojson,
        }

    def _looks_like_count_question(self, lowered: str) -> bool:
        phrases = [
            "total warnings",
            "how many warnings",
            "count warnings",
            "number of warnings",
            "warnings count",
            "how many",
            "total count",
        ]
        return any(phrase in lowered for phrase in phrases)

    def _looks_like_all_question(self, lowered: str) -> bool:
        phrases = [
            "all warnings",
            "show all warnings",
            "list all warnings",
            "everything",
        ]
        return any(phrase in lowered for phrase in phrases)

    def _looks_like_time_question(self, lowered: str) -> bool:
        phrases = [
            "last ",
            "hours",
            "hour",
            "days",
            "day",
            "week",
            "weeks",
            "month",
            "months",
            "yesterday",
            "today",
            "since ",
            "from ",
        ]
        return any(phrase in lowered for phrase in phrases)

    def _extract_hours_from_question(self, lowered: str, default: int) -> int:
        """
        Extract a time window from a question string.
        Accepts phrases like 'last 4 days', '48 hours', '2 weeks', 'yesterday'.
        """
        if "yesterday" in lowered:
            return 24
        if "today" in lowered:
            return 24

        match = re.search(r"(?:last\s+)?(\d+)\s*(hour|day|week|month)s?", lowered)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            hours_map = {
                "hour": 1,
                "day": 24,
                "week": 168,
                "month": 720,
            }
            return value * hours_map.get(unit, 24)

        match = re.search(r"\b(\d+)\s*hours?\b", lowered)
        if match:
            return int(match.group(1))

        match = re.search(r"\b(\d+)\s*days?\b", lowered)
        if match:
            return int(match.group(1)) * 24

        return default

    def _summarize_warning_objects(self, warnings: List[NavAreaWarning]) -> Dict[str, Any]:
        warnings = warnings or []
        summary = {
            "total": len(warnings),
            "with_coordinates": 0,
            "with_geometry": 0,
            "by_type": {},
            "by_priority": {},
        }

        for warning in warnings:
            summary["by_type"][warning.warning_type] = summary["by_type"].get(warning.warning_type, 0) + 1
            summary["by_priority"][warning.priority] = summary["by_priority"].get(warning.priority, 0) + 1
            if warning.coordinates:
                summary["with_coordinates"] += 1
            if warning.geometry:
                summary["with_geometry"] += 1

        return summary
    
    def _calculate_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula
        
        Args:
            lat1, lon1: First point
            lat2, lon2: Second point
        
        Returns:
            Distance in kilometers
        """
        from math import sin, cos, radians, sqrt, atan2
        
        R = 6371  # Earth radius in km
        
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        
        a = (sin(dlat / 2) ** 2 +
             cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2)
        
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    # ========================================================================
    # RESULT FORMATTING
    # ========================================================================
    
    def format_results(self, warnings: List[NavAreaWarning]) -> List[Dict[str, Any]]:
        """
        Format warnings for API response
        
        Args:
            warnings: List of warning objects
        
        Returns:
            List of formatted dictionaries
        """
        warnings = warnings or []
        results = []
        
        for warning in warnings:
            metadata = None
            if warning.warning_metadata and warning.warning_metadata.parsed_fields:
                metadata = warning.warning_metadata.parsed_fields

            result = {
                "id": warning.id,
                "warning_id": warning.warning_id,
                "date": warning.date.isoformat() if warning.date else None,
                "message": warning.message,
                "area": warning.area,
                "type": warning.warning_type,
                "priority": warning.priority,
                "source_url": warning.source_url,
                "source_type": (
                    "coastal"
                    if warning.source_url and "coastal-warnings-uploaded" in warning.source_url
                    else "navarea"
                ),
                "color": WARNING_TYPES.get(warning.warning_type, {}).get("color", "gray"),
                "coordinates_extracted": bool(warning.coordinates),
                "geometry_created": bool(warning.geometry),
                "coordinate_count": len(warning.coordinates or []),
                "coordinates": [
                    {
                        "lat": c.latitude,
                        "lon": c.longitude,
                        "method": c.extraction_method,
                        "confidence": c.confidence,
                    }
                    for c in warning.coordinates
                ],
                "metadata": metadata,
                "location_hint": metadata.get("fallback_location") if metadata else None,
                "geometry": {
                    "type": warning.geometry.geometry_type if warning.geometry else None,
                    "area_km2": warning.geometry.area_sq_km if warning.geometry else None,
                } if warning.geometry else None,
            }
            
            results.append(result)
        
        return results
    
    def format_as_geojson(self, warnings: List[NavAreaWarning]) -> Dict:
        """
        Format warnings as GeoJSON
        
        Args:
            warnings: List of warnings
        
        Returns:
            GeoJSON FeatureCollection
        """
        from gis_processor import GISProcessor

        processor = GISProcessor()
        warnings = warnings or []

        features = []
        for warning in warnings:
            geometry_payload = None
            if warning.geometry and warning.geometry.geojson:
                geometry_payload = {
                    "geometry_type": warning.geometry.geometry_type,
                    "geojson": warning.geometry.geojson,
                    "area_sq_km": warning.geometry.area_sq_km,
                }
            else:
                coordinates = [
                    (coord.latitude, coord.longitude)
                    for coord in (warning.coordinates or [])
                    if coord.latitude is not None and coord.longitude is not None
                ]
                if coordinates:
                    geometry_payload = processor.geometry_processor.create_geometry(coordinates)
                else:
                    metadata = warning.warning_metadata.parsed_fields if warning.warning_metadata and warning.warning_metadata.parsed_fields else {}
                    fallback_location = metadata.get("fallback_location") if isinstance(metadata, dict) else None
                    bounds = fallback_location.get("bounds") if isinstance(fallback_location, dict) else None
                    if bounds:
                        geometry_payload = processor._create_bounds_geometry(bounds)

            if geometry_payload and geometry_payload.get("geometry_type") == "POINT" and geometry_payload.get("buffer_geojson"):
                # Keep the original point for the feature geometry, but expose the buffer for map overlays.
                geometry_payload = {
                    **geometry_payload,
                    "display_geojson": geometry_payload.get("buffer_geojson"),
                }

            feature = processor.create_geojson_feature({
                "warning_id": warning.warning_id,
                "date": warning.date,
                "message": warning.message,
                "warning_type": warning.warning_type,
                "priority": warning.priority,
                "area": warning.area,
                "geometry": geometry_payload,
            })
            
            if feature:
                if geometry_payload and geometry_payload.get("display_geojson"):
                    feature.setdefault("properties", {})
                    feature["properties"]["display_geojson"] = geometry_payload["display_geojson"]
                features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features,
        }
    
    # ========================================================================
    # STATISTICS & AGGREGATION
    # ========================================================================
    
    def get_statistics(self, hours_back: int = None) -> Dict[str, Any]:
        """
        Get statistics for warnings
        
        Args:
            hours_back: Optional time range
        
        Returns:
            Statistics dictionary
        """
        if hours_back is None:
            hours_back = DEFAULT_QUERY_RANGE
        
        warnings = self.query_last_hours(hours_back)
        
        type_counts = {}
        priority_counts = {}
        area_counts = {}
        
        for warning in warnings:
            # Type counts
            type_counts[warning.warning_type] = type_counts.get(warning.warning_type, 0) + 1
            
            # Priority counts
            priority_counts[warning.priority] = priority_counts.get(warning.priority, 0) + 1
            
            # Area counts
            if warning.area:
                area_counts[warning.area] = area_counts.get(warning.area, 0) + 1
        
        return {
            "total": len(warnings),
            "time_range_hours": hours_back,
            "by_type": type_counts,
            "by_priority": priority_counts,
            "by_area": area_counts,
        }


# ============================================================================
# SINGLETON QUERY ENGINE
# ============================================================================

_query_engine = None


def get_query_engine() -> QueryEngine:
    """Get or create query engine instance"""
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine


def query_warnings(
    hours_back: int = DEFAULT_QUERY_RANGE,
    warning_type: Optional[str] = None,
    priority: Optional[str] = None,
    area: Optional[str] = None,
) -> List[NavAreaWarning]:
    """
    Main query function
    
    Args:
        hours_back: Hours to look back
        warning_type: Optional type filter
        priority: Optional priority filter
        area: Optional area filter
    
    Returns:
        List of warnings
    """
    engine = get_query_engine()
    return engine.query_combined(hours_back, warning_type, priority, area)
