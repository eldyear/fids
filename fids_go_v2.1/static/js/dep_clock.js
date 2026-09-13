// ============================================================================
// FIDS Departures Clock — Sheremetyevo-style
//   - Analog clock with animated hands
//   - Ring of departures within the next hour (markers by minute)
//   - Aircraft radar using OpenSky Network via a Go proxy (/api/radar)
// ============================================================================
"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";

// Osh airport (OSS)
const AIRPORT = { lat: 40.6090, lon: 72.7933 };
const RADAR_RADIUS_KM = 120;
const RADAR_REFRESH_MS = 15000; // OpenSky anonymous is rate-limited
const LIST_MAX = 12;

const T = {
    connecting: "Подключение...",
    connected: "Подключено",
    updated: "Обновлено",
    closed: "Соединение закрыто",
    error: "Ошибка соединения",
    perHour: "рейсов в ближайший час",
    radarUpdating: "Запрос к OpenSky...",
    noAircraft: "Нет бортов в зоне",
    radarError: "OpenSky недоступен"
};

const STATUS_COLORS = {
    "CHECK-IN": "#16af56",
    "BOARDING": "#ffcc00",
    "DELAYED": "#ff4d4d",
    "DEPARTED": "#3498db",
    "CANCELLED": "#7a8288"
};

let lastFlights = [];
let fidsKeys = new Set();
let clockRefs = null;
let radarRefs = null;
let digitalLast = "";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function svgEl(tag, attrs) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
}

function pad(n) { return n < 10 ? "0" + n : "" + n; }

function formatTime(t) {
    if (!t) return "";
    const p = String(t).replace(".", ":").split(":");
    return p.length >= 2 ? p[0] + ":" + p[1] : String(t);
}

function flightDate(f) {
    if (!f || !f.date1 || !f.time1) return null;
    const d = new Date(f.date1 + "T" + formatTime(f.time1));
    return isNaN(d.getTime()) ? null : d;
}

function statusColor(nameEn) {
    const key = (nameEn || "").trim().toUpperCase();
    return STATUS_COLORS[key] || "#cfd6db";
}

function statusClass(nameEn) {
    const key = (nameEn || "").trim().toUpperCase().replace(/[^A-Z0-9-]/g, "");
    return STATUS_COLORS[key] ? key : "DEFAULT";
}

// ---------------------------------------------------------------------------
// Clock (SVG) — face + hands + flight ring
// ---------------------------------------------------------------------------
function buildClock(container) {
    const svg = svgEl("svg", { viewBox: "0 0 200 200" });
    svg.classList.add("clock-face");

    svg.appendChild(svgEl("circle", { cx: 100, cy: 100, r: 80, "class": "face-bg" }));
    svg.appendChild(svgEl("circle", { cx: 100, cy: 100, r: 80, "class": "face-rim" }));

    // Ticks (60) + numerals
    for (let i = 0; i < 60; i++) {
        const a = (i * 6 * Math.PI) / 180;
        const major = i % 5 === 0;
        const r1 = major ? 67 : 72;
        const r2 = 80;
        svg.appendChild(svgEl("line", {
            x1: (100 + r1 * Math.sin(a)).toFixed(2),
            y1: (100 - r1 * Math.cos(a)).toFixed(2),
            x2: (100 + r2 * Math.sin(a)).toFixed(2),
            y2: (100 - r2 * Math.cos(a)).toFixed(2),
            "class": major ? "tick-major" : "tick-minor"
        }));
    }
    for (let i = 1; i <= 12; i++) {
        const a = (i * 30 * Math.PI) / 180;
        const t = svgEl("text", {
            x: (100 + 57 * Math.sin(a)).toFixed(1),
            y: (100 - 57 * Math.cos(a)).toFixed(1),
            "class": "clock-numeral"
        });
        t.textContent = i;
        svg.appendChild(t);
    }

    // Flight ring guide
    svg.appendChild(svgEl("circle", { cx: 100, cy: 100, r: 88, "class": "ring-guide" }));

    // Flight markers group
    const markersG = svgEl("g", { "class": "flight-markers" });
    svg.appendChild(markersG);

    // Hands
    const hour = svgEl("g", { "class": "hand hour" });
    hour.appendChild(svgEl("line", { x1: 100, y1: 104, x2: 100, y2: 58, "class": "hour-line" }));
    const minute = svgEl("g", { "class": "hand minute" });
    minute.appendChild(svgEl("line", { x1: 100, y1: 105, x2: 100, y2: 38, "class": "minute-line" }));
    const second = svgEl("g", { "class": "hand second" });
    second.appendChild(svgEl("line", { x1: 100, y1: 112, x2: 100, y2: 30, "class": "second-line" }));

    svg.appendChild(hour);
    svg.appendChild(minute);
    svg.appendChild(second);
    svg.appendChild(svgEl("circle", { cx: 100, cy: 100, r: 3, "class": "center-dot" }));

    container.appendChild(svg);

    return { hour, minute, second, markersG };
}

