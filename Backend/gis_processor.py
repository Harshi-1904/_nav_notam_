"""
GIS Processor module for NAVAREA warnings
Converts coordinates to GIS geometries (POINT, POLYGON)
"""

from typing import List, Dict, Optional, Tuple
from loguru import logger
from math import cos, radians

from config import (
    DEFAULT_CRS,
    GIS_BUFFER_DISTANCE,
    GEOMETRY_SIMPLIFICATION_TOLERANCE,
    NAVAREA_REDZONE_BOUNDS,
    NAVAREA_REDZONE_CENTER_LAT,
    NAVAREA_REDZONE_CENTER_LON,
    NAVAREA_REDZONE_NAME,
)


def _lon_degree_km(lat: float) -> float:
    """Approximate kilometers per degree of longitude at a latitude."""
    return 111.32 * max(cos(radians(lat)), 0.01)


def _lat_degree_km() -> float:
    """Approximate kilometers per degree of latitude."""
    return 110.57


def _point_geojson(lat: float, lon: float) -> Dict:
    return {"type": "Point", "coordinates": [lon, lat]}


def _polygon_geojson(ring: List[Tuple[float, float]]) -> Dict:
    coords = [[lon, lat] for lat, lon in ring]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _bbox_from_coords(coordinates: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    lats = [lat for lat, _ in coordinates]
    lons = [lon for _, lon in coordinates]
    return min(lats), min(lons), max(lats), max(lons)


def _rectangle_ring(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
) -> List[Tuple[float, float]]:
    return [
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, max_lon),
        (max_lat, min_lon),
    ]


