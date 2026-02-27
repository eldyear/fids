package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
	_ "github.com/lib/pq"
)

// Структуры данных
type Weather struct {
	Temp     float64   `json:"temp"`
	IconURL  string    `json:"icon"`
	CachedAt time.Time `json:"-"`
}

type City struct {
	ID       int    `json:"id"`
	NameRu   string `json:"name_ru"`
	NameKy   string `json:"name_ky"`
	NameEn   string `json:"name_en"`
	IataCode string `json:"iata_code"`
}

type StoikaInfo struct {
	Number      string `json:"number"`
	SkyPriority bool   `json:"sky_priority"`
}

type GateInfo struct {
	Number string `json:"number"`
}

type FlightStatus struct {
	ID     string `json:"id"`
	NameRu string `json:"name_ru"`
	NameKy string `json:"name_ky"`
	NameEn string `json:"name_en"`
}

type Flight struct {
	ID          int          `json:"id"`
	Direction   string       `json:"direction"`
	Airline     string       `json:"airline"`
	Flight      string       `json:"flight"`
	Destination City         `json:"destination"`
	Date1       string       `json:"date1"`
	Time1       string       `json:"time1"`
	LastDate    string       `json:"last_date,omitempty"`
	LastTime    string       `json:"last_time,omitempty"`
	Status      FlightStatus `json:"status"`
	Stoika      []StoikaInfo `json:"stoika,omitempty"`
	Gate        []GateInfo   `json:"gate,omitempty"`
	Weather     *Weather     `json:"weather,omitempty"`
}

// Структура для отправки времени сервера
// Структура для отправки времени сервера
type ServerTime struct {
	Time    string `json:"server_time"`
	NewYear bool   `json:"new_year"`
}

var timeOverride *time.Time // Для тестирования (переопределение времени)

// Клиент WebSocket
type Client struct {
	conn       *websocket.Conn
	clientType string // "dep", "arr", "st-{номер}", "gt-{номер}", "bg-{номер}", "dispatcher"
}

// Константы для OpenWeatherMap
var (
	openWeatherAPIKey string
	openWeatherURL              = "https://api.openweathermap.org/data/2.5/weather"
	DJANGO_API_POLLING_INTERVAL = 5 * time.Second // Интервал опроса Django API для диспетчера
)

var (
	upgrader = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}
	db        *sql.DB
	clients   = make(map[*Client]bool)
	clientsMu sync.Mutex
	lastHash  string // Для обычных табло (dep/arr/st/gt)

	weatherCache      = make(map[string]*Weather)
	weatherCacheMutex sync.RWMutex
	weatherCacheTTL   = 30 * time.Minute

	// Добавлено для диспетчера
	lastDispatcherData     map[int]Flight // Карта для хранения предыдущего состояния рейсов диспетчера по ID
	lastDispatcherDataHash string         // Для диспетчера, чтобы отправлять обновления только при изменении
)

// getServerTime возвращает текущее время сервера (или переопределенное)
// и флаг New Year (31 дек 23:59 - 1 янв 00:20)
func getServerTime() ServerTime {
	now := time.Now()
	if timeOverride != nil {
		now = *timeOverride
	}

	// Логика проверки Нового Года
	// 31 декабря с 23:59:00
	isDec31 := now.Month() == time.December && now.Day() == 31
	isJan1 := now.Month() == time.January && now.Day() == 1

	isNewYear := false
	if isDec31 {
		if now.Hour() == 23 && now.Minute() == 59 && now.Second() >= 50 {
			isNewYear = true
		}
	} else if isJan1 {
		// Первые 5 минут нового года
		if now.Hour() == 0 && now.Minute() < 5 {
			isNewYear = true
		}
	}

	return ServerTime{
		Time:    now.Format("15:04"),
		NewYear: isNewYear,
	}
}

// Debug handlers
func handleSetTime(w http.ResponseWriter, r *http.Request) {
	tParam := r.URL.Query().Get("t") // expected format: 2006-01-02T15:04:05
	if tParam == "" {
		http.Error(w, "Missing 't' parameter", http.StatusBadRequest)
		return
	}
	t, err := time.Parse("2006-01-02T15:04:05", tParam)
	if err != nil {
		http.Error(w, "Invalid time format. Use 2006-01-02T15:04:05", http.StatusBadRequest)
		return
	}
	timeOverride = &t
	w.Write([]byte(fmt.Sprintf("Time set to: %s", t.Format(time.RFC3339))))
}

func handleResetTime(w http.ResponseWriter, r *http.Request) {
	timeOverride = nil
	w.Write([]byte("Time reset to system time"))
}

