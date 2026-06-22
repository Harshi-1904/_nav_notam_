# Pakistan NAVAREA IX GIS Real-Time Agent

## 🎯 Overview

A production-ready Python agent for collecting, parsing, and visualizing Pakistan Navy NAVAREA IX maritime warnings in real-time. The system features:

- **Web Scraper**: Automated collection from official sources
- **Parser**: Extract coordinates, classify warning types
- **GIS Processor**: Convert to map-ready geometries (POINT/POLYGON)
- **Database**: SQLite with append-only storage
- **API**: FastAPI with REST endpoints + WebSocket real-time updates
- **Independent Operation**: Can run standalone or integrate with other agents
- **Modular Design**: Easy to extend and integrate

---

## 📋 System Requirements

- **Python**: 3.9+
- **OS**: Windows, Linux, macOS
- **RAM**: 2GB minimum (4GB recommended)
- **Disk**: 500MB for data
- **Network**: Internet connection for scraping

---

## 🚀 Installation & Setup

### Step 1: Clone/Extract Files

Extract all files to a directory (e.g., `C:\navarea_agent` on Windows or `~/navarea_agent` on Linux):

```
navarea_agent/
├── config.py
├── models.py
├── scraper.py
├── parser.py
├── gis_processor.py
├── database.py
├── query_engine.py
├── api.py
├── main.py
├── requirements.txt
├── data/           (created automatically)
├── output/         (created automatically)
└── logs/           (created automatically)
```

### Step 2: Create Virtual Environment

**Windows (CMD):**
```bash
cd C:\navarea_agent
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
cd ~/navarea_agent
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `fastapi` + `uvicorn` - Web API framework
- `sqlalchemy` + `pydantic` - Database ORM & validation
- `requests` + `beautifulsoup4` - Web scraping
- `shapely` + `geopandas` - GIS operations
- `apscheduler` - Background task scheduling
- `loguru` - Advanced logging

**Expected installation time**: 2-5 minutes

---

## 🎮 Running the Agent

### Mode 1: Full Agent (Default)

Runs everything: initialization → historical backfill → live monitoring → API + WebSocket

```bash
python main.py --run --host 127.0.0.1 --port 8000
```

**Output:**
```
===================
Pakistan NAVAREA IX GIS Real-Time Agent
===================

🚀 INITIALIZATION PHASE

1️⃣  Initializing database...
   ✓ Database ready

2️⃣  Historical backfill...
   ✓ Inserted 150 historical warnings

3️⃣  Fetching initial warnings...
   ✓ Inserted 15 warnings

📊 INITIAL STATISTICS

   Total warnings: 165
   Last 24h: 47
   Types: {'hazard': 25, 'exercise': 15, ...}

✓ Initialization complete

⏰ SCHEDULER SETUP

   Interval: 60 seconds
   Timezone: UTC

✓ Scheduler started

🌐 API SERVER

   Host: 127.0.0.1
   Port: 8000
   Documentation: http://127.0.0.1:8000/docs
```

**Then in browser:**
- 🔗 API Docs: http://localhost:8000/docs
- 📊 API Root: http://localhost:8000/
- 🎯 Live warnings: http://localhost:8000/api/warnings/live

---

### Mode 2: API Only (No Background Monitoring)

```bash
python main.py --api --port 8000
```

Use this if:
- Running in production with separate monitoring
- Want to control updates manually
- Integrating with external scheduler

---

### Mode 3: Single Refresh (One-time scrape)

```bash
python main.py --refresh
```

Use this for:
- Testing the pipeline
- Manual updates
- Cron job integration

---

### Mode 4: Historical Backfill Only

```bash
python main.py --backfill
```

Use this for:
- Initial data loading
- Reprocessing historical data

---

## 📡 API Endpoints

Once running, access the full API at: **http://localhost:8000/docs**

### Core Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check |
| GET | `/api/warnings/live` | Latest warnings (default: 24h) |
| GET | `/api/warnings/query` | Natural language queries |
| GET | `/api/warnings/type/{type}` | Filter by warning type |
| GET | `/api/warnings/priority/{priority}` | Filter by priority |
| GET | `/api/geojson/live` | GeoJSON format for mapping |
| GET | `/api/statistics` | Warning statistics |
| POST | `/api/admin/refresh` | Manual data refresh |
| GET | `/api/admin/export` | Export to CSV |
| WS | `/ws/live` | Real-time WebSocket updates |

### Example Requests

**Get latest warnings (cURL):**
```bash
curl "http://localhost:8000/api/warnings/live?hours_back=24&limit=10"
```

**Response:**
```json
{
  "status": "success",
  "count": 10,
  "hours_back": 24,
  "data": [
    {
      "id": 1,
      "warning_id": "NAVAREA_1234",
      "date": "2026-06-18T10:30:00",
      "message": "EXERCISE: Naval firing exercise...",
      "type": "exercise",
      "priority": "medium",
      "color": "orange",
      "coordinates": [
        {"lat": 20.5, "lon": 65.3, "confidence": 0.95}
      ],
      "geometry": {
        "type": "POLYGON",
        "area_km2": 1250.5
      }
    }
  ]
}
```

**Get GeoJSON for mapping:**
```bash
curl "http://localhost:8000/api/geojson/live?hours_back=24"
```

**Natural language query:**
```bash
curl "http://localhost:8000/api/warnings/query?query=high%20priority"
```

---

## 🗺️ React Frontend Example

If building a React frontend:

```javascript
import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, Popup } from 'react-leaflet';

