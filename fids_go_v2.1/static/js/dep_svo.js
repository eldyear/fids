// ============================================================================
// Flight Radar Clock — Sheremetyevo-style, adapted for Osh.
//
//   Blue   = ARRIVALS   (прилёты)  — airplanes fly TOWARD the centre
//   Orange = DEPARTURES (вылеты)   — airplanes fly AWAY from the centre
//
// All geometry is built mathematically around the centre (CX, CY). Every
// radius / colour / font lives in CONFIG. The airplane is an external SVG
// file (static/images/plane.svg) that you can replace with your own.
// ============================================================================
"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const XLINK_NS = "http://www.w3.org/1999/xlink";

// ---------------------------------------------------------------------------
// CONFIG
// ---------------------------------------------------------------------------
const CONFIG = {
    size: 2048,
    cx: 1024,
    cy: 1024,

    // radii
    R_outer: 1250,
    R_tick_outer: 1220,
    R_tick_major: 1140,
    R_tick_minor: 1200,
    R_minute_numbers: 1120,
    R_hour_numbers: 740,
    R_arc_labels: 720,
    R_routes_outer: 1008,   // routes run slightly past the dial circle
    R_routes_inner: 50,     // routes start ~45px from the red centre ring
    R_inner_ticks_outer: 640,
    R_inner_ticks_inner: 615,
    R_clock: 450,
    durationMinutes: 60,     // time (min) for a plane to cross the full dial

    // hands
    handHour: 280,
    handMinute: 450,
    handSecond: 540,

    // colours
    colorArrival: "#00AFCB",
    colorDeparture: "#B84924",
    colorArrivalSoft: "rgba(0,175,203,0.55)",
    colorDepartureSoft: "rgba(184,73,36,0.55)",
    colorTickMajor: "#FFFFFF",
    colorTickMinor: "#3a444c",
    colorMinuteNumber: "#d8d8d8",
    colorHourNumber: "#FFFFFF",
    colorArcLabel: "rgba(255, 255, 255, 0.7)", // Приглушенный белый
    colorSecondHand: "#FF351D",
    colorCenterRing: "#FF351D",

    // fonts
    fontMinuteNumber: 34,
    fontHourNumber: 150,
    fontArcLabel: 38,
    fontCityLabel: 22,
    cityLabelOpacity: 0.85,

    // labels
    arcTopLeft: "OSH KYRGYZSTAN",
    arcTopRight: "OSH AIRPORT",

    // airplane (external SVG, replaceable)
    planeImage: "static/images/plane.svg",
    planeSize: 34
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let flights = [];           // [{ city, type:"arrival"|"departure", angle, _time }]
let groups = {};
let hands = {};
let arcTexts = {};

const WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function svgEl(tag, attrs) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
}

function rad(deg) { return deg * Math.PI / 180; }

// polar point: angle in degrees, 0 = 12 o'clock, clockwise.
function polar(angleDeg, r) {
    return {
        x: CONFIG.cx + r * Math.sin(rad(angleDeg)),
        y: CONFIG.cy - r * Math.cos(rad(angleDeg))
    };
}

function pad2(n) { return n < 10 ? "0" + n : "" + n; }

// Map live FIDS flights (from /go/ws/flights) into the route array.
function mapLiveFlights(data) {
    const arr = [];
    for (const f of data) {
        const dest = f.destination || {};
        const city = String(dest.name_en || dest.name_ru || dest.name_ky || "").trim().toUpperCase();
        if (!city) continue;
        const type = f.direction === "arr" ? "arrival" : "departure";
        const t = String(f.time1 || "").replace(".", ":").split(":");
        const h = parseInt(t[0], 10) || 0;
        const m = parseInt(t[1], 10) || 0;
        const angle = (((h % 12) + m / 60) / 12) * 360;
        const d = f.date1 ? new Date(f.date1 + "T" + pad2(h) + ":" + pad2(m) + ":00") : null;
        arr.push({
            city,
            type,
            angle,
            _time: (d && !isNaN(d.getTime())) ? d.getTime() : null
        });
    }
    return arr;
}

