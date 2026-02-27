package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
)

// --- Structures matching fids_full.json ---

type LocalizedString struct {
	Ru string `json:"ru"`
	En string `json:"en"`
	Ky string `json:"ky"`
}

type SourceFlight struct {
	Dir       string          `json:"dir"` // "O" (Departure) or "P" (Arrival)
	Flt       string          `json:"flt"`
	Al        string          `json:"al"`
	Type      string          `json:"type"`
	CodeShare string          `json:"codeshare"`
	Dest      LocalizedString `json:"dest"`
	SchD      string          `json:"sch_d"` // "2025-12-17"
	SchT      string          `json:"sch_t"` // "02.15"
	EstT      string          `json:"est_t"`
	ActT      string          `json:"act_t"`
	Status    LocalizedString `json:"status"`
	Gate      string          `json:"gate"`
	Checkin   string          `json:"checkin"`
	Stand     string          `json:"stand"`
	Board     string          `json:"board"`
	Carousel  string          `json:"carousel"`
	Business  string          `json:"business_chk"`
	SkyPrio   string          `json:"sky_priority"`
}

// --- Structures for Frontend (Legacy compatibility) ---

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
	Business    bool   `json:"business"`
}

type BaggageInfo struct {
	Number string `json:"number"`
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
	ID          int           `json:"id"`
	Direction   string        `json:"direction"`
	Airline     string        `json:"airline"`
	Flight      string        `json:"flight"`
	Destination City          `json:"destination"`
	Date1       string        `json:"date1"`
	Time1       string        `json:"time1"`
	LastDate    string        `json:"last_date,omitempty"`
	LastTime    string        `json:"last_time,omitempty"`
	Status      FlightStatus  `json:"status"`
	Stoika      []StoikaInfo  `json:"stoika,omitempty"`
	Gate        []GateInfo    `json:"gate,omitempty"`
	Baggage     []BaggageInfo `json:"baggage,omitempty"`
	Weather     *Weather      `json:"weather,omitempty"`
}

type ServerTime struct {
	Time    string `json:"server_time"`
	NewYear bool   `json:"new_year"`
}

// --- Global State ---

var (
	// Data
	allFlights      []Flight
	allFlightsMu    sync.RWMutex
	lastDataHash    string
	notifications   []Notification // Queue for notifications
	notificationsMu sync.Mutex

	// Source Data Cache (for internal reprocessing)
	lastSourceData   []SourceFlight
	lastSourceDataMu sync.RWMutex

	// Unfiltered Data for Flights Page
	allFlightsUnfiltered   []Flight
	allFlightsUnfilteredMu sync.RWMutex

	// Weather
	weatherCache      = make(map[string]*Weather)
	weatherCacheMutex sync.RWMutex
	weatherCacheTTL   = 30 * time.Minute

	// WebSockets
	upgrader = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}
	clients   = make(map[*Client]bool)
	clientsMu sync.Mutex

	// Configuration
	sourceURL string

	// OpenWeatherMap
	openWeatherAPIKey string
	openWeatherURL    = "https://api.openweathermap.org/data/2.5/weather"
)

// --- Client Structure ---

type Notification struct {
	Type     string `json:"type"` // "notification"
	Flight   string `json:"flight"`
	StatusRu string `json:"status_ru"`
	StatusEn string `json:"status_en"`
	StatusKy string `json:"status_ky"`
	Message  string `json:"message"` // For basic display
}

type Client struct {
	conn       *websocket.Conn
	clientType string
}

// --- Main ---

