// ============================================================================
// FIDS Departures — Bilingual split board (Kyrgyz | Clocks | English)
// ============================================================================

// --- Translations for UI labels --------------------------------------------
const T = {
    connectionStatus: {
        connecting: "Туташуу...",
        connected: "Туташты",
        updated: "Жаңыртылды",
        closed: "Туташуу жабылды",
        error: "Туташууда катачылык"
    },
    flightLabel: { ru: "Рейс", en: "Flight", ky: "Каттам" }
};

// --- 4 country clocks (different time zones) ------------------------------
const WORLD_CLOCKS = [
    { tz: "Europe/Moscow", city: "Москва", country: "Россия" },
    { tz: "Asia/Dubai", city: "Дубай", country: "БАЭ" },
    { tz: "Asia/Almaty", city: "Алматы", country: "Казахстан" },
    { tz: "Asia/Shanghai", city: "Пекин", country: "Кытай" }
];

const SVG_NS = "http://www.w3.org/2000/svg";

let lastFlights = [];
let notificationTimeout;
let mainClock = null;
let miniClocks = [];
let offsetRefreshTimer = null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatTime(timeString) {
    if (!timeString) return "";
    try {
        if (timeString.includes("T")) {
            const t = timeString.split("T")[1];
            const [h, m] = t.split(":");
            return `${h}:${m}`;
        }
        const [h, m] = timeString.split(":");
        return `${h}:${m}`;
    } catch (e) {
        return "";
    }
}

function formatDateLabel(dateStr, lang) {
    if (!dateStr) return "";
    const d = new Date(dateStr + "T00:00:00");
    if (isNaN(d.getTime())) return dateStr;
    const locale = lang === "ky" ? "ky" : "en";
    try {
        return d.toLocaleDateString(locale, {
            weekday: "long", day: "numeric", month: "long", year: "numeric"
        });
    } catch (e) {
        return d.toLocaleDateString(lang === "ky" ? "ru" : "en", {
            day: "numeric", month: "long", year: "numeric"
        });
    }
}

// ---------------------------------------------------------------------------
// Flights rendering (grouped by date)
// ---------------------------------------------------------------------------
function groupFlightsByDate(flights) {
    const sorted = [...flights].sort((a, b) => {
        const da = (a.date1 || "") + " " + (a.time1 || "");
        const db = (b.date1 || "") + " " + (b.time1 || "");
        return da.localeCompare(db);
    });
    const groups = [];
    for (const f of sorted) {
        const dateKey = f.date1 || "";
        let group = groups.find(g => g.date === dateKey);
        if (!group) {
            group = { date: dateKey, flights: [] };
            groups.push(group);
        }
        group.flights.push(f);
    }
    return groups;
}

function buildFlightRow(flight, lang) {
    const tr = document.createElement("tr");
    const city = (flight.destination && flight.destination["name_" + lang]) || "";
    const status = ((flight.status && flight.status["name_" + lang]) || "").replace(/-/g, " ");

    let timeHtml = formatTime(flight.time1);
    if (flight.last_time) {
        timeHtml = `<span class="time-strike">${formatTime(flight.time1)}</span>${formatTime(flight.last_time)}`;
    }

    const counters = Array.isArray(flight.stoika)
        ? flight.stoika.map(s => s.number).join(", ")
        : "";

    tr.innerHTML = `
        <td class="c-airline">
            <div class="logo-container">
                <img src="static/images/airlines/${flight.airline}.svg" alt="" class="logo">
            </div>
        </td>
        <td class="c-flight">${flight.flight || ""}</td>
        <td class="c-dest">${city}</td>
        <td class="c-time">${timeHtml}</td>
        <td class="c-counters">${counters}</td>
        <td class="c-status">
            <div class="statusdiv ${(flight.status && flight.status.name_en) || ""}">${status}</div>
        </td>
    `;
    return tr;
}

function buildDateRow(label) {
    const tr = document.createElement("tr");
    tr.className = "date-row";
    tr.innerHTML = `<td colspan="6"><span class="date-label">${label}</span></td>`;
    return tr;
}

function renderFlights() {
    const kyBody = document.getElementById("kyBody");
    const enBody = document.getElementById("enBody");
    if (!kyBody || !enBody) return;

    if (!Array.isArray(lastFlights)) lastFlights = [];

    const groups = groupFlightsByDate(lastFlights);

    kyBody.innerHTML = "";
    enBody.innerHTML = "";

    groups.forEach(group => {
        const labelKy = formatDateLabel(group.date, "ky");
        const labelEn = formatDateLabel(group.date, "en");

        kyBody.appendChild(buildDateRow(labelKy));
        enBody.appendChild(buildDateRow(labelEn));

        group.flights.forEach(flight => {
            kyBody.appendChild(buildFlightRow(flight, "ky"));
            enBody.appendChild(buildFlightRow(flight, "en"));
        });
    });
}