function updateHands(refs, date) {
    const ms = date.getMilliseconds();
    const s = date.getSeconds() + ms / 1000;
    const m = date.getMinutes() + s / 60;
    const h = (date.getHours() % 12) + m / 60;
    refs.hour.setAttribute("transform", `rotate(${(h * 30).toFixed(3)} 100 100)`);
    refs.minute.setAttribute("transform", `rotate(${(m * 6).toFixed(3)} 100 100)`);
    refs.second.setAttribute("transform", `rotate(${(s * 6).toFixed(3)} 100 100)`);
}

// ---------------------------------------------------------------------------
// Flight ring + list + counter
// ---------------------------------------------------------------------------
function renderFlightRing(now) {
    if (!clockRefs) return 0;
    const markersG = clockRefs.markersG;
    markersG.innerHTML = "";

    const buckets = new Map();
    let count = 0;

    for (const f of lastFlights) {
        const dep = flightDate(f);
        if (!dep) continue;
        const mins = (dep.getTime() - now.getTime()) / 60000;
        if (mins < 0 || mins > 60) continue;
        count++;
        const m = Math.round(mins) % 60;
        if (!buckets.has(m)) buckets.set(m, []);
        buckets.get(m).push(f);
    }

    buckets.forEach((flights, m) => {
        const a = (m * 6 * Math.PI) / 180;
        const cx = 100 + 88 * Math.sin(a);
        const cy = 100 - 88 * Math.cos(a);
        if (flights.length === 1) {
            const c = statusColor(flights[0].status && flights[0].status.name_en);
            markersG.appendChild(svgEl("circle", { cx: cx.toFixed(2), cy: cy.toFixed(2), r: 3.2, fill: c, stroke: "#0d1114", "stroke-width": 0.6 }));
        } else {
            markersG.appendChild(svgEl("circle", { cx: cx.toFixed(2), cy: cy.toFixed(2), r: 5, fill: "#ffffff" }));
            const t = svgEl("text", { x: cx.toFixed(2), y: cy.toFixed(2), "class": "ring-marker-count" });
            t.textContent = flights.length;
            markersG.appendChild(t);
        }
    });

    return count;
}

function renderList(now) {
    const wrap = document.getElementById("nextFlights");
    if (!wrap) return;

    const upcoming = lastFlights
        .filter(f => {
            const d = flightDate(f);
            return d && d.getTime() >= now.getTime();
        })
        .sort((a, b) => flightDate(a).getTime() - flightDate(b).getTime())
        .slice(0, LIST_MAX);

    wrap.innerHTML = "";

    if (upcoming.length === 0) {
        wrap.innerHTML = '<div class="flight-item"><div class="fi-meta"><div class="fi-flight">Нет ближайших рейсов</div></div></div>';
        return;
    }

    for (const f of upcoming) {
        const item = document.createElement("div");
        item.className = "flight-item";
        const dep = flightDate(f);
        const dest = (f.destination && f.destination.name_ru) || "";
        const status = ((f.status && f.status.name_ru) || "").replace(/-/g, " ");
        const cls = statusClass(f.status && f.status.name_en);
        item.innerHTML = `
            <div class="fi-time">${pad(dep.getHours())}:${pad(dep.getMinutes())}</div>
            <div class="fi-meta">
                <div class="fi-flight">${f.airline || ""} ${f.flight || ""}</div>
                <div class="fi-dest">${dest}</div>
            </div>
            <div class="status-pill st-${cls}">${status}</div>
        `;
        wrap.appendChild(item);
    }
}

