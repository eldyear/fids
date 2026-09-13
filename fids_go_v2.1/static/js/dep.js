const translations = {
    ru: {
        title: "Вылеты",
        mainHeader: "ВЫЛЕТЫ",
        AirportName: "Аэропорт Ош",
        Manas: "Аэропорты Кыргызстана",
        TimeTitle: "время:",
        connectionStatus: {
            connecting: "Подключение...",
            connected: "Подключено",
            updated: "Обновлено:",
            closed: "Соединение закрыто",
            error: "Ошибка соединения"
        },
        columns: {
            airline: "Авиакомпания",
            flight: "Рейс",
            destination: "Направление",
            date: "Дата",
            time: "Время",
            counters: "Стойки",
            status: "Статус"
        },
        currentLang: "Текущий язык:",
        pageInfo: "Страница {current} из {total}"
    },
    en: {
        title: "Departures",
        mainHeader: "DEPARTURES",
        AirportName: "Osh Airport",
        Manas: "Airports of Kyrgyzstan",
        TimeTitle: "date/time:",
        connectionStatus: {
            connecting: "Connecting...",
            connected: "Connected",
            updated: "Updated:",
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
        currentLang: "Current language:",
        pageInfo: "Page {current} of {total}"
    },
    ky: {
        title: "Учуулар",
        mainHeader: "УЧУУЛАР",
        AirportName: "Ош Аэропорту",
        Manas: "Кыргызстан аэропорттору",
        TimeTitle: "убакыт:",
        connectionStatus: {
            connecting: "Туташуу...",
            connected: "Туташты",
            updated: "Жаңыртылды:",
            closed: "Туташуу жабылды",
            error: "Туташууда катачылык"
        },
        columns: {
            airline: "Авиакомпания",
            flight: "Каттам",
            destination: "Багыт",
            date: "Дата",
            time: "Убакыт",
            counters: "Стойкалар",
            status: "Статус"
        },
        currentLang: "Учурдагы тил:",
        pageInfo: "Бет {current} {total}дан"
    }
};

// Настройки пагинации
const FLIGHTS_PER_PAGE = 15;
const PAGE_DISPLAY_TIME = 10000; // 10 секунд на страницу

// Состояние приложения
let currentLang = 'ru';
let lastFlights = [];
const langs = ['ru', 'en', 'ky'];
let langIndex = 0;
let currentPage = 1;
let totalPages = 1;
let paginationTimer;
let notificationTimeout;

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
    document.getElementById('mainHeader').textContent = translations[currentLang].mainHeader;
    document.getElementById('AirportName').textContent = translations[currentLang].AirportName;
    document.getElementById('Manas').textContent = translations[currentLang].Manas;
    document.getElementById('TimeTitle').textContent = translations[currentLang].TimeTitle;

    document.getElementById('colAirline').textContent = translations[currentLang].columns.airline;
    document.getElementById('colFlight').textContent = translations[currentLang].columns.flight;
    document.getElementById('colDestination').textContent = translations[currentLang].columns.destination;
    document.getElementById('colDate').textContent = translations[currentLang].columns.date;
    document.getElementById('colTime').textContent = translations[currentLang].columns.time;
    document.getElementById('colCounters').textContent = translations[currentLang].columns.counters;
    document.getElementById('colStatus').textContent = translations[currentLang].columns.status;

    updatePageInfo();
    updateFlightsTable();
}

function updatePageInfo() {
    const pageInfo = document.getElementById('pageInfo');
    if (pageInfo) {
        pageInfo.textContent = translations[currentLang].pageInfo
            .replace('{current}', currentPage)
            .replace('{total}', totalPages);
    }
}

function updateLanguage() {
    langIndex = (langIndex + 1) % langs.length;
    currentLang = langs[langIndex];
    currentPage = 1; // Сброс на первую страницу
    updateInterfaceLanguage();
    startPagination(); // Перезапуск пагинации
}

function updateFlightsTable() {
    const flightsTableBody = document.getElementById('flightsTableBody');
    if (!flightsTableBody) return;

    if (!Array.isArray(lastFlights)) {
        console.error('lastFlights не является массивом:', lastFlights);
        lastFlights = [];
    }

    const startIdx = (currentPage - 1) * FLIGHTS_PER_PAGE;
    const paginatedFlights = lastFlights.slice(startIdx, startIdx + FLIGHTS_PER_PAGE);

    flightsTableBody.innerHTML = '';

    paginatedFlights.forEach(flight => {
        const row = document.createElement('tr');
        const city = flight.destination?.[`name_${currentLang}`] || '';
        const status = (flight.status?.[`name_${currentLang}`] || '').replace(/-/g, ' ');

        row.innerHTML = `
            <td>
                <div class="logo-container">
                    <img src="static/images/airlines/${flight.airline}.svg" alt="Авиакомпания" class="logo">
                </div>
            </td>
            <td>${flight.flight || ''}</td>
            <td>${city}</td>
            <td>${new Date(flight.date1).toLocaleDateString('ru-RU', {
            year: '2-digit',
            month: '2-digit',
            day: '2-digit'
        })}</td>
            <td>
                ${flight.last_time ?
                `<span style="text-decoration: line-through">${formatTime(flight.time1)}</span>  ${formatTime(flight.last_time)}`
                : formatTime(flight.time1)
            }
            </td>
            <td>${Array.isArray(flight.stoika) ? flight.stoika.map(s => s.number).join(', ') : ''}</td>
            <td class="remark">
                <div class="statusdiv ${flight.status?.name_en || ''}">
                    ${status}
                </div>
            </td>
        `;

        flightsTableBody.appendChild(row);
    });
}

