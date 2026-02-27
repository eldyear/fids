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

// Настройки анимации "Волна"
const STAGGER_MS = 30; // Задержка между символами для эффекта "тык-тык-тык"
const CELL_DELAY_MS = 150; // Задержка между анимацией соседних столбцов
const ROW_DELAY_MS = 50; // Задержка между анимацией соседних строк
const ANIMATION_PEAK_DELAY = 100; // Дополнительная задержка для смены контента

// Состояние приложения
let currentLang = 'ru';
let lastFlights = [];
const langs = ['ru', 'en', 'ky'];
let langIndex = 0;
let currentPage = 1;
let totalPages = 1;
let paginationTimer;
let isLangChange = false; // Флаг для отслеживания смены языка

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
        console.error('Error formatting time:', e);
        return '';
    }
}

// --- Функции Анимации "Волна" ---

/**
 * Превращает текст в HTML-структуру с анимируемыми символами.
 * @param {string} text - Исходный текст.
 */
function wrapChars(text) {
    if (typeof text !== 'string' || text.trim() === '') return '';
    return `<div class="animated-text-container">${text.split('').map(char => 
        `<span class="char-span">${char}</span>`
    ).join('')}</div>`;
}

/**
 * Анимирует обновление ячейки с эффектом "Волны"
 * @param {HTMLElement} cell - Ячейка таблицы (<td>).
 * @param {string} newText - Новый текст.
 * @param {number} totalDelay - Общая задержка перед началом анимации.
 */
function animateCellCharsWave(cell, newText, totalDelay = 0) {
    const container = cell.querySelector('.animated-text-container');
    if (!container) return; 

    // Используем простой текст для сравнения
    const oldText = container.textContent.trim();
    if (oldText === newText.trim() && !isLangChange) {
        // Если текст не изменился и не сменился язык, не анимируем
        return; 
    }

    const oldChars = Array.from(container.querySelectorAll('.char-span'));
    
    // 1. Анимация "Волна" на старом тексте (исчезновение)
    oldChars.forEach((char, index) => {
        setTimeout(() => {
            char.classList.add('wave-active');
        }, totalDelay + index * STAGGER_MS);
    });

    // 2. Смена содержимого в пике анимации
    const totalWaveDelay = totalDelay + (oldChars.length * STAGGER_MS) + ANIMATION_PEAK_DELAY;

    setTimeout(() => {
        // Мгновенная смена текста. Вставляем новый текст, обернутый в span'ы
        // Удаляем внешние div'ы, чтобы оставить только span'ы
        const newWrappedContent = wrapChars(newText).replace(/<div class="animated-text-container">|<\/div>/g, '');
        container.innerHTML = newWrappedContent; 

        const newChars = Array.from(container.querySelectorAll('.char-span'));
        
        // 3. Анимация "Волна" на новом тексте (появление)
        newChars.forEach((char, index) => {
            // Начинаем с активного (поднятого) состояния
            char.classList.add('wave-active');

            // С задержкой снимаем класс, чтобы он плавно опустился
            setTimeout(() => {
                char.classList.remove('wave-active');
            }, index * STAGGER_MS);
        });

    }, totalWaveDelay);
}
// --- Конец Функций Анимации ---

function updateInterfaceLanguage() {
    document.getElementById('mainHeader').textContent = translations[currentLang].mainHeader;
    document.getElementById('AirportName').textContent = translations[currentLang].AirportName;
    document.getElementById('Manas').textContent = translations[currentLang].Manas;
    document.getElementById('TimeTitle').textContent = translations[currentLang].TimeTitle;
    document.getElementById('mainHeader').textContent = translations[currentLang].mainHeader;
    document.getElementById('mainHeader').textContent = translations[currentLang].mainHeader;

    document.getElementById('colAirline').textContent = translations[currentLang].columns.airline;
    document.getElementById('colFlight').textContent = translations[currentLang].columns.flight;
    document.getElementById('colDestination').textContent = translations[currentLang].columns.destination;
    document.getElementById('colDate').textContent = translations[currentLang].columns.date;
    document.getElementById('colTime').textContent = translations[currentLang].columns.time;
    document.getElementById('colCounters').textContent = translations[currentLang].columns.counters;
    document.getElementById('colStatus').textContent = translations[currentLang].columns.status;

    updatePageInfo();
    // При смене языка вызываем updateFlightsTable, которая запустит анимацию
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
    isLangChange = true; // Устанавливаем флаг, что это смена языка
    currentPage = 1; // Сброс на первую страницу
    updateInterfaceLanguage();
    startPagination(); // Перезапуск пагинации
}