class GeometryProcessor:
    """
    Processes coordinates into GIS geometries
    Handles POINT and POLYGON creation
    """

    def __init__(self):
        self.crs = DEFAULT_CRS
        logger.info(f"GeometryProcessor initialized with CRS: {self.crs}")

    def create_geometry(self, coordinates: List[Tuple[float, float]]) -> Optional[Dict]:
        """
        Create geometry from coordinates

        Args:
            coordinates: List of (latitude, longitude) tuples

        Returns:
            Dictionary with geometry_type, geojson, and other properties
        """
        if not coordinates:
            logger.warning("No coordinates provided for geometry creation")
            return None

        try:
            if len(coordinates) == 1:
                return self._create_point_geometry(coordinates[0])
            if len(coordinates) == 2:
                return self._create_buffered_points_geometry(coordinates)
            return self._create_polygon_geometry(coordinates)
        except Exception as e:
            logger.error(f"Error creating geometry: {str(e)}")
            return None

    def _create_point_geometry(self, coord: Tuple[float, float]) -> Dict:
        """
        Create a POINT geometry with optional buffer

        Args:
            coord: (latitude, longitude) tuple

        Returns:
            Geometry dictionary
        """
        lat, lon = coord
        delta_lat = GIS_BUFFER_DISTANCE
        delta_lon = GIS_BUFFER_DISTANCE / max(cos(radians(lat)), 0.01)

        geometry = {
            "geometry_type": "POINT",
            "geojson": _point_geojson(lat, lon),
            "wkt": f"POINT ({lon} {lat})",
            "buffer_geojson": _polygon_geojson(
                _rectangle_ring(lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)
            ),
            "area_sq_km": None,
        }

        logger.debug(f"Created POINT geometry at ({lat}, {lon})")
        return geometry

    def _create_buffered_points_geometry(self, coordinates: List[Tuple[float, float]]) -> Dict:
        """
        Create geometry from two points with buffering

        Args:
            coordinates: List of two (latitude, longitude) tuples

        Returns:
            Geometry dictionary
        """
        min_lat, min_lon, max_lat, max_lon = _bbox_from_coords(coordinates)
        center_lat = (min_lat + max_lat) / 2.0
        delta_lat = GIS_BUFFER_DISTANCE
        delta_lon = GIS_BUFFER_DISTANCE / max(cos(radians(center_lat)), 0.01)

        min_lat -= delta_lat
        max_lat += delta_lat
        min_lon -= delta_lon
        max_lon += delta_lon

        ring = _rectangle_ring(min_lat, min_lon, max_lat, max_lon)
        geometry = {
            "geometry_type": "POLYGON",
            "geojson": _polygon_geojson(ring),
            "wkt": self._ring_to_wkt(ring),
            "area_sq_km": self._calculate_area_km2_from_ring(ring),
        }

        logger.debug(f"Created buffered POLYGON from {len(coordinates)} points")
        return geometry

    def _create_polygon_geometry(self, coordinates: List[Tuple[float, float]]) -> Dict:
        """
        Create a POLYGON geometry from multiple coordinates

        Args:
            coordinates: List of (latitude, longitude) tuples

        Returns:
            Geometry dictionary
        """
        try:
            ring = list(coordinates)
            if ring[0] != ring[-1]:
                ring.append(ring[0])

            geometry = {
                "geometry_type": "POLYGON",
                "geojson": _polygon_geojson(ring),
                "wkt": self._ring_to_wkt(ring),
                "area_sq_km": self._calculate_area_km2_from_ring(ring),
            }

            logger.debug(f"Created POLYGON from {len(coordinates)} coordinates")
            return geometry
        except Exception as e:
            logger.error(f"Error creating polygon: {str(e)}")
            min_lat, min_lon, max_lat, max_lon = _bbox_from_coords(coordinates)
            ring = _rectangle_ring(min_lat, min_lon, max_lat, max_lon)
            geometry = {
                "geometry_type": "POLYGON",
                "geojson": _polygon_geojson(ring),
                "wkt": self._ring_to_wkt(ring),
                "area_sq_km": self._calculate_area_km2_from_ring(ring),
            }
            logger.debug("Created POLYGON using bounding box fallback")
            return geometry

    def _ring_to_wkt(self, ring: List[Tuple[float, float]]) -> str:
        coords = ", ".join(f"{lon} {lat}" for lat, lon in ring)
        if ring and ring[0] != ring[-1]:
            coords = coords + f", {ring[0][1]} {ring[0][0]}"
        return f"POLYGON (({coords}))"

    def _calculate_area_km2_from_ring(self, ring: List[Tuple[float, float]]) -> Optional[float]:
        """
        Approximate polygon area in square kilometers.
        Uses a simple equirectangular approximation that is adequate for small regions.
        """
        try:
            if len(ring) < 4:
                return None

            points = ring[:-1] if ring[0] == ring[-1] else ring[:]
            avg_lat = sum(lat for lat, _ in points) / len(points)
            lat_scale = _lat_degree_km()
            lon_scale = _lon_degree_km(avg_lat)

            area_deg2 = 0.0
            for i in range(len(points)):
                lat1, lon1 = points[i]
                lat2, lon2 = points[(i + 1) % len(points)]
                x1, y1 = lon1 * lon_scale, lat1 * lat_scale
                x2, y2 = lon2 * lon_scale, lat2 * lat_scale
                area_deg2 += x1 * y2 - x2 * y1

            area_km2 = abs(area_deg2) / 2.0
            return round(area_km2, 2)
        except Exception as e:
            logger.debug(f"Error calculating area: {str(e)}")
            return None

    def buffer_geometry(self, geojson: dict, buffer_distance: float = None) -> Optional[dict]:
        """
        Apply buffer to a geometry.

        Args:
            geojson: GeoJSON geometry
            buffer_distance: Buffer distance in degrees (default from config)

        Returns:
            Buffered geometry GeoJSON
        """
        try:
            if buffer_distance is None:
                buffer_distance = GIS_BUFFER_DISTANCE

            geometry_type = geojson.get("type")
            if geometry_type == "Point":
                lon, lat = geojson["coordinates"]
                delta_lat = buffer_distance
                delta_lon = buffer_distance / max(cos(radians(lat)), 0.01)
                ring = _rectangle_ring(lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)
                return _polygon_geojson(ring)

            if geometry_type == "Polygon":
                ring = geojson["coordinates"][0]
                lat_lon_ring = [(lat, lon) for lon, lat in ring]
                min_lat, min_lon, max_lat, max_lon = _bbox_from_coords(lat_lon_ring)
                center_lat = (min_lat + max_lat) / 2.0
                delta_lat = buffer_distance
                delta_lon = buffer_distance / max(cos(radians(center_lat)), 0.01)
                ring = _rectangle_ring(
                    min_lat - delta_lat,
                    min_lon - delta_lon,
                    max_lat + delta_lat,
                    max_lon + delta_lon,
                )
                return _polygon_geojson(ring)

            return geojson
        except Exception as e:
            logger.error(f"Error buffering geometry: {str(e)}")
            return None

    def simplify_geometry(self, geojson: dict, tolerance: float = None) -> Optional[dict]:
        """
        Simplify geometry for performance.

        Args:
            geojson: GeoJSON geometry
            tolerance: Simplification tolerance in degrees

        Returns:
            Simplified geometry GeoJSON
        """
        try:
            if tolerance is None:
                tolerance = GEOMETRY_SIMPLIFICATION_TOLERANCE

            if geojson.get("type") != "Polygon":
                return geojson

            ring = geojson["coordinates"][0]
            if len(ring) <= 5:
                return geojson

            # Basic simplification: drop every other interior point while preserving closure.
            simplified = [ring[0]]
            for index, point in enumerate(ring[1:-1], start=1):
                if index % 2 == 0:
                    simplified.append(point)
            simplified.append(ring[-1])
            if simplified[0] != simplified[-1]:
                simplified[-1] = simplified[0]

            return {"type": "Polygon", "coordinates": [simplified]}
        except Exception as e:
            logger.error(f"Error simplifying geometry: {str(e)}")
            return None


