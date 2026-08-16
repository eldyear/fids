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
USERS_FILE = "users.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"api_url": "http://199.1.1.3/scanner/save_scan/", "com_port": "", "baud_rate": 9600}

def save_config(config_data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

C = {
    "bg": "#0f1117", "card": "#1a1d2e", "accent": "#6c63ff",
    "accent2": "#4ecdc4", "text": "#e8e8f0", "text_dim": "#8888aa",
    "success": "#43e97b", "error": "#ff4757", "border": "#2d3050",
    "btn_bg": "#252840",
}

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


class PinLoginDialog:
    def __init__(self, root):
        self.root = root
        self.result = None
        self.pin = ""
        self.users = load_users()

        self.dialog = tk.Toplevel(root)
        self.dialog.title("Авторизация")
        self.dialog.geometry("340x380")
        self.dialog.resizable(False, False)
        self.dialog.configure(bg=C["bg"])
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        self.dialog.geometry(f"340x380+{(sw-340)//2}+{(sh-380)//2}")

        self._build_ui()
        self.dialog.bind("<Key>", self._on_key)
        self.dialog.focus_set()

    def _build_ui(self):
        tk.Label(self.dialog, text="\u2708", font=("Segoe UI", 42),
                 bg=C["bg"], fg=C["accent"]).pack(pady=(28, 2))
        tk.Label(self.dialog, text="BCBP Scanner", font=("Segoe UI", 15, "bold"),
                 bg=C["bg"], fg=C["text"]).pack()
        tk.Label(self.dialog, text="Введите PIN-код", font=("Segoe UI", 10),
                 bg=C["bg"], fg=C["text_dim"]).pack(pady=(4, 20))

        dot_frame = tk.Frame(self.dialog, bg=C["bg"])
        dot_frame.pack()
        self.dots = []
        for _ in range(4):
            d = tk.Label(dot_frame, text="\u25cb", font=("Segoe UI", 22),
                         bg=C["bg"], fg=C["text_dim"], width=3)
            d.pack(side="left", padx=6)
            self.dots.append(d)

        self.msg_var = tk.StringVar(value="")
        tk.Label(self.dialog, textvariable=self.msg_var, font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["error"]).pack(pady=12)

        tk.Button(self.dialog, text="Отмена", font=("Segoe UI", 9),
                  bg=C["btn_bg"], fg=C["text_dim"], relief="flat", bd=0,
                  padx=20, pady=7, cursor="hand2", command=self._on_cancel,
                  activebackground=C["border"], activeforeground=C["text"]).pack(pady=8)

    def _update_dots(self):
        for i, d in enumerate(self.dots):
            if i < len(self.pin):
                d.configure(text="\u25cf", fg=C["accent"])
            else:
                d.configure(text="\u25cb", fg=C["text_dim"])

    def _on_key(self, event):
        if event.char.isdigit() and len(self.pin) < 4:
            self.pin += event.char
            self.msg_var.set("")
            self._update_dots()
            if len(self.pin) == 4:
                self.dialog.after(120, self._check_pin)
        elif event.keysym == "BackSpace":
            self.pin = self.pin[:-1]
            self.msg_var.set("")
            self._update_dots()

    def _check_pin(self):
        for user in self.users:
            if str(user.get("pin", "")) == self.pin:
                self.result = user
                self.dialog.destroy()
                return
        for d in self.dots:
            d.configure(fg=C["error"])
        self.msg_var.set("Неверный PIN. Попробуйте снова.")
        self.dialog.after(700, self._reset)

    def _reset(self):
        self.pin = ""
        self._update_dots()

    def _on_cancel(self):
        self.result = None
        self.dialog.destroy()
        self.root.destroy()


class AdvancedScannerApp:
    def __init__(self, root, current_user):
        self.root = root
        self.current_user = current_user
        name = current_user.get("full_name", "Пользователь")
        self.root.title(f"BCBP Scanner — {name}")
        self.root.geometry("900x680")
        self.root.configure(bg=C["bg"])

        self.config = load_config()
        self.serial_port = None
        self.is_connected = False
        self.thread = None
        self.stop_event = threading.Event()
        self.scan_count = 0

        self.setup_ui()
        self.refresh_ports()

    def logout(self):
        self.disconnect()
        for w in self.root.winfo_children():
            w.destroy()
        self.root.withdraw()
        dlg = PinLoginDialog(self.root)
        self.root.wait_window(dlg.dialog)
        if dlg.result is None:
            return
        self.current_user = dlg.result
        name = self.current_user.get("full_name", "Пользователь")
        self.root.title(f"BCBP Scanner — {name}")
        self.scan_count = 0
        self.is_connected = False
        self.stop_event = threading.Event()
        self.setup_ui()
        self.refresh_ports()
        self.root.deiconify()

    def setup_ui(self):
        is_admin = self.current_user.get("type") == "admin"
        name = self.current_user.get("full_name", "Пользователь")

        # Header
        hdr = tk.Frame(self.root, bg=C["accent"], height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="\u2708  BCBP Scanner", font=("Segoe UI", 13, "bold"),
                 bg=C["accent"], fg="white").pack(side="left", padx=16)
        tk.Button(hdr, text="Выйти", font=("Segoe UI", 9), bg="#5550d4", fg="white",
                  relief="flat", bd=0, padx=12, cursor="hand2", command=self.logout,
                  activebackground="#4440b0", activeforeground="white").pack(side="right", padx=12, pady=12)
        tk.Label(hdr, text=f"\U0001f464 {name}", font=("Segoe UI", 9),
                 bg=C["accent"], fg="#d0d0ff").pack(side="right", padx=4)

        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=12, pady=8)

        # Settings (admin only)
        self.config_frame = tk.LabelFrame(main, text="  \u2699  Настройки  ",
                                          font=("Segoe UI", 10, "bold"),
                                          bg=C["card"], fg=C["accent"],
                                          bd=1, relief="groove", padx=10, pady=8)
        self.url_var = tk.StringVar(value=self.config.get("api_url", "http://199.1.1.3/scanner/save_scan/"))
        self.url_entry = tk.Entry(self.config_frame, textvariable=self.url_var, width=46,
                                  bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                                  relief="flat", bd=4, font=("Segoe UI", 9))
        self.port_combo = ttk.Combobox(self.config_frame, width=13, font=("Segoe UI", 9))

        if is_admin:
            self.config_frame.pack(fill="x", pady=(0, 8))
            bs = dict(font=("Segoe UI", 9), bg=C["btn_bg"], fg=C["text"],
                      relief="flat", bd=0, padx=10, pady=5, cursor="hand2",
                      activebackground=C["accent"], activeforeground="white")
            tk.Label(self.config_frame, text="API URL:", font=("Segoe UI", 9),
                     bg=C["card"], fg=C["text_dim"]).grid(row=0, column=0, sticky="w", padx=5, pady=3)
            self.url_entry.grid(row=0, column=1, columnspan=3, sticky="w", padx=5, pady=3)
            tk.Label(self.config_frame, text="COM Порт:", font=("Segoe UI", 9),
                     bg=C["card"], fg=C["text_dim"]).grid(row=1, column=0, sticky="w", padx=5, pady=3)
            self.port_combo.grid(row=1, column=1, sticky="w", padx=5, pady=3)
            tk.Button(self.config_frame, text="\U0001f504 Обновить",
                      command=self.refresh_ports, **bs).grid(row=1, column=2, padx=4)
            tk.Button(self.config_frame, text="\U0001f4be Сохранить",
                      command=self.save_settings, **bs).grid(row=1, column=3, padx=4)

        # Connection bar
        conn = tk.Frame(main, bg=C["card"], padx=12, pady=10)
        conn.pack(fill="x", pady=(0, 8))
        self.connect_btn = tk.Button(conn, text="\u26a1  Подключить сканер",
                                     font=("Segoe UI", 10, "bold"),
                                     bg=C["accent"], fg="white", relief="flat", bd=0,
                                     padx=18, pady=8, cursor="hand2",
                                     command=self.toggle_connection,
                                     activebackground="#5550d4", activeforeground="white")
        self.connect_btn.pack(side="left", padx=(0, 16))
        sb = tk.Frame(conn, bg=C["card"])
        sb.pack(side="left")
        tk.Label(sb, text="Статус:", font=("Segoe UI", 9),
                 bg=C["card"], fg=C["text_dim"]).pack(side="left")
        self.status_var = tk.StringVar(value="Отключён")
        self.status_lbl = tk.Label(sb, textvariable=self.status_var,
                                   font=("Segoe UI", 10, "bold"),
                                   bg=C["card"], fg=C["error"])
        self.status_lbl.pack(side="left", padx=6)

        # Last scan card
        sf = tk.LabelFrame(main, text="  \U0001f4cb  Последнее сканирование  ",
                           font=("Segoe UI", 10, "bold"),
                           bg=C["card"], fg=C["accent2"],
                           bd=1, relief="groove", padx=10, pady=8)
        sf.pack(fill="x", pady=(0, 8))
        self.details_vars = {}
        fields = [
            ("Пассажир", "passenger_name"), ("PNR", "PNR"),
            ("Рейс", "full_flight"), ("Дата", "flight_date_info"),
            ("Место", "seat_number"), ("Сек. №", "sequence_number"),
            ("Откуда", "origin_airport"), ("Куда", "destination_airport"),
            ("API Статус", "scan_status"),
        ]
        for i, (lbl_text, key) in enumerate(fields):
            r, c = i // 2, (i % 2) * 2
            tk.Label(sf, text=f"{lbl_text}:", font=("Segoe UI", 9, "bold"),
                     bg=C["card"], fg=C["text_dim"]).grid(row=r, column=c, sticky="e", padx=(10, 4), pady=3)
            var = tk.StringVar(value="—")
            self.details_vars[key] = var
            color = C["accent2"] if key == "scan_status" else C["text"]
            lbl = tk.Label(sf, textvariable=var, font=("Segoe UI", 9),
                           bg=C["card"], fg=color)
            lbl.grid(row=r, column=c + 1, sticky="w", padx=(0, 20), pady=3)
            if key == "scan_status":
                self.status_label_widget = lbl

        # Log
        lf = tk.LabelFrame(main, text="  \U0001f4ca  Журнал сканирований  ",
                           font=("Segoe UI", 10, "bold"),
                           bg=C["card"], fg=C["accent"],
                           bd=1, relief="groove", padx=8, pady=8)
        lf.pack(fill="both", expand=True)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("D.Treeview", background=C["bg"], foreground=C["text"],
                        fieldbackground=C["bg"], font=("Segoe UI", 9), rowheight=26)
        style.configure("D.Treeview.Heading", background=C["btn_bg"],
                        foreground=C["accent"], font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("D.Treeview", background=[("selected", C["accent"])])
        cols = ("#", "Время", "Пассажир", "Рейс", "Место", "Результат")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings",
                                 height=10, style="D.Treeview")
        widths = {"#": 40, "Время": 80, "Пассажир": 200, "Рейс": 80, "Место": 60, "Результат": 140}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths.get(col, 100))
        sb2 = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb2.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")

        if self.config.get("com_port"):
            self.port_combo.set(self.config["com_port"])


    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [p.device for p in ports]
        self.port_combo['values'] = port_list
        if port_list and not self.port_combo.get():
            self.port_combo.current(0)

    def save_settings(self):
        self.config["api_url"] = self.url_var.get().strip()
        self.config["com_port"] = self.port_combo.get().strip()
        if save_config(self.config):
            messagebox.showinfo("Sys", "Настройки сохранены!")
        else:
            messagebox.showerror("Sys", "Ошибка сохранения настроек.")

    def toggle_connection(self):
        if not self.is_connected:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        port = self.port_combo.get().strip()
        if not port:
            messagebox.showerror("Ошибка", "Выберите COM порт")
            return
        try:
            baud = self.config.get("baud_rate", 9600)
            self.serial_port = serial.Serial(port, baud, timeout=0.5)
            self.is_connected = True
            self.connect_btn.config(text="\u23f9  Отключить сканер")
            self.status_var.set(f"Подключён: {port}")
            self.status_lbl.configure(fg=C["success"])
            self.port_combo.configure(state="disabled")
            self.stop_event.clear()
            self.thread = threading.Thread(target=self.read_serial_loop, daemon=True)
            self.thread.start()
        except serial.SerialException as e:
            messagebox.showerror("Ошибка подключения", str(e))

    def disconnect(self):
        self.stop_event.set()
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.connect_btn.config(text="\u26a1  Подключить сканер")
        self.status_var.set("Отключён")
        self.status_lbl.configure(fg=C["error"])
        try:
            self.port_combo.configure(state="normal")
        except Exception:
            pass

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
                    print(f"Serial error: {e}")
                    break
            time.sleep(0.05)

    def process_scan(self, raw_barcode):
        if raw_barcode.startswith("HDCERR"):
            return
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
        self.details_vars['scan_status'].set("Отправка...")
        self.status_label_widget.configure(fg=C["accent2"])
        self.send_to_backend(parsed)

    def send_to_backend(self, parsed_data):
        def _send():
            try:
                payload = {'raw_barcode': parsed_data.get('raw_barcode'),
                           'parsed_data': parsed_data, 'is_duplicate': False,
                           'client_user': self.current_user}
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
        self.details_vars['scan_status'].set("Успешно")
        self.status_label_widget.configure(fg=C["success"])
        self.scan_count += 1
        flight = f"{data.get('carrier_code', '')}{data.get('flight_number', '')}"
        self.tree.insert("", 0, values=(
            self.scan_count,
            datetime.datetime.now().strftime("%H:%M:%S"),
            data.get('passenger_name', 'Unknown'),
            flight, data.get('seat_number'), "OK"))

    def log_error(self, error_msg):
        self.details_vars['scan_status'].set("Ошибка")
        self.status_label_widget.configure(fg=C["error"])
        self.scan_count += 1
        self.tree.insert("", 0, values=(
            self.scan_count,
            datetime.datetime.now().strftime("%H:%M:%S"),
            "-", "-", "-", error_msg))


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    dlg = PinLoginDialog(root)
    root.wait_window(dlg.dialog)
    if dlg.result is None:
        import sys
        sys.exit(0)
    root.deiconify()
    app = AdvancedScannerApp(root, dlg.result)
    root.mainloop()
