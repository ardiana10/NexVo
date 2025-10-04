import sys, sqlite3, csv, os, atexit, base64, random, string
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QMessageBox, QMainWindow, QTableWidget, QTableWidgetItem,
    QToolBar, QStatusBar, QListView, QCompleter, QSizePolicy,
    QFileDialog, QHBoxLayout, QDialog, QCheckBox, QScrollArea, QHeaderView,
    QStyledItemDelegate, QInputDialog
)
from PyQt6.QtGui import QAction, QPainter, QColor, QPen, QPixmap, QFont, QIcon
from PyQt6.QtCore import Qt, QTimer, QRect

class ModernMessage(QDialog):
    def __init__(self, title, message, icon_type="info", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(320, 180)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                border-radius: 12px;
            }
            QLabel {
                color: white;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            QPushButton {
                background-color: #ff6600;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff8533;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # === Ikon modern ===
        icon_label = QLabel()
        pix = self._create_icon(icon_type)
        icon_label.setPixmap(pix)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # === Pesan ===
        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet("font-size: 11pt; margin: 4px;")
        layout.addWidget(msg)

        # === Tombol OK ===
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _create_icon(self, icon_type):
        """Gambar ikon modern (success, warning, error, info)."""
        pix = QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Warna dasar lingkaran
        colors = {
            "success": "#28a745",   # hijau
            "warning": "#ffc107",   # kuning
            "error":   "#dc3545",   # merah
            "info":    "#17a2b8",   # biru muda
        }
        color = QColor(colors.get(icon_type, "#17a2b8"))
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 64, 64)

        painter.setPen(QPen(QColor("white"), 6))
        if icon_type == "success":
            painter.drawLine(16, 34, 28, 46)
            painter.drawLine(28, 46, 48, 20)
        elif icon_type == "warning":
            painter.drawLine(32, 14, 32, 38)
            painter.drawPoint(32, 50)
        elif icon_type == "error":
            painter.drawLine(20, 20, 44, 44)
            painter.drawLine(44, 20, 20, 44)
        else:  # info
            painter.drawLine(32, 20, 32, 28)
            painter.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
            painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "i")

        painter.end()
        return pix

