const FLIGHTS_PER_PAGE = 15; // Increased to 15 for max density
const PAGE_DISPLAY_TIME = 10000;

let currentLang = 'ru';
const langs = ['ru', 'en', 'ky'];
let langIndex = 0;
let lastFlights = [];
let currentPage = 1;
let totalPages = 1;
let updateTimer;

const translations = {
    ru: {
        title: "ПРИЛЕТЫ",
        status: "Статус",
        page: "Страница",
        airline: "Авиакомпания",
        flight: "Рейс",
        origin: "Откуда",
        date: "Дата",
        time: "Время"
    },
    en: {
        title: "ARRIVALS",
        status: "Status",
        page: "Page",
        airline: "Airline",
        flight: "Flight",
        origin: "Origin",
        date: "Date",
        time: "Time"
    },
    ky: {
        title: "КЕЛҮҮЛӨР",
        status: "Статус",
        page: "Бет",
        airline: "Авиакомпания",
        flight: "Рейс",
        origin: "Кайдан",
        date: "Дата",
        time: "Убакыт"
    }
};

function formatTime(timeString) {
    if (!timeString) return '';
    try {
        if (timeString.includes('T')) {
            return timeString.split('T')[1].substring(0, 5);
        }
        return timeString.substring(0, 5);
    } catch (e) {
        return '';
    }
}

function renderFlights() {
    const container = document.getElementById('flightsContainer');

    // Pagination
    const start = (currentPage - 1) * FLIGHTS_PER_PAGE;
    const end = start + FLIGHTS_PER_PAGE;
    const pageFlights = lastFlights.slice(start, end);

    // Create table structure
    let tableHTML = `
        <table class="flights-table">
            <thead>
                <tr>
                    <th class="col-logo">${translations[currentLang].airline}</th>
                    <th class="col-flight">${translations[currentLang].flight}</th>
                    <th class="col-destination">${translations[currentLang].origin}</th>
                    <th class="col-date">${translations[currentLang].date}</th>
                    <th class="col-time">${translations[currentLang].time}</th>
                    <th class="col-status">${translations[currentLang].status}</th>
                </tr>
            </thead>
            <tbody>
    `;

    pageFlights.forEach(f => {
        const city = f.destination[`name_${currentLang}`] || f.destination.name_ru;
        const status = (f.status[`name_${currentLang}`] || f.status.name_ru).toUpperCase();

        let statusClass = 'status-ontime';
        if (f.status.name_en.includes('DELAY')) statusClass = 'status-delayed';
        if (f.status.name_en.includes('CANCEL')) statusClass = 'status-cancelled';
        if (f.status.name_en.includes('BOARDING')) statusClass = 'status-boarding';
        if (f.status.name_en.includes('CHECK-IN')) statusClass = 'status-checkin';
        if (f.status.name_en.includes('LANDED')) statusClass = 'status-landed';
        if (f.status.name_en.includes('ARRIVED')) statusClass = 'status-arrived';
        if (f.status.name_en.includes('DEPARTED')) statusClass = 'status-departed';

        // Time logic: Show both scheduled and actual if different
        let timeDisplay = `<div class="actual-time">${formatTime(f.time1)}</div>`;
        if (f.last_time && f.last_time !== f.time1) {
            timeDisplay = `
                <div class="scheduled-time">${formatTime(f.time1)}</div>
                <div class="actual-time">${formatTime(f.last_time)}</div>
            `;
        }

        // Format Date (e.g., "22.12")
        let dateDisplay = '';
        if (f.date1) {
            const parts = f.date1.split('-');
            if (parts.length === 3) {
                dateDisplay = `${parts[2]}.${parts[1]}`;
            }
        }

        tableHTML += `
            <tr class="${statusClass}">
                <td class="col-logo">
                    <img src="/go/static/images/airlines/${f.airline}.svg" class="airline-logo" onError="this.src='/go/static/images/default_airline.svg'">
                </td>
                <td class="col-flight">${f.flight}</td>
                <td class="col-destination">${city}</td>
                <td class="col-date">${dateDisplay}</td>
                <td class="col-time">
                    <div class="time-display">${timeDisplay}</div>
                </td>
                <td class="col-status">
                    <div class="status-text ${statusClass}">${status}</div>
                </td>
            </tr>
        `;
    });

    tableHTML += `
            </tbody>
        </table>
    `;

    container.innerHTML = tableHTML;
    document.getElementById('pageInfo').textContent = `${translations[currentLang].page} ${currentPage} / ${totalPages}`;
}

function cycleLanguage() {
    langIndex = (langIndex + 1) % langs.length;
    currentLang = langs[langIndex];
    document.querySelector('.page-title').textContent = translations[currentLang].title;
    renderFlights();
}

function nextPage() {
    if (currentPage < totalPages) {
        currentPage++;
        renderFlights();
    } else {
        currentPage = 1;
        cycleLanguage(); // Change lang after last page
    }
}

function initWebSocket() {
    const ws = new WebSocket('ws://' + window.location.hostname + '/go/ws/arr');
    ws.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            if (window.updateNewYearStatus) window.updateNewYearStatus(data);

            // Handle server time update
            if (data.server_time) {
                const clockElem = document.getElementById('clock');
                const dateElem = document.getElementById('date');
                if (clockElem) clockElem.textContent = data.server_time;
                if (dateElem) {
                    const now = new Date();
                    dateElem.textContent = now.toLocaleDateString('ru-RU');
                }
                return;
            }

            if (Array.isArray(data)) {
                lastFlights = data;
                totalPages = Math.ceil(lastFlights.length / FLIGHTS_PER_PAGE) || 1;
                if (currentPage > totalPages) currentPage = 1;
                renderFlights();
                document.getElementById('connectionStatus').textContent = 'Connected';
                document.getElementById('connectionStatus').style.color = '#2ecc71';
            }
        } catch (e) { console.error(e); }
    };
    ws.onclose = () => {
        document.getElementById('connectionStatus').textContent = 'Disconnected';
        document.getElementById('connectionStatus').style.color = '#e74c3c';
        setTimeout(initWebSocket, 5000);
    };
}

document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();

    // Page rotation
    setInterval(nextPage, PAGE_DISPLAY_TIME);
});
