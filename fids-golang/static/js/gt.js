const translations = {
    ru: {
        gate: "Выход на посадку",
        noActiveFlights: "Нет активных рейсов",
        direction: "Направление",
        time: "Вылет",
        serverTime: "Время:",
        flightText: "Рейс",
        status: "Статус",
        gateText: "Выход",
        currentLang: "Текущий язык:",
        tooManyFlights: "Упс, ошибка. Слишком много рейсов."
    },
    en: {
        gate: "Gate",
        noActiveFlights: "No active flights",
        direction: "Destination",
        time: "Depart",
        serverTime: "Time:",
        flightText: "Flight",
        status: "Status",
        gateText: "Gate",
        currentLang: "Current language:",
        tooManyFlights: "Oops, error. Too many flights!"
    },
    ky: {
        gate: "Чыгуу",
        noActiveFlights: "Активдүү рейстер жок",
        direction: "Багыты",
        time: "Учуу",
        serverTime: "Убакыт:",
        flightText: "Каттам",
        status: "Статус",
        gateText: "Чыгуу",
        currentLang: "Учурдагы тил:",
        tooManyFlights: "Упс, ката. Рейстер өтө көп окшойт!"
    }
};
const langs = ['ru', 'en', 'ky'];
let langIndex = 0;
let currentLang = 'ru';
const LANG_SWITCH_INTERVAL = 15000;
let langTimer;
window.lastFlights = [];
const pathParts = window.location.pathname.split('/');
const gateNumber = pathParts[pathParts.length - 1];

// Добавляем стили для ошибок
const errorStyles = `
    <style>
        .error-toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(255, 0, 0, 0.1);
            color: #ff0000;
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            z-index: 1000;
            max-width: 300px;
            opacity: 0.8;
        }
    </style>
`;
document.head.insertAdjacentHTML('beforeend', errorStyles);

function updateLocalTime() {
    const now = new Date();
    const options = { hour: '2-digit', minute: '2-digit', hour12: false };
    const timeString = now.toLocaleTimeString('ru-RU', options);
    const localTimeElem = document.getElementById('localTime');
    if (localTimeElem) localTimeElem.textContent = timeString;
}

function updateServerTime(serverTime) {
    const localTimeElem = document.getElementById('localTime');
    if (localTimeElem) localTimeElem.textContent = serverTime;
}

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
        console.error('Ошибка форматирования времени:', timeString, e);
        return '';
    }
}

function startLanguageRotation() {
    clearInterval(langTimer);
    langTimer = setInterval(() => {
        if (window.lastFlights && window.lastFlights.length > 0) updateLanguage();
    }, LANG_SWITCH_INTERVAL);
}

function updateLanguage() {
    langIndex = (langIndex + 1) % langs.length;
    currentLang = langs[langIndex];
    updateTextsForCurrentLanguage();
}

