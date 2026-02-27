const languages = {
    ru: {
        title: 'ВЫЛЕТ',
        timeLabel: 'местное время:',
        headings: ['Авиакомпания', 'Рейс', 'Направление', 'Дата', 'Время', 'Стойка', 'Статус'],
        airportInfo: { code: 'OSS/UCFO', name: 'Аэропорт Ош', operator: 'МАНАС' }
    },
    ky: {
        title: 'УЧУП ЧЫГУУ',
        timeLabel: 'убакыт:',
        headings: ['Авиакомпания', 'Каттам', 'Багыты', 'Күнү', 'Убакыт', 'Каттоо', 'Статусу'],
        airportInfo: { code: 'OSS/UCFO', name: 'Ош Аэропорту', operator: 'МАНАС' }
    },
    en: {
        title: 'DEPARTURE',
        timeLabel: 'local date/time:',
        headings: ['Airline', 'Flight', 'Destination', 'Date', 'Time', 'Counter', 'Status'],
        airportInfo: { code: 'OSS/UCFO', name: 'Osh Airport', operator: 'MANAS' }
    }
};

let currentLanguageIndex = 0;
let currentPage = 0;
const rowsPerPage = 15;
const langKeys = Object.keys(languages);
let autoPaginateInterval;

// Создание таблицы
const planeImgSrc = document.getElementById('static-data').dataset.departPlane;

function createTable(lang) {
    const { title, timeLabel, headings, airportInfo } = languages[lang];

    return `
    <table id="table-${lang}" class="table ${lang !== 'ru' ? 'hidden' : ''} text-center roboto-light">
        <thead>
            <tr class="table-bar">
                <th class="text-left" colspan="2">
                    <p class="roboto-light second-text">${airportInfo.code}</p>
                    <p class="roboto-bold first-text">${airportInfo.name}</p>
                    <p class="roboto-light second-text">${airportInfo.operator}</p>
                </th>
                <th class="roboto-bold" colspan="4">
                    <div class="depart">
                        <img src="${planeImgSrc}" alt="Airport Logo" class="depart-logo">
                        <div class="depart-text">${title}</div>
                    </div>
                </th>
                <th class="roboto-light text-right" colspan="3">
                    <p class="roboto-light second-text" id="current-date-${lang}"></p>
                    <p class="roboto-bold first-text" id="current-time-${lang}"></p>
                    <p class="roboto-light second-text">${timeLabel}</p>
                </th>
            </tr>
            <tr class="roboto-light table-header">
                ${headings.map(heading => `<th>${heading}</th>`).join('')}
            </tr>
        </thead>
        <tbody id="tbody-${lang}"></tbody>
    </table>`;
}

// Отображение всех таблиц
function renderTables() {
    const container = document.getElementById('table-container');
    container.innerHTML = langKeys.map(createTable).join('');
}

// Переключение языка
async function switchLanguage() {
    const previousLang = langKeys[currentLanguageIndex];
    document.getElementById(`table-${previousLang}`).classList.add('hidden');

    currentLanguageIndex = (currentLanguageIndex + 1) % langKeys.length;
    const currentLang = langKeys[currentLanguageIndex];

    document.getElementById(`table-${currentLang}`).classList.remove('hidden');
    
    await fetchData(currentLang);
    resetPagination(currentLang);
}

// Получение данных
async function fetchData(language) {
    const url = `/tablo_dep/${language}/`;

    try {
        const response = await fetch(url);
        const data = await response.json();

        updateTable(language, data.data);
    } catch (error) {
        console.error('Ошибка при загрузке данных:', error);
    }
}

// Обновление таблицы
function updateTable(language, data) {
    const tbody = document.getElementById(`tbody-${language}`);
    tbody.innerHTML = data.map((item, index) => {
        let timeDisplay = item.time1;
        let lastTimeDisplay = '';

        if (item.last_time) {
            timeDisplay = `<span style="text-decoration: line-through;">${item.time1}</span>`;
            lastTimeDisplay = ` ${item.last_time}`;
        }

        let stoikaDisplay = item.stoika.map(stoika => {
            const color = stoika.sky_priority ? '#FFD700' : 'inherit';
            return `<span style="color: ${color};">${stoika.stoiki}</span>`;
        }).join(', '); // Добавляем разделитель в виде запятой

        return `
            <tr class="${index < rowsPerPage ? '' : 'hidden'}">
                <td>
                    <div class="logo-container">
                        <img src="/static/images/airlines/${item.airline}.svg" alt="Airline Logo" class="logo">
                    </div>
                </td>
                <td>${item.flight}</td>
                <td>${item.destination.city_name}</td>
                <td>${item.date1}</td>
                <td>${timeDisplay}${lastTimeDisplay}</td>
                <td>${stoikaDisplay}</td>
                <td class="remark">
                    <div class="statusdiv ${item.status.style || ''}">
                        ${item.status.name || ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// Пагинация
function resetPagination(language) {
    currentPage = 0;
    paginateTable(language);
}

function paginateTable(language) {
    const tbody = document.getElementById(`tbody-${language}`);
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.forEach((row, index) => {
        row.classList.toggle('hidden', Math.floor(index / rowsPerPage) !== currentPage);
    });
}

// Главная логика: авто-пагинация + переключение языка
function autoPaginateOrSwitchLanguage() {
    const lang = langKeys[currentLanguageIndex];
    const tbody = document.getElementById(`tbody-${lang}`);
    const rows = tbody.querySelectorAll('tr');

    // Если есть еще страницы — переключаем их
    if ((currentPage + 1) * rowsPerPage < rows.length) {
        currentPage++;
        paginateTable(lang);
    } else {
        // Если страниц больше нет, переключаем язык
        switchLanguage();
    }
}

// Обновление времени
function updateTime() {
    const now = new Date();
    const formattedDate = now.toLocaleDateString('ru-RU');
    const formattedTime = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

    langKeys.forEach(lang => {
        document.getElementById(`current-date-${lang}`).textContent = formattedDate;
        document.getElementById(`current-time-${lang}`).textContent = formattedTime;
    });
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    renderTables();
    switchLanguage();

    updateTime();
    setInterval(updateTime, 1000);

    autoPaginateInterval = setInterval(autoPaginateOrSwitchLanguage, 15000);
});