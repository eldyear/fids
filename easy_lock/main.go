package main

import (
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/joho/godotenv"
	_ "github.com/mattn/go-sqlite3"
	"github.com/skip2/go-qrcode"
)

// --- СТРУКТУРЫ ---

type PaymentLog struct {
	ID        string    `json:"id"`
	Amount    float64   `json:"amount"`
	Seconds   int       `json:"seconds"`
	CreatedAt time.Time `json:"created_at"`
	TimeStr   string    `json:"time_str"`
}

type AppSettings struct {
	PricePerMinute float64
	MaxMinutes     int
	AdminUser      string
	AdminPass      string
}

type AppState struct {
	mu            sync.Mutex
	RemainingTime int          `json:"remaining_seconds"`
	IsLocked      bool         `json:"is_locked"`
	QRCodeBase64  string       `json:"qr_code"`
	Settings      AppSettings  `json:"settings"`
	DB            *sql.DB
}

type MkassaWebhook struct {
	ID     string `json:"id"`
	Amount string `json:"amount"`
	Status string `json:"status"`
}

var state = AppState{
	RemainingTime: 0,
	IsLocked:      true,
}

// --- РАБОТА С БАЗОЙ ДАННЫХ (SQLite) ---

func initDB() {
	db, err := sql.Open("sqlite3", "./data/readyboard.db")
	if err != nil {
		log.Fatal("Ошибка открытия БД:", err)
	}

	query := `
	CREATE TABLE IF NOT EXISTS payments (
		id TEXT PRIMARY KEY,
		amount REAL,
		seconds INTEGER,
		created_at DATETIME
	);`
	_, err = db.Exec(query)
	if err != nil {
		log.Fatal("Ошибка создания таблицы:", err)
	}
	state.DB = db
}

func savePayment(id string, amount float64, seconds int) {
	_, err := state.DB.Exec(
		"INSERT INTO payments (id, amount, seconds, created_at) VALUES (?, ?, ?, ?)",
		id, amount, seconds, time.Now(),
	)
	if err != nil {
		fmt.Printf("❌ Ошибка записи в БД: %v\n", err)
	}
}

// --- ВСПОМОГАТЕЛЬНОЕ ---

func generateQR(text string) string {
	png, err := qrcode.Encode(text, qrcode.Medium, 256)
	if err != nil {
		return ""
	}
	return base64.StdEncoding.EncodeToString(png)
}

func basicAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		user, pass, ok := r.BasicAuth()
		if !ok || user != state.Settings.AdminUser || pass != state.Settings.AdminPass {
			w.Header().Set("WWW-Authenticate", `Basic realm="Restricted"`)
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}
		next.ServeHTTP(w, r)
	}
}

// --- ОБРАБОТЧИКИ (HANDLERS) ---

func mkassaHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		return
	}
	var data MkassaWebhook
	body, _ := io.ReadAll(r.Body)
	json.Unmarshal(body, &data)

	if data.Status == "paid" {
		rawAmount, _ := strconv.ParseFloat(data.Amount, 64)
		somAmount := rawAmount / 100.0 // Тыйыны в сомы

		addedSeconds := int((somAmount * 60.0) / state.Settings.PricePerMinute)
		if state.Settings.MaxMinutes > 0 && addedSeconds > state.Settings.MaxMinutes*60 {
			addedSeconds = state.Settings.MaxMinutes * 60
		}

		state.mu.Lock()
		state.RemainingTime += addedSeconds
		state.IsLocked = false
		state.mu.Unlock()

		savePayment(data.ID, somAmount, addedSeconds)
		fmt.Printf("💰 ПЛАТЕЖ ПРИНЯТ: %.2f сом (+%d сек)\n", somAmount, addedSeconds)
	}
	w.WriteHeader(http.StatusOK)
}

