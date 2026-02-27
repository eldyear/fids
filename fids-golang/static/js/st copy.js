const translations = {ru: {registrationDesk: "Стойка регистрации", noActiveRegistration: "Нет активной регистрации", direction: "Направление", time: "Вылет", serverTime: "Время:", flightText: "Рейс", status: "Статус", counters: "Стойки", weather: "Погода", currentLang: "Текущий язык:", tooManyFlights: "Упс, ошибка. Слишком много рейсов."}, en: {registrationDesk: "Registration Desk", noActiveRegistration: "No active registration", direction: "Destination", time: "Depart", serverTime: "Time:", flightText: "Flight", status: "Status", counters: "Counters", weather: "Weather", currentLang: "Current language:", tooManyFlights: "Oops, error. Too many flights!"}, ky: {registrationDesk: "Каттоо столу", noActiveRegistration: "Активдүү каттоо жок", direction: "Багыты", time: "Учуу", serverTime: "Убакыт:", flightText: "Каттам", status: "Статус", counters: "Столдор", weather: "Аба ырайы", currentLang: "Учурдагы тил:", tooManyFlights: "Упс, ката. Рейстер өтө көп окшойт!"}};
const langs = ['ru', 'en', 'ky'];
let langIndex = 0;
let currentLang = 'ru';
const LANG_SWITCH_INTERVAL = 15000;
let langTimer;
window.lastFlights = [];
const pathParts = window.location.pathname.split('/');
const deskNumber = pathParts[pathParts.length - 1];

// Функция для сохранения данных в localStorage
function cacheFlightData(data) {
    try {
        localStorage.setItem('cachedFlights', JSON.stringify({
            timestamp: new Date().getTime(),
            data: data,
            deskNumber: deskNumber // сохраняем номер стойки для проверки
        }));
    } catch (e) {
        console.error('Ошибка кеширования:', e);
    }
}

// Функция для получения кешированных данных
function getCachedFlightData() {
    try {
        const cached = localStorage.getItem('cachedFlights');
        if (!cached) return null;
        
        const parsedCache = JSON.parse(cached);
        const now = new Date().getTime();
        
        // Проверяем, что кеш для текущей стойки
        if (parsedCache.deskNumber !== deskNumber) {
            localStorage.removeItem('cachedFlights');
            return null;
        }
        
        // Уменьшаем время кеша до 5 минут
        if (now - parsedCache.timestamp > 5 * 60 * 1000) {
            localStorage.removeItem('cachedFlights');
            return null;
        }

        // Проверяем время вылета рейсов
        const flights = parsedCache.data;
        if (Array.isArray(flights)) {
            const isFlightExpired = flights.some(flight => {
                if (!flight.time1) return true;
                const flightTime = new Date();
                const [hours, minutes] = flight.time1.split(':');
                flightTime.setHours(parseInt(hours), parseInt(minutes), 0);
                return flightTime < now;
            });

            if (isFlightExpired) {
                localStorage.removeItem('cachedFlights');
                return null;
            }
        }
        
        return parsedCache.data;
    } catch (e) {
        console.error('Ошибка получения кеша:', e);
        return null;
    }
}

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
    const options = {hour: '2-digit', minute: '2-digit', hour12: false};
    const timeString = now.toLocaleTimeString('ru-RU', options);
    const localTimeElem = document.getElementById('localTime');
    if (localTimeElem) localTimeElem.textContent = timeString;
}

// Функция для обновления времени сервера
function updateServerTime(serverTime) {
    const localTimeElem = document.getElementById('localTime');
    if (localTimeElem) localTimeElem.textContent = serverTime;
}