// ---------------------------------------------------------------------------
// SVG build
// ---------------------------------------------------------------------------
function buildSvg(container) {
    const svg = svgEl("svg", {
        viewBox: `0 0 ${CONFIG.size} ${CONFIG.size}`,
        preserveAspectRatio: "xMidYMid meet"
    });

    const defs = svgEl("defs", {});

    // Градиент затемнения концов городов (от белого к прозрачно-серу)
    const fadeGrad = svgEl("linearGradient", {
        id: "textFade",
        x1: "0%", y1: "0%", x2: "100%", y2: "0%"
    });
    fadeGrad.appendChild(svgEl("stop", { offset: "0%", "stop-color": "#FFFFFF", "stop-opacity": "1" }));
    fadeGrad.appendChild(svgEl("stop", { offset: "70%", "stop-color": "#E0E0E0", "stop-opacity": "0.85" }));
    fadeGrad.appendChild(svgEl("stop", { offset: "100%", "stop-color": "#505458", "stop-opacity": "0.2" }));
    defs.appendChild(fadeGrad);

    // Arc label paths (for textPath)
    const arcSpecs = {
        arcTL: [290, 340, 1], // От 9:40 до 11:20 (между 9 и 12)
        arcTR: [20, 70, 1],   // От 12:40 до 2:20 (между 12 и 3)
        arcBR: [160, 110, 0], // От 3:40 до 5:20 (между 3 и 6)
        arcBL: [250, 200, 0]  // От 6:40 до 8:20 (между 6 и 9)
    };
    for (const id in arcSpecs) {
        const [a1, a2, sweep] = arcSpecs[id];
        const p1 = polar(a1, CONFIG.R_arc_labels);
        const p2 = polar(a2, CONFIG.R_arc_labels);
        defs.appendChild(svgEl("path", {
            id,
            d: `M ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} A ${CONFIG.R_arc_labels} ${CONFIG.R_arc_labels} 0 0 ${sweep} ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`,
            fill: "none"
        }));
    }

    svg.appendChild(defs);

    const order = [
        "background", "outer-ticks", "minute-numbers", "routes",
        "airplanes", "city-labels", "inner-ticks", "arc-labels",
        "hour-numbers", "clock-hands", "center-cap"
    ];
    order.forEach(name => {
        groups[name] = svgEl("g", { id: name });
        svg.appendChild(groups[name]);
    });
    groups["arrival-routes"] = svgEl("g", { id: "arrival-routes" });
    groups["departure-routes"] = svgEl("g", { id: "departure-routes" });
    groups["routes"].appendChild(groups["arrival-routes"]);
    groups["routes"].appendChild(groups["departure-routes"]);

    container.appendChild(svg);
}

// ---------------------------------------------------------------------------
// Static draws
// ---------------------------------------------------------------------------
function drawOuterTicks() {
    const g = groups["outer-ticks"];
    for (let i = 0; i < 60; i++) {
        const a = i * 6;
        const major = i % 5 === 0;

        const p1 = polar(a, major ? CONFIG.R_tick_major : CONFIG.R_tick_minor);
        const p2 = polar(a, CONFIG.R_tick_outer);

        g.appendChild(svgEl("line", {
            x1: p1.x.toFixed(2), y1: p1.y.toFixed(2),
            x2: p2.x.toFixed(2), y2: p2.y.toFixed(2),
            stroke: major ? "#FFFFFF" : "rgba(255, 255, 255, 0.3)",
            "stroke-width": major ? 7 : 3,
            "stroke-linecap": "round"
        }));
    }
}

// Minute numbers follow the circle (tangential), flipped to stay readable.
function drawMinuteNumbers() {
    const g = groups["minute-numbers"];
    for (let i = 0; i < 12; i++) {
        const value = i * 5;
        const a = i * 30;
        const p = polar(a, CONFIG.R_minute_numbers);
        let rot = a;
        if (a > 90 && a < 270) rot += 180;
        
        const t = svgEl("text", {
            x: p.x.toFixed(2), y: p.y.toFixed(2),
            fill: CONFIG.colorMinuteNumber,
            "font-size": 42, // Увеличим размер минут
            "font-weight": "400",
            "text-anchor": "middle",
            "dominant-baseline": "central",
            transform: `rotate(${rot} ${p.x.toFixed(2)} ${p.y.toFixed(2)})`
        });
        t.textContent = pad2(value);
        g.appendChild(t);
    }
}