func main() {
	// Initialize sourceURL from environment variable
	sourceURL = os.Getenv("FLIGHT_API_URL")
	if sourceURL == "" {
		sourceURL = "http://localhost/api/fids_full.json"
	}

	// Initialize router for main app (port 8080)
	r := mux.NewRouter()

	// WebSocket endpoints
	r.HandleFunc("/ws/dep", handleDepWebSocket)
	r.HandleFunc("/ws/arr", handleArrWebSocket)
	r.HandleFunc("/ws/st/{stoika}", handleStoikaWebSocket)
	r.HandleFunc("/ws/gt/{gate}", handleGateWebSocket)
	r.HandleFunc("/ws/bg/{stoika}", handleBaggageWebSocket)
	r.HandleFunc("/ws/dispatcher", handleDispatcherWebSocket)
	r.HandleFunc("/ws/flights", handleFlightsListWebSocket)

	// Local dev /go prefix support
	r.HandleFunc("/go/ws/dep", handleDepWebSocket)
	r.HandleFunc("/go/ws/arr", handleArrWebSocket)
	r.HandleFunc("/go/ws/st/{stoika}", handleStoikaWebSocket)
	r.HandleFunc("/go/ws/gt/{gate}", handleGateWebSocket)
	r.HandleFunc("/go/ws/bg/{stoika}", handleBaggageWebSocket)
	r.HandleFunc("/go/ws/dispatcher", handleDispatcherWebSocket)
	r.HandleFunc("/go/ws/flights", handleFlightsListWebSocket)

	// Static Pages (Placeholder - serving simple text or redirecting if static files exist)
	// Assuming static files are served relative to running directory
	r.HandleFunc("/dep", serveDepPage)
	r.HandleFunc("/arr", serveArrPage)
	r.HandleFunc("/st/{stoika}", serveStoikaPage)
	r.HandleFunc("/gt/{gate}", serveGatePage)
	r.HandleFunc("/bg/{stoika}", serveBaggagePage)
	r.HandleFunc("/dispatcher", serveDispatcherPage)
	r.HandleFunc("/flights", serveFlightsPage)
	r.HandleFunc("/dep_arr", serveDepArrPage)
	r.HandleFunc("/dep_vert", serveDepVertPage)
	r.HandleFunc("/arr_vert", serveArrVertPage)

	r.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/dep", http.StatusFound)
	})

	// Static files serving
	staticHandler := http.StripPrefix("/static/", http.FileServer(http.Dir("./static")))
	safeStaticHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, ".css") {
			w.Header().Set("Content-Type", "text/css")
		} else if strings.HasSuffix(r.URL.Path, ".js") {
			w.Header().Set("Content-Type", "application/javascript")
		}
		staticHandler.ServeHTTP(w, r)
	})
	r.PathPrefix("/static/").Handler(safeStaticHandler)
	r.PathPrefix("/go/static/").Handler(http.StripPrefix("/go/static/", http.FileServer(http.Dir("./static"))))

	// Start Trigger Listener on Port 8082
	go func() {
		fmt.Println("Trigger listener started on :8082")
		http.HandleFunc("/reload", triggerHandler) // Maps to http_get.go logic
		if err := http.ListenAndServe(":8082", nil); err != nil {
			log.Fatalf("Error starting trigger listener: %v", err)
		}
	}()

	// Initial Fetch
	go fetchAndParseData()

	// Start Background Broadcaster
	go monitorUpdates()
	go reprocessLoop()

	fmt.Println("Main application started on :8085")
	if err := http.ListenAndServe(":8085", r); err != nil {
		log.Fatal(err)
	}
}

// --- Trigger Logic ---

// --- Trigger Logic ---

func triggerHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Printf("[%s] Signal received from: %s\n", time.Now().Format("15:04:05"), r.RemoteAddr)
	go fetchAndParseData() // Non-blocking update

	// Notify Django
	go func() {
		// Replace with your actual Django endpoint
		djangoURL := "http://127.0.0.1:8000/api/refresh"
		resp, err := http.Post(djangoURL, "application/json", strings.NewReader(`{"source":"fids_go"}`))
		if err != nil {
			log.Printf("Failed to notify Django: %v", err)
			return
		}
		defer resp.Body.Close()
		log.Printf("Notified Django at %s, status: %s", djangoURL, resp.Status)
	}()

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("Signal Received, updating data and notifying Django..."))
}

// --- Data Fetching & Processing ---