func main() {
	// Инициализация базы данных
	var err error

	// Get database configuration from environment variables
	dbHost := os.Getenv("DB_HOST")
	if dbHost == "" {
		dbHost = "db"
	}
	dbUser := os.Getenv("DB_USER")
	if dbUser == "" {
		dbUser = "postgres"
	}
	dbPassword := os.Getenv("DB_PASSWORD")
	if dbPassword == "" {
		dbPassword = "postgres_password_change_this"
	}
	dbName := os.Getenv("DB_NAME")
	if dbName == "" {
		dbName = "oss_db"
	}
	dbPort := os.Getenv("DB_PORT")
	if dbPort == "" {
		dbPort = "5432"
	}

	// Параметры подключения к PostgreSQL
	connStr := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=disable", dbHost, dbUser, dbPassword, dbName, dbPort)
	db, err = sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal("Database connection error:", err)
	}
	defer db.Close()

	// Retry database connection with exponential backoff
	maxRetries := 5
	for i := 0; i < maxRetries; i++ {
		if err = db.Ping(); err == nil {
			log.Println("Database connection successful")
			break
		}
		log.Printf("Database ping error (attempt %d/%d): %v\n", i+1, maxRetries, err)
		if i < maxRetries-1 {
			time.Sleep(time.Duration(math.Pow(2, float64(i))) * time.Second)
		}
	}
	if err != nil {
		log.Fatal("Failed to connect to database after retries:", err)
	}

	r := mux.NewRouter()

	// WebSocket endpoints
	r.HandleFunc("/ws/dep", handleDepWebSocket)
	r.HandleFunc("/ws/arr", handleArrWebSocket)
	// r.HandleFunc("/ws/dep_arr", handleArrWebSocket)
	r.HandleFunc("/ws/st/{stoika}", handleStoikaWebSocket)
	r.HandleFunc("/ws/gt/{gate}", handleGateWebSocket)
	r.HandleFunc("/ws/bg/{stoika}", handleBaggageWebSocket)   // Новый WebSocket endpoint для выдачи багажа
	r.HandleFunc("/ws/dispatcher", handleDispatcherWebSocket) // Новый WebSocket endpoint для диспетчера

	// WebSocket endpoints with /go prefix (for local dev compatibility with production frontend)
	r.HandleFunc("/go/ws/dep", handleDepWebSocket)
	r.HandleFunc("/go/ws/arr", handleArrWebSocket)
	r.HandleFunc("/go/ws/st/{stoika}", handleStoikaWebSocket)
	r.HandleFunc("/go/ws/gt/{gate}", handleGateWebSocket)
	r.HandleFunc("/go/ws/bg/{stoika}", handleBaggageWebSocket)
	r.HandleFunc("/go/ws/dispatcher", handleDispatcherWebSocket)

	// Статические страницы
	r.HandleFunc("/dep", serveDepPage)
	r.HandleFunc("/arr", serveArrPage)
	r.HandleFunc("/st/{stoika}", serveStoikaPage)
	r.HandleFunc("/st/{stoika}", serveStoikaPage)
	r.HandleFunc("/gt/{gate}", serveGatePage)
	r.HandleFunc("/bg/{stoika}", serveBaggagePage) // Новая страница для выдачи багажа
	r.HandleFunc("/dep_arr", serveDepArrPage)
	r.HandleFunc("/dispatcher", serveDispatcherPage) // Новая страница для диспетчера
	r.HandleFunc("/dispatcher", serveDispatcherPage) // Новая страница для диспетчера

	// Debug endpoints
	r.HandleFunc("/debug/set_time", handleSetTime)
	r.HandleFunc("/debug/reset_time", handleResetTime)

	r.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/dep", http.StatusFound)
	})

	// Статические файлы
	// Статические файлы с указанием MIME-типов
	staticHandler := http.StripPrefix("/static/", http.FileServer(http.Dir("./static")))
	safeStaticHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, ".css") {
			w.Header().Set("Content-Type", "text/css")
		} else if strings.HasSuffix(r.URL.Path, ".js") {
			w.Header().Set("Content-Type", "application/javascript")
		} else if strings.HasSuffix(r.URL.Path, ".mp3") {
			w.Header().Set("Content-Type", "audio/mpeg")
		}
		staticHandler.ServeHTTP(w, r)
	})
	r.PathPrefix("/static/").Handler(safeStaticHandler)

	goStaticHandler := http.StripPrefix("/go/static/", http.FileServer(http.Dir("./static")))
	safeGoStaticHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, ".css") {
			w.Header().Set("Content-Type", "text/css")
		} else if strings.HasSuffix(r.URL.Path, ".js") {
			w.Header().Set("Content-Type", "application/javascript")
		} else if strings.HasSuffix(r.URL.Path, ".mp3") {
			w.Header().Set("Content-Type", "audio/mpeg")
		}
		goStaticHandler.ServeHTTP(w, r)
	})
	r.PathPrefix("/go/static/").Handler(safeGoStaticHandler)

	// Инициализация хеша данных
	lastHash = getDataHash()
	lastDispatcherData = make(map[int]Flight) // Инициализация
	// Предварительная загрузка данных для диспетчера, чтобы избежать первоначальных ложных уведомлений
	if initialFlights, err := fetchActiveRegistrationsFromDB(); err == nil {
		for _, flight := range initialFlights {
			lastDispatcherData[flight.ID] = flight
		}
		jsonData, _ := json.Marshal(initialFlights)
		lastDispatcherDataHash = fmt.Sprintf("%x", jsonData)
	} else {
		log.Printf("Ошибка при предварительной загрузке данных для диспетчера: %v", err)
	}

	// Запуск проверки обновлений для обычных табло
	go monitorUpdates()
	// Запуск проверки обновлений для диспетчера
	go pollActiveRegistrations()

	log.Println("Server started on :8080")
	log.Fatal(http.ListenAndServe(":8080", r))
}

