# Pakistan NAVAREA IX - Backend + Frontend Integration Guide 🚢

Complete guide for running both FastAPI backend and Streamlit frontend together

---

## 🎯 Overview

The system consists of two components:
- **Backend** (FastAPI): Handles data scraping, parsing, GIS processing, and API
- **Frontend** (Streamlit): Interactive dashboard for visualization and querying

---

## 🚀 Quick Start (Both Services)

### Windows - One Command

Create `start_all.bat`:
```batch
@echo off
title Pakistan NAVAREA IX - Full Stack
start cmd /k "python main.py --run --port 8000"
timeout /t 3 /nobreak
start cmd /k "cd streamlit_frontend && run_streamlit.bat"
```

Run:
```bash
start_all.bat
```

### Linux/macOS - One Command

Create `start_all.sh`:
```bash
#!/bin/bash
# Start backend
python main.py --run --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
cd streamlit_frontend
./run_streamlit.sh

# Cleanup on exit
trap "kill $BACKEND_PID" EXIT
```

Run:
```bash
chmod +x start_all.sh
./start_all.sh
```

---

## 📋 Manual Startup (Two Terminals)

### Terminal 1: Start Backend

```bash
# Navigate to backend directory
cd navarea_agent

# Run with full features (recommended)
python main.py --run --host 127.0.0.1 --port 8000

# Or just API without monitoring
python main.py --api --port 8000

# Or single refresh only
python main.py --refresh
```

### Terminal 2: Start Frontend

```bash
# Navigate to frontend directory
cd streamlit_frontend

# Windows
run_streamlit.bat

# Linux/macOS
./run_streamlit.sh

# Or manually
streamlit run streamlit_app.py --server.port 8501
```

---

## 🌐 Access Points

Once both are running:

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:8501 | Main dashboard |
| Backend API | http://localhost:8000 | REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| API Redoc | http://localhost:8000/redoc | ReDoc |
| Health Check | http://localhost:8000/health | API status |

---

## ⚙️ Configuration

### Backend Settings

Edit `navarea_agent/config.py`:

```python
# Live monitoring interval
LIVE_MONITOR_INTERVAL = 60  # seconds

# Database location
DATABASE_PATH = Path("./data/navarea_master.db")

# API settings
API_HOST = "127.0.0.1"
API_PORT = 8000
```

### Frontend Settings

Edit `streamlit_frontend/.streamlit/secrets.toml`:

```toml
# Backend API URL
api_url = "http://localhost:8000"

# Refresh interval
refresh_interval = 60
```

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Streamlit Frontend (8501)                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Dashboard │ Map │ Query │ Stats │ Data Table       │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ▼                                   │
│                   REST API Calls                            │
│                          ▼                                   │
├─────────────────────────────────────────────────────────────┤
│                  FastAPI Backend (8000)                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /api/warnings/live    ◄─ Scraper                   │  │
│  │  /api/statistics       ◄─ Parser                    │  │
│  │  /api/geojson/live     ◄─ GIS Processor             │  │
│  │  /api/admin/refresh    ◄─ Database                  │  │
│  │  /ws/live              ◄─ Query Engine              │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ▼                                   │
├─────────────────────────────────────────────────────────────┤
│                  SQLite Database                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ navarea_warnings │ coordinates │ geometries │ ...    │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ▼                                   │
├─────────────────────────────────────────────────────────────┤
│              External Data Sources                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Pakistan Navy │ NAVAREA IX │ Coastal Warnings        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow

1. **Backend Scraping** (every 60 seconds):
   - Fetch from Pakistan Navy sources
   - Parse warnings, extract coordinates
   - Create GIS geometries
   - Store in SQLite

2. **Frontend Request** (user interaction):
   - User opens dashboard
   - Streamlit calls backend API
   - Backend queries database
   - Returns JSON data
   - Frontend renders visualizations

3. **Real-time Updates**:
   - User clicks "Refresh Data"
   - Frontend calls `/api/admin/refresh`
   - Backend triggers scraper immediately
   - Results returned to frontend

---

## 🐳 Docker Deployment

### Single Container with Both Services

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy everything
COPY . .

# Install dependencies
RUN pip install -r requirements.txt
RUN pip install -r streamlit_frontend/streamlit_requirements.txt

# Expose ports
EXPOSE 8000 8501

# Start script
COPY start_services.sh .
RUN chmod +x start_services.sh

CMD ["./start_services.sh"]
```

Create `start_services.sh`:
```bash
#!/bin/bash
# Start backend in background
python main.py --run --host 0.0.0.0 --port 8000 &

# Wait for backend
sleep 5

# Start frontend
cd streamlit_frontend
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

Build and run:
```bash
docker build -t navarea-gis .
docker run -p 8000:8000 -p 8501:8501 navarea-gis
```

### Docker Compose (Separate Containers)

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "8501:8501"
    depends_on:
      - backend
    environment:
      - API_URL=http://backend:8000
    volumes:
      - ./streamlit_frontend/.streamlit:/app/.streamlit

