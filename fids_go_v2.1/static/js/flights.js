const tableBody = document.getElementById('flightsTableBody');
const timeDisplay = document.getElementById('currentTime');
const dayTabs = document.querySelectorAll('.tab-btn');
const dirTabs = document.querySelectorAll('.filter-btn');

let allFlights = [];
let currentDayFilter = 'today'; // yesterday, today, tomorrow
let currentDirFilter = 'all'; // all, dep, arr
let ws;

// --- Time & Date Helpers ---

function updateClock() {
    const now = new Date();
    timeDisplay.textContent = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}
setInterval(updateClock, 1000);
updateClock();

function getFilterDate(filter) {
    const d = new Date();
    if (filter === 'yesterday') d.setDate(d.getDate() - 1);
    else if (filter === 'tomorrow') d.setDate(d.getDate() + 1);

    // Return YYYY-MM-DD
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// --- Render Logic ---

function getStatusClass(status) {
    const s = (status || '').toUpperCase();
    if (s.includes('BOARDING') || s.includes('POSADKA') || s.includes('ПОСАДКА')) return 'status-boarding';
    if (s.includes('DEPARTED') || s.includes('OTPRAVLEN') || s.includes('ОТПРАВЛЕН')) return 'status-departed';
    if (s.includes('LANDED') || s.includes('PRIZEMLILSYA') || s.includes('ПРИЗЕМЛИЛСЯ') || s.includes('ARRIVED') || s.includes('PRIBIL') || s.includes('ПРИБЫЛ')) return 'status-landed';
    if (s.includes('CANCEL') || s.includes('OTMEN') || s.includes('ОТМЕН')) return 'status-cancelled';
    if (s.includes('DELAY') || s.includes('ZADERZH') || s.includes('ЗАДЕРЖ')) return 'status-delayed';
    if (s.includes('ON TIME') || s.includes('VOVREMYA') || s.includes('ВОВРЕМЯ')) return 'status-ontime';
    return 'status-scheduled';
}

function render() {
    tableBody.innerHTML = '';

    const targetDate = getFilterDate(currentDayFilter);

    const filtered = allFlights.filter(f => {
        // Filter by Date
        // f.date1 is "YYYY-MM-DD"
        if (f.date1 !== targetDate) return false;

        // Filter by Direction
        if (currentDirFilter !== 'all' && f.direction !== currentDirFilter) return false;

        return true;
    });

    // Sort by Time
    filtered.sort((a, b) => (a.time1 || '').localeCompare(b.time1 || ''));

    if (filtered.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="4" style="text-align:center; opacity:0.5; padding: 40px;">Нет рейсов на выбранную дату</td></tr>';
        return;
    }

    filtered.forEach(f => {
        const tr = document.createElement('tr');

        const airlineCode = (f.airline || '').trim().toUpperCase();
        // Use flight number color based on direction? No, stick to global style.

        const destName = f.destination.name_ru || f.destination.name_en;
        const dirText = f.direction === 'dep' ? 'ВЫЛЕТ В' : 'ПРИЛЕТ ИЗ';
        const time = f.time1 ? (f.time1.length > 5 ? f.time1.substr(11, 5) : f.time1) : '--:--';
        const status = f.status.name_ru || f.status.name_en;
        const statusClass = getStatusClass(f.status.name_en);

        tr.innerHTML = `
            <td>
                <div style="display:flex; align-items:center; gap:10px;">
                     <!-- Optional: <img src="static/images/airlines/${airlineCode}.svg" width="30" onerror="this.style.display='none'"> -->
                     <span>${f.flight}</span>
                </div>
            </td>
            <td>
                <div class="flt-dest">${destName}</div>
                <div class="flt-sub">${dirText}</div>
            </td>
            <td><div class="flt-time">${time}</div></td>
            <td><span class="status-badge ${statusClass}">${status}</span></td>
        `;
        tableBody.appendChild(tr);
    });
}

// --- Event Listeners ---

dayTabs.forEach(btn => {
    btn.addEventListener('click', () => {
        dayTabs.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentDayFilter = btn.dataset.day;
        render();
    });
});

dirTabs.forEach(btn => {
    btn.addEventListener('click', () => {
        dirTabs.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentDirFilter = btn.dataset.dir;
        render();
    });
});

// --- WebSocket ---

function connect() {
    ws = new WebSocket('ws://' + window.location.host + '/go/ws/flights');

    ws.onopen = () => console.log('Connected to Flights WS');

    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (Array.isArray(data)) {
            allFlights = data;
            render();
        } else if (data.server_time) {
            // Can sync clock if needed
        }
    };

    ws.onclose = () => {
        setTimeout(connect, 2000);
    };
}

connect();