function renderCounter(count) {
    const el = document.getElementById("hourCounter");
    if (el) el.innerHTML = `Ближайший час: <b>${count}</b> ${T.perHour}`;
}

function refreshFlights() {
    const now = new Date();
    const count = renderFlightRing(now);
    renderList(now);
    renderCounter(count);
}

// ---------------------------------------------------------------------------
// Radar (OpenSky via /api/radar proxy)
// ---------------------------------------------------------------------------
function buildRadar(container) {
    const size = 400;
    const cx = size / 2, cy = size / 2;
    const scale = (cx - 15) / RADAR_RADIUS_KM;

    const svg = svgEl("svg", { viewBox: `0 0 ${size} ${size}`, preserveAspectRatio: "xMidYMid meet" });
    svg.appendChild(svgEl("rect", { x: 0, y: 0, width: size, height: size, rx: 8, "class": "radar-bg" }));

    // Range rings
    [1, 2, 3].forEach(i => {
        const r = (RADAR_RADIUS_KM / 3) * i * scale;
        svg.appendChild(svgEl("circle", { cx, cy, r, "class": "range-ring" + (i === 3 ? " outer" : "") }));
        const lbl = svgEl("text", { x: cx + 5, y: cy - r + 3, "class": "range-label" });
        lbl.textContent = (RADAR_RADIUS_KM / 3 * i) + " км";
        svg.appendChild(lbl);
    });

    // Crosshair
    svg.appendChild(svgEl("line", { x1: cx, y1: 8, x2: cx, y2: size - 8, "class": "crosshair" }));
    svg.appendChild(svgEl("line", { x1: 8, y1: cy, x2: size - 8, y2: cy, "class": "crosshair" }));

    // Airport
    svg.appendChild(svgEl("circle", { cx, cy, r: 5, "class": "airport-dot" }));
    const al = svgEl("text", { x: cx, y: cy - 10, "class": "airport-label" });
    al.textContent = "OSS";
    svg.appendChild(al);

    const planesG = svgEl("g", { "class": "planes" });
    svg.appendChild(planesG);

    container.appendChild(svg);

    return { planesG, scale, cx, cy };
}

function projectRadar(refs, lat, lon) {
    const kmLat = 111.32;
    const kmLon = 111.32 * Math.cos(AIRPORT.lat * Math.PI / 180);
    const dy = (lat - AIRPORT.lat) * kmLat;
    const dx = (lon - AIRPORT.lon) * kmLon;
    return {
        x: refs.cx + dx * refs.scale,
        y: refs.cy - dy * refs.scale
    };
}

function isFidsFlight(callsign) {
    const cs = (callsign || "").trim().toUpperCase().replace(/\s+/g, "");
    if (!cs) return false;
    if (fidsKeys.has(cs)) return true;
    for (const k of fidsKeys) {
        if (k.length >= 3 && cs.endsWith(k)) return true;
    }
    return false;
}

function renderPlanes(states) {
    const statusEl = document.getElementById("radarStatus");
    if (!radarRefs) return;

    const g = radarRefs.planesG;
    g.innerHTML = "";

    if (!Array.isArray(states) || states.length === 0) {
        if (statusEl) statusEl.textContent = T.noAircraft;
        return;
    }

    let drawn = 0;
    for (const s of states) {
        if (!s) continue;
        const lon = s[5], lat = s[6];
        if (lon == null || lat == null) continue;

        const p = projectRadar(radarRefs, lat, lon);
        if (Math.abs(p.x - radarRefs.cx) > radarRefs.cx - 5 || Math.abs(p.y - radarRefs.cy) > radarRefs.cy - 5) continue;

        const callsign = (s[1] || "").trim();
        const onGround = s[8] === true;
        const track = typeof s[10] === "number" ? s[10] : 0;
        const isFids = isFidsFlight(callsign);

        let cls = "plane-air";
        if (onGround) cls = "plane-ground";
        else if (isFids) cls = "plane-fids";

        const grp = svgEl("g", { transform: `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)}) rotate(${track.toFixed(0)})` });
        // Arrow pointing north (up)
        grp.appendChild(svgEl("path", {
            d: "M0,-7 L3.4,5 L0,2 L-3.4,5 Z",
            "class": cls
        }));
        g.appendChild(grp);

        if (isFids) {
            g.appendChild(svgEl("circle", { cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: 9, "class": "plane-fids-ring" }));
        }

        if (callsign) {
            const lbl = svgEl("text", { x: p.x.toFixed(1), y: (p.y + 16).toFixed(1), "class": "plane-label" });
            lbl.textContent = callsign;
            g.appendChild(lbl);
        }
        drawn++;
    }

    if (statusEl) {
        statusEl.textContent = `Бортов: ${drawn} · ${new Date().toLocaleTimeString()}`;
    }
}

