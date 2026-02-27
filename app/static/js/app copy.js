const lang = ['ru', 'ky', 'en'];
let currentLanguageIndex = 0;

// Статические переводы
const translations = {
    ru: {
        airportName: "Аэропорт Ош",
        manas: "МАНАС",
        departure: "ВЫЛЕТ",
        airline: "Авиакомпания",
        flight: "Рейс",
        destination: "Направление",
        date: "Дата",
        time: "Время",
        lastTime: "Факт время",
        counter: "Стойка",
        status: "Статус",
        localTime: "местное время:",
    },
    ky: {
        airportName: "Ош аэропорту",
        manas: "МАНАС",
        departure: "УЧУП ЧЫГУУ",
        airline: "Авиакомпания",
        flight: "Каттам",
        destination: "Багыты",
        date: "Күнү",
        time: "Убакыты",
        lastTime: "Так убакыты",
        counter: "Каттоо",
        status: "Статусу",
        localTime: "убакыт:",
    },
    en: {
        airportName: "Airport Osh",
        manas: "MANAS",
        departure: "DEPARTURE",
        airline: "Airline",
        flight: "Flight",
        destination: "Destination",
        date: "Date",
        time: "Time",
        lastTime: "Last Time",
        counter: "Counter",
        status: "Status",
        localTime: "local date/time:",
    },
};

// Создаем заголовок
function generateHeader(language) {
    const { airportName, manas } = translations[language];
    return `
        <p class="roboto-bold">${airportName}</p>
        <p class="roboto-light">${manas}</p>
    `;
}

// Создаем таблицу для текущего языка
function generateTable(language) {
    const t = translations[language];

    return `
        <table class="table table-striped text-center roboto-light">
            <thead>
                <tr class="table-bar">
                    <th colspan="3">
                        <div class="depart-text">${t.departure}</div>
                    </th>
                    <th colspan="3">
                        <p class="roboto-light" id="current-date-${language}"></p>
                        <p class="roboto-bold" id="current-time-${language}"></p>
                        <p class="roboto-light">${t.localTime}</p>
                    </th>
                </tr>
                <tr class="roboto-light table-header">
                    <th>${t.airline}</th>
                    <th>${t.flight}</th>
                    <th>${t.destination}</th>
                    <th>${t.date}</th>
                    <th>${t.time}</th>
                    <th>${t.lastTime}</th>
                    <th>${t.counter}</th>
                    <th>${t.status}</th>
                </tr>
            </thead>
            <tbody id="tbody-${language}">
                <!-- Данные будут загружены динамически -->
            </tbody>
        </table>
    `;
}

// Переключение языка
function switchLanguage() {
    const container = document.getElementById('tables-container');
    const header = document.getElementById('header');

    const language = lang[currentLanguageIndex];
    currentLanguageIndex = (currentLanguageIndex + 1) % lang.length;

    header.innerHTML = generateHeader(language);
    container.innerHTML = generateTable(language);

    updateTime(language);
}

// Обновление времени
function updateTime(language) {
    const now = new Date();
    const formattedDate = now.toLocaleDateString(language);
    const formattedTime = now.toLocaleTimeString(language, {
        hour: '2-digit',
        minute: '2-digit',
    });

    document.getElementById(`current-date-${language}`).textContent = formattedDate;
    document.getElementById(`current-time-${language}`).textContent = formattedTime;
}

// Запуск приложения
document.addEventListener('DOMContentLoaded', () => {
    switchLanguage(); // Первоначальное заполнение
    setInterval(switchLanguage, 10000); // Переключение языка каждые 10 секунд
});