function formatTime(timeString) {
    if (!timeString) return '';
    try {
        // Если строка содержит дату и время (например, "0000-01-01T21:40")
        if (timeString.includes('T')) {
            const timePart = timeString.split('T')[1];
            const [hours, minutes] = timePart.split(':');
            return `${hours}:${minutes}`;
        }
        // Если строка содержит только время (например, "21:40")
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
    document.title = `${translations[lang].registrationDesk} ${deskNumber}`;
    const flightInfoContainer = document.getElementById('flightInfo');
    if (!flightInfoContainer) return;
    
    // Обновляем текст для localTimeText
    const localTimeTextElem = document.getElementById('localTimeText');
    if (localTimeTextElem) {
        localTimeTextElem.textContent = translations[lang].serverTime;
    }
    
    if (!window.lastFlights || window.lastFlights.length === 0) {
        const noFlightsTextElem = document.getElementById('no-flights-text');
        if (noFlightsTextElem) {
            noFlightsTextElem.textContent = translations[lang].noActiveRegistration;
            const img = noFlightsTextElem.previousElementSibling;
            if (img && img.tagName === 'IMG') img.alt = translations[lang].noActiveRegistration;
        }
    } else if (window.lastFlights.length >= 1) {
        const flight0 = window.lastFlights[0];
        if (flight0) {
            setTextContent(`.destination-0`, flight0.destination[`name_${lang}`] || flight0.destination.name_ru);
            setTextContent(`.flight-label-0`, translations[lang].flightText + ':');
            setTextContent(`.time-label-0`, translations[lang].time + ':');
            if (flight0.weather) {
                setTextContent(`.weather-label-0`, translations[lang].weather + ':');
                setAltText(`.weather-icon-0`, translations[lang].weather);
            }
        }
        if (window.lastFlights.length === 2) {
            const flight1 = window.lastFlights[1];
            if (flight1) {
                setTextContent(`.destination-1`, flight1.destination[`name_${lang}`] || flight1.destination.name_ru);
                setTextContent(`.flight-label-1`, translations[lang].flightText + ':');
                setTextContent(`.time-label-1`, translations[lang].time + ':');
                if (flight1.weather) {
                    setTextContent(`.weather-label-1`, translations[lang].weather + ':');
                    setAltText(`.weather-icon-1`, translations[lang].weather);
                }
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
    let weatherHTML = '';
    if (flight.weather && flight.weather.icon && flight.weather.temp !== null) {
        weatherHTML = `
            <div class="weather-info">
                <div class="weather-row">
                    <img src="/go/static/images/weather_icons/SVG/${flight.weather.icon}.svg"
                     alt="${translations[currentLang].weather}" class="weather-icon weather-icon-${index}">
                    <span class="first-text weather-temp-${index}">${Math.round(flight.weather.temp)}°C</span>
                </div>
                <span class="second-text weather-label-${index}">${translations[currentLang].weather}:</span>
            </div>
        `;
    }
    
    // Создаем Map для хранения уникальных номеров стоек и их значений sky_priority
    const stoikaMap = new Map();
    if (flight.stoika) {
        flight.stoika.forEach(s => {
            stoikaMap.set(String(s.number), s.sky_priority);
        });
    }
    
    // Получаем значение sky_priority для текущей стойки
    const hasSkyPriority = stoikaMap.has(String(deskNumber)) && stoikaMap.get(String(deskNumber)) === true;
    
    console.log(`Рейс ${index}: hasSkyPriority = ${hasSkyPriority}, deskNumber = ${deskNumber}`);
    console.log(`Рейс ${index}: stoikaMap =`, stoikaMap);
    
    // Если есть sky_priority=true, применяем специальный шаблон
    if (hasSkyPriority) {
        console.log(`Рейс ${index}: Применяем шаблон Sky Priority`);
        return `
            <div class="check-in-header sky-priority">
                <div class="priority-logo-container ${flight.airline}">
                    <img src="/go/static/images/airlines/${flight.airline}.svg" alt="Airline Logo" class="airline-logo">
                </div>
                <div class="sky-priority-logo">
                    <img src="/go/static/images/sky_priority.svg" alt="Sky Priority" class="sky-priority-logo">
                </div>
            </div>
            <div class="destination-container">
                <div class="destination destination-${index}">${initialCityName}</div>
                <div class="flight-number sky-priority-flight-number flight-number-${index}">${flight.flight}</div>
            </div>
            <div class="time-weather-container">
                <div>
                    <div class="flight-time alighn-left flight-time-${index}">${formatTime(flight.time1)}</div>
                    <div class="second-text alighn-left time-label-${index}">${translations[currentLang].time}:</div>
                </div>
                <div>
                    ${weatherHTML}
                </div>
            </div>
        `;
    } else {
        // Стандартный шаблон без sky_priority
        // Проверяем, является ли это single-flight (один рейс)
        const isSingleFlight = window.lastFlights && window.lastFlights.length === 1;
        
        // Если это single-flight, перемещаем номер рейса под destination
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
                    <div>
                        ${weatherHTML}
                    </div>
                </div>
            `;
        } else {
            // Стандартный шаблон для нескольких рейсов
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
                        <div class="second-text alighn-left time-label-${index}">${translations[currentLang].time}:</div>
                    </div>
                    <div>
                        ${weatherHTML}
                    </div>
                </div>
            `;
        }
    }
}

function updateFlightInfo(flight, index) {
    // Создаем Map для хранения уникальных номеров стоек и их значений sky_priority
    const stoikaMap = new Map();
    if (flight.stoika) {
        flight.stoika.forEach(s => {
            stoikaMap.set(String(s.number), s.sky_priority);
        });
    }
    
    // Получаем значение sky_priority для текущей стойки
    const hasSkyPriority = stoikaMap.has(String(deskNumber)) && stoikaMap.get(String(deskNumber)) === true;
    
    // Обновляем классы в зависимости от наличия sky_priority
    const flightInfo = document.querySelector(`.flight-info-${index}`);
    if (flightInfo) {
        if (hasSkyPriority) {
            flightInfo.classList.add('sky-priority-body');
        } else {
            flightInfo.classList.remove('sky-priority-body');
        }
    }
    
    // Обновляем остальную информацию о рейсе
    const destinationElement = document.querySelector(`.destination-${index}`);
    if (destinationElement) {
        destinationElement.textContent = flight.destination[`name_${currentLang}`] || flight.destination.name_ru;
    }
    
    const flightNumberElement = document.querySelector(`.flight-number-${index}`);
    if (flightNumberElement) {
        flightNumberElement.textContent = flight.flight;
    }
    
    const flightTimeElement = document.querySelector(`.flight-time-${index}`);
    if (flightTimeElement) {
        flightTimeElement.textContent = formatTime(flight.time1);
    }
    
    // Обновляем информацию о погоде
    if (flight.weather && flight.weather.icon && flight.weather.temp !== null) {
        const weatherIconElement = document.querySelector(`.weather-icon-${index}`);
        if (weatherIconElement) {
            weatherIconElement.src = `/go/static/images/weather_icons/SVG/${flight.weather.icon}.svg`;
        }
        
        const weatherTempElement = document.querySelector(`.weather-temp-${index}`);
        if (weatherTempElement) {
            weatherTempElement.textContent = `${Math.round(flight.weather.temp)}°C`;
        }
    }
}

function updateFlightInfo(flights) {
    const flightInfo = document.getElementById('flightInfo');
    if (!flightInfo) {
        console.error("Элемент с ID 'flightInfo' не найден.");
        return;
    }
    window.lastFlights = Array.isArray(flights) ? flights : [];
    
    // Проверяем, есть ли у рейса стойка с номером, соответствующим текущей стойке
    const hasSkyPriority = window.lastFlights.some(flight => {
        // Создаем Map для хранения уникальных номеров стоек и их значений sky_priority
        const stoikaMap = new Map();
        if (flight.stoika) {
            flight.stoika.forEach(s => {
                stoikaMap.set(String(s.number), s.sky_priority);
            });
        }
        
        // Получаем значение sky_priority для текущей стойки
        return stoikaMap.has(String(deskNumber)) && stoikaMap.get(String(deskNumber)) === true;
    });
    
    // Добавляем или удаляем класс sky-priority-body
    if (hasSkyPriority) {
        document.body.classList.add('sky-priority-body');
    } else {
        document.body.classList.remove('sky-priority-body');
    }
    
    if (window.lastFlights.length === 0) {
        flightInfo.innerHTML = `
            <div class="no-flights">
                <img src="/go/static/images/wallpaper.jpg" alt="${translations[currentLang].noActiveRegistration}">
               <!-- <div class="no-flights-text" id="no-flights-text">${translations[currentLang].noActiveRegistration}</div> -->
            </div>
        `;
    } else if (window.lastFlights.length === 1) {
        flightInfo.innerHTML = `
            <div class="single-flight flight-block-0">
                ${createFlightHTML(window.lastFlights[0], 0)}
            </div>
        `;
    } else if (window.lastFlights.length === 2) {
        // Проверяем, есть ли у каждого рейса sky_priority=true
        const hasSkyPriority0 = window.lastFlights[0].stoika && 
            window.lastFlights[0].stoika.some(s => String(s.number) === String(deskNumber) && s.sky_priority === true);
        const hasSkyPriority1 = window.lastFlights[1].stoika && 
            window.lastFlights[1].stoika.some(s => String(s.number) === String(deskNumber) && s.sky_priority === true);
        
        flightInfo.innerHTML = `
            <div class="flights-container has-two-flights">
                <div class="half-width flight-block-0">
                    ${createFlightHTML(window.lastFlights[0], 0)}
                </div>
                <div class="flights-divider"></div>
                <div class="half-width flight-block-1">
                    ${createFlightHTML(window.lastFlights[1], 1)}
                </div>
            </div>
        `;
    } else {
        flightInfo.innerHTML = `
            <div class="error-message" id="error-message-text">
                ${translations[currentLang].tooManyFlights}
            </div>
        `;
    }
}

const wsUrl = 'ws://199.1.1.3/go/ws/st/' + deskNumber;
let ws;

function connectWebSocket() {
    console.log(`Попытка подключения к ${wsUrl}`);
    ws = new WebSocket(wsUrl);
    
    // Добавляем пинг каждые 30 секунд
    const pingInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
        }
    }, 30000);
    
    ws.onopen = function() {
        console.log("Соединение WebSocket открыто");
        startLanguageRotation();
        updateFlightInfo(window.lastFlights);
        updateTextsForCurrentLanguage();
    };
    ws.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            // Проверяем, что data не null и существует
            if (!data) {
                showError("Получены пустые данные");
                return;
            }
            
            // Проверяем, является ли сообщение временем сервера
            if (data && 'server_time' in data) {
                updateServerTime(data.server_time);
                return;
            }
            
            // Если это не время сервера, то это данные о рейсах
            cacheFlightData(data); // Кешируем данные
            updateFlightInfo(data);
            showError("Данные успешно обновлены", "success"); // Добавляем индикатор успеха
        } catch (e) {
            console.error("Ошибка обработки данных:", e);
            
            // Пробуем использовать кешированные данные
            const cachedData = getCachedFlightData();
            if (cachedData) {
                updateFlightInfo(cachedData);
                showError("Используются кешированные данные (не более 5 минут)", "warning");
            } else {
                showError(`Ошибка обработки данных: ${e.message}`, "error");
            }
        }
    };
    ws.onerror = function(error) {
        console.error("WebSocket error:", error);
        showError("Ошибка соединения WebSocket");
        
        // Пробуем использовать кешированные данные
        const cachedData = getCachedFlightData();
        if (cachedData) {
            updateFlightInfo(cachedData);
        }
        
        clearInterval(langTimer);
        clearInterval(pingInterval);
        setTimeout(connectWebSocket, 5000);
    };
    ws.onclose = function(event) {
        console.log(`WebSocket connection closed: Code=${event.code}, Reason=${event.reason}`);
        clearInterval(langTimer);
        clearInterval(pingInterval);
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

// Функция для показа ошибок
function showError(message, type = 'error') {
    const existingError = document.querySelector('.error-toast');
    if (existingError) {
        existingError.remove();
    }
    
    const errorDiv = document.createElement('div');
    errorDiv.className = `error-toast ${type}`;
    errorDiv.textContent = message;
    document.body.appendChild(errorDiv);
    
    // Добавляем стили в зависимости от типа сообщения
    if (type === 'warning') {
        errorDiv.style.background = 'rgba(255, 165, 0, 0.1)';
        errorDiv.style.color = '#ff9900';
    } else if (type === 'success') {
        errorDiv.style.background = 'rgba(0, 255, 0, 0.1)';
        errorDiv.style.color = '#008000';
    }
    
    // Удаляем сообщение через 5 секунд
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

document.addEventListener('DOMContentLoaded', function() {
    const deskNumElem = document.getElementById('deskNumber');
     if (deskNumElem) deskNumElem.textContent = deskNumber;
    currentLang = 'ru';
    updateTextsForCurrentLanguage();
    connectWebSocket();
});