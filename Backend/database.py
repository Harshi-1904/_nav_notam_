"""
Database operations module for NAVAREA warnings
Handles CRUD operations, deduplication, and storage
"""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, desc, func
from loguru import logger
import csv

from models import (
    NavAreaWarning,
    Coordinate,
    Geometry,
    WarningMetadata,
    get_session_factory,
)
from config import (
    NO_DUPLICATES_MODE,
    APPEND_ONLY_MODE,
    BACKUP_CSV_PATH,
)


class WarningDatabase:
    """
    Database operations for NAVAREA warnings
    Handles insert, update, query, and deduplication
    """
    
    def __init__(self):
        self.SessionLocal = get_session_factory()
        logger.info("WarningDatabase initialized")
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    # ========================================================================
    # CREATE OPERATIONS
    # ========================================================================
    
    def insert_warning(self, warning: dict, session: Session = None) -> Optional[str]:
        """
        Insert a warning into the database
        
        Args:
            warning: Warning dictionary with parsed data
            session: Optional existing session
        
        Returns:
            Warning ID if successful, None otherwise
        """
        close_session = False
        if session is None:
            session = self.get_session()
            close_session = True
        
        try:
            warning_id = warning.get("warning_id")
            
            # Check for duplicates
            if NO_DUPLICATES_MODE:
                existing = session.query(NavAreaWarning).filter(
                    NavAreaWarning.warning_id == warning_id
                ).first()
                
                if existing:
                    logger.debug(f"Warning {warning_id} already exists, skipping")
                    return None
            
            # Create warning record
            db_warning = NavAreaWarning(
                warning_id=warning_id,
                date=warning.get("date", datetime.utcnow()),
                message=warning.get("message", ""),
                area=warning.get("area"),
                warning_type=warning.get("warning_type", "unknown"),
                priority=warning.get("priority", "medium"),
                source_url=warning.get("source_url"),
                source_html=warning.get("source_html"),
            )
            
            session.add(db_warning)
            session.flush()
            
            # Insert coordinates
            coordinates = warning.get("coordinates", [])
            for idx, coord in enumerate(coordinates):
                db_coord = Coordinate(
                    warning_id=warning_id,
                    latitude=coord.get("latitude"),
                    longitude=coord.get("longitude"),
                    coordinate_order=idx,
                    extraction_method=coord.get("extraction_method"),
                    confidence=coord.get("confidence", 1.0),
                )
                session.add(db_coord)
            
            # Insert geometry
            geometry = warning.get("geometry")
            if geometry:
                db_geometry = Geometry(
                    warning_id=warning_id,
                    geometry_type=geometry.get("geometry_type"),
                    geojson=geometry.get("geojson"),
                    wkt=geometry.get("wkt"),
                    area_sq_km=geometry.get("area_sq_km"),
                    buffer_distance=geometry.get("buffer_distance"),
                )
                session.add(db_geometry)
                db_warning.geometry_created = True
            
            # Insert metadata
            metadata = warning.get("metadata", {})
            if metadata:
                db_metadata = WarningMetadata(
                    warning_id=warning_id,
                    raw_text=warning.get("message"),
                    parsed_fields=metadata,
                    extraction_confidence=metadata.get("type_confidence", 1.0),
                )
                session.add(db_metadata)
            
            if coordinates:
                db_warning.coordinates_extracted = True
            
            session.commit()
            logger.info(f"✓ Inserted warning {warning_id}")
            return warning_id
        
        except Exception as e:
            session.rollback()
            logger.error(f"✗ Error inserting warning: {str(e)}")
            return None
        
        finally:
            if close_session:
                session.close()
    
    def insert_batch(self, warnings: List[dict], batch_size: int = 100) -> Tuple[int, int]:
        """
        Insert multiple warnings in batch
        
        Args:
            warnings: List of warning dictionaries
            batch_size: Number of records per commit
        
        Returns:
            (inserted_count, skipped_count) tuple
        """
        session = self.get_session()
        inserted_count = 0
        skipped_count = 0
        
        try:
            for i, warning in enumerate(warnings):
                result = self.insert_warning(warning, session)
                if result:
                    inserted_count += 1
                else:
                    skipped_count += 1
                
                # Batch commit
                if (i + 1) % batch_size == 0:
                    session.commit()
                    logger.debug(f"Batch committed: {i + 1} warnings processed")
            
            session.commit()
            logger.info(f"✓ Batch insert complete: {inserted_count} inserted, {skipped_count} skipped")
            return inserted_count, skipped_count
        
        except Exception as e:
            session.rollback()
            logger.error(f"✗ Batch insert failed: {str(e)}")
            return inserted_count, skipped_count
        
        finally:
            session.close()
    
    # ========================================================================
    # READ OPERATIONS
    # ========================================================================
    
    def get_warning_by_id(self, warning_id: str) -> Optional[NavAreaWarning]:
        """
        Get warning by ID
        
        Args:
            warning_id: Warning ID
        
        Returns:
            NavAreaWarning object or None
        """
        session = self.get_session()
        try:
            warning = session.query(NavAreaWarning).filter(
                NavAreaWarning.warning_id == warning_id
            ).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            ).first()
            return warning
        finally:
            session.close()
    
    def get_warnings_by_time_range(
        self,
        hours_back: int = 24,
        warning_type: Optional[str] = None,
        priority: Optional[str] = None,
        area: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NavAreaWarning]:
        """
        Get warnings within a time range with optional filters
        
        Args:
            hours_back: Hours to look back
            warning_type: Filter by warning type
            priority: Filter by priority
            area: Filter by area
            limit: Maximum results
            offset: Pagination offset
        
        Returns:
            List of NavAreaWarning objects
        """
        session = self.get_session()
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(hours=hours_back)
            
            query = session.query(NavAreaWarning).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            ).filter(
                NavAreaWarning.date >= cutoff_date
            )
            
            if warning_type:
                query = query.filter(NavAreaWarning.warning_type == warning_type)
            
            if priority:
                query = query.filter(NavAreaWarning.priority == priority)
            
            if area:
                query = query.filter(NavAreaWarning.area.ilike(f"%{area}%"))
            
            warnings = query.order_by(
                desc(NavAreaWarning.date)
            ).offset(offset).limit(limit).all()
            
            return warnings
        
        finally:
            session.close()
    
    def get_all_warnings(
        self,
        limit: int = 1000,
        offset: int = 0,
        order_by_date: bool = True,
    ) -> List[NavAreaWarning]:
        """
        Get all warnings with pagination
        
        Args:
            limit: Maximum results
            offset: Pagination offset
            order_by_date: Sort by date descending
        
        Returns:
            List of NavAreaWarning objects
        """
        session = self.get_session()
        
        try:
            query = session.query(NavAreaWarning).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            )
            
            if order_by_date:
                query = query.order_by(desc(NavAreaWarning.date))
            
            warnings = query.offset(offset).limit(limit).all()
            return warnings
        
        finally:
            session.close()
    
    def count_warnings(self, hours_back: Optional[int] = None) -> int:
        """
        Count total warnings, optionally within time range
        
        Args:
            hours_back: Optional hours to look back
        
        Returns:
            Warning count
        """
        session = self.get_session()
        
        try:
            query = session.query(NavAreaWarning)
            
            if hours_back:
                cutoff_date = datetime.utcnow() - timedelta(hours=hours_back)
                query = query.filter(NavAreaWarning.date >= cutoff_date)
            
            count = query.count()
            return count
        
        finally:
            session.close()
    
    def get_warnings_by_geometry_type(self, geometry_type: str) -> List[NavAreaWarning]:
        """
        Get warnings filtered by geometry type
        
        Args:
            geometry_type: POINT or POLYGON
        
        Returns:
            List of warnings with specified geometry type
        """
        session = self.get_session()
        
        try:
            warnings = session.query(NavAreaWarning).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            ).join(
                Geometry
            ).filter(
                Geometry.geometry_type == geometry_type
            ).all()
            
            return warnings
        
        finally:
            session.close()

    def get_warnings_by_source(
        self,
        source_keyword: str,
        hours_back: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NavAreaWarning]:
        """
        Get warnings filtered by source URL keyword.

        Args:
            source_keyword: Keyword to match in the source URL
            hours_back: Optional hours to look back
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of NavAreaWarning objects
        """
        session = self.get_session()

        try:
            query = session.query(NavAreaWarning).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            )

            if hours_back is not None:
                cutoff_date = datetime.utcnow() - timedelta(hours=hours_back)
                query = query.filter(NavAreaWarning.date >= cutoff_date)

            query = query.filter(
                NavAreaWarning.source_url.isnot(None),
                NavAreaWarning.source_url.ilike(f"%{source_keyword}%"),
            )

            warnings = query.order_by(
                desc(NavAreaWarning.date)
            ).offset(offset).limit(limit).all()

            return warnings

        finally:
            session.close()

    def search_warnings(
        self,
        search_text: str,
        hours_back: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NavAreaWarning]:
        """
        Search warnings by free text across common fields.
        """
        session = self.get_session()

        try:
            query = session.query(NavAreaWarning).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            )

            if hours_back is not None:
                cutoff_date = datetime.utcnow() - timedelta(hours=hours_back)
                query = query.filter(NavAreaWarning.date >= cutoff_date)

            normalized = " ".join((search_text or "").split())
            if not normalized:
                return []

            terms = [term for term in normalized.split(" ") if len(term) > 1]
            if not terms:
                terms = [normalized]

            for term in terms:
                pattern = f"%{term}%"
                query = query.filter(
                    or_(
                        NavAreaWarning.warning_id.ilike(pattern),
                        NavAreaWarning.message.ilike(pattern),
                        NavAreaWarning.area.ilike(pattern),
                        NavAreaWarning.warning_type.ilike(pattern),
                        NavAreaWarning.source_url.ilike(pattern),
                    )
                )

            warnings = query.order_by(
                desc(NavAreaWarning.date)
            ).offset(offset).limit(limit).all()

            return warnings

        finally:
            session.close()

    def advanced_search_warnings(
        self,
        search_text: Optional[str] = None,
        hours_back: Optional[int] = None,
        warning_type: Optional[str] = None,
        priority: Optional[str] = None,
        area: Optional[str] = None,
        source_keyword: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NavAreaWarning]:
        """
        Advanced search that combines text search with structured filters.
        """
        session = self.get_session()

        try:
            query = session.query(NavAreaWarning).options(
                selectinload(NavAreaWarning.coordinates),
                selectinload(NavAreaWarning.geometry),
                selectinload(NavAreaWarning.warning_metadata),
            )

            if hours_back is not None:
                cutoff_date = datetime.utcnow() - timedelta(hours=hours_back)
                query = query.filter(NavAreaWarning.date >= cutoff_date)

            if warning_type:
                query = query.filter(NavAreaWarning.warning_type == warning_type)

            if priority:
                query = query.filter(NavAreaWarning.priority == priority)

            if area:
                query = query.filter(NavAreaWarning.area.ilike(f"%{area}%"))

            if source_keyword:
                query = query.filter(
                    NavAreaWarning.source_url.isnot(None),
                    NavAreaWarning.source_url.ilike(f"%{source_keyword}%"),
                )

            normalized = " ".join((search_text or "").split())
            if normalized:
                terms = [term for term in normalized.split(" ") if len(term) > 1]
                if not terms:
                    terms = [normalized]

                for term in terms:
                    pattern = f"%{term}%"
                    query = query.filter(
                        or_(
                            NavAreaWarning.warning_id.ilike(pattern),
                            NavAreaWarning.message.ilike(pattern),
                            NavAreaWarning.area.ilike(pattern),
                            NavAreaWarning.warning_type.ilike(pattern),
                            NavAreaWarning.source_url.ilike(pattern),
                        )
                    )

            warnings = query.order_by(
                desc(NavAreaWarning.date)
            ).offset(offset).limit(limit).all()

            return warnings

        finally:
            session.close()
    
    # ========================================================================
    # UPDATE OPERATIONS
    # ========================================================================
    
    def update_warning_type(self, warning_id: str, warning_type: str) -> bool:
        """
        Update warning type
        
        Args:
            warning_id: Warning ID
            warning_type: New warning type
        
        Returns:
            True if successful
        """
        session = self.get_session()
        
        try:
            warning = session.query(NavAreaWarning).filter(
                NavAreaWarning.warning_id == warning_id
            ).first()
            
            if warning:
                warning.warning_type = warning_type
                session.commit()
                logger.info(f"✓ Updated warning type for {warning_id}")
                return True
            
            return False
        
        except Exception as e:
            session.rollback()
            logger.error(f"✗ Error updating warning type: {str(e)}")
            return False
        
        finally:
            session.close()
    
    # ========================================================================
    # DELETE OPERATIONS
    # ========================================================================
    
    def delete_warning(self, warning_id: str) -> bool:
        """
        Delete a warning and related records
        
        Args:
            warning_id: Warning ID
        
        Returns:
            True if successful
        """
        session = self.get_session()
        
        try:
            warning = session.query(NavAreaWarning).filter(
                NavAreaWarning.warning_id == warning_id
            ).first()
            
            if warning:
                session.delete(warning)
                session.commit()
                logger.info(f"✓ Deleted warning {warning_id}")
                return True
            
            return False
        
        except Exception as e:
            session.rollback()
            logger.error(f"✗ Error deleting warning: {str(e)}")
            return False
        
        finally:
            session.close()
    
    # ========================================================================
    # EXPORT OPERATIONS
    # ========================================================================
    
    def export_to_csv(self, output_path: str = None) -> Optional[str]:
        """
        Export all warnings to CSV
        
        Args:
            output_path: Path to save CSV (default from config)
        
        Returns:
            Output path if successful, None otherwise
        """
        if output_path is None:
            output_path = BACKUP_CSV_PATH
        
        session = self.get_session()
        
        try:
            warnings = session.query(NavAreaWarning).order_by(
                desc(NavAreaWarning.date)
            ).all()
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header
                writer.writerow([
                    'warning_id', 'date', 'message', 'area', 
                    'warning_type', 'priority', 'coordinates_extracted'
                ])
                
                # Data
                for warning in warnings:
                    coords = ', '.join([
                        f"({c.latitude},{c.longitude})" 
                        for c in warning.coordinates
                    ])
                    
                    writer.writerow([
                        warning.warning_id,
                        warning.date.isoformat(),
                        warning.message[:200],
                        warning.area,
                        warning.warning_type,
                        warning.priority,
                        coords,
                    ])
            
            logger.info(f"✓ Exported {len(warnings)} warnings to {output_path}")
            return str(output_path)
        
        except Exception as e:
            logger.error(f"✗ Error exporting to CSV: {str(e)}")
            return None
        
        finally:
            session.close()
    
    # ========================================================================
    # UTILITY OPERATIONS
    # ========================================================================
    
    def check_duplicate(self, warning_id: str) -> bool:
        """
        Check if warning already exists
        
        Args:
            warning_id: Warning ID
        
        Returns:
            True if exists
        """
        session = self.get_session()
        
        try:
            exists = session.query(NavAreaWarning).filter(
                NavAreaWarning.warning_id == warning_id
            ).first() is not None
            
            return exists
        
        finally:
            session.close()
    
    def get_statistics(self) -> dict:
        """
        Get database statistics
        
        Returns:
            Dictionary with statistics
        """
        session = self.get_session()
        
        try:
            total_warnings = session.query(NavAreaWarning).count()
            warnings_24h = session.query(NavAreaWarning).filter(
                NavAreaWarning.date >= datetime.utcnow() - timedelta(hours=24)
            ).count()
            
            type_counts = {}
            for result in session.query(
                NavAreaWarning.warning_type,
                func.count(NavAreaWarning.id)
            ).group_by(NavAreaWarning.warning_type).all():
                type_counts[result[0]] = result[1]
            
            priority_counts = {}
            for result in session.query(
                NavAreaWarning.priority,
                func.count(NavAreaWarning.id)
            ).group_by(NavAreaWarning.priority).all():
                priority_counts[result[0]] = result[1]
            
            return {
                "total_warnings": total_warnings,
                "warnings_24h": warnings_24h,
                "type_distribution": type_counts,
                "priority_distribution": priority_counts,
            }
        
        except Exception as e:
            logger.error(f"✗ Error getting statistics: {str(e)}")
            return {}
        
        finally:
            session.close()


# ============================================================================
# SINGLETON DATABASE INSTANCE
# ============================================================================

_db_instance = None


def get_database() -> WarningDatabase:
    """Get or create database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = WarningDatabase()
    return _db_instance