// Функция для получения погоды (без изменений)
func getWeather(cityName string) (*Weather, error) {
	// Проверяем кэш
	weatherCacheMutex.RLock()
	cached, exists := weatherCache[cityName]
	weatherCacheMutex.RUnlock()

	if exists && time.Since(cached.CachedAt) < weatherCacheTTL {
		return cached, nil
	}

	// Делаем запрос к API
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(fmt.Sprintf("%s?q=%s&appid=%s&units=metric&lang=ru",
		openWeatherURL, url.QueryEscape(cityName), openWeatherAPIKey))
	if err != nil {
		return nil, fmt.Errorf("weather API request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("weather API returned status %d", resp.StatusCode)
	}

	var data struct {
		Main struct {
			Temp float64 `json:"temp"`
		} `json:"main"`
		Weather []struct {
			Icon string `json:"icon"`
		} `json:"weather"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, fmt.Errorf("failed to decode weather response: %v", err)
	}

	if len(data.Weather) == 0 {
		return nil, fmt.Errorf("no weather data available")
	}

	weather := &Weather{
		Temp:     data.Main.Temp,
		IconURL:  data.Weather[0].Icon,
		CachedAt: time.Now(),
	}

	// Обновляем кэш
	weatherCacheMutex.Lock()
	weatherCache[cityName] = weather
	weatherCacheMutex.Unlock()

	return weather, nil
}

// Обработчики WebSocket
func handleDepWebSocket(w http.ResponseWriter, r *http.Request) {
	handleFlightsWebSocket(w, r, "dep")
}

func handleArrWebSocket(w http.ResponseWriter, r *http.Request) {
	handleFlightsWebSocket(w, r, "arr")
}

func handleStoikaWebSocket(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	stoika := vars["stoika"]

	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}
	defer ws.Close()

	client := &Client{
		conn:       ws,
		clientType: "st-" + stoika,
	}

	registerClient(client)
	defer unregisterClient(client)

	// Отправка времени сервера
	serverTime := getServerTime()
	if err := ws.WriteJSON(serverTime); err != nil {
		log.Printf("Error sending server time: %v", err)
		return
	}

	// Отправка данных для конкретной стойки
	flights, err := fetchFlightsByStoika(stoika)
	if err != nil {
		log.Printf("Error fetching stoika data: %v", err)
		return
	}

	if err := ws.WriteJSON(flights); err != nil {
		log.Printf("Error sending stoika data: %v", err)
		return
	}

	// Запускаем поддержание соединения без жесткого таймаута чтения
	keepConnectionAlive(ws)
}

func handleGateWebSocket(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	gate := vars["gate"]

	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}
	defer ws.Close()

	client := &Client{
		conn:       ws,
		clientType: "gt-" + gate,
	}

	registerClient(client)
	defer unregisterClient(client)

	// Отправка времени сервера
	serverTime := getServerTime()
	if err := ws.WriteJSON(serverTime); err != nil {
		log.Printf("Error sending server time: %v", err)
		return
	}

	// Отправка данных для конкретного гейта
	flights, err := fetchFlightsByGate(gate)
	if err != nil {
		log.Printf("Error fetching gate data: %v", err)
		return
	}

	if err := ws.WriteJSON(flights); err != nil {
		log.Printf("Error sending gate data: %v", err)
		return
	}

	// Запускаем поддержание соединения без жесткого таймаута чтения
	keepConnectionAlive(ws)
}

func handleBaggageWebSocket(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	gate := vars["stoika"]

	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}
	defer ws.Close()

	client := &Client{
		conn:       ws,
		clientType: "bg-" + gate,
	}

	registerClient(client)
	defer unregisterClient(client)

	// Отправка времени сервера
	serverTime := getServerTime()
	if err := ws.WriteJSON(serverTime); err != nil {
		log.Printf("Error sending server time: %v", err)
		return
	}

	// Отправка данных для конкретной стойки (карусели)
	flights, err := fetchFlightsByBaggage(gate)
	if err != nil {
		log.Printf("Error fetching baggage data: %v", err)
		return
	}

	if err := ws.WriteJSON(flights); err != nil {
		log.Printf("Error sending baggage data: %v", err)
		return
	}

	// Запускаем поддержание соединения без жесткого таймаута чтения
	keepConnectionAlive(ws)
}

func handleFlightsWebSocket(w http.ResponseWriter, r *http.Request, direction string) {
	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}
	defer ws.Close()

	client := &Client{
		conn:       ws,
		clientType: direction,
	}

	registerClient(client)
	defer unregisterClient(client)

	// Отправка времени сервера
	serverTime := getServerTime()
	if err := ws.WriteJSON(serverTime); err != nil {
		log.Printf("Error sending server time: %v", err)
		return
	}

	// Отправка данных по направлению
	flights, err := fetchFlightsByDirection(direction)
	if err != nil {
		log.Printf("Error fetching %s data: %v", direction, err)
		return
	}

	if err := ws.WriteJSON(flights); err != nil {
		log.Printf("Error sending %s data: %v", direction, err)
		return
	}

	// Запускаем поддержание соединения без жесткого таймаута чтения
	keepConnectionAlive(ws)
}

// НОВЫЙ обработчик WebSocket для диспетчера
func handleDispatcherWebSocket(w http.ResponseWriter, r *http.Request) {
	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error for dispatcher: %v", err)
		return
	}
	defer func() {
		ws.Close()
		log.Printf("Client disconnected: %s", r.RemoteAddr)
	}()

	client := &Client{
		conn:       ws,
		clientType: "dispatcher", // Указываем тип клиента
	}

	registerClient(client)
	defer unregisterClient(client)

	// Отправка времени сервера
	serverTime := getServerTime()
	if err := ws.WriteJSON(serverTime); err != nil {
		log.Printf("Error sending server time to dispatcher: %v", err)
		return
	}

	// Отправка текущих активных регистраций сразу после подключения
	activeRegistrations, err := fetchActiveRegistrationsFromDB()
	if err != nil {
		log.Printf("Error fetching active registrations for new dispatcher client: %v", err)
		if err := ws.WriteJSON([]Flight{}); err != nil {
			log.Printf("Error sending empty data to new dispatcher client: %v", err)
		}
	} else {
		if err := ws.WriteJSON(activeRegistrations); err != nil {
			log.Printf("Error sending initial active registrations to dispatcher: %v", err)
		}
	}

	// Запускаем поддержание соединения без жесткого таймаута чтения
	keepConnectionAlive(ws)
}

// Регистрация клиента (без изменений)
func registerClient(client *Client) {
	clientsMu.Lock()
	clients[client] = true
	clientsMu.Unlock()
}

// Удаление клиента (без изменений)
func unregisterClient(client *Client) {
	clientsMu.Lock()
	delete(clients, client)
	clientsMu.Unlock()
}

// keepConnectionAlive (без изменений)
func keepConnectionAlive(ws *websocket.Conn) {
	clientID := fmt.Sprintf("ws://%s%s", ws.RemoteAddr().Network(), ws.RemoteAddr().String())
	log.Printf("Client connected: %s", clientID)

	// Определяем интервалы
	timeSendInterval := 15 * time.Second
	pingInterval := 30 * time.Second                          // Установим пинг каждые 30 секунд для надёжности
	readDeadlineInterval := pingInterval + (10 * time.Second) // Таймаут на чтение с запасом

	// Устанавливаем хендлер для Pong-сообщений
	ws.SetPongHandler(func(string) error {
		log.Printf("Pong received from %s", clientID)
		// При получении Pong-пакета сбрасываем ReadDeadline
		ws.SetReadDeadline(time.Now().Add(readDeadlineInterval))
		return nil
	})

	// Горутина для чтения входящих сообщений
	go func() {
		// Мы читаем сообщения, чтобы получать Pong-пакеты и сбросить таймаут
		for {
			_, _, err := ws.ReadMessage()
			if err != nil {
				// Обрабатываем ошибки закрытия соединения
				if !websocket.IsCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway) {
					log.Printf("WebSocket read error from %s: %v", clientID, err)
				}
				ws.Close()
				return
			}
		}
	}()

	// Горутина для отправки сообщений
	timeTicker := time.NewTicker(timeSendInterval)
	pingTicker := time.NewTicker(pingInterval)
	defer timeTicker.Stop()
	defer pingTicker.Stop()

	for {
		select {
		case <-timeTicker.C:
			serverTime := getServerTime()
			ws.SetWriteDeadline(time.Now().Add(5 * time.Second))
			if err := ws.WriteJSON(serverTime); err != nil {
				log.Printf("Error sending server time to %s: %v", clientID, err)
				return
			}
			ws.SetWriteDeadline(time.Time{})
			log.Printf("Server time sent to %s: %s", clientID, serverTime.Time)

		case <-pingTicker.C:
			ws.SetWriteDeadline(time.Now().Add(5 * time.Second))
			if err := ws.WriteControl(websocket.PingMessage, []byte{}, time.Now().Add(5*time.Second)); err != nil {
				log.Printf("Error sending ping to %s: %v", clientID, err)
				return
			}
			ws.SetWriteDeadline(time.Time{})
			log.Printf("Ping sent to %s", clientID)
		}
	}
}

// monitorUpdates (для обычных табло) - без изменений
func monitorUpdates() {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		currentHash := getDataHash()
		if currentHash != lastHash {
			lastHash = currentHash
			broadcastUpdates()
		}
	}
}

// Рассылка обновлений (для обычных табло) - без изменений, т.к. диспетчер теперь получает обновления через pollActiveRegistrations
func broadcastUpdates() {
	// Получаем данные
	depFlights, err := fetchFlightsByDirection("dep")
	if err != nil {
		log.Printf("Error fetching departures: %v", err)
	}

	arrFlights, err := fetchFlightsByDirection("arr")
	if err != nil {
		log.Printf("Error fetching arrivals: %v", err)
	}

	// Получаем текущее время сервера
	serverTime := getServerTime()

	clientsMu.Lock()
	defer clientsMu.Unlock()

	// Создаем список клиентов для удаления
	var clientsToRemove []*Client

	for client := range clients {
		// Диспетчеры обрабатываются отдельно в pollActiveRegistrations
		if client.clientType == "dispatcher" {
			continue
		}

		// Устанавливаем таймаут записи перед отправкой
		client.conn.SetWriteDeadline(time.Now().Add(5 * time.Second))

		// Отправляем время сервера
		if err := client.conn.WriteJSON(serverTime); err != nil {
			log.Printf("Error sending server time: %v", err)
			clientsToRemove = append(clientsToRemove, client)
			continue
		}

		var data interface{}
		switch client.clientType {
		case "dep":
			data = depFlights
		case "arr":
			data = arrFlights
		default:
			if len(client.clientType) > 3 && client.clientType[:3] == "st-" {
				stoika := client.clientType[3:]
				flights, err := fetchFlightsByStoika(stoika)
				if err != nil {
					log.Printf("Error fetching stoika data for broadcast: %v", err)
					continue
				}
				data = flights
				data = flights
			} else if len(client.clientType) > 3 && client.clientType[:3] == "gt-" {
				gate := client.clientType[3:]
				flights, err := fetchFlightsByGate(gate)
				if err != nil {
					log.Printf("Error fetching gate data for broadcast: %v", err)
					continue
				}
				data = flights
			} else if len(client.clientType) > 3 && client.clientType[:3] == "bg-" {
				gate := client.clientType[3:]
				flights, err := fetchFlightsByBaggage(gate)
				if err != nil {
					log.Printf("Error fetching baggage data for broadcast: %v", err)
					continue
				}
				data = flights
			}
		}

		// Отправляем данные о рейсах
		if data != nil {
			if err := client.conn.WriteJSON(data); err != nil {
				log.Printf("Error sending data to %s: %v", client.clientType, err)
				clientsToRemove = append(clientsToRemove, client)
				continue
			}
		}

		// Сбрасываем таймаут записи после успешной отправки
		client.conn.SetWriteDeadline(time.Time{})
	}

	// Удаляем клиентов с ошибками
	for _, client := range clientsToRemove {
		client.conn.Close()
		delete(clients, client)
	}
}

// Функция для получения временного окна (3 часа назад + 30 часов вперед) - без изменений
func getOperationalWindow() (string, string) {
	now := time.Now()
	startWindow := now.Add(-3 * time.Hour)
	endWindow := now.Add(30 * time.Hour)
	return startWindow.Format("2006-01-02 15:04:05"),
		endWindow.Format("2006-01-02 15:04:05")
}

// fetchFlightsByDirection - убираем лишние поля из SELECT
func fetchFlightsByDirection(direction string) ([]Flight, error) {
	start, _ := getOperationalWindow()
	query := `
        SELECT
            COALESCE(i.id, 0),
            COALESCE(i.direction, ''),
            COALESCE(i.airline, ''),
            COALESCE(f.flights, ''),
            COALESCE(c.id, 0),
            COALESCE(c.city_name_ru, ''),
            COALESCE(c.city_name_ky, ''),
            COALESCE(c.city_name_en, ''),
            COALESCE(c.iata_code, ''),
            i.date1, i.time1, i.last_date, i.last_time,
            COALESCE(s.status_id, ''),
            COALESCE(s.name_ru, ''),
            COALESCE(s.name_ky, ''),
            COALESCE(s.name_en, ''),
            NULL as sky_priority
        FROM "InfTablo" i
        JOIN "FlightNumber" f ON i.flight_id = f.id
        JOIN "City" c ON i.destination_id = c.id
        LEFT JOIN "Status" s ON i.status_id = s.id
        WHERE i.direction = $1 AND (
            CASE WHEN i.date1 IS NULL OR i.time1 IS NULL THEN false
                 ELSE make_timestamp(
                    EXTRACT(YEAR FROM i.date1)::int,
                    EXTRACT(MONTH FROM i.date1)::int,
                    EXTRACT(DAY FROM i.date1)::int,
                    EXTRACT(HOUR FROM i.time1)::int,
                    EXTRACT(MINUTE FROM i.time1)::int,
                    EXTRACT(SECOND FROM i.time1)::int
                 ) BETWEEN ($2::timestamp - interval '3 hours') AND ($2::timestamp + interval '30 hours')
                 OR make_timestamp(
                    EXTRACT(YEAR FROM i.date1)::int,
                    EXTRACT(MONTH FROM i.date1)::int,
                    EXTRACT(DAY FROM i.date1)::int,
                    EXTRACT(HOUR FROM i.time1)::int,
                    EXTRACT(MINUTE FROM i.time1)::int,
                    EXTRACT(SECOND FROM i.time1)::int
                 ) - interval '3 hours' BETWEEN ($2::timestamp - interval '3 hours') AND ($2::timestamp + interval '30 hours')
            END
        )
        ORDER BY i.date1, i.time1
    `
	return fetchFlightsWithQuery(query, direction, start)
}

// fetchFlightsByStoika - убираем лишние поля из SELECT
func fetchFlightsByStoika(stoika string) ([]Flight, error) {
	start, _ := getOperationalWindow()
	query := `
        SELECT DISTINCT
            COALESCE(i.id, 0),
            COALESCE(i.direction, ''),
            COALESCE(i.airline, ''),
            COALESCE(f.flights, ''),
            COALESCE(c.id, 0),
            COALESCE(c.city_name_ru, ''),
            COALESCE(c.city_name_ky, ''),
            COALESCE(c.city_name_en, ''),
            COALESCE(c.iata_code, ''),
            i.date1, i.time1, i.last_date, i.last_time,
            COALESCE(s.status_id, ''),
            COALESCE(s.name_ru, ''),
            COALESCE(s.name_ky, ''),
            COALESCE(s.name_en, ''),
            st.sky_priority
        FROM "InfTablo" i
        JOIN "FlightNumber" f ON i.flight_id = f.id
        JOIN "City" c ON i.destination_id = c.id
        LEFT JOIN "Status" s ON i.status_id = s.id
        JOIN "InfTablo_stoika" its ON its.inftablo_id = i.id
        JOIN "Stoiki" st ON its.stoiki_id = st.id
        WHERE st.stoiki = $1 AND (s.name_en = 'CHECK-IN' OR s.name_en = 'CHECK-IN BOARDING') AND (
            CASE WHEN i.date1 IS NULL OR i.time1 IS NULL THEN false
                 ELSE make_timestamp(
                    EXTRACT(YEAR FROM i.date1)::int,
                    EXTRACT(MONTH FROM i.date1)::int,
                    EXTRACT(DAY FROM i.date1)::int,
                    EXTRACT(HOUR FROM i.time1)::int,
                    EXTRACT(MINUTE FROM i.time1)::int,
                    EXTRACT(SECOND FROM i.time1)::int
                 ) BETWEEN ($2::timestamp - interval '3 hours') AND ($2::timestamp + interval '30 hours')
                 OR make_timestamp(
                    EXTRACT(YEAR FROM i.date1)::int,
                    EXTRACT(MONTH FROM i.date1)::int,
                    EXTRACT(DAY FROM i.date1)::int,
                    EXTRACT(HOUR FROM i.time1)::int,
                    EXTRACT(MINUTE FROM i.time1)::int,
                    EXTRACT(SECOND FROM i.time1)::int
                 ) - interval '3 hours' BETWEEN ($2::timestamp - interval '3 hours') AND ($2::timestamp + interval '30 hours')
            END
        )
        ORDER BY i.date1, i.time1
    `
	flights, err := fetchFlightsWithQuery(query, stoika, start)
	if err != nil {
		return nil, err
	}

	for i := range flights {
		if len(flights[i].Stoika) > 0 {
			flights[i].Stoika[0].Number = stoika
		}
	}

	return flights, nil
}

// fetchFlightsByGate - убираем лишние поля из SELECT
func fetchFlightsByGate(gate string) ([]Flight, error) {
	start, _ := getOperationalWindow()
	query := `
        SELECT DISTINCT
            COALESCE(i.id, 0),
            COALESCE(i.direction, ''),
            COALESCE(i.airline, ''),
            COALESCE(f.flights, ''),
            COALESCE(c.id, 0),
            COALESCE(c.city_name_ru, ''),
            COALESCE(c.city_name_ky, ''),
            COALESCE(c.city_name_en, ''),
            COALESCE(c.iata_code, ''),
            i.date1, i.time1, i.last_date, i.last_time,
            COALESCE(s.status_id, ''),
            COALESCE(s.name_ru, ''),
            COALESCE(s.name_ky, ''),
            COALESCE(s.name_en, ''),
            NULL as sky_priority
        FROM "InfTablo" i
        JOIN "FlightNumber" f ON i.flight_id = f.id
        JOIN "City" c ON i.destination_id = c.id
        LEFT JOIN "Status" s ON i.status_id = s.id
        JOIN "InfTablo_gate" itg ON itg.inftablo_id = i.id
        JOIN "Gates" g ON itg.gates_id = g.id
        WHERE g.gate = $1 AND (LOWER(s.name_en) = 'boarding' OR LOWER(s.name_en) = 'check-in boarding') AND (
            CASE WHEN i.date1 IS NULL OR i.time1 IS NULL THEN false
                 ELSE make_timestamp(
                    EXTRACT(YEAR FROM i.date1)::int,
                    EXTRACT(MONTH FROM i.date1)::int,
                    EXTRACT(DAY FROM i.date1)::int,
                    EXTRACT(HOUR FROM i.time1)::int,
                    EXTRACT(MINUTE FROM i.time1)::int,
                    EXTRACT(SECOND FROM i.time1)::int
                 ) BETWEEN ($2::timestamp - interval '3 hours') AND ($2::timestamp + interval '30 hours')
                 OR make_timestamp(
                    EXTRACT(YEAR FROM i.date1)::int,
                    EXTRACT(MONTH FROM i.date1)::int,
                    EXTRACT(DAY FROM i.date1)::int,
                    EXTRACT(HOUR FROM i.time1)::int,
                    EXTRACT(MINUTE FROM i.time1)::int,
                    EXTRACT(SECOND FROM i.time1)::int
                 ) - interval '3 hours' BETWEEN ($2::timestamp - interval '3 hours') AND ($2::timestamp + interval '30 hours')
            END
        )
        ORDER BY i.date1, i.time1
    `
	flights, err := fetchFlightsWithQuery(query, gate, start)
	if err != nil {
		return nil, err
	}

	for i := range flights {
		if len(flights[i].Gate) > 0 {
			flights[i].Gate[0].Number = gate
		}
	}

	return flights, nil
}

// fetchFlightsByBaggage - получение рейсов для выдачи багажа
func fetchFlightsByBaggage(gate string) ([]Flight, error) {
	start, _ := getOperationalWindow()
	query := `
        SELECT DISTINCT
            COALESCE(i.id, 0),
            COALESCE(i.direction, ''),
            COALESCE(i.airline, ''),
            COALESCE(f.flights, ''),
            COALESCE(c.id, 0),
            COALESCE(c.city_name_ru, ''),
            COALESCE(c.city_name_ky, ''),
            COALESCE(c.city_name_en, ''),
            COALESCE(c.iata_code, ''),
            i.date1, i.time1, i.last_date, i.last_time,
            COALESCE(s.status_id, ''),
            COALESCE(s.name_ru, ''),
            COALESCE(s.name_ky, ''),
            COALESCE(s.name_en, ''),
            NULL as sky_priority
        FROM "InfTablo" i
        JOIN "FlightNumber" f ON i.flight_id = f.id
        JOIN "City" c ON i.destination_id = c.id
        LEFT JOIN "Status" s ON i.status_id = s.id
        JOIN "InfTablo_gate" itg ON itg.inftablo_id = i.id
        JOIN "Gates" g ON itg.gates_id = g.id
        WHERE g.gate = $1 AND i.direction = 'arr' AND (
            -- LOWER(s.name_en) LIKE '%baggage%'
            -- ) AND (
            CASE WHEN i.date1 IS NULL OR i.time1 IS NULL THEN false
                 ELSE make_timestamp(
                    EXTRACT(YEAR FROM i.date1)::int,
                    EXTRACT(MONTH FROM i.date1)::int,
                    EXTRACT(DAY FROM i.date1)::int,
                    EXTRACT(HOUR FROM i.time1)::int,
                    EXTRACT(MINUTE FROM i.time1)::int,
                    EXTRACT(SECOND FROM i.time1)::int
                 ) BETWEEN ($2::timestamp - interval '3 hours') AND ($2::timestamp + interval '30 hours')
                 OR make_timestamp(
                    EXTRACT(YEAR FROM i.date1)::int,
                    EXTRACT(MONTH FROM i.date1)::int,
                    EXTRACT(DAY FROM i.date1)::int,
                    EXTRACT(HOUR FROM i.time1)::int,
                    EXTRACT(MINUTE FROM i.time1)::int,
                    EXTRACT(SECOND FROM i.time1)::int
                 ) - interval '3 hours' BETWEEN ($2::timestamp - interval '3 hours') AND ($2::timestamp + interval '30 hours')
            END
        )
        ORDER BY i.date1, i.time1
    `
	flights, err := fetchFlightsWithQuery(query, gate, start)
	if err != nil {
		log.Printf("Error fetching baggage flights for gate %s: %v", gate, err)
		return nil, err
	}

	log.Printf("Fetched %d baggage flights for gate %s", len(flights), gate)

	for i := range flights {
		if len(flights[i].Gate) > 0 {
			flights[i].Gate[0].Number = gate
		}
	}

	return flights, nil
}

// getDataHash - ОСТАВЛЕНО БЕЗ ИЗМЕНЕНИЙ (как в вашем файле)
func getDataHash() string {
	var hash string
	start, _ := getOperationalWindow()
	query := `
        SELECT COALESCE(string_agg(
            COALESCE(i.id::text, '') ||
            COALESCE(i.direction, '') ||
            COALESCE(i.airline, '') ||
            COALESCE(i.flight_id::text, '') ||
            COALESCE(i.destination_id::text, '') ||
            COALESCE(i.date1::text,'') ||
            COALESCE(i.time1::text,'') ||
            COALESCE(i.last_date::text,'') ||
            COALESCE(i.last_time::text,'') ||
            COALESCE(i.status_id::text,'') ||
            (SELECT COALESCE(string_agg(
                COALESCE(s.stoiki, '') || ':' ||
                CASE WHEN spd.id IS NOT NULL THEN 'true' ELSE 'false' END,
                ''
            ), '')
            FROM "InfTablo_stoika" its
            JOIN "Stoiki" s ON its.stoiki_id = s.id
            LEFT JOIN "InfTablo_sky_priority_desks" spd ON spd.inftablo_id = its.inftablo_id AND spd.stoiki_id = s.id
            WHERE its.inftablo_id = i.id) ||
            (SELECT COALESCE(string_agg(COALESCE(g.gate, ''), ''), '')
             FROM "InfTablo_gate" itg
             JOIN "Gates" g ON itg.gates_id = g.id
             WHERE itg.inftablo_id = i.id)
        , '|'), '')
        FROM "InfTablo" i
        WHERE i.date1 IS NULL
           OR i.time1 IS NULL
           OR make_timestamp(
                EXTRACT(YEAR FROM i.date1)::int,
                EXTRACT(MONTH FROM i.date1)::int,
                EXTRACT(DAY FROM i.date1)::int,
                EXTRACT(HOUR FROM i.time1)::int,
                EXTRACT(MINUTE FROM i.time1)::int,
                EXTRACT(SECOND FROM i.time1)::int
              ) BETWEEN ($1::timestamp - interval '3 hours') AND ($1::timestamp + interval '30 hours')
           OR make_timestamp(
                EXTRACT(YEAR FROM i.date1)::int,
                EXTRACT(MONTH FROM i.date1)::int,
                EXTRACT(DAY FROM i.date1)::int,
                EXTRACT(HOUR FROM i.time1)::int,
                EXTRACT(MINUTE FROM i.time1)::int,
                EXTRACT(SECOND FROM i.time1)::int
              ) - interval '3 hours' BETWEEN ($1::timestamp - interval '3 hours') AND ($1::timestamp + interval '30 hours')
    `
	err := db.QueryRow(query, start).Scan(&hash)
	if err != nil {
		log.Printf("Error getting data hash: %v", err)
		return ""
	}
	return hash
}

// Общая функция для выполнения запросов (без изменений)
func fetchFlightsWithQuery(query string, args ...interface{}) ([]Flight, error) {
	rows, err := db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var flights []Flight
	for rows.Next() {
		var f Flight
		var date1, lastDate, time1, lastTime, statusID, statusRu, statusKy, statusEn sql.NullString
		var skyPriority sql.NullBool

		if err := rows.Scan(
			&f.ID, &f.Direction, &f.Airline, &f.Flight,
			&f.Destination.ID, &f.Destination.NameRu, &f.Destination.NameKy, &f.Destination.NameEn, &f.Destination.IataCode,
			&date1, &time1, &lastDate, &lastTime,
			&statusID, &statusRu, &statusKy, &statusEn,
			&skyPriority,
		); err != nil {
			return nil, err
		}

		f.Date1 = date1.String
		f.Time1 = time1.String
		f.LastDate = lastDate.String
		f.LastTime = lastTime.String
		f.Status.ID = statusID.String
		f.Status.NameRu = statusRu.String
		f.Status.NameKy = statusKy.String
		f.Status.NameEn = statusEn.String
		f.Stoika = []StoikaInfo{
			{
				SkyPriority: skyPriority.Bool,
			},
		}
		f.Gate = []GateInfo{}

		// --- КОНВЕРТАЦИЯ ВРЕМЕНИ В ЛОКАЛЬНЫЙ ЧАСОВОЙ ПОЯС ---
		if date1.Valid && time1.Valid {
			dateTimeStr := date1.String + " " + time1.String
			layout := "2006-01-02 15:04:05"
			t, err := time.Parse(layout, dateTimeStr)
			if err == nil {
				loc, _ := time.LoadLocation("Asia/Bishkek")
				t = t.In(loc)
				f.Date1 = t.Format("2006-01-02")
				f.Time1 = t.Format("15:04:05")
			}
		}
		// --- КОНЕЦ КОНВЕРТАЦИИ ---

		if err := fetchRelatedData(&f); err != nil {
			log.Printf("Error fetching related data: %v", err)
			continue
		}

		flights = append(flights, f)
	}

	return flights, nil
}

// Получение связанных данных (стойки, гейты, погода) - без изменений
func fetchRelatedData(f *Flight) error {
	// Получение стоек
	if err := fetchStoiki(f); err != nil {
		return err
	}

	// Получение гейтов
	if err := fetchGates(f); err != nil {
		return err
	}

	// Получение погоды только для стоек регистрации
	if f.Destination.NameRu != "" && len(f.Stoika) > 0 {
		weather, err := getWeather(f.Destination.NameRu)
		if err != nil {
			log.Printf("Error getting weather for %s: %v", f.Destination.NameRu, err)
		} else {
			f.Weather = weather
		}
	}

	return nil
}

// fetchStoiki (без изменений)
func fetchStoiki(f *Flight) error {
	rows, err := db.Query(`
        SELECT
            s.stoiki,
            CASE
                WHEN spd.id IS NOT NULL THEN 1
                ELSE 0
            END as is_sky_priority
        FROM "InfTablo_stoika" its
        JOIN "Stoiki" s ON its.stoiki_id = s.id
        LEFT JOIN "InfTablo_sky_priority_desks" spd
            ON spd.inftablo_id = its.inftablo_id AND spd.stoiki_id = s.id
        WHERE its.inftablo_id = $1
    `, f.ID)
	if err != nil {
		return err
	}
	defer rows.Close()

	f.Stoika = []StoikaInfo{}
	for rows.Next() {
		var stoika StoikaInfo
		if err := rows.Scan(&stoika.Number, &stoika.SkyPriority); err != nil {
			return err
		}
		f.Stoika = append(f.Stoika, stoika)
	}
	return nil
}

// fetchGates (без изменений)
func fetchGates(f *Flight) error {
	rows, err := db.Query(`
        SELECT g.gate
        FROM "InfTablo_gate" itg
        JOIN "Gates" g ON itg.gates_id = g.id
        WHERE itg.inftablo_id = $1
    `, f.ID)
	if err != nil {
		return err
	}
	defer rows.Close()

	f.Gate = []GateInfo{}
	for rows.Next() {
		var gateInfo GateInfo
		var gate string
		if err := rows.Scan(&gate); err != nil {
			return err
		}
		gateInfo.Number = gate
		f.Gate = append(f.Gate, gateInfo)
	}
	return nil
}

// Обработчики страниц
func serveDepPage(w http.ResponseWriter, r *http.Request) {
	serveHTMLPage(w, r, "dep.html")
}

func serveArrPage(w http.ResponseWriter, r *http.Request) {
	serveHTMLPage(w, r, "arr.html")
}

func serveDepArrPage(w http.ResponseWriter, r *http.Request) {
	serveHTMLPage(w, r, "dep_arr.html")
}

func serveStoikaPage(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	if _, err := strconv.Atoi(vars["stoika"]); err != nil {
		http.Error(w, "Invalid desk number", http.StatusBadRequest)
		return
	}
	serveHTMLPage(w, r, "st.html")
}

func serveGatePage(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	if _, err := strconv.Atoi(vars["gate"]); err != nil {
		http.Error(w, "Invalid gate number", http.StatusBadRequest)
		return
	}
	serveHTMLPage(w, r, "gt.html")
}

func serveBaggagePage(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	if _, err := strconv.Atoi(vars["stoika"]); err != nil {
		http.Error(w, "Invalid baggage carousel number", http.StatusBadRequest)
		return
	}
	serveHTMLPage(w, r, "bg.html")
}

// НОВЫЙ обработчик страницы для диспетчера
func serveDispatcherPage(w http.ResponseWriter, r *http.Request) {
	serveHTMLPage(w, r, "dispatcher.html")
}

// serveHTMLPage (без изменений)
func serveHTMLPage(w http.ResponseWriter, r *http.Request, filename string) {
	path := filepath.Join("./static", filename)
	if _, err := os.Stat(path); os.IsNotExist(err) {
		http.Error(w, "Page not found", http.StatusNotFound)
		return
	}
	http.ServeFile(w, r, path)
}

// Функция для получения активных регистраций напрямую из БД (для диспетчера)
func fetchActiveRegistrationsFromDB() ([]Flight, error) {
	// Временное окно: от -2 часов до +4 часов от текущего времени (локального)
	now := time.Now()
	startWindow := now.Add(-2 * time.Hour)
	endWindow := now.Add(4 * time.Hour)

	query := `
		SELECT
			COALESCE(i.id, 0),
			COALESCE(i.direction, ''),
			COALESCE(i.airline, ''),
			COALESCE(f.flights, ''),
			COALESCE(c.id, 0),
			COALESCE(c.city_name_ru, ''),
			COALESCE(c.city_name_ky, ''),
			COALESCE(c.city_name_en, ''),
			COALESCE(c.iata_code, ''),
			i.date1, i.time1, i.last_date, i.last_time,
			COALESCE(s.status_id, ''),
			COALESCE(s.name_ru, ''),
			COALESCE(s.name_ky, ''),
			COALESCE(s.name_en, ''),
			NULL as sky_priority
		FROM "InfTablo" i
		JOIN "FlightNumber" f ON i.flight_id = f.id
		JOIN "City" c ON i.destination_id = c.id
		LEFT JOIN "Status" s ON i.status_id = s.id
		WHERE (
			(i.date1 > $1::date)
			OR (i.date1 = $1::date AND i.time1 >= $2::time)
		) AND (
			(i.date1 < $3::date)
			OR (i.date1 = $3::date AND i.time1 <= $4::time)
		) AND s.name_en IN ('CHECK-IN', 'BOARDING', 'CHECK-IN BOARDING', 'LAST CALL')
		ORDER BY i.date1, i.time1
	`
	return fetchFlightsWithQuery(query,
		startWindow.Format("2006-01-02"), startWindow.Format("15:04:05"),
		endWindow.Format("2006-01-02"), endWindow.Format("15:04:05"))
}

// НОВАЯ функция для мониторинга активных регистраций из Django API (для диспетчера)
func pollActiveRegistrations() {
	ticker := time.NewTicker(DJANGO_API_POLLING_INTERVAL)
	defer ticker.Stop()

	for range ticker.C {
		activeRegistrations, err := fetchActiveRegistrationsFromDB()
		if err != nil {
			log.Printf("Ошибка при опросе БД для активных регистраций: %v", err)
			continue
		}

		currentFlightsMap := make(map[int]Flight)
		for _, flight := range activeRegistrations {
			currentFlightsMap[flight.ID] = flight
		}

		// Обнаружение изменений статусов для отправки уведомлений
		notificationsToSend := []map[string]interface{}{}

		for flightID, currentFlight := range currentFlightsMap {
			previousFlight, exists := lastDispatcherData[flightID]

			// Уведомление о начале РЕГИСТРАЦИИ
			if exists && previousFlight.Status.NameEn != "CHECK-IN" && currentFlight.Status.NameEn == "CHECK-IN" {
				notificationsToSend = append(notificationsToSend, map[string]interface{}{
					"type":          "checkin_started",
					"flight_id":     currentFlight.ID,
					"flight_number": currentFlight.Flight,
					"destination":   currentFlight.Destination.NameEn,
				})
				log.Printf("Обнаружено начало РЕГИСТРАЦИИ для рейса %s (%s)", currentFlight.Flight, currentFlight.Destination.NameEn)
			}

			// Уведомление о начале ПОСАДКИ
			if exists && previousFlight.Status.NameEn != "BOARDING" && currentFlight.Status.NameEn == "BOARDING" {
				notificationsToSend = append(notificationsToSend, map[string]interface{}{
					"type":          "boarding_started",
					"flight_id":     currentFlight.ID,
					"flight_number": currentFlight.Flight,
					"destination":   currentFlight.Destination.NameEn,
				})
				log.Printf("Обнаружено начало ПОСАДКИ для рейса %s (%s)", currentFlight.Flight, currentFlight.Destination.NameEn)
			}
		}

		// Обновляем lastDispatcherData для следующего опроса
		lastDispatcherData = currentFlightsMap

		// Проверяем, изменились ли данные или есть ли уведомления, чтобы отправить их диспетчерам
		jsonData, err := json.Marshal(activeRegistrations)
		if err != nil {
			log.Printf("Ошибка при маршалинге данных для хеша диспетчера: %v", err)
			continue
		}
		currentDispatcherDataHash := fmt.Sprintf("%x", jsonData)

		if currentDispatcherDataHash != lastDispatcherDataHash || len(notificationsToSend) > 0 {
			log.Println("Обнаружены изменения в активных регистрациях (из БД) ИЛИ есть уведомления. Обновление диспетчеров.")
			lastDispatcherDataHash = currentDispatcherDataHash

			clientsMu.Lock()
			var clientsToRemove []*Client
			for client := range clients {
				if client.clientType == "dispatcher" {
					client.conn.SetWriteDeadline(time.Now().Add(5 * time.Second))

					// Сначала отправляем обычное обновление данных о рейсах
					if err := client.conn.WriteJSON(activeRegistrations); err != nil {
						log.Printf("Ошибка отправки активных регистраций диспетчеру (%s): %v", client.conn.RemoteAddr().String(), err)
						clientsToRemove = append(clientsToRemove, client)
						continue
					}

					// Затем отправляем любые ожидающие уведомления отдельными сообщениями
					for _, notification := range notificationsToSend {
						if err := client.conn.WriteJSON(notification); err != nil {
							log.Printf("Ошибка отправки уведомления диспетчеру (%s): %v", client.conn.RemoteAddr().String(), err)
							clientsToRemove = append(clientsToRemove, client)
							break
						}
					}
					client.conn.SetWriteDeadline(time.Time{})
				}
			}
			// Удаляем клиентов с ошибками
			for _, client := range clientsToRemove {
				client.conn.Close()
				delete(clients, client)
			}
			clientsMu.Unlock()
		}
	}
}