func fetchAndParseData() {
	client := http.Client{Timeout: 10 * time.Second}
	log.Printf("Fetching data from: %s", sourceURL)
	resp, err := client.Get(sourceURL)
	if err != nil {
		log.Printf("Error fetching JSON: %v", err)
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	// log.Println("Reading data from local file: fids_full.json")
	// body, err := os.ReadFile("fids_full.json")
	if err != nil {
		log.Printf("Error reading body: %v", err)
		return
	}

	var sourceData []SourceFlight
	if err := json.Unmarshal(body, &sourceData); err != nil {
		log.Printf("Error unmarshalling JSON: %v", err)
		return
	}

	// Optional: Save copy for debugging/backup
	// os.WriteFile("fids_full_last.json", body, 0644)

	// Save to global cache
	lastSourceDataMu.Lock()
	lastSourceData = sourceData
	lastSourceDataMu.Unlock()

	processData(sourceData)
}

func processData(source []SourceFlight) {
	var processed []Flight
	now := time.Now()
	// Define window: -4 hours to +24 hours
	startWindow := now.Add(-4 * time.Hour)
	endWindow := now.Add(24 * time.Hour)

	// Unfiltered Window: -48h to +48h for Flights Page
	startWindowUnfiltered := now.Add(-48 * time.Hour)
	endWindowUnfiltered := now.Add(48 * time.Hour)

	var processedUnfiltered []Flight

	for i, s := range source {
		// Parse Dates
		// Layouts needed: JSON seems to use "2006-01-02" and "15.04" (dot separator?)
		// Let's verify format. Example: "sch_d":"2025-12-17","sch_t":"02.15"

		// Helper to parse date/time
		dateTimeStr := s.SchD + " " + strings.ReplaceAll(s.SchT, ".", ":")
		flightTime, err := time.Parse("2006-01-02 15:04", dateTimeStr)
		if err != nil {
			// Try without replacing dot if that fails, just in case
			flightTime, err = time.Parse("2006-01-02 15:04", s.SchD+" "+s.SchT)
			if err != nil {
				// Log error but maybe skip flight?
				continue
			}
		}

		// Check if est_t (estimated time) exists and use it for filtering
		// This allows delayed flights to remain visible based on estimated time
		timeForFiltering := flightTime
		if s.EstT != "" {
			estTimeStr := s.SchD + " " + strings.ReplaceAll(s.EstT, ".", ":")
			estTime, err := time.Parse("2006-01-02 15:04", estTimeStr)
			if err == nil {
				timeForFiltering = estTime
			}
		}

		// Filter Window - use estimated time if available, otherwise scheduled time
		inStandardWindow := !timeForFiltering.Before(startWindow) && !timeForFiltering.After(endWindow)
		inUnfilteredWindow := !timeForFiltering.Before(startWindowUnfiltered) && !timeForFiltering.After(endWindowUnfiltered)

		if !inStandardWindow && !inUnfilteredWindow {
			continue
		}

		// Convert Direction
		dir := "dep"
		if s.Dir == "P" {
			dir = "arr"
		}

		// Map to Flight Struct
		f := Flight{
			ID:        i + 1, // Generate a pseudo ID
			Direction: dir,
			Airline:   s.Al,
			Flight:    s.Flt,
			Destination: City{
				NameRu: s.Dest.Ru,
				NameEn: s.Dest.En,
				NameKy: s.Dest.Ky,
			},
			Date1: s.SchD,
			Time1: strings.ReplaceAll(s.SchT, ".", ":"), // Fix format for frontend
			LastTime: func() string {
				t := s.ActT
				if t == "" {
					t = s.EstT
				}
				return strings.ReplaceAll(t, ".", ":")
			}(),
			Status: FlightStatus{
				NameRu: s.Status.Ru,
				NameEn: s.Status.En,
				NameKy: s.Status.Ky,
			},
		}

		// Handle Stoika (Checkin)
		if s.Checkin != "" {
			// Split Checkin, Business, SkyPriority strings
			checkinParts := strings.Split(s.Checkin, ",")
			businessParts := strings.Split(s.Business, ",")
			skyParts := strings.Split(s.SkyPrio, ",")

			// Maps for fast lookup
			businessMap := make(map[string]bool)
			for _, p := range businessParts {
				businessMap[strings.TrimSpace(p)] = true
			}
			skyMap := make(map[string]bool)
			for _, p := range skyParts {
				skyMap[strings.TrimSpace(p)] = true
			}

			var stoikas []StoikaInfo
			for _, p := range checkinParts {
				val := strings.TrimSpace(p)
				if val != "" {
					stoikas = append(stoikas, StoikaInfo{
						Number:      val,
						SkyPriority: skyMap[val],
						Business:    businessMap[val],
					})
				}
			}
			f.Stoika = stoikas
		}

		// Handle Gate
		if s.Gate != "" {
			f.Gate = []GateInfo{{Number: s.Gate}}
		}

		// Handle Baggage (Carousel)
		if s.Carousel != "" {
			parts := strings.Split(s.Carousel, ",")
			var bags []BaggageInfo
			for _, p := range parts {
				val := strings.TrimSpace(p)
				if val != "" {
					bags = append(bags, BaggageInfo{Number: val})
				}
			}
			f.Baggage = bags
		}

		// Weather Fetching
		// Only fetch for Destination (Departures) or Origin?
		// Usually for Departures we show weather at Destination.
		// For Arrivals we show local weather? Or weather at Origin?
		// Standard FIDS logic: Time/Weather usually refers to Destination for departures.
		// For arrivals, it's irrelevant or local. But City struct is Destination.
		if f.Direction == "dep" {
			// Fetch weather for Destination City (English name usually works best for API)
			// Ensure we have a valid city name
			if f.Destination.NameEn != "" {
				f.Weather = getWeather(f.Destination.NameEn)
			}
		}

		if inStandardWindow {
			processed = append(processed, f)
		}
		if inUnfilteredWindow {
			processedUnfiltered = append(processedUnfiltered, f)
		}
	}

	// Detect Status Changes
	allFlightsMu.RLock()
	oldFlights := make(map[string]Flight)
	for _, f := range allFlights {
		// Use Flight number + Date as key (or simplified key)
		key := f.Flight + "_" + f.Date1
		oldFlights[key] = f
	}
	allFlightsMu.RUnlock()

	var newNotifications []Notification
	for _, f := range processed {
		key := f.Flight + "_" + f.Date1
		if old, exists := oldFlights[key]; exists {
			// Check if status changed
			if old.Status.NameRu != f.Status.NameRu {
				log.Printf("Status changed for %s: %s -> %s", f.Flight, old.Status.NameRu, f.Status.NameRu)
				newNotifications = append(newNotifications, Notification{
					Type:     "notification",
					Flight:   f.Flight,
					StatusRu: f.Status.NameRu,
					StatusEn: f.Status.NameEn,
					StatusKy: f.Status.NameKy,
					Message:  fmt.Sprintf("Flight %s: %s", f.Flight, f.Status.NameRu),
				})
			}
		}
	}

	if len(newNotifications) > 0 {
		notificationsMu.Lock()
		notifications = append(notifications, newNotifications...)
		notificationsMu.Unlock()
	}

	// SORTING
	sort.Slice(processed, func(i, j int) bool {
		// Combine Date and Time for comparison
		// Formats are: Date1 "2006-01-02", Time1 "15:04"
		// Simple string comparison works for ISO dates, but safer to just string compare if format is fixed
		dt1 := processed[i].Date1 + " " + processed[i].Time1
		dt2 := processed[j].Date1 + " " + processed[j].Time1
		return dt1 < dt2
	})

	allFlightsMu.Lock()
	allFlights = processed
	allFlightsMu.Unlock()

	// Sort Unfiltered
	sort.Slice(processedUnfiltered, func(i, j int) bool {
		dt1 := processedUnfiltered[i].Date1 + " " + processedUnfiltered[i].Time1
		dt2 := processedUnfiltered[j].Date1 + " " + processedUnfiltered[j].Time1
		return dt1 < dt2
	})

	allFlightsUnfilteredMu.Lock()
	allFlightsUnfiltered = processedUnfiltered
	allFlightsUnfilteredMu.Unlock()

	// Recalculate Hash
	// Simple string representation for hash
	newHash := fmt.Sprintf("%d flights at %s", len(processed), now.String())
	if newHash != lastDataHash {
		lastDataHash = newHash
		log.Println("Data updated, broadcasting...")
		broadcastUpdates()
	}
}

// --- Handlers ---

func serveDepPage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/dep.html")
}
func serveArrPage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/arr.html")
}
func serveStoikaPage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/st.html")
}
func serveGatePage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/gt.html")
}
func serveBaggagePage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/bg.html")
}
func serveDispatcherPage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/dispatcher.html")
}
func serveDepArrPage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/dep_arr.html")
}
func serveDepVertPage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/dep_vert.html")
}
func serveArrVertPage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/arr_vert.html")
}
func serveFlightsPage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "./static/flights.html")
}

