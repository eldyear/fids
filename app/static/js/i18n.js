// Translations Dictionary
const translations = {
    ru: {
        // Dashboard
        dashboard: "Панель управления",
        home: "Главная",
        dailyPlan: "План на день",
        templates: "Шаблоны",
        generateSchedule: "Создать расписание",
        airlines: "Авиакомпании",
        cities: "Города",
        gates: "Выходы",
        desks: "Стойки",
        logout: "Выход",

        // Home Page Widgets
        totalFlightsToday: "Всего рейсов сегодня",
        updatedJustNow: "Обновлено только что",
        departuresWidget: "Вылеты",
        arrivalsWidget: "Прилеты",
        today: "Сегодня",
        activeGatesWidget: "Активные выходы",
        inUse: "В использовании",
        flightsByCity: "Рейсы по городам",
        airlineDistribution: "Распределение по авиакомпаниям",
        flightStatusesToday: "Статусы рейсов сегодня",
        onTimeStatus: "Вовремя",
        delayedStatus: "Задержка",
        boardingStatus: "Посадка",
        departedStatus: "Вылетел",
        arrivedStatus: "Прибыл",
        cancelledStatus: "Отменен",

        // Chart labels
        departuresChart: "Вылеты",
        arrivalsChart: "Прилеты",

        // Daily Plan
        departures: "Вылеты",
        arrivals: "Прилеты",
        importFromAPI: "Импорт из API",
        addFlight: "Добавить рейс",
        export: "Экспорт",

        // Table Headers
        airline: "Авиакомпания",
        time: "Время",
        flight: "Рейс",
        route: "Маршрут",
        estTime: "Ожид. время",
        status: "Статус",
        gate: "Выход",
        desk: "Стойка",
        actions: "Действия",

        // Actions
        edit: "Редактировать",
        delete: "Удалить",
        cancel: "Отмена",
        save: "Сохранить",

        // Accordion
        gatesCSV: "Выходы (через запятую)",
        desksCSV: "Стойки регистрации (через запятую)",
        skyPriorityDesks: "Стойки Sky Priority",
        mustBeIncluded: "Должны быть в списке стоек",

        // Status Messages
        saved: "Сохранено",
        saving: "Сохранение...",
        error: "Ошибка",

        // Misc
        noFlights: "Нет рейсов на эту дату",
        loading: "Загрузка...",
        confirmDelete: "Вы уверены, что хотите удалить этот рейс?",
        confirmImport: "Импортировать рейсы из API для"
    },
    en: {
        // Dashboard
        dashboard: "Dashboard",
        home: "Home",
        dailyPlan: "Daily Plan",
        templates: "Templates",
        generateSchedule: "Generate Schedule",
        airlines: "Airlines",
        cities: "Cities",
        gates: "Gates",
        desks: "Desks",
        logout: "Logout",

        // Home Page Widgets
        totalFlightsToday: "Total Flights Today",
        updatedJustNow: "Updated just now",
        departuresWidget: "Departures",
        arrivalsWidget: "Arrivals",
        today: "Today",
        activeGatesWidget: "Active Gates",
        inUse: "In use",
        flightsByCity: "Flights by City",
        airlineDistribution: "Airline Distribution",
        flightStatusesToday: "Flight Statuses Today",
        onTimeStatus: "On Time",
        delayedStatus: "Delayed",
        boardingStatus: "Boarding",
        departedStatus: "Departed",
        arrivedStatus: "Arrived",
        cancelledStatus: "Cancelled",

        // Chart labels
        departuresChart: "Departures",
        arrivalsChart: "Arrivals",

        // Daily Plan
        departures: "Departures",
        arrivals: "Arrivals",
        importFromAPI: "Import from API",
        addFlight: "Add Flight",
        export: "Export",

        // Table Headers
        airline: "Airline",
        time: "Time",
        flight: "Flight",
        route: "Route",
        estTime: "Est. Time",
        status: "Status",
        gate: "Gate",
        desk: "Desk",
        actions: "Actions",

        // Actions
        edit: "Edit",
        delete: "Delete",
        cancel: "Cancel",
        save: "Save",

        // Accordion
        gatesCSV: "Gates (comma separated)",
        desksCSV: "Check-in Desks (comma separated)",
        skyPriorityDesks: "Sky Priority Desks",
        mustBeIncluded: "Must be included in Check-in Desks",

        // Status Messages
        saved: "Saved",
        saving: "Saving...",
        error: "Error",

        // Misc
        noFlights: "No flights found for this date",
        loading: "Loading...",
        confirmDelete: "Are you sure you want to delete this flight?",
        confirmImport: "Import flights from API for"
    }
};

// Get current language
function getCurrentLanguage() {
    return localStorage.getItem('language') || 'ru';
}

// Set language
function setLanguage(lang) {
    localStorage.setItem('language', lang);
    applyTranslations(lang);
}

// Apply translations to page
function applyTranslations(lang) {
    const t = translations[lang];

    // Update all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (t[key]) {
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                element.placeholder = t[key];
            } else {
                // Preserve child elements (like icons)
                const childNodes = Array.from(element.childNodes);
                const textNode = childNodes.find(node => node.nodeType === Node.TEXT_NODE);
                if (textNode) {
                    textNode.textContent = ' ' + t[key];
                } else {
                    element.innerHTML = t[key];
                }
            }
        }
    });

    // Update page title (optional)
    const titleKey = document.body.getAttribute('data-title-i18n');
    if (titleKey && t[titleKey]) {
        document.title = t[titleKey];
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const currentLang = getCurrentLanguage();
    applyTranslations(currentLang);
});
