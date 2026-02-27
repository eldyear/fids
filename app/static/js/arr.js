const languages = {
    ru: {
        title: 'Прилет',
        timeLabel: 'местное время:',
        headings: ['Авиакомпания', 'Рейс', 'Направление', 'Время', 'Факт время', 'Багаж', 'Статус'],
        airportInfo: { code: 'OSS/UCFO', name: 'Аэропорт Ош', operator: 'МАНАС' }
    },
    ky: {
        title: 'КОНУУ',
        timeLabel: 'убакыт:',
        headings: ['Авиакомпания', 'Каттам', 'Багыты', 'Убакыты', 'Так убакыты', 'Жүк', 'Статусу'],
        airportInfo: { code: 'OSS/UCFO', name: 'Ош Аэропорту', operator: 'МАНАС' }
    },
    en: {
        title: 'ARRIVAL',
        timeLabel: 'local date/time:',
        headings: ['Airline', 'Flight', 'Destination', 'Time', 'Last Time', 'Baggage', 'Status'],
        airportInfo: { code: 'OSS/UCFO', name: 'Osh Airport', operator: 'MANAS' }
    }
};

let currentLanguageIndex = 0;
const langKeys = Object.keys(languages);
const rowsPerPage = 15;
let currentPage = 0;
let autoPaginateInterval;
let languageSwitchInterval;

// Функция для создания таблицы
const planeImgSrc = document.getElementById('static-data').dataset.departPlane;

function createTable(lang) {
    const { title, timeLabel, headings, airportInfo } = languages[lang];
    const modifiedHeadings = [...headings.slice(0, 6), languages[lang].headings[6]];

    return `
    <table id="table-${lang}" class="table ${lang !== 'ru' ? 'hidden' : ''} text-center roboto-light">
        <thead>
            <tr class="table-bar">
                <th class="text-left">
                    <p class="roboto-light">${airportInfo.code}</p>
                    <p class="roboto-bold">${airportInfo.name}</p>
                    <p class="roboto-light">${airportInfo.operator}</p>
                </th>
                <th class="roboto-bold" colspan="5">
                    <div class="depart">
                        <img src="${planeImgSrc}" alt="Airport Logo" class="depart-logo">
                        <div class="depart-text">${title}</div>
                    </div>
                </th>
                <th class="roboto-light text-right" colspan="3">
                    <p class="roboto-light" id="current-date-${lang}"></p>
                    <p class="roboto-bold" id="current-time-${lang}"></p>
                    <p class="roboto-light">${timeLabel}</p>
                </th>
            </tr>
            <tr class="roboto-light table-header">
                ${modifiedHeadings.map((heading, index) => 
                    heading === languages[lang].headings[6] ? `<th colspan="2">${heading}</th>` : `<th>${heading}</th>`).join('')}
            </tr>
        </thead>
        <tbody id="tbody-${lang}"></tbody>
    </table>`;
}

// Функция для отображения всех таблиц
function renderTables() {
    const container = document.getElementById('table-container');
    container.innerHTML = langKeys.map(createTable).join('');
}

// Синхронное переключение языка и данных
async function switchLanguage() {
    const previousLang = langKeys[currentLanguageIndex];
    document.getElementById(`table-${previousLang}`).classList.add('hidden');

    currentLanguageIndex = (currentLanguageIndex + 1) % langKeys.length;
    const currentLang = langKeys[currentLanguageIndex];

    document.getElementById(`table-${currentLang}`).classList.remove('hidden');
    
    await fetchData(currentLang);
    resetPagination(currentLang);
}

// Получение данных с сервера
async function fetchData(language) {
    const url = `/tablo_arr/${language}/`;

    try {
        const response = await fetch(url);
        const data = await response.json();

        updateTable(language, data.data); // Обновляем только видимую таблицу
    } catch (error) {
        console.error('Ошибка при загрузке данных:', error);
    }
}

// Обновление таблицы
function updateTable(language, data) {
    const tbody = document.getElementById(`tbody-${language}`);
    tbody.innerHTML = data.map((item, index) => `
        <tr class="${index < rowsPerPage ? '' : 'hidden'}">
            <td>
                <div class="logo-container">
                    <img src="/static/images/airlines/${item.airline}.svg" alt="Airline Logo" class="logo">
                </div>
            </td>
            <td>${item.flight}</td>
            <td>${item.destination.city_name}</td>
            <td>${item.time1}</td>
            <td>${item.last_time || ''}</td>
            <td>${item.stoika}</td>
            <td class="remark">
                <div class="statusdiv ${item.status.style || ''}">
                    ${item.status.name || ''}
                </div>
            </td>
        </tr>
    `).join('');
}

// Сброс пагинации
function resetPagination(language) {
    currentPage = 0;
    paginateTable(language);
}

// Пагинация таблицы
function paginateTable(language) {
    const tbody = document.getElementById(`tbody-${language}`);
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.forEach((row, index) => {
        row.classList.toggle('hidden', Math.floor(index / rowsPerPage) !== currentPage);
    });
}

// Автопагинация
function autoPaginate() {
    const lang = langKeys[currentLanguageIndex];
    const tbody = document.getElementById(`tbody-${lang}`);
    const rows = tbody.querySelectorAll('tr');

    currentPage = (currentPage + 1) * rowsPerPage >= rows.length ? 0 : currentPage + 1;
    paginateTable(lang);
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
    renderTables(); // Отрисовка таблиц
    switchLanguage(); // Первоначальное переключение языка

    updateTime(); // Обновление времени
    setInterval(updateTime, 1000); // Обновление времени каждую секунду

    languageSwitchInterval = setInterval(switchLanguage, 60000); // Переключение языка каждые 6 секунд
    autoPaginateInterval = setInterval(autoPaginate, 15000); // Пагинация каждые 3 секунды
});