// --- WebSocket Handlers ---

func handleDepWebSocket(w http.ResponseWriter, r *http.Request) {
	handleFlightsWebSocket(w, r, "dep")
}

func handleArrWebSocket(w http.ResponseWriter, r *http.Request) {
	handleFlightsWebSocket(w, r, "arr")
}

func handleFlightsWebSocket(w http.ResponseWriter, r *http.Request, direction string) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer conn.Close()

	client := &Client{conn: conn, clientType: direction}
	registerClient(client)
	defer unregisterClient(client)

	// Send Server Time
	conn.WriteJSON(getServerTime())

	// Send Initial Data
	data := getFlightsByDirection(direction)
	conn.WriteJSON(data)

	keepConnectionAlive(conn)
}

func handleStoikaWebSocket(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	stoika := vars["stoika"]
	handleSpecificWebSocket(w, r, "st-"+stoika, func() interface{} {
		return getFlightsByStoika(stoika)
	})
}

func handleGateWebSocket(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	gate := vars["gate"]
	handleSpecificWebSocket(w, r, "gt-"+gate, func() interface{} {
		return getFlightsByGate(gate)
	})
}

func handleBaggageWebSocket(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["stoika"] // reused var name in router, effectively carousel number
	handleSpecificWebSocket(w, r, "bg-"+id, func() interface{} {
		return getFlightsByCarousel(id)
	})
}

