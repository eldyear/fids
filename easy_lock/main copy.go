package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"sync"
	"time"

	"github.com/skip2/go-qrcode"
)

type AppState struct {
	mu            sync.Mutex
	RemainingTime int    `json:"remaining_seconds"`
	IsLocked      bool   `json:"is_locked"`
	QRCodeBase64  string `json:"qr_code"`
}

var state = AppState{
	RemainingTime: 0,
	IsLocked:      true,
}

// Генерирует QR и превращает его в строку Base64
func generateQR(text string) string {
	png, err := qrcode.Encode(text, qrcode.Medium, 256)
	if err != nil {
		return ""
	}
	return base64.StdEncoding.EncodeToString(png)
}

const htmlAdmin = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ReadyBoard Admin</title>
    <style>
        body { font-family: sans-serif; text-align: center; background: #121212; color: white; }
        .card { background: #1e1e1e; padding: 20px; border-radius: 15px; display: inline-block; margin-top: 20px; border: 1px solid #333; }
        .status { font-size: 24px; padding: 10px; margin: 10px; border-radius: 5px; }
        .locked { color: #ff6666; border: 1px solid #ff6666; }
        .unlocked { color: #66ff66; border: 1px solid #66ff66; }
        .qr-box { background: white; padding: 10px; margin-top: 15px; border-radius: 10px; display: inline-block; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Управление ReadyBoard</h1>
        <div class="status {{if .IsLocked}}locked{{else}}unlocked{{end}}">
            {{if .IsLocked}}ЗАБЛОКИРОВАНО{{else}}АКТИВНО{{end}}
        </div>
        <p>Времени осталось: <strong>{{.RemainingTime}}</strong> сек.</p>
        <form action="/add" method="GET">
            <input type="number" name="seconds" value="60">
            <button type="submit">Добавить время</button>
        </form>
        <div class="qr-box">
            <p style="color: black; margin: 0 0 5px 0;">Текущий QR:</p>
            <img src="data:image/png;base64,{{.QRCodeBase64}}" width="150"/>
        </div>
    </div>
</body>
</html>
`

func main() {
	// Генерируем тестовую ссылку (потом заменим на реальную оплату)
	state.QRCodeBase64 = generateQR("https://mbank.kg/pay/readyboard_test")

	go ticker()

	http.HandleFunc("/", indexHandler)
	http.HandleFunc("/status", getStatus)
	http.HandleFunc("/add", addTime)

	fmt.Println("🚀 Бэкенд запущен: http://localhost:8080")
	http.ListenAndServe("0.0.0.0:8080", nil)
}

func ticker() {
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

func addTime(w http.ResponseWriter, r *http.Request) {
	secStr := r.URL.Query().Get("seconds")
	var sec int
	fmt.Sscanf(secStr, "%d", &sec)
	state.mu.Lock()
	state.RemainingTime += sec
	state.IsLocked = false
	state.mu.Unlock()
	http.Redirect(w, r, "/", http.StatusSeeOther)
}
