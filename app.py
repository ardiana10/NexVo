import sys, sqlite3, csv, os, atexit, base64
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QMessageBox, QMainWindow, QTableWidget, QTableWidgetItem,
    QToolBar, QStatusBar, QListView, QCompleter, QSizePolicy,
    QFileDialog, QHBoxLayout, QDialog, QCheckBox, QScrollArea
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHeaderView
from datetime import datetime

# === Enkripsi (cryptography - Fernet) ===
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# ====== KONFIGURASI KUNCI ENKRIPSI ======
APP_PASSPHRASE = "9@%RM79hiQt%^@7BneHFtRS&9k9*fJ"   # <<< WAJIB kamu ubah
APP_SALT = b"698z*#$&moK&g6^c43WFkS4#3@Ks%&"

_kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=APP_SALT,
    iterations=390000,
)
_KEY = base64.urlsafe_b64encode(_kdf.derive(APP_PASSPHRASE.encode("utf-8")))
_fernet = Fernet(_KEY)

# === Lokasi folder NexVo (tempat app.py) ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _encrypt_file(plain_path: str, enc_path: str):
    with open(plain_path, "rb") as f:
        data = f.read()
    token = _fernet.encrypt(data)
    with open(enc_path, "wb") as f:
        f.write(token)

def _decrypt_file(enc_path: str, plain_path: str):
    with open(enc_path, "rb") as f:
        token = f.read()
    data = _fernet.decrypt(token)
    with open(plain_path, "wb") as f:
        f.write(data)

# === DB utama ===
DB_NAME = os.path.join(BASE_DIR, "app.db")

def get_kecamatan():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS kecamatan (nama_kecamatan TEXT, nama_desa TEXT)")
    cur.execute("SELECT DISTINCT nama_kecamatan FROM kecamatan ORDER BY nama_kecamatan")
    data = [row[0] for row in cur.fetchall()]
    conn.close()
    return data

def get_desa(kecamatan):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT nama_desa FROM kecamatan WHERE nama_kecamatan = ? ORDER BY nama_desa", (kecamatan,))
    data = [row[0] for row in cur.fetchall()]
    conn.close()
    return data

# =====================================================
# Dialog Setting Aplikasi
# =====================================================
class SettingDialog(QDialog):
    def __init__(self, parent=None, db_name=DB_NAME):
        super().__init__(parent)
        self.setWindowTitle("Tampilan Pemutakhiran")
        self.setFixedSize(280, 380)
        self.db_name = db_name

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        inner = QWidget()
        vbox = QVBoxLayout(inner)

        self.columns = [
            ("DPID", "DPID"),
            ("KECAMATAN", "Kecamatan"),
            ("DESA", "Kelurahan/Desa"),
            ("JK", "Jenis Kelamin"),
            ("TMPT_LHR", "Tempat Lahir"),
            ("ALAMAT", "Alamat"),
            ("DIS", "Disabilitas"),
            ("KTPel", "KTP Elektronik"),
            ("SUMBER", "Sumber"),
            ("KET", "Saringan"),
            ("LastUpdate", "LastUpdate"),
        ]

        self.checks = {}
        for col, label in self.columns:
            cb = QCheckBox(label)
            cb.setStyleSheet("font-size: 10pt; color: white;")
            vbox.addWidget(cb)
            self.checks[col] = cb

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # Tombol
        btn_layout = QHBoxLayout()
        btn_tutup = QPushButton("Tutup")
        btn_simpan = QPushButton("Simpan")

        btn_tutup.setStyleSheet("background:#444; color:white; min-width:100px; min-height:30px; border-radius:6px;")
        btn_simpan.setStyleSheet("background:#ff6600; color:white; font-weight:bold; min-width:100px; min-height:30px; border-radius:6px;")

        btn_tutup.clicked.connect(self.reject)
        btn_simpan.clicked.connect(self.save_settings)

        btn_layout.addWidget(btn_tutup)
        btn_layout.addWidget(btn_simpan)
        layout.addLayout(btn_layout)

        self.load_settings()

    def load_settings(self):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS setting_aplikasi (nama_kolom TEXT PRIMARY KEY, tampil INTEGER)")
        cur.execute("SELECT nama_kolom, tampil FROM setting_aplikasi")
        rows = dict(cur.fetchall())
        conn.close()

        for col, _ in self.columns:
            if col in rows:
                self.checks[col].setChecked(bool(rows[col]))
            else:
                self.checks[col].setChecked(True)  # default ON

    def save_settings(self):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        for col, _ in self.columns:
            val = 1 if self.checks[col].isChecked() else 0
            cur.execute("INSERT OR REPLACE INTO setting_aplikasi (nama_kolom, tampil) VALUES (?, ?)", (col, val))
        conn.commit()
        conn.close()
        self.accept()   # close dialog dengan "OK"