// ---------------------------------------------------------------------------
// Analog clock builder (SVG) + animation
// ---------------------------------------------------------------------------
function svgEl(tag, attrs) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
}

function buildClock(container, opts) {
    const wrap = document.createElement("div");
    wrap.className = "clock";

    const svg = svgEl("svg", { viewBox: "0 0 100 100" });
    svg.classList.add("clock-face");

    // Face
    svg.appendChild(svgEl("circle", { cx: 50, cy: 50, r: 49, "class": "face-bg" }));
    svg.appendChild(svgEl("circle", { cx: 50, cy: 50, r: 47, "class": "face-rim" }));

    // Ticks
    for (let i = 0; i < 60; i++) {
        const a = (i * 6 * Math.PI) / 180;
        const major = i % 5 === 0;
        const r1 = major ? 41 : 44;
        const r2 = 47;
        const cls = major ? "tick-major" : "tick-minor";
        svg.appendChild(svgEl("line", {
            x1: (50 + r1 * Math.sin(a)).toFixed(2),
            y1: (50 - r1 * Math.cos(a)).toFixed(2),
            x2: (50 + r2 * Math.sin(a)).toFixed(2),
            y2: (50 - r2 * Math.cos(a)).toFixed(2),
            "class": cls
        }));
    }

    // Numerals (main clock only)
    if (opts.numerals) {
        const positions = [
            [50, 18, "12"], [82, 50, "3"], [50, 82, "6"], [18, 50, "9"]
        ];
        positions.forEach(([x, y, t]) => {
            const txt = svgEl("text", { x, y, "class": "clock-numeral" });
            txt.textContent = t;
            svg.appendChild(txt);
        });
    }

    // Hands (groups rotated around center 50,50)
    const hour = svgEl("g", { "class": "hand hour" });
    hour.appendChild(svgEl("line", { x1: 50, y1: 52, x2: 50, y2: 32, "class": "hour-line" }));
    const minute = svgEl("g", { "class": "hand minute" });
    minute.appendChild(svgEl("line", { x1: 50, y1: 53, x2: 50, y2: 19, "class": "minute-line" }));
    const second = svgEl("g", { "class": "hand second" });
    second.appendChild(svgEl("line", { x1: 50, y1: 58, x2: 50, y2: 14, "class": "second-line" }));

    svg.appendChild(hour);
    svg.appendChild(minute);
    svg.appendChild(second);
    svg.appendChild(svgEl("circle", { cx: 50, cy: 50, r: 2.6, "class": "center-dot" }));

    wrap.appendChild(svg);

    if (opts.city) {
        const cityEl = document.createElement("div");
        cityEl.className = "clock-city";
        cityEl.textContent = opts.city;
        wrap.appendChild(cityEl);
    }
    if (opts.country) {
        const countryEl = document.createElement("div");
        countryEl.className = "clock-country";
        countryEl.textContent = opts.country;
        wrap.appendChild(countryEl);
    }

    container.appendChild(wrap);

    return { hour, minute, second, tz: opts.tz || null, offsetMs: 0 };
}

function updateClockHands(clock, date) {
    const ms = date.getMilliseconds();
    const s = date.getSeconds() + ms / 1000;
    const m = date.getMinutes() + s / 60;
    const h = (date.getHours() % 12) + m / 60;
    clock.hour.setAttribute("transform", `rotate(${(h * 30).toFixed(3)} 50 50)`);
    clock.minute.setAttribute("transform", `rotate(${(m * 6).toFixed(3)} 50 50)`);
    clock.second.setAttribute("transform", `rotate(${(s * 6).toFixed(3)} 50 50)`);
}

// Offset (ms) between a time zone and local time, computed via Intl.
function computeOffsetMs(tz, date) {
    try {
        const dtf = new Intl.DateTimeFormat("en-US", {
            timeZone: tz,
            hourCycle: "h23",
            hour12: false,
            year: "numeric", month: "2-digit", day: "2-digit",
            hour: "2-digit", minute: "2-digit", second: "2-digit"
        });
        const parts = {};
        for (const p of dtf.formatToParts(date)) {
            if (p.type !== "literal") parts[p.type] = p.value;
        }
        const asUTC = Date.UTC(
            +parts.year, +parts.month - 1, +parts.day,
            +parts.hour % 24, +parts.minute, +parts.second
        );
        return asUTC - Math.floor(date.getTime() / 1000) * 1000;
    } catch (e) {
        return 0;
    }
}