class CheckboxDelegate(QStyledItemDelegate):
    def __init__(self, theme="dark", parent=None):
        super().__init__(parent)
        self.theme = theme

    def setTheme(self, theme):
        self.theme = theme

    def paint(self, painter, option, index):
        value = index.data(Qt.ItemDataRole.CheckStateRole)
        if value is not None:
            rect = self.get_checkbox_rect(option)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if value == Qt.CheckState.Checked:
                # kotak oranye saat dicentang
                painter.setBrush(QColor("#ff9900"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect, 4, 4)

                # centang putih
                painter.setPen(QPen(QColor("white"), 2))  # biar garis centang lebih jelas
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(rect.left() + 4, rect.center().y(),
                                 rect.center().x(), rect.bottom() - 4)
                painter.drawLine(rect.center().x(), rect.bottom() - 4,
                                 rect.right() - 4, rect.top() + 4)
            else:
                if self.theme == "dark":
                    # dark mode → transparan + border putih tipis
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor("white"), 1))
                    painter.drawRoundedRect(rect, 4, 4)
                else:
                    # light mode → abu-abu dengan border tipis
                    painter.setBrush(QColor("#e0e0e0"))
                    painter.setPen(QPen(QColor("#555"), 1))
                    painter.drawRoundedRect(rect, 4, 4)

            painter.restore()
            return

        super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        if not index.flags() & Qt.ItemFlag.ItemIsUserCheckable or not index.flags() & Qt.ItemFlag.ItemIsEnabled:
            return False

        if event.type() == event.Type.MouseButtonRelease:
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            new_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
            model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
            return True
        return False

    def get_checkbox_rect(self, option):
        size = 14
        x = option.rect.x() + (option.rect.width() - size) // 2
        y = option.rect.y() + (option.rect.height() - size) // 2
        return QRect(x, y, size, size)

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
        self.setFixedSize(280, 400)
        self.db_name = db_name

        layout = QVBoxLayout(self)

        self.setStyleSheet("""
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #555;
                border-radius: 4px;
                background: transparent;
            }
            QCheckBox::indicator:unchecked {
                background: transparent;
                border: 1px solid #888;
            }
            QCheckBox::indicator:checked {
                background-color: #ff9900;   /* oranye */
                border: 1px solid #ff9900;
                image: url(:/qt-project.org/styles/commonstyle/images/checkmark.png);
            }
        """)

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
            cb.setStyleSheet("font-size: 10pt;")
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
    def __init__(self, username, kecamatan, desa, db_name, tahapan):
        super().__init__()
        self.tahapan = tahapan.upper()   # ✅ simpan jenis tahapan (DPHP/DPSHP/DPSHPA)

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

        self.sort_lastupdate_asc = True  # ✅ toggle: True = dari terbaru ke lama, False = sebaliknya

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
        self.table.setShowGrid(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setFixedHeight(24)
        self.checkbox_delegate = CheckboxDelegate("dark")  # default dark
        self.table.setItemDelegateForColumn(0, self.checkbox_delegate)

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
        # === Header dan sorting klik ===
        header = self.table.horizontalHeader()
        try:
            header.sectionClicked.disconnect()  # pastikan tidak dobel koneksi
        except Exception:
            pass
        header.sectionClicked.connect(self.header_clicked)

        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 30)
        header.setStretchLastSection(True)

        # ✅ Tambahkan di sini:
        self.connect_header_events()   # memastikan event klik header LastUpdate aktif


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
        action_dashboard = QAction("  Dashboard", self)
        action_dashboard.setShortcut("Alt+H")
        file_menu.addAction(action_dashboard)
        action_pemutakhiran = QAction("  Pemutakhiran Data", self)
        action_pemutakhiran.setShortcut("Alt+C")
        file_menu.addAction(action_pemutakhiran)
        action_unggah_reguler = QAction("  Unggah Webgrid TPS Reguler", self)
        action_unggah_reguler.setShortcut("Alt+I")
        file_menu.addAction(action_unggah_reguler)
        action_rekap = QAction("  Rekapitulasi", self)
        action_rekap.setShortcut("Alt+R")
        file_menu.addAction(action_rekap)
        action_import = QAction("  Import CSV", self)
        action_import.setShortcut("Alt+M")
        action_import.triggered.connect(self.import_csv)
        file_menu.addAction(action_import)
        file_menu.addSeparator()
        action_keluar = QAction("  Keluar", self)
        action_keluar.setShortcut("Ctrl+W")
        action_keluar.triggered.connect(self.close)
        file_menu.addAction(action_keluar)

        generate_menu = menubar.addMenu("Generate")
        view_menu = menubar.addMenu("View")

        # Menambahkan tema Dark & Light
        action_dark = QAction("  Dark", self, shortcut="Ctrl+D")
        action_dark.triggered.connect(lambda: self.apply_theme("dark"))
        view_menu.addAction(action_dark)

        action_light = QAction("  Light", self, shortcut="Ctrl+L")
        action_light.triggered.connect(lambda: self.apply_theme("light"))
        view_menu.addAction(action_light)

        view_menu.addAction(QAction("  Actual Size", self, shortcut="Ctrl+0"))
        view_menu.addAction(QAction("  Zoom In", self, shortcut="Ctrl+Shift+="))
        view_menu.addAction(QAction("  Zoom Out", self, shortcut="Ctrl+-"))
        view_menu.addSeparator()
        view_menu.addAction(QAction("  Toggle Full Screen", self, shortcut="F11"))

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(QAction("  Shortcut", self, shortcut="Alt+Z"))

        action_setting = QAction("  Setting Aplikasi", self)
        action_setting.setShortcut("Alt+T")
        action_setting.triggered.connect(self.show_setting_dialog)
        help_menu.addAction(action_setting)

        action_hapus_data = QAction("  Hapus Data Pemilih", self)
        action_hapus_data.triggered.connect(self.hapus_data_pemilih)
        help_menu.addAction(action_hapus_data)

        help_menu.addAction(QAction("  Backup", self))
        help_menu.addAction(QAction("  Restore", self))
        help_menu.addAction(QAction("  cekdptonline.kpu.go.id", self))

        # ==========================================================
        # ✅ Tampilkan menu "Import Ecoklit" hanya jika tahapan = DPHP
        # ==========================================================
        if self.tahapan == "DPHP":
            import_ecoklit_menu = menubar.addMenu("Import Ecoklit")

            action_import_baru = QAction("  Import Pemilih Baru", self)
            action_import_tms = QAction("  Import Pemilih TMS", self)
            action_import_ubah = QAction("  Import Pemilih Ubah Data", self)

            # Placeholder fungsi (bisa diisi nanti)
            action_import_baru.triggered.connect(lambda: QMessageBox.information(self, "Info", "Import Pemilih Baru diklik"))
            action_import_tms.triggered.connect(lambda: QMessageBox.information(self, "Info", "Import Pemilih TMS diklik"))
            action_import_ubah.triggered.connect(lambda: QMessageBox.information(self, "Info", "Import Pemilih Ubah Data diklik"))

            import_ecoklit_menu.addAction(action_import_baru)
            import_ecoklit_menu.addAction(action_import_tms)
            import_ecoklit_menu.addAction(action_import_ubah)

       # === Toolbar ===
        toolbar = QToolBar("Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # fungsi bantu untuk bikin jarak antar tombol
        def add_spacer(width=8):
            spacer = QWidget()
            spacer.setFixedWidth(width)
            toolbar.addWidget(spacer)

        # === Tombol kiri ===
        btn_baru = QPushButton("Baru")
        self.style_button(btn_baru, bg="green", fg="white", bold=True)
        toolbar.addWidget(btn_baru)
        add_spacer()

        btn_rekap = QPushButton("Rekap")
        self.style_button(btn_rekap)
        toolbar.addWidget(btn_rekap)

        # === Spacer kiri ke tengah ===
        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_left)

        # === Label User di tengah ===
        self.user_label = QLabel(username)
        self.user_label.setStyleSheet("font-family: Calibri; font-weight: bold; font-size: 14px;")
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.user_label)

        # === Spacer tengah ke kanan ===
        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_right)

        # === Tombol kanan ===
        btn_urutkan = QPushButton("Urutkan")
        self.style_button(btn_urutkan)
        btn_urutkan.clicked.connect(self.sort_data)
        toolbar.addWidget(btn_urutkan)
        add_spacer()

        btn_cekdata = QPushButton("Cek Data")
        self.style_button(btn_cekdata)
        toolbar.addWidget(btn_cekdata)
        add_spacer()

        btn_tools = QPushButton("Tools")
        self.style_button(btn_tools)
        toolbar.addWidget(btn_tools)
        add_spacer()

        btn_filter = QPushButton("Filter")
        self.style_button(btn_filter, bg="orange", fg="black", bold=True)
        toolbar.addWidget(btn_filter)

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

        # ✅ Load theme terakhir dari database
        theme = self.load_theme()
        self.apply_theme(theme)

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

    def save_theme(self, mode):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS setting_aplikasi_theme (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme TEXT
            )
        """)
        cur.execute("DELETE FROM setting_aplikasi_theme")  # hanya simpan 1 row
        cur.execute("INSERT INTO setting_aplikasi_theme (theme) VALUES (?)", (mode,))
        conn.commit()
        conn.close()

    def load_theme(self):
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS setting_aplikasi_theme (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme TEXT
            )
        """)
        cur.execute("SELECT theme FROM setting_aplikasi_theme ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
        return "dark"  # default pertama kali
    
    def style_button(self, btn, width=90, height=28, bg="#2d2d30", fg="white", bold=False):
        btn.setFixedSize(width, height)
        style = f"""
            QPushButton {{
                font-family: Calibri;
                font-size: 12px;
                {"font-weight: bold;" if bold else ""}
                border: 1px solid #666;
                border-radius: 4px;
                padding: 2px 6px;
                background-color: {bg};
                color: {fg};
            }}
            QPushButton:hover {{
                background-color: #3e3e42;
            }}
        """
        btn.setStyleSheet(style)
        return btn

    def apply_theme(self, mode):
        if mode == "dark":
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    font-family: Segoe UI, Calibri, sans-serif;
                }
                QTableWidget {
                    background-color: #1e1e1e;
                    alternate-background-color: #252526;
                    color: #d4d4d4;
                    gridline-color: #3e3e42;
                    selection-background-color: #264f78;
                    selection-color: white;
                }
                QHeaderView::section {
                    background-color: #333333;
                    color: #dcdcdc;
                    font-weight: bold;
                    border: 1px solid #3e3e42;
                    padding: 4px;
                }
                QMenu::item:selected {
                    background-color: #ff9900;   /* 🔥 hover oranye */
                    color: black;
                    border-radius: 4px;
                }
            """)
            self.checkbox_delegate.setTheme("dark")

        elif mode == "light":
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #f9f9f9;
                    color: #333333;
                    font-family: Segoe UI, Calibri, sans-serif;
                }
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f3f3f3;
                    color: #333333;
                    gridline-color: #c0c0c0;
                    selection-background-color: #bcbcbc;
                    selection-color: #000000;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    color: #333333;
                    font-weight: bold;
                    border: 1px solid #c0c0c0;
                    padding: 4px;
                }
                QMenu::item:selected {
                    background-color: #ff9900;   /* 🔥 hover oranye */
                    color: black;
                    border-radius: 4px;
                }
            """)
            self.checkbox_delegate.setTheme("light")

        # ✅ Simpan pilihan theme ke DB
        self.save_theme(mode)

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
                    "SUMBER": "SUMBER",
                    "KETERANGAN": "KET",
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
                        SUMBER TEXT,
                        KET TEXT,
                        TPS TEXT,
                        LastUpdate DATETIME,
                        "CEK DATA" TEXT
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

                            # Pastikan kolom KET selalu "0"
                            if app_col == "KET":
                                val = "0"

                            # ✅ Normalisasi kolom LastUpdate (format jadi DD/MM/YYYY)
                            if app_col == "LastUpdate" and val:
                                try:
                                    from datetime import datetime
                                    # coba berbagai format ISO umum
                                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                                        try:
                                            dt = datetime.strptime(val, fmt)
                                            val = dt.strftime("%d/%m/%Y")
                                            break
                                        except Exception:
                                            continue
                                except Exception:
                                    pass

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

                # ✅ Pastikan klik header aktif setelah render
                self.connect_header_events()

                QMessageBox.information(self, "Sukses", "Import CSV selesai!")

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
                SUMBER TEXT,
                KET TEXT,
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
    # Pengurutan Data
    # =================================================

    def sort_data(self):
        # Konfirmasi sebelum mengurutkan
        reply = QMessageBox.question(
            self,
            "Konfirmasi",
            "Apakah Anda ingin mengurutkan data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return  # batal, tidak ada perubahan

        # Lakukan pengurutan data
        self.all_data.sort(
            key=lambda x: (
                str(x.get("TPS", "")),
                str(x.get("RW", "")),
                str(x.get("RT", "")),
                str(x.get("NKK", "")),
                str(x.get("NAMA", ""))
            )
        )

        # Refresh tampilan tabel (tampilkan ulang page 1)
        self.show_page(1)

        # Pemberitahuan selesai
        QMessageBox.information(self, "Selesai", "Pengurutan data telah selesai!")

    # =================================================
    # Klik Header Kolom "LastUpdate" untuk sorting toggle
    # =================================================
    def header_clicked(self, logicalIndex):
        header_item = self.table.horizontalHeaderItem(logicalIndex)
        if not header_item:
            return

        header_text = header_item.text().strip().upper()
        if header_text != "LASTUPDATE":
            return

        try:
            def parse_tgl(val):
                if not val:
                    return datetime.min
                val = val.strip()
                # ✅ Dukung semua format umum
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(val, fmt)
                    except Exception:
                        continue
                return datetime.min

            # ✅ Sort data berdasarkan kolom LastUpdate
            self.all_data.sort(
                key=lambda x: parse_tgl(x.get("LastUpdate", x.get("LASTUPDATE", ""))),
                reverse=not self.sort_lastupdate_asc
            )

            self.sort_lastupdate_asc = not self.sort_lastupdate_asc
            self.show_page(1)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Gagal mengurutkan kolom LastUpdate:\n{e}")

    def connect_header_events(self):
        """Pastikan koneksi klik header aktif setelah tabel diperbarui."""
        header = self.table.horizontalHeader()
        try:
            header.sectionClicked.disconnect()
        except Exception:
            pass
        header.sectionClicked.connect(self.header_clicked)

        # =================================================
    # Hapus Seluruh Data Pemilih (sub-menu Help)
    # =================================================
    def hapus_data_pemilih(self):
        reply = QMessageBox.question(
            self,
            "Konfirmasi",
            "Apakah Anda yakin ingin menghapus SELURUH data di database ini?\nTindakan ini tidak dapat dibatalkan.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            # Batalkan penghapusan
            QMessageBox.information(self, "Dibatalkan", "Proses penghapusan data dibatalkan.")
            return

        try:
            # Hapus seluruh data dari tabel data_pemilih
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
                    SUMBER TEXT,
                    KET TEXT,
                    TPS TEXT,
                    LastUpdate DATETIME,
                    CEK DATA TEXT
                )
            """)
            cur.execute("DELETE FROM data_pemilih")
            conn.commit()
            conn.close()

            # Kosongkan data di tabel tampilan
            self.all_data.clear()
            self.table.setRowCount(0)
            self.lbl_total.setText("0 total")
            self.lbl_selected.setText("0 selected")

            # ✅ Reset pagination dan refresh tampilan
            self.total_pages = 1
            self.current_page = 1
            self.update_pagination()
            self.show_page(1)

            # ✅ Popup sukses
            QMessageBox.information(
                self,
                "Selesai",
                "Seluruh data pemilih telah berhasil dihapus dari database!"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menghapus data:\n{e}")

    # =================================================
    # Show page data (fix checkbox terlihat)
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
            # ✅ Kolom pertama: checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            chk_item.setData(Qt.ItemDataRole.CheckStateRole, Qt.CheckState.Unchecked)
            chk_item.setText("")  # kosong, biar hanya kotak ceklis
            self.table.setItem(i, 0, chk_item)

            # ✅ Kolom lainnya
            for j, col in enumerate(app_columns[1:], start=1):
                val = d.get(col, "")

                # Format khusus untuk kolom KET
                if col == "KET":
                    val = "0"

                # Format khusus untuk kolom LastUpdate
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

                # Tengahkan kolom tertentu
                if col in center_cols:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Nonaktifkan edit
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(i, j, item)

        self.table.blockSignals(False)
        self.lbl_selected.setText("0 selected")
        self.lbl_total.setText(f"{len(self.all_data)} total")
        self.update_statusbar()
        self.update_pagination()
        self.table.horizontalHeader().setSortIndicatorShown(False)

        # jadwalkan auto resize kolom setelah layout selesai
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
# =====================================================
# LOGIN WINDOW (Versi Final: Email, Password, Tahapan)
# =====================================================
class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login Akun")
        self.showMaximized()

        outer_layout = QVBoxLayout()
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        # === Email ===
        self.email_label = QLabel("Email:")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Masukkan Email Aktif...")
        form_layout.addWidget(self.email_label)
        form_layout.addWidget(self.email_input)

        # === Password + tombol lihat ===
        self.pass_label = QLabel("Kata Sandi:")
        pw_layout = QHBoxLayout()
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Masukkan Password...")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_pw = QPushButton("👁")
        self.toggle_pw.setFixedWidth(40)
        self.toggle_pw.clicked.connect(lambda: self.toggle_password(self.pass_input))
        pw_layout.addWidget(self.pass_input)
        pw_layout.addWidget(self.toggle_pw)
        form_layout.addWidget(self.pass_label)
        form_layout.addLayout(pw_layout)

        # === Tahapan ===
        self.tahapan_label = QLabel("Tahapan:")
        self.tahapan_combo = QComboBox()
        self.tahapan_combo.addItems(["-- Pilih Tahapan --", "DPHP", "DPSHP", "DPSHPA"])
        form_layout.addWidget(self.tahapan_label)
        form_layout.addWidget(self.tahapan_combo)

        # === Tombol Login ===
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.check_login)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #ff8533;
            }
        """)
        form_layout.addWidget(self.login_button)

        # === Tombol Buat Akun ===
        self.buat_akun = QPushButton("Buat Akun")
        self.buat_akun.setStyleSheet("""
            color:#ff6600;
            font-weight:bold;
            text-decoration:underline;
            background:transparent;
            border:none;
        """)
        self.buat_akun.clicked.connect(self.konfirmasi_buat_akun)
        form_layout.addWidget(self.buat_akun, alignment=Qt.AlignmentFlag.AlignCenter)

        # === Tata letak utama ===
        center_box = QWidget()
        center_box.setLayout(form_layout)
        center_box.setFixedWidth(300)
        outer_layout.addWidget(center_box, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(outer_layout)

        self.setStyleSheet("""
            QWidget { font-size: 11pt; color: white; background-color: #1e1e1e; }
            QLineEdit, QComboBox {
                min-height: 28px;
                font-size: 11pt;
                border: 1px solid #555;
                border-radius: 4px;
                padding-left: 6px;
                background-color: #2d2d30;
                color: white;
            }
        """)

    # === Toggle tampil/sembunyikan password ===
    def toggle_password(self, field):
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)

    # === Proses login ===
    def check_login(self):
        email = self.email_input.text().strip()
        pw = self.pass_input.text().strip()
        tahapan = self.tahapan_combo.currentText()

        if not email or not pw or tahapan == "-- Pilih Tahapan --":
            QMessageBox.warning(self, "Error", "Semua field harus diisi!")
            return

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT,
                email TEXT,
                kecamatan TEXT,
                desa TEXT,
                password TEXT,
                otp_secret TEXT
            )
        """)
        cur.execute("SELECT nama, kecamatan, desa FROM users WHERE email=? AND password=?", (email, pw))
        row = cur.fetchone()
        conn.close()

        if not row:
            QMessageBox.warning(self, "Login Gagal", "Email atau password salah!")
            return

        nama, kecamatan, desa = row
        self.accept_login(nama, kecamatan, desa, tahapan)

    # === Konfirmasi Buat Akun ===
    def konfirmasi_buat_akun(self):
        reply = QMessageBox.question(
            self,
            "Konfirmasi",
            "Apakah Anda yakin ingin membuat akun baru?\nSeluruh data lama akan dihapus!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        kode, ok = QInputDialog.getText(self, "Kode Konfirmasi", "Masukkan kode konfirmasi:")
        if not ok:
            return
        if kode.strip() != "KabTasik3206":
            QMessageBox.warning(self, "Salah", "Kode konfirmasi salah. Proses dibatalkan.")
            return

        # ✅ Kode benar → hapus semua data lama
        hapus_semua_data()

        # ✅ Tampilkan form RegisterWindow sebagai window utama
        self.register_window = RegisterWindow(None)
        self.register_window.show()

        # Tutup login window setelah register window muncul
        self.close()

    # === Masuk ke MainWindow ===
    def accept_login(self, nama, kecamatan, desa, tahapan):
        tahapan = tahapan.upper()
        db_map = {
            "DPHP": os.path.join(BASE_DIR, "DPHP.db"),
            "DPSHP": os.path.join(BASE_DIR, "DPSHP.db"),
            "DPSHPA": os.path.join(BASE_DIR, "DPSHPA.db")
        }
        db_name = db_map.get(tahapan, os.path.join(BASE_DIR, "DPHP.db"))

        # === Pastikan DB terenkripsi siap ===
        plain_temp = os.path.join(BASE_DIR, f"temp_{os.path.basename(db_name)}")
        enc_file = db_name + ".enc"

        if not os.path.exists(enc_file):
            conn = sqlite3.connect(plain_temp)
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
                    SUMBER TEXT,
                    KET TEXT,
                    TPS TEXT,
                    LastUpdate DATETIME,
                    CEK DATA TEXT
                )
            """)
            conn.commit()
            conn.close()

            try:
                _encrypt_file(plain_temp, enc_file)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Gagal membuat database terenkripsi:\n{e}")
            finally:
                if os.path.exists(plain_temp):
                    os.remove(plain_temp)

        # === Masuk ke MainWindow ===
        self.main_window = MainWindow(nama.upper(), kecamatan, desa, db_name, tahapan)
        self.main_window.show()
        self.close()

