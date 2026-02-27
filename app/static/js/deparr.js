// Конфигурация языков для вылетов и прилетов
const languagesDep = { /* ваш объект языков для вылетов */ };
const languagesArr = { /* ваш объект языков для прилетов */ };

let currentLangIndexDep = 0;
let currentLangIndexArr = 0;
let currentPageDep = 0;
let currentPageArr = 0;
const langKeysDep = Object.keys(languagesDep);
const langKeysArr = Object.keys(languagesArr);
const rowsPerPage = 15; // Количество строк на странице

// AJAX-запрос для получения данных вылетов
function fetchDeparturesData(language, page) {
    $.ajax({
        url: `/get_flight_data/`,
        data: {
            type: 'tablo_dep',
            language: language,
            page: page
        },
        success: function (data) {
            $('#departures-table').html(data.departures_html); // обновление таблицы вылетов
        }
    });
}

// AJAX-запрос для получения данных прилетов
function fetchArrivalsData(language, page) {
    $.ajax({
        url: `/get_flight_data/`,
        data: {
            type: 'tablo_arr',
            language: language,
            page: page
        },
        success: function (data) {
            $('#arrivals-table').html(data.arrivals_html); // обновление таблицы прилетов
        }
    });
}

// Логика переключения языка для вылетов
function toggleLanguageDep() {
    currentLangIndexDep = (currentLangIndexDep + 1) % langKeysDep.length;
    const currentLanguage = langKeysDep[currentLangIndexDep];
    fetchDeparturesData(currentLanguage, currentPageDep);
}

// Логика переключения языка для прилетов
function toggleLanguageArr() {
    currentLangIndexArr = (currentLangIndexArr + 1) % langKeysArr.length;
    const currentLanguage = langKeysArr[currentLangIndexArr];
    fetchArrivalsData(currentLanguage, currentPageArr);
}

// Логика для смены страниц вылетов
function nextPageDep() {
    currentPageDep++;
    const currentLanguage = langKeysDep[currentLangIndexDep];
    fetchDeparturesData(currentLanguage, currentPageDep);
}

// Логика для смены страниц прилетов
function nextPageArr() {
    currentPageArr++;
    const currentLanguage = langKeysArr[currentLangIndexArr];
    fetchArrivalsData(currentLanguage, currentPageArr);
}

// Запуск интервалов для обновления языков и страниц для обеих таблиц
setInterval(toggleLanguageDep, 6000);
setInterval(nextPageDep, 3000);
setInterval(toggleLanguageArr, 6000);
setInterval(nextPageArr, 3000);

// Инициализация первого запроса для вылетов и прилетов
fetchDeparturesData(langKeysDep[currentLangIndexDep], currentPageDep);
fetchArrivalsData(langKeysArr[currentLangIndexArr], currentPageArr);
