import os
import time
import sqlite3
import threading
import subprocess
import platform
import urllib.request
import urllib.error
from datetime import datetime
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

DB_PATH        = os.environ.get("DB_PATH", "netmon.db")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "10"))
PING_HOST      = os.environ.get("PING_HOST", "8.8.8.8")
PING_HOST2     = os.environ.get("PING_HOST2", "1.1.1.1")
HTTP_URL       = os.environ.get("HTTP_URL", "http://connectivitycheck.gstatic.com/generate_204")
HTTP_URL2      = os.environ.get("HTTP_URL2", "http://www.msftconnecttest.com/connecttest.txt")

# ---------- DB ----------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            status      TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            host        TEXT,
            latency_ms  REAL,
            note        TEXT,
            ping_ok     INTEGER,
            http_ok     INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            status      TEXT    NOT NULL,
            host        TEXT    NOT NULL,
            latency_ms  REAL,
            ping_ok     INTEGER,
            http_ok     INTEGER
        )
    """)
    # Migrate old tables that might not have new columns
    for col, typ in [("ping_ok", "INTEGER"), ("http_ok", "INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE events ADD COLUMN {col} {typ}")
        except Exception:
            pass
        try:
            conn.execute(f"ALTER TABLE checks ADD COLUMN {col} {typ}")
        except Exception:
            pass
    conn.commit()
    conn.close()

# ---------- Checks ----------

def ping_host(host):
    """Returns (ok: bool, latency_ms: float|None)"""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        start = time.time()
        result = subprocess.run(
            ["ping", param, "1", "-W", "2", host],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        elapsed = (time.time() - start) * 1000
        return result.returncode == 0, round(elapsed, 1)
    except Exception:
        return False, None

def http_check(url, timeout=5):
    """
    Returns (ok: bool, latency_ms: float|None).
    Considers HTTP 204 or any 2xx/3xx a success; what matters is
    that the internet routing actually delivered the packet.
    """
    try:
        start = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "netmon/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read(512)
        elapsed = (time.time() - start) * 1000
        return True, round(elapsed, 1)
    except urllib.error.HTTPError as e:
        # Even 4xx means we reached the server → internet is up
        elapsed = (time.time() - start) * 1000
        return (e.code < 500), round(elapsed, 1)
    except Exception:
        return False, None

# ---------- State ----------

state = {
    "status":         "unknown",
    "ping_ok":        None,
    "http_ok":        None,
    "last_check":     None,
    "last_up":        None,
    "last_down":      None,
    "latency_ms":     None,
    "http_latency_ms":None,
    "uptime_start":   None,
    "downtime_start": None,
    "check_count":    0,
    "up_count":       0,
}
state_lock = threading.Lock()

def record_event(status, host, latency_ms, note, ping_ok, http_ok):
    conn = get_db()
    conn.execute(
        "INSERT INTO events (status, timestamp, host, latency_ms, note, ping_ok, http_ok) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (status, datetime.utcnow().isoformat(), host, latency_ms, note, int(ping_ok), int(http_ok))
    )
    conn.commit()
    conn.close()

def record_check(status, host, latency_ms, ping_ok, http_ok):
    conn = get_db()
    conn.execute(
        "INSERT INTO checks (timestamp, status, host, latency_ms, ping_ok, http_ok) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), status, host, latency_ms, int(ping_ok), int(http_ok))
    )
    conn.execute("DELETE FROM checks WHERE id NOT IN (SELECT id FROM checks ORDER BY id DESC LIMIT 5000)")
    conn.commit()
    conn.close()

def monitor_loop():
    while True:
        # 1. Ping (LAN/router check)
        p1_ok, p1_lat = ping_host(PING_HOST)
        p2_ok, p2_lat = ping_host(PING_HOST2)
        ping_ok  = p1_ok or p2_ok
        ping_lat = p1_lat if p1_ok else p2_lat
        host_used = PING_HOST if p1_ok else PING_HOST2

        # 2. HTTP (real internet check)
        h1_ok, h1_lat = http_check(HTTP_URL)
        h2_ok = h2_lat = None
        if not h1_ok:
            h2_ok, h2_lat = http_check(HTTP_URL2)
        http_ok  = h1_ok or bool(h2_ok)
        http_lat = h1_lat if h1_ok else h2_lat

        # Network is UP only if BOTH ping and http succeed
        # (ping without http = router reachable but no internet)
        is_up = ping_ok and http_ok
        new_status = "up" if is_up else "down"
        now_iso = datetime.utcnow().isoformat()

        # Derive a human note for partial failures
        if ping_ok and not http_ok:
            note_detail = "ping_only"   # LAN OK, internet lost
        elif not ping_ok and http_ok:
            note_detail = "http_only"   # unusual but handle it
        else:
            note_detail = None

        with state_lock:
            prev_status = state["status"]
            state["check_count"]    += 1
            state["last_check"]      = now_iso
            state["latency_ms"]      = ping_lat
            state["http_latency_ms"] = http_lat
            state["status"]          = new_status
            state["ping_ok"]         = ping_ok
            state["http_ok"]         = http_ok
            state["note_detail"]     = note_detail

            if new_status == "up":
                state["up_count"] += 1
                state["last_up"]   = now_iso
                if prev_status != "up":
                    state["downtime_start"] = None
                    state["uptime_start"]   = now_iso
            else:
                state["last_down"] = now_iso
                if prev_status != "down":
                    state["uptime_start"]   = None
                    state["downtime_start"] = now_iso

        record_check(new_status, host_used, ping_lat, ping_ok, http_ok)

        if new_status != prev_status or prev_status == "unknown":
            if new_status == "up" and prev_status == "down":
                note = "Сеть восстановлена"
            elif new_status == "down" and prev_status == "up":
                if ping_ok and not http_ok:
                    note = "Интернет недоступен (роутер отвечает)"
                else:
                    note = "Сеть недоступна"
            else:
                note = "Мониторинг запущен"
            record_event(new_status, host_used, ping_lat, note, ping_ok, http_ok)

        time.sleep(CHECK_INTERVAL)

# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html",
        ping_host=PING_HOST, ping_host2=PING_HOST2,
        http_url=HTTP_URL,   http_url2=HTTP_URL2,
        check_interval=CHECK_INTERVAL)

@app.route("/api/status")
def api_status():
    with state_lock:
        s = dict(state)
    total = s["check_count"]
    s["uptime_pct"] = round(s["up_count"] / total * 100, 1) if total > 0 else None
    return jsonify(s)

@app.route("/api/events")
def api_events():
    limit = int(request.args.get("limit", 60))
    conn  = get_db()
    rows  = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/checks")
def api_checks():
    limit = int(request.args.get("limit", 200))
    conn  = get_db()
    rows  = conn.execute("SELECT * FROM checks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in reversed(rows)])

@app.route("/api/stats")
def api_stats():
    conn    = get_db()
    total   = conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
    up      = conn.execute("SELECT COUNT(*) FROM checks WHERE status='up'").fetchone()[0]
    avg_lat = conn.execute("SELECT AVG(latency_ms) FROM checks WHERE status='up'").fetchone()[0]
    avg_hlt = conn.execute("SELECT AVG(http_ok) FROM checks").fetchone()[0]
    outages = conn.execute("SELECT COUNT(*) FROM events WHERE status='down'").fetchone()[0]
    conn.close()
    return jsonify({
        "total_checks":    total,
        "up_checks":       up,
        "down_checks":     total - up,
        "uptime_pct":      round(up / total * 100, 2) if total > 0 else None,
        "avg_latency_ms":  round(avg_lat, 1) if avg_lat else None,
        "outages_count":   outages,
    })

if __name__ == "__main__":
    init_db()
    threading.Thread(target=monitor_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
