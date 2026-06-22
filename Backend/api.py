"""
FastAPI application for Pakistan NAVAREA IX GIS Real-Time Agent
Provides REST API and WebSocket endpoints for warning data
"""

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime
import asyncio
import json
from loguru import logger

from config import (
    API_HOST,
    API_PORT,
    ALLOWED_ORIGINS,
    LOG_LEVEL,
    LOG_FILE,
    ENABLE_WEBSOCKET,
)
from models import (
    init_db,
    NavAreaWarningSchema,
    get_db,
)
from database import get_database
from query_engine import get_query_engine
from scraper import scrape_pakistan_navarea
from parser import parse_navarea_warnings
from gis_processor import process_warnings_for_gis

# ============================================================================
# LOGGING SETUP
# ============================================================================

logger.remove()  # Remove default handler
logger.add(
    LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level=LOG_LEVEL,
)
logger.add(
    lambda msg: None,  # Console output
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level=LOG_LEVEL,
)

# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        logger.info("ConnectionManager initialized")
    
    async def connect(self, websocket: WebSocket):
        """Accept and store new connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✓ Client connected. Total clients: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove disconnected client"""
        self.active_connections.remove(websocket)
        logger.info(f"✓ Client disconnected. Total clients: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {str(e)}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            await self.disconnect(connection)
        
        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected clients")


manager = ConnectionManager()

# ============================================================================
# LIFESPAN EVENTS
# ============================================================================

async def startup():
    """Initialize on startup"""
    logger.info("🚀 Starting Pakistan NAVAREA IX GIS Agent")
    
    try:
        # Initialize database
        init_db()
        logger.info("✓ Database initialized")
        
        # Optional: Run initial data collection
        logger.info("📡 Fetching initial warnings...")
        warnings = scrape_pakistan_navarea()
        if warnings:
            logger.info(f"✓ Scraped {len(warnings)} initial warnings")
            
            # Parse warnings
            parsed = parse_navarea_warnings(warnings)
            
            # Process for GIS
            gis_processed = process_warnings_for_gis(parsed)
            
            # Insert into database
            db = get_database()
            inserted, skipped = db.insert_batch(gis_processed)
            logger.info(f"✓ Inserted {inserted} warnings, skipped {skipped} duplicates")
    
    except Exception as e:
        logger.error(f"✗ Startup error: {str(e)}")


async def shutdown():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down Pakistan NAVAREA IX GIS Agent")
    
    # Close all WebSocket connections
    for connection in manager.active_connections:
        await connection.close()
    
    logger.info("✓ All connections closed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    await startup()
    yield
    await shutdown()

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Pakistan NAVAREA IX GIS Real-Time Agent",
    description="Real-time maritime warnings and GIS visualization",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db = get_database()
    warning_count = db.count_warnings()
    
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "warnings_in_database": warning_count,
    }

# ============================================================================
# WARNING ENDPOINTS
# ============================================================================

@app.get("/api/warnings/live")
async def get_live_warnings(
    hours_back: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
) -> JSONResponse:
    """
    Get latest warnings from past N hours
    
    Query Parameters:
        - hours_back: Number of hours to look back (default: 24)
        - limit: Maximum results (default: 100)
    
    Returns:
        List of warnings with coordinates and geometries
    """
    try:
        query_engine = get_query_engine()
        warnings = query_engine.query_last_hours(hours_back)[:limit]
        
        results = query_engine.format_results(warnings)
        
        return JSONResponse({
            "status": "success",
            "count": len(results),
            "hours_back": hours_back,
            "data": results,
        })
    
    except Exception as e:
        logger.error(f"✗ Error in /api/warnings/live: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

@app.get("/api/warnings/query")
async def query_warnings(
    query: str = Query(..., description="Query string (e.g., 'last 24 hours')"),
    limit: int = Query(100, ge=1, le=1000),
) -> JSONResponse:
    """
    Query warnings with natural language
    
    Examples:
        - /api/warnings/query?query=last%2024%20hours
        - /api/warnings/query?query=high%20priority
        - /api/warnings/query?query=weapon%20firing
    
    Returns:
        List of matching warnings
    """
    try:
        query_engine = get_query_engine()
        warnings = query_engine.query_by_natural_language(query)[:limit]
        
        results = query_engine.format_results(warnings)
        
        return JSONResponse({
            "status": "success",
            "count": len(results),
            "query": query,
            "data": results,
        })
    
    except Exception as e:
        logger.error(f"✗ Error in /api/warnings/query: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

@app.get("/api/warnings/search")
async def search_warnings(
    query: Optional[str] = Query(None, description="Free-text query"),
    hours_back: int = Query(24, ge=1, le=720),
    warning_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    source: Optional[str] = Query(None, description="all, navarea, or coastal"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=10000),
    include_geojson: bool = Query(True),
) -> JSONResponse:
    """
    Advanced database-backed search endpoint.
    """
    try:
        query_engine = get_query_engine()
        warnings = query_engine.advanced_search(
            search_text=query,
            hours_back=hours_back,
            warning_type=warning_type,
            priority=priority,
            area=area,
            source=source,
            limit=limit,
            offset=offset,
        )

        results = query_engine.format_results(warnings)
        payload = {
            "status": "success",
            "count": len(results),
            "query": query,
            "filters": {
                "hours_back": hours_back,
                "warning_type": warning_type,
                "priority": priority,
                "area": area,
                "source": source,
                "offset": offset,
            },
            "data": results,
        }

        if include_geojson:
            payload["geojson"] = query_engine.format_as_geojson(warnings)

        return JSONResponse(payload)

    except Exception as e:
        logger.error(f"Error in /api/warnings/search: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500,
        )

@app.get("/api/warnings/ask")
async def ask_warnings(
    query: Optional[str] = Query(None, description="Plain-language question"),
    hours_back: int = Query(24, ge=1, le=720),
    warning_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    source: Optional[str] = Query(None, description="all, navarea, or coastal"),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=10000),
    include_geojson: bool = Query(True),
) -> JSONResponse:
    """
    Smart question endpoint for simple natural-language requests.
    Examples:
      - total warnings
      - all warnings
      - last 4 days
      - 48 hours
    """
    try:
        query_engine = get_query_engine()
        payload = query_engine.answer_question(
            question=query,
            hours_back=hours_back,
            warning_type=warning_type,
            priority=priority,
            area=area,
            source=source,
            limit=limit,
            offset=offset,
        )

        response_payload = {
            "status": "success",
            **payload,
        }

        if not include_geojson:
            response_payload.pop("geojson", None)

        return JSONResponse(response_payload)

    except Exception as e:
        logger.exception("Error in /api/warnings/ask")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500,
        )

@app.get("/api/warnings/type/{warning_type}")
async def get_warnings_by_type(
    warning_type: str,
    hours_back: int = Query(24, ge=1, le=720),
    limit: int = Query(100),
) -> JSONResponse:
    """Get warnings by type"""
    try:
        query_engine = get_query_engine()
        warnings = query_engine.query_by_type(warning_type, hours_back)[:limit]
        
        results = query_engine.format_results(warnings)
        
        return JSONResponse({
            "status": "success",
            "count": len(results),
            "warning_type": warning_type,
            "data": results,
        })
    
    except Exception as e:
        logger.error(f"✗ Error in /api/warnings/type: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

@app.get("/api/warnings/priority/{priority}")
async def get_warnings_by_priority(
    priority: str,
    hours_back: int = Query(24),
    limit: int = Query(100),
) -> JSONResponse:
    """Get warnings by priority (high, medium, low)"""
    try:
        query_engine = get_query_engine()
        warnings = query_engine.query_by_priority(priority, hours_back)[:limit]
        
        results = query_engine.format_results(warnings)
        
        return JSONResponse({
            "status": "success",
            "count": len(results),
            "priority": priority,
            "data": results,
        })
    
    except Exception as e:
        logger.error(f"✗ Error in /api/warnings/priority: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

@app.get("/api/warnings/coastal")
async def get_coastal_warnings(
    hours_back: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
) -> JSONResponse:
    """Get warnings scraped from the coastal warnings source."""
    try:
        query_engine = get_query_engine()
        warnings = query_engine.query_coastal_warnings(hours_back=hours_back, limit=limit)
        results = query_engine.format_results(warnings)

        return JSONResponse({
            "status": "success",
            "source": "coastal",
            "count": len(results),
            "hours_back": hours_back,
            "data": results,
        })

    except Exception as e:
        logger.error(f"Error in /api/warnings/coastal: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

@app.get("/api/warnings/navarea")
async def get_navarea_warnings(
    hours_back: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
) -> JSONResponse:
    """Get warnings scraped from the NAVAREA source."""
    try:
        query_engine = get_query_engine()
        warnings = query_engine.query_navarea_warnings(hours_back=hours_back, limit=limit)
        results = query_engine.format_results(warnings)

        return JSONResponse({
            "status": "success",
            "source": "navarea",
            "count": len(results),
            "hours_back": hours_back,
            "data": results,
        })

    except Exception as e:
        logger.error(f"Error in /api/warnings/navarea: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

# ============================================================================
# GEOJSON ENDPOINTS
# ============================================================================

@app.get("/api/geojson/live")
async def get_geojson_live(
    hours_back: int = Query(24),
) -> JSONResponse:
    """Get latest warnings as GeoJSON"""
    try:
        query_engine = get_query_engine()
        warnings = query_engine.query_last_hours(hours_back)
        
        geojson = query_engine.format_as_geojson(warnings)
        
        return JSONResponse({
            "status": "success",
            "count": len(geojson["features"]),
            "geojson": geojson,
        })
    
    except Exception as e:
        logger.error(f"✗ Error in /api/geojson/live: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@app.get("/api/statistics")
async def get_statistics(
    hours_back: int = Query(24),
) -> JSONResponse:
    """Get warning statistics"""
    try:
        query_engine = get_query_engine()
        stats = query_engine.get_statistics(hours_back)
        
        return JSONResponse({
            "status": "success",
            "statistics": stats,
        })
    
    except Exception as e:
        logger.error(f"✗ Error in /api/statistics: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

# ============================================================================
# WEBSOCKET ENDPOINTS (REAL-TIME UPDATES)
# ============================================================================

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    WebSocket endpoint for real-time warning updates
    
    Broadcasts latest warnings to all connected clients
    """
    if not ENABLE_WEBSOCKET:
        await websocket.close(code=1000, reason="WebSocket disabled")
        return
    
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive ping or other messages from client
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
            
            # Echo response
            await websocket.send_json({
                "type": "ping_response",
                "timestamp": datetime.utcnow().isoformat(),
            })
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await manager.disconnect(websocket)


async def broadcast_new_warnings(warnings: List[dict]):
    """Broadcast new warnings to all connected clients"""
    if not ENABLE_WEBSOCKET or not manager.active_connections:
        return
    
    message = {
        "type": "new_warnings",
        "timestamp": datetime.utcnow().isoformat(),
        "count": len(warnings),
        "warnings": warnings,
    }
    
    await manager.broadcast(message)

# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@app.post("/api/admin/refresh")
async def refresh_warnings() -> JSONResponse:
    """
    Manually trigger warning refresh
    
    Scrapes latest warnings and updates database
    """
    try:
        logger.info("🔄 Manual refresh triggered")
        
        # Scrape
        warnings = scrape_pakistan_navarea()
        if not warnings:
            return JSONResponse(
                {"status": "error", "message": "Failed to scrape warnings"},
                status_code=500
            )
        
        # Parse
        parsed = parse_navarea_warnings(warnings)
        
        # Process GIS
        gis_processed = process_warnings_for_gis(parsed)
        
        # Insert
        db = get_database()
        inserted, skipped = db.insert_batch(gis_processed)
        
        logger.info(f"✓ Refresh complete: {inserted} inserted, {skipped} skipped")
        
        # Broadcast to WebSocket clients
        await broadcast_new_warnings(gis_processed[:10])  # Broadcast first 10
        
        return JSONResponse({
            "status": "success",
            "inserted": inserted,
            "skipped": skipped,
        })
    
    except Exception as e:
        logger.error(f"✗ Error in refresh: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

@app.get("/api/admin/export")
async def export_warnings() -> FileResponse:
    """Export warnings to CSV"""
    try:
        db = get_database()
        csv_path = db.export_to_csv()
        
        if not csv_path:
            return JSONResponse(
                {"status": "error", "message": "CSV export failed"},
                status_code=500,
            )

        return FileResponse(
            path=csv_path,
            filename="navarea_warnings.csv",
            media_type="text/csv",
        )
    
    except Exception as e:
        logger.error(f"✗ Error exporting: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """API information endpoint"""
    return {
        "name": "Pakistan NAVAREA IX GIS Real-Time Agent",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "warnings": {
                "live": "/api/warnings/live",
                "query": "/api/warnings/query",
                "coastal": "/api/warnings/coastal",
                "navarea": "/api/warnings/navarea",
                "by_type": "/api/warnings/type/{type}",
                "by_priority": "/api/warnings/priority/{priority}",
            },
            "geojson": {
                "live": "/api/geojson/live",
            },
            "statistics": "/api/statistics",
            "websocket": {
                "live": "ws://localhost:8000/ws/live",
            },
            "admin": {
                "refresh": "/api/admin/refresh (POST)",
                "export": "/api/admin/export (GET)",
            },
        },
        "docs": "/docs",
    }

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        {"status": "error", "message": "Internal server error"},
        status_code=500
    )

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level=LOG_LEVEL.lower(),
    )
