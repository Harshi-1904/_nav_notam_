"""
Database models for Pakistan NAVAREA IX GIS Real-Time Agent
Defines the schema for storing warnings, coordinates, and metadata
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, 
    JSON, Text, Boolean, UniqueConstraint, Index, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from pydantic import BaseModel, Field
from config import (
    DATABASE_URL,
    DATABASE_POOL_SIZE,
    DATABASE_POOL_RECYCLE,
    get_database_path,
)

Base = declarative_base()

# ============================================================================
# DATABASE MODELS (SQLAlchemy ORM)
# ============================================================================

class NavAreaWarning(Base):
    """
    Main table for storing NAVAREA warnings
    """
    __tablename__ = "navarea_warnings"
    
    id = Column(Integer, primary_key=True, index=True)
    warning_id = Column(String(255), unique=True, nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    message = Column(Text, nullable=False)
    area = Column(String(255), nullable=True, index=True)
    warning_type = Column(String(50), default="unknown", nullable=False, index=True)
    priority = Column(String(20), default="medium", nullable=False, index=True)
    
    # Raw source data
    source_url = Column(String(500), nullable=True)
    source_html = Column(Text, nullable=True)
    
    # Processing metadata
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    coordinates_extracted = Column(Boolean, default=False)
    geometry_created = Column(Boolean, default=False)
    
    # Relationships
    coordinates = relationship(
        "Coordinate",
        back_populates="warning",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    geometry = relationship(
        "Geometry",
        back_populates="warning",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    warning_metadata = relationship(
        "WarningMetadata",
        back_populates="warning",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_warning_date_type', 'date', 'warning_type'),
        Index('idx_warning_area_date', 'area', 'date'),
    )
    
    def __repr__(self):
        return f"<NavAreaWarning(id={self.warning_id}, date={self.date}, type={self.warning_type})>"


class Coordinate(Base):
    """
    Table for storing extracted coordinates from warnings
    Supports multiple coordinates per warning (polygon scenarios)
    """
    __tablename__ = "coordinates"
    
    id = Column(Integer, primary_key=True, index=True)
    warning_id = Column(String(255), ForeignKey("navarea_warnings.warning_id"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    coordinate_order = Column(Integer, default=0)  # For polygon ordering
    extraction_method = Column(String(50), nullable=True)  # dms, dd, latlon, etc.
    confidence = Column(Float, default=1.0)  # 0.0 to 1.0
    
    # Relationship
    warning = relationship("NavAreaWarning", back_populates="coordinates")
    
    # Indexes
    __table_args__ = (
        Index('idx_coord_latlon', 'latitude', 'longitude'),
        UniqueConstraint('warning_id', 'coordinate_order', name='uq_warning_coord_order'),
    )
    
    def __repr__(self):
        return f"<Coordinate(lat={self.latitude}, lon={self.longitude})>"


class Geometry(Base):
    """
    Table for storing GIS geometries (POINT or POLYGON)
    """
    __tablename__ = "geometries"
    
    id = Column(Integer, primary_key=True, index=True)
    warning_id = Column(String(255), ForeignKey("navarea_warnings.warning_id"), unique=True, nullable=False, index=True)
    geometry_type = Column(String(20), nullable=False)  # POINT, POLYGON
    geojson = Column(JSON, nullable=False)  # GeoJSON representation
    wkt = Column(Text, nullable=True)  # Well-Known Text representation
    area_sq_km = Column(Float, nullable=True)  # For polygons
    buffer_distance = Column(Float, nullable=True)  # Buffer applied
    
    # Relationship
    warning = relationship("NavAreaWarning", back_populates="geometry")
    
    def __repr__(self):
        return f"<Geometry(type={self.geometry_type}, warning_id={self.warning_id})>"


class WarningMetadata(Base):
    """
    Table for storing additional metadata about warnings
    """
    __tablename__ = "warning_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    warning_id = Column(String(255), ForeignKey("navarea_warnings.warning_id"), unique=True, nullable=False)
    raw_text = Column(Text, nullable=True)
    parsed_fields = Column(JSON, nullable=True)
    extraction_confidence = Column(Float, default=1.0)
    notes = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    warning = relationship("NavAreaWarning", back_populates="warning_metadata")
    
    def __repr__(self):
        return f"<WarningMetadata(warning_id={self.warning_id})>"


# ============================================================================
# PYDANTIC MODELS (API Response/Request Schemas)
# ============================================================================

class CoordinateSchema(BaseModel):
    """Schema for coordinate data"""
    latitude: float
    longitude: float
    coordinate_order: int = 0
    extraction_method: Optional[str] = None
    confidence: float = 1.0
    
    class Config:
        from_attributes = True


class GeometrySchema(BaseModel):
    """Schema for geometry data"""
    geometry_type: str
    geojson: dict
    wkt: Optional[str] = None
    area_sq_km: Optional[float] = None
    
    class Config:
        from_attributes = True


class WarningMetadataSchema(BaseModel):
    """Schema for warning metadata"""
    raw_text: Optional[str] = None
    parsed_fields: Optional[dict] = None
    extraction_confidence: float = 1.0
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class NavAreaWarningSchema(BaseModel):
    """Schema for warning API responses"""
    id: int
    warning_id: str
    date: datetime
    message: str
    area: Optional[str] = None
    warning_type: str
    priority: str
    source_url: Optional[str] = None
    processed_at: datetime
    coordinates_extracted: bool
    geometry_created: bool
    coordinates: List[CoordinateSchema] = []
    geometry: Optional[GeometrySchema] = None
    metadata: Optional[WarningMetadataSchema] = None
    
    class Config:
        from_attributes = True


class WarningCreateSchema(BaseModel):
    """Schema for creating new warnings"""
    warning_id: str
    date: datetime
    message: str
    area: Optional[str] = None
    warning_type: str = "unknown"
    priority: str = "medium"
    source_url: Optional[str] = None
    source_html: Optional[str] = None


class WarningQuerySchema(BaseModel):
    """Schema for querying warnings"""
    hours_back: int = 24
    warning_type: Optional[str] = None
    priority: Optional[str] = None
    area: Optional[str] = None
    limit: int = 100
    offset: int = 0


# ============================================================================
# DATABASE ENGINE AND SESSION
# ============================================================================

def create_db_engine():
    """Create database engine with connection pooling"""
    return create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=DATABASE_POOL_SIZE,
        pool_recycle=DATABASE_POOL_RECYCLE,
        connect_args={"timeout": 15, "check_same_thread": False},  # SQLite specific
    )


def create_db_session(engine):
    """Create session factory"""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_database(engine):
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)


def _is_valid_sqlite_file(path: Path) -> bool:
    """Check whether a file looks like a valid SQLite database."""
    if not path.exists() or path.stat().st_size < 100:
        return True

    try:
        with path.open("rb") as handle:
            header = handle.read(16)
        return header == b"SQLite format 3\x00"
    except Exception:
        return False


def _backup_corrupted_database(path: Path) -> None:
    """Move a corrupted database file aside so a fresh one can be created."""
    if not path.exists():
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.stem}.corrupt_{timestamp}{path.suffix}")

    try:
        path.replace(backup_path)
        print(f"Existing database was invalid; moved to {backup_path}")
    except Exception:
        path.unlink(missing_ok=True)


# ============================================================================
# GLOBAL DATABASE INSTANCE
# ============================================================================

_engine = None
_SessionLocal = None


def get_engine():
    """Get or create database engine"""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory():
    """Get or create session factory"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = create_db_session(get_engine())
    return _SessionLocal


def get_db():
    """Get database session (for FastAPI dependency injection)"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database and create all tables"""
    db_path = get_database_path()
    if not _is_valid_sqlite_file(db_path):
        _backup_corrupted_database(db_path)

    engine = get_engine()
    try:
        init_database(engine)
    except Exception:
        # If SQLite still thinks the file is invalid, back it up and retry once.
        _backup_corrupted_database(db_path)
        init_database(engine)

    print(f"Database initialized at {DATABASE_URL}")
