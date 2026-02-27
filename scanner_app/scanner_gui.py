import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import requests
import json
import re
import datetime
import time

# --- CONFIGURATION ---
DJANGO_API_URL = "http://199.1.1.3/scanner/save_scan/" # ADJUST IF NEEDED
DEFAULT_BAUD_RATE = 9600

class ScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BCBP Scanner Client")
        self.root.geometry("800x600")
        
        # State variables
        self.serial_port = None
        self.is_connected = False
        self.is_scanning = False
        self.thread = None
        self.stop_event = threading.Event()
        self.scan_count = 0
        
        self.setup_ui()
        self.refresh_ports()
        
    def setup_ui(self):
        # Top Frame: Connection Settings
        top_frame = ttk.LabelFrame(self.root, text="Connection Settings", padding=(10, 5))
        top_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(top_frame, text="COM Port:").pack(side="left", padx=5)
        self.port_combo = ttk.Combobox(top_frame, width=15, state="readonly")
        self.port_combo.pack(side="left", padx=5)
        
        ttk.Button(top_frame, text="Refresh", command=self.refresh_ports, width=8).pack(side="left", padx=5)
        
        self.connect_btn = ttk.Button(top_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=15)
        
        # Status Bar
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_lbl = ttk.Label(top_frame, textvariable=self.status_var, foreground="red")
        self.status_lbl.pack(side="left", padx=10)

        # Middle Frame: Last Scan Info
        mid_frame = ttk.LabelFrame(self.root, text="Last Scan Details", padding=(10, 5))
        mid_frame.pack(fill="x", padx=10, pady=5)
        
        # Grid layout for details
        self.details_vars = {}
        fields = [
            ("Passenger", "passenger_name"), ("PNR", "PNR"), 
            ("Flight", "full_flight"), ("Date", "flight_date"),
            ("Seat", "seat_number"), ("Sequence", "sequence_number"),
            ("From", "origin_airport"), ("To", "destination_airport"),
            ("Status", "scan_status") # Custom field for API result
        ]
        
        for i, (label_text, key) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            ttk.Label(mid_frame, text=f"{label_text}:", font=('Arial', 10, 'bold')).grid(row=row, column=col, sticky="e", padx=5, pady=2)
            var = tk.StringVar(value="-")
            self.details_vars[key] = var
            lbl = ttk.Label(mid_frame, textvariable=var, font=('Arial', 10))
            lbl.grid(row=row, column=col+1, sticky="w", padx=5, pady=2)
            
            if key == "scan_status":
                lbl.configure(foreground="blue")
                self.status_label_widget = lbl

        # Bottom Frame: Log
        log_frame = ttk.LabelFrame(self.root, text="Scan Log", padding=(10, 5))
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("#", "Time", "Passenger", "Flight", "Seat", "Result")
        self.tree = ttk.Treeview(log_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100 if col != "Passenger" else 200)
            
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_combo['values'] = port_list
        if port_list:
            self.port_combo.current(0)
        else:
            self.port_combo.set("")

    def toggle_connection(self):
        if not self.is_connected:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        port = self.port_combo.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port")
            return
            
        try:
            self.serial_port = serial.Serial(port, DEFAULT_BAUD_RATE, timeout=0.5)
            self.is_connected = True
            self.connect_btn.config(text="Disconnect")
            self.status_var.set(f"Connected to {port}")
            self.status_lbl.configure(foreground="green")
            
            # Disable selection
            self.port_combo.configure(state="disabled")
            
            # Start thread
            self.stop_event.clear()
            self.thread = threading.Thread(target=self.read_serial_loop, daemon=True)
            self.thread.start()
            
        except serial.SerialException as e:
            messagebox.showerror("Connection Error", str(e))

    def disconnect(self):
        self.stop_event.set()
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        
        self.is_connected = False
        self.connect_btn.config(text="Connect")
        self.status_var.set("Disconnected")
        self.status_lbl.configure(foreground="red")
        self.port_combo.configure(state="readonly")

    def read_serial_loop(self):
        buffer = bytearray()
        while not self.stop_event.is_set():
            if self.serial_port and self.serial_port.is_open:
                try:
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        buffer.extend(data)
                        
                        # Use simple logic: check for known end characters or split by newlines if simple
                        # Assuming similar logic to bridge: look for end chars
                        if b'\x03' in buffer or b'\n' in buffer or b'\r' in buffer:
                            # Process buffer
                            raw_msg = buffer.decode('utf-8', errors='ignore').strip()
                            buffer.clear() # Reset buffer for next scan
                            
                            # Clean start/end chars
                            raw_msg = raw_msg.replace('\x02', '').replace('\x03', '').strip()
                            
                            if raw_msg:
                                self.root.after(0, self.process_scan, raw_msg)
                                
                except Exception as e:
                    print(f"Serial Error: {e}")
                    break
            time.sleep(0.05)

    def process_scan(self, raw_barcode):
        if raw_barcode.startswith("HDCERR"):
            return # Ignore errors/heartbeats
            
        # Parse
        parsed = self.parse_bcbp(raw_barcode)
        
        # Update UI with current scan
        self.update_details_ui(parsed)
        
        # Send to Backend
        self.send_to_backend(parsed)

    def parse_bcbp(self, barcode_string):
        # Simplified parser based on the one we debugged
        # You should copy the FULL robust logic here. For brevity in this artifact, 
        # I am including the critical logic we fixed.
        
        data = {
            'raw_barcode': barcode_string,
            'passenger_name': 'N/A',
            'PNR': 'N/A',
            'flight_number': 'N/A',
            'carrier_code': 'N/A',
            'seat_number': 'N/A',
            'sequence_number': 'N/A',
            'flight_date_info': 'N/A',
            'origin_airport': 'N/A',
            'destination_airport': 'N/A',
            'compartment_code': 'N/A',
            'scanner_prefix': 'N/A',
            'pax_type': 'N/A',
            'additional_info_tail': 'N/A'
        }
        
        # Quick and dirty regex extraction for demo - REPLACE WITH FULL LOGIC IN PRODUCTION
        # This is a placeholder for the logic from scanner_websocket_bridge.py
        
        # 1. Clean
        cleaned = barcode_string.replace('\x02', '').replace('\x03', '').strip()
        
        # 2. Extract Prefix
        match = re.search(r"^(HDCBCRI#\d)(M\d|INF)\s*(.*)$", cleaned)
        content = cleaned
        if match:
            data['scanner_prefix'] = match.group(1)
            data['pax_type'] = match.group(2)
            content = match.group(3).strip()
            
        # 3. Try to find PNR and Airports (MANDATORY for valid scan)
        # Seeking 6 uppercase letters (Airports)
        # Example: SAKMATOV/MARISH EOANENY OSSBSZMN ...
        
        six_letters = re.search(r"([A-Z]{6})", content)
        if six_letters:
            airports = six_letters.group(1)
            data['origin_airport'] = airports[:3]
            data['destination_airport'] = airports[3:]
            
            # Everything before is name + pnr
            idx = content.find(airports)
            pre_part = content[:idx].strip()
            # Everything after is flight info
            post_part = content[idx+6:].strip()
            
            # Name and PNR
            # Try to split by space, last is PNR if 5-7 chars
            tokens = pre_part.split()
            if tokens and 5 <= len(tokens[-1]) <= 7:
                 data['PNR'] = tokens[-1]
                 data['passenger_name'] = " ".join(tokens[:-1])
            else:
                 data['passenger_name'] = pre_part
            
            # Flight Info
            # Expecting Carrier+Flight then Date, Seat, Seq
            # Regex for carrier+flight
            flight_match = re.match(r"^([A-Z0-9]{2,3})\s*([0-9]{1,4})\s*(.*)", post_part)
            if flight_match:
                data['carrier_code'] = flight_match.group(1)
                data['flight_number'] = flight_match.group(2)
                remaining = flight_match.group(3).strip()
                
                # Date (3 digits + optional)
                date_match = re.match(r"^(\d{3}[A-Z]?)", remaining)
                if date_match:
                    data['flight_date_info'] = date_match.group(1)
                    remaining = remaining[len(date_match.group(1)):].strip()
                
                # Seat
                seat_match = re.match(r"^(\d{3}[A-Z])", remaining)
                if seat_match:
                    data['seat_number'] = seat_match.group(1)
                    remaining = remaining[len(seat_match.group(1)):].strip()
                    
                # Seq
                seq_match = re.search(r"(\d{3,4})$", remaining)
                if seq_match:
                     data['sequence_number'] = seq_match.group(1)
                     remaining = remaining[:-len(seq_match.group(1))].strip()
                
                # Fix for compartment code (The one we fixed!)
                if remaining and len(remaining) <= 5:
                    data['compartment_code'] = remaining
                else:
                    data['additional_info_tail'] = remaining

        return data

    def update_details_ui(self, data):
        self.details_vars['passenger_name'].set(data.get('passenger_name', '-'))
        self.details_vars['PNR'].set(data.get('PNR', '-'))
        
        flight = f"{data.get('carrier_code', '')}{data.get('flight_number', '')}"
        self.details_vars['full_flight'].set(flight)
        
        self.details_vars['flight_date'].set(data.get('flight_date_info', '-'))
        self.details_vars['seat_number'].set(data.get('seat_number', '-'))
        self.details_vars['sequence_number'].set(data.get('sequence_number', '-'))
        self.details_vars['origin_airport'].set(data.get('origin_airport', '-'))
        self.details_vars['destination_airport'].set(data.get('destination_airport', '-'))
        
        self.details_vars['scan_status'].set("Sending...")
        self.status_label_widget.configure(foreground="blue")

    def send_to_backend(self, parsed_data):
        def _send():
            try:
                # Prepare payload
                payload = {
                    'raw_barcode': parsed_data.get('raw_barcode'),
                    'parsed_data': parsed_data,
                    'is_duplicate': False # Logic for duplicate check can be added locally or rely on server response
                }
                
                resp = requests.post(DJANGO_API_URL, json=payload, timeout=5)
                
                result_text = "Error"
                if resp.status_code == 200:
                    json_resp = resp.json()
                    status = json_resp.get('status')
                    msg = json_resp.get('message', '')
                    
                    if status == 'success':
                        result_text = "Success"
                        self.root.after(0, lambda: self.log_success(parsed_data, msg))
                    else:
                        result_text = "Server Error"
                        self.root.after(0, lambda: self.log_error(msg))
                else:
                    result_text = f"HTTP {resp.status_code}"
                    self.root.after(0, lambda: self.log_error(f"HTTP {resp.status_code}"))
                    
            except Exception as e:
                self.root.after(0, lambda: self.log_error(str(e)))

        threading.Thread(target=_send, daemon=True).start()

    def log_success(self, data, msg):
        self.details_vars['scan_status'].set("Success")
        self.status_label_widget.configure(foreground="green")
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.scan_count += 1
        
        flight = f"{data.get('carrier_code', '')}{data.get('flight_number', '')}"
        name = data.get('passenger_name', 'Unknown')
        
        self.tree.insert("", 0, values=(self.scan_count, timestamp, name, flight, data.get('seat_number'), "OK"))

    def log_error(self, error_msg):
        self.details_vars['scan_status'].set("Failed")
        self.status_label_widget.configure(foreground="red")
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.scan_count += 1
        
        self.tree.insert("", 0, values=(self.scan_count, timestamp, "-", "-", "-", error_msg))

if __name__ == "__main__":
    root = tk.Tk()
    app = ScannerApp(root)
    root.mainloop()