function drawHourNumbers() {
    const g = groups["hour-numbers"];
    const items = [["12", 0], ["3", 90], ["6", 180], ["9", 270]];
    items.forEach(([txt, a]) => {
        const p = polar(a, CONFIG.R_hour_numbers);
        const t = svgEl("text", {
            x: p.x.toFixed(2), y: p.y.toFixed(2),
            fill: CONFIG.colorHourNumber,
            "font-size": CONFIG.fontHourNumber,
            "font-weight": "700",
            "text-anchor": "middle",
            "dominant-baseline": "central",
            "letter-spacing": "-2"
        });
        t.textContent = txt;
        g.appendChild(t);
    });
}

function drawInnerTicks() {
    const g = groups["inner-ticks"];
    for (let i = 0; i < 60; i++) {
        const a = i * 6;
        const major = i % 5 === 0;

        // Увеличиваем длину внутренних засечек
        const rInner = major ? 600 : 615; // Длинные крупные засечки
        const rOuter = 650;              // Внешний край засечек

        const p1 = polar(a, rInner);
        const p2 = polar(a, rOuter);

        g.appendChild(svgEl("line", {
            x1: p1.x.toFixed(2), y1: p1.y.toFixed(2),
            x2: p2.x.toFixed(2), y2: p2.y.toFixed(2),
            stroke: major ? "#FFFFFF" : "#5A6670", // Основные — ярко-белые, мелкие — четкие серые
            "stroke-width": major ? 3.5 : 1.5,     // Увеличиваем толщину
            "stroke-linecap": "round"
        }));
    }
}

function addArcLabel(text, pathId) {
    const t = svgEl("text", {
        fill: CONFIG.colorArcLabel,
        "font-size": CONFIG.fontArcLabel,
        "font-weight": "600",
        "letter-spacing": "4",
        "text-anchor": "middle",
        "dominant-baseline": "central"
    });
    const tp = svgEl("textPath", { href: "#" + pathId, startOffset: "50%" });
    tp.setAttributeNS(XLINK_NS, "xlink:href", "#" + pathId);
    tp.textContent = text;
    t.appendChild(tp);
    groups["arc-labels"].appendChild(t);
    return tp;
}

function drawArcLabels() {
    addArcLabel(CONFIG.arcTopLeft, "arcTL");
    addArcLabel(CONFIG.arcTopRight, "arcTR");
    arcTexts.count = addArcLabel("", "arcBL");
    arcTexts.date = addArcLabel("", "arcBR");
}

function drawClockHands() {
    const g = groups["clock-hands"];
    const c = CONFIG;

    // Часовая стрелка (увеличиваем толщину с 12 до 18)
    const hour = svgEl("g", {});
    hour.appendChild(svgEl("line", {
        x1: c.cx, y1: c.cy + 30, x2: c.cx, y2: c.cy - c.handHour,
        stroke: "#ffffff", "stroke-width": 18, "stroke-linecap": "round"
    }));
    g.appendChild(hour);

    // Минутная стрелка (увеличиваем толщину с 7 до 11)
    const minute = svgEl("g", {});
    minute.appendChild(svgEl("line", {
        x1: c.cx, y1: c.cy + 35, x2: c.cx, y2: c.cy - c.handMinute,
        stroke: "#e8ecf0", "stroke-width": 11, "stroke-linecap": "round"
    }));
    g.appendChild(minute);

    // Секундная стрелка (увеличиваем толщину с 2 до 4)
    const second = svgEl("g", {});
    second.appendChild(svgEl("line", {
        x1: c.cx, y1: c.cy + 65, x2: c.cx, y2: c.cy - c.handSecond,
        stroke: c.colorSecondHand, "stroke-width": 4, "stroke-linecap": "round"
    }));
    second.appendChild(svgEl("circle", {
        cx: c.cx, cy: c.cy + 65, r: 14, fill: c.colorSecondHand
    }));
    g.appendChild(second);

    hands = { hour, minute, second };
}