class GISProcessor:
    """
    Main GIS processor combining geometry creation and spatial operations
    """

    def __init__(self):
        self.geometry_processor = GeometryProcessor()
        logger.info("GISProcessor initialized")

    def process_warning_coordinates(self, warning: dict) -> dict:
        """
        Process coordinates from a warning into GIS geometry

        Args:
            warning: Warning dictionary with coordinates

        Returns:
            Warning with geometry added
        """
        coordinates = warning.get("coordinates", [])
        metadata = warning.get("metadata", {}) or {}

        if not coordinates:
            fallback_location = metadata.get("fallback_location")
            if fallback_location:
                warning.setdefault("metadata", {})
                warning["metadata"]["fallback_location"] = {
                    "name": fallback_location.get("name", NAVAREA_REDZONE_NAME),
                    "type": fallback_location.get("type", "navarea_redzone"),
                    "center": fallback_location.get(
                        "center",
                        {
                            "latitude": NAVAREA_REDZONE_CENTER_LAT,
                            "longitude": NAVAREA_REDZONE_CENTER_LON,
                        },
                    ),
                    "bounds": fallback_location.get("bounds", NAVAREA_REDZONE_BOUNDS),
                    "synthetic": True,
                }
                geometry = self._create_bounds_geometry(
                    warning["metadata"]["fallback_location"]["bounds"]
                )
                if geometry:
                    warning["geometry"] = geometry
                    logger.debug(
                        f"Created fallback POLYGON for warning {warning.get('warning_id')}"
                    )
                return warning
            else:
                logger.debug(f"No coordinates in warning {warning.get('warning_id')}")
                return warning

        coord_list = [
            (c["latitude"], c["longitude"])
            for c in coordinates
            if "latitude" in c and "longitude" in c
        ]

        if not coord_list:
            return warning

        geometry = self.geometry_processor.create_geometry(coord_list)
        if geometry:
            warning["geometry"] = geometry
            logger.debug(f"Created {geometry['geometry_type']} for warning {warning.get('warning_id')}")

        return warning

    def _create_bounds_geometry(self, bounds: dict) -> Optional[Dict]:
        """Create a red-zone polygon from stored bounds."""
        try:
            min_lat = float(bounds["min_lat"])
            max_lat = float(bounds["max_lat"])
            min_lon = float(bounds["min_lon"])
            max_lon = float(bounds["max_lon"])
        except Exception:
            logger.debug("Invalid bounds supplied for fallback geometry")
            return None

        ring = [
            (min_lat, min_lon),
            (min_lat, max_lon),
            (max_lat, max_lon),
            (max_lat, min_lon),
            (min_lat, min_lon),
        ]

        area_km2 = self.geometry_processor._calculate_area_km2_from_ring(ring)
        return {
            "geometry_type": "POLYGON",
            "geojson": {
                "type": "Polygon",
                "coordinates": [[[min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat], [min_lon, max_lat], [min_lon, min_lat]]],
            },
            "wkt": f"POLYGON (({min_lon} {min_lat}, {max_lon} {min_lat}, {max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))",
            "area_sq_km": area_km2,
        }

    def process_batch(self, warnings: List[dict]) -> List[dict]:
        """
        Process multiple warnings

        Args:
            warnings: List of warning dictionaries

        Returns:
            List of warnings with geometries
        """
        processed = []

        for warning in warnings:
            try:
                processed_warning = self.process_warning_coordinates(warning)
                processed.append(processed_warning)
            except Exception as e:
                logger.error(f"Error processing warning {warning.get('warning_id')}: {str(e)}")
                continue

        logger.info(f"Processed {len(processed)}/{len(warnings)} warnings with GIS")
        return processed

    def create_geojson_feature(self, warning: dict) -> Optional[Dict]:
        """
        Create a GeoJSON feature from a warning

        Args:
            warning: Warning dictionary with geometry

        Returns:
            GeoJSON feature or None
        """
        try:
            geometry = warning.get("geometry")
            if not geometry:
                return None

            feature = {
                "type": "Feature",
                "geometry": geometry.get("geojson"),
                "properties": {
                    "warning_id": warning.get("warning_id"),
                    "date": warning.get("date").isoformat() if warning.get("date") else None,
                    "message": warning.get("message", "")[:200],
                    "warning_type": warning.get("warning_type"),
                    "priority": warning.get("priority"),
                    "area": warning.get("area"),
                    "geometry_type": geometry.get("geometry_type"),
                    "area_sq_km": geometry.get("area_sq_km"),
                },
            }

            return feature
        except Exception as e:
            logger.error(f"Error creating GeoJSON feature: {str(e)}")
            return None

    def create_geojson_collection(self, warnings: List[dict]) -> Dict:
        """
        Create a GeoJSON FeatureCollection from warnings

        Args:
            warnings: List of warning dictionaries

        Returns:
            GeoJSON FeatureCollection
        """
        features = []
        for warning in warnings:
            feature = self.create_geojson_feature(warning)
            if feature:
                features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
        }


def process_warnings_for_gis(warnings: List[dict]) -> List[dict]:
    """
    Process warnings for GIS visualization

    Args:
        warnings: List of warning dictionaries

    Returns:
        List of warnings with GIS geometries
    """
    processor = GISProcessor()
    return processor.process_batch(warnings)


def create_geojson_from_warnings(warnings: List[dict]) -> Dict:
    """
    Create GeoJSON collection from warnings

    Args:
        warnings: List of warning dictionaries

    Returns:
        GeoJSON FeatureCollection
    """
    processor = GISProcessor()
    return processor.create_geojson_collection(warnings)
