import sys, sqlite3, csv, os, atexit, base64, random, string, pyotp, qrcode # type: ignore
from datetime import datetime, date, timedelta
import calendar
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QMessageBox, QMainWindow, QTableWidget, QTableWidgetItem,
    QToolBar, QStatusBar, QCompleter, QSizePolicy,
    QFileDialog, QHBoxLayout, QDialog, QCheckBox, QScrollArea, QHeaderView,
    QStyledItemDelegate, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QFrame, QMenu, QTableWidgetSelectionRange,
    QFormLayout, QSlider, QRadioButton, QDockWidget, QGridLayout, QStyle, QStyleOptionButton
)
from PyQt6.QtGui import QAction, QPainter, QColor, QPen, QPixmap, QFont, QIcon
from PyQt6.QtCore import Qt, QTimer, QRect, QPropertyAnimation
from io import BytesIO

# ===================================================
# 🚀 MEMUAT VARIABEL LINGKUNGAN DARI FILE .env
# ===================================================
from dotenv import load_dotenv # 👈 Tambahkan import ini
load_dotenv()
# ===================================================


def show_modern_warning(parent, title, text):
    """Tampilkan pesan peringatan (kuning)."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    _apply_modern_style(msg, accent="#ffc107")  # kuning lembut
    msg.exec()


def show_modern_info(parent, title, text):
    """Tampilkan pesan informasi (biru)."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    _apply_modern_style(msg, accent="#17a2b8")  # biru toska
    msg.exec()


def show_modern_error(parent, title, text):
    """Tampilkan pesan error (merah)."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    _apply_modern_style(msg, accent="#dc3545")  # merah elegan
    msg.exec()


def show_modern_question(parent, title, text):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.No)

    msg.setStyleSheet("""
        QMessageBox {
            background-color: #2b2b2b;
            color: white;
            font-family: 'Segoe UI';
            font-size: 11pt;
            border-radius: 12px;
        }
        QLabel {
            background: transparent;     /* ✅ Hilangkan background hitam */
            color: white;
            font-size: 11pt;
            padding: 4px 2px;
        }
        QPushButton {
            background-color: #cc6a00;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: bold;
            font-size: 10.5pt;
            min-width: 120px;
        }
        QPushButton:hover {
            background-color: #ff8c1a;
        }
    """)

    msg.button(QMessageBox.StandardButton.Yes).setText("Ya")
    msg.button(QMessageBox.StandardButton.No).setText("Tidak")

    result = msg.exec()
    return result == QMessageBox.StandardButton.Yes

# ===================================================
# 🎨 Gaya Universal Modern QMessageBox
# ===================================================
def _apply_modern_style(msg, accent="#ff6600"):
    lighter = _lighten_color(accent)
    msg.setStyleSheet(f"""
        QMessageBox {{
            background-color: #2b2b2b;
            color: white;
            font-family: 'Segoe UI';
            font-size: 11pt;
            border-radius: 12px;
            border: 1px solid #444;
        }}
        QLabel {{
            background: transparent;     /* ✅ Hilangkan background hitam */
            color: white;
            font-size: 11pt;
            margin: 6px;
        }}
        QPushButton {{
            background-color: {accent};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: bold;
            font-size: 10.5pt;
            min-width: 120px;
        }}
        QPushButton:hover {{
            background-color: {lighter};
        }}
    """)


def _lighten_color(hex_color):
    """Buat warna tombol lebih terang (untuk efek hover)."""
    color = QColor(hex_color)
    h, s, v, a = color.getHsv()
    v = min(255, int(v * 1.25))
    lighter = QColor.fromHsv(h, s, v, a)
    return lighter.name()

class ModernMessage(QDialog):
    def __init__(self, title, message, icon_type="info", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(340, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                border-radius: 12px;
                border: 1px solid #444;
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
                padding: 6px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff8533;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

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
        msg.setStyleSheet("font-size: 11pt; margin: 6px;")
        layout.addWidget(msg)

        # === Tombol OK ===
        btn = QPushButton("OK")
        btn.setFixedWidth(100)  # 🔹 Tambah lebar
        btn.setFixedHeight(36)  # 🔹 Tinggi lebih proporsional
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 10.5pt;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #ff8533;
            }
        """)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # === Efek Fade-In ===
        opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacity_effect)
        self.fade_anim = QPropertyAnimation(opacity_effect, b"opacity")
        self.fade_anim.setDuration(350)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        self.fade_anim.start()

        # === Posisikan di tengah layar ===
        QTimer.singleShot(0, self.center_on_screen)

    def center_on_screen(self):
        """Tampilkan dialog tepat di tengah layar utama."""
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center() - self.rect().center()
        )

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

        # Gambar simbol di tengah
        painter.setPen(QPen(QColor("white"), 5))
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
    
class ModernInputDialog(QDialog):
    def __init__(self, title, prompt, parent=None, is_password=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(360, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                border-radius: 12px;
                border: 1px solid #444;
            }
            QLabel {
                color: white;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            QLineEdit {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #666;
                border-radius: 6px;
                padding: 6px;
                font-size: 11pt;
            }
            QPushButton {
                background-color: #ff6600;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff8533;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(30, 20, 30, 20)

        # === Pesan ===
        label = QLabel(prompt)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # === Input Field ===
        self.line_edit = QLineEdit()
        if is_password:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.line_edit)

        # === Tombol OK dan Cancel ===
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Batal")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        # === Event handler ===
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        # === Efek fade in ===
        opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacity_effect)
        self.fade_anim = QPropertyAnimation(opacity_effect, b"opacity")
        self.fade_anim.setDuration(350)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        self.fade_anim.start()

        QTimer.singleShot(0, self.center_on_screen)

    def center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center() - self.rect().center())

    def getText(self):
        """Kembalikan teks input jika OK ditekan."""
        if self.exec() == QDialog.DialogCode.Accepted:
            return self.line_edit.text(), True
        return "", False