// Увеличиваем центральную шайбу/колпачок (center cap)
function drawCenterCap() {
    const g = groups["center-cap"];
    const c = CONFIG;
    g.appendChild(svgEl("circle", { cx: c.cx, cy: c.cy, r: 32, fill: "#000000" }));
    g.appendChild(svgEl("circle", {
        cx: c.cx, cy: c.cy, r: 25,
        fill: "none", stroke: c.colorCenterRing, "stroke-width": 9
    }));
    g.appendChild(svgEl("circle", { cx: c.cx, cy: c.cy, r: 7, fill: "#ffffff" }));
}

function drawCenterCap() {
    const g = groups["center-cap"];
    const c = CONFIG;
    g.appendChild(svgEl("circle", { cx: c.cx, cy: c.cy, r: 24, fill: "#000000" }));
    g.appendChild(svgEl("circle", {
        cx: c.cx, cy: c.cy, r: 19,
        fill: "none", stroke: c.colorCenterRing, "stroke-width": 7
    }));
    g.appendChild(svgEl("circle", { cx: c.cx, cy: c.cy, r: 5, fill: "#ffffff" }));
}

// ---------------------------------------------------------------------------
// Dynamic: routes + airplanes + city labels
// ---------------------------------------------------------------------------
function clearDynamic() {
    groups["arrival-routes"].innerHTML = "";
    groups["departure-routes"].innerHTML = "";
    groups["airplanes"].innerHTML = "";
    groups["city-labels"].innerHTML = "";
}

function renderRoutes() {
    const c = CONFIG;
    for (const f of flights) {
        // Устанавливаем нейтральный белый цвет для всех городов вместо синего/оранжевого
        f._color = "#E0E0E0"; 
        
        // Линии больше не рисуем (группы маршрутов остаются пустыми)
    }
}

// Time-based plane position:
//   departure: at the centre at departure time, moves outward, then leaves the dial.
//   arrival:   comes in from beyond the dial (invisible at first), reaches centre at arrival time.
function renderAirplanes() {
    const c = CONFIG;
    const DUR = c.durationMinutes * 60 * 1000;
    const now = Date.now();
    const half = c.planeSize / 2;
    for (const f of flights) {
        if (f._time == null) continue;
        let p;
        if (f.type === "departure") {
            p = (now - f._time) / DUR;      // 0 at departure, grows after
        } else {
            p = (f._time - now) / DUR;      // 0 at arrival, shrinks before
        }
        if (p < 0 || p > 1) continue;       // outside the visible window
        const r = c.R_routes_inner + p * (c.R_routes_outer - c.R_routes_inner);
        const pos = polar(f.angle, r);
        let ang = f.angle;                  // departures: nose outward
        if (f.type === "arrival") ang += 180; // arrivals: nose inward
        const g = svgEl("g", {
            transform: `translate(${pos.x.toFixed(1)} ${pos.y.toFixed(1)}) rotate(${ang.toFixed(1)})`
        });
        const img = svgEl("image", {
            href: c.planeImage,
            x: -half, y: -half, width: c.planeSize, height: c.planeSize
        });
        img.setAttributeNS(XLINK_NS, "xlink:href", c.planeImage);
        g.appendChild(img);
        groups["airplanes"].appendChild(g);
    }
}

