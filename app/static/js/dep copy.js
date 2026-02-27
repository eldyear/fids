const languagesDep = {
    ru: {
        title: 'ВЫЛЕТ',
        timeLabel: 'местное время:',
        headings: ['Авиакомпания', 'Рейс', 'Направление', 'Время', 'Факт время', 'Стойка', 'Статус'],
        airportInfo: { code: 'OSS/UCFO', name: 'Аэропорт Ош', operator: 'МАНАС' }
    },
    ky: {
        title: 'УЧУП ЧЫГУУ',
        timeLabel: 'убакыт:',
        headings: ['Авиакомпания', 'Каттам', 'Багыты', 'Убакыты', 'Так убакыты', 'Каттоо', 'Статусу'],
        airportInfo: { code: 'OSS/UCFO', name: 'Ош Аэропорту', operator: 'МАНАС' }
    },
    en: {
        title: 'DEPARTURE',
        timeLabel: 'local date/time:',
        headings: ['Airline', 'Flight', 'Destination', 'Time', 'Last Time', 'Counter', 'Status'],
        airportInfo: { code: 'OSS/UCFO', name: 'Osh Airport', operator: 'MANAS' }
    }
};

let currentLanguageIndex = 0;
const langKeysDep = Object.keys(languagesDep);
const rowsPerPage = 15;
let currentPage = 0;

const planeImgSrc = document.getElementById('static-data-dep').dataset.departPlane;

function createTable(lang) {
    const { title, timeLabel, headings, airportInfo } = languagesDep[lang];
    const modifiedHeadings = [...headings.slice(0, 6), languagesDep[lang].headings[6]];

    return `
    <table id="table-${lang}" class="table ${lang !== 'ru' ? 'hidden' : ''} text-center roboto-light">
        <thead>
            <tr class="table-bar">
                <th class="text-left">
                    <p class="roboto-light">${airportInfo.code}</p>
                    <p class="roboto-bold">${airportInfo.name}</p>
                    <p class="roboto-light">${airportInfo.operator}</p>
                </th>
                <th class="roboto-bold" colspan="6">
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
                    heading === languagesDep[lang].headings[6] ? `<th colspan="2">${heading}</th>` : `<th>${heading}</th>`).join('')}
            </tr>
        </thead>
        <tbody id="tbody-${lang}"></tbody>
    </table>`;
}

// Функция для отображения всех таблиц
function renderTables() {
    const container = document.getElementById('table-container-dep');
    container.innerHTML = langKeysDep.map(createTable).join('');
}

async function switchLanguage() {
    const previousLang = langKeysDep[currentLanguageIndex];
    document.getElementById(`table-${previousLang}`).classList.add('hidden');

    currentLanguageIndex = (currentLanguageIndex + 1) % langKeysDep.length;
    const currentLang = langKeysDep[currentLanguageIndex];

    document.getElementById(`table-${currentLang}`).classList.remove('hidden');
    
    await fetchData(currentLang);
    resetPagination(currentLang);
}

// Получение данных с сервера
async function fetchData(language) {
    const url = `/tablo_dep/${language}/`;

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
                    <img src="${item.airline.svg_logo}" alt="Логотип авиакомпании" class="logo">
                </div>
            </td>
            <td>${item.flight}</td>
            <td>${item.destination?.city_name || 'N/A'} (${item.destination?.iata_code || 'N/A'})</td>
            <td>${item.time1}</td>
            <td>${item.last_time || ''}</td>
            <td>${item.stoika.join(', ')}</td>
            <td id="${item.status.id || ''}"></td>
            <td>${item.status.name || ''}</td>
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

function autoPaginate() {
    const lang = langKeysDep[currentLanguageIndex];
    const tbody = document.getElementById(`tbody-${lang}`);
    const rows = Array.from(tbody.querySelectorAll('tr'));

    if (currentPage < Math.floor(rows.length / rowsPerPage)) {
        currentPage++;
    } else {
        currentPage = 0;
    }
    paginateTable(lang);
}

renderTables();
setInterval(switchLanguage, 6000);
setInterval(autoPaginate, 3000);
