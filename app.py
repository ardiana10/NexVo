import sys, sqlite3, csv
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QMessageBox, QMainWindow, QTableWidget, QTableWidgetItem,
    QToolBar, QStatusBar, QListView, QCompleter, QSizePolicy, QHeaderView,
    QFileDialog, QProgressDialog, QHBoxLayout
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
    def __init__(self, username, kecamatan, desa):
        super().__init__()
        self.setWindowTitle("Sidalih Pilkada 2024 Desktop v2.2.29 - Pemutakhiran Data")
        self.resize(900, 550)

        self.kecamatan_login = kecamatan.upper()
        self.desa_login = desa.upper()
        self.all_data = []      # semua data hasil import CSV
        self.current_page = 1   # halaman aktif
        self.rows_per_page = 100
        self.total_pages = 1

        # ===== Table =====
        self.table = QTableWidget()
        columns = [
            " ","KECAMATAN","DESA","DPID","NKK","NIK","NAMA","JK","TMPT_LHR","TGL_LHR",
            "STS","ALAMAT","RT","RW","DIS","KTPel","SUMBER","KET","TPS","LastUpdate"
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        # Style tabel dengan border putih tipis
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

        # Tinggi baris & header
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setFixedHeight(24)

        # ==== Dictionary lebar kolom ====
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
            "LastUpdate": 100
        }
        for idx, col in enumerate(columns):
            if col in col_widths:
                self.table.setColumnWidth(idx, col_widths[col])

        # === Central widget (table + pagination di bawah) ===
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

        # connect itemChanged untuk hitung selected realtime + highlight
        self.table.itemChanged.connect(self.on_item_changed)

        # ===== Menu Bar =====
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                font-family: Calibri;
                font-size: 12px;
                padding: 0px;
                margin-bottom: -6px;   /* geser garis ke atas */
            }
            QMenuBar::item {
                padding: 2px 8px;      /* jarak kiri-kanan biar proporsional */
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

        # Import CSV
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
        help_menu.addAction(QAction("Setting Aplikasi", self, shortcut="Alt+T"))
        help_menu.addAction(QAction("Hapus Data Pemilih", self))
        help_menu.addAction(QAction("Backup", self))
        help_menu.addAction(QAction("Restore", self))
        help_menu.addAction(QAction("cekdptonline.kpu.go.id", self))

        # ===== Toolbar =====
        toolbar = QToolBar("Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        btn_baru = QPushButton("Baru")
        btn_baru.setStyleSheet("""
            font-family: Calibri;
            font-size: 13px;
            text-align: center;
            qproperty-alignment: AlignCenter;
            background-color: green;
            color: white;
        """)
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
        btn_filter.setStyleSheet("""
            font-family: Calibri;
            font-size: 13px;
            background-color: orange;
            font-weight: bold;
        """)
        toolbar.addWidget(btn_filter)
        for btn in [btn_baru, btn_rekap, btn_tools, btn_filter]:
            btn.setFixedHeight(30)   # sesuaikan tinggi, misalnya 28–32px


        # ===== Status Bar =====
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_selected = QLabel("0 selected")
        self.lbl_total = QLabel("0 total")
        self.lbl_version = QLabel("NexVo v1.0")
        self.status.addWidget(self.lbl_selected)
        self.status.addWidget(self.lbl_total)
        self.status.addPermanentWidget(self.lbl_version)

        # Pertama kali: render pagination kosong
        self.update_pagination()

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
            # highlight baris on/off
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
        self.table.blockSignals(True)  # hindari itemChanged saat setup
        self.table.setRowCount(0)

        start = (page - 1) * self.rows_per_page
        end = start + self.rows_per_page
        data_rows = self.all_data[start:end]

        self.table.setRowCount(len(data_rows))
        app_columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        center_cols = {"DPID","JK","STS","TGL_LHR","RT","RW","DIS","KTPel","KET","TPS"}

        for i, d in enumerate(data_rows):
            # checkbox centered
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, chk)

            # isi kolom lain
            for j, col in enumerate(app_columns[1:], start=1):
                val = d.get(col, "")
                if col == "KET":
                    val = "0"   # paksa jadi 0
                item = QTableWidgetItem(val)
                if col in center_cols:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # buat readonly
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, j, item)
        self.table.blockSignals(False)
        self.update_statusbar()
        self.update_pagination()

    # =================================================
    # Pagination UI (sliding window seperti contoh)
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
                border: 1px solid #ffa047;
                font-weight: reguler;
            }
        """)
        return btn

    def update_pagination(self):
        # bersihkan tombol lama
        for i in reversed(range(self.pagination_layout.count())):
            w = self.pagination_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        # jika belum ada data, tampilkan kosong
        if self.total_pages <= 1:
            # tetap render tombol 1 disabled agar container terlihat rapi
            self.pagination_layout.addWidget(self.make_page_button("1", lambda: None, checked=True, enabled=False))
            return

        # Tombol Prev
        prev_btn = self.make_page_button("<", lambda: self.show_page(self.current_page - 1),
                                         checked=False, enabled=(self.current_page > 1))
        self.pagination_layout.addWidget(prev_btn)

        # Window nomor (maks 5 angka)
        window = 5
        half = window // 2
        start = max(1, self.current_page - half)
        end = min(self.total_pages, start + window - 1)
        # adjust jika di ujung kanan
        start = max(1, end - window + 1)

        # Halaman pertama + ellipsis jika perlu
        if start > 1:
            self.pagination_layout.addWidget(self.make_page_button("1", lambda: self.show_page(1)))
            if start > 2:
                self.pagination_layout.addWidget(QLabel("..."))

        # Nomor halaman dalam window
        for p in range(start, end + 1):
            self.pagination_layout.addWidget(
                self.make_page_button(str(p), lambda _, x=p: self.show_page(x),
                                      checked=(p == self.current_page))
            )

        # Ellipsis + halaman terakhir jika perlu
        if end < self.total_pages:
            if end < self.total_pages - 1:
                self.pagination_layout.addWidget(QLabel("..."))
            self.pagination_layout.addWidget(
                self.make_page_button(str(self.total_pages), lambda: self.show_page(self.total_pages))
            )

        # Tombol Next
        next_btn = self.make_page_button(">", lambda: self.show_page(self.current_page + 1),
                                         checked=False, enabled=(self.current_page < self.total_pages))
        self.pagination_layout.addWidget(next_btn)

    # =================================================
    # Import CSV Function
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

                # Verifikasi baris-15 kolom-2 & kolom-4 (index 14, [1] & [3])
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
                    "TEMPAT LAHIR": "TMPT_LHR",
                    "TANGGAL LAHIR": "TGL_LHR",
                    "STS KAWIN": "STS",
                    "KELAMIN": "JK",
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
                # refresh all_data
                self.all_data = []
                for row in reader[1:]:
                    status_val = row[idx_status].strip().upper()
                    if status_val not in ("AKTIF", "UBAH", "BARU"):
                        continue
                    data_dict = {}
                    for csv_col, app_col in mapping.items():
                        if csv_col in header:
                            col_idx = header.index(csv_col)
                            data_dict[app_col] = row[col_idx].strip()
                    data_dict["KET"] = "0"  # paksa isi 0
                    self.all_data.append(data_dict)

                # hitung total pages & tampilkan halaman 1
                self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
                self.show_page(1)
                QMessageBox.information(self, "Sukses", "Import CSV selesai!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal import CSV: {e}")


# =====================================================
# Login Window (seperti semula)
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

        self.user_label = QLabel("Nama Pengguna:")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ketik Username...")
        form_layout.addWidget(self.user_label)
        form_layout.addWidget(self.user_input)

        self.user_input.textChanged.connect(
            lambda text: self.user_input.setText(text.upper()) if text != text.upper() else None
        )

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

        self.desa_label = QLabel("Desa:")
        self.desa_combo = QComboBox()
        self.desa_combo.setView(QListView())
        self.desa_combo.addItem("-- Pilih Desa --")
        form_layout.addWidget(self.desa_label)
        form_layout.addWidget(self.desa_combo)

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

        self.accept_login(user, kecamatan, desa)

    def accept_login(self, user, kecamatan, desa):
        self.main_window = MainWindow(user.upper(), kecamatan, desa)
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