func handleDispatcherWebSocket(w http.ResponseWriter, r *http.Request) {
	handleSpecificWebSocket(w, r, "dispatcher", func() interface{} {
		allFlightsMu.RLock()
		defer allFlightsMu.RUnlock()
		// Copy slice
		res := make([]Flight, len(allFlights))
		copy(res, allFlights)
		return res
	})
}

func handleFlightsListWebSocket(w http.ResponseWriter, r *http.Request) {
	handleSpecificWebSocket(w, r, "flights_list", func() interface{} {
		allFlightsUnfilteredMu.RLock()
		defer allFlightsUnfilteredMu.RUnlock()
		// Copy slice
		res := make([]Flight, len(allFlightsUnfiltered))
		copy(res, allFlightsUnfiltered)
		return res
	})
}

func handleSpecificWebSocket(w http.ResponseWriter, r *http.Request, clientType string, dataFetcher func() interface{}) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer conn.Close()

	client := &Client{conn: conn, clientType: clientType}
	registerClient(client)
	defer unregisterClient(client)

	conn.WriteJSON(getServerTime())
	conn.WriteJSON(dataFetcher())

	keepConnectionAlive(conn)
}

// --- WebSocket Helpers ---

func registerClient(c *Client) {
	clientsMu.Lock()
	clients[c] = true
	clientsMu.Unlock()
}
func unregisterClient(c *Client) {
	clientsMu.Lock()
	delete(clients, c)
	clientsMu.Unlock()
}

func keepConnectionAlive(ws *websocket.Conn) {
	for {
		if _, _, err := ws.ReadMessage(); err != nil {
			break
		}
	}
}

func monitorUpdates() {
	// Not strictly needed if we rely solely on Trigger, but good for periodic housekeeping or ensuring time updates
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		// Broadcast time or just check stuff
		// Actually, we broadcast on data change.
		// But we also need to send ServerTime periodically?
		broadcastTime()
	}
}

func reprocessLoop() {
	// Re-process cached data every 30 seconds
	// This ensures flights drop off the board (window filtering) even if no new API data comes in.
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		lastSourceDataMu.RLock()
		data := lastSourceData
		lastSourceDataMu.RUnlock()

		if len(data) > 0 {
			processData(data)
		}
	}
}