function updateFlightsTable() {
    const flightsTableBody = document.getElementById('flightsTableBody');
    if (!flightsTableBody) return;

    if (!Array.isArray(lastFlights)) {
        lastFlights = [];
    }

    const startIdx = (currentPage - 1) * FLIGHTS_PER_PAGE;
    const paginatedFlights = lastFlights.slice(startIdx, startIdx + FLIGHTS_PER_PAGE);
    
    // 1. ПОЛНЫЙ РЕНДЕР: При первой загрузке или если нет строк
    if (flightsTableBody.children.length === 0) {
        flightsTableBody.innerHTML = '';
        
        paginatedFlights.forEach(flight => {
            const row = document.createElement('tr');
            const city = flight.destination[`name_${currentLang}`] || '';
            const statusText = (flight.status?.[`name_${currentLang}`] || '').replace(/-/g, ' ');
            const timeDisplay = flight.last_time ? 
                `${formatTime(flight.time1)} ${formatTime(flight.last_time)}`
                : formatTime(flight.time1);

            row.innerHTML = `
                <td>
                    <div class="logo-container">
                        <img src="static/images/airlines/${flight.airline}.svg" alt="Авиакомпания" class="logo">
                    </div>
                </td>
                <td>${wrapChars(flight.flight || '')}</td>
                <td>${wrapChars(city)}</td>
                <td>${wrapChars(new Date(flight.date1).toLocaleDateString('ru-RU', {
                    year: '2-digit',
                    month: '2-digit',
                    day: '2-digit'
                }))}</td>
                <td>${wrapChars(timeDisplay)}</td>
                <td>${wrapChars(Array.isArray(flight.stoika) ? flight.stoika.map(s => s.number).join(', ') : '')}</td>
                <td class="remark">
                    <div class="statusdiv ${flight.status.name_en || ''}">${wrapChars(statusText)}</div>
                </td>
            `;
            flightsTableBody.appendChild(row);
        });

    } else {
        // 2. АНИМАЦИЯ: При пагинации, смене языка или обновлении WebSocket
        triggerWaveAnimation(paginatedFlights);
    }
}

/**
 * Запускает анимацию "Волна" на всех строках таблицы.
 */
function triggerWaveAnimation(paginatedFlights) {
    const flightsTableBody = document.getElementById('flightsTableBody');
    const rows = flightsTableBody.querySelectorAll('tr');

    rows.forEach((row, rowIndex) => {
        const flight = paginatedFlights[rowIndex];
        if (!flight) return;

        // Определяем общую задержку для всей строки
        const rowTotalDelay = rowIndex * ROW_DELAY_MS; 

        // Массив данных для анимации в порядке следования столбцов
        const timeDisplay = flight.last_time ? 
            formatTime(flight.time1) + ' ' + formatTime(flight.last_time)
            : formatTime(flight.time1);

        const newValues = [
            flight.airline || '', // 1. Логотип (не анимируем, но включаем для порядка)
            flight.flight || '', // 2. Рейс
            flight.destination[`name_${currentLang}`] || '', // 3. Направление
            new Date(flight.date1).toLocaleDateString('ru-RU', {year: '2-digit', month: '2-digit', day: '2-digit'}), // 4. Дата
            timeDisplay, // 5. Время
            Array.isArray(flight.stoika) ? flight.stoika.map(s => s.number).join(', ') : '', // 6. Стойки
            (flight.status?.[`name_${currentLang}`] || '').replace(/-/g, ' ') // 7. Статус
        ];

        const cells = row.querySelectorAll('td');

        cells.forEach((cell, cellIndex) => {
            // Пропускаем ячейку с логотипом (первая ячейка)
            if (cellIndex === 0) return;

            const newValue = newValues[cellIndex] || '';
            
            // Дополнительная задержка между столбцами для эффекта "перетекания"
            const cellDelay = cellIndex * CELL_DELAY_MS; 

            // Для ячейки со статусом, ищем контейнер статуса внутри
            const statusDiv = cell.querySelector('.statusdiv');
            
            if (statusDiv) {
                // Если это ячейка статуса, анимируем текст внутри div.statusdiv
                animateCellCharsWave(statusDiv, newValue, rowTotalDelay + cellDelay);
            } else {
                // Иначе анимируем текст в основной ячейке
                animateCellCharsWave(cell, newValue, rowTotalDelay + cellDelay);
            }
        });
    });

    // Сброс флага смены языка после анимации
    isLangChange = false;
}

