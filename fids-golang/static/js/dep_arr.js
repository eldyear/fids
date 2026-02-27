const translations = {
    ru: {
        title: "Общее табло",
        AirportName: "Ош Аэропорту",
        Manas: "МАНАС",
        TimeTitle: "время:",
        depHeader: "ВЫЛЕТЫ",
        arrHeader: "Прилеты",
        connectionStatus: {
            connecting: "Подключение...",
            connected: "Подключено",
            updated: "Данные обновлены:",
            closed: "Соединение закрыто",
            error: "Ошибка соединения"
        },
        columns: {
            airline: "А/К",
            flight: "Рейс",
            destination: "Направление",
            date: "Дата",
            time: "Время",
            counters: "Стойки",
            status: "Статус"
        },
        languageButtons: {
            ru: "Русский",
            en: "English",
            ky: "Кыргызча"
        }
    },
    en: {
        title: "Combined Board",
        AirportName: "Osh Airport",
        Manas: "MANAS",
        TimeTitle: "date/time:",
        depHeader: "DEPARTURES",
        arrHeader: "Arrivals",
        connectionStatus: {
            connecting: "Connecting...",
            connected: "Connected",
            updated: "Data updated:",
            closed: "Connection closed",
            error: "Connection error"
        },
        columns: {
            airline: "Airline",
            flight: "Flight",
            destination: "Destination",
            date: "Date",
            time: "Time",
            counters: "Counters",
            status: "Status"
        },
        languageButtons: {
            ru: "Русский",
            en: "English",
            ky: "Кыргызча"
        }
    },
    ky: {
        title: "Бирдиктүү такта",
        AirportName: "Ош Аэропорту",
        Manas: "МАНАС",
        TimeTitle: "убакыт:",
        depHeader: "УЧУУЛАР",
        arrHeader: "Конуулар",
        connectionStatus: {
            connecting: "Туташуу...",
            connected: "Туташты",
            updated: "Маалымат жаңыртылды:",
            closed: "Туташуу жабылды",
            error: "Туташууда катачылык"
        },
        columns: {
            airline: "А/К",
            flight: "Каттам",
            destination: "Багыт",
            date: "Дата",
            time: "Убакыт",
            counters: "Стойкалар",
            status: "Статус"
        },
        languageButtons: {
            ru: "Русский",
            en: "English",
            ky: "Кыргызча"
        }
    }
};

let currentLang = 'ru';
const langs = ['ru', 'en', 'ky'];
let depFlights = [];
let arrFlights = [];
let depSocket = null;
let arrSocket = null;
let pingIntervalDep;
let pingIntervalArr;

// === НАСТРОЙКИ ПАГИНАЦИИ ===
const FLIGHTS_PER_PAGE = 24;
const PAGE_DISPLAY_TIME = 10000; // 10 секунд на страницу
let currentPage = 1;
let totalPages = 1;
let langIndex = 0;
let paginationTimer;

function formatTime(timeString) {
    if (!timeString) return '';
    try {
        if (timeString.includes('T')) {
            const timePart = timeString.split('T')[1];
            const [hours, minutes] = timePart.split(':');
            return `${hours}:${minutes}`;
        }
        const [hours, minutes] = timeString.split(':');
        return `${hours}:${minutes}`;
    } catch (e) {
        console.error('Error formatting time:', e);
        return '';
    }
}

function updateInterfaceLanguage() {
    document.getElementById('combinedTitle').textContent = translations[currentLang].title;
    document.getElementById('combinedMainHeader').textContent = translations[currentLang].combinedMainHeader;
    document.getElementById('AirportName').textContent = translations[currentLang].AirportName;
    document.getElementById('Manas').textContent = translations[currentLang].Manas;
    document.getElementById('TimeTitle').textContent = translations[currentLang].TimeTitle;
    document.getElementById('depHeader').textContent = translations[currentLang].depHeader;
    document.getElementById('arrHeader').textContent = translations[currentLang].arrHeader;

    document.getElementById('depColAirline').textContent = translations[currentLang].columns.airline;
    document.getElementById('depColFlight').textContent = translations[currentLang].columns.flight;
    document.getElementById('depColDestination').textContent = translations[currentLang].columns.destination;
    document.getElementById('depColDate').textContent = translations[currentLang].columns.date;
    document.getElementById('depColTime').textContent = translations[currentLang].columns.time;
    document.getElementById('depColStatus').textContent = translations[currentLang].columns.status;

    document.getElementById('arrColAirline').textContent = translations[currentLang].columns.airline;
    document.getElementById('arrColFlight').textContent = translations[currentLang].columns.flight;
    document.getElementById('arrColDestination').textContent = translations[currentLang].columns.destination;
    document.getElementById('arrColDate').textContent = translations[currentLang].columns.date;
    document.getElementById('arrColTime').textContent = translations[currentLang].columns.time;
    document.getElementById('arrColStatus').textContent = translations[currentLang].columns.status;

    updateAllTablesAndPages();
}