function handlePageTurn() {
    if (currentPage < totalPages) {
        currentPage++;
        updateFlightsTable();
        updatePageInfo();
    } else {
        updateLanguage();
    }
}

function startPagination() {
    clearInterval(paginationTimer);
    paginationTimer = setInterval(handlePageTurn, PAGE_DISPLAY_TIME);
}

function initWebSocket() {
    const connectionStatus = document.getElementById('connectionStatus');
    const socket = new WebSocket('ws://' + window.location.hostname + '/go/ws/dep');

    const pingInterval = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
        }
    }, 30000);

    socket.onopen = function () {
        connectionStatus.textContent = `${translations[currentLang].connectionStatus.connected} (${new Date().toLocaleTimeString()})`;
        startPagination();
    };

    socket.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            if (window.updateNewYearStatus) window.updateNewYearStatus(data);

            if (data.type === 'notification') {
                showNotification(data);
                return;
            }

            if (data && data.server_time) {
                const currentTimeElem = document.getElementById('current-time');
                if (currentTimeElem) currentTimeElem.textContent = data.server_time;
                return;
            }

            lastFlights = Array.isArray(data) ? data : [];
            totalPages = Math.ceil(lastFlights.length / FLIGHTS_PER_PAGE) || 1;
            currentPage = 1;

            updateFlightsTable();
            updatePageInfo();
            startPagination();

            connectionStatus.textContent = `${translations[currentLang].connectionStatus.updated} ${new Date().toLocaleTimeString()}`;
        } catch (e) {
            console.error('Ошибка обработки данных:', e);
        }
    };

    socket.onclose = function () {
        connectionStatus.innerHTML = `<span style="color:red">${translations[currentLang].connectionStatus.closed}</span> ${new Date().toLocaleTimeString()}`;
        clearInterval(paginationTimer);
        clearInterval(pingInterval);

        setTimeout(() => {
            location.reload();
        }, 10000);
    };

    socket.onerror = function (error) {
        console.error('WebSocket error:', error);
        connectionStatus.innerHTML = `<span style="color:red">${translations[currentLang].connectionStatus.error}</span> ${new Date().toLocaleTimeString()}`;
        clearInterval(paginationTimer);
        clearInterval(pingInterval);
    };
}

function updateDateTime() {
    const currentDate = document.getElementById('current-date');
    if (currentDate) {
        currentDate.textContent = new Date().toLocaleDateString('ru-RU');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('connectionStatus') ||
        !document.getElementById('flightsTableBody') ||
        !document.getElementById('current-date') ||
        !document.getElementById('current-time')) {
        console.error('Не найдены необходимые элементы DOM');
        return;
    }

    updateInterfaceLanguage();
    initWebSocket();
    updateDateTime();

    setInterval(updateDateTime, 1000);
});

// Улучшенная логика уведомления с анимацией и динамическим стилем
function showNotification(data) {
    let notificationBar = document.getElementById('notification-bar');

    if (!notificationBar) {
        notificationBar = document.createElement('div');
        notificationBar.id = 'notification-bar';

        // Базовые стили позиционирования и анимации перехода
        notificationBar.style.cssText = `
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            padding: 18px 20px;
            text-align: center;
            font-size: 2.2em;
            font-weight: bold;
            z-index: 1000;
            box-shadow: 0 -4px 15px rgba(0,0,0,0.4);
            transform: translateX(-100%);
            transition: transform 0.6s cubic-bezier(0.25, 1, 0.5, 1);
            box-sizing: border-box;
        `;
        document.body.appendChild(notificationBar);
    }

    // Сбрасываем старый таймер, если пришло новое уведомление до истечения 7 секунд
    clearTimeout(notificationTimeout);

    // Определяем имя класса статуса (например, CHECK-IN, DELAYED и т.д.)
    const statusClass = data.status_en || data.status?.name_en || '';

    // Присваиваем класс статуса плашке, чтобы подтянулся background-color из твоих CSS
    notificationBar.className = statusClass;

    const langKey = 'status_' + currentLang;
    const statusText = data[langKey] || data.status_ru || (data.status?.[`name_${currentLang}`] || '');

    const flightLabel = {
        ru: "Рейс",
        en: "Flight",
        ky: "Каттам"
    };

    notificationBar.innerHTML = `
        <span style="opacity: 0.9; margin-right: 15px;">${flightLabel[currentLang] || 'Flight'} ${data.flight}:</span>
        <span style="text-transform: uppercase;">${statusText}</span>
    `;

    // Выезжает слева
    requestAnimationFrame(() => {
        notificationBar.style.transform = 'translateX(0)';
    });

    // Через 7 секунд уезжает дальше вправо
    notificationTimeout = setTimeout(() => {
        notificationBar.style.transform = 'translateX(100%)';

        // После окончания анимации возвращаем элемент за левую границу без прыжков
        setTimeout(() => {
            notificationBar.style.transition = 'none';
            notificationBar.style.transform = 'translateX(-100%)';
            // Возвращаем свойство transition обратно
            requestAnimationFrame(() => {
                notificationBar.style.transition = 'transform 0.6s cubic-bezier(0.25, 1, 0.5, 1)';
            });
        }, 600);
    }, 7000);
}