# =====================================================
# FORM BUAT AKUN BARU (REGISTER)
# =====================================================
class RegisterWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buat Akun Baru")
        self.setFixedSize(360, 520)
        self.setStyleSheet("""
            QWidget { font-family: Calibri; font-size: 11pt; }
            QLineEdit, QComboBox { 
                min-height: 28px; 
                border-radius: 4px; 
                border: 1px solid #aaa; 
                padding-left: 6px; 
            }
            QPushButton { min-height: 30px; border-radius: 5px; }
            QPushButton:hover { background-color: #f0f0f0; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # === Nama ===
        self.nama = QLineEdit()
        self.nama.setPlaceholderText("Nama Lengkap")
        self.nama.textChanged.connect(lambda t: self.nama.setText(t.upper()) if t != t.upper() else None)
        layout.addWidget(self.nama)

        # === Email ===
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email Aktif")
        layout.addWidget(self.email)

        # === Kecamatan ===
        self.kecamatan = QLineEdit()
        self.kecamatan.setPlaceholderText("Ketik Kecamatan...")
        kec_list = get_kecamatan()
        completer = QCompleter(kec_list, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.kecamatan.setCompleter(completer)
        self.kecamatan.textChanged.connect(self.update_desa)
        layout.addWidget(self.kecamatan)

        # === Desa ===
        self.desa = QComboBox()
        self.desa.addItem("-- Pilih Desa --")
        layout.addWidget(self.desa)

        # === Password + toggle ===
        pw_layout = QHBoxLayout()
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_pw = QPushButton("👁")
        self.toggle_pw.setFixedWidth(40)
        self.toggle_pw.clicked.connect(lambda: self.toggle_password(self.password))
        pw_layout.addWidget(self.password)
        pw_layout.addWidget(self.toggle_pw)
        layout.addLayout(pw_layout)

        # === Ulangi password + toggle ===
        pw2_layout = QHBoxLayout()
        self.password2 = QLineEdit()
        self.password2.setPlaceholderText("Tulis Ulang Password")
        self.password2.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_pw2 = QPushButton("👁")
        self.toggle_pw2.setFixedWidth(40)
        self.toggle_pw2.clicked.connect(lambda: self.toggle_password(self.password2))
        pw2_layout.addWidget(self.password2)
        pw2_layout.addWidget(self.toggle_pw2)
        layout.addLayout(pw2_layout)

        # === Captcha modern (gambar) ===
        self.captcha_code = self.generate_captcha()
        self.captcha_label = QLabel()
        self.captcha_label.setFixedHeight(60)
        self.captcha_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.refresh_captcha_image()

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedWidth(40)
        self.refresh_btn.clicked.connect(self.refresh_captcha_image)

        captcha_layout = QHBoxLayout()
        captcha_layout.addWidget(self.captcha_label)
        captcha_layout.addWidget(self.refresh_btn)
        layout.addLayout(captcha_layout)

        self.captcha_input = QLineEdit()
        self.captcha_input.setPlaceholderText("Tulis ulang captcha di atas")
        layout.addWidget(self.captcha_input)

        # === Tombol Buat Akun ===
        self.btn_buat = QPushButton("Buat Akun")
        self.btn_buat.setStyleSheet("background-color:#ff6600; color:white; font-weight:bold;")
        self.btn_buat.clicked.connect(self.create_account)
        layout.addWidget(self.btn_buat)

    # ===================================================
    # 🔹 Helper untuk captcha dan interaksi UI
    # ===================================================
    def toggle_password(self, field):
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)

    def update_desa(self):
        kecamatan = self.kecamatan.text().strip()
        self.desa.clear()
        if kecamatan:
            desa_list = get_desa(kecamatan)
            self.desa.addItem("-- Pilih Desa --")
            self.desa.addItems(desa_list)
        else:
            self.desa.addItem("-- Pilih Desa --")

    # ===================================================
    # 🔹 Captcha generator
    # ===================================================
    def generate_captcha(self, length=5):
        """Generate random captcha string (A-Z + 0-9)."""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))

    def generate_captcha_image(self, text):
        """Buat gambar captcha berwarna acak dengan noise."""
        width, height = 160, 50
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#f5f5f5"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Calibri", 22, QFont.Weight.Bold)
        painter.setFont(font)

        spacing = width // (len(text) + 1)
        for i, ch in enumerate(text):
            painter.setPen(QColor(random.randint(20, 150), random.randint(20, 150), random.randint(20, 150)))
            angle = random.randint(-25, 25)
            painter.save()
            painter.translate((i + 1) * spacing, random.randint(25, 40))
            painter.rotate(angle)
            painter.drawText(0, 0, ch)
            painter.restore()

        # Tambahkan noise berupa garis acak
        for _ in range(6):
            pen = QColor(random.randint(120, 200), random.randint(120, 200), random.randint(120, 200))
            painter.setPen(pen)
            x1, y1, x2, y2 = [random.randint(0, width) for _ in range(4)]
            painter.drawLine(x1, y1, x2, y2)

        painter.end()
        return pixmap

    def refresh_captcha_image(self):
        """Refresh captcha dengan gambar baru."""
        self.captcha_code = self.generate_captcha()
        pixmap = self.generate_captcha_image(self.captcha_code)
        self.captcha_label.setPixmap(pixmap)

    # ===================================================
    # 🔹 Validasi dan Simpan Akun
    # ===================================================
    def create_account(self):
        nama = self.nama.text().strip()
        email = self.email.text().strip()
        kecamatan = self.kecamatan.text().strip()
        desa = self.desa.currentText().strip()
        pw = self.password.text().strip()
        pw2 = self.password2.text().strip()
        captcha = self.captcha_input.text().strip()

        if not all([nama, email, kecamatan, desa, pw, pw2, captcha]):
            QMessageBox.warning(self, "Error", "Semua kolom harus diisi!")
            return

        if "@" not in email or "." not in email:
            QMessageBox.warning(self, "Error", "Format email tidak valid!")
            return

        if pw != pw2:
            QMessageBox.warning(self, "Error", "Password tidak sama!")
            return

        import re
        if len(pw) < 8 or not re.search(r"[A-Z]", pw) or not re.search(r"[0-9]", pw) or not re.search(r"[^A-Za-z0-9]", pw):
            QMessageBox.warning(
                self,
                "Error",
                "Password harus minimal 8 karakter dan memuat minimal:\n"
                "- 1 huruf kapital\n- 1 angka\n- 1 karakter khusus (!@#$%^&*)"
            )
            return

        if captcha != self.captcha_code:
            QMessageBox.warning(self, "Error", "Captcha salah! Coba lagi.")
            self.refresh_captcha_image()
            return

        # Simpan akun baru ke DB
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT,
                email TEXT,
                kecamatan TEXT,
                desa TEXT,
                password TEXT,
                otp_secret TEXT
            )
        """)
        cur.execute("DELETE FROM users")  # hanya 1 akun aktif
        cur.execute("INSERT INTO users (nama, email, kecamatan, desa, password, otp_secret) VALUES (?, ?, ?, ?, ?, ?)",
                    (nama, email, kecamatan, desa, pw, None))
        conn.commit()
        conn.close()

        dlg = ModernMessage("Sukses", "Akun berhasil dibuat!\nSilakan login kembali.")
        dlg.exec()
        self.close()
        self.login_window = LoginWindow()
        self.login_window.show()