function renderCityLabels() {
    const c = CONFIG;
    
    // Счетчик дубликатов углов для разводки слоев
    const angleSlots = {};

    for (const f of flights) {
        // Округляем угол до 1 градуса для группировки близких по времени рейсов
        const slotKey = Math.round(f.angle);
        if (!angleSlots[slotKey]) angleSlots[slotKey] = 0;
        
        const stackIndex = angleSlots[slotKey];
        angleSlots[slotKey]++;

        // Внутреннее базовое кольцо (откуда начинаются первые буквы городов).
        // Для дубликатов сдвигаем слои наружу.
        const startR = 300 + (stackIndex * 38);

        let rot = f.angle - 90;
        let textAnchor = "start"; // По умолчанию начало слова фиксируется на startR и уходит наружу

        // Для нижней полусферы разворачиваем текст на 180°, чтобы не читать "вверх ногами",
        // и меняем привязку на "end", чтобы НАЧАЛО слова точно так же оставалось на startR и шло наружу!
        if (f.angle > 90 && f.angle < 270) {
            rot += 180;
            textAnchor = "end";
        }

        const p = polar(f.angle, startR);
        const t = svgEl("text", {
            x: p.x.toFixed(1), 
            y: p.y.toFixed(1),
            fill: f.city.length > 9 ? "url(#textFade)" : "#E0E0E0",
            "font-size": c.fontCityLabel || 20,
            "font-weight": "500",
            "letter-spacing": "2",
            "text-anchor": textAnchor,
            "dominant-baseline": "central",
            opacity: c.cityLabelOpacity || 0.85,
            transform: `rotate(${rot.toFixed(1)} ${p.x.toFixed(1)} ${p.y.toFixed(1)})`
        });
        
        t.textContent = f.city;
        groups["city-labels"].appendChild(t);
    }
}

function renderDynamic() {
    clearDynamic();
    renderRoutes();
    renderAirplanes();
    renderCityLabels();
    if (arcTexts.count) arcTexts.count.textContent = `${flights.length} FLIGHTS`;
}

function updateDate() {
    if (!arcTexts.date) return;
    const d = new Date();
    arcTexts.date.textContent = `${WEEKDAYS[d.getDay()]} ${pad2(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

// ---------------------------------------------------------------------------
// Animation (second hand ticks in 1 s steps)
// ---------------------------------------------------------------------------
function updateHands(date) {
    const c = CONFIG;
    const s = date.getSeconds();
    const m = date.getMinutes() + s / 60;
    const h = (date.getHours() % 12) + m / 60;
    hands.hour.setAttribute("transform", `rotate(${(h * 30).toFixed(3)} ${c.cx} ${c.cy})`);
    hands.minute.setAttribute("transform", `rotate(${(m * 6).toFixed(3)} ${c.cx} ${c.cy})`);
    hands.second.setAttribute("transform", `rotate(${(s * 6).toFixed(1)} ${c.cx} ${c.cy})`);
}

function animate() {
    updateHands(new Date());
    requestAnimationFrame(animate);
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
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const socket = new WebSocket(protocol + window.location.host + '/go/ws/flights');

    const ping = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
        }
    }, 30000);

    socket.onopen = function () {
        setConnectionStatus("connected · " + new Date().toLocaleTimeString());
    };

    socket.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            if (window.updateNewYearStatus) window.updateNewYearStatus(data);
            if (data && data.type === "notification") return;
            if (data && data.server_time) return;

            const mapped = mapLiveFlights(Array.isArray(data) ? data : []);
            flights = mapped; // no demo fallback — empty until live data arrives
            renderDynamic();
            setConnectionStatus("updated · " + new Date().toLocaleTimeString());
        } catch (e) {
            console.error("Ошибка данных:", e);
        }
    };

    socket.onclose = function () {
        setConnectionStatus("closed · " + new Date().toLocaleTimeString(), true);
        clearInterval(ping);
        // Мягкое переподключение без перезагрузки всей страницы
        setTimeout(initWebSocket, 5000);
    };

    socket.onerror = function () {
        setConnectionStatus("error · " + new Date().toLocaleTimeString(), true);
        clearInterval(ping);
    };
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", function () {
    buildSvg(document.getElementById("clockContainer"));

    drawOuterTicks();
    drawMinuteNumbers();
    drawInnerTicks();
    drawArcLabels();
    drawHourNumbers();
    drawClockHands();
    drawCenterCap();

    flights = []; // no placeholder cities
    renderDynamic();
    updateDate();

    animate();
    initWebSocket();

    setInterval(updateDate, 60000);

    // Reposition airplanes over time (time-based tracker)
    setInterval(function () {
        groups["airplanes"].innerHTML = "";
        renderAirplanes();
    }, 1000);
});