function updatePageInfo() {
    const depPageInfo = document.getElementById('depPageInfo');
    const arrPageInfo = document.getElementById('arrPageInfo');
    if (depPageInfo) {
        depPageInfo.textContent = `${translations[currentLang].depHeader} — ${currentPage} / ${totalPages}`;
    }
    if (arrPageInfo) {
        arrPageInfo.textContent = `${translations[currentLang].arrHeader} — ${currentPage} / ${totalPages}`;
    }
}

function updateLanguage() {
    langIndex = (langIndex + 1) % langs.length;
    currentLang = langs[langIndex];
    currentPage = 1;
    updateInterfaceLanguage();
    startPagination();
}

function updateFlightsTable(direction) {
    const tableBodyId = direction === 'dep' ? 'flightsDepTableBody' : 'flightsArrTableBody';
    const flights = direction === 'dep' ? depFlights : arrFlights;
    const flightsTableBody = document.getElementById(tableBodyId);
    if (!flightsTableBody) return;
    flightsTableBody.innerHTML = '';
    // Пагинация
    const totalPagesForThis = Math.ceil(flights.length / FLIGHTS_PER_PAGE) || 1;
    const startIdx = (currentPage - 1) * FLIGHTS_PER_PAGE;
    const paginatedFlights = flights.slice(startIdx, startIdx + FLIGHTS_PER_PAGE);
    paginatedFlights.forEach(flight => {
        const row = document.createElement('tr');
        const city = flight.destination[`name_${currentLang}`] || '';
        const status = (flight.status?.[`name_${currentLang}`] || '').replace(/-/g, ' ');
        let countersHtml = '';
        if (flight.stoika && flight.stoika.length > 0) {
            const hasSkyPriority = flight.stoika.some(s => s.SkyPriority);
            const stoikaNumbers = flight.stoika.map(s => s.Number).join(', ');
            countersHtml = `<div class="counters-info"><span>${stoikaNumbers}</span>${hasSkyPriority ? '<img src="static/images/skypriority.svg" alt="Sky Priority" class="sky-priority-icon">' : ''}</div>`;
        }
        let gateHtml = '';
        if (flight.gate && flight.gate.length > 0) {
            const gateNumbers = flight.gate.map(g => g.Number).join(', ');
            gateHtml = `<span>${gateNumbers}</span>`;
        }
        const actualTime = flight.last_time || flight.time1;
        const actualDate = flight.last_date || flight.date1;
        row.innerHTML = `
            <td>
                <div class="dep-arr-logo-container">
                    <img src="static/images/airlines/${flight.airline}.svg" alt="${flight.airline}" class="dep-arr-airline-logo" onerror="this.onerror=null;this.src='static/images/airlines/default.svg';">
                   
                </div>
            </td>
            <td>${flight.flight}</td>
            <td>${city}</td>
            <td>${new Date(flight.date1).toLocaleDateString('ru-RU', { year: '2-digit', month: '2-digit', day: '2-digit' })}</td>
            <td>${flight.last_time ? `<span style="text-decoration: line-through">${formatTime(flight.time1)}</span>  ${formatTime(flight.last_time)}` : formatTime(flight.time1)}</td>
            <td>${status}</td>
        `;
        flightsTableBody.appendChild(row);
    });
    return totalPagesForThis;
}