async function refreshRadar() {
    const statusEl = document.getElementById("radarStatus");
    try {
        const dLat = RADAR_RADIUS_KM / 111.32;
        const dLon = RADAR_RADIUS_KM / (111.32 * Math.cos(AIRPORT.lat * Math.PI / 180));
        const url = `/api/radar?lamin=${(AIRPORT.lat - dLat).toFixed(4)}&lomin=${(AIRPORT.lon - dLon).toFixed(4)}&lamax=${(AIRPORT.lat + dLat).toFixed(4)}&lomax=${(AIRPORT.lon + dLon).toFixed(4)}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error("bad status " + resp.status);
        const data = await resp.json();
        renderPlanes(data.states);
    } catch (e) {
        if (statusEl) statusEl.textContent = T.radarError;
    }
}

// ---------------------------------------------------------------------------
// WebSocket (FIDS departures)
// ---------------------------------------------------------------------------
function setConnectionStatus(text, isError) {
    const el = document.getElementById("connectionStatus");
    if (!el) return;
    el.textContent = text;
    el.style.color = isError ? "#ff4d4d" : "";
}

function updateFidsKeys() {
    fidsKeys.clear();
    for (const f of lastFlights) {
        const fl = (f.flight || "").trim().toUpperCase().replace(/\s+/g, "");
        const al = (f.airline || "").trim().toUpperCase().replace(/\s+/g, "");
        if (fl) fidsKeys.add(fl);
        if (al && fl) fidsKeys.add(al + fl);
    }
}

function initWebSocket() {
    const socket = new WebSocket("ws://" + window.location.hostname + "/go/ws/dep");

    const ping = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
        }
    }, 30000);

    socket.onopen = function () {
        setConnectionStatus(`${T.connected} (${new Date().toLocaleTimeString()})`);
    };

    socket.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            if (window.updateNewYearStatus) window.updateNewYearStatus(data);

            if (data && data.type === "notification") return;
            if (data && data.server_time) return;

            lastFlights = Array.isArray(data) ? data : [];
            updateFidsKeys();
            refreshFlights();
            setConnectionStatus(`${T.updated} ${new Date().toLocaleTimeString()}`);
        } catch (e) {
            console.error("Ошибка данных:", e);
        }
    };

    socket.onclose = function () {
        setConnectionStatus(`${T.closed} ${new Date().toLocaleTimeString()}`, true);
        clearInterval(ping);
        setTimeout(() => location.reload(), 10000);
    };

    socket.onerror = function () {
        setConnectionStatus(`${T.error} ${new Date().toLocaleTimeString()}`, true);
        clearInterval(ping);
    };
}

// ---------------------------------------------------------------------------
// Animation + init
// ---------------------------------------------------------------------------
function animate() {
    const now = new Date();
    updateHands(clockRefs, now);

    const digital = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    if (digital !== digitalLast) {
        digitalLast = digital;
        const dEl = document.getElementById("clockDigital");
        if (dEl) dEl.textContent = digital;
    }
    requestAnimationFrame(animate);
}

document.addEventListener("DOMContentLoaded", function () {
    clockRefs = buildClock(document.getElementById("clockWrap"));
    radarRefs = buildRadar(document.getElementById("radarWrap"));

    const dateEl = document.getElementById("clockDate");
    if (dateEl) dateEl.textContent = new Date().toLocaleDateString("ru-RU", {
        weekday: "long", day: "numeric", month: "long", year: "numeric"
    });

    refreshFlights();
    initWebSocket();
    animate();

    // Recompute ring/list every 5s as "now" moves
    setInterval(refreshFlights, 5000);

    // Radar loop
    refreshRadar();
    setInterval(refreshRadar, RADAR_REFRESH_MS);
});