function NavAreaMap() {
  const [geojson, setGeojson] = useState(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/geojson/live?hours_back=24')
      .then(r => r.json())
      .then(data => setGeojson(data.geojson));
  }, []);

  return (
    <MapContainer center={[20, 65]} zoom={5} style={{ height: '100vh' }}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {geojson && <GeoJSON data={geojson} />}
    </MapContainer>
  );
}

export default NavAreaMap;
```

---

## 🗄️ Database

Database is automatically created at: `./data/navarea_master.db` (SQLite)

### Tables

| Table | Purpose |
|-------|---------|
| `navarea_warnings` | Main warning records |
| `coordinates` | Extracted lat/lon points |
| `geometries` | GIS geometries (POINT/POLYGON) |
| `warning_metadata` | Additional parsing metadata |

### Backup/Export

Export warnings to CSV:
```bash
curl -X GET "http://localhost:8000/api/admin/export" > warnings.csv
```

---

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Change source URL
PAKISTAN_NAVAREA_URL = "https://custom-source.com/warnings/"

# Change monitoring interval (seconds)
LIVE_MONITOR_INTERVAL = 60

# Change query defaults
DEFAULT_QUERY_RANGE = 24  # hours

# Change API host/port
API_HOST = "0.0.0.0"  # 0.0.0.0 to allow external connections
API_PORT = 8000
```

---

## 🔧 Development & Integration

### Running Tests

```bash
# Test database
python -c "from models import init_db; init_db(); print('✓ DB OK')"

# Test scraper
python -c "from scraper import scrape_pakistan_navarea; print(scrape_pakistan_navarea())"

# Test parser
from parser import parse_navarea_warnings
warnings = parse_navarea_warnings([...])

# Test API
python main.py --api
# Then: curl http://localhost:8000/health
```

### Integrating with Other Agents

The agent is modular and can be imported:

```python
from scraper import scrape_pakistan_navarea
from parser import parse_navarea_warnings
from gis_processor import process_warnings_for_gis
from database import get_database

# Collect data
warnings = scrape_pakistan_navarea()

# Parse
parsed = parse_navarea_warnings(warnings)

# Process
gis = process_warnings_for_gis(parsed)

# Store
db = get_database()
db.insert_batch(gis)

# Query
from query_engine import get_query_engine
engine = get_query_engine()
recent = engine.query_last_hours(24)
```

### Custom Plugins

Extend the system:

```python
# custom_processor.py
from gis_processor import GISProcessor

class CustomProcessor(GISProcessor):
    def custom_method(self, warnings):
        # Your logic here
        return processed_warnings
```

---

## 📊 Monitoring & Logs

Logs are saved to: `./logs/navarea_YYYYMMDD.log`

**View logs in real-time:**
```bash
tail -f logs/navarea_*.log
```

**Example log output:**
```
2026-06-18 10:30:45 | INFO     | scraper.py:45 | ✓ Fetched https://... - Status: 200
2026-06-18 10:30:46 | INFO     | parser.py:102 | Extracted coordinate: 20.5, 65.3 (dms)
2026-06-18 10:30:47 | INFO     | database.py:89 | ✓ Inserted warning NAVAREA_1234
```

---

## 🐛 Troubleshooting

### Issue: Database locked

**Solution:**
```bash
# Remove old database and reinitialize
rm data/navarea_master.db
python main.py --refresh
```

### Issue: Import errors

**Solution:**
```bash
pip install --upgrade -r requirements.txt
```

### Issue: API won't start on port 8000

**Solution:**
```bash
# Use different port
python main.py --port 8888

# Or kill process using port 8000 (Linux/macOS):
lsof -ti:8000 | xargs kill -9
```

### Issue: Scraper returns no data

**Check:**
1. Internet connection
2. Website still live (try in browser)
3. Logs for detailed error messages
4. Try manual test:
```python
from scraper import NavAreaScraper
scraper = NavAreaScraper()
html = scraper.fetch_page("https://hydrography.paknavy.gov.pk/navarea-ix-warnings/")
print(html[:500])
```

---

## 🎯 Typical Workflow

1. **Start agent:**
   ```bash
   python main.py --run
   ```

2. **Wait for initialization** (1-2 minutes for backfill)

3. **Access API** in browser:
   ```
   http://localhost:8000/docs
   ```

4. **Query warnings:**
   ```bash
   curl "http://localhost:8000/api/warnings/live"
   ```

5. **Watch live updates** - Agent updates every 60 seconds

6. **Export data when needed:**
   ```bash
   curl "http://localhost:8000/api/admin/export" > warnings.csv
   ```

---

## 📈 Performance Notes

- **Startup time**: ~30 seconds to 2 minutes (backfill)
- **Update cycle**: ~10-20 seconds
- **Database size**: ~10-50MB per 10,000 warnings
- **Memory usage**: 100-300MB typical
- **Concurrent users**: Handle 50+ via WebSocket

---

## 🔒 Production Deployment

For production:

1. **Set proper host:**
   ```python
   # config.py
   API_HOST = "0.0.0.0"  # Listen on all interfaces
   API_PORT = 8000
   ```

2. **Use reverse proxy** (Nginx/Apache)

3. **Set environment variables:**
   ```bash
   export API_HOST="0.0.0.0"
   export API_PORT="8000"
   export LOG_LEVEL="INFO"
   ```

4. **Use supervisor/systemd** for process management

5. **Enable authentication** if exposing publicly

---

## 📞 Support

- Check logs: `logs/navarea_*.log`
- Test endpoints: `/health` endpoint
- Review API docs: `http://localhost:8000/docs`
- Check database: `data/navarea_master.db` (use SQLite browser)

---

## 📄 License

This agent is provided as-is for maritime intelligence purposes.

---

**Created**: June 2026  
**Framework**: Python 3.9+, FastAPI, SQLAlchemy, Shapely, GeoDataFrame
