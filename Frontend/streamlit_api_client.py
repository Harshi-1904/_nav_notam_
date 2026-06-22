"""
API Client for Pakistan NAVAREA IX GIS Agent
Handles all HTTP requests and data transformation
"""

import requests
import streamlit as st
import os
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import json
from loguru import logger


class NavAreaAPIClient:
    """Client for NAVAREA IX REST API"""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.timeout = 10
        logger.info(f"NavAreaAPIClient initialized with API URL: {api_url}")
    
    def health_check(self) -> bool:
        """Check if API is healthy"""
        try:
            response = requests.get(
                f"{self.api_url}/health",
                timeout=5,
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def get_live_warnings(self, hours_back: int = 24, limit: int = 100) -> Dict:
        """
        Fetch live warnings from past N hours
        
        Args:
            hours_back: Number of hours to look back
            limit: Maximum results
        
        Returns:
            Dict with status, count, and warning data
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/warnings/live",
                params={
                    "hours_back": hours_back,
                    "limit": limit,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch live warnings: {str(e)}")
            return {"status": "error", "data": [], "message": str(e)}
    
    def query_warnings(self, query: str, limit: int = 100) -> Dict:
        """
        Query warnings with natural language
        
        Args:
            query: Natural language query string
            limit: Maximum results
        
        Returns:
            Dict with matching warnings
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/warnings/query",
                params={
                    "query": query,
                    "limit": limit,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to query warnings: {str(e)}")
            return {"status": "error", "data": [], "message": str(e)}

    def search_warnings(
        self,
        query: Optional[str] = None,
        hours_back: int = 24,
        warning_type: Optional[str] = None,
        priority: Optional[str] = None,
        area: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
        include_geojson: bool = True,
    ) -> Dict:
        """Advanced database-backed search."""
        try:
            params = {
                "hours_back": hours_back,
                "limit": limit,
                "include_geojson": include_geojson,
            }

            if query:
                params["query"] = query
            if warning_type and warning_type != "All":
                params["warning_type"] = warning_type
            if priority and priority != "All":
                params["priority"] = priority
            if area:
                params["area"] = area
            if source and source != "all":
                params["source"] = source

            response = requests.get(
                f"{self.api_url}/api/warnings/search",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to search warnings: {str(e)}")
            return {
                "status": "error",
                "data": [],
                "geojson": {"type": "FeatureCollection", "features": []},
                "message": str(e),
            }

    def ask_warnings(
        self,
        question: Optional[str] = None,
        hours_back: int = 24,
        warning_type: Optional[str] = None,
        priority: Optional[str] = None,
        area: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 500,
        include_geojson: bool = True,
    ) -> Dict:
        """Ask the smart question endpoint for a simple answer plus map data."""
        try:
            params = {
                "hours_back": hours_back,
                "limit": limit,
                "include_geojson": include_geojson,
            }

            if question:
                params["query"] = question
            if warning_type and warning_type != "All":
                params["warning_type"] = warning_type
            if priority and priority != "All":
                params["priority"] = priority
            if area:
                params["area"] = area
            if source and source != "all":
                params["source"] = source

            response = requests.get(
                f"{self.api_url}/api/warnings/ask",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to ask warnings: {str(e)}")
            return {
                "status": "error",
                "answer": "I couldn't read the database right now.",
                "data": [],
                "geojson": {"type": "FeatureCollection", "features": []},
                "summary": {"total": 0, "with_coordinates": 0, "with_geometry": 0, "by_priority": {}, "by_type": {}},
                "message": str(e),
            }
    
    def get_warnings_by_type(self, warning_type: str, hours_back: int = 24, limit: int = 100) -> Dict:
        """Get warnings filtered by type"""
        try:
            response = requests.get(
                f"{self.api_url}/api/warnings/type/{warning_type}",
                params={
                    "hours_back": hours_back,
                    "limit": limit,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch warnings by type: {str(e)}")
            return {"status": "error", "data": [], "message": str(e)}
    
    def get_warnings_by_priority(self, priority: str, hours_back: int = 24, limit: int = 100) -> Dict:
        """Get warnings filtered by priority"""
        try:
            response = requests.get(
                f"{self.api_url}/api/warnings/priority/{priority}",
                params={
                    "hours_back": hours_back,
                    "limit": limit,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch warnings by priority: {str(e)}")
            return {"status": "error", "data": [], "message": str(e)}
    
    def get_statistics(self, hours_back: int = 24) -> Dict:
        """Get warning statistics"""
        try:
            response = requests.get(
                f"{self.api_url}/api/statistics",
                params={"hours_back": hours_back},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch statistics: {str(e)}")
            return {"status": "error", "statistics": {}, "message": str(e)}
    
    def get_geojson(self, hours_back: int = 24) -> Dict:
        """Get GeoJSON for mapping"""
        try:
            response = requests.get(
                f"{self.api_url}/api/geojson/live",
                params={"hours_back": hours_back},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch GeoJSON: {str(e)}")
            return {
                "status": "error",
                "geojson": {"type": "FeatureCollection", "features": []},
                "message": str(e)
            }
    
    def refresh_warnings(self) -> Dict:
        """Manually trigger refresh on backend"""
        try:
            response = requests.post(
                f"{self.api_url}/api/admin/refresh",
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh warnings: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def export_csv(self) -> Optional[bytes]:
        """Export warnings to CSV"""
        try:
            response = requests.get(
                f"{self.api_url}/api/admin/export",
                timeout=30,
            )
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to export CSV: {str(e)}")
            return None


class DataTransformer:
    """Transform API data for visualization"""
    
    @staticmethod
    def warnings_to_dataframe(warnings: List[Dict]) -> pd.DataFrame:
        """Convert warnings to DataFrame"""
        rows = []
        for w in warnings:
            coords = w.get("coordinates", [])
            rows.append({
                "ID": w.get("warning_id", "N/A"),
                "Date": w.get("date", "N/A"),
                "Type": w.get("warning_type", "N/A"),
                "Priority": w.get("priority", "N/A"),
                "Message": w.get("message", "N/A")[:100],
                "Coordinates": len(coords),
                "Area": w.get("area", "N/A"),
            })
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows)
    
    @staticmethod
    def extract_geojson_features(geojson: Dict) -> List[Dict]:
        """Extract features from GeoJSON"""
        return geojson.get("features", [])
    
    @staticmethod
    def get_priority_color(priority: str) -> str:
        """Map priority to hex color"""
        colors = {
            "high": "#ff0000",
            "medium": "#ff9800",
            "low": "#ffeb3b",
        }
        return colors.get(priority.lower(), "#9c27b0")
    
    @staticmethod
    def get_warning_type_icon(warning_type: str) -> str:
        """Get emoji for warning type"""
        icons = {
            "weapon_firing": "💥",
            "exercise": "🎯",
            "dredging": "🏗️",
            "buoy_missing": "🔴",
            "hazard": "⚠️",
            "search_rescue": "🆘",
            "navigation_hazard": "⛵",
            "construction": "🏗️",
            "unknown": "❓",
        }
        return icons.get(warning_type.lower(), "📌")


# Singleton instance
_api_client = None


def get_api_client(api_url: Optional[str] = None) -> NavAreaAPIClient:
    """Get or create API client instance"""
    global _api_client
    
    if api_url is None:
        try:
            secrets = st.secrets
            api_url = secrets.get("api_url", None)
        except FileNotFoundError:
            api_url = None
        except Exception:
            api_url = None

        if not api_url:
            api_url = os.getenv("API_URL", "http://localhost:8000")
    
    if _api_client is None or _api_client.api_url != api_url:
        _api_client = NavAreaAPIClient(api_url)
    
    return _api_client
