# _nav_notam_

**Backend  commands**


1)cd Backend 

2)pip install -r requirements.txt

3).\run.bat     




**Frontend commands**

1)cd Frontend

2)pip install -r streamlit_requirements.txt

3).\run_streamlit.bat




**COMPLETE END-TO-END WORKFLOW CHART**

                    ┌──────────────────────────────┐
                    │   NAVAREA DATA SOURCES       │
                    │ (Pakistan Navy, Hydro sites)│
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        SCRAPER LAYER         │
                    │        (scraper.py)          │
                    │  • Fetch HTML               │
                    │  • Retry handling           │
                    │  • Deduplication            │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        PARSER LAYER          │
                    │        (parser.py)           │
                    │  • Extract coordinates       │
                    │  • Detect warning type       │
                    │  • Assign priority           │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │      GIS PROCESSOR           │
                    │     (gis_processor.py)       │
                    │  • POINT / POLYGON           │
                    │  • GeoJSON generation        │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        DATABASE LAYER        │
                    │   (SQLite + SQLAlchemy)     │
                    │  • warnings table            │
                    │  • coordinates table         │
                    │  • geometries table          │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       QUERY ENGINE           │
                    │     (query_engine.py)        │
                    │  • Filters (time/type)       │
                    │  • Natural language queries  │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        FASTAPI API           │
                    │        (api.py)              │
                    │                              │
                    │  GET /api/warnings/live      │
                    │  GET /api/statistics         │
                    │  GET /api/geojson/live       │
                    │  GET /api/warnings/query     │
                    │  POST /api/admin/refresh     │
                    └──────────────┬───────────────┘
                                   │
                     REST API (JSON / GeoJSON)
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     STREAMLIT FRONTEND       │
                    │    (streamlit_app.py)        │
                    │                              │
                    │  • API calls (requests)      │
                    │  • Data processing (pandas)  │
                    │                              │
                    │  VIEWS:                      │
                    │   • Dashboard                │
                    │   • Map (Folium)             │
                    │   • Query                    │
                    │   • Statistics               │
                    │   • Data Table               │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        VISUALIZATION         │
                    │                              │
                    │  • Map (GeoJSON → Folium)    │
                    │  • Charts (Plotly)           │
                    │  • Tables (Pandas)           │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │            USER              │
                    │   (Browser - Dashboard UI)   │
                    └──────────────────────────────┘
