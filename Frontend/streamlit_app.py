"""
Pakistan NAVAREA IX GIS Real-Time Agent - Streamlit Frontend
Interactive dashboard for maritime intelligence and warning visualization
"""

import streamlit as st
import streamlit_folium as stf
import folium
import folium.plugins
import requests
import os
import pandas as pd
import json
import websocket
import threading
import time
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import plotly.graph_objects as go
import plotly.express as px
from loguru import logger

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Pakistan NAVAREA IX - Maritime Intelligence",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-container {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .warning-card {
        background-color: #fff5f5;
        padding: 15px;
        border-left: 4px solid #ff6b6b;
        margin: 10px 0;
        border-radius: 5px;
    }
    .high-priority {
        border-left-color: #ff0000 !important;
        background-color: #ffe0e0 !important;
    }
    .medium-priority {
        border-left-color: #ff9800 !important;
        background-color: #fff3e0 !important;
    }
    .low-priority {
        border-left-color: #ffeb3b !important;
        background-color: #fffde7 !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CONFIGURATION
# ============================================================================

def _get_config_value(key: str, default):
    """Read a Streamlit secret if available, otherwise fall back to env/default."""
    try:
        secrets = st.secrets
        if key in secrets:
            return secrets[key]
    except FileNotFoundError:
        pass
    except Exception:
        pass

    env_key = key.upper()
    if env_key in os.environ:
        value = os.environ.get(env_key)
        if isinstance(default, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        return value

    return default


API_BASE_URL = _get_config_value("api_url", "http://localhost:8000")
REFRESH_INTERVAL = _get_config_value("refresh_interval", 60)

# Initialize session state
if "warnings_data" not in st.session_state:
    st.session_state.warnings_data = []
    st.session_state.last_update = None
    st.session_state.ws_connected = False

# ============================================================================
# API FUNCTIONS
# ============================================================================

@st.cache_data(ttl=30)
def fetch_live_warnings(hours_back: int = 24, limit: int = 100) -> Dict:
    """Fetch live warnings from API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/warnings/live",
            params={"hours_back": hours_back, "limit": limit},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch live warnings: {str(e)}")
        return {"status": "error", "data": []}


@st.cache_data(ttl=30)
def fetch_statistics(hours_back: int = 24) -> Dict:
    """Fetch statistics from API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/statistics",
            params={"hours_back": hours_back},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch statistics: {str(e)}")
        return {"status": "error", "statistics": {}}


@st.cache_data(ttl=30)
def fetch_geojson(hours_back: int = 24) -> Dict:
    """Fetch GeoJSON data from API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/geojson/live",
            params={"hours_back": hours_back},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch GeoJSON: {str(e)}")
        return {"status": "error", "geojson": {"type": "FeatureCollection", "features": []}}


def query_warnings(query: str) -> Dict:
    """Query warnings with natural language"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/warnings/query",
            params={"query": query, "limit": 100},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to query warnings: {str(e)}")
        return {"status": "error", "data": []}


def search_warnings_advanced(
    query: Optional[str] = None,
    hours_back: int = 24,
    warning_type: Optional[str] = None,
    priority: Optional[str] = None,
    area: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100,
    include_geojson: bool = True,
) -> Dict:
    """Search warnings using the advanced database-backed endpoint."""
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
            params["area"] = area.strip()
        if source and source != "all":
            params["source"] = source

        response = requests.get(
            f"{API_BASE_URL}/api/warnings/search",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to search warnings: {str(e)}")
        return {"status": "error", "data": [], "geojson": {"type": "FeatureCollection", "features": []}}


def ask_warnings_smart(
    question: Optional[str] = None,
    hours_back: int = 24,
    warning_type: Optional[str] = None,
    priority: Optional[str] = None,
    area: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 500,
    include_geojson: bool = True,
) -> Dict:
    """Ask the backend a natural-language question and get answer + map data."""
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
            params["area"] = area.strip()
        if source and source != "all":
            params["source"] = source

        response = requests.get(
            f"{API_BASE_URL}/api/warnings/ask",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to ask warnings: {str(e)}")
        return {
            "status": "error",
            "answer": "I couldn't read the database right now.",
            "data": [],
            "geojson": {"type": "FeatureCollection", "features": []},
            "summary": {"total": 0, "with_coordinates": 0, "with_geometry": 0, "by_priority": {}, "by_type": {}},
        }


def refresh_warnings() -> Dict:
    """Manually trigger refresh on API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/admin/refresh",
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to refresh warnings: {str(e)}")
        return {"status": "error"}


def export_warnings_csv() -> bytes:
    """Export warnings to CSV"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/admin/export",
            timeout=30,
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"Failed to export warnings: {str(e)}")
        return b""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def reset_all_controls() -> None:
    """Reset all sidebar and query widgets to their defaults."""
    defaults = {
        "sidebar_query_text": "",
        "sidebar_source": "all",
        "sidebar_warning_type": "All",
        "sidebar_priority": "All",
        "sidebar_area": "",
        "sidebar_result_limit": 500,
        "sidebar_live_refresh": False,
        "sidebar_refresh_seconds": int(REFRESH_INTERVAL),
        "legacy_hours_back": 24,
        "legacy_view_mode": "Dashboard",
        "legacy_warning_type": "All",
        "legacy_priority": "All",
        "query_text_search": "",
        "query_hours_back": 24,
        "query_source": "all",
        "query_warning_type": "All",
        "query_priority": "All",
        "query_area": "",
    }

    for key, value in defaults.items():
        st.session_state[key] = value

    st.cache_data.clear()


def reset_query_controls() -> None:
    """Reset the query tab controls without touching the rest of the page."""
    defaults = {
        "query_text_search": "",
        "query_hours_back": 24,
        "query_source": "all",
        "query_warning_type": "All",
        "query_priority": "All",
        "query_area": "",
    }

    for key, value in defaults.items():
        st.session_state[key] = value

    st.cache_data.clear()

def get_priority_color(priority: str) -> str:
    """Map priority to color"""
    priority_colors = {
        "high": "#ff0000",
        "medium": "#ff9800",
        "low": "#ffeb3b",
    }
    return priority_colors.get(priority.lower(), "#9c27b0")


def get_warning_type_icon(warning_type: str) -> str:
    """Get emoji icon for warning type"""
    type_icons = {
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
    return type_icons.get(warning_type.lower(), "📌")


def create_folium_map(geojson_data: Dict) -> folium.Map:
    """Create Folium map with GeoJSON warnings"""
    
    # Create base map centered on Pakistan NAVAREA IX
    m = folium.Map(
        location=[20.0, 65.0],  # Center of NAVAREA IX
        zoom_start=6,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    point_cluster = folium.plugins.MarkerCluster(name="Point warnings")
    point_cluster.add_to(m)
    
    # Add GeoJSON features
    features = geojson_data.get("features", [])
    
    for feature in features:
        props = feature.get("properties", {})
        geom = props.get("display_geojson") or feature.get("geometry", {})
        
        if not geom or "coordinates" not in geom:
            continue
        
        warning_type = props.get("warning_type", "unknown")
        priority = props.get("priority", "medium")
        warning_id = props.get("warning_id", "Unknown")
        message = props.get("message", "")[:100]
        
        # Choose color based on priority
        color = get_priority_color(priority)
        
        # Get coordinates
        coords = geom.get("coordinates", [])
        
        if geom.get("type") == "Point" and len(coords) >= 2:
            # Point geometry
            lon, lat = coords[0], coords[1]
            
            popup_text = f"""
            <b>{warning_id}</b><br>
            Type: {warning_type}<br>
            Priority: {priority}<br>
            Message: {message}
            """
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=f"{warning_id} | {warning_type} | {priority}",
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.75,
                weight=2,
            ).add_to(point_cluster)
        
        elif geom.get("type") == "Polygon" and len(coords) > 0:
            # Polygon geometry
            polygon_coords = [[lat, lon] for lon, lat in coords[0]]
            
            popup_text = f"""
            <b>{warning_id}</b><br>
            Type: {warning_type}<br>
            Priority: {priority}
            """
            
            folium.Polygon(
                locations=polygon_coords,
                popup=folium.Popup(popup_text, max_width=250),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.3,
                weight=2,
            ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)

    # Add minimap
    minimap = folium.plugins.MiniMap(toggle_display=True)
    m.add_child(minimap)
    
    # Add fullscreen button
    folium.plugins.Fullscreen().add_to(m)
    
    return m


def format_warning_card(warning: Dict) -> str:
    """Format warning as HTML card"""
    icon = get_warning_type_icon(warning.get("warning_type", "unknown"))
    priority = warning.get("priority", "medium").lower()
    
    coords = warning.get("coordinates", [])
    coord_text = ""
    if coords:
        for i, coord in enumerate(coords[:2], 1):
            coord_text += f"<br>📍 Coord {i}: {coord.get('latitude', 0):.4f}°, {coord.get('longitude', 0):.4f}°"
    
    return f"""
    <div class="warning-card {priority}-priority">
        <strong>{icon} {warning.get('warning_id', 'Unknown')}</strong><br>
        <small>{warning.get('date', 'N/A')}</small><br>
        <strong>Type:</strong> {warning.get('warning_type', 'Unknown')}<br>
        <strong>Priority:</strong> <span style="color: {get_priority_color(priority)};"><strong>{priority.upper()}</strong></span><br>
        <strong>Message:</strong> {warning.get('message', '')[:150]}...{coord_text}
    </div>
    """


def summarize_warnings(warnings: List[Dict]) -> Dict[str, Dict]:
    """Summarize a warning list for charts and metrics."""
    summary = {
        "total": len(warnings),
        "with_coordinates": 0,
        "with_geometry": 0,
        "by_priority": {},
        "by_type": {},
    }

    for warning in warnings:
        priority = (warning.get("priority") or "unknown").lower()
        warning_type = (warning.get("warning_type") or warning.get("type") or "unknown").lower()
        coords = warning.get("coordinates") or []

        summary["by_priority"][priority] = summary["by_priority"].get(priority, 0) + 1
        summary["by_type"][warning_type] = summary["by_type"].get(warning_type, 0) + 1

        if coords:
            summary["with_coordinates"] += 1
        if warning.get("geometry") or warning.get("location_hint"):
            summary["with_geometry"] += 1

    return summary


def build_warning_dataframe(warnings: List[Dict]) -> pd.DataFrame:
    """Build a compact table for the current query results."""
    rows = []
    for warning in warnings:
        coords = warning.get("coordinates") or []
        rows.append(
            {
                "ID": warning.get("warning_id", "N/A"),
                "Date": warning.get("date", "N/A"),
                "Type": warning.get("warning_type") or warning.get("type") or "N/A",
                "Priority": warning.get("priority", "N/A"),
                "Area": warning.get("area", "N/A"),
                "Source": warning.get("source_type", "N/A"),
                "Coordinates": len(coords),
                "Geometry": (warning.get("geometry") or {}).get("type")
                if isinstance(warning.get("geometry"), dict)
                else warning.get("geometry"),
            }
        )

    return pd.DataFrame(rows)


def enable_live_refresh(interval_seconds: int, enabled: bool) -> None:
    """Keep the UI live without forcing a browser reload."""
    if not enabled:
        return

    interval_seconds = max(int(interval_seconds), 15)
    st.caption(
        f"Live updates enabled. Click Refresh Data for an immediate backend sync; "
        f"browser reloads are disabled to keep the page stable."
    )


# ============================================================================
# UNIFIED COMMAND CENTER
# ============================================================================

st.sidebar.title("⚙️ Query Controls")

hours_back = st.sidebar.slider(
    "Time Range (hours)",
    min_value=1,
    max_value=720,
    value=24,
    step=1,
)

st.sidebar.subheader("Search")
query_text = st.sidebar.text_input(
    "Ask the database",
    placeholder="e.g., total warnings, all warnings, last 4 days, 48 hours",
    key="sidebar_query_text",
)

all_types = [
    "All",
    "weapon_firing",
    "exercise",
    "dredging",
    "buoy_missing",
    "hazard",
    "search_rescue",
    "navigation_hazard",
    "construction",
    "unknown",
]
all_priorities = ["All", "high", "medium", "low"]

selected_source = st.sidebar.selectbox("Source", ["all", "navarea", "coastal"], index=0, key="sidebar_source")
selected_type = st.sidebar.selectbox("Warning Type", all_types, index=0, key="sidebar_warning_type")
selected_priority = st.sidebar.selectbox("Priority", all_priorities, index=0, key="sidebar_priority")
selected_area = st.sidebar.text_input("Area contains", placeholder="e.g., Karachi, Gwadar, Arabian Sea", key="sidebar_area")
result_limit = st.sidebar.slider("Result limit", min_value=25, max_value=1000, value=500, step=25, key="sidebar_result_limit")
live_refresh = st.sidebar.checkbox("Auto refresh", value=False, key="sidebar_live_refresh")
refresh_seconds = st.sidebar.slider("Refresh every (seconds)", min_value=30, max_value=120, value=int(REFRESH_INTERVAL), step=5, key="sidebar_refresh_seconds")

st.sidebar.button("🔄 Reset All", use_container_width=True, on_click=reset_all_controls)

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    result = refresh_warnings()
    if result.get("status") == "success":
        st.success(f"✓ Refreshed: {result.get('inserted', 0)} new warnings")
    else:
        st.error(f"Failed to refresh: {result.get('message', 'Unknown error')}")

if st.sidebar.button("📥 Export CSV", use_container_width=True):
    csv_data = export_warnings_csv()
    if csv_data:
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=f"navarea_warnings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

st.sidebar.subheader("API Status")
try:
    health = requests.get(f"{API_BASE_URL}/health", timeout=5).json()
    st.sidebar.success("✓ Connected")
    db_total = health.get("warnings_in_database", 0)
    st.sidebar.metric("Warnings in DB", db_total)
except Exception:
    health = {"warnings_in_database": 0}
    st.sidebar.error("✗ API Unavailable")

st.sidebar.caption("Results update automatically as you change filters.")
st.sidebar.markdown("---")
st.sidebar.caption("Pakistan NAVAREA IX GIS Agent v1.0")

col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    st.image("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext x='50' y='50' font-size='80' text-anchor='middle' dominant-baseline='middle'%3E🚢%3C/text%3E%3C/svg%3E", width=80)

with col2:
    st.title("🌊 Pakistan NAVAREA IX")
    st.markdown("### Maritime Intelligence & Database-Driven Warning Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Time range: Last {hours_back} hours")

with col3:
    st.write("")

st.markdown("---")

enable_live_refresh(refresh_seconds, live_refresh)

search_response = ask_warnings_smart(
    question=query_text or None,
    hours_back=hours_back,
    warning_type=selected_type,
    priority=selected_priority,
    area=selected_area or None,
    source=selected_source,
    limit=result_limit,
    include_geojson=True,
)

warnings = search_response.get("data", [])
geojson = search_response.get("geojson", {"type": "FeatureCollection", "features": []})
filters = search_response.get("filters", {})
summary = search_response.get("summary", summarize_warnings(warnings))
answer_text = search_response.get("answer", "Showing matching warnings.")

st.subheader("📊 Live Overview")
metric_cols = st.columns(5)

with metric_cols[0]:
    st.metric("Warnings in DB", health.get("warnings_in_database", 0))
with metric_cols[1]:
    st.metric("Matching Warnings", summary["total"])
with metric_cols[2]:
    st.metric("High Priority", summary["by_priority"].get("high", 0))
with metric_cols[3]:
    st.metric("With Coordinates", summary["with_coordinates"])
with metric_cols[4]:
    st.metric("With Boundaries", summary["with_geometry"])

st.success(answer_text)

if filters:
    st.caption(
        " | ".join(
            [
                f"hours_back={filters.get('hours_back')}",
                f"query={query_text or 'all warnings'}",
                f"type={filters.get('warning_type') or 'all'}",
                f"priority={filters.get('priority') or 'all'}",
                f"area={filters.get('area') or 'any'}",
                f"source={filters.get('source') or 'all'}",
                f"limit={result_limit}",
            ]
        )
    )

map_col, stats_col = st.columns([2, 1])

with map_col:
    st.subheader("🗺️ Interactive Map")
    try:
        map_obj = create_folium_map(geojson)
        stf.folium_static(map_obj, width=900, height=620)
    except Exception as e:
        st.error(f"Failed to render map: {str(e)}")

with stats_col:
    st.subheader("📈 Statistics")

    if summary["by_priority"]:
        priority_data = summary["by_priority"]
        fig_priority = go.Figure(
            data=[
                go.Bar(
                    x=list(priority_data.keys()),
                    y=list(priority_data.values()),
                    marker=dict(color=["#ff0000", "#ff9800", "#ffeb3b", "#4caf50"]),
                )
            ]
        )
        fig_priority.update_layout(
            title="By Priority",
            xaxis_title="",
            yaxis_title="Count",
            height=300,
            showlegend=False,
            margin=dict(l=0, r=0, t=30, b=0),
        )
        st.plotly_chart(fig_priority, use_container_width=True)

    if summary["by_type"]:
        type_data = summary["by_type"]
        fig_type = go.Figure(
            data=[go.Pie(labels=list(type_data.keys()), values=list(type_data.values()))]
        )
        fig_type.update_layout(
            title="By Type",
            height=300,
            margin=dict(l=0, r=0, t=30, b=0),
        )
        st.plotly_chart(fig_type, use_container_width=True)

st.subheader("📋 Matching Results")
if warnings:
    df = build_warning_dataframe(warnings)
    st.dataframe(df, use_container_width=True, height=280)

    st.download_button(
        label="Download Matching Results as CSV",
        data=df.to_csv(index=False),
        file_name=f"navarea_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

    with st.expander("Show warning cards"):
        for warning in warnings[:50]:
            st.markdown(format_warning_card(warning), unsafe_allow_html=True)
else:
    st.info("No warnings found matching the current database filters.")

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 12px;">
    <p>Pakistan NAVAREA IX GIS Real-Time Agent | Maritime Intelligence Dashboard</p>
    <p>Data sourced from Pakistan Navy Hydrography & Coastal Warnings</p>
</div>
""", unsafe_allow_html=True)

st.stop()

# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================

st.sidebar.title("⚙️ Configuration")

# Time range selector
hours_back = st.sidebar.slider(
    "Time Range (hours)",
    min_value=1,
    max_value=168,
    value=24,
    step=1,
    key="legacy_hours_back",
)

# View selector
view_mode = st.sidebar.radio(
    "View Mode",
    ["Dashboard", "Map", "Query", "Statistics", "Data Table"],
    index=0,
    key="legacy_view_mode",
)

# Filter by type
st.sidebar.subheader("Filters")
all_types = [
    "All",
    "weapon_firing",
    "exercise",
    "dredging",
    "buoy_missing",
    "hazard",
    "search_rescue",
    "navigation_hazard",
    "construction",
    "unknown",
]
selected_type = st.sidebar.selectbox("Warning Type", all_types, index=0, key="legacy_warning_type")

# Filter by priority
all_priorities = ["All", "high", "medium", "low"]
selected_priority = st.sidebar.selectbox("Priority", all_priorities, index=0, key="legacy_priority")

# Refresh button
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    result = refresh_warnings()
    if result.get("status") == "success":
        st.success(f"✓ Refreshed: {result.get('inserted', 0)} new warnings")
    else:
        st.error(f"Failed to refresh: {result.get('message', 'Unknown error')}")

# Export button
if st.sidebar.button("📥 Export CSV", use_container_width=True):
    csv_data = export_warnings_csv()
    if csv_data:
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=f"navarea_warnings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

# API status
st.sidebar.subheader("API Status")
try:
    health = requests.get(f"{API_BASE_URL}/health", timeout=5).json()
    st.sidebar.success(f"✓ Connected")
    st.sidebar.metric("Warnings in DB", health.get("warnings_in_database", 0))
except:
    st.sidebar.error("✗ API Unavailable")

st.sidebar.markdown("---")
st.sidebar.caption("Pakistan NAVAREA IX GIS Agent v1.0")

# ============================================================================
# MAIN CONTENT AREA
# ============================================================================

# Header
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    st.image("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext x='50' y='50' font-size='80' text-anchor='middle' dominant-baseline='middle'%3E🚢%3C/text%3E%3C/svg%3E", width=80)

with col2:
    st.title("🌊 Pakistan NAVAREA IX")
    st.markdown("### Maritime Intelligence & Real-Time Warning Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Time range: Last {hours_back} hours")

with col3:
    st.write("")

st.markdown("---")

# ============================================================================
# DASHBOARD VIEW
# ============================================================================

if view_mode == "Dashboard":
    # Fetch data
    warnings_response = fetch_live_warnings(hours_back=hours_back, limit=result_limit)
    stats_response = fetch_statistics(hours_back=hours_back)
    geojson_response = fetch_geojson(hours_back=hours_back)
    
    warnings = warnings_response.get("data", [])
    stats = stats_response.get("statistics", {})
    geojson = geojson_response.get("geojson", {"type": "FeatureCollection", "features": []})
    
    # Filter warnings
    if selected_type != "All":
        warnings = [w for w in warnings if w.get("warning_type") == selected_type]
    if selected_priority != "All":
        warnings = [w for w in warnings if w.get("priority") == selected_priority]
    
    # Key metrics
    st.subheader("📊 Key Metrics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Warnings in DB",
            health.get("warnings_in_database", 0),
            delta=stats.get("total", 0),
            delta_color="off",
        )
    
    with col2:
        high_priority = len([w for w in warnings if w.get("priority") == "high"])
        st.metric(
            "High Priority",
            high_priority,
            delta=f"{(high_priority/len(warnings)*100):.0f}%" if warnings else "0%",
        )
    
    with col3:
        by_type = stats.get("by_type", {})
        exercise_count = by_type.get("exercise", 0)
        st.metric("Exercises", exercise_count)
    
    with col4:
        hazard_count = by_type.get("hazard", 0)
        st.metric("Hazards", hazard_count)
    
    with col5:
        coords_extracted = len([w for w in warnings if w.get("coordinates_extracted")])
        st.metric(
            "With Coordinates",
            coords_extracted,
            delta=f"{(coords_extracted/len(warnings)*100):.0f}%" if warnings else "0%",
        )
    
    # Two column layout
    col_map, col_stats = st.columns([2, 1])
    
    with col_map:
        st.subheader("🗺️ Interactive Map")
        try:
            map_obj = create_folium_map(geojson)
            stf.folium_static(map_obj, width=700, height=500)
        except Exception as e:
            st.error(f"Failed to render map: {str(e)}")
    
    with col_stats:
        st.subheader("📈 Statistics")
        
        # Priority distribution
        if stats.get("by_priority"):
            priority_data = stats.get("by_priority", {})
            fig_priority = go.Figure(
                data=[
                    go.Bar(
                        x=list(priority_data.keys()),
                        y=list(priority_data.values()),
                        marker=dict(
                            color=["#ff0000", "#ff9800", "#ffeb3b"],
                        ),
                    )
                ]
            )
            fig_priority.update_layout(
                title="By Priority",
                xaxis_title="",
                yaxis_title="Count",
                height=300,
                showlegend=False,
                margin=dict(l=0, r=0, t=30, b=0),
            )
            st.plotly_chart(fig_priority, use_container_width=True)
        
        # Type distribution
        if stats.get("by_type"):
            type_data = stats.get("by_type", {})
            fig_type = go.Figure(
                data=[
                    go.Pie(
                        labels=list(type_data.keys()),
                        values=list(type_data.values()),
                    )
                ]
            )
            fig_type.update_layout(
                title="By Type",
                height=300,
                margin=dict(l=0, r=0, t=30, b=0),
            )
            st.plotly_chart(fig_type, use_container_width=True)
    
    # Latest warnings
    st.subheader("📋 Latest Warnings")
    
    if warnings:
        for warning in warnings[:10]:
            st.markdown(format_warning_card(warning), unsafe_allow_html=True)
    else:
        st.info("No warnings found for the selected filters and time range.")

# ============================================================================
# MAP VIEW
# ============================================================================

elif view_mode == "Map":
    st.subheader("🗺️ Interactive Map")
    
    geojson_response = fetch_geojson(hours_back=hours_back)
    geojson = geojson_response.get("geojson", {"type": "FeatureCollection", "features": []})
    
    try:
        map_obj = create_folium_map(geojson)
        stf.folium_static(map_obj, width=1400, height=700)
    except Exception as e:
        st.error(f"Failed to render map: {str(e)}")
    
    # Show features info
    st.subheader("📍 Map Features")
    features = geojson.get("features", [])
    st.write(f"Total features: {len(features)}")
    
    if features:
        df_features = pd.DataFrame([f.get("properties", {}) for f in features])
        st.dataframe(df_features, use_container_width=True)

# ============================================================================
# QUERY VIEW
# ============================================================================

elif view_mode == "Query":
    st.subheader("🔍 Advanced Database Query")

    st.button("🔄 Reset Query Filters", use_container_width=True, key="reset_query_filters", on_click=reset_query_controls)

    with st.form("advanced_query_form", clear_on_submit=False):
        st.caption("Search the database using text plus structured filters.")
        query = st.text_input(
            "Search text",
            placeholder="e.g., Karachi, exercise, buoy missing, coastal, last 4 days",
            key="query_text_search",
        )

        col_a, col_b = st.columns(2)
        with col_a:
            query_hours_back = st.slider(
                "Hours back",
                min_value=1,
                max_value=720,
                value=hours_back,
                step=1,
                key="query_hours_back",
            )
            query_source = st.selectbox(
                "Source",
                ["all", "navarea", "coastal"],
                index=0,
                key="query_source",
            )

        with col_b:
            query_warning_type = st.selectbox("Warning Type", all_types, index=0, key="query_warning_type")
            query_priority = st.selectbox("Priority", all_priorities, index=0, key="query_priority")

        query_area = st.text_input(
            "Area contains",
            placeholder="e.g., Karachi, Gwadar, Arabian Sea",
            key="query_area",
        )

        submitted = st.form_submit_button("Search Database", use_container_width=True)

    if submitted:
        result = search_warnings_advanced(
            query=query or None,
            hours_back=query_hours_back,
            warning_type=query_warning_type,
            priority=query_priority,
            area=query_area or None,
            source=query_source,
            limit=200,
            include_geojson=True,
        )

        warnings = result.get("data", [])
        geojson = result.get("geojson", {"type": "FeatureCollection", "features": []})
        filters = result.get("filters", {})

        st.success(f"Found {len(warnings)} warnings in the database")

        if filters:
            st.caption(
                " | ".join(
                    [
                        f"hours_back={filters.get('hours_back')}",
                        f"type={filters.get('warning_type') or 'all'}",
                        f"priority={filters.get('priority') or 'all'}",
                        f"area={filters.get('area') or 'any'}",
                        f"source={filters.get('source') or 'all'}",
                    ]
                )
            )

        col_results, col_query_map = st.columns([1, 1])

        with col_query_map:
            st.markdown("#### Query Map")
            try:
                if geojson.get("features"):
                    map_obj = create_folium_map(geojson)
                    stf.folium_static(map_obj, width=700, height=520)
                else:
                    st.info("No coordinates were available for the query results.")
            except Exception as e:
                st.error(f"Failed to render query map: {str(e)}")

        with col_results:
            st.markdown("#### Results")
            if warnings:
                df_query = pd.DataFrame([
                    {
                        "ID": w.get("warning_id", "N/A"),
                        "Date": w.get("date", "N/A"),
                        "Type": w.get("warning_type", "N/A"),
                        "Priority": w.get("priority", "N/A"),
                        "Area": w.get("area", "N/A"),
                        "Source": w.get("source_type", "N/A"),
                        "Coords": len(w.get("coordinates", [])),
                    }
                    for w in warnings
                ])
                st.dataframe(df_query, use_container_width=True, height=250)

                with st.expander("Show warning cards"):
                    for warning in warnings[:25]:
                        st.markdown(format_warning_card(warning), unsafe_allow_html=True)
            else:
                st.info("No warnings found matching your database search.")

# ============================================================================
# STATISTICS VIEW
# ============================================================================

elif view_mode == "Statistics":
    st.subheader("📊 Detailed Statistics")
    
    stats_response = fetch_statistics(hours_back=hours_back)
    stats = stats_response.get("statistics", {})
    
    # Overview stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Warnings", stats.get("total", 0))
    
    with col2:
        st.metric("Unique Types", len(stats.get("by_type", {})))
    
    with col3:
        st.metric("High Priority %", f"{stats.get('high_priority_percentage', 0):.1f}%")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        if stats.get("by_type"):
            type_data = stats.get("by_type", {})
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=list(type_data.keys()),
                        y=list(type_data.values()),
                        marker=dict(color="rgba(99,110,250,0.7)"),
                    )
                ]
            )
            fig.update_layout(
                title="Warnings by Type",
                xaxis_title="Warning Type",
                yaxis_title="Count",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if stats.get("by_priority"):
            priority_data = stats.get("by_priority", {})
            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=list(priority_data.keys()),
                        values=list(priority_data.values()),
                        marker=dict(
                            colors=["#ff0000", "#ff9800", "#ffeb3b"],
                        ),
                    )
                ]
            )
            fig.update_layout(
                title="Warnings by Priority",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Raw statistics
    st.subheader("Raw Data")
    st.json(stats)

# ============================================================================
# DATA TABLE VIEW
# ============================================================================

elif view_mode == "Data Table":
    st.subheader("📋 Data Table")
    
    warnings_response = fetch_live_warnings(hours_back=hours_back, limit=500)
    warnings = warnings_response.get("data", [])
    
    # Filter warnings
    if selected_type != "All":
        warnings = [w for w in warnings if w.get("warning_type") == selected_type]
    if selected_priority != "All":
        warnings = [w for w in warnings if w.get("priority") == selected_priority]
    
    if warnings:
        # Create DataFrame
        df_data = []
        for w in warnings:
            coords = w.get("coordinates", [])
            df_data.append({
                "ID": w.get("warning_id", "N/A"),
                "Date": w.get("date", "N/A"),
                "Type": w.get("warning_type", "N/A"),
                "Priority": w.get("priority", "N/A"),
                "Message": w.get("message", "N/A")[:100],
                "Coordinates": f"{len(coords)} points",
                "Area": w.get("area", "N/A"),
            })
        
        df = pd.DataFrame(df_data)
        
        # Display table
        st.dataframe(df, use_container_width=True)
        
        # Download CSV
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"navarea_warnings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No warnings found for the selected filters and time range.")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 12px;">
    <p>Pakistan NAVAREA IX GIS Real-Time Agent | Maritime Intelligence Dashboard</p>
    <p>Data sourced from Pakistan Navy Hydrography & Coastal Warnings</p>
</div>
""", unsafe_allow_html=True)
