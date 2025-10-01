import sys, sqlite3
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QMessageBox, QMainWindow, QTableWidget, QTableWidgetItem,
    QToolBar, QStatusBar, QListView, QCompleter, QSizePolicy, QHeaderView
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

DB_NAME = "app.db"

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
# Main Window (Setelah login)
# =====================================================
class MainWindow(QMainWindow):
    def __init__(self, username):
        super().__init__()
        self.setWindowTitle("Sidalih Pilkada 2024 Desktop v2.2.29 - Pemutakhiran Data")
        self.resize(900, 550)

        # ===== Table =====
        self.table = QTableWidget()
        columns = [
            "KECAMATAN","DESA","DPID","NKK","NIK","NAMA","JK","TMPT_LHR","TGL_LHR",
            "STS","ALAMAT","RT","RW","DIS","KTPel","SUMBER","KET","TPS","LastUpdate"
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setAlternatingRowColors(True)

        # Style tabel
        self.table.setStyleSheet("""
            QTableWidget {
                font-family: Calibri;
                font-size: 12px;
            }
            QHeaderView::section {
                font-family: Calibri;
                font-size: 12px;
                font-weight: bold;
            }
        """)

        # Tinggi baris & header
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setFixedHeight(24)

        # ==== Dictionary lebar kolom ====
        col_widths = {
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
            "LastUpdate": 100
        }

        # Terapkan lebar kolom dari dictionary
        for idx, col in enumerate(columns):
            if col in col_widths:
                self.table.setColumnWidth(idx, col_widths[col])

        # Aktifkan word wrap
        self.table.setWordWrap(True)
        self.table.resizeRowsToContents()

        self.setCentralWidget(self.table)

        # ===== Menu Bar =====
        menubar = self.menuBar()
        menubar.setStyleSheet("font-family: Calibri; font-size: 12px;")
        file_menu = menubar.addMenu("File")

        # Submenu Dashboard
        action_dashboard = QAction("Dashboard", self)
        action_dashboard.setShortcut("Alt+H")
        file_menu.addAction(action_dashboard)

        # Submenu Pemutakhiran Data
        action_pemutakhiran = QAction("Pemutakhiran Data", self)
        action_pemutakhiran.setShortcut("Alt+C")
        file_menu.addAction(action_pemutakhiran)

        # Submenu Unggah Webgrid TPS Reguler
        action_unggah_reguler = QAction("Unggah Webgrid TPS Reguler", self)
        action_unggah_reguler.setShortcut("Alt+I")
        file_menu.addAction(action_unggah_reguler)

        # Submenu Rekapitulasi
        action_rekap = QAction("Rekapitulasi", self)
        action_rekap.setShortcut("Alt+R")
        file_menu.addAction(action_rekap)

        # Submenu Import Data
        action_import = QAction("Import Data", self)
        action_import.setShortcut("Alt+M")
        file_menu.addAction(action_import)

        # Separator
        file_menu.addSeparator()

        # Submenu Keluar
        action_keluar = QAction("Keluar", self)
        action_keluar.setShortcut("Ctrl+W")
        action_keluar.triggered.connect(self.close)
        file_menu.addAction(action_keluar)

        generate_menu = menubar.addMenu("Generate")

        view_menu = menubar.addMenu("View")
        action_reload = QAction("Reload", self)
        action_reload.setShortcut("Ctrl+R")
        view_menu.addAction(action_reload)
        action_force_reload = QAction("Force Reload", self)
        action_force_reload.setShortcut("Ctrl+Shift+R")
        view_menu.addAction(action_force_reload)
        action_actual_size = QAction("Actual Size", self)
        action_actual_size.setShortcut("Ctrl+0")
        view_menu.addAction(action_actual_size)
        action_zoom_in = QAction("Zoom In", self)
        action_zoom_in.setShortcut("Ctrl+Shift+=")
        view_menu.addAction(action_zoom_in)
        action_zoom_out = QAction("Zoom Out", self)
        action_zoom_out.setShortcut("Ctrl+-")
        view_menu.addAction(action_zoom_out)
        view_menu.addSeparator()
        action_fullscreen = QAction("Toggle Full Screen", self)
        action_fullscreen.setShortcut("F11")
        view_menu.addAction(action_fullscreen)

        help_menu = menubar.addMenu("Help")
        action_shortcut = QAction("Shortcut", self)
        action_shortcut.setShortcut("Alt+Z")
        help_menu.addAction(action_shortcut)
        action_setting = QAction("Setting Aplikasi", self)
        action_setting.setShortcut("Alt+T")
        help_menu.addAction(action_setting)
        action_hapus = QAction("Hapus Data Pemilih", self)
        help_menu.addAction(action_hapus)
        action_backup = QAction("Backup", self)
        help_menu.addAction(action_backup)
        action_restore = QAction("Restore", self)
        help_menu.addAction(action_restore)
        action_cekdpt = QAction("cekdptonline.kpu.go.id", self)
        help_menu.addAction(action_cekdpt)

        # ===== Toolbar =====
        toolbar = QToolBar("Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Tombol kiri
        btn_baru = QPushButton("Baru")
        btn_baru.setStyleSheet("""
            font-family: Calibri;
            font-size: 12px;
            text-align: center;
            qproperty-alignment: AlignCenter;
            background-color: green;
            color: white;             /* biar teks terlihat jelas */
        """)
        toolbar.addWidget(btn_baru)

        btn_rekap = QPushButton("Rekap")
        btn_rekap.setStyleSheet("font-family: Calibri; font-size: 12px;")
        toolbar.addWidget(btn_rekap)

        # Spacer kiri
        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_left)

        # Label user di tengah toolbar
        self.user_label = QLabel(username)
        self.user_label.setStyleSheet("font-family: Calibri; font-weight: bold; font-size: 14px;")
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.user_label)

        # Spacer kanan
        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_right)

        # Tombol kanan
        btn_tools = QPushButton("Tools")
        btn_tools.setStyleSheet("font-family: Calibri; font-size: 12px;")
        toolbar.addWidget(btn_tools)

        btn_filter = QPushButton("Filter")
        btn_filter.setStyleSheet("""
            font-family: Calibri;
            font-size: 12px;
            background-color: orange;
            font-weight: bold;
        """)
        toolbar.addWidget(btn_filter)

        # Status bar
        self.setStatusBar(QStatusBar())