function refreshOffsets() {
    const now = new Date();
    miniClocks.forEach(c => {
        if (c.tz) c.offsetMs = computeOffsetMs(c.tz, now);
    });
}

function pad(n) {
    return n < 10 ? "0" + n : "" + n;
}

function updateDigital(date) {
    const el = document.getElementById("mainClockDigital");
    if (el) el.textContent = `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function animateClocks() {
    const now = Date.now();
    const local = new Date(now);
    updateClockHands(mainClock, local);
    updateDigital(local);
    for (const c of miniClocks) {
        updateClockHands(c, new Date(now + c.offsetMs));
    }
    requestAnimationFrame(animateClocks);
}

function initClocks() {
    mainClock = buildClock(document.getElementById("mainClock"), {
        numerals: true
    });

    const miniContainer = document.getElementById("miniClocks");
    miniClocks = WORLD_CLOCKS.map(wc => buildClock(miniContainer, {
        city: wc.city,
        country: wc.country,
        tz: wc.tz,
        numerals: false
    }));

    refreshOffsets();
    offsetRefreshTimer = setInterval(refreshOffsets, 30000);
    animateClocks();
}

// ---------------------------------------------------------------------------
// Notification bar
// ---------------------------------------------------------------------------
function showNotification(data) {
    let bar = document.getElementById("notification-bar");
    if (!bar) {
        bar = document.createElement("div");
        bar.id = "notification-bar";
        document.body.appendChild(bar);
    }
    clearTimeout(notificationTimeout);

    const statusClass = data.status_en || (data.status && data.status.name_en) || "";
    bar.className = statusClass;

    const statusText = data.status_ky || (data.status && data.status.name_ky) || "";

    bar.innerHTML = `
        <span style="opacity:0.9;margin-right:15px;">${T.flightLabel.ky} ${data.flight}:</span>
        <span style="text-transform:uppercase;">${statusText}</span>
    `;

    requestAnimationFrame(() => { bar.style.transform = "translateX(0)"; });

    notificationTimeout = setTimeout(() => {
        bar.style.transform = "translateX(100%)";
        setTimeout(() => {
            bar.style.transition = "none";
            bar.style.transform = "translateX(-100%)";
            requestAnimationFrame(() => {
                bar.style.transition = "transform 0.6s cubic-bezier(0.25, 1, 0.5, 1)";
            });
        }, 600);
    }, 7000);
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
function setConnectionStatus(text, isError) {
    const el = document.getElementById("connectionStatus");
    if (!el) return;
    el.textContent = text;
    el.style.color = isError ? "#ff4d4d" : "";
}

function initWebSocket() {
    const socket = new WebSocket("ws://" + window.location.hostname + "/go/ws/dep");

    const pingInterval = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
        }
    }, 30000);

    socket.onopen = function () {
        setConnectionStatus(`${T.connectionStatus.connected} (${new Date().toLocaleTimeString()})`);
    };

    socket.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            if (window.updateNewYearStatus) window.updateNewYearStatus(data);

            if (data && data.type === "notification") {
                showNotification(data);
                return;
            }

            // Server time snapshot — we keep local clock, just ignore it.
            if (data && data.server_time) {
                return;
            }

            lastFlights = Array.isArray(data) ? data : [];
            renderFlights();
            setConnectionStatus(`${T.connectionStatus.updated} ${new Date().toLocaleTimeString()}`);
        } catch (e) {
            console.error("Ошибка обработки данных:", e);
        }
    };

    socket.onclose = function () {
        setConnectionStatus(`${T.connectionStatus.closed} ${new Date().toLocaleTimeString()}`, true);
        clearInterval(pingInterval);
        setTimeout(() => location.reload(), 10000);
    };

    socket.onerror = function () {
        setConnectionStatus(`${T.connectionStatus.error} ${new Date().toLocaleTimeString()}`, true);
        clearInterval(pingInterval);
    };
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", function () {
    const required = ["kyBody", "enBody", "mainClock", "miniClocks", "connectionStatus"];
    for (const id of required) {
        if (!document.getElementById(id)) {
            console.error("Не найден элемент: " + id);
            return;
        }
    }

    initClocks();
    renderFlights();
    initWebSocket();
});
