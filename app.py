import sys, sqlite3
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QMessageBox, QMainWindow, QTableWidget,
    QTableWidgetItem, QToolBar, QStatusBar, QListView, QCompleter
)
from PyQt6.QtCore import Qt

DB_NAME = "app.db"

def get_kecamatan():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aplikasi CRUD Data")
        self.resize(800, 600)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Nama", "Keterangan"])
        self.setCentralWidget(self.table)

        toolbar = QToolBar("Toolbar")
        self.addToolBar(toolbar)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.load_data)
        toolbar.addWidget(btn_refresh)

        btn_add = QPushButton("Tambah")
        btn_add.clicked.connect(self.add_data)
        toolbar.addWidget(btn_add)

        btn_delete = QPushButton("Hapus")
        btn_delete.clicked.connect(self.delete_data)
        toolbar.addWidget(btn_delete)

        self.setStatusBar(QStatusBar())
        self.load_data()

    def load_data(self):
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS data (id INTEGER PRIMARY KEY, nama TEXT, ket TEXT)")
        cur.execute("SELECT * FROM data")
        rows = cur.fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))

    def add_data(self):
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO data (nama, ket) VALUES (?, ?)", ("Contoh", "Keterangan"))
        conn.commit()
        conn.close()
        self.load_data()

    def delete_data(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Hapus", "Pilih baris yang ingin dihapus!")
            return
        id_val = self.table.item(row, 0).text()
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("DELETE FROM data WHERE id = ?", (id_val,))
        conn.commit()
        conn.close()
        self.load_data()

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

        # Update desa saat selesai mengetik / pilih dari completer
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

            # Hilangkan title bar asli
            msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

            # Judul manual di dalam teks
            title = "<div style='font-weight:bold; font-size:10pt; margin-bottom:1px;'>""</div>"
            text = "Semua field harus diisi!"
            msg.setText(title + text)

            # Style sheet custom
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: white;
                    border: 2px solid black;
                    border-radius: 6px;
                }
                QMessageBox QLabel {
                    color: black;
                    qproperty-alignment: AlignLeft;  /* teks rata kiri */
                    font-size: 10pt;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                    min-height: 25px;
                }
            """)

            msg.exec()
            return

        self.accept_login()

    def accept_login(self):
        self.main_window = MainWindow()
        self.main_window.show()
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    login = LoginWindow()
    login.show()
    sys.exit(app.exec())