networks:
  default:
    driver: bridge
```

Run:
```bash
docker-compose up -d
```

---

## 🚀 Production Deployment

### Using Supervisor (Linux/macOS)

Create `/etc/supervisor/conf.d/navarea.conf`:
```ini
[program:navarea-backend]
directory=/home/user/navarea_agent
command=python main.py --run --host 0.0.0.0 --port 8000
autostart=true
autorestart=true
stderr_logfile=/var/log/navarea-backend.err.log
stdout_logfile=/var/log/navarea-backend.out.log

[program:navarea-frontend]
directory=/home/user/navarea_agent/streamlit_frontend
command=streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
autostart=true
autorestart=true
stderr_logfile=/var/log/navarea-frontend.err.log
stdout_logfile=/var/log/navarea-frontend.out.log
```

Control:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start navarea-backend
sudo supervisorctl start navarea-frontend
```

### Using Nginx Reverse Proxy

Create `/etc/nginx/sites-available/navarea`:
```nginx
upstream backend {
    server 127.0.0.1:8000;
}

upstream frontend {
    server 127.0.0.1:8501;
}

server {
    listen 80;
    server_name navarea.example.com;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/navarea /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📈 Monitoring

### Backend Logs
```bash
tail -f logs/navarea_*.log
```

### Frontend Logs
```bash
streamlit run streamlit_app.py --logger.level=debug
```

### System Resources
```bash
# Monitor process memory
watch -n 1 'ps aux | grep -E "python|streamlit"'

# Monitor ports
netstat -tulpn | grep -E '8000|8501'
```

---

## 🔐 Security Checklist

- [ ] Change `API_HOST` to `0.0.0.0` only if using firewall
- [ ] Enable HTTPS with Let's Encrypt
- [ ] Add authentication to API endpoints
- [ ] Configure CORS properly
- [ ] Use environment variables for secrets
- [ ] Enable database backups
- [ ] Set up firewall rules
- [ ] Monitor API access logs
- [ ] Rate limit API endpoints
- [ ] Implement API key authentication

---

## 🐛 Troubleshooting

### "API Unavailable" in Frontend
```bash
# Check backend is running
curl http://localhost:8000/health

# Check port is open
netstat -tulpn | grep 8000

# Check firewall
sudo ufw allow 8000
```

### Frontend can't connect to backend (Docker)
```bash
# Use container hostname instead of localhost
# In docker-compose: http://backend:8000
# In secrets.toml: api_url = "http://backend:8000"
```

### Database locked error
```bash
# Remove lock file
rm data/navarea_master.db-shm
rm data/navarea_master.db-wal

# Or delete and recreate
rm data/navarea_master.db
python main.py --refresh
```

### Port already in use
```bash
# Kill process using port
# Linux/macOS:
lsof -ti:8000 | xargs kill -9

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

## 📊 Performance Tuning

### Backend
```python
# Increase batch size for faster inserts
BATCH_INSERT_SIZE = 500

# Increase worker threads
MAX_WORKERS_THREAD_POOL = 8

# Increase database pool
DATABASE_POOL_SIZE = 20
```

### Frontend
```python
# Increase cache TTL
@st.cache_data(ttl=120)

# Reduce data volume
LIMIT = 500  # Query fewer rows
```

---

## 📚 Integration Examples

### With External Monitoring
```python
import requests

api = "http://localhost:8000"
stats = requests.get(f"{api}/api/statistics").json()

if stats['high_priority_count'] > 10:
    send_alert("High activity detected!")
```

### With Slack Notifications
```python
import slack

def notify_high_priority_warning(warning):
    client = slack.WebClient(token=os.environ['SLACK_TOKEN'])
    client.chat_postMessage(
        channel='#navarea-alerts',
        text=f"⚠️ {warning['message']}"
    )
```

### With Email Alerts
```python
import smtplib

def email_alert(recipients, subject, body):
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('email@gmail.com', 'password')
    server.sendmail('email@gmail.com', recipients, ...)
```

---

## ✅ Verification Checklist

- [ ] Backend starts without errors
- [ ] Frontend loads at http://localhost:8501
- [ ] API responds at http://localhost:8000/health
- [ ] Dashboard displays warnings
- [ ] Map renders with markers
- [ ] Filters work correctly
- [ ] CSV export functions
- [ ] Refresh button updates data
- [ ] Query search works
- [ ] Statistics show correct counts

---

## 🎓 Next Steps

1. **Customize the dashboard**: Edit `streamlit_app.py`
2. **Add new API endpoints**: Extend `api.py`
3. **Deploy to production**: Use Docker or Nginx
4. **Setup monitoring**: Add alerting for critical warnings
5. **Integrate with external systems**: Slack, Email, etc.

---

**Status**: ✅ Both services production-ready

For questions, check individual README files in each service folder.