func broadcastTime() {
	st := getServerTime()
	clientsMu.Lock()
	defer clientsMu.Unlock()
	for client := range clients {
		client.conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
		client.conn.WriteJSON(st)
		client.conn.SetWriteDeadline(time.Time{})
	}
}

func broadcastUpdates() {
	clientsMu.Lock()
	defer clientsMu.Unlock()

	// Snapshot data
	dep := getFlightsByDirection("dep")
	arr := getFlightsByDirection("arr")

	// Get pending notifications
	notificationsMu.Lock()
	params := notifications          // Copy slice
	notifications = []Notification{} // Clear queue
	notificationsMu.Unlock()

	for client := range clients {
		var data interface{}
		if client.clientType == "dep" {
			data = dep
		} else if client.clientType == "arr" {
			data = arr
		} else if strings.HasPrefix(client.clientType, "st-") {
			data = getFlightsByStoika(strings.TrimPrefix(client.clientType, "st-"))
		} else if strings.HasPrefix(client.clientType, "gt-") {
			data = getFlightsByGate(strings.TrimPrefix(client.clientType, "gt-"))
		} else if strings.HasPrefix(client.clientType, "bg-") {
			data = getFlightsByCarousel(strings.TrimPrefix(client.clientType, "bg-"))
		} else if client.clientType == "dispatcher" {
			allFlightsMu.RLock()
			c := make([]Flight, len(allFlights))
			copy(c, allFlights)
			allFlightsMu.RUnlock()
			data = c
		} else if client.clientType == "flights_list" {
			allFlightsUnfilteredMu.RLock()
			c := make([]Flight, len(allFlightsUnfiltered))
			copy(c, allFlightsUnfiltered)
			allFlightsUnfilteredMu.RUnlock()
			data = c
		}

		if data != nil {
			client.conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
			client.conn.WriteJSON(data)

			// Send notifications if applicable (only to dep/arr boards usually)
			if (client.clientType == "dep" || client.clientType == "arr") && len(params) > 0 {
				for _, n := range params {
					client.conn.WriteJSON(n)
				}
			}
			client.conn.SetWriteDeadline(time.Time{})
		}
	}
}

// --- Filtering Helpers ---

func getFlightsByDirection(dir string) []Flight {
	allFlightsMu.RLock()
	defer allFlightsMu.RUnlock()
	var res []Flight
	for _, f := range allFlights {
		if f.Direction == dir {
			res = append(res, f)
		}
	}
	return res
}

func getFlightsByStoika(num string) []Flight {
	allFlightsMu.RLock()
	defer allFlightsMu.RUnlock()
	var res []Flight
	for _, f := range allFlights {
		for _, s := range f.Stoika {
			if s.Number == num {
				// Filter by Status (Only Check-in related)
				// Status names in fids_full.json might have trailing spaces
				statusEn := strings.TrimSpace(f.Status.NameEn)

				// Check against allowed statuses
				if statusEn == "CHECK-IN" || statusEn == "CHECK-IN BOARDING" {
					res = append(res, f)
				}
				break
			}
		}
	}
	return res
}

func getFlightsByGate(num string) []Flight {
	allFlightsMu.RLock()
	defer allFlightsMu.RUnlock()
	var res []Flight
	for _, f := range allFlights {
		for _, g := range f.Gate {
			if g.Number == num {
				// Filter by Status: Only show during active boarding phase
				statusEn := strings.TrimSpace(strings.ToUpper(f.Status.NameEn))

				// Allowed statuses: BOARDING, CHECK-IN BOARDING, FINAL CALL, GATE OPEN
				if strings.Contains(statusEn, "BOARDING") ||
					strings.Contains(statusEn, "FINAL CALL") ||
					strings.Contains(statusEn, "GATE OPEN") {
					res = append(res, f)
				}
				break
			}
		}
	}
	return res
}