function updateTextsForCurrentLanguage() {
    const lang = currentLang;
    document.title = `${translations[lang].gate} ${gateNumber}`;
    const flightInfoContainer = document.getElementById('flightInfo');
    if (!flightInfoContainer) return;

    const localTimeTextElem = document.getElementById('localTimeText');
    if (localTimeTextElem) {
        localTimeTextElem.textContent = translations[lang].serverTime;
    }

    if (!window.lastFlights || window.lastFlights.length === 0) {
        const noFlightsTextElem = document.getElementById('no-flights-text');
        if (noFlightsTextElem) {
            noFlightsTextElem.textContent = translations[lang].noActiveFlights;
            const img = noFlightsTextElem.previousElementSibling;
            if (img && img.tagName === 'IMG') img.alt = translations[lang].noActiveFlights;
        }
    } else if (window.lastFlights.length >= 1) {
        const flight0 = window.lastFlights[0];
        if (flight0) {
            setTextContent(`.destination-0`, flight0.destination[`name_${lang}`] || flight0.destination.name_ru);
            setTextContent(`.flight-label-0`, translations[lang].flightText + ':');
            setTextContent(`.time-label-0`, translations[lang].time + ':');
            setTextContent(`.gate-label-0`, translations[lang].gateText + ':');
        }
        if (window.lastFlights.length === 2) {
            const flight1 = window.lastFlights[1];
            if (flight1) {
                setTextContent(`.destination-1`, flight1.destination[`name_${lang}`] || flight1.destination.name_ru);
                setTextContent(`.flight-label-1`, translations[lang].flightText + ':');
                setTextContent(`.time-label-1`, translations[lang].time + ':');
                setTextContent(`.gate-label-1`, translations[lang].gateText + ':');
            }
        }
    } else {
        const errorTextElem = document.getElementById('error-message-text');
        if (errorTextElem) errorTextElem.textContent = translations[lang].tooManyFlights;
    }

    function setTextContent(selector, text) {
        const elem = flightInfoContainer.querySelector(selector);
        if (elem) elem.textContent = text;
    }

    function setAltText(selector, text) {
        const elem = flightInfoContainer.querySelector(selector);
        if (elem) elem.alt = text;
    }
}

function createFlightHTML(flight, index) {
    const initialCityName = flight.destination[`name_${currentLang}`] || flight.destination.name_ru;

    const gateMap = new Map();
    if (flight.gate) {
        flight.gate.forEach(g => {
            gateMap.set(String(g.number), true);
        });
    }

    const isCurrentGate = gateMap.has(String(gateNumber));
    const isSingleFlight = window.lastFlights && window.lastFlights.length === 1; // Определяем, отображается ли только один рейс

    if (isCurrentGate) {
        if (isSingleFlight) {
            return `
                <div class="check-in-header">
                    <div class="logo-container ${flight.airline}">
                        <img src="/go/static/images/airlines/${flight.airline}.svg" alt="Airline Logo" class="airline-logo">
                    </div>
                </div>
                <div class="destination-container">
                    <div class="destination destination-${index}">${initialCityName}</div>
                    <div class="first-text flight-number-${index}">${flight.flight}</div>
                </div>
                <div class="time-weather-container">
                    <div>
                        <div class="flight-time alighn-left flight-time-${index}">${formatTime(flight.time1)}</div>
                        <div class="second-text alighn-left time-label-${index}">${translations[currentLang].time}:</div>
                    </div>
                </div>
            `;
        } else {
            return `
                <div class="check-in-header">
                    <div class="logo-container ${flight.airline}">
                        <img src="/go/static/images/airlines/${flight.airline}.svg" alt="Airline Logo" class="airline-logo">
                    </div>
                    <div class="first-text flight-number-${index}">${flight.flight}</div>
                </div>
                <div class="destination-container">
                    <div class="destination destination-${index}">${initialCityName}</div>
                </div>
                <div class="time-weather-container">
                    <div>
                        <div class="flight-time alighn-left flight-time-${index}">${formatTime(flight.time1)}</div>
                    </div>
                </div>
            `;
        }
    } else {
        return '';
    }
}