function handlePageTurn() {
    if (currentPage < totalPages) {
        // Есть еще страницы - переключаем на следующую
        currentPage++;
        isLangChange = false; // При пагинации это НЕ смена языка
        updateFlightsTable();
        updatePageInfo();
    } else {
        // Страницы кончились - меняем язык
        updateLanguage();
    }
}

function startPagination() {
    clearInterval(paginationTimer);
    paginationTimer = setInterval(handlePageTurn, PAGE_DISPLAY_TIME);
}

function initWebSocket() {
    const connectionStatus = document.getElementById('connectionStatus');
    // Используем 'ws' или 'wss' в зависимости от протокола страницы
    const socket = new WebSocket((window.location.protocol === 'https:' ? 'wss' : 'ws') + '://' + window.location.host + '/go/ws/dep');

    // Добавляем пинг каждые 30 секунд
    const pingInterval = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
        }
    }, 30000);

    socket.onopen = function() {
        connectionStatus.textContent = `${translations[currentLang].connectionStatus.connected} (${new Date().toLocaleTimeString()})`;
        startPagination();
    };

    socket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);

            // Проверяем, является ли сообщение временем сервера
            if (data.server_time) {
                const currentTimeElem = document.getElementById('current-time');
                if (currentTimeElem) currentTimeElem.textContent = data.server_time;
                return;
            }

            // Убеждаемся, что lastFlights всегда будет массивом
            const newData = Array.isArray(data) ? data : [];
            const isDataUpdate = JSON.stringify(lastFlights) !== JSON.stringify(newData);
            lastFlights = newData;

            totalPages = Math.ceil(lastFlights.length / FLIGHTS_PER_PAGE) || 1;
            
            // Если пришли новые данные, сбрасываем страницу и запускаем анимацию
            if (isDataUpdate) {
                currentPage = 1;
                isLangChange = true; // Заставляем анимацию сработать на весь экран
            }

            updateFlightsTable();
            updatePageInfo();
            startPagination();

            connectionStatus.textContent = `${translations[currentLang].connectionStatus.updated} ${new Date().toLocaleTimeString()}`;
        } catch (e) {
            console.error('Ошибка обработки данных:', e);
            lastFlights = []; // Устанавливаем пустой массив в случае ошибки
            connectionStatus.innerHTML = `<span style="color:red">${translations[currentLang].connectionStatus.error}</span> ${new Date().toLocaleTimeString()}`;
        }
    };

    socket.onclose = function() {
        connectionStatus.innerHTML = `<span style="color:red">${translations[currentLang].connectionStatus.closed}</span> ${new Date().toLocaleTimeString()}`;
        clearInterval(paginationTimer);
        clearInterval(pingInterval);

        // Запланировать перезагрузку страницы через 10 секунд
        setTimeout(() => {
            location.reload();
        }, 10000);
    };

    socket.onerror = function(error) {
        console.error('WebSocket error:', error);
        connectionStatus.innerHTML = `<span style="color:red">${translations[currentLang].connectionStatus.error}</span> ${new Date().toLocaleTimeString()}`;
        clearInterval(paginationTimer);
        clearInterval(pingInterval);
    };
}

// Функция для обновления даты
function updateDateTime() {
    const currentDate = document.getElementById('current-date');
    if (currentDate) {
        currentDate.textContent = new Date().toLocaleDateString('ru-RU');
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
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

    // Запускаем интервал для периодического обновления только даты (каждую секунду)
    setInterval(updateDateTime, 1000);
});