# =====================================================
# Date Range Picker Dialog for LastUpdate Filter
# =====================================================
class DateRangePickerDialog(QDialog):
    """Dialog untuk memilih rentang tanggal dengan dua kalender berdampingan dan preset di kiri.

    Format keluaran: (date_awal, date_akhir)
    """
    def __init__(self, parent=None, start_date: date | None = None, end_date: date | None = None):
        super().__init__(parent)
        self.setWindowTitle("Pilih Rentang Tanggal")
        self.setModal(True)
        self.setFixedSize(720, 360)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.start_date: date | None = start_date
        self.end_date: date | None = end_date

        self.setStyleSheet("""
            QDialog { background:#2b2b2b; border:1px solid #444; border-radius:10px; }
            QLabel { color:#fff; font-family:'Segoe UI'; }
            QPushButton { background:#444; color:#fff; border:none; border-radius:6px; padding:6px 12px; }
            QPushButton:hover { background:#555; }
            QPushButton.primary { background:#ff7700; font-weight:bold; }
            QPushButton.primary:hover { background:#ff8c1a; }
        """)

        main = QHBoxLayout(self)
        main.setContentsMargins(14,14,14,14)
        main.setSpacing(14)

        # === Preset panel ===
        preset_panel = QVBoxLayout()
        preset_panel.setSpacing(8)
        lbl_preset = QLabel("Preset")
        lbl_preset.setStyleSheet("font-weight:bold;")
        preset_panel.addWidget(lbl_preset)

        def add_preset(name, func):
            btn = QPushButton(name)
            btn.clicked.connect(lambda: self.apply_preset(func))
            preset_panel.addWidget(btn)
        today = date.today()
        add_preset("Hari ini", lambda: (today, today))
        add_preset("Kemarin", lambda: (today - timedelta(days=1), today - timedelta(days=1)))
        first_day_month = today.replace(day=1)
        last_day_month = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        add_preset("Bulan ini", lambda: (first_day_month, last_day_month))
        # Bulan lalu
        prev_year, prev_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        first_prev = date(prev_year, prev_month, 1)
        last_prev = date(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])
        add_preset("Bulan lalu", lambda: (first_prev, last_prev))
        preset_panel.addStretch(1)
        main.addLayout(preset_panel)

        # === Dua kalender ===
        cal_container = QHBoxLayout()
        cal_container.setSpacing(12)
        from PyQt6.QtWidgets import QCalendarWidget  # local import agar jelas
        self.cal_left = QCalendarWidget()
        self.cal_right = QCalendarWidget()
        # Sinkronisasi agar right selalu month+1 (kecuali Desember -> Januari tahun berikutnya)
        self.cal_left.currentPageChanged.connect(self.sync_right_calendar)
        for cal in (self.cal_left, self.cal_right):
            cal.setGridVisible(True)
            cal.clicked.connect(self.on_date_clicked)
            cal.setVerticalHeaderFormat(cal.VerticalHeaderFormat.NoVerticalHeader)
            cal.setStyleSheet("""
                QCalendarWidget QWidget { alternate-background-color:#333; }
                QCalendarWidget QAbstractItemView:enabled { color:#eee; selection-background-color:#ff7700; selection-color:#fff; }
            """)
        # Set posisi awal
        if self.start_date:
            self.cal_left.setSelectedDate(self.start_date)
        if self.end_date:
            self.cal_right.setSelectedDate(self.end_date)
        cal_container.addWidget(self.cal_left)
        cal_container.addWidget(self.cal_right)
        main.addLayout(cal_container, 1)

        # === Panel kanan (info + aksi) ===
        side = QVBoxLayout()
        self.lbl_range = QLabel("Pilih tanggal mulai dan tanggal akhir")
        self.lbl_range.setWordWrap(True)
        side.addWidget(self.lbl_range)
        side.addStretch(1)
        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Batal")
        self.btn_ok = QPushButton("Pilih")
        self.btn_ok.setObjectName("pilihBtn")
        self.btn_ok.setProperty("class","primary")
        self.btn_ok.setStyleSheet("QPushButton { background:#ff7700; } QPushButton:hover { background:#ff8c1a; }")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept_if_valid)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)
        side.addLayout(btn_row)
        main.addLayout(side)

        # Sync right calendar now
        self.sync_right_calendar(self.cal_left.yearShown(), self.cal_left.monthShown())
        self.refresh_highlight()

    def apply_preset(self, fn):
        self.start_date, self.end_date = fn()
        self.refresh_highlight()
        self.update_range_label()

    def sync_right_calendar(self, year, month):
        # Set calendar right ke bulan berikutnya
        if month == 12:
            next_month = 1; next_year = year + 1
        else:
            next_month = month + 1; next_year = year
        self.cal_right.blockSignals(True)
        self.cal_right.setCurrentPage(next_year, next_month)
        self.cal_right.blockSignals(False)

    def on_date_clicked(self, qdate):
        d = date(qdate.year(), qdate.month(), qdate.day())
        if self.start_date is None or (self.start_date and self.end_date):
            # Mulai baru
            self.start_date = d
            self.end_date = None
        else:
            # Set end
            if d < self.start_date:
                self.start_date, self.end_date = d, self.start_date
            else:
                self.end_date = d
        self.refresh_highlight()
        self.update_range_label()

    def refresh_highlight(self):
        from PyQt6.QtGui import QTextCharFormat
        from PyQt6.QtCore import QDate
        fmt_range = QTextCharFormat(); fmt_range.setBackground(QColor("#ff7700")); fmt_range.setForeground(QColor("white"))
        fmt_start_end = QTextCharFormat(); fmt_start_end.setBackground(QColor("#cc5600")); fmt_start_end.setForeground(QColor("white"))
        fmt_clear = QTextCharFormat()
        # Clear semua (cukup untuk visible pages)
        for cal in (self.cal_left, self.cal_right):
            year = cal.yearShown(); month = cal.monthShown()
            days_in_month = calendar.monthrange(year, month)[1]
            for day in range(1, days_in_month+1):
                cal.setDateTextFormat(QDate(year, month, day), fmt_clear)
        if self.start_date:
            if self.end_date:
                cur = self.start_date
                while cur <= self.end_date:
                    qd = QDate(cur.year, cur.month, cur.day)
                    # Start / End beda warna
                    if cur == self.start_date or cur == self.end_date:
                        self.cal_left.setDateTextFormat(qd, fmt_start_end)
                        self.cal_right.setDateTextFormat(qd, fmt_start_end)
                    else:
                        self.cal_left.setDateTextFormat(qd, fmt_range)
                        self.cal_right.setDateTextFormat(qd, fmt_range)
                    cur += timedelta(days=1)
            else:
                qd = QDate(self.start_date.year, self.start_date.month, self.start_date.day)
                self.cal_left.setDateTextFormat(qd, fmt_start_end)
                self.cal_right.setDateTextFormat(qd, fmt_start_end)

    def update_range_label(self):
        if self.start_date and self.end_date:
            self.lbl_range.setText(f"Dipilih: {self.start_date.strftime('%d/%m/%Y')} - {self.end_date.strftime('%d/%m/%Y')}")
        elif self.start_date:
            self.lbl_range.setText(f"Tanggal mulai: {self.start_date.strftime('%d/%m/%Y')} (pilih akhir)")
        else:
            self.lbl_range.setText("Pilih tanggal mulai dan tanggal akhir")

    def accept_if_valid(self):
        if self.start_date and self.end_date:
            self.accept()
        else:
            show_modern_warning(self, "Rentang belum lengkap", "Silakan pilih tanggal mulai dan tanggal akhir.")

    def get_range(self):
        return self.start_date, self.end_date


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
# Custom Checkbox untuk Filter Sidebar
# =====================================================
class CustomCheckBox(QCheckBox):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.theme = "dark"
        
        # Set smaller size and better margins
        self.setMinimumHeight(18)
        self.setMaximumHeight(22)
        self.setContentsMargins(0, 0, 0, 0)
        
        # Override mouse press area to be more precise
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
    def setTheme(self, theme):
        self.theme = theme
        self.update()
        
    def paintEvent(self, event):
        # Custom paint untuk checkbox dengan checkmark yang sama seperti tabel
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get checkbox rect - make it smaller
        option = QStyleOptionButton()
        self.initStyleOption(option)
        style = self.style()
        
        # Calculate smaller checkbox size and position
        checkbox_size = 12  # Reduced from default 14
        checkbox_rect = QRect(2, (self.height() - checkbox_size) // 2, checkbox_size, checkbox_size)
        
        # Draw checkbox background and border
        if self.isChecked():
            # Orange background when checked
            painter.setBrush(QColor("#ff9900"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(checkbox_rect, 3, 3)
            
            # White checkmark - adjusted for smaller size
            painter.setPen(QPen(QColor("white"), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(checkbox_rect.left() + 3, checkbox_rect.center().y(),
                             checkbox_rect.center().x(), checkbox_rect.bottom() - 3)
            painter.drawLine(checkbox_rect.center().x(), checkbox_rect.bottom() - 3,
                             checkbox_rect.right() - 3, checkbox_rect.top() + 3)
        else:
            # Unchecked state
            if self.theme == "dark":
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("white"), 1))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#888"), 1))
            painter.drawRoundedRect(checkbox_rect, 3, 3)
        
        # Draw text with smaller font and better spacing
        text_rect = QRect(checkbox_rect.right() + 6, 0, self.width() - checkbox_rect.right() - 8, self.height())
        painter.setPen(QColor("#d4d4d4") if self.theme == "dark" else QColor("#333"))
        
        # Set smaller font
        font = painter.font()
        font.setPointSize(8)  # Smaller font size
        painter.setFont(font)
        
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        
        painter.end()
    
    def mousePressEvent(self, event):
        # Handle click on checkbox area more precisely
        checkbox_size = 12
        checkbox_rect = QRect(2, (self.height() - checkbox_size) // 2, checkbox_size, checkbox_size)
        
        if event.button() == Qt.MouseButton.LeftButton:
            if checkbox_rect.contains(event.pos()) or event.pos().x() < 20:
                # Click on checkbox or very close to it
                self.toggle()
                return
        
        # For clicks on text area, also toggle
        super().mousePressEvent(event)

# =====================================================
# Custom ComboBox dengan simbol dropdown ∨
# =====================================================
class CustomComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = "dark"  # default theme
        # Hilangkan panah & drop-down default; padding kanan untuk arrow kustom
        self.setStyleSheet(
            "QComboBox { padding-right: 22px; }"
            "QComboBox::down-arrow { image: none; }"
            "QComboBox::drop-down { width: 0px; border: none; }"
        )

    def setTheme(self, theme):
        """Atur tema untuk warna simbol yang benar."""
        self.theme = theme
        self.update()  # Memicu penggambaran ulang

    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        # Penempatan arrow geser sedikit agar tidak terlalu rapat ke border
        arrow_size = 5
        center_x = rect.width() - 14
        center_y = rect.height() // 2
        
        # Pilih warna berdasarkan tema
        color = "#d4d4d4" if self.theme == "dark" else "#333"
        
        # Gambar panah chevron kustom
        pen = QPen(QColor(color), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Gambar bentuk 'V'
        painter.drawLine(center_x - arrow_size, center_y - (arrow_size // 2), center_x, center_y + (arrow_size // 2))
        painter.drawLine(center_x, center_y + (arrow_size // 2), center_x + arrow_size, center_y - (arrow_size // 2))
        
        painter.end()

# =====================================================
# Filter Sidebar (right dock)
# =====================================================
class FilterSidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Spacing seragam
        gap = 8

        # Container utama
        main_container_layout = QVBoxLayout(self)
        main_container_layout.setContentsMargins(0, 0, 0, 0)
        main_container_layout.setSpacing(0)

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        main_layout = QVBoxLayout(scroll_content)
        # Tambah margin kiri/kanan agar field tidak terlalu mepet sisi dock
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(gap)

        # Blok input atas
        inputs_layout = QVBoxLayout()
        inputs_layout.setContentsMargins(0, 0, 0, 0)
        inputs_layout.setSpacing(gap)

        # ====== Tanggal Update (Date Range Picker) ======
        tgl_update_layout = QHBoxLayout(); tgl_update_layout.setContentsMargins(0,0,0,0); tgl_update_layout.setSpacing(4)
        self.tgl_update = QLineEdit(); self.tgl_update.setPlaceholderText("Tanggal Update"); self.tgl_update.setReadOnly(True)
        self.btn_tgl_update = QPushButton("📅")
        self.btn_tgl_update.setFixedWidth(36)
        self.btn_tgl_update.clicked.connect(self.open_date_range_picker)
        tgl_update_layout.addWidget(self.tgl_update)
        tgl_update_layout.addWidget(self.btn_tgl_update)
        inputs_layout.addLayout(tgl_update_layout)
        self.nama = QLineEdit(); self.nama.setPlaceholderText("Nama"); inputs_layout.addWidget(self.nama)
        
        nik_nkk_row = QHBoxLayout(); nik_nkk_row.setContentsMargins(0,0,0,0); nik_nkk_row.setSpacing(gap)
        self.nik = QLineEdit(); self.nik.setPlaceholderText("NIK")
        self.nkk = QLineEdit(); self.nkk.setPlaceholderText("NKK")
        nik_nkk_row.addWidget(self.nik); nik_nkk_row.addWidget(self.nkk)
        inputs_layout.addLayout(nik_nkk_row)

        self.tgl_lahir = QLineEdit(); self.tgl_lahir.setPlaceholderText("Tanggal Lahir (Format : DD|MM|YYYY)"); inputs_layout.addWidget(self.tgl_lahir)

        # Umur
        umur_container = QVBoxLayout(); umur_container.setContentsMargins(0,0,0,0); umur_container.setSpacing(gap)
        lbl_umur = QLabel("Umur")
        umur_layout = QHBoxLayout(); umur_layout.setContentsMargins(2,0,2,0); umur_layout.setSpacing(gap)
        self.umur_slider = QSlider(Qt.Orientation.Horizontal); self.umur_slider.setRange(0,100)
        self.umur_label = QLabel("0"); self.umur_label.setMinimumWidth(26); self.umur_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.umur_slider.valueChanged.connect(self.update_umur_label)
        umur_layout.addWidget(self.umur_slider); umur_layout.addWidget(self.umur_label)
        umur_container.addWidget(lbl_umur); umur_container.addLayout(umur_layout)
        inputs_layout.addLayout(umur_container)

        main_layout.addLayout(inputs_layout)

        # Dropdown grid
        grid_layout = QGridLayout(); grid_layout.setContentsMargins(0,0,0,0)
        grid_layout.setHorizontalSpacing(gap); grid_layout.setVerticalSpacing(gap)
        self.keterangan = CustomComboBox(); self.kelamin = CustomComboBox(); self.kawin = CustomComboBox()
        self.disabilitas = CustomComboBox(); self.ktp_el = CustomComboBox(); self.sumber = CustomComboBox(); self.rank = CustomComboBox()
        self.alamat = QLineEdit(); self.alamat.setPlaceholderText("Alamat")
        self.keterangan.addItems(["Keterangan","1 (Meninggal)","2 (Ganda)","3 (Di Bawah Umur)","4 (Pindah Domisili)","5 (WNA)","6 (TNI)","7 (Polri)","8 (Salah TPS)","U (Ubah)","90 (Keluar Loksus)","91 (Meninggal)","92 (Ganda)","93 (Di Bawah Umur)","94 (Pindah Domisili)","95 (WNA)","96 (TNI)","97 (Polri)"])
        self.kelamin.addItems(["Kelamin","L","P"])
        self.kawin.addItems(["Kawin","S","B","P"])
        self.disabilitas.addItems(["Disabilitas","0 (Normal)","1 (Fisik)","2 (Intelektual)","3 (Mental)","4 (Sensorik Wicara)","5 (Sensorik Rungu)","6 (Sensorik Netra)"])
        self.ktp_el.addItems(["KTP-el","B","S"])
        self.sumber.addItems(["Sumber","DP4","DPTb","DPK"])
        self.rank.addItems(["Rank","Aktif","Ubah","TMS","Baru"])
        grid_layout.addWidget(self.keterangan,0,0); grid_layout.addWidget(self.kelamin,0,1); grid_layout.addWidget(self.kawin,0,2)
        grid_layout.addWidget(self.disabilitas,1,0); grid_layout.addWidget(self.ktp_el,1,1); grid_layout.addWidget(self.sumber,1,2)
        grid_layout.addWidget(self.alamat,2,0,1,2); grid_layout.addWidget(self.rank,2,2)
        main_layout.addSpacing(gap)
        main_layout.addLayout(grid_layout)

        # Checkboxes
        checkbox_layout = QGridLayout(); checkbox_layout.setContentsMargins(0,0,0,0)
        checkbox_layout.setHorizontalSpacing(gap); checkbox_layout.setVerticalSpacing(gap)
        self.cb_ganda = CustomCheckBox("Ganda"); self.cb_invalid_tgl = CustomCheckBox("Invalid Tgl")
        self.cb_nkk_terpisah = CustomCheckBox("NKK Terpisah"); self.cb_analisis_tms = CustomCheckBox("Analisis TMS 8")
        for cb in [self.cb_ganda, self.cb_invalid_tgl, self.cb_nkk_terpisah, self.cb_analisis_tms]:
            cb.setFixedHeight(22)
        checkbox_layout.addWidget(self.cb_ganda,0,0); checkbox_layout.addWidget(self.cb_invalid_tgl,0,1)
        checkbox_layout.addWidget(self.cb_nkk_terpisah,1,0); checkbox_layout.addWidget(self.cb_analisis_tms,1,1)
        main_layout.addSpacing(gap)
        main_layout.addLayout(checkbox_layout)

        # Radio buttons
        radio_layout = QHBoxLayout(); radio_layout.setContentsMargins(0,0,0,0); radio_layout.setSpacing(gap)
        self.rb_reguler = QRadioButton("Reguler"); self.rb_khusus = QRadioButton("Khusus"); self.rb_reguler_khusus = QRadioButton("Reguler & Khusus")
        self.rb_reguler_khusus.setChecked(True)
        for rb in [self.rb_reguler, self.rb_khusus, self.rb_reguler_khusus]:
            radio_layout.addWidget(rb)
        main_layout.addSpacing(gap)
        main_layout.addLayout(radio_layout)

        # Buttons
        btn_layout = QHBoxLayout(); btn_layout.setContentsMargins(0,4,0,4); btn_layout.setSpacing(gap)
        self.btn_reset = QPushButton("Reset"); self.btn_reset.setObjectName("resetBtn"); self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_filter = QPushButton("Filter"); self.btn_filter.setObjectName("filterBtn"); self.btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_filters)
        btn_layout.addStretch(); btn_layout.addWidget(self.btn_reset); btn_layout.addWidget(self.btn_filter); btn_layout.addStretch()
        main_layout.addSpacing(gap)
        main_layout.addLayout(btn_layout)

        # Finalize
        scroll_area.setWidget(scroll_content)
        main_container_layout.addWidget(scroll_area)

        # Tinggi input & combo
        desired_height = 38
        for w in [self.tgl_update, self.nama, self.nik, self.nkk, self.tgl_lahir, self.alamat,
                  self.keterangan, self.kelamin, self.kawin, self.disabilitas, self.ktp_el, self.sumber, self.rank]:
            w.setFixedHeight(desired_height)

    # ==========================
    # Method: Reset Filters
    # ==========================
    def reset_filters(self):
        self.tgl_update.clear()
        self.nama.clear()
        self.nik.clear()
        self.nkk.clear()
        self.tgl_lahir.clear()
        self.alamat.clear()
        self.keterangan.setCurrentIndex(0)
        self.kelamin.setCurrentIndex(0)
        self.kawin.setCurrentIndex(0)
        self.disabilitas.setCurrentIndex(0)
        self.ktp_el.setCurrentIndex(0)
        self.sumber.setCurrentIndex(0)
        self.rank.setCurrentIndex(0)
        self.cb_ganda.setChecked(False)
        self.cb_invalid_tgl.setChecked(False)
        self.cb_nkk_terpisah.setChecked(False)
        self.cb_analisis_tms.setChecked(False)
        self.rb_reguler_khusus.setChecked(True)
        self.umur_slider.setValue(0)

    def update_umur_label(self, value):
        self.umur_label.setText(str(value))

    def get_filters(self):
        keterangan_text = self.keterangan.currentText()
        keterangan_value = keterangan_text.split(' ')[0] if keterangan_text != "Keterangan" else ""
        disabilitas_text = self.disabilitas.currentText()
        disabilitas_value = disabilitas_text.split(' ')[0] if disabilitas_text != "Disabilitas" else ""
        rank_text = self.rank.currentText()
        rank_value = rank_text if rank_text != "Rank" else ""
        # Parse rentang tanggal update (format: DD/MM/YYYY - DD/MM/YYYY)
        last_update_start = ""; last_update_end = ""
        raw_range = self.tgl_update.text().strip()
        if raw_range and ' - ' in raw_range:
            part_start, part_end = raw_range.split(' - ', 1)
            if self._valid_date(part_start) and self._valid_date(part_end):
                last_update_start, last_update_end = part_start, part_end
        return {
            "nama": self.nama.text().strip(),
            "nik": self.nik.text().strip(),
            "nkk": self.nkk.text().strip(),
            "tgl_lahir": self.tgl_lahir.text().strip(),
            "umur": self.umur_slider.value(),
            "keterangan": keterangan_value,
            "jk": self.kelamin.currentText() if self.kelamin.currentText() != "Kelamin" else "",
            "sts": self.kawin.currentText() if self.kawin.currentText() != "Kawin" else "",
            "dis": disabilitas_value,
            "ktpel": self.ktp_el.currentText() if self.ktp_el.currentText() != "KTP-el" else "",
            "sumber": self.sumber.currentText() if self.sumber.currentText() != "Sumber" else "",
            "rank": rank_value,
            "last_update_start": last_update_start,
            "last_update_end": last_update_end
        }

    def open_date_range_picker(self):
        # Jika sudah ada nilai sebelumnya, parse agar pramuat
        start = end = None
        txt = self.tgl_update.text().strip()
        if txt and ' - ' in txt:
            s,e = txt.split(' - ',1)
            try:
                start = datetime.strptime(s, "%d/%m/%Y").date()
                end = datetime.strptime(e, "%d/%m/%Y").date()
            except ValueError:
                start = end = None
        dlg = DateRangePickerDialog(self, start, end)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            s,e = dlg.get_range()
            if s and e:
                self.tgl_update.setText(f"{s.strftime('%d/%m/%Y')} - {e.strftime('%d/%m/%Y')}")

    def _valid_date(self, s: str) -> bool:
        try:
            datetime.strptime(s, "%d/%m/%Y")
            return True
        except ValueError:
            return False

    def apply_theme(self, mode):
        for checkbox in [self.cb_ganda, self.cb_invalid_tgl, self.cb_nkk_terpisah, self.cb_analisis_tms]:
            checkbox.setTheme(mode)
        for combo in [self.keterangan, self.kelamin, self.kawin, self.disabilitas, self.ktp_el, self.sumber, self.rank]:
            combo.setTheme(mode)
        if mode == "dark":
            self.setStyleSheet("""
                QWidget { font-family: 'Segoe UI', 'Calibri'; font-size: 9px; background: #1e1e1e; color: #d4d4d4; }
                QScrollArea { border: none; background: #1e1e1e; }
                QScrollBar:vertical { border: none; background: #3e3e42; width: 6px; margin: 0px; }
                QScrollBar::handle:vertical { background: #666666; border-radius: 3px; min-height: 20px; }
                QScrollBar::handle:vertical:hover { background: #888888; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0px; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
                QLineEdit, QComboBox { padding: 8px 10px; border: 1px solid #555; border-radius: 4px; background: #2d2d30; min-height: 34px; color: #d4d4d4; font-size: 10px; }
                QLineEdit:focus, QComboBox:focus { border: 1px solid #888; }
                QComboBox QListView { background: #2d2d30; border: 1px solid #555; selection-background-color: #094771; }
                QSlider::groove:horizontal { height: 6px; background: #2d2d30; border-radius: 3px; }
                QSlider::handle:horizontal { background: #007acc; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }
                QPushButton#resetBtn { background: #444; border: 1px solid #666; border-radius: 4px; padding: 6px 14px; }
                QPushButton#resetBtn:hover { background: #555; }
                QPushButton#filterBtn { background: #0e639c; border: 1px solid #1177bb; border-radius: 4px; padding: 6px 14px; }
                QPushButton#filterBtn:hover { background: #1177bb; }
            """)
        else:
            self.setStyleSheet("""
                QWidget { font-family: 'Segoe UI', 'Calibri'; font-size: 9px; background: #f2f2f2; color: #222; }
                QScrollArea { border: none; background: #f2f2f2; }
                QScrollBar:vertical { border: none; background: #d0d0d0; width: 6px; margin: 0px; }
                QScrollBar::handle:vertical { background: #999; border-radius: 3px; min-height: 20px; }
                QScrollBar::handle:vertical:hover { background: #777; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0px; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
                QLineEdit, QComboBox { padding: 8px 10px; border: 1px solid #bbb; border-radius: 4px; background: #ffffff; min-height: 34px; color: #222; font-size: 10px; }
                QLineEdit:focus, QComboBox:focus { border: 1px solid #888; }
                QComboBox QListView { background: #ffffff; border: 1px solid #bbb; selection-background-color: #d7ebff; }
                QSlider::groove:horizontal { height: 6px; background: #d0d0d0; border-radius: 3px; }
                QSlider::handle:horizontal { background: #0e639c; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }
                QPushButton#resetBtn { background: #e0e0e0; border: 1px solid #ccc; border-radius: 4px; padding: 6px 14px; }
                QPushButton#resetBtn:hover { background: #dadada; }
                QPushButton#filterBtn { background: #0e639c; border: 1px solid #1177bb; border-radius: 4px; padding: 6px 14px; color: #fff; }
                QPushButton#filterBtn:hover { background: #1177bb; }
            """)

# =====================================================
# FixedDockWidget untuk mencegah resize lebar sidebar
# =====================================================
class FixedDockWidget(QDockWidget):
    def __init__(self, title: str, parent=None, fixed_width: int = 320):
        super().__init__(title, parent)
        self._fixed_width = fixed_width
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        # Hanya bisa di-close, tidak bisa di-float / ubah size
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.setMinimumWidth(fixed_width)
        self.setMaximumWidth(fixed_width)

    def setWidget(self, widget: QWidget) -> None:  # type: ignore
        super().setWidget(widget)
        widget.setFixedWidth(self._fixed_width)

    def sizeHint(self):  # type: ignore
        sz = super().sizeHint()
        sz.setWidth(self._fixed_width)
        return sz
            
        if mode == "dark":
            self.setStyleSheet("""
                QWidget {
                    font-family: 'Segoe UI', 'Calibri';
                    font-size: 9px;
                    background: #1e1e1e;
                    color: #d4d4d4;
                }
                QScrollArea {
                    border: none;
                    background: #1e1e1e;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #3e3e42;
                    width: 6px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #666666;
                    border-radius: 3px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #888888;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                    height: 0px;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
                QLineEdit, QComboBox {
                    padding: 8px 10px;
                    border: 1px solid #555;
                    border-radius: 4px;
                    background: #2d2d30;
                    min-height: 34px; /* disesuaikan dengan tinggi baru */
                    color: #d4d4d4;
                    font-size: 10px;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 1px solid #ff9800;
                    outline: none;
                }
                QLineEdit::placeholder {
                    color: #888;
                }
                QLabel {
                    font-weight: normal;
                    color: #d4d4d4;
                    padding: 1px;
                    background: transparent;
                    font-size: 9px;
                }
                QPushButton {
                    padding: 8px 20px;
                    border: none;
                    border-radius: 3px;
                    font-weight: bold;
                    min-width: 70px;
                    font-size: 10px;
                    color: white;
                }
                QPushButton#resetBtn {
                    background: #ff9800;
                }
                QPushButton#filterBtn {
                    background: #ff9800;
                }
                QPushButton#resetBtn:hover {
                    background: #fb8c00;
                }
                QPushButton#filterBtn:hover {
                    background: #fb8c00;
                }
                QPushButton:pressed {
                    background: #f57c00;
                }
                QRadioButton {
                    spacing: 3px;
                    padding: 1px;
                    color: #d4d4d4;
                    background: transparent;
                    font-size: 8px;
                }
                QRadioButton::indicator {
                    width: 10px;
                    height: 10px;
                    border: 1px solid #555;
                    border-radius: 5px;
                    background: #2d2d30;
                }
                QRadioButton::indicator:checked {
                    background: #ff9800;
                    border-color: #ff9800;
                }
                QRadioButton::indicator:hover {
                    border-color: #777;
                }
                QSlider::groove:horizontal {
                    border: none;
                    height: 3px;
                    background: #555;
                    margin: 0px;
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    background: #ff9800;
                    border: 2px solid #2d2d30;
                    width: 14px;
                    height: 14px;
                    margin: -6px 0;
                    border-radius: 8px;
                }
                QSlider::handle:horizontal:hover {
                    background: #fb8c00;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 6px;
                    width: 16px;
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                }
                QComboBox::down-arrow {
                    image: none;
                    width: 0;
                    height: 0;
                }
                QComboBox:hover {
                    border: 1px solid #ff9800;
                }
                QFrame[frameShape="4"] {
                    color: #555;
                    background-color: #555;
                }
            """)
        else:  # light theme
            self.setStyleSheet("""
                QWidget {
                    font-family: 'Segoe UI', 'Calibri';
                    font-size: 9px;
                    background: white;
                }
                QScrollArea {
                    border: none;
                    background: white;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #f0f0f0;
                    width: 6px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #cccccc;
                    border-radius: 3px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #aaaaaa;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                    height: 0px;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
                QLineEdit, QComboBox {
                    padding: 8px 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: white;
                    min-height: 34px; /* disesuaikan dengan tinggi baru */
                    color: #333;
                    font-size: 10px;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 1px solid #ff9800;
                    outline: none;
                }
                QLineEdit::placeholder {
                    color: #999;
                }
                QLabel {
                    font-weight: normal;
                    color: #666;
                    padding: 1px;
                    background: transparent;
                    font-size: 9px;
                }
                QPushButton {
                    padding: 8px 20px;
                    border: none;
                    border-radius: 3px;
                    font-weight: bold;
                    min-width: 70px;
                    font-size: 10px;
                    color: white;
                }
                QPushButton#resetBtn {
                    background: #ff9800;
                }
                QPushButton#filterBtn {
                    background: #ff9800;
                }
                QPushButton#resetBtn:hover {
                    background: #fb8c00;
                }
                QPushButton#filterBtn:hover {
                    background: #fb8c00;
                }
                QPushButton:pressed {
                    background: #f57c00;
                }
                QCheckBox {
                    padding: 2px;
                    spacing: 4px;
                    color: #333;
                    background: transparent;
                    font-size: 9px;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1px solid #888;
                    border-radius: 4px;
                    background: transparent;
                }
                QCheckBox::indicator:checked {
                    background-color: #ff9900;
                    border: 1px solid #ff9900;
                }
                QCheckBox::indicator:checked::after {
                    content: "✓";
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                    text-align: center;
                    line-height: 14px;
                }
                QCheckBox::indicator:hover {
                    border-color: #ff9900;
                }
                QRadioButton {
                    spacing: 3px;
                    padding: 1px;
                    color: #333;
                    background: transparent;
                    font-size: 8px;
                }
                QRadioButton::indicator {
                    width: 10px;
                    height: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background: white;
                }
                QRadioButton::indicator:checked {
                    background: #2196F3;
                    border-color: #2196F3;
                }
                QRadioButton::indicator:hover {
                    border-color: #aaa;
                }
                QSlider::groove:horizontal {
                    border: none;
                    height: 3px;
                    background: #e0e0e0;
                    margin: 0px;
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    background: #2196F3;
                    border: 2px solid white;
                    width: 14px;
                    height: 14px;
                    margin: -6px 0;
                    border-radius: 8px;
                }
                QSlider::handle:horizontal:hover {
                    background: #1976D2;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 6px;
                    width: 16px;
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                }
                QComboBox::down-arrow {
                    image: none;
                    width: 0;
                    height: 0;
                }
                QComboBox:hover {
                    border: 1px solid #ff9800;
                }
                QFrame[frameShape="4"] {
                    color: #e0e0e0;
                    background-color: #e0e0e0;
                }
            """)

# =========================================================
# 🔹 FUNGSI GLOBAL: PALET TEMA
# =========================================================
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication

def apply_global_palette(app, mode: str):
    """Atur palet global (QPalette) agar semua widget ikut tema aktif."""
    palette = QPalette()
    if mode == "dark":
        # 🌑 Tema Gelap
        palette.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#252526"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2d2d30"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2b2b2b"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#333333"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff6600"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#264f78"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    else:
        # ☀️ Tema Terang
        palette.setColor(QPalette.ColorRole.Window, QColor("#f9f9f9"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f0f0f0"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#f2f2f2"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff6600"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#bcbcbc"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))

    app.setPalette(palette)

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
                show_modern_error(self, "Error", f"Gagal dekripsi database:\n{e}")
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
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

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
            action_import_baru.triggered.connect(lambda: show_modern_info(self, "Info", "Import Pemilih Baru diklik"))
            action_import_tms.triggered.connect(lambda: show_modern_info(self, "Info", "Import Pemilih TMS diklik"))
            action_import_ubah.triggered.connect(lambda: show_modern_info(self, "Info", "Import Pemilih Ubah Data diklik"))

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
        self.style_button(btn_filter, bg="#ff6634", fg="white", bold=True)
        btn_filter.setIcon(QIcon.fromTheme("view-filter")) # type: ignore
        btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_filter.clicked.connect(self.toggle_filter_sidebar)
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

        # ✅ Tampilkan jendela langsung dalam keadaan maximize
        self.showMaximized()

        # ✅ Jalankan fungsi urutkan data secara senyap setelah login
        QTimer.singleShot(200, lambda: self.sort_data(auto=True))

        # ✅ Initialize filter sidebar
        self.filter_sidebar = None
        self.filter_dock = None

        atexit.register(self._encrypt_and_cleanup)

    def show_setting_dialog(self):
        dlg = SettingDialog(self, self.db_name)
        if dlg.exec():
            self.apply_column_visibility()
            self.auto_fit_columns()
    
    def toggle_filter_sidebar(self):
        """Toggle the filter sidebar visibility"""
        if self.filter_dock is None:
            # Create filter sidebar and dock widget
            self.filter_sidebar = FilterSidebar(self)
            # Gunakan FixedDockWidget agar lebar benar-benar fix dan tidak bisa digeser
            fixed_width = 320
            self.filter_dock = FixedDockWidget("Filter", self, fixed_width=fixed_width)
            self.filter_dock.setWidget(self.filter_sidebar)
            
            # Apply current theme to filter sidebar
            current_theme = self.load_theme()
            self.filter_sidebar.apply_theme(current_theme)
            
            # Connect filter button in sidebar to apply filters
            self.filter_sidebar.btn_filter.clicked.connect(self.apply_filters)
            
            # Connect reset button to clear filters
            self.filter_sidebar.btn_reset.clicked.connect(self.clear_filters)
            
            # Add to main window
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.filter_dock)
            
            # Lebar sudah dikunci oleh FixedDockWidget; tidak perlu setFixedWidth lagi
        
        # Toggle visibility
        self.filter_dock.setVisible(not self.filter_dock.isVisible())
    
    def apply_filters(self):
        """Apply filters from the filter sidebar"""
        if not self.filter_sidebar:
            return
            
        filters = self.filter_sidebar.get_filters()
        
        # Store original data if not already stored
        if not hasattr(self, 'original_data') or self.original_data is None:
            self.original_data = self.all_data.copy()
        
        # Always filter from original data, not from previously filtered data
        # This allows applying new filters without resetting first
        filtered_data = []
        for item in self.original_data:
            if self.matches_filters(item, filters):
                filtered_data.append(item)
        
        # Replace all_data with filtered data
        self.all_data = filtered_data
        
        # Update pagination and display
        self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
        self.current_page = 1
        self.show_page(1)
        
        # Update status bar with filter info (no popup)
        self.lbl_total.setText(f"{len(filtered_data)} dari {len(self.original_data)} total (filtered)")
    
    def clear_filters(self):
        """Clear all filters and restore original data"""
        if hasattr(self, 'original_data') and self.original_data is not None:
            self.all_data = self.original_data.copy()
            self.original_data = None
            
            # Update pagination and display
            self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
            self.current_page = 1
            self.show_page(1)
        
        # Reset filter form
        if self.filter_sidebar:
            self.filter_sidebar.reset_filters()
    
    def wildcard_match(self, pattern, text):
        """Wildcard matching with % support
        
        Args:
            pattern: Pattern string with % as wildcard (e.g., "john%doe", "%smith", "mary%")
            text: Text to match against
            
        Returns:
            bool: True if pattern matches text
        """
        if not pattern:
            return True
            
        # Convert to lowercase for case-insensitive matching
        pattern = pattern.lower()
        text = text.lower()
        
        # If no wildcard, use simple contains check
        if '%' not in pattern:
            return pattern in text
            
        # Split pattern by wildcards
        parts = pattern.split('%')
        
        # Handle edge cases
        if len(parts) == 1:
            return pattern in text
            
        # Check if text starts with first part (if not empty)
        if parts[0] and not text.startswith(parts[0]):
            return False
            
        # Check if text ends with last part (if not empty)
        if parts[-1] and not text.endswith(parts[-1]):
            return False
            
        # Check middle parts in order
        current_pos = 0
        for i, part in enumerate(parts):
            if not part:  # Skip empty parts (from consecutive wildcards)
                continue
                
            if i == 0:  # First part
                current_pos = len(part)
            elif i == len(parts) - 1:  # Last part
                continue  # Already checked with endswith
            else:  # Middle parts
                pos = text.find(part, current_pos)
                if pos == -1:
                    return False
                current_pos = pos + len(part)
                
        return True
    
    def matches_filters(self, item, filters):
        """Check if an item matches the given filters"""
        # Name filter with wildcard support
        if filters["nama"]:
            nama_item = item.get("NAMA", "")
            if not self.wildcard_match(filters["nama"], nama_item):
                return False
            
        # NIK filter
        if filters["nik"] and filters["nik"] not in item.get("NIK", ""):
            return False
            
        # NKK filter
        if filters["nkk"] and filters["nkk"] not in item.get("NKK", ""):
            return False
            
        # Date filter (simple contains check)
        if filters["tgl_lahir"] and filters["tgl_lahir"] not in item.get("TGL_LHR", ""):
            return False
            
        # Keterangan filter
        if filters["keterangan"] and filters["keterangan"] != item.get("KET", ""):
            return False
            
        # Gender filter
        if filters["jk"] and filters["jk"] != item.get("JK", ""):
            return False
            
        # Marital status filter
        if filters["sts"] and filters["sts"] != item.get("STS", ""):
            return False
            
        # Disability filter
        if filters["dis"] and filters["dis"] != item.get("DIS", ""):
            return False
            
        # KTP-el filter
        if filters["ktpel"] and filters["ktpel"] != item.get("KTPel", ""):
            return False
            
        # Source filter
        if filters["sumber"] and filters["sumber"] != item.get("SUMBER", ""):
            return False
        
        # Rank filter - map rank values to KET values
        if filters["rank"]:
            rank_mapping = {
                "Aktif": "0",      # KET = 0 means active
                "Ubah": "U",       # KET = U means changed
                "TMS": ["1", "2", "3", "4", "5", "6", "7", "8"],  # KET = 1-8 means TMS
                "Baru": "B"        # KET = B means new
            }
            
            ket_value = item.get("KET", "")
            rank_filter = filters["rank"]
            
            if rank_filter == "TMS":
                if ket_value not in rank_mapping["TMS"]:
                    return False
            else:
                expected_ket = rank_mapping.get(rank_filter, "")
                if ket_value != expected_ket:
                    return False

        # LastUpdate date range filter
        if filters.get("last_update_start") and filters.get("last_update_end"):
            raw_last = item.get("LastUpdate", "").strip()
            if not raw_last:
                return False
            parsed = None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    parsed = datetime.strptime(raw_last, fmt).date()
                    break
                except ValueError:
                    continue
            if not parsed:
                return False
            try:
                start_dt = datetime.strptime(filters["last_update_start"], "%d/%m/%Y").date()
                end_dt = datetime.strptime(filters["last_update_end"], "%d/%m/%Y").date()
            except ValueError:
                return False
            if parsed < start_dt or parsed > end_dt:
                return False
            
        return True

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
        app = QApplication.instance()
        apply_global_palette(app, mode)

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
                QMenu {
                    background-color: #2d2d30;
                    color: white;
                    border: 1px solid #444;
                    border-radius: 6px;
                    padding: 4px;
                }
                QMenu::item:selected {
                    background-color: #ff9900;
                    color: black;
                    border-radius: 4px;
                }
                QDockWidget {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3e3e42;
                }
                QDockWidget::title {
                    background-color: #333333;
                    color: #dcdcdc;
                    padding: 6px;
                    font-weight: bold;
                }
            """)
            self.checkbox_delegate.setTheme("dark")

        elif mode == "light":
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #f9f9f9;
                    color: #000000;
                    font-family: Segoe UI, Calibri, sans-serif;
                }
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f3f3f3;
                    color: #000000;
                    gridline-color: #c0c0c0;
                    selection-background-color: #bcbcbc;
                    selection-color: #000000;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    color: #000000;
                    font-weight: bold;
                    border: 1px solid #c0c0c0;
                    padding: 4px;
                }
                QMenu {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #aaa;
                    border-radius: 6px;
                    padding: 4px;
                }
                QMenu::item:selected {
                    background-color: #ff9900;
                    color: black;
                    border-radius: 4px;
                }
                QDockWidget {
                    background-color: #f9f9f9;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                }
                QDockWidget::title {
                    background-color: #f0f0f0;
                    color: #000000;
                    padding: 6px;
                    font-weight: bold;
                }
            """)
            self.checkbox_delegate.setTheme("light")

        # Apply theme to filter sidebar if it exists
        if hasattr(self, 'filter_sidebar') and self.filter_sidebar is not None:
            self.filter_sidebar.apply_theme(mode)

        # ✅ Simpan pilihan ke DB
        self.save_theme(mode)
        self.show_page(self.current_page)
        
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

    # Memunculkan menu klik kanan
    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        row = index.row()
        chk_item = self.table.item(row, 0)

        # --- Ambil semua baris yang sudah dicentang
        checked_rows = [
            r for r in range(self.table.rowCount())
            if self.table.item(r, 0)
            and self.table.item(r, 0).checkState() == Qt.CheckState.Checked
        ]

        # --- Jika belum ada checkbox tercentang → anggap klik kanan tunggal
        if not checked_rows:
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item:
                    item.setCheckState(Qt.CheckState.Unchecked)
            if not chk_item:
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, 0, chk_item)
            chk_item.setCheckState(Qt.CheckState.Checked)
            checked_rows = [row]

        self.table.viewport().update()
        self.update_statusbar()

        # --- Buat Context Menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d30;
                color: white;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 28px;
                border-radius: 4px;
                font-family: 'Segoe UI';
                font-size: 10.5pt;
            }
            QMenu::item:selected {
                background-color: #ff9900;
                color: black;
            }
        """)

        actions = [
            ("✏️ Lookup", lambda: self._context_action_wrapper(checked_rows, self.lookup_pemilih)),
            ("🔁 Aktifkan Pemilih", lambda: self._context_action_wrapper(checked_rows, self.aktifkan_pemilih)),
            ("🔥 Hapus", lambda: self._context_action_wrapper(checked_rows, self.hapus_pemilih)),
            ("🚫 Meninggal", lambda: self._context_action_wrapper(checked_rows, self.meninggal_pemilih)),
            ("⚠️ Ganda", lambda: self._context_action_wrapper(checked_rows, self.ganda_pemilih)),
            ("🧒 Di Bawah Umur", lambda: self._context_action_wrapper(checked_rows, self.bawah_umur_pemilih)),
            ("🏠 Pindah Domisili", lambda: self._context_action_wrapper(checked_rows, self.pindah_domisili)),
            ("🌍 WNA", lambda: self._context_action_wrapper(checked_rows, self.wna_pemilih)),
            ("🪖 TNI", lambda: self._context_action_wrapper(checked_rows, self.tni_pemilih)),
            ("👮‍♂️ Polri", lambda: self._context_action_wrapper(checked_rows, self.polri_pemilih)),
            ("📍 Salah TPS", lambda: self._context_action_wrapper(checked_rows, self.salah_tps)),
        ]

        for text, func in actions:
            act = QAction(text, self)
            act.triggered.connect(func)
            menu.addAction(act)

        # --- Jalankan dan tangkap hasil
        chosen_action = menu.exec(self.table.viewport().mapToGlobal(pos))

        # ✅ Jika user klik di luar menu → hapus seleksi & ceklis
        if not chosen_action:
            self._clear_row_selection(checked_rows)


    def _context_action_wrapper(self, rows, func):
        """Menjalankan fungsi context untuk 1 atau banyak baris dengan konfirmasi batch."""
        if isinstance(rows, int):
            rows = [rows]

        is_batch = len(rows) > 1

        # --- Jika batch, minta konfirmasi dulu
        if is_batch:
            label_action = func.__name__.replace("_pemilih", "").replace("_", " ").title()
            if not show_modern_question(
                self,
                "Konfirmasi Batch",
                f"Anda yakin ingin memproses <b>{len(rows)}</b> data sebagai <b>{label_action}</b>?"
            ):
                self._clear_row_selection(rows)
                return

            # Aktifkan mode batch supaya popup per baris dimatikan
            self._in_batch_mode = True

        # --- Jalankan fungsi untuk setiap baris
        for r in rows:
            func(r)

        # --- Selesai, tampilkan ringkasan & reset flag
        if is_batch:
            self._in_batch_mode = False
            show_modern_info(
                self,
                "Selesai",
                f"{len(rows)} data berhasil diproses."
            )

        # --- Hapus seleksi & centang
        QTimer.singleShot(150, lambda: self._clear_row_selection(rows))

    def _clear_row_selection(self, rows):
        """Reset seleksi & ceklis. rows boleh int atau list[int]."""
        # Normalisasi ke list
        if isinstance(rows, int):
            rows = [rows]
        elif not isinstance(rows, (list, tuple, set)):
            rows = []

        # Hapus centang di semua baris yang diminta
        for r in rows:
            chk_item = self.table.item(r, 0)
            if chk_item:
                chk_item.setCheckState(Qt.CheckState.Unchecked)

        # Bersihkan highlight seleksi
        self.table.clearSelection()
        self.table.viewport().update()
        self.update_statusbar()

    # =========================================================
    # 🔹 1. AKTIFKAN PEMILIH
    # =========================================================
    def aktifkan_pemilih(self, row):
        """Aktifkan kembali pemilih hanya jika:
        1️⃣ DPID tidak kosong / bukan 0, dan
        2️⃣ Nilai kolom KET adalah salah satu dari 1–8 (TMS).
        """
        dpid_item = self.table.item(row, self.col_index("DPID"))
        ket_item = self.table.item(row, self.col_index("KET"))
        nama_item = self.table.item(row, self.col_index("NAMA"))

        dpid = dpid_item.text().strip() if dpid_item else ""
        ket  = ket_item.text().strip().upper() if ket_item else ""
        nama = nama_item.text().strip() if nama_item else ""

        # ⚠️ Validasi 1: pastikan DPID valid
        if not dpid or dpid == "0":
            show_modern_warning(
                self, "Ditolak",
                f"Tindakan ditolak.<br>{nama} adalah Pemilih Aktif."
            )
            return

        # ⚠️ Validasi 2: hanya boleh jika KET = 1–8
        if ket not in ("1","2","3","4","5","6","7","8"):
            show_modern_warning(
                self, "Ditolak",
                f"Tindakan ditolak.<br>{nama} adalah Pemilih Aktif."
            )
            return

        # ✅ Set kolom KET jadi 0 (aktif)
        ket_item.setText("0")
        self.update_database_field(row, "KET", "0")

        # ✅ Sinkronkan di memori
        gi = self._global_index(row)
        if 0 <= gi < len(self.all_data):
            self.all_data[gi]["KET"] = "0"

        # 🌗 Tentukan warna teks normal sesuai tema
        bg_color = self.table.palette().color(self.table.backgroundRole())
        brightness = (bg_color.red() + bg_color.green() + bg_color.blue()) / 3
        is_light_theme = brightness > 128
        warna_normal = QColor("black") if is_light_theme else QColor("white")

        # ✅ Ubah warna teks seluruh baris ke normal
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it:
                it.setForeground(warna_normal)

        # ✅ Hanya tampilkan popup tunggal jika bukan mode batch
        if not getattr(self, "_in_batch_mode", False):
            show_modern_info(self, "Aktifkan", f"{nama} telah diaktifkan kembali.")

    # =========================================================
    # 🔹 2. HAPUS PEMILIH
    # =========================================================
    def hapus_pemilih(self, row):
        """Hapus data hanya jika DPID kosong/0, berdasarkan kombinasi ROWID + NIK + NKK + DPID + TGL_LAHIR + LastUpdate."""
        dpid_item = self.table.item(row, self.col_index("DPID"))
        nik_item  = self.table.item(row, self.col_index("NIK"))
        nkk_item  = self.table.item(row, self.col_index("NKK"))
        nama_item = self.table.item(row, self.col_index("NAMA"))

        dpid = dpid_item.text().strip() if dpid_item else ""
        nik  = nik_item.text().strip() if nik_item else ""
        nkk  = nkk_item.text().strip() if nkk_item else ""
        nama = nama_item.text().strip() if nama_item else ""

        # ⚠️ Hanya boleh hapus jika DPID kosong atau 0
        if dpid and dpid != "0":
            show_modern_warning(
                self, "Ditolak",
                f"{nama} tidak dapat dihapus dari Daftar Pemilih.<br>"
                f"Hanya Pemilih Baru di tahap ini yang bisa dihapus!"
            )
            return

        # 🔸 Konfirmasi sebelum hapus
        if not show_modern_question(
            self, "Konfirmasi Hapus",
            f"Apakah Anda yakin ingin menghapus data ini?<br>"
            f"<b>{nama}</b><br>NIK: <b>{nik}</b><br>NKK: <b>{nkk}</b>"
        ):
            return

        gi = self._global_index(row)
        if not (0 <= gi < len(self.all_data)):
            return

        sig = self._row_signature_from_ui(row)
        rowid = self.all_data[gi].get("ROWID") or self.all_data[gi].get("_rowid_")

        if not rowid:
            show_modern_error(self, "Error", "ROWID tidak ditemukan — data tidak dapat dihapus.")
            return

        # Normalisasi tanggal (kadang tersimpan sebagai 2024-10-05, kadang 05/10/2024)
        last_update = sig.get("LastUpdate", "").strip()
        if "/" in last_update:
            try:
                from datetime import datetime
                dt = datetime.strptime(last_update, "%d/%m/%Y")
                last_update = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        try:
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()

            # 🔥 Hapus hanya jika semua identitas cocok persis
            cur.execute("""
                DELETE FROM data_pemilih
                WHERE ROWID = ?
                AND IFNULL(NIK,'') = ?
                AND IFNULL(NKK,'') = ?
                AND (IFNULL(DPID,'') = ? OR DPID IS NULL)
                AND IFNULL(TGL_LHR,'') = ?
                AND IFNULL(LastUpdate,'') = ?
            """, (rowid, sig["NIK"], sig["NKK"], sig["DPID"], sig["TGL_LHR"], last_update))
            conn.commit()
            conn.close()

            # 🔹 Hapus dari memori
            del self.all_data[gi]

            # 🔹 Jika halaman kosong setelah hapus, pindah ke halaman sebelumnya
            if (self.current_page > 1) and ((self.current_page - 1) * self.rows_per_page >= len(self.all_data)):
                self.current_page -= 1

            # ✅ Hanya tampilkan popup tunggal jika bukan mode batch
            if not getattr(self, "_in_batch_mode", False):
                show_modern_info(self, "Selesai", f"{nama} berhasil dihapus dari Daftar Pemilih!")

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal menghapus data:\n{e}")


    # =========================================================
    # 🔹 3. STATUS PEMILIH (Meninggal, Ganda, Dll)
    # =========================================================
    def set_ket_status(self, row, new_value: str, label: str):
        dpid_item = self.table.item(row, self.col_index("DPID"))
        nama_item = self.table.item(row, self.col_index("NAMA"))
        nama = nama_item.text().strip() if nama_item else ""

        if not dpid_item or dpid_item.text().strip() in ("", "0"):
            show_modern_warning(self, "Ditolak", "Data Pemilih Baru tidak bisa di TMS-kan.")
            return

        # ubah nilai di tabel dan database
        ket_item = self.table.item(row, self.col_index("KET"))
        if ket_item:
            ket_item.setText(new_value)
            self.update_database_field(row, "KET", new_value)

        # sinkronkan memori
        gi = self._global_index(row)
        if 0 <= gi < len(self.all_data):
            self.all_data[gi]["KET"] = new_value

        # ubah warna teks menjadi merah
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it:
                it.setForeground(QColor("red"))

        # ✅ Hanya tampilkan popup tunggal jika bukan mode batch
        if not getattr(self, "_in_batch_mode", False):
            show_modern_info(self, label, f"{nama} disaring sebagai Pemilih {label}.")


    # =========================================================
    # 🔹 4. Fungsi status cepat (delegasi ke helper di atas)
    # =========================================================
    def meninggal_pemilih(self, row): self.set_ket_status(row, "1", "Meninggal")
    def ganda_pemilih(self, row): self.set_ket_status(row, "2", "Ganda")
    def bawah_umur_pemilih(self, row): self.set_ket_status(row, "3", "Di Bawah Umur")
    def pindah_domisili(self, row): self.set_ket_status(row, "4", "Pindah Domisili")
    def wna_pemilih(self, row): self.set_ket_status(row, "5", "WNA")
    def tni_pemilih(self, row): self.set_ket_status(row, "6", "TNI")
    def polri_pemilih(self, row): self.set_ket_status(row, "7", "Polri")
    def salah_tps(self, row): self.set_ket_status(row, "8", "Salah TPS")


    # =========================================================
    # 🔹 Helper kolom dan update database
    # =========================================================
    def col_index(self, header_name):
        for i in range(self.table.columnCount()):
            if self.table.horizontalHeaderItem(i).text().strip().upper() == header_name.upper():
                return i
        return -1

    def _global_index(self, row_in_page: int) -> int:
        """Konversi nomor baris di tampilan jadi index global di all_data."""
        return (self.current_page - 1) * self.rows_per_page + row_in_page

    def _row_signature_from_ui(self, row: int) -> dict:
        """Ambil identitas unik baris untuk keperluan penghapusan yang aman."""
        fields = ["KECAMATAN","DESA","DPID","NKK","NIK","NAMA","JK","TMPT_LHR",
                  "TGL_LHR","STS","ALAMAT","RT","RW","DIS","KTPel","SUMBER","TPS","LastUpdate"]
        sig = {}
        for f in fields:
            ci = self.col_index(f)
            sig[f] = self.table.item(row, ci).text().strip() if ci != -1 and self.table.item(row, ci) else ""
        return sig

    def update_database_field(self, row, field_name, value):
        """Update satu kolom di database berdasar NIK."""
        try:
            nik_col = self.col_index("NIK")
            nik = self.table.item(row, nik_col).text().strip() if nik_col != -1 else None
            if not nik:
                return
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()
            cur.execute(f"UPDATE data_pemilih SET {field_name}=? WHERE NIK=?", (value, nik))
            conn.commit()
            conn.close()
        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memperbarui database:\n{e}")

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
                    show_modern_warning(self, "Error", "File CSV tidak valid atau terlalu pendek.")
                    return

                # 🔹 Verifikasi baris ke-15 (index 14)
                kecamatan_csv = reader[14][1].strip().upper()
                desa_csv = reader[14][3].strip().upper()
                if kecamatan_csv != self.kecamatan_login or desa_csv != self.desa_login:
                    show_modern_warning(
                        self, "Error",
                        f"Import CSV gagal!\n"
                        f"Harap Import CSV untuk Desa {self.desa_login.title()} yang bersumber dari Sidalih"
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
                    if not row or len(row) < len(header):
                        continue

                    status_val = row[idx_status].strip().upper()
                    if status_val not in ("AKTIF", "UBAH", "BARU"):
                        continue

                    data_dict, values = {}, []
                    for csv_col, app_col in mapping.items():
                        if csv_col in header:
                            col_idx = header.index(csv_col)
                            val = row[col_idx].strip()

                            # ⚡ Pastikan kolom KET selalu "0" saat import CSV
                            if app_col == "KET":
                                val = "0"

                            # 🔹 Format tanggal
                            if app_col == "LastUpdate" and val:
                                try:
                                    from datetime import datetime
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

                # ✅ Semua data KET diset ke 0 secara paksa juga di database
                try:
                    conn = sqlite3.connect(self.db_name)
                    cur = conn.cursor()
                    cur.execute("UPDATE data_pemilih SET KET='0'")
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"[Warning] Gagal set KET=0 massal: {e}")

                self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
                self.show_page(1)

                # Pastikan event header aktif lagi
                self.connect_header_events()

                # ✅ Urutkan otomatis setelah import (tanpa konfirmasi & popup)
                self.sort_data(auto=True)

                show_modern_info(self, "Sukses", "Import CSV selesai!")

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal import CSV: {e}")

    # =================================================
    # Load data dari database saat login ulang
    # =================================================
    def load_data_from_db(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row  # hasilnya jadi dictionary otomatis
        cur = conn.cursor()

        # ✅ Pastikan tabel ada
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

        # ✅ Ambil data + ROWID untuk operasi update/hapus
        cur.execute("SELECT rowid, * FROM data_pemilih")
        rows = cur.fetchall()
        conn.close()

        self.all_data = []

        for row in rows:
            # row adalah sqlite3.Row → bisa diakses seperti dict
            data_dict = dict(row)

            # Simpan rowid di key "_rowid_" tapi JANGAN tampilkan di tabel
            data_dict["_rowid_"] = data_dict.pop("rowid", None)

            # Format tanggal agar selalu DD/MM/YYYY
            if data_dict.get("LastUpdate"):
                val = str(data_dict["LastUpdate"])
                try:
                    from datetime import datetime
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            dt = datetime.strptime(val, fmt)
                            data_dict["LastUpdate"] = dt.strftime("%d/%m/%Y")
                            break
                        except:
                            continue
                except:
                    pass

            # Pastikan semua kolom yang digunakan di tabel ada
            for col in [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]:
                if col not in data_dict:
                    data_dict[col] = ""

            self.all_data.append(data_dict)

        # ✅ Pagination
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
        
        # Tampilkan info filter jika sedang aktif
        if hasattr(self, 'original_data') and self.original_data is not None:
            self.lbl_total.setText(f"{total} dari {len(self.original_data)} total (filtered)")
        else:
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
    def sort_data(self, auto=False):
        """
        Urutkan data berdasarkan TPS, RW, RT, NKK, dan NAMA.
        Jika auto=True maka dijalankan tanpa konfirmasi & popup.
        """
        # ✅ Jika bukan mode otomatis, baru minta konfirmasi
        if not auto:
            if not show_modern_question(self, "Konfirmasi", "Apakah Anda ingin mengurutkan data?"):
                return

        # 🔹 Lakukan pengurutan
        self.all_data.sort(
            key=lambda x: (
                str(x.get("TPS", "")),
                str(x.get("RW", "")),
                str(x.get("RT", "")),
                str(x.get("NKK", "")),
                str(x.get("NAMA", ""))
            )
        )

        # 🔹 Refresh tampilan
        self.show_page(1)

        # ✅ Kalau manual, baru tampilkan popup sukses
        if not auto:
            show_modern_info(self, "Selesai", "Pengurutan data telah selesai!")

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
            show_modern_warning(self, "Error", f"Gagal mengurutkan kolom LastUpdate:\n{e}")

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
        # 🔸 Dialog konfirmasi modern
        if not show_modern_question(
            self,
            "Konfirmasi",
            "Apakah Anda yakin ingin menghapus <b>SELURUH data</b> di database ini?<br>"
            "Tindakan ini <b>tidak dapat dibatalkan!</b>"
        ):
            show_modern_info(self, "Dibatalkan", "Proses penghapusan data dibatalkan.")
            return

        try:
            # 🔸 Hapus seluruh data dari tabel data_pemilih
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

            # 🔸 Kosongkan tabel tampilan
            self.all_data.clear()
            self.table.setRowCount(0)
            self.lbl_total.setText("0 total")
            self.lbl_selected.setText("0 selected")

            # 🔸 Reset pagination dan refresh tampilan
            self.total_pages = 1
            self.current_page = 1
            self.update_pagination()
            self.show_page(1)

            # 🔸 Popup sukses
            show_modern_info(
                self,
                "Selesai",
                "Seluruh data pemilih telah berhasil dihapus dari database!"
            )

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal menghapus data:\n{e}")

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

        # Jika tidak ada data, tampilkan "Data Tidak Ditemukan"
        if len(data_rows) == 0 and len(self.all_data) == 0:
            self.table.setRowCount(1)
            # Buat item "Data Tidak Ditemukan" yang span semua kolom
            item = QTableWidgetItem("Data Tidak Ditemukan")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Tidak bisa diedit atau dicentang
            
            # Set font style untuk membedakan
            font = item.font()
            font.setItalic(True)
            font.setBold(True)
            item.setFont(font)
            
            # Set warna abu-abu
            item.setForeground(QColor("gray"))
            
            self.table.setItem(0, 0, item)
            
            # Kosongkan kolom lainnya
            for j in range(1, self.table.columnCount()):
                empty_item = QTableWidgetItem("")
                empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(0, j, empty_item)
            
            # Span kolom pertama ke semua kolom
            self.table.setSpan(0, 0, 1, self.table.columnCount())
            
            self.table.blockSignals(False)
            self.lbl_selected.setText("0 selected")
            self.update_statusbar()
            self.update_pagination()
            return
        
        self.table.setRowCount(len(data_rows))
        app_columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        center_cols = {"DPID", "JK", "STS", "TGL_LHR", "RT", "RW", "DIS", "KTPel", "KET", "TPS"}

        for i, d in enumerate(data_rows):
            # ✅ Kolom pertama: checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            chk_item.setData(Qt.ItemDataRole.CheckStateRole, Qt.CheckState.Unchecked)
            chk_item.setText("")
            self.table.setItem(i, 0, chk_item)

            # ✅ Kolom lainnya (lewati _rowid_)
            for j, col in enumerate(app_columns[1:], start=1):
                if col == "_rowid_":  # jangan tampilkan rowid
                    continue

                val = d.get(col, "")

                # Format tanggal jika perlu
                if col == "LastUpdate" and val:
                    try:
                        from datetime import datetime
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                            try:
                                dt = datetime.strptime(val, fmt)
                                val = dt.strftime("%d/%m/%Y")
                                break
                            except Exception:
                                continue
                    except Exception:
                        pass

                item = QTableWidgetItem(val)

                # Tengahkan kolom tertentu
                if col in center_cols:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Nonaktifkan edit
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(i, j, item)

            # =========================================================
            # 🔹 Pewarnaan otomatis berdasarkan nilai kolom KET (tema adaptif)
            # =========================================================
            ket_index = self.col_index("KET")
            if ket_index != -1:
                ket_val = str(self.table.item(i, ket_index).text()).strip().upper()

                # Deteksi mode tema berdasarkan warna background table
                bg_color = self.table.palette().color(self.table.backgroundRole())
                brightness = (bg_color.red() + bg_color.green() + bg_color.blue()) / 3
                is_light_theme = brightness > 128

                # Warna dasar (default teks)
                warna_default = QColor("black") if is_light_theme else QColor("white")

                # Warna khusus berdasarkan KET
                if ket_val in ("1", "2", "3", "4", "5", "6", "7", "8"):
                    warna = QColor("red")       # ❌ TMS
                elif ket_val == "B":
                    warna = QColor("green")     # 🟢 BARU
                elif ket_val == "U":
                    warna = QColor("orange")    # 🟡 UBAH
                else:
                    warna = warna_default       # ⚪ Normal

                # Terapkan ke seluruh baris
                for c in range(self.table.columnCount()):
                    item = self.table.item(i, c)
                    if item:
                        item.setForeground(warna)

        self.table.blockSignals(False)
        self.lbl_selected.setText("0 selected")
        self.update_statusbar()
        self.update_pagination()
        self.table.horizontalHeader().setSortIndicatorShown(False)

        # Jadwalkan auto resize kolom setelah layout selesai
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
        self.setWindowTitle("Login Akun")

        # === Logo aplikasi di title bar ===
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "KPU.png")
        self.setWindowIcon(QIcon(logo_path))
        self.showMaximized()
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        # === Layout utama ===
        outer_layout = QVBoxLayout()
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # === Frame utama (dengan border & shadow) ===
        form_frame = QFrame()
        form_frame.setObjectName("FormFrame")  # penting agar style hanya ke frame ini
        form_frame.setFixedWidth(420)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(35)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 180))
        form_frame.setGraphicsEffect(shadow)

        # === Layout isi frame ===
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # === Logo KPU ===
        logo_label = QLabel()
        pixmap = QPixmap(logo_path)
        if pixmap.isNull():
            print(f"[PERINGATAN] Gambar tidak ditemukan di: {logo_path}")
        else:
            pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(logo_label)

        # === Teks judul ===
        title_label = QLabel("KOMISI PEMILIHAN UMUM<br>KABUPATEN TASIKMALAYA")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 13pt;
                font-weight: bold;
                font-family: 'Segoe UI';
                margin-bottom: 20px;
            }
        """)
        form_layout.addWidget(title_label)

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

        # === Tempel layout ke frame & frame ke tampilan utama ===
        form_frame.setLayout(form_layout)
        outer_layout.addWidget(form_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(outer_layout)

        # === Style global ===
        self.setStyleSheet("""
            QWidget {
                font-size: 11pt;
                color: white;
                background-color: #1e1e1e;
            }
            QFrame#FormFrame {
                background-color: #262626;
                border: 1px solid rgba(255, 255, 255, 0.25);  /* 🔹 Border hanya di frame utama */
                border-radius: 10px;
                padding: 30px 40px;
            }
            QLabel {
                background-color: transparent;  /* 🔹 Hilangkan background hitam label */
                color: white;
            }
            QLineEdit, QComboBox {
                min-height: 28px;
                font-size: 11pt;
                border: 1px solid #555;
                border-radius: 4px;
                padding-left: 6px;
                background-color: #2d2d30;
                color: white;
            }
            QPushButton {
                background-color: transparent;
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
            show_modern_warning(self, "Error", "Semua field harus diisi!")
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
        cur.execute("SELECT id, nama, kecamatan, desa, otp_secret FROM users WHERE email=? AND password=?", (email, pw))
        row = cur.fetchone()

        if not row:
            conn.close()
            show_modern_warning(self, "Login Gagal", "Email atau password salah!")
            return

        user_id, nama, kecamatan, desa, otp_secret = row

        # ============================================================
        # 1️⃣ Jika OTP belum dibuat (login pertama)
        # ============================================================
        if not otp_secret:
            import pyotp, qrcode # type: ignore
            from io import BytesIO

            otp_secret = pyotp.random_base32()

            # Simpan secret baru
            cur.execute("UPDATE users SET otp_secret=? WHERE id=?", (otp_secret, user_id))
            conn.commit()
            conn.close()

            # Buat QR Code OTP
            totp_uri = pyotp.totp.TOTP(otp_secret).provisioning_uri(name=email, issuer_name="NexVo Sidalih Pilkada 2024")
            qr = qrcode.make(totp_uri)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())

            # Tampilkan QR code untuk aktivasi OTP
            qr_dialog = QDialog(self)
            qr_dialog.setWindowTitle("Aktivasi OTP Pertama")
            qr_dialog.setFixedSize(340, 420)
            qr_dialog.setStyleSheet("""
                QDialog {
                    background-color: #1e1e1e;
                    color: white;
                    border-radius: 10px;
                }
                QLabel { color: white; font-size: 11pt; }
                QPushButton {
                    background-color: #ff6600;
                    color: white;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 6px;
                }
                QPushButton:hover { background-color: #ff8533; }
            """)

            vbox = QVBoxLayout(qr_dialog)
            lbl = QLabel("Scan QR berikut di aplikasi Authenticator Anda:")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            vbox.addWidget(lbl)

            img = QLabel()
            img.setPixmap(pixmap.scaled(260, 260, Qt.AspectRatioMode.KeepAspectRatio))
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(img)

            lbl2 = QLabel(f"Atau masukkan kode manual:\n<b>{otp_secret}</b>")
            lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl2.setStyleSheet("color:#ff9900; font-size:10pt;")
            vbox.addWidget(lbl2)

            ok_btn = QPushButton("Sudah Saya Scan")
            ok_btn.clicked.connect(qr_dialog.accept)
            vbox.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

            qr_dialog.exec()

        else:
            conn.close()

        # ============================================================
        # 2️⃣ Verifikasi OTP Modern
        # ============================================================
        otp_dialog = QDialog(self)
        otp_dialog.setWindowTitle("Verifikasi OTP")
        otp_dialog.setFixedSize(340, 220)
        otp_dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: white;
                border-radius: 10px;
            }
            QLabel { color: white; font-size: 12pt; }
            QLineEdit {
                border: 2px solid #555;
                border-radius: 6px;
                padding: 6px;
                font-size: 16pt;
                letter-spacing: 4px;
                background-color: #2b2b2b;
                color: #00ff99;
                qproperty-alignment: AlignCenter;
            }
            QPushButton {
                background-color: #ff6600;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #ff8533; }
        """)

        layout = QVBoxLayout(otp_dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        lbl = QLabel("Masukkan kode OTP dari aplikasi Authenticator Anda:")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        otp_input = QLineEdit()
        otp_input.setMaxLength(6)
        otp_input.setPlaceholderText("••••••")
        otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        otp_input.setEchoMode(QLineEdit.EchoMode.Normal)
        layout.addWidget(otp_input)

        btn_verify = QPushButton("Verifikasi")
        btn_verify.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_verify)

        def do_verify():
            import pyotp # type: ignore
            code = otp_input.text().strip()
            if not code:
                show_modern_warning(otp_dialog, "Error", "Kode OTP belum diisi.")
                return
            totp = pyotp.TOTP(otp_secret)
            if not totp.verify(code):
                show_modern_error(otp_dialog, "Gagal", "Kode OTP salah atau sudah kedaluwarsa!")
                return
            otp_dialog.accept()

        btn_verify.clicked.connect(do_verify)

        if otp_dialog.exec() == QDialog.DialogCode.Accepted:
            self.accept_login(nama, kecamatan, desa, tahapan)
            
    # Konfirmasi Pembuatan akun
    def konfirmasi_buat_akun(self):
        # 🔹 Dialog konfirmasi modern
        if not show_modern_question(
            self,
            "Konfirmasi",
            "Apakah Anda yakin ingin membuat akun baru?<br>"
            "Seluruh data lama akan <b>dihapus permanen</b>!"
        ):
            show_modern_info(self, "Dibatalkan", "Proses pembuatan akun dibatalkan.")
            return

        # 🔹 Input kode konfirmasi (password style)
        dlg = ModernInputDialog("Kode Konfirmasi", "Masukkan kode konfirmasi:", self, is_password=True)
        kode, ok = dlg.getText()
        if not ok:
            return

        if kode.strip() != "KabTasik3206":
            show_modern_warning(self, "Salah", "Kode konfirmasi salah. Proses dibatalkan.")
            return

        # ✅ Kode benar → hapus semua data lama
        hapus_semua_data()

        # ✅ Tampilkan form RegisterWindow sebagai window utama
        self.register_window = RegisterWindow(None)
        self.register_window.show()

        # ✅ Tutup login window setelah register window muncul
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
                show_modern_error(self, "Error", f"Gagal membuat database terenkripsi:\n{e}")
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
        self.showFullScreen()  # ✅ Fullscreen
        self.setStyleSheet("""
            QWidget {
                font-family: Calibri;
                font-size: 11pt;
                background-color: #121212;
                color: white;
            }
            QLineEdit, QComboBox {
                min-height: 32px;
                border-radius: 6px;
                border: 1px solid #555;
                padding-left: 8px;
                background-color: #1e1e1e;
            }
            QPushButton {
                min-height: 34px;
                border-radius: 6px;
                background-color: #ff6600;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff8533;
            }
        """)

        # ====== MAIN LAYOUT ======
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(12)
        center_layout.setContentsMargins(480, 60, 480, 60)  # proporsional tengah

        # ====== ISIAN FORM ======
        title = QLabel("✨ Buat Akun Baru ✨")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:20pt; font-weight:bold; color:#ff9900; margin-bottom:20px;")
        center_layout.addWidget(title)

        # Nama Lengkap
        self.nama = QLineEdit()
        self.nama.setPlaceholderText("Nama Lengkap")
        self.nama.textChanged.connect(lambda t: self.nama.setText(t.upper()) if t != t.upper() else None)
        center_layout.addWidget(self.nama)

        # Email
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email Aktif")
        center_layout.addWidget(self.email)

        # Kecamatan
        self.kecamatan = QLineEdit()
        self.kecamatan.setPlaceholderText("Ketik Kecamatan...")
        kec_list = get_kecamatan()
        completer = QCompleter(kec_list, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.kecamatan.setCompleter(completer)
        self.kecamatan.textChanged.connect(self.update_desa)
        center_layout.addWidget(self.kecamatan)

        # Desa
        self.desa = QComboBox()
        self.desa.addItem("-- Pilih Desa --")
        center_layout.addWidget(self.desa)

        # Password dan Konfirmasi
        for field, placeholder in [(1, "Password"), (2, "Tulis Ulang Password")]:
            layout = QHBoxLayout()
            pw = QLineEdit()
            pw.setPlaceholderText(placeholder)
            pw.setEchoMode(QLineEdit.EchoMode.Password)
            toggle = QPushButton("👁")
            toggle.setFixedWidth(40)
            toggle.clicked.connect(lambda _, f=pw: self.toggle_password(f))
            layout.addWidget(pw)
            layout.addWidget(toggle)
            center_layout.addLayout(layout)
            if field == 1:
                self.password = pw
            else:
                self.password2 = pw

        # Captcha
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
        center_layout.addLayout(captcha_layout)

        self.captcha_input = QLineEdit()
        self.captcha_input.setPlaceholderText("Tulis ulang captcha di atas")
        center_layout.addWidget(self.captcha_input)

        # Tombol Buat Akun
        self.btn_buat = QPushButton("Buat Akun")
        self.btn_buat.clicked.connect(self.create_account)
        center_layout.addWidget(self.btn_buat)

        outer_layout.addWidget(center_widget, alignment=Qt.AlignmentFlag.AlignCenter)

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
            show_modern_warning(self, "Error", "Semua kolom harus diisi!")
            return

        if "@" not in email or "." not in email:
            show_modern_warning(self, "Error", "Format email tidak valid!")
            return

        if pw != pw2:
            show_modern_warning(self, "Error", "Password tidak sama!")
            return

        import re
        if len(pw) < 8 or not re.search(r"[A-Z]", pw) or not re.search(r"[0-9]", pw) or not re.search(r"[^A-Za-z0-9]", pw):
            show_modern_warning(
                self,
                "Error",
                "Password harus minimal 8 karakter dan memuat minimal:\n"
                "- 1 huruf kapital\n- 1 angka\n- 1 karakter khusus (!@#$%^&*)"
            )
            return

        if captcha != self.captcha_code:
            show_modern_warning(self, "Error", "Captcha salah! Coba lagi.")
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
        
        # === Buat secret OTP unik ===
        otp_secret = pyotp.random_base32()
        cur.execute("DELETE FROM users")  # hanya 1 akun aktif
        cur.execute("INSERT INTO users (nama, email, kecamatan, desa, password, otp_secret) VALUES (?, ?, ?, ?, ?, ?)",
                    (nama, email, kecamatan, desa, pw, otp_secret))

        conn.commit()
        conn.close()

        # === Generate QR Code ===
        totp_uri = pyotp.totp.TOTP(otp_secret).provisioning_uri(name=email, issuer_name="NexVo Sidalih Pilkada 2024")
        qr = qrcode.make(totp_uri)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())

        # === Tampilkan QR Code Modern Adaptif ===
        qr_dialog = QDialog(self)
        qr_dialog.setWindowTitle("Aktivasi OTP")
        qr_dialog.setFixedSize(480, 620)
        qr_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        # Deteksi tema dari latar utama (dark/light)
        bg_is_dark = True
        if hasattr(self, "palette"):
            bg_color = self.palette().color(self.backgroundRole()).lightness()
            bg_is_dark = bg_color < 128  # nilai <128 dianggap gelap

        bg_color = "#111" if bg_is_dark else "#f7f7f7"
        text_color = "white" if bg_is_dark else "#222"
        accent_color = "#ff6600" if bg_is_dark else "#d35400"
        qr_frame_color = "#000" if bg_is_dark else "#fff"

        qr_dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 16px;
                border: 1px solid {'#444' if bg_is_dark else '#ccc'};
            }}
            QLabel {{
                font-family: 'Segoe UI';
            }}
            QPushButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: #ff8533;
            }}
        """)

        vbox = QVBoxLayout(qr_dialog)
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(18)
        vbox.setContentsMargins(40, 36, 40, 36)

        # === Header ===
        title_lbl = QLabel("🔐 <b>Aktivasi Keamanan OTP</b>")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(f"font-size:15pt; color:{'#ffcc66' if bg_is_dark else '#c47c00'}; margin-bottom:12px;")
        vbox.addWidget(title_lbl)

        lbl = QLabel("Scan kode QR di bawah menggunakan aplikasi <b>Google Authenticator</b> atau <b>Authy</b>.")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"font-size:11pt; color:{'#dddddd' if bg_is_dark else '#333'}; margin-bottom:10px;")
        vbox.addWidget(lbl)

        # === QR Code persegi proporsional ===
        img = QLabel()
        pixmap_scaled = pixmap.scaled(
            240, 240,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        img.setPixmap(pixmap_scaled)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet(f"background-color: {qr_frame_color}; border-radius: 10px; padding: 10px; margin: 12px;")
        vbox.addWidget(img)

        # === Label kode manual (wrap penuh) ===
        lbl2 = QLabel(
            f"<i>Atau masukkan kode berikut secara manual di aplikasi Anda:</i><br><b>{otp_secret}</b>"
        )
        lbl2.setWordWrap(True)
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl2.setStyleSheet(f"color:{'#00ff99' if bg_is_dark else '#008040'}; font-size:11pt; margin-top:16px;")
        vbox.addWidget(lbl2)

        # === Tombol konfirmasi besar ===
        ok_btn = QPushButton("✅ Saya Sudah Scan")
        ok_btn.setFixedWidth(260)
        ok_btn.setFixedHeight(46)
        ok_btn.clicked.connect(qr_dialog.accept)
        vbox.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # === Center di layar ===
        screen_geo = QApplication.primaryScreen().geometry()
        qr_dialog.move(screen_geo.center() - qr_dialog.rect().center())

        qr_dialog.exec()

        dlg = ModernMessage("Sukses", "Akun berhasil dibuat!", "success")
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
#if __name__ == "__main__":
#   app = QApplication(sys.argv)
#   login = LoginWindow()
#   login.show()
#   sys.exit(app.exec())

# =====================================================
# Main
# =====================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Baca environment variable 'APP_MODE'.
    # Jika tidak ditemukan, defaultnya adalah 'production' untuk keamanan.
    app_mode = os.getenv('APP_MODE', 'production')

    if app_mode == 'development':
        # --- MODE PENGEMBANG AKTIF ---
        print("================================================")
        print("== 🚀 MENJALANKAN DALAM MODE PENGEMBANG ...  ==")
        print("==      Login dan OTP akan dilewati.      ==")
        print("================================================")

        # Data tiruan (mock data) untuk testing, sesuaikan jika perlu
        mock_username = "DEVELOPER"
        mock_kecamatan = "KECAMATAN_TEST"
        mock_desa = "DESA_TEST"
        mock_tahapan = "DPHP"  # Pilih salah satu: DPHP, DPSHP, atau DPSHPA
        
        # Logika ini meniru `accept_login` untuk menentukan nama database
        mock_db_name = os.path.join(BASE_DIR, f"{mock_tahapan}.db")

        # Langsung buat dan tampilkan MainWindow
        main_window = MainWindow(
            username=mock_username,
            kecamatan=mock_kecamatan,
            desa=mock_desa,
            db_name=mock_db_name,
            tahapan=mock_tahapan
        )
        main_window.show()
    else:
        # --- MODE NORMAL (LOGIN) ---
        # Kode ini akan berjalan jika APP_MODE bukan 'development'
        login = LoginWindow()
        login.show()

    sys.exit(app.exec())