"""
Main entry point for Pakistan NAVAREA IX GIS Real-Time Agent
Orchestrates all components: scraper, parser, GIS, database, and API
"""

import asyncio
import sys
from typing import List
from datetime import datetime, timedelta
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    LOG_FILE,
    LOG_LEVEL,
    ENABLE_HISTORICAL_BACKFILL,
    ENABLE_LIVE_MONITORING,
    LIVE_MONITOR_INTERVAL,
    SCHEDULER_ENABLED,
    SCHEDULER_TIMEZONE,
)
from models import init_db
from scraper import scrape_pakistan_navarea, backfill_pakistan_navarea
from parser import parse_navarea_warnings
from gis_processor import process_warnings_for_gis
from database import get_database
from api import app
import uvicorn

# ============================================================================
# LOGGING SETUP
# ============================================================================

logger.remove()
logger.add(
    LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {function}:{line} | {message}",
    level=LOG_LEVEL,
    rotation="00:00",  # Rotate at midnight
    retention="7 days",
)
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}:{line}</cyan> | {message}",
    level=LOG_LEVEL,
    colorize=True,
)

# ============================================================================
# AGENT CLASS
# ============================================================================

class NavAreaAgent:
    """
    Pakistan NAVAREA IX GIS Real-Time Agent
    Coordinates all components for real-time maritime intelligence
    """
    
    def __init__(self):
        self.db = get_database()
        self.scheduler = None
        self.last_update = None
        
        logger.info("=" * 70)
        logger.info("Pakistan NAVAREA IX GIS Real-Time Agent")
        logger.info("=" * 70)
    
    async def initialize(self):
        """Initialize agent components"""
        logger.info("\n🚀 INITIALIZATION PHASE\n")
        
        # Initialize database
        logger.info("1️⃣  Initializing database...")
        try:
            init_db()
            logger.info("   ✓ Database ready")
        except Exception as e:
            logger.error(f"   ✗ Database initialization failed: {str(e)}")
            return False
        
        # Perform historical backfill
        if ENABLE_HISTORICAL_BACKFILL:
            logger.info("2️⃣  Historical backfill...")
            try:
                warnings = await backfill_pakistan_navarea()
                if warnings:
                    parsed = parse_navarea_warnings(warnings)
                    gis_processed = process_warnings_for_gis(parsed)
                    inserted, skipped = self.db.insert_batch(gis_processed)
                    logger.info(f"   ✓ Inserted {inserted} historical warnings")
                else:
                    logger.warning("   ⚠ No historical warnings found")
            except Exception as e:
                logger.error(f"   ✗ Backfill error: {str(e)}")
        
        # Get initial data
        logger.info("3️⃣  Fetching initial warnings...")
        try:
            warnings = scrape_pakistan_navarea()
            if warnings:
                parsed = parse_navarea_warnings(warnings)
                gis_processed = process_warnings_for_gis(parsed)
                inserted, skipped = self.db.insert_batch(gis_processed)
                logger.info(f"   ✓ Inserted {inserted} warnings")
                self.last_update = datetime.utcnow()
            else:
                logger.warning("   ⚠ No warnings scraped")
        except Exception as e:
            logger.error(f"   ✗ Scraping error: {str(e)}")
        
        # Show statistics
        logger.info("\n📊 INITIAL STATISTICS\n")
        try:
            stats = self.db.get_statistics()
            logger.info(f"   Total warnings: {stats.get('total_warnings', 0)}")
            logger.info(f"   Last 24h: {stats.get('warnings_24h', 0)}")
            logger.info(f"   Types: {stats.get('type_distribution', {})}")
            logger.info(f"   Priorities: {stats.get('priority_distribution', {})}")
        except Exception as e:
            logger.warning(f"   Could not get statistics: {str(e)}")
        
        logger.info("\n✓ Initialization complete\n")
        return True
    
    async def update_warnings(self):
        """Update warnings from source"""
        logger.info(f"\n🔄 UPDATE CYCLE - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        try:
            # Scrape latest
            logger.info("   Scraping...")
            warnings = scrape_pakistan_navarea()
            
            if not warnings:
                logger.info("   No new warnings")
                return
            
            logger.info(f"   Found {len(warnings)} warnings")
            
            # Parse
            logger.info("   Parsing...")
            parsed = parse_navarea_warnings(warnings)
            
            # GIS processing
            logger.info("   GIS processing...")
            gis_processed = process_warnings_for_gis(parsed)
            
            # Insert
            logger.info("   Inserting...")
            inserted, skipped = self.db.insert_batch(gis_processed)
            
            logger.info(f"   ✓ Inserted {inserted}, skipped {skipped} (duplicates)")
            
            self.last_update = datetime.utcnow()
        
        except Exception as e:
            logger.error(f"   ✗ Update error: {str(e)}")
    
    async def report_status(self):
        """Log current status"""
        try:
            total = self.db.count_warnings()
            last_24h = self.db.count_warnings(24)
            
            logger.info(f"\n📊 STATUS - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"   Total warnings: {total}")
            logger.info(f"   Last 24h: {last_24h}")
            logger.info(f"   Last update: {self.last_update}")
            logger.info()
        
        except Exception as e:
            logger.warning(f"Could not get status: {str(e)}")
    
    def setup_scheduler(self):
        """Setup APScheduler for live monitoring"""
        if not SCHEDULER_ENABLED or not ENABLE_LIVE_MONITORING:
            logger.info("⏸️  Live monitoring disabled")
            return False
        
        logger.info(f"\n⏰ SCHEDULER SETUP\n")
        logger.info(f"   Interval: {LIVE_MONITOR_INTERVAL} seconds")
        logger.info(f"   Timezone: {SCHEDULER_TIMEZONE}\n")
        
        self.scheduler = AsyncIOScheduler(timezone=SCHEDULER_TIMEZONE)
        
        # Add jobs
        self.scheduler.add_job(
            self.update_warnings,
            IntervalTrigger(seconds=LIVE_MONITOR_INTERVAL),
            id="update_warnings",
            name="Update warnings from source",
            replace_existing=True,
        )
        
        self.scheduler.add_job(
            self.report_status,
            IntervalTrigger(minutes=5),
            id="report_status",
            name="Report status",
            replace_existing=True,
        )
        
        try:
            self.scheduler.start()
            logger.info("✓ Scheduler started")
            return True
        except Exception as e:
            logger.error(f"✗ Scheduler error: {str(e)}")
            return False
    
    async def run_api(self, host: str = "127.0.0.1", port: int = 8000):
        """Run FastAPI server"""
        logger.info(f"\n🌐 API SERVER\n")
        logger.info(f"   Host: {host}")
        logger.info(f"   Port: {port}")
        logger.info(f"   Documentation: http://{host}:{port}/docs\n")
        
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info",
        )
        
        server = uvicorn.Server(config)
        await server.serve()
    
    async def run(self, api_host: str = "127.0.0.1", api_port: int = 8000):
        """Run agent in full mode (initialization + live monitoring + API)"""
        
        # Initialize
        success = await self.initialize()
        if not success:
            logger.error("Initialization failed, exiting")
            return
        
        # Setup scheduler
        scheduler_ok = self.setup_scheduler()
        
        # Run API
        logger.info(f"\n▶️  RUNNING AGENT\n")
        
        try:
            if scheduler_ok:
                # Run API with background scheduler
                await self.run_api(api_host, api_port)
            else:
                # Run API only
                logger.warning("Running API only (scheduler unavailable)")
                await self.run_api(api_host, api_port)
        
        except KeyboardInterrupt:
            logger.info("\n\n🛑 Shutdown signal received")
        
        finally:
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("✓ Scheduler stopped")

# ============================================================================
# CLI INTERFACE
# ============================================================================

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Pakistan NAVAREA IX GIS Real-Time Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --run              # Run full agent with API and monitoring
  python main.py --backfill         # Perform historical backfill only
  python main.py --api              # Run API only (no monitoring)
  python main.py --refresh          # Single refresh and exit
        """,
    )
    
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run full agent (default)",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run API server only",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Perform historical backfill",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Single refresh and exit",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="API host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API port (default: 8000)",
    )
    
    args = parser.parse_args()
    
    agent = NavAreaAgent()
    
    if args.backfill:
        logger.info("🔄 Historical backfill mode\n")
        init_db()
        warnings = await backfill_pakistan_navarea()
        parsed = parse_navarea_warnings(warnings)
        gis_processed = process_warnings_for_gis(parsed)
        inserted, skipped = agent.db.insert_batch(gis_processed)
        logger.info(f"✓ Inserted {inserted} warnings, skipped {skipped}\n")
    
    elif args.refresh:
        logger.info("🔄 Single refresh mode\n")
        init_db()
        warnings = scrape_pakistan_navarea()
        parsed = parse_navarea_warnings(warnings)
        gis_processed = process_warnings_for_gis(parsed)
        inserted, skipped = agent.db.insert_batch(gis_processed)
        logger.info(f"✓ Inserted {inserted} warnings, skipped {skipped}\n")
    
    elif args.api:
        logger.info("🌐 API server mode (no background monitoring)\n")
        init_db()
        await agent.run_api(args.host, args.port)
    
    else:
        # Default: run full agent
        await agent.run(args.host, args.port)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n🛑 Agent stopped by user\n")
    except Exception as e:
        logger.error(f"\n\n✗ Fatal error: {str(e)}\n")
        sys.exit(1)