function updateAllTablesAndPages() {
    const depPages = updateFlightsTable('dep');
    const arrPages = updateFlightsTable('arr');
    totalPages = Math.max(depPages, arrPages);
    updatePageInfo();
}

function handlePageTurn() {
    if (currentPage < totalPages) {
        currentPage++;
    } else {
        currentPage = 1;
        updateLanguage();
        return;
    }
    updateAllTablesAndPages();
}

function startPagination() {
    clearInterval(paginationTimer);
    paginationTimer = setInterval(handlePageTurn, PAGE_DISPLAY_TIME);
}

function initWebSocket(direction) {
    const connectionStatus = document.getElementById('connectionStatus');
    const wsUrl = 'ws://' + window.location.hostname + '/go/ws/' + direction;
    // const wsUrl = new WebSocket('ws://' + window.location.host + '/go/ws/');
    console.log('WebSocket URL:', wsUrl);
    let socket;
    let pingInterval;

    if (direction === 'dep') {
        if (depSocket) depSocket.close();
        if (pingIntervalDep) clearInterval(pingIntervalDep);
        socket = new WebSocket(wsUrl);
        depSocket = socket;
    } else { // arr
        if (arrSocket) arrSocket.close();
        if (pingIntervalArr) clearInterval(pingIntervalArr);
        socket = new WebSocket(wsUrl);
        arrSocket = socket;
    }

    socket.onopen = function () {
        console.log(`WebSocket for ${direction} connected.`);
        connectionStatus.innerHTML = translations[currentLang].connectionStatus.connected;
        // Start sending pings to keep the connection alive
        pingInterval = setInterval(() => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send('ping');
            }
        }, 30000); // Send ping every 30 seconds

        if (direction === 'dep') pingIntervalDep = pingInterval;
        else pingIntervalArr = pingInterval;
    };

    socket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (window.updateNewYearStatus) window.updateNewYearStatus(data);
        if (data.server_time) {
            const currentTimeElem = document.getElementById('current-time');
            if (currentTimeElem) currentTimeElem.textContent = data.server_time;
            return;
        } else {
            if (direction === 'dep') {
                depFlights = data;
            } else {
                arrFlights = data;
            }
            updateAllTablesAndPages();
            connectionStatus.innerHTML = `${translations[currentLang].connectionStatus.updated} ${new Date().toLocaleTimeString()}`;
        }
    };

    socket.onclose = function (event) {
        console.log(`WebSocket for ${direction} closed:`, event);
        connectionStatus.innerHTML = `<span style="color:orange">${translations[currentLang].connectionStatus.closed}</span> ${new Date().toLocaleTimeString()}`;
        if (direction === 'dep') {
            if (pingIntervalDep) clearInterval(pingIntervalDep);
        } else {
            if (pingIntervalArr) clearInterval(pingIntervalArr);
        }
        // Attempt to reconnect after a delay
        setTimeout(() => {
            initWebSocket(direction);
        }, 5000); // Reconnect after 5 seconds
    };

    socket.onerror = function (error) {
        console.error(`WebSocket error for ${direction}:`, error);
        connectionStatus.innerHTML = `<span style="color:red">${translations[currentLang].connectionStatus.error}</span> ${new Date().toLocaleTimeString()}`;
        if (direction === 'dep') {
            if (pingIntervalDep) clearInterval(pingIntervalDep);
        } else {
            if (pingIntervalArr) clearInterval(pingIntervalArr);
        }
    };
}

// Function to update date
function updateDateTime() {
    const currentDate = document.getElementById('current-date');
    if (currentDate) {
        currentDate.textContent = new Date().toLocaleDateString(currentLang === 'ru' ? 'ru-RU' : currentLang === 'ky' ? 'ky-KG' : 'en-US');
    }
}

// Initialization on load
document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('connectionStatus') ||
        !document.getElementById('flightsDepTableBody') ||
        !document.getElementById('flightsArrTableBody') ||
        !document.getElementById('current-date') ||
        !document.getElementById('current-time')) {
        console.error('Не найдены необходимые элементы DOM для combined.js');
        return;
    }

    updateInterfaceLanguage();
    initWebSocket('dep');
    initWebSocket('arr');
    updateDateTime();

    setInterval(updateDateTime, 1000); // Update date every second
    startPagination();
});