# =====================================================
# Main Window (Setelah login)
# =====================================================
class MainWindow(QMainWindow):
    def __init__(self, username, kecamatan, desa, db_name):
        super().__init__()
        self.setWindowTitle("Sidalih Pilkada 2024 Desktop v2.2.29 - Pemutakhiran Data")
        self.resize(900, 550)

        # ✅ simpan info login (wajib ada agar import_csv tidak error)
        self.kecamatan_login = kecamatan.upper()
        self.desa_login = desa.upper()
        self.username = username

        # Path database absolut
        self.db_name = db_name

        # ==== Enkripsi: siapkan path encrypted & plaintext sementara ====
        base = os.path.basename(self.db_name)
        self.enc_path = self.db_name + ".enc"
        self.plain_db_path = os.path.join(BASE_DIR, f"temp_{base}")

        if os.path.exists(self.enc_path):
            try:
                _decrypt_file(self.enc_path, self.plain_db_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Gagal dekripsi database:\n{e}")
                conn = sqlite3.connect(self.plain_db_path)
                conn.close()
        else:
            conn = sqlite3.connect(self.plain_db_path)
            conn.close()

        self.db_name = self.plain_db_path

        self.all_data = []
        self.current_page = 1
        self.rows_per_page = 100
        self.total_pages = 1

        self.table = QTableWidget()
        columns = [
            " ","KECAMATAN","DESA","DPID","NKK","NIK","NAMA","JK","TMPT_LHR","TGL_LHR",
            "STS","ALAMAT","RT","RW","DIS","KTPel","SUMBER","KET","TPS","LastUpdate","CEK DATA"
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        self.table.setStyleSheet("""
            QTableWidget {
                font-family: Calibri;
                font-size: 12px;
                gridline-color: rgba(255,255,255,80);
                border: 1px solid rgba(255,255,255,80);
            }
            QHeaderView::section {
                font-family: Calibri;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid rgba(255,255,255,80);
            }
        """)

        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setFixedHeight(24)

        col_widths = {
            " ": 30,
            "KECAMATAN": 120,
            "DESA": 150,
            "DPID": 100,
            "NKK": 130,
            "NIK": 130,
            "NAMA": 180,
            "JK": 50,
            "TMPT_LHR": 120,
            "TGL_LHR": 100,
            "STS": 80,
            "ALAMAT": 250,
            "RT": 50,
            "RW": 50,
            "DIS": 60,
            "KTPel": 80,
            "SUMBER": 100,
            "KET": 100,
            "TPS": 80,
            "LastUpdate": 100,
            "CEK DATA": 200
        }
        for idx, col in enumerate(columns):
            if col in col_widths:
                self.table.setColumnWidth(idx, col_widths[col])
        
        # === Auto resize kolom sesuai isi, tapi tetap bisa manual resize ===
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 30)
        header.setStretchLastSection(True)
        self.pagination_container = QWidget()
        self.pagination_layout = QHBoxLayout(self.pagination_container)
        self.pagination_layout.setContentsMargins(0, 2, 0, 2)
        self.pagination_layout.setSpacing(4)
        self.pagination_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        central_box = QWidget()
        v = QVBoxLayout(central_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.table)
        v.addWidget(self.pagination_container)
        self.setCentralWidget(central_box)

        self.table.itemChanged.connect(self.on_item_changed)

        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                font-family: Calibri;
                font-size: 12px;
                padding: 0px;
                margin-bottom: -6px;
            }
            QMenuBar::item {
                padding: 2px 8px;
                spacing: 4px;
            }
            QMenuBar::item:selected {
                background: rgba(255, 255, 255, 40);
                border-radius: 3px;
            }
        """)

        file_menu = menubar.addMenu("File")
        action_dashboard = QAction("Dashboard", self)
        action_dashboard.setShortcut("Alt+H")
        file_menu.addAction(action_dashboard)
        action_pemutakhiran = QAction("Pemutakhiran Data", self)
        action_pemutakhiran.setShortcut("Alt+C")
        file_menu.addAction(action_pemutakhiran)
        action_unggah_reguler = QAction("Unggah Webgrid TPS Reguler", self)
        action_unggah_reguler.setShortcut("Alt+I")
        file_menu.addAction(action_unggah_reguler)
        action_rekap = QAction("Rekapitulasi", self)
        action_rekap.setShortcut("Alt+R")
        file_menu.addAction(action_rekap)
        action_import = QAction("Import CSV", self)
        action_import.setShortcut("Alt+M")
        action_import.triggered.connect(self.import_csv)
        file_menu.addAction(action_import)
        file_menu.addSeparator()
        action_keluar = QAction("Keluar", self)
        action_keluar.setShortcut("Ctrl+W")
        action_keluar.triggered.connect(self.close)
        file_menu.addAction(action_keluar)

        generate_menu = menubar.addMenu("Generate")
        view_menu = menubar.addMenu("View")
        view_menu.addAction(QAction("Reload", self, shortcut="Ctrl+R"))
        view_menu.addAction(QAction("Force Reload", self, shortcut="Ctrl+Shift+R"))
        view_menu.addAction(QAction("Actual Size", self, shortcut="Ctrl+0"))
        view_menu.addAction(QAction("Zoom In", self, shortcut="Ctrl+Shift+="))
        view_menu.addAction(QAction("Zoom Out", self, shortcut="Ctrl+-"))
        view_menu.addSeparator()
        view_menu.addAction(QAction("Toggle Full Screen", self, shortcut="F11"))

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(QAction("Shortcut", self, shortcut="Alt+Z"))
        action_setting = QAction("Setting Aplikasi", self)
        action_setting.setShortcut("Alt+T")
        action_setting.triggered.connect(self.show_setting_dialog)
        help_menu.addAction(action_setting)
        help_menu.addAction(QAction("Hapus Data Pemilih", self))
        help_menu.addAction(QAction("Backup", self))
        help_menu.addAction(QAction("Restore", self))
        help_menu.addAction(QAction("cekdptonline.kpu.go.id", self))

        toolbar = QToolBar("Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        btn_baru = QPushButton("Baru")
        btn_baru.setStyleSheet("font-family: Calibri; font-size: 13px; text-align: center; background-color: green; color: white;")
        toolbar.addWidget(btn_baru)
        btn_rekap = QPushButton("Rekap")
        btn_rekap.setStyleSheet("font-family: Calibri; font-size: 13px;")
        toolbar.addWidget(btn_rekap)
        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_left)
        self.user_label = QLabel(username)
        self.user_label.setStyleSheet("font-family: Calibri; font-weight: bold; font-size: 14px;")
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.user_label)
        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_right)
        btn_tools = QPushButton("Tools")
        btn_tools.setStyleSheet("font-family: Calibri; font-size: 13px;")
        toolbar.addWidget(btn_tools)
        btn_filter = QPushButton("Filter")
        btn_filter.setStyleSheet("font-family: Calibri; font-size: 13px; background-color: orange; font-weight: bold;")
        toolbar.addWidget(btn_filter)
        for btn in [btn_baru, btn_rekap, btn_tools, btn_filter]:
            btn.setFixedHeight(30)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_selected = QLabel("0 selected")
        self.lbl_total = QLabel("0 total")
        self.lbl_version = QLabel("NexVo v1.0")
        self.status.addWidget(self.lbl_selected)
        self.status.addWidget(self.lbl_total)
        self.status.addPermanentWidget(self.lbl_version)

        self.update_pagination()
        self.load_data_from_db()
        self.apply_column_visibility()

        # ✅ Tambahkan ini biar auto resize kolom jalan setelah login
        QTimer.singleShot(0, self.auto_fit_columns)

        atexit.register(self._encrypt_and_cleanup)

    def show_setting_dialog(self):
        dlg = SettingDialog(self, self.db_name)
        if dlg.exec():
            self.apply_column_visibility()
            self.auto_fit_columns()

    def apply_column_visibility(self):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS setting_aplikasi (nama_kolom TEXT PRIMARY KEY, tampil INTEGER)")
        cur.execute("SELECT nama_kolom, tampil FROM setting_aplikasi")
        settings = dict(cur.fetchall())
        conn.close()

        for i in range(self.table.columnCount()):
            col_name = self.table.horizontalHeaderItem(i).text()
            if col_name in settings:
                self.table.setColumnHidden(i, settings[col_name] == 0)

    def closeEvent(self, event):
        self._encrypt_and_cleanup()
        super().closeEvent(event)

    def _encrypt_and_cleanup(self):
        try:
            if os.path.exists(self.plain_db_path):
                _encrypt_file(self.plain_db_path, self.enc_path)
                os.remove(self.plain_db_path)
        except Exception as e:
            print(f"[WARN] Gagal encrypt/cleanup: {e}")

    def auto_fit_columns(self):
        header = self.table.horizontalHeader()
        self.table.resizeColumnsToContents()

        max_widths = {
            "CEK DATA": 200,   # cukup untuk yyyy-mm-dd
        }

        for i in range(self.table.columnCount()):
            col_name = self.table.horizontalHeaderItem(i).text()
            if col_name in max_widths:
                current = self.table.columnWidth(i)
                if current > max_widths[col_name]:
                    self.table.setColumnWidth(i, max_widths[col_name])

        # Jangan stretch kolom terakhir, tapi stretch kolom tertentu saja
        header.setStretchLastSection(False)
        header.setSectionResizeMode(self.table.columnCount()-1, QHeaderView.ResizeMode.Interactive)


    # =================================================
    # Import CSV Function (sekarang benar jadi method)
    # =================================================
    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = list(csv.reader(csvfile, delimiter="#"))
                if len(reader) < 15:
                    QMessageBox.warning(self, "Error", "File CSV tidak valid atau terlalu pendek.")
                    return

                # Verifikasi baris-15 kolom-2 & kolom-4
                kecamatan_csv = reader[14][1].strip().upper()
                desa_csv = reader[14][3].strip().upper()
                if kecamatan_csv != self.kecamatan_login or desa_csv != self.desa_login:
                    QMessageBox.warning(
                        self, "Error",
                        f"Verifikasi gagal!\nCSV Kecamatan='{kecamatan_csv}', Desa='{desa_csv}'\n"
                        f"Login Kecamatan='{self.kecamatan_login}', Desa='{self.desa_login}'"
                    )
                    return

                header = [h.strip().upper() for h in reader[0]]
                mapping = {
                    "KECAMATAN": "KECAMATAN",
                    "KELURAHAN": "DESA",
                    "DPID": "DPID",
                    "NKK": "NKK",
                    "NIK": "NIK",
                    "NAMA": "NAMA",
                    "KELAMIN": "JK",
                    "TEMPAT LAHIR": "TMPT_LHR",
                    "TANGGAL LAHIR": "TGL_LHR",
                    "STS KAWIN": "STS",
                    "ALAMAT": "ALAMAT",
                    "RT": "RT",
                    "RW": "RW",
                    "DISABILITAS": "DIS",
                    "EKTP": "KTPel",
                    "KETERANGAN": "KET",
                    "SUMBER": "SUMBER",
                    "TPS": "TPS",
                    "UPDATED_AT": "LastUpdate"
                }

                idx_status = header.index("STATUS")

                conn = sqlite3.connect(self.db_name)
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS data_pemilih (
                        KECAMATAN TEXT,
                        DESA TEXT,
                        DPID TEXT,
                        NKK TEXT,
                        NIK TEXT,
                        NAMA TEXT,
                        JK TEXT,
                        TMPT_LHR TEXT,
                        TGL_LHR TEXT,
                        STS TEXT,
                        ALAMAT TEXT,
                        RT TEXT,
                        RW TEXT,
                        DIS TEXT,
                        KTPel TEXT,
                        KET TEXT,
                        SUMBER TEXT,
                        TPS TEXT,
                        LastUpdate DATETIME,
                        CEK DATA TEXT
                    )
                """)
                cur.execute("DELETE FROM data_pemilih")

                self.all_data = []
                for row in reader[1:]:
                    status_val = row[idx_status].strip().upper()
                    if status_val not in ("AKTIF", "UBAH", "BARU"):
                        continue
                    data_dict, values = {}, []
                    for csv_col, app_col in mapping.items():
                        if csv_col in header:
                            col_idx = header.index(csv_col)
                            val = row[col_idx].strip()
                            if app_col == "KET":
                                val = "0"
                            data_dict[app_col] = val
                            values.append(val)
                    self.all_data.append(data_dict)

                    placeholders = ",".join(["?"] * len(mapping))
                    cur.execute(
                        f"INSERT INTO data_pemilih ({','.join(mapping.values())}) VALUES ({placeholders})",
                        values
                    )

                conn.commit()
                conn.close()

                self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
                self.show_page(1)
                QMessageBox.information(self, "Sukses", f"Import CSV selesai!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal import CSV: {e}")

    # =================================================
    # Load data dari database saat login ulang
    # =================================================
    def load_data_from_db(self):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        # ✅ Buat tabel jika belum ada
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_pemilih (
                KECAMATAN TEXT,
                DESA TEXT,
                DPID TEXT,
                NKK TEXT,
                NIK TEXT,
                NAMA TEXT,
                JK TEXT,
                TMPT_LHR TEXT,
                TGL_LHR TEXT,
                STS TEXT,
                ALAMAT TEXT,
                RT TEXT,
                RW TEXT,
                DIS TEXT,
                KTPel TEXT,
                KET TEXT,
                SUMBER TEXT,
                TPS TEXT,
                LastUpdate DATETIME,
                CEK DATA TEXT
            )
        """)
        cur.execute("SELECT * FROM data_pemilih")
        rows = cur.fetchall()
        conn.close()

        self.all_data = []
        columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]

        for row in rows:
            data_dict = {}
            for col, val in zip(columns[1:], row):
                if col == "LastUpdate" and val:
                    try:
                        # kalau format ISO penuh
                        dt = datetime.fromisoformat(str(val))
                        val = dt.strftime("%d/%m/%Y")
                    except Exception:
                        # fallback kalau sudah string DD/MM/YYYY
                        try:
                            dt = datetime.strptime(str(val), "%Y-%m-%d")
                            val = dt.strftime("%d/%m/%Y")
                        except:
                            pass
                data_dict[col] = str(val) if val is not None else ""
            self.all_data.append(data_dict)

        self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
        self.show_page(1)


    # =================================================
    # Update status bar selected & total
    # =================================================
    def update_statusbar(self):
        total = len(self.all_data)
        selected = 0
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected += 1
        self.lbl_selected.setText(f"{selected} selected")
        self.lbl_total.setText(f"{total} total")

    def on_item_changed(self, item):
        if item.column() == 0:  # kolom checkbox
            row = item.row()
            checked = (item.checkState() == Qt.CheckState.Checked)
            for c in range(self.table.columnCount()):
                cell = self.table.item(row, c)
                if not cell:
                    cell = QTableWidgetItem("")
                    self.table.setItem(row, c, cell)
                cell.setBackground(Qt.GlobalColor.darkGray if checked else Qt.GlobalColor.transparent)
            self.update_statusbar()

    # =================================================
    # Show page data
    # =================================================
    def show_page(self, page):
        if page < 1 or page > self.total_pages:
            return
        self.current_page = page
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        start = (page - 1) * self.rows_per_page
        end = start + self.rows_per_page
        data_rows = self.all_data[start:end]

        self.table.setRowCount(len(data_rows))
        app_columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        center_cols = {"DPID", "JK", "STS", "TGL_LHR", "RT", "RW", "DIS", "KTPel", "KET", "TPS"}

        for i, d in enumerate(data_rows):
            # Kolom checkbox
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, chk)

            # Isi data
            for j, col in enumerate(app_columns[1:], start=1):
                val = d.get(col, "")

                if col == "KET":
                    val = "0"

                if col == "LastUpdate" and val:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(val)
                        val = dt.strftime("%d/%m/%Y")
                    except:
                        try:
                            dt = datetime.strptime(val, "%Y-%m-%d")
                            val = dt.strftime("%d/%m/%Y")
                        except:
                            pass

                item = QTableWidgetItem(val)
                if col in center_cols:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, j, item)

        self.table.blockSignals(False)
        self.update_statusbar()
        self.update_pagination()


        # jadwalkan setelah layout selesai, supaya ukuran benar2 final
        QTimer.singleShot(0, self.auto_fit_columns)

    # =================================================
    # Pagination UI
    # =================================================
    def make_page_button(self, text, handler, checked=False, enabled=True):
        btn = QPushButton(text)
        btn.setEnabled(enabled)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.clicked.connect(handler)
        btn.setStyleSheet("""
            QPushButton {
                padding: 2px 6px;
                border: 1px solid rgba(255,255,255,80);
                border-radius: 6px;
            }
            QPushButton:checked {
                border: 2px solid #ffa047;
                font-weight: bold;
            }
        """)
        return btn

    def update_pagination(self):
        for i in reversed(range(self.pagination_layout.count())):
            w = self.pagination_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        if self.total_pages <= 1:
            self.pagination_layout.addWidget(self.make_page_button("1", lambda: None, checked=True, enabled=False))
            return

        prev_btn = self.make_page_button("<", lambda: self.show_page(self.current_page - 1),
                                         checked=False, enabled=(self.current_page > 1))
        self.pagination_layout.addWidget(prev_btn)

        window = 5
        half = window // 2
        start = max(1, self.current_page - half)
        end = min(self.total_pages, start + window - 1)
        start = max(1, end - window + 1)

        if start > 1:
            self.pagination_layout.addWidget(self.make_page_button("1", lambda: self.show_page(1)))
            if start > 2:
                self.pagination_layout.addWidget(QLabel("..."))

        for p in range(start, end + 1):
            self.pagination_layout.addWidget(
                self.make_page_button(str(p), lambda _, x=p: self.show_page(x),
                                      checked=(p == self.current_page))
            )

        if end < self.total_pages:
            if end < self.total_pages - 1:
                self.pagination_layout.addWidget(QLabel("..."))
            self.pagination_layout.addWidget(
                self.make_page_button(str(self.total_pages), lambda: self.show_page(self.total_pages))
            )

        next_btn = self.make_page_button(">", lambda: self.show_page(self.current_page + 1),
                                         checked=False, enabled=(self.current_page < self.total_pages))
        self.pagination_layout.addWidget(next_btn)

# =====================================================
# Login Window (dengan tambahan pilihan Tahapan)
# =====================================================
class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.showMaximized()

        outer_layout = QVBoxLayout()
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        # --- Username ---
        self.user_label = QLabel("Nama Pengguna:")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ketik Username...")
        form_layout.addWidget(self.user_label)
        form_layout.addWidget(self.user_input)

        self.user_input.textChanged.connect(
            lambda text: self.user_input.setText(text.upper()) if text != text.upper() else None
        )

        # --- Kecamatan ---
        self.kec_label = QLabel("Kecamatan:")
        form_layout.addWidget(self.kec_label)

        self.kec_input = QLineEdit()
        self.kec_input.setPlaceholderText("Ketik nama kecamatan...")

        kec_list = get_kecamatan()
        completer = QCompleter(kec_list, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.kec_input.setCompleter(completer)

        popup = completer.popup()
        popup.setStyleSheet("QListView { font-size: 10px; }")

        self.kec_input.textChanged.connect(
            lambda text: self.kec_input.setText(text.upper()) if text != text.upper() else None
        )

        form_layout.addWidget(self.kec_input)

        self.kec_input.editingFinished.connect(self.update_desa)
        completer.activated.connect(self.update_desa)

        # --- Desa ---
        self.desa_label = QLabel("Desa:")
        self.desa_combo = QComboBox()
        self.desa_combo.setView(QListView())
        self.desa_combo.addItem("-- Pilih Desa --")
        form_layout.addWidget(self.desa_label)
        form_layout.addWidget(self.desa_combo)

        # --- Tahapan ---
        self.tahapan_label = QLabel("Tahapan:")
        self.tahapan_combo = QComboBox()
        self.tahapan_combo.addItems(["-- Pilih Tahapan --", "dphp", "dpshp", "dpshpa"])
        form_layout.addWidget(self.tahapan_label)
        form_layout.addWidget(self.tahapan_combo)

        # --- Tombol Login ---
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.check_login)
        form_layout.addWidget(self.login_button)

        center_box = QWidget()
        center_box.setLayout(form_layout)
        center_box.setFixedWidth(300)
        outer_layout.addWidget(center_box, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(outer_layout)

        self.setStyleSheet("""
            QWidget { font-size: 11px; }
            QLineEdit, QComboBox, QPushButton { min-height: 28px; font-size: 11px; }
            QComboBox QAbstractItemView { font-size: 11px; }
        """)

    def update_desa(self):
        kecamatan = self.kec_input.text().strip()
        self.desa_combo.clear()
        if kecamatan:
            desa_list = get_desa(kecamatan)
            self.desa_combo.addItem("-- Pilih Desa --")
            self.desa_combo.addItems(desa_list)
        else:
            self.desa_combo.addItem("-- Pilih Desa --")

    def check_login(self):
        user = self.user_input.text().strip()
        kecamatan = self.kec_input.text().strip()
        desa = self.desa_combo.currentText()
        tahapan = self.tahapan_combo.currentText()

        if not user or not kecamatan or desa == "-- Pilih Desa --" or tahapan == "-- Pilih Tahapan --":
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            msg.setText("Semua field harus diisi!")
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: white;
                    border: 2px solid black;
                    border-radius: 6px;
                }
                QMessageBox QLabel {
                    color: black;
                    qproperty-alignment: AlignLeft;
                    font-size: 10pt;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                    min-height: 25px;
                }
            """)
            msg.exec()
            return

        self.accept_login(user, kecamatan, desa, tahapan)

    def accept_login(self, user, kecamatan, desa, tahapan):
        db_map = {
            "dphp": os.path.join(BASE_DIR, "dphp.db"),
            "dpshp": os.path.join(BASE_DIR, "dpshp.db"),
            "dpshpa": os.path.join(BASE_DIR, "dpshpa.db")
        }
        db_name = db_map.get(tahapan.lower(), os.path.join(BASE_DIR, "dphp.db"))

        if not os.path.exists(db_name + ".enc"):
            # buat file temp kosong biar bisa dipakai pertama kali
            conn = sqlite3.connect(os.path.join(BASE_DIR, f"temp_{os.path.basename(db_name)}"))
            conn.close()

        self.main_window = MainWindow(user.upper(), kecamatan, desa, db_name)
        self.main_window.show()
        self.close()

# =====================================================
# Main
# =====================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    login = LoginWindow()
    login.show()
    sys.exit(app.exec())
