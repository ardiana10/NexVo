import sys, sqlite3, csv, os, atexit, base64, random, string, pyotp, qrcode # type: ignore
from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QMessageBox, QMainWindow, QTableWidget, QTableWidgetItem,
    QToolBar, QStatusBar, QCompleter, QSizePolicy,
    QFileDialog, QHBoxLayout, QDialog, QCheckBox, QScrollArea, QHeaderView,
    QStyledItemDelegate, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QFrame, QMenu, QTableWidgetSelectionRange,
    QFormLayout, QSlider, QRadioButton, QDockWidget, QGridLayout, QStyle, QStyleOptionButton
)
from PyQt6.QtGui import QAction, QPainter, QColor, QPen, QPixmap, QFont, QIcon
from PyQt6.QtCore import Qt, QTimer, QRect, QPropertyAnimation, QSize, QPoint
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
# Utility function untuk proteksi dropdown
# =====================================================
def protect_combobox_from_scroll(combobox):
    """Mencegah dropdown berubah nilai dengan scroll wheel atau keyboard tanpa diklik dulu."""
    
    def wheelEvent(event):
        if not combobox.view().isVisible():
            event.ignore()
            return
        # Jika dropdown terbuka, gunakan behavior default
        QComboBox.wheelEvent(combobox, event)
    
    def keyPressEvent(event):
        if not combobox.view().isVisible():
            # Hanya izinkan Enter, Space, atau arrow down untuk membuka dropdown
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Down):
                combobox.showPopup()
            event.ignore()
            return
        # Jika dropdown terbuka, gunakan behavior default
        QComboBox.keyPressEvent(combobox, event)
    
    # Override methods
    combobox.wheelEvent = wheelEvent
    combobox.keyPressEvent = keyPressEvent

