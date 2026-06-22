"""
Example usage and testing for Pakistan NAVAREA IX GIS Real-Time Agent
Demonstrates how to use the agent programmatically
"""

import asyncio
from datetime import datetime
from scraper import scrape_pakistan_navarea, NavAreaScraper
from parser import parse_navarea_warnings, WarningTypeClassifier
from gis_processor import process_warnings_for_gis
from database import get_database
from query_engine import get_query_engine
from models import init_db


def example_1_basic_scraping():
    """Example 1: Basic web scraping"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Web Scraping")
    print("="*70 + "\n")
    
    print("Scraping Pakistan NAVAREA IX warnings...\n")
    warnings = scrape_pakistan_navarea()
    
    print(f"Found {len(warnings)} warnings\n")
    
    if warnings:
        print("First warning:")
        first = warnings[0]
        for key, value in first.items():
            if key != "source_html":  # Skip HTML
                print(f"  {key}: {value}")


def example_2_parsing():
    """Example 2: Parsing and classification"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Parsing & Classification")
    print("="*70 + "\n")
    
    # Sample warning text
    sample_warning = {
        "warning_id": "TEST_001",
        "date": datetime.utcnow(),
        "message": "EXERCISE: Naval live firing exercise ongoing in area 23°N 66°E to 24°N 67°E. Depth 150-200m. Avoid area.",
        "area": "NAVAREA_IX",
    }
    
    print(f"Sample warning: {sample_warning['message']}\n")
    
    # Parse it
    from parser import WarningParser
    parser = WarningParser()
    parsed = parser.parse_warning(sample_warning)
    
    print("Parsed result:")
    print(f"  Warning Type: {parsed['warning_type']}")
    print(f"  Priority: {parsed['priority']}")
    print(f"  Coordinates Found: {len(parsed['coordinates'])}")
    
    if parsed['coordinates']:
        for i, coord in enumerate(parsed['coordinates'], 1):
            print(f"    Coordinate {i}: {coord['latitude']}, {coord['longitude']}")
            print(f"      Method: {coord['extraction_method']}")
            print(f"      Confidence: {coord['confidence']}")


def example_3_gis_processing():
    """Example 3: GIS geometry creation"""
    print("\n" + "="*70)
    print("EXAMPLE 3: GIS Geometry Processing")
    print("="*70 + "\n")
    
    # Sample warning with coordinates
    sample_warning = {
        "warning_id": "TEST_GIS_001",
        "message": "Warning in area",
        "date": datetime.utcnow(),
        "coordinates": [
            {"latitude": 20.0, "longitude": 65.0, "extraction_method": "manual"},
            {"latitude": 21.0, "longitude": 66.0, "extraction_method": "manual"},
            {"latitude": 20.5, "longitude": 67.0, "extraction_method": "manual"},
        ]
    }
    
    print("Processing coordinates for GIS...\n")
    
    from gis_processor import GISProcessor
    processor = GISProcessor()
    processed = processor.process_warning_coordinates(sample_warning)
    
    if processed.get('geometry'):
        geom = processed['geometry']
        print(f"Geometry Type: {geom['geometry_type']}")
        if geom.get('area_sq_km'):
            print(f"Area: {geom['area_sq_km']} km²")
        print(f"GeoJSON: {geom['geojson']}")