# =====================================================
# Fungsi Hapus Semua Data Akun & Database
# =====================================================
def hapus_semua_data():
    db_files = ["DPHP.db", "DPSHP.db", "DPSHPA.db"]
    for dbfile in db_files:
        plain_tmp = os.path.join(BASE_DIR, f"temp_{dbfile}")
        enc_path  = os.path.join(BASE_DIR, dbfile + ".enc")

        # Jika ada file terenkripsi, buka, kosongkan, lalu enkripsi ulang
        if os.path.exists(enc_path):
            try:
                _decrypt_file(enc_path, plain_tmp)
                conn = sqlite3.connect(plain_tmp)
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS data_pemilih (
                        KECAMATAN TEXT, DESA TEXT, DPID TEXT, NKK TEXT, NIK TEXT, NAMA TEXT,
                        JK TEXT, TMPT_LHR TEXT, TGL_LHR TEXT, STS TEXT, ALAMAT TEXT,
                        RT TEXT, RW TEXT, DIS TEXT, KTPel TEXT, SUMBER TEXT, KET TEXT,
                        TPS TEXT, LastUpdate DATETIME, "CEK DATA" TEXT
                    )
                """)
                cur.execute("DELETE FROM data_pemilih")
                conn.commit()
                conn.close()

                _encrypt_file(plain_tmp, enc_path)
            finally:
                if os.path.exists(plain_tmp):
                    os.remove(plain_tmp)
        else:
            # Jika belum ada .enc, siapkan kosong dari awal
            conn = sqlite3.connect(plain_tmp)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS data_pemilih (
                    KECAMATAN TEXT, DESA TEXT, DPID TEXT, NKK TEXT, NIK TEXT, NAMA TEXT,
                    JK TEXT, TMPT_LHR TEXT, TGL_LHR TEXT, STS TEXT, ALAMAT TEXT,
                    RT TEXT, RW TEXT, DIS TEXT, KTPel TEXT, SUMBER TEXT, KET TEXT,
                    TPS TEXT, LastUpdate DATETIME, "CEK DATA" TEXT
                )
            """)
            conn.commit()
            conn.close()
            _encrypt_file(plain_tmp, enc_path)
            os.remove(plain_tmp)

    # Hapus user lama
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    conn.close()

# =====================================================
# Main
# =====================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    login = LoginWindow()
    login.show()
    sys.exit(app.exec())
