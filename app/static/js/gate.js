const languages = ['ru', 'ky', 'en'];
let currentLanguageIndex = 0;

const translations = {
    ru: { flight: 'Рейс:', depart: 'Вылет:', weather: 'Погода:', advert: 'Ваша реклама могла бы осветить этот экран!' },
    ky: { flight: 'Каттам:', depart: 'Учуу убакыты:', weather: 'Аба ырайы:', advert: 'Сиздин жарнамаңыз бул экранды жарыктандырмак!' },
    en: { flight: 'Flight:', depart: 'Depart:', weather: 'Weather:', advert: 'Your ad could light up this screen!' }
};

const contentContainer = document.getElementById('content'); // Кэшируем контейнер
const checkinNumber = document.querySelector('.checkin-number'); // Кэшируем элемент с pk

async function switchLanguage() {
    const lang = languages[currentLanguageIndex];
    const stoika = checkinNumber.textContent.trim(); // Получаем pk и удаляем пробелы

    try {
        const response = await fetch(`/get_flight_data_gate/${lang}/${stoika}/`);
        // console.log(`Запрос к серверу: /get_flight_data_check/${lang}/${stoika}/`);

        if (!response.ok) {
            throw new Error(`Ошибка: ${response.status} - ${response.statusText}`);
        }

        const data = await response.json();
        // console.log('Ответ от сервера:', data); // Логируем ответ

        if (data.advert) {
            showAdvert(data.advert); // Если пришла реклама, показываем её
            return;
        }

        if (!data.data || !Array.isArray(data.data)) {
            throw new Error('Ошибка: данные не получены или пустой ответ.');
        }

        updateContent(data.data, lang);
    } catch (error) {
        console.error(error.message); // Логируем ошибку
        showError(error.message);
    }

    currentLanguageIndex = (currentLanguageIndex + 1) % languages.length;
}

function showAdvert(advertText) {
    const advertDiv = document.createElement('div');
    advertDiv.className = 'advert';

    const image = new Image(); // Создаем объект изображения
    image.src = advertImageURL;
    image.alt = 'Реклама';
    image.className = 'advert-image';

    // Если изображение загрузилось успешно, добавляем его в div
    image.onload = () => {
        advertDiv.appendChild(image); // Добавляем изображение
    };

    // Если изображение не загрузилось, показываем только текст
    image.onerror = () => {
        const textDiv = document.createElement('div');
        textDiv.textContent = advertText;
        advertDiv.appendChild(textDiv);
    };

    contentContainer.innerHTML = ''; // Очистка контейнера
    contentContainer.appendChild(advertDiv); // Добавляем div с рекламой
    checkinNumber.classList.remove('half-width', 'full-width'); // Сбрасываем классы
}


function updateContent(flights, lang) {
    contentContainer.innerHTML = ''; // Очистка контейнера

    if (flights.length === 2) {
        checkinNumber.classList.add('half-width');
        checkinNumber.classList.remove('full-width');
    } else {
        checkinNumber.classList.add('full-width');
        checkinNumber.classList.remove('half-width');
    }

    const row = createRow();
    flights.forEach(flight => {
        const flightBlock = createFlightBlock(flight, lang, flights.length);
        row.appendChild(flightBlock);
    });

    contentContainer.appendChild(row);
}


function createRow() {
    const row = document.createElement('div');
    row.className = 'row';
    return row;
}

function createFlightBlock(item, lang, flightCount) {
    const colClass = flightCount === 2 ? 'half-width' : 'full-width';
    const flightDiv = document.createElement('div');
    flightDiv.className = `flight-block ${colClass}`;

    flightDiv.innerHTML = `
        <div class="flight-info">
            <div class="stoika-logo">
                <img src="/static/images/airlines/${item.airline}.svg" alt="Airline Logo" class="airline-logo">
            </div>
            <div class="flight-container">
                <div class="flight-number">${item.flight}</div>
                <div class="second-text">${translations[lang].flight}</div>
            </div>
        </div>
        <div class="destination-container">
            <div class="destination">${item.destination.city_name}</div>
            <div class="iata">${item.destination.iata_code}</div>
        </div>
        <div class="time-weather-container">
            <div>
                <div class="flight-time">${item.time1}</div>
                <div class="second-text">${translations[lang].depart}</div>
            </div>
            <div>
                ${createWeatherContent(item.weather)}
                <div class="second-text">${translations[lang].weather}</div>
            </div>
        </div>`;

    return flightDiv;
}

function createWeatherContent(weather) {
    if (!weather) return '<div class="weather">N/A</div>';
    return `
        <div class="weather">
            <img src="${weather.icon}" alt="Погода" class="weather-icon">
            <span>${weather.temperature}</span>
        </div>`;
}

function showError(message) {
    contentContainer.innerHTML = `<div class="error_400"><h5>${message}</h5></div>`;
    console.error(message); // Логирование для отладки
}

document.addEventListener('DOMContentLoaded', () => {
    switchLanguage(); // Начальный вызов
    setInterval(switchLanguage, 15000); // Переключение каждые 10 секунд
});