def example_4_database_operations():
    """Example 4: Database operations"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Database Operations")
    print("="*70 + "\n")
    
    # Initialize database
    init_db()
    db = get_database()
    
    # Create sample warnings
    sample_warnings = [
        {
            "warning_id": f"DEMO_{i:04d}",
            "date": datetime.utcnow(),
            "message": f"Test warning {i}",
            "area": "IX",
            "warning_type": "exercise" if i % 2 == 0 else "hazard",
            "priority": "high" if i % 3 == 0 else "medium",
            "coordinates": [
                {
                    "latitude": 20.0 + i * 0.1,
                    "longitude": 65.0 + i * 0.1,
                    "extraction_method": "manual",
                    "confidence": 0.9,
                }
            ]
        }
        for i in range(5)
    ]
    
    print("Inserting sample warnings into database...\n")
    inserted, skipped = db.insert_batch(sample_warnings, batch_size=10)
    
    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}\n")
    
    # Query database
    print("Querying warnings...")
    all_warnings = db.get_all_warnings(limit=10)
    print(f"Total warnings in database: {db.count_warnings()}")
    print(f"Last 24 hours: {db.count_warnings(24)}\n")
    
    if all_warnings:
        print("Latest warnings:")
        for warning in all_warnings[:3]:
            print(f"  - {warning.warning_id}: {warning.message[:40]}...")


def example_5_querying():
    """Example 5: Query engine"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Query Engine")
    print("="*70 + "\n")
    
    engine = get_query_engine()
    
    # Query examples
    print("Query 1: Last 24 hours")
    warnings_24h = engine.query_last_hours(24)
    print(f"  Found: {len(warnings_24h)} warnings\n")
    
    print("Query 2: High priority")
    high_priority = engine.query_by_priority("high")
    print(f"  Found: {len(high_priority)} warnings\n")
    
    print("Query 3: By type - exercise")
    exercises = engine.query_by_type("exercise")
    print(f"  Found: {len(exercises)} warnings\n")
    
    # Statistics
    print("Statistics:")
    stats = engine.get_statistics(hours_back=24)
    print(f"  Total: {stats['total']}")
    print(f"  By Type: {stats['by_type']}")
    print(f"  By Priority: {stats['by_priority']}\n")


def example_6_full_pipeline():
    """Example 6: Full pipeline (scrape → parse → GIS → database)"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Full Pipeline")
    print("="*70 + "\n")
    
    init_db()
    
    print("Step 1: Scraping...")
    warnings = scrape_pakistan_navarea()
    print(f"  Scraped: {len(warnings)} warnings\n")
    
    if not warnings:
        print("  No warnings to process")
        return
    
    print("Step 2: Parsing...")
    parsed = parse_navarea_warnings(warnings)
    print(f"  Parsed: {len(parsed)} warnings\n")
    
    print("Step 3: GIS Processing...")
    gis_processed = process_warnings_for_gis(parsed)
    print(f"  Processed: {len(gis_processed)} warnings\n")
    
    print("Step 4: Database Insert...")
    db = get_database()
    inserted, skipped = db.insert_batch(gis_processed)
    print(f"  Inserted: {inserted}, Skipped: {skipped}\n")
    
    print("Pipeline complete!")


def example_7_geojson_export():
    """Example 7: GeoJSON export for mapping"""
    print("\n" + "="*70)
    print("EXAMPLE 7: GeoJSON Export")
    print("="*70 + "\n")
    
    engine = get_query_engine()
    warnings = engine.query_last_hours(24)
    
    print(f"Converting {len(warnings)} warnings to GeoJSON...\n")
    
    geojson = engine.format_as_geojson(warnings)
    
    print(f"GeoJSON FeatureCollection:")
    print(f"  Type: {geojson['type']}")
    print(f"  Features: {len(geojson['features'])}\n")
    
    if geojson['features']:
        print("First feature:")
        feature = geojson['features'][0]
        print(f"  ID: {feature['properties']['warning_id']}")
        print(f"  Type: {feature['properties']['warning_type']}")
        print(f"  Geometry: {feature['geometry']['type']}")


# ========================================================================
# MAIN
# ========================================================================

def main():
    """Run all examples"""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " Pakistan NAVAREA IX GIS Agent - Examples ".center(68) + "║")
    print("╚" + "="*68 + "╝")
    
    examples = [
        ("Basic Scraping", example_1_basic_scraping),
        ("Parsing & Classification", example_2_parsing),
        ("GIS Processing", example_3_gis_processing),
        ("Database Operations", example_4_database_operations),
        ("Query Engine", example_5_querying),
        ("Full Pipeline", example_6_full_pipeline),
        ("GeoJSON Export", example_7_geojson_export),
    ]
    
    while True:
        print("\n" + "="*70)
        print("Available Examples:")
        print("="*70)
        
        for i, (name, _) in enumerate(examples, 1):
            print(f"  {i}. {name}")
        
        print(f"  0. Exit")
        
        try:
            choice = int(input("\nSelect example (0-7): "))
            
            if choice == 0:
                print("\nExiting...\n")
                break
            
            if 1 <= choice <= len(examples):
                name, example_func = examples[choice - 1]
                print(f"\nRunning: {name}\n")
                
                try:
                    example_func()
                except Exception as e:
                    print(f"\n✗ Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
            else:
                print("Invalid choice")
        
        except KeyboardInterrupt:
            print("\n\nExiting...\n")
            break
        except ValueError:
            print("Please enter a valid number")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
