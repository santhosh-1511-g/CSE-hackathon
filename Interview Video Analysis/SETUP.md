# ProctorShield – Setup & Run Instructions

## Prerequisites

Install these on your machine **before** first run:

| Tool | Download Link |
|------|------|
| **Python 3.10+** | https://www.python.org/downloads/ |
| **Docker Desktop** | https://www.docker.com/products/docker-desktop/ |

> During Python installation, **check "Add Python to PATH"**.

---

## First-Time Setup (One-Time Only)

### 1. Install Python Dependencies

```bash
cd "Interview Video Analysis/backend"
pip install -r requirements.txt
```

### 2. Download NLTK Data (One-Time)

```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
```

---

## Running the Application

Every time you want to use the app, follow these 3 steps:

### Step 1 — Start Docker Desktop

Open **Docker Desktop** from the Start menu and wait until it shows "Engine Running" (green icon in system tray).

### Step 2 — Start MongoDB

```bash
cd "Interview Video Analysis/backend"
docker-compose up -d
```

You should see:
```
Container interview_mongo  Running
```

### Step 3 — Start the Backend Server

```bash
cd "Interview Video Analysis/backend"
python server.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
```

### Step 4 — Open in Browser

Go to: **http://127.0.0.1:5000**

---

## Stopping the Application

1. Press `Ctrl+C` in the terminal running the server
2. Stop MongoDB:
   ```bash
   cd "Interview Video Analysis/backend"
   docker-compose down
   ```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **"Database not available"** in Integrity Archive tab | Docker Desktop is not running, or MongoDB container is stopped. Run `docker-compose up -d` |
| **"ARCHIVE OFFLINE"** | The Flask backend server is not running. Start it with `python server.py` |
| **`pip install` fails** | Make sure Python is on your PATH. Try `py -m pip install -r requirements.txt` |
| **`docker-compose` not found** | Docker Desktop is not installed or not on PATH |
| **Port 5000 already in use** | Another process is using port 5000. Kill it or change the port in `server.py` |