func getFlightsByCarousel(num string) []Flight {
	allFlightsMu.RLock()
	defer allFlightsMu.RUnlock()
	var res []Flight
	for _, f := range allFlights {
		// Baggage carousels are only for arrivals
		if f.Direction != "arr" {
			continue
		}

		for _, b := range f.Baggage {
			if b.Number == num {
				// Filter by Status: Only show arrived/landed flights
				statusEn := strings.TrimSpace(strings.ToUpper(f.Status.NameEn))

				// Allowed statuses: ARRIVED, LANDED
				if strings.Contains(statusEn, "ARRIVED") ||
					strings.Contains(statusEn, "LANDED") {
					res = append(res, f)
				}
				break
			}
		}
	}
	return res
}

// --- Utils ---

// --- Weather Logic ---

type OpenWeatherResponse struct {
	Main struct {
		Temp float64 `json:"temp"`
	} `json:"main"`
	Weather []struct {
		Icon string `json:"icon"`
	} `json:"weather"`
}

func getWeather(city string) *Weather {
	if city == "" {
		return nil
	}

	// 1. Normalize City Name
	// OpenWeatherMap is sensitive to casing and specific names
	// Map upper case input from FIDS to OpenWeatherMap friendly names
	normalizedCity := strings.TrimSpace(city)
	upperCity := strings.ToUpper(normalizedCity)

	cityMap := map[string]string{
		"SAINT-PETERSBURG": "Saint Petersburg",
		"EL-KUWAIT":        "Kuwait City",
		"MOSCOW":           "Moscow",
		"ISTANBUL":         "Istanbul",
		"ANTALYA":          "Antalya",
		"DUBAI":            "Dubai",
		"SHARJAH":          "Sharjah",
		"TASHKENT":         "Tashkent",
		"ALMATY":           "Almaty", // sometimes Almaty, KZ
		"DELHI":            "Delhi",
		"JEDDAH":           "Jeddah",
	}

	if val, ok := cityMap[upperCity]; ok {
		normalizedCity = val
	} else {
		// Default capitalization for others: "CITY NAME" -> "City Name"
		// This is a naive capitalization, but might help for valid cities not in map
		// Actually, let's just try sending the input if not in map, but maybe Title Case?
		// strings.Title is deprecated, lets use cases.Title or just leave it if API handles upper case (it usually does for common cities)
		// But "SAINT-PETERSBURG" with hyphen might be the issue if API expects spaces?
		// Let's rely on the map for known issues and pass others through.
	}

	// 2. Check Cache (use normalized name for key to avoid dupes)
	weatherCacheMutex.RLock()
	if w, ok := weatherCache[normalizedCity]; ok {
		if time.Since(w.CachedAt) < weatherCacheTTL {
			weatherCacheMutex.RUnlock()
			return w
		}
	}
	weatherCacheMutex.RUnlock()

	// 3. Fetch from API
	// Note: We should probably throttle this or do it asynchronously to avoid blocking the main loop too much.
	// But since we have a cache, it should be fine after the first run.

	// Replace spaces for URL
	encodedCity := strings.ReplaceAll(normalizedCity, " ", "+")
	url := fmt.Sprintf("%s?q=%s&units=metric&appid=%s", openWeatherURL, encodedCity, openWeatherAPIKey)

	// Set a short timeout for weather to avoid hanging
	client := http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		log.Printf("Error fetching weather for %s: %v", normalizedCity, err)
		return nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("Weather API returned status %d for %s (orig: %s)", resp.StatusCode, normalizedCity, city)
		return nil
	}

	var owResp OpenWeatherResponse
	if err := json.NewDecoder(resp.Body).Decode(&owResp); err != nil {
		log.Printf("Error decoding weather json for %s: %v", normalizedCity, err)
		return nil
	}

	if len(owResp.Weather) == 0 {
		return nil
	}

	w := &Weather{
		Temp:     owResp.Main.Temp,
		IconURL:  owResp.Weather[0].Icon,
		CachedAt: time.Now(),
	}

	// 4. Update Cache
	weatherCacheMutex.Lock()
	weatherCache[normalizedCity] = w
	weatherCacheMutex.Unlock()

	return w
}

func getServerTime() ServerTime {
	now := time.Now()
	// Simplified New Year logic
	return ServerTime{
		Time:    now.Format("15:04"),
		NewYear: false, // Implement if needed
	}
}