func reportHandler(w http.ResponseWriter, r *http.Request) {
	start := r.URL.Query().Get("from")
	end := r.URL.Query().Get("to")

	rows, err := state.DB.Query(
		"SELECT id, amount, seconds, created_at FROM payments WHERE created_at BETWEEN ? AND ? ORDER BY created_at DESC",
		start+" 00:00:00", end+" 23:59:59",
	)
	if err != nil {
		http.Error(w, "DB Error", 500)
		return
	}
	defer rows.Close()

	var logs []PaymentLog
	var total float64
	for rows.Next() {
		var l PaymentLog
		rows.Scan(&l.ID, &l.Amount, &l.Seconds, &l.CreatedAt)
		l.TimeStr = l.CreatedAt.Format("02.01 15:04")
		logs = append(logs, l)
		total += l.Amount
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"Logs": logs, "Total": total})
}

func updateSettings(w http.ResponseWriter, r *http.Request) {
	p, _ := strconv.ParseFloat(r.URL.Query().Get("price"), 64)
	m, _ := strconv.Atoi(r.URL.Query().Get("max"))
	state.mu.Lock()
	if p > 0 { state.Settings.PricePerMinute = p }
	state.Settings.MaxMinutes = m
	state.mu.Unlock()
	w.WriteHeader(http.StatusOK)
}

func indexHandler(w http.ResponseWriter, r *http.Request) {
	tmpl, _ := template.New("admin").Parse(htmlAdmin)
	state.mu.Lock()
	tmpl.Execute(w, state)
	state.mu.Unlock()
}

func getStatus(w http.ResponseWriter, r *http.Request) {
	state.mu.Lock()
	defer state.mu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(state)
}

func qrImageHandler(w http.ResponseWriter, r *http.Request) {
	qrURL := os.Getenv("QR_PAYMENT_URL")
	png, _ := qrcode.Encode(qrURL, qrcode.Medium, 512)
	w.Header().Set("Content-Type", "image/png")
	w.Write(png)
}

func manualAddHandler(w http.ResponseWriter, r *http.Request) {
    mins, _ := strconv.Atoi(r.URL.Query().Get("minutes"))
    
    state.mu.Lock()
    if mins == 0 {
        state.RemainingTime = 0 // Сброс
    } else {
        state.RemainingTime += mins * 60
    }
    if state.RemainingTime > 0 {
        state.IsLocked = false
    }
    state.mu.Unlock()
    
    w.WriteHeader(http.StatusOK)
}

// --- MAIN ---

func main() {
	godotenv.Load()
	initDB()

	// Установка админа через консоль
	if len(os.Args) > 2 && os.Args[1] == "-setadmin" {
		parts := strings.Split(os.Args[2], ":")
		if len(parts) == 2 {
			fmt.Printf("\nADMIN_USER=%s\nADMIN_PASS=%s\n", parts[0], parts[1])
		}
		return
	}

	// Загрузка конфигов
	state.Settings.AdminUser = os.Getenv("ADMIN_USER")
	state.Settings.AdminPass = os.Getenv("ADMIN_PASS")
	if state.Settings.AdminUser == "" { state.Settings.AdminUser = "admin"; state.Settings.AdminPass = "1234" }
	
	if p, err := strconv.ParseFloat(os.Getenv("DEFAULT_PRICE"), 64); err == nil {
		state.Settings.PricePerMinute = p
	} else {
		state.Settings.PricePerMinute = 1.0
	}

	state.QRCodeBase64 = generateQR(os.Getenv("QR_PAYMENT_URL"))

	go func() {
		for {
			time.Sleep(1 * time.Second)
			state.mu.Lock()
			if state.RemainingTime > 0 {
				state.RemainingTime--
				state.IsLocked = false
			} else {
				state.IsLocked = true
			}
			state.mu.Unlock()
		}
	}()

	http.HandleFunc("/", basicAuth(indexHandler))
	http.HandleFunc("/status", getStatus)
	http.HandleFunc("/report", basicAuth(reportHandler))
	http.HandleFunc("/update_settings", basicAuth(updateSettings))
	http.HandleFunc("/mhook", mkassaHandler)
	http.HandleFunc("/mhook/", mkassaHandler)
	http.HandleFunc("/qr.png", qrImageHandler)
	http.HandleFunc("/manual_add", basicAuth(manualAddHandler))

	fmt.Println("🚀 ReadyBoard OSS запущен на http://localhost:8080")
	log.Fatal(http.ListenAndServe("0.0.0.0:8080", nil))
}

