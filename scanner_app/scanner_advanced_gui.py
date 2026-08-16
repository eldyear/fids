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
import os

CONFIG_FILE = "scanner_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "api_url": "http://199.1.1.3/scanner/save_scan/",
        "com_port": "",
        "baud_rate": 9600
    }

def save_config(config_data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def parse_bcbp_data_improved(barcode_string):
    data = {
        'raw_barcode': barcode_string,
        'scanner_prefix': 'N/A',
        'pax_type': 'N/A',
        'passenger_name': 'N/A',
        'PNR': 'N/A',
        'origin_airport': 'N/A',
        'destination_airport': 'N/A',
        'carrier_code': 'N/A',
        'flight_number': 'N/A',
        'flight_date_info': 'N/A',
        'seat_number': 'N/A',
        'sequence_number': 'N/A',
        'additional_info_tail': 'N/A',
        'compartment_code': 'N/A',
    }

    cleaned_string = barcode_string.replace('\x02', '').replace('\x03', '').strip()
    data['raw_barcode'] = cleaned_string

    if cleaned_string.startswith("HDCERR1") or not cleaned_string.strip():
        data['scanner_prefix'] = 'UNKNOWN_FORMAT'
        return data

    initial_block_regex = re.compile(r"^(HDCBCRI#\d)(M\d|INF)\s*(.*)$")
    initial_match = initial_block_regex.match(cleaned_string)
    content_after_initial_prefix = cleaned_string

    if initial_match:
        data['scanner_prefix'] = initial_match.group(1)
        data['pax_type'] = initial_match.group(2)
        content_after_initial_prefix = initial_match.group(3).strip()

    raw_name_candidate = content_after_initial_prefix
    remaining_string_for_flight_details = ""
    
    six_letters_with_carrier_pattern = re.compile(r"^(.+?)\s+([A-Z]{6})([A-Z0-9]{2,3}\s+\d+.*)$")
    six_letters_match = six_letters_with_carrier_pattern.match(content_after_initial_prefix)
    
    if six_letters_match:
        name_and_pnr_block = six_letters_match.group(1).strip()
        airports_6letter = six_letters_match.group(2)
        remaining_string_for_flight_details = six_letters_match.group(3).strip()
        data['origin_airport'] = airports_6letter[0:3]
        data['destination_airport'] = airports_6letter[3:6]
        
        pnr_extract_regex = re.compile(r"^(.+?)\s+([A-Z0-9]{5,7})$")
        pnr_extract_match = pnr_extract_regex.match(name_and_pnr_block)
        
        if pnr_extract_match:
            raw_name_candidate = pnr_extract_match.group(1).strip()
            data['PNR'] = pnr_extract_match.group(2)
        else:
            pnr_extracted = False
            for pnr_regex in [re.compile(r"^(.+?)([A-Z0-9]{7})$"), re.compile(r"^(.+?)([A-Z0-9]{6})$"), re.compile(r"^(.+?)([A-Z0-9]{5})$")]:
                pnr_at_end_match = pnr_regex.match(name_and_pnr_block)
                if pnr_at_end_match:
                    pot_name, pot_pnr = pnr_at_end_match.groups()
                    is_valid_pnr = False
                    if pot_name.endswith('/') or pot_name.endswith(' '):
                        is_valid_pnr = True
                    elif len(pot_pnr) >= 6:
                        if re.search(r'\d', pot_pnr) or (len(pot_pnr) == 6 and '/' in pot_name):
                            is_valid_pnr = True
                    
                    if is_valid_pnr:
                        raw_name_candidate = pot_name.strip()
                        data['PNR'] = pot_pnr
                        pnr_extracted = True
                        break
            
            if not pnr_extracted:
                words = name_and_pnr_block.split()
                if words and 5 <= len(words[-1]) <= 7:
                    data['PNR'] = words[-1]
                    raw_name_candidate = ' '.join(words[:-1])
                else:
                    raw_name_candidate = name_and_pnr_block
    else:
        pnr_marker_regex = re.compile(r"([A-Z0-9]{5,7})\s+([A-Z]{3})([A-Z]{3})([A-Z0-9]*.*)$")
        pnr_marker_match = pnr_marker_regex.search(content_after_initial_prefix)
        if pnr_marker_match:
            data['PNR'] = pnr_marker_match.group(1)
            data['origin_airport'] = pnr_marker_match.group(2)
            data['destination_airport'] = pnr_marker_match.group(3)
            raw_name_candidate = content_after_initial_prefix[:pnr_marker_match.start(1)].strip()
            remaining_string_for_flight_details = pnr_marker_match.group(4).strip()
        else:
            six_letters_anywhere = re.compile(r"([A-Z]{6})")
            six_letters_matches = list(six_letters_anywhere.finditer(content_after_initial_prefix))
            if six_letters_matches:
                first_match = six_letters_matches[0]
                airports_6letter = first_match.group(1)
                data['origin_airport'] = airports_6letter[0:3]
                data['destination_airport'] = airports_6letter[3:6]
                name_and_pnr_block = content_after_initial_prefix[:first_match.start()].strip()
                remaining_string_for_flight_details = content_after_initial_prefix[first_match.end():].strip()
                words = name_and_pnr_block.split()
                if words and 5 <= len(words[-1]) <= 7:
                    data['PNR'] = words[-1]
                    raw_name_candidate = ' '.join(words[:-1])
                else:
                    raw_name_candidate = name_and_pnr_block

    processed_name = raw_name_candidate.replace('<', ' ').strip()
    if '/' in processed_name:
        name_parts = processed_name.split('/')
        data['passenger_name'] = f"{name_parts[0].strip()} / {' '.join(name_parts[1:]).strip()}" if len(name_parts) > 1 else name_parts[0].strip()
    else:
        data['passenger_name'] = processed_name.strip()

    if data['origin_airport'] == 'N/A' and data['destination_airport'] == 'N/A' and remaining_string_for_flight_details:
        airport_carrier_match = re.match(r"^([A-Z]{3})([A-Z]{3})([A-Z0-9]{1,3})?", remaining_string_for_flight_details)
        if airport_carrier_match:
            data['origin_airport'] = airport_carrier_match.group(1)
            data['destination_airport'] = airport_carrier_match.group(2)
            if airport_carrier_match.group(3): data['carrier_code'] = airport_carrier_match.group(3)
            remaining_string_for_flight_details = remaining_string_for_flight_details[airport_carrier_match.end():].strip()

    flight_details_regex = re.compile(r"^([A-Z0-9]{2,3})\s*([A-Z0-9]{1,5})\s*(.*)$")
    flight_match = flight_details_regex.match(remaining_string_for_flight_details)

    if flight_match:
        potential_carrier = flight_match.group(1).strip()
        potential_flight = flight_match.group(2).strip()
        if re.search(r'[A-Z]', potential_carrier):
            data['carrier_code'] = potential_carrier
            data['flight_number'] = potential_flight
            remaining_string_for_flight_details = flight_match.group(3).strip()
        else:
            if potential_flight.isdigit() and len(potential_carrier) <= 4:
                data['flight_number'] = potential_carrier + potential_flight
                remaining_string_for_flight_details = flight_match.group(3).strip()
            else:
                data['carrier_code'] = potential_carrier
                data['flight_number'] = potential_flight
                remaining_string_for_flight_details = flight_match.group(3).strip()
    else:
        parts_of_flight_details = [p for p in re.split(r'\s+', remaining_string_for_flight_details) if p]
        current_segment_index = 0
        if len(parts_of_flight_details) > current_segment_index:
            candidate_carrier_or_flight = parts_of_flight_details[current_segment_index]
            if re.match(r"^[A-Z0-9]{2,3}$", candidate_carrier_or_flight) and re.search(r'[A-Z]', candidate_carrier_or_flight):
                data['carrier_code'] = candidate_carrier_or_flight
                current_segment_index += 1
                if len(parts_of_flight_details) > current_segment_index:
                    candidate_flight_number = parts_of_flight_details[current_segment_index]
                    if re.match(r"^[A-Z0-9]{1,5}$", candidate_flight_number):
                        data['flight_number'] = candidate_flight_number
                        current_segment_index += 1
            elif candidate_carrier_or_flight.isdigit():
                data['flight_number'] = candidate_carrier_or_flight
                current_segment_index += 1
            remaining_string_for_flight_details = " ".join(parts_of_flight_details[current_segment_index:]).strip()

    if remaining_string_for_flight_details:
        complex_data_segment = remaining_string_for_flight_details.strip()
        flight_date_match = re.match(r"^(\d{3}[A-Z]{1,2}\d{0,1})", complex_data_segment)
        if flight_date_match:
            data['flight_date_info'] = flight_date_match.group(1)
            complex_data_segment = complex_data_segment[len(data['flight_date_info']):].strip()

        seat_number_match = re.match(r"^(\d{2,3}[A-Z]{1,2})", complex_data_segment)
        if seat_number_match:
            data['seat_number'] = seat_number_match.group(1)
            complex_data_segment = complex_data_segment[len(data['seat_number']):].strip()

        sequence_number_match = re.search(r"(\d{3,4})$", complex_data_segment)
        if sequence_number_match:
            data['sequence_number'] = sequence_number_match.group(1)
            complex_data_segment = complex_data_segment[:-len(data['sequence_number'])].strip()

        if len(complex_data_segment) > 0:
            data['compartment_code'] = complex_data_segment

        if data.get('seat_number') == '00NO':
            data['seat_number'] = '00'
            data['compartment_code'] = 'NO'

    if remaining_string_for_flight_details:
        data['additional_info_tail'] = remaining_string_for_flight_details.strip()

    if data['flight_number'] == 'N/A' and data['carrier_code'] != 'N/A' and re.match(r"^\d+$", data['carrier_code']):
        data['flight_number'] = data['carrier_code']
        data['carrier_code'] = 'N/A'

    return data


class AdvancedScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BCBP Advanced Scanner Client")
        self.root.geometry("850x650")
        
        self.config = load_config()
        self.serial_port = None
        self.is_connected = False
        self.thread = None
        self.stop_event = threading.Event()
        self.scan_count = 0
        
        self.setup_ui()
        self.refresh_ports()
        
    def setup_ui(self):
        config_frame = ttk.LabelFrame(self.root, text="Settings", padding=(10, 5))
        config_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(config_frame, text="API URL:").grid(row=0, column=0, sticky="w", padx=5)
        self.url_var = tk.StringVar(value=self.config.get("api_url", "http://199.1.1.3/scanner/save_scan/"))
        self.url_entry = ttk.Entry(config_frame, textvariable=self.url_var, width=50)
        self.url_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(config_frame, text="COM Port:").grid(row=1, column=0, sticky="w", padx=5)
        
        port_frame = ttk.Frame(config_frame)
        port_frame.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        self.port_combo = ttk.Combobox(port_frame, width=15)
        self.port_combo.pack(side="left")
        
        ttk.Button(port_frame, text="Refresh Ports", command=self.refresh_ports).pack(side="left", padx=5)
        ttk.Button(port_frame, text="Save Settings", command=self.save_settings).pack(side="left", padx=5)
        
        control_frame = ttk.Frame(config_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=5)
        self.connect_btn = ttk.Button(control_frame, text="Connect Scanner", command=self.toggle_connection, width=20)
        self.connect_btn.pack(side="left", padx=5)
        
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_lbl = ttk.Label(control_frame, textvariable=self.status_var, foreground="red", font=('Arial', 10, 'bold'))
        self.status_lbl.pack(side="left", padx=15)

        mid_frame = ttk.LabelFrame(self.root, text="Last Scan Details", padding=(10, 5))
        mid_frame.pack(fill="x", padx=10, pady=5)
        
        self.details_vars = {}
        fields = [
            ("Passenger", "passenger_name"), ("PNR", "PNR"), 
            ("Flight", "full_flight"), ("Date", "flight_date_info"),
            ("Seat", "seat_number"), ("Sequence", "sequence_number"),
            ("From", "origin_airport"), ("To", "destination_airport"),
            ("API Status", "scan_status")
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

        log_frame = ttk.LabelFrame(self.root, text="Scan Log", padding=(10, 5))
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("#", "Time", "Passenger", "Flight", "Seat", "Result")
        self.tree = ttk.Treeview(log_frame, columns=columns, show="headings", height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120 if col != "Passenger" else 200)
            
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        if self.config.get("com_port"):
            self.port_combo.set(self.config["com_port"])

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_combo['values'] = port_list
        if port_list and not self.port_combo.get():
            self.port_combo.current(0)

    def save_settings(self):
        self.config["api_url"] = self.url_var.get().strip()
        self.config["com_port"] = self.port_combo.get().strip()
        if save_config(self.config):
            messagebox.showinfo("Sys", "Settings saved successfully!")
        else:
            messagebox.showerror("Sys", "Failed to save settings.")

    def toggle_connection(self):
        if not self.is_connected:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        port = self.port_combo.get().strip()
        if not port:
            messagebox.showerror("Error", "Please select a COM port")
            return
            
        try:
            baud = self.config.get("baud_rate", 9600)
            self.serial_port = serial.Serial(port, baud, timeout=0.5)
            self.is_connected = True
            self.connect_btn.config(text="Disconnect Scanner")
            self.status_var.set(f"Connected to {port}")
            self.status_lbl.configure(foreground="green")
            self.port_combo.configure(state="disabled")
            
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
        self.connect_btn.config(text="Connect Scanner")
        self.status_var.set("Disconnected")
        self.status_lbl.configure(foreground="red")
        self.port_combo.configure(state="normal")

    def read_serial_loop(self):
        buffer = bytearray()
        while not self.stop_event.is_set():
            if self.serial_port and self.serial_port.is_open:
                try:
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        buffer.extend(data)
                        if b'\x03' in buffer or b'\n' in buffer or b'\r' in buffer:
                            raw_msg = buffer.decode('utf-8', errors='ignore').strip()
                            buffer.clear()
                            raw_msg = raw_msg.replace('\x02', '').replace('\x03', '').strip()
                            if raw_msg:
                                self.root.after(0, self.process_scan, raw_msg)
                except Exception as e:
                    print(f"Serial log error: {e}")
                    break
            time.sleep(0.05)

    def process_scan(self, raw_barcode):
        if raw_barcode.startswith("HDCERR"): return
        parsed = parse_bcbp_data_improved(raw_barcode)
        
        self.details_vars['passenger_name'].set(parsed.get('passenger_name', '-'))
        self.details_vars['PNR'].set(parsed.get('PNR', '-'))
        flight = f"{parsed.get('carrier_code', '')}{parsed.get('flight_number', '')}"
        self.details_vars['full_flight'].set(flight)
        self.details_vars['flight_date_info'].set(parsed.get('flight_date_info', '-'))
        self.details_vars['seat_number'].set(parsed.get('seat_number', '-'))
        self.details_vars['sequence_number'].set(parsed.get('sequence_number', '-'))
        self.details_vars['origin_airport'].set(parsed.get('origin_airport', '-'))
        self.details_vars['destination_airport'].set(parsed.get('destination_airport', '-'))
        
        self.details_vars['scan_status'].set("Sending...")
        self.status_label_widget.configure(foreground="blue")
        
        self.send_to_backend(parsed)

    def send_to_backend(self, parsed_data):
        def _send():
            try:
                payload = {
                    'raw_barcode': parsed_data.get('raw_barcode'),
                    'parsed_data': parsed_data,
                    'is_duplicate': False
                }
                api_url = self.url_var.get().strip()
                resp = requests.post(api_url, json=payload, timeout=5)
                
                if resp.status_code == 200:
                    json_resp = resp.json()
                    if json_resp.get('status') == 'success':
                        self.root.after(0, lambda: self.log_success(parsed_data, json_resp.get('message', 'OK')))
                    else:
                        self.root.after(0, lambda: self.log_error(json_resp.get('message', 'Server rejected')))
                else:
                    self.root.after(0, lambda: self.log_error(f"HTTP {resp.status_code}"))
            except Exception as e:
                self.root.after(0, lambda: self.log_error(str(e)))

        threading.Thread(target=_send, daemon=True).start()

    def log_success(self, data, msg):
        self.details_vars['scan_status'].set("Success")
        self.status_label_widget.configure(foreground="green")
        self.scan_count += 1
        flight = f"{data.get('carrier_code', '')}{data.get('flight_number', '')}"
        self.tree.insert("", 0, values=(self.scan_count, datetime.datetime.now().strftime("%H:%M:%S"), data.get('passenger_name', 'Unknown'), flight, data.get('seat_number'), "OK"))

    def log_error(self, error_msg):
        self.details_vars['scan_status'].set("Failed")
        self.status_label_widget.configure(foreground="red")
        self.scan_count += 1
        self.tree.insert("", 0, values=(self.scan_count, datetime.datetime.now().strftime("%H:%M:%S"), "-", "-", "-", error_msg))

if __name__ == "__main__":
    root = tk.Tk()
    app = AdvancedScannerApp(root)
    root.mainloop()