function updateFlightInfo(flights) {
    const flightInfo = document.getElementById('flightInfo');
    const body = document.body;
    if (!flightInfo || !body) {
        console.error("Не найдены элементы с ID 'flightInfo' или <body>.");
        return;
    }
    window.lastFlights = Array.isArray(flights) ? flights : [];

    console.log('Все полученные рейсы:', window.lastFlights);

    const activeFlightsForGate = window.lastFlights.filter(flight => {
        if (flight.gate) {
            return flight.gate.some(g => String(g.number) === gateNumber);
        }
        return false;
    });

    console.log('Активные рейсы для гейта:', activeFlightsForGate);

    flightInfo.innerHTML = ''; // Очищаем предыдущее содержимое

    if (activeFlightsForGate.length === 0) {
        flightInfo.innerHTML = `
            <div class="no-flights">
                <img src="/go/static/images/wallpaper.jpg" alt="${translations[currentLang].noActiveFlights}" class="wallpaper">
            </div>
        `;
    } else if (activeFlightsForGate.length === 1) {
        flightInfo.innerHTML = `
            <div class="single-flight flight-block-0">
                ${createFlightHTML(activeFlightsForGate[0], 0)}
            </div>
        `;
    } else if (activeFlightsForGate.length === 2) {
        let html = '<div class="flights-container has-two-flights">';
        activeFlightsForGate.forEach((flight, index) => {
            html += `
                <div class="half-flight flight-block-${index}">
                    ${createFlightHTML(flight, index)}
                </div>
                ${index === 0 ? '<div class="flights-divider"></div>' : ''}
            `;
        });
        html += '</div>';
        flightInfo.innerHTML = html;
    } else if (activeFlightsForGate.length > 2) {
        flightInfo.innerHTML = `
            <div class="error-message" id="error-message-text">
                ${translations[currentLang].tooManyFlights}
            </div>
        `;
    }

    window.lastFlights = activeFlightsForGate;
    updateTextsForCurrentLanguage(); // Обновляем текст после изменения HTML
}

const wsUrl = 'ws://' + window.location.hostname + '/go/ws/gt/' + gateNumber;
let ws;

function connectWebSocket() {
    console.log(`Попытка подключения к ${wsUrl}`);
    ws = new WebSocket(wsUrl);

    const pingInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
        }
    }, 60000);

    ws.onopen = function () {
        console.log("Соединение WebSocket открыто");
        startLanguageRotation();
        updateFlightInfo(window.lastFlights);
        updateTextsForCurrentLanguage();
    };

    ws.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            if (window.updateNewYearStatus) window.updateNewYearStatus(data);

            if (!data) {
                showError("Получены пустые данные");
                updateFlightInfo([]); // Вызываем updateFlightInfo с пустым массивом
                return;
            }

            if (data && 'server_time' in data) {
                updateServerTime(data.server_time);
                return;
            }

            updateFlightInfo(data);
            showError("Данные успешно обновлены", "success");
        } catch (e) {
            console.error("Ошибка обработки данных:", e);
            showError(`Ошибка обработки данных: ${e.message}`, "error");
        }
    };

    ws.onerror = function (error) {
        console.error("WebSocket error:", error);
        showError("Ошибка соединения WebSocket");
        clearInterval(langTimer);
        setTimeout(connectWebSocket, 5000);
    };

    ws.onclose = function (event) {
        console.log(`WebSocket connection closed: Code=${event.code}, Reason=${event.reason}`);
        clearInterval(langTimer);
        if (!event.wasClean && document.getElementById('flightInfo')) {
            document.getElementById('flightInfo').innerHTML =
                `<div class="error-message">Соединение WebSocket закрыто (Code: ${event.code})</div>`;
        } else {
            if (document.getElementById('flightInfo')) {
                updateFlightInfo([]);
            }
        }
        setTimeout(connectWebSocket, 5000);
    };
}

function showError(message, type = 'error') {
    const existingError = document.querySelector('.error-toast');
    if (existingError) {
        existingError.remove();
    }

    const errorDiv = document.createElement('div');
    errorDiv.className = `error-toast ${type}`;
    errorDiv.textContent = message;
    document.body.appendChild(errorDiv);

    if (type === 'warning') {
        errorDiv.style.background = 'rgba(255, 165, 0, 0.1)';
        errorDiv.style.color = '#ff9900';
    } else if (type === 'success') {
        errorDiv.style.background = 'rgba(0, 255, 0, 0.1)';
        errorDiv.style.color = '#008000';
    }

    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

document.addEventListener('DOMContentLoaded', function () {
    const gateNumElem = document.getElementById('gateNumber');
    if (gateNumElem) gateNumElem.textContent = gateNumber;
    currentLang = 'ru';
    updateTextsForCurrentLanguage();
    connectWebSocket();
});