const htmlAdmin = `
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EasyLocker Admin | ReadyBoard</title>
    <style>
        :root {
            --bg-dark: #0f172a;
            --card-bg: #1e293b;
            --accent: #6366f1;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --success: #10b981;
            --danger: #ef4444;
            --border: #334155;
        }
        body { 
            font-family: 'Inter', system-ui, sans-serif; 
            background-color: var(--bg-dark); 
            color: var(--text-main);
            margin: 0; padding: 20px;
            display: flex; justify-content: center;
        }
        .dashboard { width: 100%; max-width: 900px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
        .full-width { grid-column: span 2; }
        
        h1, h2 { margin-top: 0; letter-spacing: -0.5px; }
        .dim { color: var(--text-dim); font-size: 0.85rem; }

        .status-header { display: flex; justify-content: space-between; align-items: center; }
        .timer-display { font-size: 64px; font-weight: 900; color: var(--accent); margin: 10px 0; font-variant-numeric: tabular-nums; }
        .badge { padding: 6px 12px; border-radius: 8px; font-weight: bold; font-size: 12px; }
        .badge-locked { background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid var(--danger); }
        .badge-open { background: rgba(16, 185, 129, 0.1); color: var(--success); border: 1px solid var(--success); }

        .input-box { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 500; color: var(--text-dim); }
        input { 
            background: #0f172a; border: 1px solid var(--border); border-radius: 8px; 
            color: white; padding: 12px; width: 100%; box-sizing: border-box; font-size: 16px; 
        }
        button { 
            background: var(--accent); color: white; border: none; padding: 12px 20px; 
            border-radius: 8px; cursor: pointer; width: 100%; font-weight: 700; transition: 0.2s;
        }
        button:hover { filter: brightness(1.1); }
        .btn-export { background: #475569; margin-top: 10px; font-size: 13px; padding: 8px; }

        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }
        th { text-align: left; color: var(--text-dim); padding: 10px; border-bottom: 2px solid var(--border); }
        td { padding: 12px 10px; border-bottom: 1px solid var(--border); }
        .total-row { font-size: 20px; font-weight: bold; color: var(--success); margin-top: 15px; display: flex; justify-content: space-between; align-items: center;}

        @media print {
            body { background: white; color: black; padding: 0; }
            .card:not(.full-width), button, input, .dim, .status-header { display: none !important; }
            .card.full-width { border: none; width: 100%; box-shadow: none; }
            table { color: black; border: 1px solid #eee; }
            th { color: #333; }
            .total-row { color: black; border-bottom: 2px solid #000; padding-bottom: 10px; }
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="card">
            <div class="status-header">
                <span class="dim">EasyLock OSS v2.2</span>
                <div id="badge" class="badge">Загрузка...</div>
            </div>
            <div id="timer" class="timer-display">00:00:00</div>
            <p class="dim">До блокировки доступа</p>
        </div>

        <div class="card">
            <h2>Тариф и Лимиты</h2>
            <div class="input-box">
                <label>Цена (KGS / мин)</label>
                <input type="number" id="p" value="{{.Settings.PricePerMinute}}" step="0.01">
            </div>
            <div class="input-box">
                <label>Лимит сессии (мин)</label>
                <input type="number" id="m" value="{{.Settings.MaxMinutes}}">
            </div>
            <button onclick="save()">Сохранить настройки</button>
        </div>

        <div class="card">
            <h2>Сервис и Тест</h2>
            <p class="dim">Ручное управление</p>
            <div style="display: flex; gap: 10px; margin-top: 15px;">
                <button onclick="manualAdd(15)" style="background: #475569;">+15 мин</button>
                <button onclick="manualAdd(60)" style="background: #475569;">+1 ч</button>
            </div>
            <button onclick="manualAdd(0)" style="background: var(--danger); margin-top: 10px;">Сбросить (Блок)</button>
        </div>

        <div class="card full-width">
            <h2>Отчеты и Экспорт</h2>
            <div style="display: flex; gap: 15px; align-items: flex-end; margin-bottom: 20px;" class="no-print">
                <div style="flex: 1;">
                    <label>С даты</label>
                    <input type="date" id="df">
                </div>
                <div style="flex: 1;">
                    <label>По дату</label>
                    <input type="date" id="dt">
                </div>
                <div style="flex: 1;">
                    <button onclick="loadReport()" style="background: var(--success);">Сформировать</button>
                </div>
            </div>

            <div id="repArea" style="display:none;">
                <div class="total-row">
                    <span>Итого: <span id="total">0.00</span> KGS</span>
                    <div style="display: flex; gap: 10px;" class="no-print">
                        <button onclick="exportExcel()" class="btn-export">Excel (CSV)</button>
                        <button onclick="window.print()" class="btn-export" style="background:#0ea5e9;">Скачать PDF</button>
                    </div>
                </div>
                <table id="reportTable">
                    <thead>
                        <tr>
                            <th>Дата</th>
                            <th>ID Транзакции</th>
                            <th>Время</th>
                            <th>Сумма (KGS)</th>
                        </tr>
                    </thead>
                    <tbody id="lgs"></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const API = '/easylock'; // Базовый путь для Nginx

        function formatTime(totalSeconds) {
            if (totalSeconds <= 0) return "00:00:00";
            const hrs = Math.floor(totalSeconds / 3600);
            const mins = Math.floor((totalSeconds % 3600) / 60);
            const secs = totalSeconds % 60;
            return [hrs, mins, secs].map(v => String(v).padStart(2, '0')).join(':');
        }

        async function refresh() {
            try {
                const res = await fetch(API + '/status');
                if (!res.ok) throw new Error();
                const data = await res.json();
                
                document.getElementById('timer').innerText = formatTime(data.remaining_seconds);
                
                const b = document.getElementById('badge');
                b.innerText = data.is_locked ? 'ЗАБЛОКИРОВАНО' : 'СИСТЕМА АКТИВНА';
                b.className = 'badge ' + (data.is_locked ? 'badge-locked' : 'badge-open');
            } catch(e) {
                console.error("Ошибка обновления статуса");
            }
        }

        async function save() {
            const p = document.getElementById('p').value;
            const m = document.getElementById('m').value;
            await fetch(API + '/update_settings?price=' + p + '&max=' + m);
            alert('✅ Настройки сохранены');
        }

        async function manualAdd(m) {
            if (m === 0 && !confirm('Сбросить таймер?')) return;
            await fetch(API + '/manual_add?minutes=' + m);
            refresh();
        }

        async function loadReport() {
            const from = document.getElementById('df').value;
            const to = document.getElementById('dt').value;
            if (!from || !to) return alert('Выберите даты');

            const res = await fetch(API + '/report?from=' + from + '&to=' + to);
            const data = await res.json();
            currentReportData = data.Logs || [];
            
            document.getElementById('repArea').style.display = 'block';
            document.getElementById('total').innerText = data.Total.toFixed(2);
            
            let html = currentReportData.length > 0 ? 
                currentReportData.map(l => 
                    '<tr>' +
                        '<td>' + l.time_str + '</td>' +
                        '<td class="dim">' + l.id.substring(0,16) + '...</td>' +
                        '<td>' + formatTime(l.seconds) + '</td>' +
                        '<td><b>' + l.amount.toFixed(2) + '</b></td>' +
                    '</tr>'
                ).join('') : 
                '<tr><td colspan="4" style="text-align:center; padding:20px;" class="dim">Нет транзакций</td></tr>';
            
            document.getElementById('lgs').innerHTML = html;
        }

        function exportExcel() {
            if (!currentReportData.length) return;
            let csv = "\uFEFFДата;ID;Время;Сумма KGS\n";
            currentReportData.forEach(l => {
                csv += l.time_str + ";" + l.id + ";" + formatTime(l.seconds) + ";" + l.amount.toFixed(2) + "\n";
            });
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.setAttribute("download", "report.csv");
            link.click();
        }

        setInterval(refresh, 1000); 
        refresh();
    </script>
</body>
</html>
`