# =====================================================
# Delegate untuk kolom checkbox di tabel (hilang -> ditambahkan kembali)
class CheckboxDelegate(QStyledItemDelegate):
    def __init__(self, theme="dark", parent=None):
        super().__init__(parent)
        self.theme = theme

    def setTheme(self, theme):
        self.theme = theme

    def paint(self, painter, option, index):  # type: ignore
        value = index.data(Qt.ItemDataRole.CheckStateRole)
        if value is not None:
            # Hitung rect checkbox custom (14px square)
            size = 14
            x = option.rect.x() + (option.rect.width() - size) // 2
            y = option.rect.y() + (option.rect.height() - size) // 2
            rect = QRect(x, y, size, size)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Border & background
            if self.theme == "dark":
                border_color = QColor("#777")
                bg_unchecked = QColor(0, 0, 0, 0)
            else:
                border_color = QColor("#999")
                bg_unchecked = QColor(0, 0, 0, 0)
            if value == Qt.CheckState.Checked:
                painter.setBrush(QColor("#ff9900"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect, 3, 3)
                # Centang
                pen = QPen(QColor("white"), 1.8)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(rect.left() + 3, rect.center().y(), rect.center().x(), rect.bottom() - 3)
                painter.drawLine(rect.center().x(), rect.bottom() - 3, rect.right() - 3, rect.top() + 3)
            else:
                painter.setBrush(bg_unchecked)
                pen = QPen(border_color, 1)
                painter.setPen(pen)
                painter.drawRoundedRect(rect, 3, 3)
            painter.restore()
            return
        super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):  # type: ignore
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable) or not (index.flags() & Qt.ItemFlag.ItemIsEnabled):
            return False
        if event.type() == event.Type.MouseButtonRelease:
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            new_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
            model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
            return True
        return False

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
        self.theme = "dark"
        self.setStyleSheet(
            "QComboBox { padding-right: 22px; }"
            "QComboBox::down-arrow { image: none; }"
            "QComboBox::drop-down { width: 0px; border: none; }"
        )
        self._max_popup_width = 500
        # Force always downward popup as requested
        self._popup_direction_mode = 'down'

    def setPopupDirection(self, mode: str):
        if mode in ("down", "up", "auto"):
            self._popup_direction_mode = mode

    def showPopup(self):  # type: ignore
        view = self.view()
        if view is None:
            super().showPopup()
            return
        try:
            fm = view.fontMetrics()
            max_text_width = max((fm.horizontalAdvance(self.itemText(i)) for i in range(self.count())), default=0)
            padding = 56  # beri ruang lebih supaya tidak cepat terpotong
            popup_width = max(self.width(), min(max_text_width + padding, self._max_popup_width))
        except Exception:
            popup_width = self.width()
        super().showPopup()
        try:
            # Hilangkan elide agar teks panjang tidak jadi 'Sens...'
            try:
                view.setTextElideMode(Qt.TextElideMode.ElideNone)  # type: ignore
            except Exception:
                pass
            view.setMinimumWidth(int(popup_width))
            view.setMaximumWidth(int(max(popup_width, self.width())))
        except Exception:
            pass
        # Do NOT reposition upward when mode is 'down'
        if self._popup_direction_mode != 'down':
            try:
                combo_rect = self.rect()
                below_point = self.mapToGlobal(combo_rect.bottomLeft())
                above_point = self.mapToGlobal(combo_rect.topLeft())
                screen = QApplication.screenAt(self.mapToGlobal(self.rect().center())) or QApplication.primaryScreen()
                if not screen:
                    return
                avail = screen.availableGeometry()
                row_height = view.sizeHintForRow(0) if self.count() > 0 else 18
                visible_items = min(self.count(), self.maxVisibleItems()) if self.maxVisibleItems() > 0 else min(self.count(), 12)
                popup_height = (row_height * visible_items) + 8
                space_below = avail.bottom() - below_point.y()
                space_above = above_point.y() - avail.top()
                move_up = False
                if self._popup_direction_mode == 'up':
                    move_up = space_above >= popup_height
                elif self._popup_direction_mode == 'auto':
                    if space_below < popup_height and space_above > space_below:
                        move_up = True
                if move_up:
                    geo = view.geometry()
                    new_top = above_point.y() - geo.height()
                    if new_top < avail.top():
                        new_top = avail.top()
                    geo.moveTop(new_top)
                    view.setGeometry(geo)
            except Exception:
                pass

    def setTheme(self, theme):
        self.theme = theme
        self.update()

    def wheelEvent(self, event):
        if not self.view().isVisible():
            event.ignore()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if not self.view().isVisible():
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Down):
                self.showPopup()
            event.ignore()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        arrow_size = 5
        center_x = rect.width() - 14
        center_y = rect.height() // 2
        color = "#d4d4d4" if self.theme == "dark" else "#333"
        pen = QPen(QColor(color), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(center_x - arrow_size, center_y - (arrow_size // 2), center_x, center_y + (arrow_size // 2))
        painter.drawLine(center_x, center_y + (arrow_size // 2), center_x + arrow_size, center_y - (arrow_size // 2))
        painter.end()

# =====================================================
# RangeSlider: Komponen Slider Ganda untuk Rentang Umur
# =====================================================
class RangeSlider(QWidget):
    """
    Widget slider dengan dua handle untuk memilih rentang nilai (min-max).
    
    Dirancang khusus untuk filter rentang umur dengan antarmuka yang intuitif:
    - Dua handle yang dapat digeser untuk menentukan nilai minimum dan maksimum
    - Label yang muncul saat hover atau sedang aktif dengan animasi fade yang halus
    - Efek visual modern dengan glow effect saat handle aktif
    - Persistent state untuk menjaga handle tetap aktif setelah diklik
    - Animasi smooth untuk pergerakan handle dan transisi visual
    
    Fitur Interaksi:
    - Hover: Label muncul dan handle berubah warna
    - Click: Handle menjadi persistent (tetap aktif) sampai handle lain diklik
    - Drag: Geser handle untuk mengubah nilai dengan animasi smooth
    - Keyboard: Arrow keys dengan Shift untuk handle kiri, tanpa Shift untuk handle kanan
    """
    
    def __init__(self, minimum=0, maximum=100, parent=None):
        """
        Inisialisasi RangeSlider dengan rentang nilai tertentu.
        
        Args:
            minimum (int): Nilai minimum slider (default: 0)
            maximum (int): Nilai maksimum slider (default: 100)
            parent (QWidget): Widget parent
        """
        super().__init__(parent)
        
        # === Pengaturan Nilai Rentang ===
        self._min = minimum
        self._max = maximum
        self._lower = minimum  # Nilai handle kiri (minimum yang dipilih)
        self._upper = maximum  # Nilai handle kanan (maksimum yang dipilih)
        
        # === Pengaturan Visual ===
        self._bar_height = 4      # Tinggi track slider
        self._handle_radius = 7   # Radius handle (diperkecil untuk tampilan compact)
        
        # === State Management ===
        self._active_handle = None  # Handle yang sedang di-drag ('lower'/'upper'/None)
        self._hover_lower = False   # Apakah mouse hover di handle kiri
        self._hover_upper = False   # Apakah mouse hover di handle kanan
        self._hover_track = False   # Apakah mouse hover di area track
        self._hover_active_track = False  # Apakah mouse hover di area selection
        
        # Persistent states - handle tetap aktif setelah diklik
        self._persistent_lower = False  # Handle kiri tetap aktif
        self._persistent_upper = False  # Handle kanan tetap aktif
        
        # === Sistem Animasi untuk Pergerakan Handle ===
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._update_handle_animation)
        self._animation_timer.setInterval(16)  # 60 FPS untuk animasi yang smooth
        
        # Target values untuk smooth dragging
        self._target_lower = minimum
        self._target_upper = maximum
        self._animation_speed = 0.18  # Kecepatan animasi (0.18 untuk gerakan halus)
        
        # === Sistem Animasi untuk Label Fade Effect ===
        self._label_fade_timer = QTimer(self)
        self._label_fade_timer.timeout.connect(self._update_label_fade)
        self._label_fade_timer.setInterval(25)  # 40 FPS untuk balance smooth dan performa
        
        # Opacity values untuk fade effect label
        self._label_opacity = {'lower': 0.0, 'upper': 0.0}     # Opacity saat ini
        self._target_opacity = {'lower': 0.0, 'upper': 0.0}    # Target opacity
        
        # === Pengaturan Widget ===
        self.setMouseTracking(True)  # Untuk mendeteksi hover tanpa click
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Untuk keyboard input
        
        # === Tema dan Warna ===
        self._dark_theme = False
        self._accent_color = QColor('#ff9900')  # Warna accent orange
        
        # Tinggi widget dengan ruang untuk label di atas
        self.setFixedHeight(self._handle_radius * 2 + 50)

    def sizeHint(self):
        """Memberikan ukuran yang disarankan untuk widget."""
        return QSize(160, self._handle_radius * 2 + 10)

    def setDark(self, dark_mode: bool):
        """
        Mengatur tema tampilan slider.
        
        Args:
            dark_mode (bool): True untuk tema gelap, False untuk tema terang
        """
        self._dark_theme = dark_mode
        self.update()

    def setRange(self, minimum, maximum):
        """
        Mengatur rentang nilai slider.
        
        Args:
            minimum (int): Nilai minimum baru
            maximum (int): Nilai maksimum baru
        """
        self._min, self._max = minimum, maximum
        
        # Pastikan nilai saat ini masih dalam rentang yang valid
        self._lower = max(self._min, min(self._lower, self._max))
        self._upper = max(self._min, min(self._upper, self._max))
        
        # Pastikan lower tidak lebih besar dari upper
        if self._lower > self._upper:
            self._lower, self._upper = self._upper, self._lower
            
        self.update()

    # === Getter Methods ===
    def lowerValue(self):
        """Mendapatkan nilai handle kiri (minimum)."""
        return self._lower
        
    def upperValue(self):
        """Mendapatkan nilai handle kanan (maksimum)."""
        return self._upper
        
    def values(self):
        """Mendapatkan kedua nilai sebagai tuple (lower, upper)."""
        return self._lower, self._upper

    def setValues(self, lower_val, upper_val):
        """
        Mengatur kedua nilai slider sekaligus dengan animasi smooth.
        
        Args:
            lower_val (int): Nilai baru untuk handle kiri
            upper_val (int): Nilai baru untuk handle kanan
        """
        # Pastikan nilai dalam rentang yang valid
        self._target_lower = max(self._min, min(lower_val, upper_val))
        self._target_upper = min(self._max, max(upper_val, self._target_lower))
        
        # Jika animasi belum diinisialisasi, langsung set nilai
        if not hasattr(self, '_animation_timer'):
            self._lower = self._target_lower
            self._upper = self._target_upper
        else:
            # Mulai animasi smooth
            self._animation_timer.start()
            
        self.update()
        self._emit_value_changed()

    def _update_handle_animation(self):
        """
        Update animasi smooth untuk pergerakan handle.
        
        Menggunakan interpolasi linear untuk transisi yang halus dari nilai
        saat ini ke nilai target. Animasi berhenti ketika handle sudah
        mencapai posisi target.
        """
        animation_active = False
        
        # Smooth interpolation untuk handle kiri
        lower_difference = self._target_lower - self._lower
        if abs(lower_difference) > 0.1:
            self._lower += lower_difference * self._animation_speed
            animation_active = True
        else:
            self._lower = self._target_lower
            
        # Smooth interpolation untuk handle kanan
        upper_difference = self._target_upper - self._upper
        if abs(upper_difference) > 0.1:
            self._upper += upper_difference * self._animation_speed
            animation_active = True
        else:
            self._upper = self._target_upper
            
        # Update tampilan jika masih ada perubahan
        if animation_active:
            self.update()
        else:
            # Hentikan timer jika animasi selesai
            self._animation_timer.stop()

    def _update_label_fade(self):
        """
        Update animasi fade in/out untuk label nilai.
        
        Label akan muncul dengan fade in saat hover atau handle aktif,
        dan fade out saat tidak ada interaksi. Kecepatan fade disesuaikan
        untuk memberikan feedback yang responsif namun tidak mengganggu.
        """
        animation_active = False
        fade_speed = 0.25  # Kecepatan fade yang seimbang
        
        for handle_type in ['lower', 'upper']:
            opacity_difference = self._target_opacity[handle_type] - self._label_opacity[handle_type]
            
            if abs(opacity_difference) > 0.01:
                self._label_opacity[handle_type] += opacity_difference * fade_speed
                animation_active = True
            else:
                self._label_opacity[handle_type] = self._target_opacity[handle_type]
                
        # Update tampilan jika masih ada perubahan opacity
        if animation_active:
            self.update()
        else:
            # Hentikan timer jika fade selesai
            self._label_fade_timer.stop()

    def _emit_value_changed(self):
        """
        Mengirim signal perubahan nilai ke parent widget.
        
        Mencoba memanggil method on_age_range_changed pada parent jika tersedia.
        Ini memungkinkan parent widget merespons perubahan nilai slider.
        """
        if hasattr(self.parent(), 'on_age_range_changed'):
            try:
                self.parent().on_age_range_changed(int(self._lower), int(self._upper))
            except Exception:
                # Abaikan error jika parent tidak dapat memproses callback
                pass

    def paintEvent(self, event):
        """
        Menggambar seluruh komponen slider termasuk track, selection, handle, dan label.
        
        Komponen yang digambar:
        1. Background track dengan efek hover
        2. Selection area (area antara dua handle)
        3. Handle kiri dan kanan dengan efek glow saat aktif
        4. Label nilai dengan fade effect dan bubble styling
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # === Kalkulasi Posisi dan Dimensi ===
        widget_width = self.width()
        widget_height = self.height()
        center_y = widget_height // 2 + 5  # Posisi vertikal track (sedikit ke bawah untuk ruang label)
        
        # Margin samping untuk menghindari handle terpotong
        side_margin = 8
        track_left = side_margin + self._handle_radius
        track_right = widget_width - (side_margin + self._handle_radius)
        
        # === Menggambar Background Track ===
        self._draw_background_track(painter, track_left, track_right, center_y)
        
        # === Menggambar Selection Area ===
        left_handle_x = self._value_to_x_position(self._lower, track_left, track_right)
        right_handle_x = self._value_to_x_position(self._upper, track_left, track_right)
        self._draw_selection_area(painter, left_handle_x, right_handle_x, center_y)
        
        # === Menggambar Handle dan Label ===
        self._draw_handle_and_label(painter, 'lower', left_handle_x, center_y)
        self._draw_handle_and_label(painter, 'upper', right_handle_x, center_y)
        
        painter.end()

    def _draw_background_track(self, painter, left, right, center_y):
        """
        Menggambar track latar belakang dengan efek hover.
        
        Args:
            painter (QPainter): Object painter untuk menggambar
            left (int): Posisi x kiri track
            right (int): Posisi x kanan track  
            center_y (int): Posisi y tengah track
        """
        # Tentukan warna track berdasarkan state hover dan tema
        if self._hover_track:
            # Warna lebih terang saat hover
            if self._dark_theme:
                track_color = QColor('#444')  # Lebih terang dari default gelap
            else:
                track_color = QColor('#bbb')  # Lebih gelap dari default terang
        else:
            # Warna default
            track_color = QColor('#333') if self._dark_theme else QColor('#dcdcdc')
        
        # Gambar track sebagai rounded rectangle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        
        track_rect = QRect(left, center_y - self._bar_height // 2, 
                          right - left, self._bar_height)
        painter.drawRoundedRect(track_rect, 2, 2)

    def _draw_selection_area(self, painter, left_x, right_x, center_y):
        """
        Menggambar area selection (antara dua handle) dengan efek hover.
        
        Args:
            painter (QPainter): Object painter untuk menggambar
            left_x (float): Posisi x handle kiri
            right_x (float): Posisi x handle kanan
            center_y (int): Posisi y tengah track
        """
        selection_rect = QRect(int(left_x), center_y - self._bar_height // 2, 
                              int(right_x - left_x), self._bar_height)
        
        # Warna selection berdasarkan hover state
        if self._hover_active_track:
            # Efek hover: accent color dengan transparansi
            hover_accent = QColor(self._accent_color)
            hover_accent.setAlpha(180)  # Sedikit transparan untuk efek hover
            painter.setBrush(hover_accent)
        else:
            # Warna normal
            painter.setBrush(self._accent_color)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(selection_rect, 2, 2)

    def _draw_handle_and_label(self, painter, handle_type, x_position, center_y):
        """
        Menggambar handle dan label untuk satu handle (kiri atau kanan).
        
        Args:
            painter (QPainter): Object painter untuk menggambar
            handle_type (str): Tipe handle ('lower' atau 'upper')
            x_position (float): Posisi x handle
            center_y (int): Posisi y tengah handle
        """
        # Tentukan state handle
        is_hover = (handle_type == 'lower' and self._hover_lower) or \
                   (handle_type == 'upper' and self._hover_upper)
        is_pressed = self._active_handle == handle_type
        is_persistent = (handle_type == 'lower' and self._persistent_lower) or \
                       (handle_type == 'upper' and self._persistent_upper)
        
        is_active = is_hover or is_pressed or is_persistent
        
        # === Gambar Glow Effect untuk Handle Aktif ===
        if is_pressed or is_persistent:
            self._draw_glow_effect(painter, x_position, center_y)
        
        # === Gambar Handle ===
        self._draw_handle_circle(painter, x_position, center_y, is_active)
        
        # === Gambar Label dengan Fade Effect ===
        self._draw_handle_label(painter, handle_type, x_position, center_y, is_active)

    def _draw_glow_effect(self, painter, x_position, center_y):
        """
        Menggambar efek glow di sekitar handle yang aktif.
        
        Args:
            painter (QPainter): Object painter untuk menggambar
            x_position (float): Posisi x pusat glow
            center_y (int): Posisi y pusat glow
        """
        from PyQt6.QtGui import QRadialGradient
        
        glow_color = QColor('#ff9900')  # Warna orange sesuai accent
        
        # Layer 1: Glow luar (efek lebih lembut)
        outer_radius = self._handle_radius + 8
        outer_rect = QRect(int(x_position - outer_radius), int(center_y - outer_radius), 
                          2 * outer_radius, 2 * outer_radius)
        
        outer_gradient = QRadialGradient(x_position, center_y, outer_radius)
        outer_gradient.setColorAt(0.0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 0))
        outer_gradient.setColorAt(0.8, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 40))
        outer_gradient.setColorAt(1.0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 0))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(outer_gradient)
        painter.drawEllipse(outer_rect)
        
        # Layer 2: Glow dalam (efek lebih terang dan tajam)
        inner_radius = self._handle_radius + 4
        inner_rect = QRect(int(x_position - inner_radius), int(center_y - inner_radius), 
                          2 * inner_radius, 2 * inner_radius)
        
        inner_gradient = QRadialGradient(x_position, center_y, inner_radius)
        inner_gradient.setColorAt(0.0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 0))
        inner_gradient.setColorAt(0.7, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 80))
        inner_gradient.setColorAt(1.0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 0))
        
        painter.setBrush(inner_gradient)
        painter.drawEllipse(inner_rect)

    def _draw_handle_circle(self, painter, x_position, center_y, is_active):
        """
        Menggambar lingkaran handle dengan styling yang sesuai state.
        
        Args:
            painter (QPainter): Object painter untuk menggambar
            x_position (float): Posisi x pusat handle
            center_y (int): Posisi y pusat handle
            is_active (bool): Apakah handle dalam state aktif
        """
        # Tentukan warna berdasarkan tema dan state
        if self._dark_theme:
            face_color = QColor('#3a3a3a') if is_active else QColor('#2a2a2a')
        else:
            face_color = QColor('#f8f8f8') if is_active else QColor('#ffffff')
            
        border_color = QColor('#ff9900')  # Selalu orange untuk konsistensi
        
        # Gambar handle dengan border
        painter.setBrush(face_color)
        
        border_pen = QPen(border_color)
        border_pen.setWidth(2)  # Border selalu tebal untuk visibility
        painter.setPen(border_pen)
        
        handle_rect = QRect(int(x_position - self._handle_radius), 
                           int(center_y - self._handle_radius),
                           2 * self._handle_radius, 2 * self._handle_radius)
        painter.drawEllipse(handle_rect)
        
        # Titik tengah untuk grip visual saat aktif
        if is_active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(border_color)
            center_dot = QRect(int(x_position - 2), int(center_y - 2), 4, 4)
            painter.drawEllipse(center_dot)

    def _draw_handle_label(self, painter, handle_type, x_position, center_y, is_active):
        """
        Menggambar label nilai handle dengan bubble styling dan fade effect.
        
        Args:
            painter (QPainter): Object painter untuk menggambar
            handle_type (str): Tipe handle ('lower' atau 'upper')
            x_position (float): Posisi x handle
            center_y (int): Posisi y handle
            is_active (bool): Apakah handle dalam state aktif
        """
        opacity = self._label_opacity.get(handle_type, 0.0)
        should_show_label = is_active or opacity > 0.01
        
        if not should_show_label or opacity <= 0.01:
            return
            
        # Dapatkan nilai untuk ditampilkan
        value = int(self._lower) if handle_type == 'lower' else int(self._upper)
        label_text = str(value)
        
        # Setup font
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        
        # Kalkulasi dimensi bubble
        font_metrics = painter.fontMetrics()
        padding_horizontal = 8
        padding_vertical = 4
        text_width = font_metrics.horizontalAdvance(label_text) + padding_horizontal
        text_height = font_metrics.height() + padding_vertical
        
        # Posisi label di atas handle
        distance_from_center = 35 if (is_active and self._active_handle == handle_type) else 25
        label_top_y = int(center_y - distance_from_center - text_height)
        
        # Pastikan label tidak keluar dari area widget
        if label_top_y < 2:
            label_top_y = 2
            
        bubble_rect = QRect(int(x_position - text_width / 2), label_top_y, 
                           int(text_width), int(text_height))
        
        # Alpha untuk fade effect
        alpha = int(240 * opacity)
        
        # Gambar bubble background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(60, 60, 60, alpha))  # Dark background dengan alpha
        painter.drawRoundedRect(bubble_rect, 4, 4)
        
        # Gambar segitiga pointer
        self._draw_label_pointer(painter, x_position, label_top_y + text_height, alpha)
        
        # Gambar teks
        text_alpha = int(255 * opacity)
        painter.setPen(QColor(255, 255, 255, text_alpha))  # White text dengan alpha
        painter.drawText(bubble_rect, Qt.AlignmentFlag.AlignCenter, label_text)

    def _draw_label_pointer(self, painter, x_position, bottom_y, alpha):
        """
        Menggambar segitiga pointer di bawah bubble label.
        
        Args:
            painter (QPainter): Object painter untuk menggambar
            x_position (float): Posisi x pusat segitiga
            bottom_y (int): Posisi y dasar bubble
            alpha (int): Nilai alpha untuk transparansi
        """
        from PyQt6.QtGui import QPolygon
        from PyQt6.QtCore import QPoint
        
        triangle_size = 4
        triangle_tip_x = int(x_position)
        
        triangle = QPolygon([
            QPoint(triangle_tip_x - triangle_size, bottom_y),
            QPoint(triangle_tip_x + triangle_size, bottom_y), 
            QPoint(triangle_tip_x, bottom_y + triangle_size)
        ])
        
        painter.setBrush(QColor(60, 60, 60, alpha))
        painter.drawPolygon(triangle)

    def _value_to_x_position(self, value, left_bound, right_bound):
        """
        Konversi nilai slider ke posisi x pada widget.
        
        Args:
            value (float): Nilai yang akan dikonversi
            left_bound (int): Batas kiri area track
            right_bound (int): Batas kanan area track
            
        Returns:
            float: Posisi x yang sesuai dengan nilai
        """
        if self._max == self._min:
            return left_bound
        
        ratio = (value - self._min) / (self._max - self._min)
        return left_bound + ratio * (right_bound - left_bound)

    def _x_position_to_value(self, x_position, left_bound, right_bound):
        """
        Konversi posisi x pada widget ke nilai slider.
        
        Args:
            x_position (float): Posisi x yang akan dikonversi
            left_bound (int): Batas kiri area track
            right_bound (int): Batas kanan area track
            
        Returns:
            int: Nilai slider yang sesuai dengan posisi x
        """
        ratio = (x_position - left_bound) / (right_bound - left_bound)
        value = self._min + ratio * (self._max - self._min)
        return int(round(max(self._min, min(value, self._max))))

    def mousePressEvent(self, event):
        """
        Menangani event klik mouse untuk aktivasi dan toggle handle.
        
        Logika click:
        - Klik pada handle yang sudah persistent: matikan persistent state
        - Klik pada handle yang tidak persistent: aktifkan handle tersebut
        - Klik di area track: aktifkan handle terdekat dengan posisi klik
        - Klik di luar area: matikan semua persistent state
        """
        if event.button() != Qt.MouseButton.LeftButton:
            return
            
        # Kalkulasi area track
        left_bound = self._handle_radius
        right_bound = self.width() - self._handle_radius
        
        # Posisi handle saat ini
        left_handle_x = self._value_to_x_position(self._lower, left_bound, right_bound)
        right_handle_x = self._value_to_x_position(self._upper, left_bound, right_bound)
        
        mouse_x = event.position().x()
        mouse_y = event.position().y()
        
        # Toleransi untuk area klik handle
        click_tolerance = self._handle_radius + 4
        
        # Cek klik pada handle
        clicked_on_lower = abs(mouse_x - left_handle_x) <= click_tolerance
        clicked_on_upper = abs(mouse_x - right_handle_x) <= click_tolerance
        
        if clicked_on_lower:
            # Toggle persistent state untuk handle kiri
            if self._persistent_lower:
                self._persistent_lower = False
                self._active_handle = None
            else:
                self._active_handle = 'lower'
                self._persistent_upper = False  # Matikan handle lain
                
        elif clicked_on_upper:
            # Toggle persistent state untuk handle kanan
            if self._persistent_upper:
                self._persistent_upper = False
                self._active_handle = None
            else:
                self._active_handle = 'upper'
                self._persistent_lower = False  # Matikan handle lain
                
        else:
            # Klik di area track atau di luar
            center_y = self.height() // 2 + 5
            side_margin = 8
            track_left = side_margin + self._handle_radius
            track_right = self.width() - (side_margin + self._handle_radius)
            
            is_in_track = (track_left <= mouse_x <= track_right) and (abs(mouse_y - center_y) <= 15)
            
            if is_in_track:
                # Klik di area track - aktifkan handle terdekat
                self._persistent_lower = False
                self._persistent_upper = False
                
                # Tentukan handle terdekat
                if abs(mouse_x - left_handle_x) < abs(mouse_x - right_handle_x):
                    self._active_handle = 'lower'
                else:
                    self._active_handle = 'upper'
            else:
                # Klik di luar area - matikan semua persistent state
                self._persistent_lower = False
                self._persistent_upper = False
                self._active_handle = None
        
        # Mulai drag jika ada handle aktif
        if self._active_handle:
            self.mouseMoveEvent(event)
            
        self.update()

    def mouseMoveEvent(self, event):
        """
        Menangani event pergerakan mouse untuk hover effect dan dragging.
        
        Fitur:
        - Deteksi hover pada handle dan track untuk visual feedback
        - Smooth dragging dengan animasi
        - Update cursor sesuai area (pointing hand untuk handle, arrow untuk lainnya)
        - Kontrol fade in/out label berdasarkan interaksi
        """
        # Kalkulasi area dan posisi
        left_bound = self._handle_radius
        right_bound = self.width() - self._handle_radius
        left_handle_x = self._value_to_x_position(self._lower, left_bound, right_bound)
        right_handle_x = self._value_to_x_position(self._upper, left_bound, right_bound)
        
        mouse_x = event.position().x()
        mouse_y = event.position().y()
        
        # Reset hover states
        prev_hover_lower = self._hover_lower
        prev_hover_upper = self._hover_upper
        self._hover_lower = False
        self._hover_upper = False
        self._hover_track = False
        self._hover_active_track = False
        
        # Area hit yang diperluas untuk responsivitas lebih baik
        hit_radius = self._handle_radius + 6
        
        # Deteksi hover pada handle
        if abs(mouse_x - left_handle_x) <= hit_radius:
            self._hover_lower = True
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._target_opacity['lower'] = 1.0
            
            # Soft instant show untuk feedback responsif
            if self._label_opacity['lower'] < 0.3:
                self._label_opacity['lower'] = 0.4
                
        elif abs(mouse_x - right_handle_x) <= hit_radius:
            self._hover_upper = True
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._target_opacity['upper'] = 1.0
            
            # Soft instant show untuk feedback responsif
            if self._label_opacity['upper'] < 0.3:
                self._label_opacity['upper'] = 0.4
                
        else:
            # Deteksi hover pada track
            center_y = self.height() // 2 + 5
            side_margin = 8
            track_left = side_margin + self._handle_radius
            track_right = self.width() - (side_margin + self._handle_radius)
            
            if (track_left <= mouse_x <= track_right) and (abs(mouse_y - center_y) <= 20):
                self._hover_track = True
                self._hover_active_track = True
                self.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # Update target opacity untuk fade effect
        if not self._hover_lower and not (self._active_handle == 'lower') and not self._persistent_lower:
            self._target_opacity['lower'] = 0.0
        if not self._hover_upper and not (self._active_handle == 'upper') and not self._persistent_upper:
            self._target_opacity['upper'] = 0.0
            
        # Maintain opacity untuk persistent handles
        if self._persistent_lower:
            self._target_opacity['lower'] = 1.0
        if self._persistent_upper:
            self._target_opacity['upper'] = 1.0
            
        # Start fade animation jika ada perubahan hover state
        if (prev_hover_lower != self._hover_lower or prev_hover_upper != self._hover_upper):
            if not self._label_fade_timer.isActive():
                self._label_fade_timer.start()
        
        # Handle dragging dengan hover effect
        if self._active_handle:
            self._hover_track = True
            self._hover_active_track = True
            
            # Maintain label visibility saat drag
            if self._active_handle == 'lower':
                self._target_opacity['lower'] = 1.0
            elif self._active_handle == 'upper':
                self._target_opacity['upper'] = 1.0
        
        self.update()
        
        # Smooth dragging dengan precision yang diperbaiki
        if self._active_handle:
            new_value = self._x_position_to_value(mouse_x, left_bound, right_bound)
            
            if self._active_handle == 'lower': 
                clamped_value = min(new_value, self._upper)
                if abs(clamped_value - self._target_lower) > 0.3:  # Threshold untuk gerakan halus
                    self._target_lower = clamped_value
                    self._animation_timer.start()
            else: 
                clamped_value = max(new_value, self._lower)
                if abs(clamped_value - self._target_upper) > 0.3:
                    self._target_upper = clamped_value
                    self._animation_timer.start()
                    
            self._emit_value_changed()

    def mouseReleaseEvent(self, event): 
        """
        Menangani event pelepasan mouse untuk set persistent state.
        
        Setelah drag selesai, handle yang di-drag akan menjadi persistent
        (tetap aktif) sampai handle lain diklik atau area di luar diklik.
        """
        # Set persistent state berdasarkan handle yang sedang aktif
        if self._active_handle == 'lower':
            self._persistent_lower = True
            self._persistent_upper = False
            self._target_opacity['lower'] = 1.0  # Maintain label visibility
        elif self._active_handle == 'upper':
            self._persistent_upper = True
            self._persistent_lower = False
            self._target_opacity['upper'] = 1.0  # Maintain label visibility
            
        self._active_handle = None
        
        # Start fade animation untuk smooth transition
        if not self._label_fade_timer.isActive():
            self._label_fade_timer.start()
        
        self.update()
        
    def leaveEvent(self, event): 
        """
        Menangani event mouse meninggalkan widget.
        
        Reset semua hover states dan fade out label yang tidak persistent.
        """
        self._hover_lower = False
        self._hover_upper = False
        self._hover_track = False
        self._hover_active_track = False
        
        # Fade out labels kecuali yang persistent
        if not self._persistent_lower:
            self._target_opacity['lower'] = 0.0
        if not self._persistent_upper:
            self._target_opacity['upper'] = 0.0
            
        # Start fade animation
        if not self._label_fade_timer.isActive():
            self._label_fade_timer.start()
            
        self.setCursor(Qt.CursorShape.ArrowCursor)  # reset cursor saat meninggalkan widget
        self.update()
    def keyPressEvent(self, e):
        step = 1
        if e.key()==Qt.Key.Key_Left:
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier: self._lower=max(self._min,self._lower-step)
            else: self._upper=max(self._min,self._upper-step)
            self._emit(); self.update()
        elif e.key()==Qt.Key.Key_Right:
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier: self._lower=min(self._upper,self._lower+step)
            else: self._upper=min(self._max,self._upper+step)
            self._emit(); self.update()
        else: super().keyPressEvent(e)

# =====================================================
# Panel Filter Samping (dock kanan)
# =====================================================
class FilterSidebar(QWidget):
    """Panel filter sidebar yang memungkinkan pengguna melakukan pencarian
    dan penyaringan data dengan berbagai kriteria seperti tanggal, nama, 
    NIK, umur, dan parameter lainnya.
    
    Panel ini dirancang dengan lebar tetap dan dapat di-scroll untuk 
    menampung semua kontrol filter dengan rapi.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Konfigurasi dimensi dan spacing untuk tampilan yang rapi
        self._dock_width = 260  # Lebar dock harus selaras dengan FixedDockWidget
        gap = 6  # Jarak antar elemen yang pas - tidak terlalu rapat
        side_margin = 2  # Margin samping yang minimal namun tetap memberikan ruang
        
        # Setup container utama
        main_container_layout = QVBoxLayout(self)
        main_container_layout.setContentsMargins(0, 0, 0, 0)
        main_container_layout.setSpacing(0)
        
        # Buat area scroll untuk menampung semua kontrol filter
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget konten yang akan di-scroll
        scroll_content = QWidget()
        main_layout = QVBoxLayout(scroll_content)
        # Berikan margin yang cukup agar field tidak menempel ke sisi dock
        main_layout.setContentsMargins(side_margin, 10, side_margin, 10)
        main_layout.setSpacing(gap)
        
        # === Bagian Input Utama ===
        # Kelompok field input yang paling sering digunakan
        inputs_layout = QVBoxLayout()
        inputs_layout.setContentsMargins(0, 0, 0, 0)
        inputs_layout.setSpacing(gap)
        
        # Field Tanggal Update dengan date picker
        self._setup_date_filter(inputs_layout)
        
        # Field pencarian teks
        self._setup_text_fields(inputs_layout, gap)
        
        # Kontrol slider umur
        self._setup_age_slider(inputs_layout, gap)
        
        main_layout.addLayout(inputs_layout)
        
        # === Grid Dropdown ===
        # Kelompok dropdown untuk kategori data
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(gap)
        grid_layout.setVerticalSpacing(gap)
        
        self._setup_dropdown_grid(grid_layout)
        main_layout.addSpacing(gap)
        main_layout.addLayout(grid_layout)
        
        # === Checkbox Options ===
        # Opsi checkbox untuk filter tambahan
        checkbox_layout = QGridLayout()
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setHorizontalSpacing(gap)
        checkbox_layout.setVerticalSpacing(gap)
        
        self._setup_checkboxes(checkbox_layout)
        main_layout.addSpacing(gap)
        main_layout.addLayout(checkbox_layout)
        
        # === Radio Button Options ===
        # Pilihan tipe data (Reguler/Khusus)
        radio_layout = QHBoxLayout()
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(2)  # Spacing yang rapat untuk radio button
        
        self._setup_radio_buttons(radio_layout)
        main_layout.addSpacing(gap)
        main_layout.addLayout(radio_layout)
        
        # === Tombol Aksi ===
        # Tombol untuk reset dan apply filter
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 4)
        btn_layout.setSpacing(gap)
        
        self._setup_action_buttons(btn_layout)
        main_layout.addSpacing(gap)
        main_layout.addLayout(btn_layout)
        
        # Finalisasi setup
        scroll_area.setWidget(scroll_content)
        main_container_layout.addWidget(scroll_area)
        
        # Terapkan ukuran yang konsisten untuk semua input
        self._apply_consistent_sizing()
        
        # Terapkan lebar internal yang tepat
        self._apply_internal_widths(gap, side_margin)
    
    def _setup_date_filter(self, layout):
        """Setup field filter tanggal dengan compact popup date range picker."""
        self.tgl_update = QLineEdit()
        self.tgl_update.setPlaceholderText("Tanggal Update")
        self.tgl_update.setReadOnly(True)
        self.tgl_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tgl_update.setToolTip("Klik untuk memilih rentang tanggal")
        self.tgl_update.setStyleSheet(
            """
            QLineEdit {
                background:#2f2f2f; border:1px solid #444; border-radius:6px;
                padding:6px 10px; color:#eee; font-size:10pt;
            }
            QLineEdit:hover { border-color:#ff8800; }
            QLineEdit:focus { border-color:#ff8800; }
            """
        )

        layout.addWidget(self.tgl_update)

        # --- Popup Date Range Picker (compact) ---------------------------------
        class CompactDateRangePopup(QFrame):
            def __init__(self, parent_field: QLineEdit, theme_mode: str = "light"):
                super().__init__(parent_field)
                self.parent_field = parent_field
                self.theme_mode = theme_mode.lower()
                self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
                self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                self.setObjectName("CompactDateRangePopup")

                # --- Dynamic color palette based on theme ---
                accent = "#ff8800"
                if self.theme_mode == "dark":
                    bg = "#1e1e1e"
                    text = "#dddddd"
                    subtext = "#aaaaaa"
                    border = "#444444"
                    # Gunakan satu warna hover konsisten seperti preset
                    preset_hover_bg = "#252525"
                    hover_bg = preset_hover_bg
                    sel_bg = accent
                    sel_text = "#ffffff"
                    # Samakan range dengan gaya preset hover (tidak pakai tint khusus)
                    range_bg = preset_hover_bg
                    range_text = text
                    clear_color = "#bbbbbb"
                else:  # light
                    bg = "#ffffff"
                    text = "#222222"
                    subtext = "#555555"
                    border = "#d6d6d6"
                    # Satukan warna hover kalender dengan hover preset
                    preset_hover_bg = "#f7f7f7"
                    hover_bg = preset_hover_bg
                    sel_bg = accent
                    sel_text = "#ffffff"
                    # Range kini sama dengan hover preset agar konsisten
                    range_bg = preset_hover_bg
                    range_text = text
                    clear_color = "#666666"

                # Simpan warna penting untuk dipakai ulang (highlight preset & today)
                self.accent = accent
                self.sel_bg = sel_bg
                self.sel_text = sel_text
                self.text_color = text
                self.subtext_color = subtext

                self.setStyleSheet(f"""
                    QFrame#CompactDateRangePopup {{ background:{bg}; border:1px solid {border}; border-radius:8px; }}
                    QFrame#PresetItem {{ background:{bg}; border-radius:4px; }}
                    QFrame#PresetItem:hover {{ background:{preset_hover_bg}; }}
                    QLabel {{ color:{text}; font-size:9pt; background:transparent; }}
                    QLabel.title {{ font-weight:600; font-size:9pt; letter-spacing:.3px; }}
                    QPushButton.day {{ background:transparent; border:0; border-radius:4px; min-width:30px; min-height:30px; font-size:8pt; color:{text}; }}
                    QPushButton.day:hover {{ background:{hover_bg}; }}
                    QPushButton.day.sel {{ background:{sel_bg}; color:{sel_text}; }}
                    QPushButton.day.range {{ background:{range_bg}; color:{range_text}; }}
                    /* Today (non-selected) border highlight */
                    QPushButton[today="true"] {{ border:1px solid {accent}; }}
                    /* Selected today keeps selection background */
                    QPushButton.day.sel[today="true"] {{ border:0; }}
                    QPushButton.nav {{ background:transparent; border:0; font-size:11pt; padding:2px 6px; color:{text}; }}
                    QPushButton.nav:hover {{ background:{hover_bg}; border-radius:4px; }}
                    QPushButton#applyBtn {{ background:{accent}; color:#fff; font-weight:600; border:0; border-radius:6px; padding:6px 14px; }}
                    QPushButton#applyBtn:hover {{ background:#ff9a26; }}
                    QPushButton#clearBtn {{ background:transparent; color:{clear_color}; border:0; padding:6px 10px; }}
                    QPushButton#clearBtn:hover {{ color:{accent}; }}
                    QScrollArea {{ border:0; }}
                """)

                self.start_date: date | None = None
                self.end_date: date | None = None
                self.base_month = date.today().replace(day=1)

                # Root layout changed to vertical to allow a unified bottom action bar spanning both columns
                root = QVBoxLayout(self)
                # Tightened outer margins & spacing (was 10,10,10,10 and spacing 12)
                # Add horizontal margins for better breathing room (was 0,8,0,0)
                root.setContentsMargins(8, 8, 8, 0)
                root.setSpacing(6)
                top_row = QHBoxLayout()
                top_row.setSpacing(8)
                # Reduce overall width (was 560) to shrink horizontal footprint
                self.setFixedSize(520, 260)  # compact size

                # LEFT PRESETS (revised)
                preset_container = QVBoxLayout(); preset_container.setSpacing(2)  # match calendar month vertical spacing
                today = date.today()

                # Formatter (English default)
                def fmt(d: date):
                    return d.strftime('%a %d %b %Y')

                presets: list[tuple[str, date, date]] = [
                    ("Today", today, today),
                    ("Yesterday", today - timedelta(days=1), today - timedelta(days=1)),
                    ("This month", today.replace(day=1), today),
                    ("This year", today.replace(month=1, day=1), today),
                    ("Last month", (today.replace(day=1) - timedelta(days=1)).replace(day=1), today.replace(day=1) - timedelta(days=1)),
                ]

                # Komponen preset kustom agar teks tidak berantakan (tanpa HTML mentah di QPushButton)
                class PresetItem(QFrame):
                    def __init__(self, raw_label: str, s_d: date, e_d: date, cb_apply):
                        super().__init__()
                        self.s_d = s_d; self.e_d = e_d; self.cb_apply = cb_apply
                        self.setObjectName("PresetItem")
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                        self.setFixedWidth(120)
                        wrap = QVBoxLayout(self)
                        wrap.setContentsMargins(4, 2, 4, 2)
                        wrap.setSpacing(0)

                        def short(d: date):
                            p = d.strftime('%a %d %b %Y').split()
                            return f"{p[1]} {p[2]} {p[3]}"

                        title_lbl = QLabel(raw_label)
                        # Title color matches primary text via stylesheet inheritance; override only weight/size
                        title_lbl.setStyleSheet("font-size:8pt; font-weight:600; margin:0; padding:0;")
                        wrap.addWidget(title_lbl)

                        if s_d == e_d:
                            sd = short(s_d)
                            dates_text = f"{sd} - {sd}"
                        else:
                            dates_text = f"{short(s_d)} - {short(e_d)}"
                        dates_lbl = QLabel(dates_text)
                        # Subtext color adapt (inline for clarity)
                        dates_lbl.setStyleSheet(f"font-size:6pt; color:{subtext}; margin-top:1px;")
                        dates_lbl.setWordWrap(True)
                        wrap.addWidget(dates_lbl)
                        self.setStyleSheet("QFrame#PresetItem { border-radius:4px; }")

                    def setSelected(self, selected: bool, sel_bg: str, sel_text: str, text_color: str, subtext_color: str):
                        # Ambil dua label anak
                        if selected:
                            # Gunakan warna accent background & ubah semua label ke kontras
                            self.setStyleSheet(
                                f"QFrame#PresetItem {{ background:{sel_bg}; border-radius:4px; }}\n"
                                f"QFrame#PresetItem:hover {{ background:{sel_bg}; }}\n"
                                f"QFrame#PresetItem QLabel {{ color:{sel_text}; }}\n"
                                f"QFrame#PresetItem QLabel:last-child {{ color:{sel_text}; font-size:6pt; }}"
                            )
                        else:
                            # Kembali ke default
                            self.setStyleSheet(
                                "QFrame#PresetItem { border-radius:4px; }"
                            )

                    def mousePressEvent(self, ev):
                        if ev.button() == Qt.MouseButton.LeftButton:
                            self.cb_apply(self.s_d, self.e_d)
                        return super().mousePressEvent(ev)

                self.preset_items: list[PresetItem] = []  # collect for later dynamic height adjustment
                for label, s, e in presets:
                    item = PresetItem(label, s, e, self._apply_preset)
                    preset_container.addWidget(item)
                    self.preset_items.append(item)
                preset_container.addStretch()
                # (Logo moved to bottom unified action bar)

                top_row.addLayout(preset_container)

                # Separator vertical line
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine); sep.setFrameShadow(QFrame.Shadow.Plain)
                sep.setStyleSheet("background:#e0e0e0; width:1px;")
                sep.setFixedWidth(1)
                top_row.addWidget(sep)

                # RIGHT - CALENDARS + ACTIONS
                right_box = QVBoxLayout()
                right_box.setSpacing(4)
                cal_row = QHBoxLayout()
                # Reduce gap between the two month calendars (was 24)
                cal_row.setSpacing(16)

                # build two month widgets
                self.month_widgets: list[QWidget] = []
                for offset in (0, 1):
                    mdate = (self.base_month.replace(day=15) + timedelta(days=31*offset)).replace(day=1)
                    cal = self._build_month(mdate, offset)
                    self.month_widgets.append(cal)
                    cal_row.addWidget(cal)

                right_box.addLayout(cal_row)

                # (Action bar moved to unified bottom bar)
                top_row.addLayout(right_box, 1)
                root.addLayout(top_row, 1)

                # Unified bottom bar: logo | vertical divider | preview stretch | clear | apply
                bottom_bar_frame = QFrame()
                bottom_bar_frame.setObjectName("BottomBar")
                bottom_bar_frame.setStyleSheet("QFrame#BottomBar { background:transparent; border:none; }")
                bottom_bar_frame.setFixedHeight(40)  # adjust bar height
                bottom_bar = QHBoxLayout(bottom_bar_frame)
                # Remove left, right, and bottom margins (keep small top padding only)
                # Full bleed bottom bar (no internal side padding)
                bottom_bar.setContentsMargins(4, 2, 6, 2)
                bottom_bar.setSpacing(8)
                logo_lbl = QLabel("\uD83D\uDCC5")
                logo_lbl.setStyleSheet(f"font-size:16px; color:{text}; margin:0 6px 0 4px; background:transparent;")
                logo_lbl.setFixedHeight(28)
                bottom_bar.addWidget(logo_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
                self.range_preview = QLabel("-")
                # Transparent background, visible text color
                self.range_preview.setStyleSheet(f"background:transparent; color:{text}; font-size:11px; margin:0 0 0 2px;")
                self.range_preview.setFixedHeight(28)
                bottom_bar.addWidget(self.range_preview, 1)
                clear_btn = QPushButton("-")
                clear_btn.setObjectName("clearBtn")
                clear_btn.clicked.connect(self._clear)
                clear_btn.setStyleSheet(f"background:transparent; color:{clear_color}; padding:4px 8px; border:0; font-size:10px;")
                bottom_bar.addWidget(clear_btn)
                apply_btn = QPushButton("Pilih")
                apply_btn.setObjectName("applyBtn")
                apply_btn.clicked.connect(self._apply)
                apply_btn.setStyleSheet("background:#ff8800; color:#fff; font-weight:600; border:0; border-radius:4px; padding:6px 14px; font-size:10px;")
                bottom_bar.addWidget(apply_btn)
                root.addWidget(bottom_bar_frame)
                self._update_preview()
                # Schedule height synchronization after layout pass so calendar widgets have a sizeHint
                QTimer.singleShot(0, self._sync_preset_heights)
                QTimer.singleShot(0, self._update_preset_highlight)

            # --- helpers ---
            def _icon_label(self):
                # Legacy method retained (not used after redesign); could be removed if desired.
                lab = QLabel("\uD83D\uDCC5")  # calendar emoji
                lab.setStyleSheet("font-size:11pt; margin-right:4px;")
                return lab

            def _apply_preset(self, s: date, e: date):
                self.start_date, self.end_date = s, e
                self._refresh_calendars()
                self._update_preview()
                self._update_preset_highlight()

            def _clear(self):
                self.start_date = None
                self.end_date = None
                self._refresh_calendars()
                self._update_preview()
                self._update_preset_highlight()

            def _apply(self):
                if self.start_date and not self.end_date:
                    self.end_date = self.start_date
                if self.start_date and self.end_date:
                    txt = f"{self.start_date.strftime('%d/%m/%Y')} - {self.end_date.strftime('%d/%m/%Y')}"
                    self.parent_field.setText(txt)
                self.close()

            def _build_month(self, month_date: date, offset: int):
                box = QVBoxLayout()
                box.setSpacing(2)
                wrap = QFrame()
                wrap.setLayout(box)
                header = QHBoxLayout()
                header.setSpacing(2)
                if offset == 0:
                    prev_btn = QPushButton("<")
                    prev_btn.setProperty("class", "nav")
                    prev_btn.clicked.connect(lambda: self._shift_month(-1))
                    header.addWidget(prev_btn)
                else:
                    header.addSpacing(24)
                title = QLabel(month_date.strftime("%b %Y"))
                # Updated font size: month title to 8pt per latest request
                title.setStyleSheet("font-weight:600; font-size:8pt;")
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                header.addWidget(title, 1)
                if offset == 1:
                    next_btn = QPushButton(">")
                    next_btn.setProperty("class", "nav")
                    next_btn.clicked.connect(lambda: self._shift_month(1))
                    header.addWidget(next_btn)
                else:
                    header.addSpacing(24)
                box.addLayout(header)

                # day names
                dn = QHBoxLayout(); dn.setSpacing(0)
                for d in ["Su","Mo","Tu","We","Th","Fr","Sa"]:
                    lbl = QLabel(d)
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Updated weekday header to 8pt bold per latest request
                    lbl.setStyleSheet("color:#666; font-size:8pt; font-weight:600; min-width:30px;")
                    dn.addWidget(lbl)
                box.addLayout(dn)

                # grid days
                grid = QGridLayout(); grid.setSpacing(0)
                first = month_date
                # weekday: Monday=0..Sunday=6; we want Sunday=0
                start_col = (first.weekday()+1) % 7
                # days in month
                if month_date.month == 12:
                    next_m = month_date.replace(year=month_date.year+1, month=1)
                else:
                    next_m = month_date.replace(month=month_date.month+1)
                days_in = (next_m - timedelta(days=1)).day
                row = 0; col = 0
                # leading blanks
                for _ in range(start_col):
                    spacer = QLabel(" ")
                    spacer.setFixedSize(30, 30)
                    grid.addWidget(spacer, row, col); col += 1
                for day in range(1, days_in+1):
                    btn = QPushButton(str(day))
                    btn.setProperty("class", "day")
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.setFixedSize(30,30)
                    ddate = month_date.replace(day=day)
                    btn.clicked.connect(lambda _=False, dd=ddate: self._pick(dd))
                    grid.addWidget(btn, row, col)
                    col += 1
                    if col>6:
                        col=0; row+=1
                box.addLayout(grid)
                # store for refresh
                wrap.month_date = month_date
                wrap.title_label = title
                wrap.grid = grid
                return wrap

            def _pick(self, ddate: date):
                if not self.start_date or (self.start_date and self.end_date):
                    self.start_date = ddate; self.end_date = None
                else:
                    if ddate < self.start_date:
                        self.end_date, self.start_date = self.start_date, ddate
                    else:
                        self.end_date = ddate
                self._refresh_calendars(); self._update_preview()
                self._update_preset_highlight()

            def _shift_month(self, delta: int):
                # prevent overlapping earlier than year 1970 simple guard
                base_month_num = self.base_month.month + delta
                year = self.base_month.year + (base_month_num-1)//12
                month = (base_month_num-1)%12 + 1
                self.base_month = self.base_month.replace(year=year, month=month, day=1)
                # rebuild titles & days
                for idx, wrap in enumerate(self.month_widgets):
                    mdate = (self.base_month.replace(day=15) + timedelta(days=31*idx)).replace(day=1)
                    wrap.month_date = mdate
                    wrap.title_label.setText(mdate.strftime("%b %Y"))
                    # clear old buttons
                    while wrap.grid.count():
                        item = wrap.grid.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
                    # rebuild grid
                    first = mdate
                    start_col = (first.weekday()+1) % 7
                    if mdate.month == 12:
                        next_m = mdate.replace(year=mdate.year+1, month=1)
                    else:
                        next_m = mdate.replace(month=mdate.month+1)
                    days_in = (next_m - timedelta(days=1)).day
                    row=0; col=0
                    for _ in range(start_col):
                        spacer = QLabel(" "); spacer.setFixedSize(30,30); wrap.grid.addWidget(spacer,row,col); col+=1
                    for day in range(1, days_in+1):
                        btn = QPushButton(str(day)); btn.setProperty("class","day"); btn.setCursor(Qt.CursorShape.PointingHandCursor); btn.setFixedSize(30,30)
                        ddate = mdate.replace(day=day)
                        btn.clicked.connect(lambda _=False, dd=ddate: self._pick(dd))
                        wrap.grid.addWidget(btn,row,col); col+=1
                        if col>6: col=0; row+=1
                self._refresh_calendars()

            def _refresh_calendars(self):
                for wrap in self.month_widgets:
                    for i in range(wrap.grid.count()):
                        item = wrap.grid.itemAt(i)
                        w = item.widget()
                        if isinstance(w, QPushButton):
                            dtext = w.text()
                            if not dtext.isdigit():
                                continue
                            ddate = wrap.month_date.replace(day=int(dtext))
                            cls = "day"
                            if self.start_date and self.end_date and self.start_date <= ddate <= self.end_date:
                                if ddate == self.start_date or ddate == self.end_date:
                                    cls = "day sel"
                                else:
                                    cls = "day range"
                            elif self.start_date and ddate == self.start_date:
                                cls = "day sel"
                            w.setProperty("class", cls)
                            # Tandai hari ini (today) agar punya border
                            if ddate == date.today():
                                w.setProperty("today", True)
                            else:
                                w.setProperty("today", False)
                            w.setStyleSheet("")  # trigger polish

            def _update_preview(self):
                if self.start_date and self.end_date:
                    self.range_preview.setText(
                        f"{self.start_date.strftime('%d %b %Y')} - {self.end_date.strftime('%d %b %Y')}"
                    )
                elif self.start_date:
                    self.range_preview.setText(f"Mulai: {self.start_date.strftime('%d %b %Y')}")
                else:
                    self.range_preview.setText("-")

            def _update_preset_highlight(self):
                # Highlight preset yang cocok dengan start & end saat ini
                if not hasattr(self, "preset_items"):
                    return
                for it in self.preset_items:
                    match = False
                    if self.start_date and self.end_date:
                        match = (it.s_d == self.start_date and it.e_d == self.end_date)
                    elif self.start_date and not self.end_date:
                        # Saat baru pilih 1 hari belum highlight apapun
                        match = False
                    it.setSelected(match, self.sel_bg, self.sel_text, self.text_color, self.subtext_color)

            def _sync_preset_heights(self):
                # Dynamically distribute preset item heights to roughly match calendar vertical height
                try:
                    if not self.preset_items:
                        return
                    # Use first month widget height as reference (already built)
                    cal_ref = self.month_widgets[0]
                    target_total = cal_ref.sizeHint().height()
                    # Fallback if sizeHint too small
                    if target_total < 160:
                        target_total = 200
                    spacing =  self.preset_items[0].parentWidget().layout().spacing() if self.preset_items[0].parentWidget() else 2
                    n = len(self.preset_items)
                    # Remove stretch temporarily if present at end of layout
                    # Compute available height minus inter-item spacing
                    total_spacing = spacing * (n - 1)
                    available = max(100, target_total - total_spacing)
                    per_item = int(available / n)
                    # Clamp reasonable bounds
                    per_item = max(30, min(46, per_item))
                    for it in self.preset_items:
                        it.setFixedHeight(per_item)
                except Exception:
                    pass

            def show_near(self):
                # position below field, anchor right edge of popup ke right edge field agar memanjang ke kiri
                field_global_top_left = self.parent_field.mapToGlobal(QPoint(0, 0))
                field_w = self.parent_field.width()
                popup_w = self.width()
                x = field_global_top_left.x() + field_w - popup_w  # right align
                y = field_global_top_left.y() + self.parent_field.height() + 4
                # jaga agar tidak keluar layar kiri
                if x < 4:
                    x = 4
                self.move(x, y)
                self.show()
                self.raise_()

            def set_theme(self, mode: str):
                """Update palette & stylesheet tanpa membuat ulang popup."""
                self.theme_mode = mode.lower()
                accent = "#ff8800"
                if self.theme_mode == "dark":
                    bg = "#1e1e1e"; text = "#dddddd"; subtext = "#aaaaaa"; border = "#444444"; preset_hover_bg = "#252525"; hover_bg = preset_hover_bg; sel_bg = accent; sel_text = "#ffffff"; range_bg = preset_hover_bg; range_text = text; clear_color = "#bbbbbb"
                else:
                    bg = "#ffffff"; text = "#222222"; subtext = "#555555"; border = "#d6d6d6"; preset_hover_bg = "#f7f7f7"; hover_bg = preset_hover_bg; sel_bg = accent; sel_text = "#ffffff"; range_bg = preset_hover_bg; range_text = text; clear_color = "#666666"
                self.accent = accent; self.sel_bg = sel_bg; self.sel_text = sel_text; self.text_color = text; self.subtext_color = subtext
                self.setStyleSheet(f"""
                    QFrame#CompactDateRangePopup {{ background:{bg}; border:1px solid {border}; border-radius:8px; }}
                    QFrame#PresetItem {{ background:{bg}; border-radius:4px; }}
                    QFrame#PresetItem:hover {{ background:{preset_hover_bg}; }}
                    QLabel {{ color:{text}; font-size:9pt; background:transparent; }}
                    QLabel.title {{ font-weight:600; font-size:9pt; letter-spacing:.3px; }}
                    QPushButton.day {{ background:transparent; border:0; border-radius:4px; min-width:30px; min-height:30px; font-size:8pt; color:{text}; }}
                    QPushButton.day:hover {{ background:{hover_bg}; }}
                    QPushButton.day.sel {{ background:{sel_bg}; color:{sel_text}; }}
                    QPushButton.day.range {{ background:{range_bg}; color:{range_text}; }}
                    QPushButton[today="true"] {{ border:1px solid {accent}; }}
                    QPushButton.day.sel[today="true"] {{ border:0; }}
                    QPushButton.nav {{ background:transparent; border:0; font-size:11pt; padding:2px 6px; color:{text}; }}
                    QPushButton.nav:hover {{ background:{hover_bg}; border-radius:4px; }}
                    QPushButton#applyBtn {{ background:{accent}; color:#fff; font-weight:600; border:0; border-radius:6px; padding:6px 14px; }}
                    QPushButton#applyBtn:hover {{ background:#ff9a26; }}
                    QPushButton#clearBtn {{ background:transparent; color:{clear_color}; border:0; padding:6px 10px; }}
                    QPushButton#clearBtn:hover {{ color:{accent}; }}
                    QScrollArea {{ border:0; }}
                """)
                # Refresh current visual states
                self._refresh_calendars()
                self._update_preset_highlight()
                self._update_preview()

        # ---------------------------------------------------------------
        def open_popup():
            # Tutup popup lama jika masih ada
            if hasattr(self, "_date_popup") and self._date_popup is not None:
                try:
                    self._date_popup.close()
                except Exception:
                    pass
            # Gunakan mode tema saat ini bila tersedia
            current_mode = getattr(self, "_current_theme_mode", "light")
            self._date_popup = CompactDateRangePopup(self.tgl_update, theme_mode=current_mode)
            self._date_popup.show_near()

        # Override click
        def mousePressEvent(ev):
            if ev.button() == Qt.MouseButton.LeftButton:
                open_popup()
            else:
                QLineEdit.mousePressEvent(self.tgl_update, ev)
        self.tgl_update.mousePressEvent = mousePressEvent
    
    def _setup_text_fields(self, layout, gap):
        """Setup field input teks untuk pencarian nama, NIK, NKK, dll."""
        # Field nama
        self.nama = QLineEdit()
        self.nama.setPlaceholderText("Nama")
        layout.addWidget(self.nama)
        
        # Baris NIK & NKK dalam satu baris untuk efisiensi ruang
        nik_nkk_row = QHBoxLayout()
        nik_nkk_row.setContentsMargins(0, 0, 0, 0)
        nik_nkk_row.setSpacing(gap)
        
        self.nik = QLineEdit()
        self.nik.setPlaceholderText("NIK")
        self.nkk = QLineEdit()
        self.nkk.setPlaceholderText("NKK")
        
        nik_nkk_row.addWidget(self.nik)
        nik_nkk_row.addWidget(self.nkk)
        layout.addLayout(nik_nkk_row)
        
        # Field tanggal lahir
        self.tgl_lahir = QLineEdit()
        self.tgl_lahir.setPlaceholderText("Tanggal Lahir (Format : DD|MM|YYYY)")
        layout.addWidget(self.tgl_lahir)
    
    def _setup_age_slider(self, layout, gap):
        """Setup slider rentang umur dengan label yang interaktif."""
        umur_container = QVBoxLayout()
        umur_container.setContentsMargins(0, 8, 0, 0)  # Beri jarak dari elemen di atas
        umur_container.setSpacing(gap)
        
        # Label umur
        lbl_umur = QLabel("Umur")
        
        # Container untuk slider
        umur_layout = QHBoxLayout()
        umur_layout.setContentsMargins(0, 0, 0, 0)
        umur_layout.setSpacing(0)
        
        # Slider rentang umur (0-100 tahun)
        self.umur_slider = RangeSlider(0, 100, parent=self)
        
        # Callback untuk perubahan nilai umur (opsional)
        def _handle_age_change(min_age, max_age):
            # Label individual ditangani langsung oleh RangeSlider
            pass
        
        self.on_age_range_changed = _handle_age_change
        umur_layout.addWidget(self.umur_slider)
        
        umur_container.addWidget(lbl_umur)
        umur_container.addLayout(umur_layout)
        layout.addLayout(umur_container)
    
    def _setup_dropdown_grid(self, grid_layout):
        """Setup grid dropdown untuk berbagai kategori filter."""
        # Inisialisasi semua dropdown
        self.keterangan = CustomComboBox()
        self.kelamin = CustomComboBox()
        self.kawin = CustomComboBox()
        self.disabilitas = CustomComboBox()
        self.ktp_el = CustomComboBox()
        self.sumber = CustomComboBox()
        self.rank = CustomComboBox()
        
        # Field alamat
        self.alamat = QLineEdit()
        self.alamat.setPlaceholderText("Alamat")
        
        # Populate dropdown dengan opsi yang relevan
        self._populate_dropdown_options()
        
        # Susun dalam grid 3 kolom untuk efisiensi ruang
        grid_layout.addWidget(self.keterangan, 0, 0)
        grid_layout.addWidget(self.kelamin, 0, 1)
        grid_layout.addWidget(self.kawin, 0, 2)
        grid_layout.addWidget(self.disabilitas, 1, 0)
        grid_layout.addWidget(self.ktp_el, 1, 1)
        grid_layout.addWidget(self.sumber, 1, 2)
        grid_layout.addWidget(self.alamat, 2, 0, 1, 2)  # Alamat span 2 kolom
        grid_layout.addWidget(self.rank, 2, 2)
    
    def _populate_dropdown_options(self):
        """Mengisi dropdown dengan opsi-opsi yang tersedia."""
        # Dropdown keterangan dengan kode TMS
        self.keterangan.addItems([
            "Keterangan", "1 (Meninggal)", "2 (Ganda)", "3 (Di Bawah Umur)", 
            "4 (Pindah Domisili)", "5 (WNA)", "6 (TNI)", "7 (Polri)", 
            "8 (Salah TPS)", "U (Ubah)", "90 (Keluar Loksus)", "91 (Meninggal)", 
            "92 (Ganda)", "93 (Di Bawah Umur)", "94 (Pindah Domisili)", 
            "95 (WNA)", "96 (TNI)", "97 (Polri)"
        ])
        
        # Dropdown jenis kelamin
        self.kelamin.addItems(["Kelamin", "L", "P"])
        
        # Dropdown status perkawinan
        self.kawin.addItems(["Kawin", "S", "B", "P"])
        
        # Dropdown disabilitas
        self.disabilitas.addItems([
            "Disabilitas", "0 (Normal)", "1 (Fisik)", "2 (Intelektual)", 
            "3 (Mental)", "4 (Sensorik Wicara)", "5 (Sensorik Rungu)", 
            "6 (Sensorik Netra)"
        ])
        
        # Dropdown KTP Elektronik
        self.ktp_el.addItems(["KTP-el", "B", "S"])
        
        # Dropdown sumber data - berisi berbagai sumber pemutakhiran
        self.sumber.addItems([
            "Sumber", "dp4", "trw3_2025", "tms_trw 2 _2025", "kemendagri", 
            "coklit", "trw2_2025", "ubah_trw 2 _2025", "ganda kab", 
            "ganda prov", "loksus", "masyarakat", "dpk"
        ])
        
        # Dropdown rank status pemilih
        self.rank.addItems(["Rank", "Aktif", "Ubah", "TMS", "Baru"])
    
    def _setup_checkboxes(self, layout):
        """Setup checkbox untuk opsi filter tambahan."""
        # Inisialisasi checkbox dengan label yang jelas
        self.cb_ganda = CustomCheckBox("Ganda")
        self.cb_invalid_tgl = CustomCheckBox("Invalid Tgl")
        self.cb_nkk_terpisah = CustomCheckBox("NKK Terpisah")
        self.cb_analisis_tms = CustomCheckBox("Analisis TMS 8")
        
        # Set tinggi yang konsisten untuk semua checkbox
        for checkbox in [self.cb_ganda, self.cb_invalid_tgl, self.cb_nkk_terpisah, self.cb_analisis_tms]:
            checkbox.setFixedHeight(22)
        
        # Susun dalam grid 2x2 untuk tampilan yang rapi
        layout.addWidget(self.cb_ganda, 0, 0)
        layout.addWidget(self.cb_invalid_tgl, 0, 1)
        layout.addWidget(self.cb_nkk_terpisah, 1, 0)
        layout.addWidget(self.cb_analisis_tms, 1, 1)
    
    def _setup_radio_buttons(self, layout):
        """Setup radio button untuk memilih tipe TPS."""
        self.rb_reguler = QRadioButton("Reguler")
        self.rb_khusus = QRadioButton("Khusus")
        self.rb_reguler_khusus = QRadioButton("Reguler & Khusus")
        
        # Set default ke "Reguler & Khusus" untuk menampilkan semua data
        self.rb_reguler_khusus.setChecked(True)
        
        # Tambahkan semua radio button ke layout
        for radio_button in [self.rb_reguler, self.rb_khusus, self.rb_reguler_khusus]:
            layout.addWidget(radio_button)
    
    def _setup_action_buttons(self, layout):
        """Setup tombol aksi untuk reset dan apply filter."""
        # Tombol reset untuk mengembalikan semua filter ke default
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setObjectName("resetBtn")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_filters)
        
        # Tombol filter untuk menerapkan semua filter yang telah diset
        self.btn_filter = QPushButton("Filter")
        self.btn_filter.setObjectName("filterBtn")
        self.btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Layout tombol dengan spacer untuk posisi center
        layout.addStretch()
        layout.addWidget(self.btn_reset)
        layout.addWidget(self.btn_filter)
        layout.addStretch()
    
    def _apply_consistent_sizing(self):
        """Terapkan ukuran yang konsisten untuk semua field input."""
        desired_height = 34  # Tinggi yang pas untuk tampilan compact
        
        # Daftar semua widget yang perlu ukuran konsisten
        input_widgets = [
            self.tgl_update, self.nama, self.nik, self.nkk, self.tgl_lahir, 
            self.alamat, self.keterangan, self.kelamin, self.kawin, 
            self.disabilitas, self.ktp_el, self.sumber, self.rank
        ]
        
        # Terapkan tinggi yang sama untuk semua widget
        for widget in input_widgets:
            widget.setFixedHeight(desired_height)
    
    def _apply_internal_widths(self, gap: int, side_margin: int):
        """Hitung dan terapkan lebar yang tepat agar tidak ada overflow horizontal.
        
        Args:
            gap: Jarak antar elemen dalam grid
            side_margin: Margin kiri dan kanan
        """
        # Hitung lebar yang tersedia setelah dikurangi margin
        total_inner_width = self._dock_width - (side_margin * 2)
        
        # Untuk grid 3 kolom: ada 2 gap horizontal antar kolom
        column_width = int((total_inner_width - (gap * 2)) / 3)
        double_column_width = (column_width * 2) + gap
        
        # Field yang menggunakan lebar penuh
        full_width_fields = [self.tgl_update, self.nama, self.tgl_lahir]
        for field in full_width_fields:
            field.setFixedWidth(total_inner_width)
        
        # Field NIK/NKK yang berbagi satu baris (2 kolom)
        half_width = int((total_inner_width - gap) / 2)
        self.nik.setFixedWidth(half_width)
        self.nkk.setFixedWidth(half_width)
        
        # Field dalam grid 3 kolom
        grid_fields = [
            self.keterangan, self.kelamin, self.kawin, 
            self.disabilitas, self.ktp_el, self.sumber, self.rank
        ]
        for field in grid_fields:
            field.setFixedWidth(column_width)
        
        # Field alamat yang span 2 kolom
        self.alamat.setFixedWidth(double_column_width)
    
    def resizeEvent(self, event):  # type: ignore
        """Handle perubahan ukuran widget untuk menjaga proporsi layout.
        
        Args:
            event: Event resize dari Qt
        """
        try:
            # Jika lebar dock berubah, sesuaikan ulang proporsi
            parent_widget = self.parent()
            if parent_widget and parent_widget.width() != self._dock_width:
                self._dock_width = parent_widget.width()
                # Terapkan ulang dengan konfigurasi margin/gap standar
                self._apply_internal_widths(gap=6, side_margin=6)
        except Exception:
            # Abaikan error jika terjadi masalah dalam resize
            pass
        super().resizeEvent(event)
    
    # ==========================
    # Metode: Reset Semua Filter
    # ==========================
    def reset_filters(self):
        """Reset semua field filter ke nilai default/kosong."""
        # Reset semua field input teks
        text_fields = [
            self.tgl_update, self.nama, self.nik, self.nkk, 
            self.tgl_lahir, self.alamat
        ]
        for field in text_fields:
            field.clear()
        
        # Reset semua dropdown ke pilihan pertama (placeholder)
        dropdown_fields = [
            self.keterangan, self.kelamin, self.kawin, self.disabilitas, 
            self.ktp_el, self.sumber, self.rank
        ]
        for dropdown in dropdown_fields:
            dropdown.setCurrentIndex(0)
        
        # Reset semua checkbox ke unchecked
        checkboxes = [
            self.cb_ganda, self.cb_invalid_tgl, 
            self.cb_nkk_terpisah, self.cb_analisis_tms
        ]
        for checkbox in checkboxes:
            checkbox.setChecked(False)
        
        # Reset radio button ke default (Reguler & Khusus)
        self.rb_reguler_khusus.setChecked(True)
        
        # Reset slider umur ke rentang penuh (0-100)
        self.umur_slider.setValues(0, 100)
    
    def update_umur_label(self, value):
        """Metode kompatibilitas untuk update label umur (tidak digunakan aktif).
        
        Args:
            value: Nilai umur (untuk kompatibilitas)
        """
        # Metode ini disediakan untuk kompatibilitas dengan versi lama
        # Label umur sekarang ditangani langsung oleh RangeSlider
        return
    
    def get_filters(self):
        """Ambil semua nilai filter yang telah diset pengguna.
        
        Returns:
            dict: Dictionary berisi semua nilai filter yang aktif
        """
        # Proses nilai keterangan (ambil kode angka/huruf saja)
        keterangan_text = self.keterangan.currentText()
        keterangan_value = keterangan_text.split(' ')[0] if keterangan_text != "Keterangan" else ""
        
        # Proses nilai disabilitas (ambil kode angka saja)
        disabilitas_text = self.disabilitas.currentText()
        disabilitas_value = disabilitas_text.split(' ')[0] if disabilitas_text != "Disabilitas" else ""
        
        # Proses nilai rank
        rank_text = self.rank.currentText()
        rank_value = rank_text if rank_text != "Rank" else ""
        
        # Parse rentang tanggal update dari field yang berformat "DD/MM/YYYY - DD/MM/YYYY"
        last_update_start = ""
        last_update_end = ""
        raw_date_range = self.tgl_update.text().strip()
        
        if raw_date_range and ' - ' in raw_date_range:
            start_part, end_part = raw_date_range.split(' - ', 1)
            if self._is_valid_date(start_part) and self._is_valid_date(end_part):
                last_update_start = start_part
                last_update_end = end_part
        
        # Kembalikan dictionary dengan semua nilai filter
        return {
            "nama": self.nama.text().strip(),
            "nik": self.nik.text().strip(),
            "nkk": self.nkk.text().strip(),
            "tgl_lahir": self.tgl_lahir.text().strip(),
            "umur_min": self.umur_slider.lowerValue(),
            "umur_max": self.umur_slider.upperValue(),
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
    def _is_valid_date(self, date_string: str) -> bool:
        """Validasi apakah string merupakan tanggal yang valid.
        
        Args:
            date_string: String tanggal yang akan divalidasi
            
        Returns:
            bool: True jika valid, False jika tidak
        """
        try:
            datetime.strptime(date_string, "%d/%m/%Y")
            return True
        except ValueError:
            return False
    
    def apply_theme(self, mode):
        """Terapkan tema tampilan (gelap atau terang) ke semua elemen filter.
        
        Args:
            mode: Mode tema ('dark' atau 'light')
        """
        # Simpan mode untuk dipakai popup date range
        self._current_theme_mode = mode
        # Terapkan tema ke custom checkbox
        custom_checkboxes = [
            self.cb_ganda, self.cb_invalid_tgl, 
            self.cb_nkk_terpisah, self.cb_analisis_tms
        ]
        for checkbox in custom_checkboxes:
            checkbox.setTheme(mode)
        
        # Terapkan tema ke custom combobox
        custom_comboxes = [
            self.keterangan, self.kelamin, self.kawin, 
            self.disabilitas, self.ktp_el, self.sumber, self.rank
        ]
        for combobox in custom_comboxes:
            combobox.setTheme(mode)
        
        # Terapkan stylesheet sesuai mode tema
        if mode == "dark":
            self._apply_dark_theme()
        else:
            self._apply_light_theme()
        # Update popup jika sedang terbuka
        if hasattr(self, "_date_popup") and self._date_popup is not None:
            try:
                self._date_popup.set_theme(mode)
            except Exception:
                pass
    
    def _apply_dark_theme(self):
        """Terapkan stylesheet untuk tema gelap."""
        self.setStyleSheet("""
            /* Styling umum untuk widget */
            QWidget {
                font-family: 'Segoe UI', 'Calibri';
                font-size: 9px;
                background: #1e1e1e;
                color: #d4d4d4;
            }
            
            /* Scroll area styling */
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
            
            /* Input field styling */
            QLineEdit, QComboBox {
                padding: 8px 10px;
                border: 1px solid #555;
                border-radius: 4px;
                background: #2d2d30;
                min-height: 34px;
                color: #d4d4d4;
                font-size: 10px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #888;
            }
            QComboBox QListView {
                background: #2d2d30;
                border: 1px solid #555;
                outline: 0;
                padding: 4px;
            }
            QComboBox QListView::item {
                padding: 4px 8px;
                border-radius: 5px;
                margin: 2px 2px;
            }
            QComboBox QListView::item:hover {
                background: #ff9800;
                color: #1e1e1e;
                border-radius: 5px;
                margin: 2px 2px;
            }
            QComboBox QListView::item:selected {
                background: #ff9800;
                color: #1e1e1e;
                border-radius: 5px;
                margin: 2px 2px;
            }
            
            /* Slider styling */
            QSlider::groove:horizontal {
                height: 6px;
                background: #2d2d30;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #007acc;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            
            /* Button styling */
            QPushButton#resetBtn {
                background: #444;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton#resetBtn:hover {
                background: #555;
            }
            QPushButton#filterBtn {
                background: #0e639c;
                border: 1px solid #1177bb;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton#filterBtn:hover {
                background: #1177bb;
            }
        """)
    
    def _apply_light_theme(self):
        """Terapkan stylesheet untuk tema terang."""
        self.setStyleSheet("""
            /* Styling umum untuk widget */
            QWidget {
                font-family: 'Segoe UI', 'Calibri';
                font-size: 9px;
                background: #f2f2f2;
                color: #222;
            }
            
            /* Scroll area styling */
            QScrollArea {
                border: none;
                background: #f2f2f2;
            }
            QScrollBar:vertical {
                border: none;
                background: #d0d0d0;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #999;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #777;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
            /* Input field styling */
            QLineEdit, QComboBox {
                padding: 8px 10px;
                border: 1px solid #bbb;
                border-radius: 4px;
                background: #ffffff;
                min-height: 34px;
                color: #222;
                font-size: 10px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #888;
            }
            QComboBox QListView {
                background: #ffffff;
                border: 1px solid #bbb;
                outline: 0;
                padding: 4px;
            }
            QComboBox QListView::item {
                padding: 4px 8px;
                border-radius: 5px;
                margin: 2px 2px;
            }
            QComboBox QListView::item:hover {
                background: #ff9800;
                color: #ffffff;
                border-radius: 5px;
                margin: 2px 2px;
            }
            QComboBox QListView::item:selected {
                background: #ff9800;
                color: #ffffff;
                border-radius: 5px;
                margin: 2px 2px;
            }
            
            /* Slider styling */
            QSlider::groove:horizontal {
                height: 6px;
                background: #d0d0d0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0e639c;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            
            /* Button styling */
            QPushButton#resetBtn {
                background: #e0e0e0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton#resetBtn:hover {
                background: #dadada;
            }
            QPushButton#filterBtn {
                background: #0e639c;
                border: 1px solid #1177bb;
                border-radius: 4px;
                padding: 6px 14px;
                color: #fff;
            }
            QPushButton#filterBtn:hover {
                background: #1177bb;
            }
        """)


# =====================================================
# Widget Dock dengan Lebar Tetap
# =====================================================
class FixedDockWidget(QDockWidget):
    """Dock widget dengan lebar tetap yang tidak dapat diubah ukurannya.
    
    Widget ini digunakan untuk sidebar filter agar memiliki lebar yang 
    konsisten dan tidak bisa di-resize oleh pengguna.
    """
    
    def __init__(self, title: str, parent=None, fixed_width: int = 320):
        """Inisialisasi dock widget dengan lebar tetap.
        
        Args:
            title: Judul yang ditampilkan di header dock
            parent: Widget parent
            fixed_width: Lebar tetap dalam pixel
        """
        super().__init__(title, parent)
        self._fixed_width = fixed_width
        
        # Hanya bisa di-dock di sisi kanan
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        
        # Hanya bisa di-close, tidak bisa di-float atau resize
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        
        # Set lebar minimum dan maksimum yang sama untuk mengunci ukuran
        self.setMinimumWidth(fixed_width)
        self.setMaximumWidth(fixed_width)
    
    def setWidget(self, widget: QWidget) -> None:  # type: ignore
        """Override setWidget untuk memastikan widget child juga memiliki lebar tetap.
        
        Args:
            widget: Widget yang akan diset sebagai konten dock
        """
        super().setWidget(widget)
        widget.setFixedWidth(self._fixed_width)
    
    def sizeHint(self):  # type: ignore
        """Override sizeHint untuk memberikan ukuran yang tepat.
        
        Returns:
            QSize: Ukuran yang disarankan untuk dock widget
        """
        size = super().sizeHint()
        size.setWidth(self._fixed_width)
        return size

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
            # Lebar SUMBER diperlebar supaya seluruh teks pilihan (misal: "ubah_trw 2 _2025") tidak terpotong
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
        if filters["keterangan"]:
            ket_filter = filters["keterangan"].strip().upper()
            ket_data = item.get("KET", "").strip().upper()
            if ket_filter != ket_data:
                return False
            
        # Gender filter
        if filters["jk"]:
            jk_filter = filters["jk"].strip().upper()
            jk_data = item.get("JK", "").strip().upper()
            if jk_filter != jk_data:
                return False
            
        # Marital status filter
        if filters["sts"]:
            sts_filter = filters["sts"].strip().upper()
            sts_data = item.get("STS", "").strip().upper()
            if sts_filter != sts_data:
                return False
            
        # Disability filter
        if filters["dis"]:
            dis_filter = filters["dis"].strip().upper()
            dis_data = item.get("DIS", "").strip().upper()
            if dis_filter != dis_data:
                return False
            
        # KTP-el filter
        if filters["ktpel"]:
            ktpel_filter = filters["ktpel"].strip().upper()
            ktpel_data = item.get("KTPel", "").strip().upper()
            if ktpel_filter != ktpel_data:
                return False
            
        # Source filter
        if filters["sumber"]:
            sumber_filter = filters["sumber"].strip().upper()
            sumber_data = item.get("SUMBER", "").strip().upper()
            if sumber_filter != sumber_data:
                return False
        
        # Rank filter (Aktif / Ubah / Baru / TMS) adaptif
        if filters["rank"]:
            rank_filter_raw = filters["rank"].strip().upper()
            ket_raw = (item.get("KET", "") or "").strip().upper()
            dpid_val = (item.get("DPID", "") or "").strip()

            # Rekonstruksi nilai jika kosong
            if not ket_raw:
                if dpid_val and dpid_val != "0":
                    ket_val = "0"  # dianggap aktif
                else:
                    ket_val = "B"  # dianggap baru
            else:
                ket_val = ket_raw

            is_tms = ket_val in {"1","2","3","4","5","6","7","8"}

            def matches_rank():
                if rank_filter_raw == "AKTIF":
                    return ket_val == "0"
                if rank_filter_raw == "UBAH":
                    return ket_val == "U"
                if rank_filter_raw == "BARU":
                    return ket_val == "B"
                if rank_filter_raw == "TMS":
                    return is_tms
                return True

            if not matches_rank():
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
                            if app_col == "KET":
                                val = val.upper()

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

                    # Derivasi KET jika kosong berdasarkan STATUS
                    if not data_dict.get("KET", "").strip():
                        if status_val == "AKTIF":
                            data_dict["KET"] = "0"
                        elif status_val == "UBAH":
                            data_dict["KET"] = "U"
                        elif status_val == "BARU":
                            data_dict["KET"] = "B"
                        else:
                            data_dict["KET"] = "0"

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
        protect_combobox_from_scroll(self.tahapan_combo)  # Proteksi dari scroll
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
        protect_combobox_from_scroll(self.desa)  # Proteksi dari scroll
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