# =====================================================
# Login Window (seperti semula)
# =====================================================
class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.showMaximized()  # fullscreen

        outer_layout = QVBoxLayout()
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        # Username
        self.user_label = QLabel("Nama Pengguna:")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ketik Username...")
        form_layout.addWidget(self.user_label)
        form_layout.addWidget(self.user_input)

        # Kapital otomatis
        self.user_input.textChanged.connect(
            lambda text: self.user_input.setText(text.upper()) if text != text.upper() else None
        )

        # Kecamatan
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

        # Kapital otomatis
        self.kec_input.textChanged.connect(
            lambda text: self.kec_input.setText(text.upper()) if text != text.upper() else None
        )

        form_layout.addWidget(self.kec_input)

        # Update desa saat selesai pilih/ketik
        self.kec_input.editingFinished.connect(self.update_desa)
        completer.activated.connect(self.update_desa)

        # Desa
        self.desa_label = QLabel("Desa:")
        self.desa_combo = QComboBox()
        self.desa_combo.setView(QListView())
        self.desa_combo.addItem("-- Pilih Desa --")
        form_layout.addWidget(self.desa_label)
        form_layout.addWidget(self.desa_combo)

        # Tombol login
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.check_login)
        form_layout.addWidget(self.login_button)

        # Bungkus form
        center_box = QWidget()
        center_box.setLayout(form_layout)
        center_box.setFixedWidth(300)
        outer_layout.addWidget(center_box, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(outer_layout)

        # Style global
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

        if not user or not kecamatan or desa == "-- Pilih Desa --":
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

        self.accept_login(user)

    def accept_login(self, user):
        self.main_window = MainWindow(user.upper())
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
