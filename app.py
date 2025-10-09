import sys, sqlite3, csv, os, atexit, base64, random, string, pyotp, qrcode, hashlib, tempfile # type: ignore
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QMessageBox, QMainWindow, QTableWidget, QTableWidgetItem,
    QToolBar, QStatusBar, QCompleter, QSizePolicy,
    QFileDialog, QHBoxLayout, QDialog, QCheckBox, QScrollArea, QHeaderView,
    QStyledItemDelegate, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QFrame, QMenu,
    QFormLayout, QSlider, QRadioButton, QDockWidget, QGridLayout, QStackedWidget, QInputDialog
)
from PyQt6.QtGui import QAction, QPainter, QColor, QPen, QPixmap, QFont, QIcon, QRegularExpressionValidator
from PyQt6.QtCore import Qt, QTimer, QRect, QPropertyAnimation, QEasingCurve, QRegularExpression
from io import BytesIO
from cryptography.fernet import Fernet

# ===================== ENKRIPSI/DEKRIPSI DB (pakai nexvo.key) =====================
import os, hashlib, tempfile
from cryptography.fernet import Fernet

# --- Konstanta format file terenkripsi ---
MAGIC = b"NEXVOENC1"          # header format/versi berkas terenkripsi
SQLITE_HEADER = b"SQLite format 3"  # header DB SQLite

# --- Lokasi file kunci. Pastikan fungsi generate_key() & load_key() tersedia ---
KEY_FILE = "nexvo.key"

def generate_key():
    """Buat key baru dan simpan ke file jika belum ada."""
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    return key

def load_key():
    """Muat key dari file, atau buat baru jika belum ada."""
    if not os.path.exists(KEY_FILE):
        print("[INFO] Key enkripsi belum ada, membuat baru...")
        return generate_key()
    with open(KEY_FILE, "rb") as f:
        return f.read()

# --- Helper I/O atomic (aman dari file setengah jadi) ---
def _atomic_write(path: str, data: bytes):
    """Tulis bytes ke file secara atomic (safe replace)."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_enc_", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic swap
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def _sha256(b: bytes) -> bytes:
    """Kembalikan raw digest SHA-256 (32 bytes)."""
    return hashlib.sha256(b).digest()

def _encrypt_file(plain_path: str, enc_path: str):
    """
    Enkripsi database SQLite plaintext -> file terenkripsi (.enc)
    Format file: MAGIC (9b) | CHECKSUM(32b) | CIPHERTEXT
    """
    if not os.path.exists(plain_path):
        raise FileNotFoundError(f"Plain DB tidak ditemukan: {plain_path}")

    with open(plain_path, "rb") as f:
        db = f.read()

    # Validasi: ini harus DB SQLite yang valid
    if not db.startswith(SQLITE_HEADER):
        raise ValueError("File plaintext bukan database SQLite yang valid.")

    # Muat kunci dari nexvo.key (konsisten untuk encrypt/decrypt)
    key = load_key()
    fernet = Fernet(key)

    # Hitung checksum plaintext sebelum dienkripsi
    checksum = _sha256(db)             # 32 bytes
    ciphertext = fernet.encrypt(db)    # bytes terenkripsi

    # Payload akhir: header + checksum + ciphertext
    payload = MAGIC + checksum + ciphertext

    # Tulis secara atomic agar aman
    _atomic_write(enc_path, payload)

def _decrypt_file(enc_path: str, dec_path: str):
    """
    Dekripsi file terenkripsi (.enc) -> database plaintext SQLite.
    Verifikasi: MAGIC, checksum plaintext, dan header SQLite.
    """
    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"Encrypted DB tidak ditemukan: {enc_path}")

    with open(enc_path, "rb") as f:
        blob = f.read()

    # Cek ukuran minimal: MAGIC + 32 bytes checksum + minimal 1 byte ciphertext
    min_len = len(MAGIC) + 32 + 1
    if len(blob) < min_len:
        raise ValueError("File .enc terlalu pendek / corrupt.")

    # Cek header MAGIC
    if not blob.startswith(MAGIC):
        raise ValueError("MAGIC header tidak cocok (bukan format NEXVOENC1).")

    # Ambil potongan: checksum dan ciphertext
    hdr_len = len(MAGIC)
    checksum = blob[hdr_len:hdr_len + 32]
    ciphertext = blob[hdr_len + 32:]

    # Dekripsi memakai kunci dari nexvo.key
    key = load_key()
    fernet = Fernet(key)
    try:
        db = fernet.decrypt(ciphertext)
    except Exception as e:
        raise ValueError(f"Gagal decrypt ciphertext (salah kunci atau data rusak): {e}")

    # Verifikasi checksum plaintext
    if _sha256(db) != checksum:
        raise ValueError("Checksum plaintext tidak cocok. File terenkripsi rusak.")

    # Verifikasi header SQLite
    if not db.startswith(SQLITE_HEADER):
        raise ValueError("Hasil dekripsi bukan database SQLite yang valid.")

    # Tulis plaintext secara atomic
    _atomic_write(dec_path, db)
# ================================================================================

def show_modern_warning(parent, title, text):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)

    msg.setWindowModality(Qt.WindowModality.NonModal)              # ✅ perbaikan
    msg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    _apply_modern_style(msg, accent="#ffc107")
    msg.show()

    # (opsional) fade-in
    anim = QPropertyAnimation(msg, b"windowOpacity")
    anim.setDuration(150)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    msg.anim = anim

def show_modern_info(parent, title, text):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)

    msg.setWindowModality(Qt.WindowModality.NonModal)              # ✅ perbaikan
    msg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    _apply_modern_style(msg, accent="#17a2b8")
    msg.show()

    anim = QPropertyAnimation(msg, b"windowOpacity")
    anim.setDuration(150)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    msg.anim = anim

def show_modern_error(parent, title, text):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)

    msg.setWindowModality(Qt.WindowModality.NonModal)              # ✅ perbaikan
    msg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    _apply_modern_style(msg, accent="#dc3545")
    msg.show()

    anim = QPropertyAnimation(msg, b"windowOpacity")
    anim.setDuration(150)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    msg.anim = anim

def show_modern_question(parent, title, text):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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


class CheckboxDelegate(QStyledItemDelegate):
    def __init__(self, theme="dark", parent=None):
        super().__init__(parent)
        self.theme = theme

    def setTheme(self, theme):
        self.theme = theme

    def paint(self, painter, option, index):
        value = index.data(Qt.ItemDataRole.CheckStateRole)
        if value is not None:
            # ✅ Cast int -> Qt.CheckState
            try:
                state = Qt.CheckState(value)
            except Exception:
                state = Qt.CheckState.Unchecked

            rect = self.get_checkbox_rect(option)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if state == Qt.CheckState.Checked:
                # kotak oranye saat dicentang
                painter.setBrush(QColor("#ff9900"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect, 4, 4)

                # centang putih (buat sedikit lebih tebal/proporsional)
                painter.setPen(QPen(QColor("white"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(rect.left() + 3, rect.center().y(),
                                rect.center().x() - 1, rect.bottom() - 4)
                painter.drawLine(rect.center().x() - 1, rect.bottom() - 4,
                                rect.right() - 3, rect.top() + 3)
            else:
                if self.theme == "dark":
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor("white"), 1))
                    painter.drawRoundedRect(rect, 4, 4)
                else:
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
            raw = index.data(Qt.ItemDataRole.CheckStateRole)
            try:
                current = Qt.CheckState(raw)
            except Exception:
                current = Qt.CheckState.Unchecked

            new_state = (Qt.CheckState.Unchecked if current == Qt.CheckState.Checked
                        else Qt.CheckState.Checked)

            # ❌ was: model.setData(index, int(new_state), Qt.ItemDataRole.CheckStateRole)
            # ✅ kirim enum langsung
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

# === DB utama ===
DB_NAME = os.path.join(BASE_DIR, "app.db")


#####################################*************########################################
#####################################*************########################################
#####################################*************########################################
def is_dev_mode_requested():
    """Cek apakah mode Dev diaktifkan via environment variable atau argumen CLI."""
    if os.getenv("NEXVO_DEV_MODE", "") == "1":
        return True
    if "--dev" in sys.argv:
        return True
    return False


def confirm_dev_mode(parent=None):
    """
    Jika ada password dev di environment variable, minta password dulu.
    Jika tidak, hanya tampilkan konfirmasi yes/no.
    """
    dev_pw = os.getenv("NEXVO_DEV_PASSWORD", "").strip()
    if dev_pw:
        pw, ok = QInputDialog.getText(
            parent, "Dev Mode",
            "Masukkan DEV password:",
            echo=QInputDialog.EchoMode.Password
        )
        if not ok:
            return False
        return pw == dev_pw
    else:
        ans = QMessageBox.question(
            parent, "Dev Mode",
            "Jalankan aplikasi dalam MODE DEV (bypass login & OTP)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return ans == QMessageBox.StandardButton.Yes
#####################################*************########################################
#####################################*************########################################
#####################################*************########################################

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
# Filter Sidebar (right dock)
# =====================================================
class FilterSidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Main layout untuk widget utama
        main_container_layout = QVBoxLayout(self)
        main_container_layout.setContentsMargins(0, 0, 0, 0)
        main_container_layout.setSpacing(0)
        
        # Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget yang akan di-scroll
        scroll_content = QWidget()
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)


        # Form layout dengan spacing dan margin yang lebih baik
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form_layout.setSpacing(6)
        form_layout.setContentsMargins(0, 0, 0, 0)

        # Tanggal Update
        tgl_update_layout = QHBoxLayout()
        tgl_update_layout.setContentsMargins(0, 0, 0, 0)
        self.tgl_update = QLineEdit()
        self.tgl_update.setPlaceholderText("Tanggal Update")
        tgl_update_layout.addWidget(self.tgl_update)
        form_layout.addRow(tgl_update_layout)

        # Nama
        nama_layout = QHBoxLayout()
        nama_layout.setContentsMargins(0, 0, 0, 0)
        self.nama = QLineEdit()
        self.nama.setPlaceholderText("Nama")
        nama_layout.addWidget(self.nama)
        form_layout.addRow(nama_layout)

        # NIK & NKK
        nik_nkk_layout = QHBoxLayout()
        nik_nkk_layout.setContentsMargins(0, 0, 0, 0)
        nik_nkk_layout.setSpacing(4)
        self.nik = QLineEdit()
        self.nik.setPlaceholderText("NIK")
        self.nkk = QLineEdit()
        self.nkk.setPlaceholderText("NKK")
        nik_nkk_layout.addWidget(self.nik)
        nik_nkk_layout.addWidget(self.nkk)
        form_layout.addRow(nik_nkk_layout)

        # Tanggal Lahir
        tgl_lahir_layout = QHBoxLayout()
        tgl_lahir_layout.setContentsMargins(0, 0, 0, 0)
        self.tgl_lahir = QLineEdit()
        self.tgl_lahir.setPlaceholderText("Tanggal Lahir (Format : DD|MM|YYYY)")
        tgl_lahir_layout.addWidget(self.tgl_lahir)
        form_layout.addRow(tgl_lahir_layout)

        # Umur slider
        umur_layout = QHBoxLayout()
        umur_layout.setContentsMargins(0, 0, 0, 0)
        umur_layout.setSpacing(4)
        self.umur_slider = QSlider(Qt.Orientation.Horizontal)
        self.umur_slider.setMinimum(0)
        self.umur_slider.setMaximum(100)
        self.umur_slider.setValue(0)
        self.umur_label = QLabel("0")
        self.umur_label.setMinimumWidth(20)
        self.umur_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.umur_slider.valueChanged.connect(self.update_umur_label)
        umur_layout.addWidget(self.umur_slider)
        umur_layout.addWidget(self.umur_label)
        form_layout.addRow("Umur", umur_layout)

        main_layout.addLayout(form_layout)

        # Dropdowns and Alamat
        grid_layout = QGridLayout()
        grid_layout.setSpacing(4)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        self.keterangan = QComboBox()
        self.kelamin = QComboBox()
        self.kawin = QComboBox()
        self.disabilitas = QComboBox()
        self.ktp_el = QComboBox()
        self.sumber = QComboBox()
        self.rank = QComboBox()
        self.alamat = QLineEdit()
        self.alamat.setPlaceholderText("Alamat")

        self.keterangan.addItems([
            "Keterangan",
            "1 (Meninggal)",
            "2 (Ganda)",
            "3 (Di Bawah Umur)",
            "4 (Pindah Domisili)",
            "5 (WNA)",
            "6 (TNI)",
            "7 (Polri)",
            "8 (Salah TPS)",
            "U (Ubah)",
            "90 (Keluar Loksus)",
            "91 (Meninggal)",
            "92 (Ganda)",
            "93 (Di Bawah Umur)",
            "94 (Pindah Domisili)",
            "95 (WNA)",
            "96 (TNI)",
            "97 (Polri)"
        ])
        self.kelamin.addItems(["Kelamin", "L", "P"])
        self.kawin.addItems(["Kawin", "S", "B", "P"])
        self.disabilitas.addItems(["Disabilitas", "0", "1", "2", "3", "4"])
        self.ktp_el.addItems(["KTP-el", "B", "K", "S"])
        self.sumber.addItems(["Sumber", "DP4", "DPTb", "DPK"])
        self.rank.addItems(["Rank"]) # Placeholder

        grid_layout.addWidget(self.keterangan, 0, 0)
        grid_layout.addWidget(self.kelamin, 0, 1)
        grid_layout.addWidget(self.kawin, 0, 2)
        grid_layout.addWidget(self.disabilitas, 1, 0)
        grid_layout.addWidget(self.ktp_el, 1, 1)
        grid_layout.addWidget(self.sumber, 1, 2)
        grid_layout.addWidget(self.alamat, 2, 0, 1, 2)
        grid_layout.addWidget(self.rank, 2, 2)
        main_layout.addLayout(grid_layout)

        # Checkboxes
        checkbox_layout = QGridLayout()
        checkbox_layout.setSpacing(4)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.cb_ganda = QCheckBox("Ganda")
        self.cb_invalid_tgl = QCheckBox("Invalid Tgl")
        self.cb_nkk_terpisah = QCheckBox("NKK Terpisah")
        self.cb_analisis_tms = QCheckBox("Analisis TMS 8")
        checkbox_layout.addWidget(self.cb_ganda, 0, 0)
        checkbox_layout.addWidget(self.cb_invalid_tgl, 0, 1)
        checkbox_layout.addWidget(self.cb_nkk_terpisah, 1, 0)
        checkbox_layout.addWidget(self.cb_analisis_tms, 1, 1)
        main_layout.addLayout(checkbox_layout)

        # Radio Buttons
        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(6)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        self.rb_reguler = QRadioButton("Reguler")
        self.rb_khusus = QRadioButton("Khusus")
        self.rb_reguler_khusus = QRadioButton("Reguler & Khusus")
        self.rb_reguler_khusus.setChecked(True)
        radio_layout.addWidget(self.rb_reguler)
        radio_layout.addWidget(self.rb_khusus)
        radio_layout.addWidget(self.rb_reguler_khusus)
        main_layout.addLayout(radio_layout)

        # Separator line sebelum tombol
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(line)

        # Buttons dengan style yang lebih baik
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 5)
        btn_layout.setSpacing(8)
        
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setObjectName("resetBtn")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.btn_filter = QPushButton("Filter")
        self.btn_filter.setObjectName("filterBtn")
        self.btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.btn_reset.clicked.connect(self.reset_filters)
        # Note: parent (MainWindow) will connect btn_reset.clicked to clear filters
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_filter)
        main_layout.addLayout(btn_layout)
        
        # Set scroll content widget
        scroll_area.setWidget(scroll_content)
        main_container_layout.addWidget(scroll_area)

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
        
        return {
            "nama": self.nama.text().strip(),
            "nik": self.nik.text().strip(),
            "nkk": self.nkk.text().strip(),
            "tgl_lahir": self.tgl_lahir.text().strip(),
            "umur": self.umur_slider.value(),
            "keterangan": keterangan_value,
            "jk": self.kelamin.currentText() if self.kelamin.currentText() != "Kelamin" else "",
            "sts": self.kawin.currentText() if self.kawin.currentText() != "Kawin" else "",
            "dis": self.disabilitas.currentText() if self.disabilitas.currentText() != "Disabilitas" else "",
            "ktpel": self.ktp_el.currentText() if self.ktp_el.currentText() != "KTP-el" else "",
            "sumber": self.sumber.currentText() if self.sumber.currentText() != "Sumber" else ""
        }
    
    def apply_theme(self, mode: str):
        """Hanya styling FilterSidebar. Jangan sentuh objek milik MainWindow."""
        if mode == "dark":
            self.setStyleSheet("""
                QWidget { font-family: 'Segoe UI','Calibri'; font-size: 9px; background: #1e1e1e; color: #d4d4d4; }
                QScrollArea { border: none; background: #1e1e1e; }
                QScrollBar:vertical { border: none; background: #3e3e42; width: 6px; margin: 0; }
                QScrollBar::handle:vertical { background: #666; border-radius: 3px; min-height: 20px; }
                QScrollBar::handle:vertical:hover { background: #888; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

                QLineEdit, QComboBox {
                    padding: 6px 8px; border: 1px solid #555; border-radius: 3px;
                    background: #2d2d30; min-height: 20px; color: #d4d4d4; font-size: 9px;
                }
                QLineEdit:focus, QComboBox:focus { border: 1px solid #ff9800; outline: none; }
                QLineEdit::placeholder { color: #888; }

                QLabel { color: #d4d4d4; padding: 1px; background: transparent; font-size: 9px; }

                QPushButton {
                    padding: 8px 20px; border: none; border-radius: 3px; font-weight: bold;
                    min-width: 70px; font-size: 10px; color: white; background: #ff9800;
                }
                QPushButton:hover { background: #fb8c00; }
                QPushButton:pressed { background: #f57c00; }

                QCheckBox { padding: 2px; spacing: 4px; color: #d4d4d4; background: transparent; font-size: 9px; }
                QCheckBox::indicator {
                    width: 14px; height: 14px; border: 2px solid #555; border-radius: 2px; background: #2d2d30;
                }
                QCheckBox::indicator:checked { border-color: #ff9800; }

                QRadioButton { spacing: 4px; padding: 2px; color: #d4d4d4; background: transparent; font-size: 9px; }
                QRadioButton::indicator {
                    width: 12px; height: 12px; border: 2px solid #555; border-radius: 7px; background: #2d2d30;
                }
                QRadioButton::indicator:checked { background: #ff9800; border-color: #ff9800; }

                QSlider::groove:horizontal { border: none; height: 3px; background: #555; margin: 0; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background: #ff9800; border: 2px solid #2d2d30; width: 14px; height: 14px; margin: -6px 0; border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget { font-family: 'Segoe UI','Calibri'; font-size: 9px; background: white; color: #333; }
                QScrollArea { border: none; background: white; }
                QScrollBar:vertical { border: none; background: #f0f0f0; width: 6px; margin: 0; }
                QScrollBar::handle:vertical { background: #ccc; border-radius: 3px; min-height: 20px; }
                QScrollBar::handle:vertical:hover { background: #aaa; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

                QLineEdit, QComboBox {
                    padding: 6px 8px; border: 1px solid #ddd; border-radius: 3px;
                    background: white; min-height: 20px; color: #333; font-size: 9px;
                }
                QLineEdit:focus, QComboBox:focus { border: 1px solid #4CAF50; outline: none; }
                QLineEdit::placeholder { color: #999; }

                QLabel { color: #666; padding: 1px; background: transparent; font-size: 9px; }

                QPushButton {
                    padding: 8px 20px; border: none; border-radius: 3px; font-weight: bold;
                    min-width: 70px; font-size: 10px; color: white; background: #ff9800;
                }
                QPushButton:hover { background: #fb8c00; }
                QPushButton:pressed { background: #f57c00; }

                QCheckBox { padding: 2px; spacing: 4px; color: #333; background: transparent; font-size: 9px; }
                QCheckBox::indicator {
                    width: 14px; height: 14px; border: 2px solid #ddd; border-radius: 2px; background: white;
                }
                QCheckBox::indicator:checked { border-color: #4CAF50; }

                QRadioButton { spacing: 4px; padding: 2px; color: #333; background: transparent; font-size: 9px; }
                QRadioButton::indicator {
                    width: 12px; height: 12px; border: 2px solid #ddd; border-radius: 7px; background: white;
                }
                QRadioButton::indicator:checked { background: #2196F3; border-color: #2196F3; }

                QSlider::groove:horizontal { border: none; height: 3px; background: #e0e0e0; margin: 0; border-radius: 2px; }
                QSlider::handle:horizontal {
                    background: #2196F3; border: 2px solid white; width: 14px; height: 14px; margin: -6px 0; border-radius: 8px;
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
        self._init_db_pragmas()

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
            "STS","ALAMAT","RT","RW","DIS","KTPel","SUMBER","KET","TPS","LastUpdate","CEK_DATA"
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setFixedHeight(24)
        mode = self.load_theme()
        self.checkbox_delegate = CheckboxDelegate("dark" if mode == "dark" else "light", self.table)
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
            "CEK_DATA": 200
        }
        for idx, col in enumerate(columns):
            if col in col_widths:
                self.table.setColumnWidth(idx, col_widths[col])

        # Flag & koneksi sinkronisasi checkbox baris -> header
        self._header_bulk_toggling = False
        try:
            self.table.itemChanged.disconnect(self._on_row_checkbox_changed_for_header_sync)
        except Exception:
            pass
        self.table.itemChanged.connect(self._on_row_checkbox_changed_for_header_sync)

        # === Auto resize kolom sesuai isi, tapi tetap bisa manual resize ===
        # === Header dan sorting klik ===
        self.connect_header_events()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 30)
        self.table.horizontalHeader().setStretchLastSection(True)
        QTimer.singleShot(0, self.init_header_checkbox)

        self.pagination_container = QWidget()
        self.pagination_layout = QHBoxLayout(self.pagination_container)
        self.pagination_layout.setContentsMargins(0, 2, 0, 2)
        self.pagination_layout.setSpacing(4)
        self.pagination_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Halaman Data (tetap hidup selama app jalan)
        self.data_page = QWidget()
        v = QVBoxLayout(self.data_page)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.table)
        v.addWidget(self.pagination_container)

        # --- Stack: penampung semua halaman (Data & Dashboard)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.data_page)         # index 0 = Data
        self.setCentralWidget(self.stack)

        # Flag posisi halaman
        self._is_on_dashboard = False

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
        action_dashboard.triggered.connect(self.show_dashboard_page)
        file_menu.addAction(action_dashboard)

        action_pemutakhiran = QAction("  Pemutakhiran Data", self)
        action_pemutakhiran.setShortcut("Alt+C")
        action_pemutakhiran.triggered.connect(self.show_data_page)
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

        # ============================================================
        # 🧭 Tema Dark & Light — dengan style elegan & soft disabled
        # ============================================================
        self.action_dark = QAction("  Dark", self, shortcut="Ctrl+D")
        self.action_light = QAction("  Light", self, shortcut="Ctrl+L")

        # Hubungkan ke fungsi apply_theme
        self.action_dark.triggered.connect(lambda: self.apply_theme("dark"))
        self.action_light.triggered.connect(lambda: self.apply_theme("light"))

        view_menu.addAction(self.action_dark)
        view_menu.addAction(self.action_light)

        # 🎨 Style menu agar efek disabled tampak lembut & modern
        view_menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #ff9900;
                color: black;
            }
            QMenu::item:disabled {
                color: rgba(100, 100, 100, 130);
                background: transparent;
                font-style: italic;
            }
        """)

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
        btn_cekdata.clicked.connect(self.cek_data)
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

    # --- Batch flags & stats (aman dari AttributeError) ---
        self._batch_stats = {"ok": 0, "rejected": 0, "skipped": 0}
        self._in_batch_mode = False
        self._warning_shown_in_batch = {}
        self._install_safe_shutdown_hooks()

    def _on_row_checkbox_changed_for_header_sync(self, item):
        # Hanya respons kalau kolom checkbox (kolom 0) yang berubah
        if item and item.column() == 0 and not getattr(self, "_header_bulk_toggling", False):
            QTimer.singleShot(0, self.sync_header_checkbox_state)


    def show_setting_dialog(self):
        dlg = SettingDialog(self, self.db_name)
        if dlg.exec():
            self.apply_column_visibility()
            self.auto_fit_columns()
    
    def toggle_filter_sidebar(self):
        if self.filter_dock is None:
            self.filter_sidebar = FilterSidebar(self)
            self.filter_dock = QDockWidget("Filter", self)
            self.filter_dock.setWidget(self.filter_sidebar)
            self.filter_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
            self.filter_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)

            # Terapkan tema
            current_theme = self.load_theme()
            self.filter_sidebar.apply_theme(current_theme)

            # Tambahkan ke main window
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.filter_dock)

            # >>> PASANG DROP SHADOW DI SINI <<<
            eff = QGraphicsDropShadowEffect(self.filter_dock)
            eff.setBlurRadius(18)
            eff.setOffset(0, 4)
            eff.setColor(QColor(0, 0, 0, 140))
            self.filter_dock.setGraphicsEffect(eff)

            # Opsi: ukuran awal
            self.filter_dock.setMinimumWidth(300)
            self.filter_dock.setMaximumWidth(400)

            # Koneksi tombol sidebar
            self.filter_sidebar.btn_filter.clicked.connect(self.apply_filters)
            self.filter_sidebar.btn_reset.clicked.connect(self.clear_filters)

        # Sinkron tema & header checkbox tiap toggle (opsional)
        current_theme = self.load_theme()
        self.table.viewport().update()
        QTimer.singleShot(0, self.position_header_checkbox)

        # Toggle tampil/sembunyi
        if self.filter_dock.isVisible():
            self.filter_dock.hide()
        else:
            self.filter_dock.show()
    
    def apply_filters(self):
        """Apply filters from the filter sidebar"""
        if not self.filter_sidebar:
            return
            
        filters = self.filter_sidebar.get_filters()
        
        # Store original data if not already stored
        if not hasattr(self, 'original_data') or self.original_data is None:
            self.original_data = self.all_data.copy()
        
        # Filter self.all_data based on the filters
        filtered_data = []
        for item in self.all_data:
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
                print(f"[INFO] Database terenkripsi ulang: {self.enc_path}")
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

    def apply_theme(self, mode: str):
        """
        Menerapkan tema aplikasi (dark / light) dengan aman.
        Tidak menimbulkan error meskipun berada di Dashboard.
        """
        # =====================================================
        # 🧩 1️⃣ Cegah perubahan tema saat di Dashboard
        # =====================================================
        if getattr(self, "_is_on_dashboard", False):
            show_modern_info(self, "Info", "Mode tema tidak dapat diubah saat di Dashboard.")
            return

        # =====================================================
        # 🎨 2️⃣ Terapkan palet global Qt
        # =====================================================
        app = QApplication.instance()
        apply_global_palette(app, mode)

        # =====================================================
        # 🌗 3️⃣ Terapkan gaya utama per tema
        # =====================================================
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

        # =====================================================
        # 🧱 4️⃣ Update sidebar / komponen tambahan
        # =====================================================
        if hasattr(self, "filter_sidebar") and self.filter_sidebar is not None:
            try:
                self.filter_sidebar.apply_theme(mode)
            except Exception:
                pass

        # =====================================================
        # 💾 5️⃣ Simpan pilihan tema ke database
        # =====================================================
        try:
            self.save_theme(mode)
        except Exception as e:
            print("Gagal menyimpan tema:", e)

        # =====================================================
        # 📊 6️⃣ Refresh tampilan tabel jika halaman aktif adalah data
        # =====================================================
        if hasattr(self, "table") and not getattr(self, "_is_on_dashboard", False):
            try:
                central = self.centralWidget()
                if isinstance(central, QWidget) and self.table in central.findChildren(QTableWidget):
                    # Refresh isi tabel sesuai halaman aktif
                    self.show_page(self.current_page)

                # Update checkbox dan posisi header
                self.checkbox_delegate.setTheme("dark" if mode == "dark" else "light")
                self.table.viewport().update()
                QTimer.singleShot(0, self.position_header_checkbox)

            except RuntimeError:
                # Jika table sudah dilepas Qt (misalnya saat sedang ganti halaman)
                pass
            except Exception as e:
                print("Warning saat update tabel:", e)

        # =====================================================
        # 🧭 7️⃣ Update status bar agar pengguna tahu mode aktif
        # =====================================================
        #if hasattr(self, "status"):
            #theme_text = "Mode Gelap" if mode == "dark" else "Mode Terang"
            #self.status.showMessage(f"Tema diperbarui: {theme_text}")


    # =========================================================
    # DASHBOARD PAGE
    # =========================================================
    def show_dashboard_page(self):
        """Tampilkan Dashboard elegan (dengan animasi, tanpa status bar)."""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect, QToolBar
        from PyQt6.QtGui import QIcon
        import os

        # === Pastikan ikon aplikasi (KPU.png) muncul di kiri atas ===
        icon_path = os.path.join(os.path.dirname(__file__), "KPU.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # === Siapkan dashboard jika belum ada ===
        if not hasattr(self, "dashboard_page"):
            self.dashboard_page = self._build_dashboard_widget()
            self.stack.addWidget(self.dashboard_page)

        self._is_on_dashboard = True

        # === Sembunyikan toolbar & filter ===
        for tb in self.findChildren(QToolBar):
            tb.hide()
        if hasattr(self, "filter_dock") and self.filter_dock:
            self.filter_dock.hide()

        # === Status bar tetap ada tapi hanya menampilkan versi NexVo ===
        if self.statusBar():
            self.statusBar().showMessage("NexVo v1.0")

        # === Nonaktifkan tema sementara ===
        self.action_dark.setEnabled(False)
        self.action_light.setEnabled(False)
        for act in [self.action_dark, self.action_light]:
            f = act.font()
            f.setItalic(True)
            act.setFont(f)

        # === Fade-in Dashboard ===
        self._stack_fade_to(self.dashboard_page, duration=600)


    def _build_dashboard_widget(self) -> QWidget:
        """Bangun halaman Dashboard modern, elegan, dan bersih."""
        import os
        from PyQt6.QtCharts import QChart, QChartView, QPieSeries, QLegend
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
            QGraphicsDropShadowEffect, QGraphicsOpacityEffect
        )
        from PyQt6.QtGui import QColor, QPainter, QFont, QPixmap
        from PyQt6.QtCore import Qt, QMargins, QPropertyAnimation, QEasingCurve

        # === ROOT DASHBOARD ===
        dash_widget = QWidget()
        dash_layout = QVBoxLayout(dash_widget)
        dash_layout.setContentsMargins(30, 0, 30, 10)
        dash_layout.setSpacing(25)

        # === HEADER ===
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        logo_path = os.path.join(os.path.dirname(__file__), "KPU.png")
        logo = QLabel()
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(
                42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            logo.setPixmap(pix)
        else:
            logo.setText("🗳️")

        title_lbl = QLabel("Sidalih Pilkada 2024 Desktop – Pemutakhiran Data")
        title_lbl.setStyleSheet("font-size:14pt; font-weight:600; color:#333;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        header.addWidget(logo)
        header.addWidget(title_lbl)
        header.addStretch()

        header_frame = QFrame()
        header_frame.setLayout(header)
        dash_layout.addWidget(header_frame)
        dash_layout.addSpacing(-50)

        # === Fade-in untuk header ===
        header_effect = QGraphicsOpacityEffect(header_frame)
        header_frame.setGraphicsEffect(header_effect)
        header_anim = QPropertyAnimation(header_effect, b"opacity")
        header_anim.setDuration(800)
        header_anim.setStartValue(0.0)
        header_anim.setEndValue(1.0)
        header_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        header_anim.start()

        # === KARTU RINGKASAN ===
        top_row = QHBoxLayout()
        top_row.setSpacing(15)

        def make_card(icon, title, value):
            """Kartu elegan tanpa border luar, semua center."""
            card = QFrame()
            card.setMinimumWidth(150)
            card.setMaximumWidth(220)
            lay = QVBoxLayout(card)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_icon = QLabel(icon)
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_icon.setStyleSheet("font-size:30pt; color:#ff6600;")

            lbl_value = QLabel(value)
            lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_value.setStyleSheet("font-size:18pt; font-weight:700; color:#222;")

            lbl_title = QLabel(title)
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_title.setStyleSheet("font-size:10pt; color:#777;")

            for w in (lbl_icon, lbl_value, lbl_title):
                lay.addWidget(w)

            sh = QGraphicsDropShadowEffect()
            sh.setBlurRadius(25)
            sh.setOffset(0, 3)
            sh.setColor(QColor(0, 0, 0, 40))
            card.setGraphicsEffect(sh)
            card.setStyleSheet("background:#fff; border-radius:12px;")
            return card

            # 🪪🤴👸♀️♂️⚧️📠📖📚📬📫📮🗓️🏛️🏦👧🏻👦🏻📌🚩🚹🚺🚻🏠
        cards = [
            ("🏦", "Nama Desa", "Sukasenang"),
            ("🚻", "Pemilih", "1.439.738"),
            ("🚹", "Laki-laki", "728.475"),
            ("🚺", "Perempuan", "711.263"),
            ("🏠", "Kelurahan", "351"),
            ("🚩", "TPS", "2.847"),
        ]
        for icon, title, value in cards:
            top_row.addWidget(make_card(icon, title, value))
        dash_layout.addLayout(top_row)

        # === PIE DONUT + BAR ===
        middle_row = QHBoxLayout()
        middle_row.setSpacing(40)

        # === PIE DONUT ===
        series = QPieSeries()
        series.append("Laki-laki", 50.6)
        series.append("Perempuan", 49.4)

        series.slices()[0].setBrush(QColor("#6b4e71"))
        series.slices()[1].setBrush(QColor("#ff6600"))
        for s in series.slices():
            s.setLabelVisible(False)
            s.setBorderColor(Qt.GlobalColor.transparent)
        series.setHoleSize(0.65)

        chart = QChart()
        chart.addSeries(series)
        chart.setBackgroundVisible(False)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setMarkerShape(QLegend.MarkerShape.MarkerShapeFromSeries)
        chart.setMargins(QMargins(10, 10, 10, 10))

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumSize(330, 280)
        chart_view.setStyleSheet("background:#fff; border-radius:12px;")

        class ChartContainer(QFrame):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setMinimumSize(330, 230)
                self.setStyleSheet("background:#fff; border-radius:12px;")
                self._center_label = None

            def set_center_label(self, label: QLabel):
                self._center_label = label
                self._reposition_label()

            def resizeEvent(self, event):
                self._reposition_label()
                super().resizeEvent(event)

            def _reposition_label(self):
                if self._center_label:
                    self._center_label.setGeometry(0, 0, self.width(), self.height())
                    self._center_label.raise_()

        chart_container = ChartContainer()
        cc_layout = QVBoxLayout(chart_container)
        cc_layout.setContentsMargins(0, 0, 0, 0)
        cc_layout.addWidget(chart_view)

        # === Label tengah terdiri dari dua bagian (judul + nilai)
        center_widget = QWidget(chart_container)
        center_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        center_widget.setStyleSheet("background:transparent;")

        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(2)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_center_title = QLabel("Laki-laki")
        lbl_center_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_center_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_center_title.setStyleSheet("color:#444; background:transparent;")

        lbl_center_value = QLabel("50.6%")
        lbl_center_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_center_value.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        lbl_center_value.setStyleSheet("color:#222; background:transparent;")

        center_layout.addWidget(lbl_center_title)
        center_layout.addWidget(lbl_center_value)

        # Pasang widget label ke tengah lingkaran
        chart_container.set_center_label(center_widget)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 50))
        chart_container.setGraphicsEffect(shadow)

        def update_center_label(slice_obj):
            lbl_center_title.setText(slice_obj.label())
            lbl_center_value.setText(f"{slice_obj.value():.1f}%")

        def handle_hovered(state, slice_obj):
            slice_obj.setExploded(state)
            if state:
                update_center_label(slice_obj)

        for sl in series.slices():
            sl.setExploded(False)
            sl.setExplodeDistanceFactor(0.05)
            sl.hovered.connect(lambda state, s=sl: handle_hovered(state, s))
            sl.clicked.connect(lambda _checked, s=sl: update_center_label(s))

        middle_row.addWidget(chart_container, 0)
        #middle_row.addSpacing(10)

        # === BAR HORIZONTAL ===
        bar_frame = QFrame()
        bar_layout = QVBoxLayout(bar_frame)
        bar_layout.setSpacing(14)
        bar_layout.setContentsMargins(5, 35, 20, 35)

        bars = [
            ("Meninggal", 0.051), ("Ganda", 0.002), ("Di Bawah Umur", 0.000),
            ("Pindah Domisili", 0.019), ("WNA", 0.000), ("TNI", 0.000),
            ("Polri", 0.000), ("Salah TPS", 0.017),
        ]

        for label, val in bars:
            row = QHBoxLayout()
            row.setSpacing(0)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size:10pt; color:#555; min-width:115px;")

            bg = QFrame()
            bg.setFixedHeight(8)
            bg.setMaximumWidth(280)
            bg.setStyleSheet("background:#eee; border-radius:2px;")

            inner = QHBoxLayout(bg)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(0)

            fg = QFrame()
            fg.setFixedHeight(8)
            fg.setStyleSheet("background:#ff6600; border-radius:2px;")

            base_ratio = 0.9
            stretch_val = max(1, min(int(val * 100 * base_ratio), 80))
            inner.addWidget(fg, stretch_val)
            inner.addStretch(100 - stretch_val)

            pct = QLabel(f"{val:.3%}")
            pct.setStyleSheet("font-size:10pt; color:#333; min-width:55px; text-align:right;")

            bar_group = QHBoxLayout()
            bar_group.setSpacing(6)
            bar_group.addWidget(bg)
            bar_group.addWidget(pct)

            wrapper = QFrame()
            wrapper_layout = QHBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(-35, 0, 0, 0)
            wrapper_layout.addLayout(bar_group)

            row.addWidget(lbl)
            row.addWidget(wrapper)
            bar_layout.addLayout(row)

        middle_row.addWidget(bar_frame, 2)
        dash_layout.addLayout(middle_row)

        # === STYLE GLOBAL ===
        dash_widget.setStyleSheet("""
            QWidget { background:#f9f9f9; color:#333; font-family:'Segoe UI','Calibri'; }
            QLabel { color:#333; }
        """)
        return dash_widget
    
    def _stack_fade_to(self, target_widget, duration=350):
        """Fade-in ke target page di QStackedWidget (aman, tanpa hapus widget)."""
        self.stack.setCurrentWidget(target_widget)

        # Nonaktifkan sementara update untuk mencegah konflik painter
        target_widget.setUpdatesEnabled(False)

        eff = QGraphicsOpacityEffect(target_widget)
        target_widget.setGraphicsEffect(eff)
        eff.setOpacity(0.0)

        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Setelah selesai, aktifkan kembali update
        def on_finished():
            target_widget.setUpdatesEnabled(True)
            target_widget.update()  # paksa repaint final agar tampil sempurna
            target_widget.setGraphicsEffect(None)

        anim.finished.connect(on_finished)
        anim.start()

        # Simpan referensi supaya animasi tidak berhenti mendadak
        self._fade_anim = anim
        
    def show_data_page(self):
        """Kembali ke halaman utama Data."""
        from PyQt6.QtWidgets import QToolBar

        self._is_on_dashboard = False

        # Tampilkan lagi toolbar & status bar
        for tb in self.findChildren(QToolBar):
            tb.show()
        if self.statusBar():
            self.statusBar().show()

        if hasattr(self, "filter_dock") and self.filter_dock:
            self.filter_dock.hide()

        # Aktifkan lagi kontrol tema
        self.action_dark.setEnabled(True)
        self.action_light.setEnabled(True)
        for act in [self.action_dark, self.action_light]:
            f = act.font()
            f.setItalic(False)
            act.setFont(f)

        # Pindah page ke Data
        self._stack_fade_to(self.data_page, duration=300)
        try:
            self.show_page(getattr(self, "_last_page_index", self.current_page))
        except Exception:
            pass

    # =========================================================
    # 🔸 Fungsi bantu animasi transisi
    # =========================================================
    def _fade_transition(self, old_widget, new_widget, duration=400):
        """Efek transisi fade-in/out antara dua widget."""
        # Step 1: Opacity effect
        old_effect = QGraphicsOpacityEffect(old_widget)
        old_widget.setGraphicsEffect(old_effect)

        new_effect = QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(new_effect)
        new_effect.setOpacity(0)

        # Step 2: Tambahkan widget baru di posisi yang sama sementara
        old_widget.setVisible(True)
        new_widget.setVisible(True)
        self.setCentralWidget(new_widget)

        # Step 3: Buat animasi fade-out untuk lama, fade-in untuk baru
        anim_out = QPropertyAnimation(old_effect, b"opacity")
        anim_out.setDuration(duration)
        anim_out.setStartValue(1.0)
        anim_out.setEndValue(0.0)
        anim_out.setEasingCurve(QEasingCurve.Type.InOutCubic)

        anim_in = QPropertyAnimation(new_effect, b"opacity")
        anim_in.setDuration(duration)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)
        anim_in.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Jalankan animasi
        anim_out.start()
        anim_in.start()

        # Simpan agar tidak di-garbage collect
        self._fade_anims = (anim_out, anim_in)


    def _slide_transition(self, old_widget, new_widget, direction="left", duration=450):
        """Transisi geser elegan antar halaman (aman dari widget deletion)."""
        # 🛡️ Pastikan widget valid
        if old_widget is None or new_widget is None:
            self.setCentralWidget(new_widget)
            return
        try:
            if old_widget.parent() is None or new_widget.parent() is None:
                self.setCentralWidget(new_widget)
                return
        except RuntimeError:
            # Kalau sudah dihapus Qt (C++ object deleted)
            self.setCentralWidget(new_widget)
            return

        # 🧭 Jalankan animasi aman
        geo = self.centralWidget().geometry()
        w, h = geo.width(), geo.height()
        new_widget.setGeometry(geo)

        # Posisi awal berdasarkan arah transisi
        start_rect = QRect(0, 0, w, h)
        if direction == "left":
            start_rect.moveTo(w, 0)
        elif direction == "right":
            start_rect.moveTo(-w, 0)

        new_widget.setGeometry(start_rect)
        self.setCentralWidget(new_widget)

        # Animasi geser halus
        anim = QPropertyAnimation(new_widget, b"geometry")
        anim.setDuration(duration)
        anim.setStartValue(start_rect)
        anim.setEndValue(geo)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

        # Simpan referensi supaya animasi tidak dihentikan premature
        self._slide_anim = anim

    
    def auto_fit_columns(self):
        header = self.table.horizontalHeader()
        self.table.resizeColumnsToContents()

        max_widths = {
            "CEK_DATA": 200,   # cukup untuk yyyy-mm-dd
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

    # === Checkbox di Header Kolom Pertama (Select All) ===
    def init_header_checkbox(self):
        header = self.table.horizontalHeader()
        self.header_checkbox = QCheckBox(header)
        self.header_checkbox.setToolTip("Centang semua / batalkan semua")
        self.header_checkbox.setTristate(False)
        self.header_checkbox.setChecked(False)

        # Tema
        theme = self.load_theme()
        if theme == "dark":
            self.header_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 12px; height: 12px;
                    border: 2px solid #ff9900;
                    border-radius: 4px;
                    background: #1e1e1e;
                }
                QCheckBox::indicator:checked { background-color: #ff9900; }
            """)
        else:
            self.header_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 12px; height: 12px;
                    border: 2px solid #555;
                    border-radius: 4px;
                    background: white;
                }
                QCheckBox::indicator:checked { background-color: #ff9900; }
            """)

        # 🔗 Sinyal
        self.header_checkbox.pressed.connect(self._on_header_checkbox_pressed)  # ⬅️ TAMBAH INI
        self.header_checkbox.stateChanged.connect(self.toggle_all_rows_checkboxes)

        # Reposisi bila header berubah
        header.sectionResized.connect(self.position_header_checkbox)
        header.sectionMoved.connect(self.position_header_checkbox)
        header.geometriesChanged.connect(self.position_header_checkbox)
        QTimer.singleShot(0, self.position_header_checkbox)

    def _on_header_checkbox_pressed(self):
        st = self.header_checkbox.checkState()
        if st == Qt.CheckState.PartiallyChecked:
            # Jangan timpa sinyal berikutnya—cukup set langsung ke Checked.
            self.header_checkbox.setCheckState(Qt.CheckState.Checked)
            # Catatan: setCheckState di atas akan memicu stateChanged → toggle_all_rows_checkboxes()

    def position_header_checkbox(self):
        """Posisikan checkbox tepat di header kolom 0."""
        header = self.table.horizontalHeader()
        col = 0
        x = header.sectionViewportPosition(col)
        w = header.sectionSize(col)
        y = (header.height() - 16) // 2
        self.header_checkbox.setGeometry(x + (w - 16)//2, y, 16, 16)
        self.header_checkbox.raise_()
        self.header_checkbox.show()


    def toggle_all_rows_checkboxes(self, state):
        """Centang / hapus centang semua baris YANG TAMPIL (halaman aktif)."""
        # Pastikan tipe enum
        try:
            state = Qt.CheckState(state)
        except Exception:
            return

        # 🟠 KUNCI: anggap PartiallyChecked sebagai Checked (Select All)
        if state == Qt.CheckState.PartiallyChecked:
            state = Qt.CheckState.Checked

        if state not in (Qt.CheckState.Checked, Qt.CheckState.Unchecked):
            return

        checked = (state == Qt.CheckState.Checked)

        # Hindari loop sinyal
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):    # hanya baris yang tampil (halaman aktif)
            it = self.table.item(r, 0)
            if it is None:
                it = QTableWidgetItem()
                it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(r, 0, it)
            it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.table.blockSignals(False)

        self.table.viewport().update()
        self.update_statusbar()
        QTimer.singleShot(0, self.sync_header_checkbox_state)


    def sync_header_checkbox_state(self):
        """Selaraskan status header dengan baris yang sedang terlihat."""
        total = self.table.rowCount()
        if total == 0:
            self.header_checkbox.blockSignals(True)
            self.header_checkbox.setCheckState(Qt.CheckState.Unchecked)
            self.header_checkbox.blockSignals(False)
            return

        checked_cnt = 0
        for r in range(total):
            it = self.table.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                checked_cnt += 1

        self.header_checkbox.blockSignals(True)
        if checked_cnt == 0:
            self.header_checkbox.setCheckState(Qt.CheckState.Unchecked)
        elif checked_cnt == total:
            self.header_checkbox.setCheckState(Qt.CheckState.Checked)
        else:
            self.header_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        self.header_checkbox.blockSignals(False)

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
        # Deteksi tema aktif dari palet global
        palette = QApplication.instance().palette()
        bg_color = palette.color(QPalette.ColorRole.Window)
        brightness = (bg_color.red() + bg_color.green() + bg_color.blue()) / 3
        is_dark = brightness < 128  # kalau gelap → tema dark
        self.style_menu(menu, "dark" if is_dark else "light")
        # (alternatif, lebih konsisten dengan app)
        # self.style_menu(menu, self.load_theme())

        if is_dark:
            # 🌙 Tema Dark
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2d2d30;
                    color: white;
                    border: 1px solid #444;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::item {
                    padding: 6px 28px;
                    border-radius: 5px;
                    font-family: 'Segoe UI';
                    font-size: 10.5pt;
                }
                QMenu::item:selected {
                    background-color: #ff9900;
                    color: black;
                }
            """)
        else:
            # ☀️ Tema Light
            menu.setStyleSheet("""
                QMenu {
                    background-color: #f0eeee;
                    color: #000000;
                    border: 2px solid #000000;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::item {
                    padding: 6px 28px;
                    border-radius: 5px;
                    font-family: 'Segoe UI';
                    font-size: 10.5pt;
                }
                QMenu::item:selected {
                    background-color: #ffcc66;   /* hover kuning lembut */
                    color: #000000;
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

    # =============================
    # 🔧 Batch Stats Helpers
    # =============================
    def _batch_reset_stats(self):
        self._batch_stats = {"ok": 0, "rejected": 0, "skipped": 0}

    def _batch_add(self, key, func_name=None):
        # key ∈ {"ok","rejected","skipped"}
        if not hasattr(self, "_batch_stats"):
            self._batch_reset_stats()
        self._batch_stats[key] = self._batch_stats.get(key, 0) + 1

    def _context_action_wrapper(self, rows, func):
        """Menjalankan fungsi context untuk 1 atau banyak baris (versi super kilat penuh)."""
        if isinstance(rows, int):
            rows = [rows]

        # --- Inisialisasi atribut batch
        if not hasattr(self, "_batch_stats"):
            self._batch_stats = {"ok": 0, "rejected": 0, "skipped": 0}
        if not hasattr(self, "_warning_shown_in_batch"):
            self._warning_shown_in_batch = {}
        if not hasattr(self, "_in_batch_mode"):
            self._in_batch_mode = False

        is_batch = len(rows) > 1

        # --- Konfirmasi batch
        if is_batch:
            label_action = func.__name__.replace("_pemilih", "").replace("_", " ").title()
            if not show_modern_question(
                self, "Konfirmasi Batch",
                f"Anda yakin ingin memproses <b>{len(rows)}</b> data sebagai <b>{label_action}</b>?"
            ):
                self._clear_row_selection(rows)
                return
            self._in_batch_mode = True
            self._warning_shown_in_batch.clear()
            self._batch_stats = {"ok": 0, "rejected": 0, "skipped": 0}

        # --- Matikan update GUI
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)

        # --- Gunakan satu koneksi untuk batch
        shared_conn = shared_cur = None
        if is_batch:
            shared_conn = sqlite3.connect(self.db_name)
            shared_conn.execute("PRAGMA busy_timeout=3000;")
            shared_cur = shared_conn.cursor()
            self._shared_conn = shared_conn
            self._shared_cur = shared_cur

        try:
            for r in rows:
                func(r)
        finally:
            if shared_conn:
                shared_conn.commit()
                shared_cur.close()
                shared_conn.close()
                self._shared_conn = self._shared_cur = None

            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()

        # --- Ringkasan batch
        if is_batch:
            stats = self._batch_stats
            ok, rej = stats.get("ok", 0), stats.get("rejected", 0)
            self._in_batch_mode = False
            self._warning_shown_in_batch.clear()
            self._batch_stats = {"ok": 0, "rejected": 0, "skipped": 0}

            lines = [f"<b>Selesai memproses {len(rows)} data.</b><br>"]
            if ok:  lines.append(f"✔️ Berhasil: <b>{ok}</b><br>")
            if rej: lines.append(f"⛔ Ditolak: <b>{rej}</b><br>")
            if not ok and not rej:
                lines.append("<i>Tidak ada data yang berhasil atau ditolak.</i>")

            show_modern_info(self, "Ringkasan", "".join(lines))

        QTimer.singleShot(100, lambda: self._clear_row_selection(rows))

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
        dpid_item = self.table.item(row, self.col_index("DPID"))
        ket_item  = self.table.item(row, self.col_index("KET"))
        nama_item = self.table.item(row, self.col_index("NAMA"))

        dpid = dpid_item.text().strip() if dpid_item else ""
        ket  = ket_item.text().strip().upper() if ket_item else ""
        nama = nama_item.text().strip() if nama_item else ""

        # ⚠️ Validasi 1
        if not dpid or dpid == "0":
            if getattr(self, "_in_batch_mode", False):
                if not self._warning_shown_in_batch.get("aktifkan_pemilih", False):
                    #show_modern_warning(self, "Ditolak", "Data yang kamu pilih adalah Pemilih Aktif.")
                    self._warning_shown_in_batch["aktifkan_pemilih"] = True
            else:
                show_modern_warning(self, "Ditolak", f"Tindakan ditolak.<br>{nama} adalah Pemilih Aktif.")
            self._batch_add("rejected", "aktifkan_pemilih")
            return

        # ⚠️ Validasi 2
        if ket not in ("1","2","3","4","5","6","7","8"):
            if getattr(self, "_in_batch_mode", False):
                if not self._warning_shown_in_batch.get("aktifkan_pemilih", False):
                    #show_modern_warning(self, "Ditolak", "Data yang kamu pilih adalah Pemilih Aktif.")
                    self._warning_shown_in_batch["aktifkan_pemilih"] = True
            else:
                show_modern_warning(self, "Ditolak", f"Tindakan ditolak.<br>{nama} adalah Pemilih Aktif.")
            self._batch_add("rejected", "aktifkan_pemilih")
            return

        # ✅ Set KET ke 0
        ket_item.setText("0")
        self.update_database_field(row, "KET", "0")

        gi = self._global_index(row)
        if 0 <= gi < len(self.all_data):
            self.all_data[gi]["KET"] = "0"

        # 🌗 Warna sesuai tema
        bg_color = self.table.palette().color(self.table.backgroundRole())
        brightness = (bg_color.red() + bg_color.green() + bg_color.blue()) / 3
        warna_normal = QColor("black") if brightness > 128 else QColor("white")
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it:
                it.setForeground(warna_normal)

        if not getattr(self, "_in_batch_mode", False):
            show_modern_info(self, "Aktifkan", f"{nama} telah diaktifkan kembali.")

        self._batch_add("ok", "aktifkan_pemilih")

    # =========================================================
    # 🔹 2. HAPUS PEMILIH
    # =========================================================
    def hapus_pemilih(self, row):
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
            if getattr(self, "_in_batch_mode", False):
                if not self._warning_shown_in_batch.get("hapus_pemilih", False):
                    #show_modern_warning(self, "Ditolak", "Hanya Pemilih Baru di tahap ini yang bisa dihapus!")
                    self._warning_shown_in_batch["hapus_pemilih"] = True
            else:
                show_modern_warning(
                    self, "Ditolak",
                    f"{nama} tidak dapat dihapus dari Daftar Pemilih.<br>"
                    f"Hanya Pemilih Baru di tahap ini yang bisa dihapus!"
                )
            self._batch_add("rejected", "hapus_pemilih")
            return

        # 🔸 Konfirmasi sebelum hapus (hanya jika bukan batch)
        if not getattr(self, "_in_batch_mode", False):
            if not show_modern_question(
                self, "Konfirmasi Hapus",
                f"Apakah Anda yakin ingin menghapus data ini?<br>"
                f"<b>{nama}</b><br>NIK: <b>{nik}</b><br>NKK: <b>{nkk}</b>"
            ):
                self._batch_add("skipped", "hapus_pemilih")
                return

        gi = self._global_index(row)
        if not (0 <= gi < len(self.all_data)):
            self._batch_add("skipped", "hapus_pemilih")
            return

        sig = self._row_signature_from_ui(row)
        rowid = self.all_data[gi].get("ROWID") or self.all_data[gi].get("_rowid_")
        if not rowid:
            show_modern_error(self, "Error", "ROWID tidak ditemukan — data tidak dapat dihapus.")
            self._batch_add("skipped", "hapus_pemilih")
            return

        last_update = sig.get("LastUpdate", "").strip()
        if "/" in last_update:
            try:
                dt = datetime.strptime(last_update, "%d/%m/%Y")
                last_update = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        try:
            # 🟢 Shared cursor versi super kilat
            if getattr(self, "_in_batch_mode", False) and hasattr(self, "_shared_cur") and self._shared_cur:
                cur = self._shared_cur
                cur.execute("""
                    DELETE FROM data_pemilih
                    WHERE ROWID = ?
                    AND IFNULL(NIK,'') = ?
                    AND IFNULL(NKK,'') = ?
                    AND (IFNULL(DPID,'') = ? OR DPID IS NULL)
                    AND IFNULL(TGL_LHR,'') = ?
                    AND IFNULL(LastUpdate,'') = ?
                """, (rowid, sig["NIK"], sig["NKK"], sig["DPID"], sig["TGL_LHR"], last_update))
            else:
                with sqlite3.connect(self.db_name) as conn:
                    conn.execute("PRAGMA busy_timeout=3000;")
                    conn.execute("""
                        DELETE FROM data_pemilih
                        WHERE ROWID = ?
                        AND IFNULL(NIK,'') = ?
                        AND IFNULL(NKK,'') = ?
                        AND (IFNULL(DPID,'') = ? OR DPID IS NULL)
                        AND IFNULL(TGL_LHR,'') = ?
                        AND IFNULL(LastUpdate,'') = ?
                    """, (rowid, sig["NIK"], sig["NKK"], sig["DPID"], sig["TGL_LHR"], last_update))
                    conn.commit()

            # ✅ Setelah sukses, hapus dari memori
            del self.all_data[gi]
            if (self.current_page > 1) and ((self.current_page - 1) * self.rows_per_page >= len(self.all_data)):
                self.current_page -= 1

            if not getattr(self, "_in_batch_mode", False):
                show_modern_info(self, "Selesai", f"{nama} berhasil dihapus dari Daftar Pemilih!")

            self._batch_add("ok", "hapus_pemilih")

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal menghapus data:\n{e}")
            self._batch_add("skipped", "hapus_pemilih")

    # =========================================================
    # 🔹 3. STATUS PEMILIH (Meninggal, Ganda, Dll)
    # =========================================================
    def set_ket_status(self, row, new_value: str, label: str):
        dpid_item = self.table.item(row, self.col_index("DPID"))
        nama_item = self.table.item(row, self.col_index("NAMA"))
        nama = nama_item.text().strip() if nama_item else ""

        # ⚠️ Validasi
        if not dpid_item or dpid_item.text().strip() in ("", "0"):
            if getattr(self, "_in_batch_mode", False):
                if not self._warning_shown_in_batch.get("set_ket_status", False):
                    show_modern_warning(self, "Ditolak", "Data Pemilih Baru tidak bisa di-TMS-kan.")
                    self._warning_shown_in_batch["set_ket_status"] = True
            else:
                show_modern_warning(self, "Ditolak", f"{nama} adalah Pemilih Baru dan tidak bisa di-TMS-kan.")
            self._batch_add("rejected", f"set_ket_status_{label}")
            return

        ket_item = self.table.item(row, self.col_index("KET"))
        if ket_item and ket_item.text().strip() == new_value:
            return

        if ket_item:
            ket_item.setText(new_value)
            self.update_database_field(row, "KET", new_value)

        gi = self._global_index(row)
        if 0 <= gi < len(self.all_data):
            self.all_data[gi]["KET"] = new_value

        # 🎨 Warnai merah
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it:
                it.setForeground(QColor("red"))

        self._batch_add("ok", f"set_ket_status_{label}")

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
        """Update satu kolom di database berdasar NIK (super kilat)."""
        try:
            nik_col = self.col_index("NIK")
            nik = self.table.item(row, nik_col).text().strip() if nik_col != -1 else None
            if not nik:
                return

            if getattr(self, "_in_batch_mode", False) and hasattr(self, "_shared_cur") and self._shared_cur:
                self._shared_cur.execute(f"UPDATE data_pemilih SET {field_name}=? WHERE NIK=?", (value, nik))
            else:
                with sqlite3.connect(self.db_name) as conn:
                    conn.execute(f"UPDATE data_pemilih SET {field_name}=? WHERE NIK=?", (value, nik))
                    conn.commit()
        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memperbarui database:\n{e}")

    def apply_shadow(self, widget, blur=24, dx=0, dy=6, rgba=(0,0,0,180)):
        eff = QGraphicsDropShadowEffect(widget)
        eff.setBlurRadius(blur)
        eff.setOffset(dx, dy)
        eff.setColor(QColor(*rgba))
        widget.setGraphicsEffect(eff)

    def cek_data(self):
        """Validasi seluruh data (semua halaman) dengan super ultra kilat + commit batch."""
        from datetime import datetime
        import sqlite3

        target_date = datetime(2029, 6, 26)
        nik_seen = {}
        nik_count = {}
        hasil = ["Sesuai"] * len(self.all_data)  # default

        # === Hitung kemunculan NIK untuk seluruh data ===
        for d in self.all_data:
            nik = str(d.get("NIK", "")).strip()
            if nik:
                nik_count[nik] = nik_count.get(nik, 0) + 1

        # === Loop utama validasi semua baris di self.all_data ===
        for i, d in enumerate(self.all_data):
            nkk = str(d.get("NKK", "")).strip()
            nik = str(d.get("NIK", "")).strip()
            tgl_lhr = str(d.get("TGL_LHR", "")).strip()
            ket = str(d.get("KET", "")).strip()
            sts = str(d.get("STS", "")).strip()

            # --- Validasi NKK ---
            if len(nkk) != 16:
                hasil[i] = "NKK Invalid"
                continue
            try:
                dd_nkk = int(nkk[6:8])
                mm_nkk = int(nkk[8:10])
                if dd_nkk < 1 or dd_nkk > 31 or mm_nkk < 1 or mm_nkk > 12:
                    hasil[i] = "Potensi NKK Invalid"
                    continue
            except:
                hasil[i] = "Potensi NKK Invalid"
                continue

            # --- Validasi NIK ---
            if len(nik) != 16:
                hasil[i] = "NIK Invalid"
                continue
            try:
                dd_nik = int(nik[6:8])
                mm_nik = int(nik[8:10])
                if dd_nik < 1 or dd_nik > 71 or mm_nik < 1 or mm_nik > 12:
                    hasil[i] = "Potensi NIK Invalid"
                    continue
            except:
                hasil[i] = "Potensi NIK Invalid"
                continue

            # --- Validasi umur ---
            if "|" in tgl_lhr:
                try:
                    dd, mm, yy = map(int, tgl_lhr.split("|"))
                    lahir = datetime(yy, mm, dd)
                    umur = (target_date - lahir).days / 365.25
                    if umur < 0 or umur < 13:
                        hasil[i] = "Potensi Dibawah Umur"
                        continue
                    elif umur < 17 and sts.upper() == "B":
                        hasil[i] = "Dibawah Umur"
                        continue
                except:
                    pass

            # --- Catat untuk deteksi ganda nanti ---
            if nik and ket not in ("1", "2", "3", "4", "5", "6", "7", "8"):
                nik_seen.setdefault(nik, []).append(i)

        # === Tandai Ganda ===
        for nik, idxs in nik_seen.items():
            if len(idxs) > 1:
                for j in idxs:
                    ket = str(self.all_data[j].get("KET", ""))
                    hasil[j] = "Sesuai" if ket in ("1","2","3","4","5","6","7","8") else "Ganda"

        # === Pemilih Baru / Pemilih Pemula ===
        for i, d in enumerate(self.all_data):
            ket = str(d.get("KET", "")).upper()
            nik = str(d.get("NIK", "")).strip()
            if ket == "B":
                hasil[i] = "Pemilih Baru" if nik_count.get(nik, 0) > 1 else "Pemilih Pemula"

        # === Simpan hasil ke self.all_data ===
        for i, status in enumerate(hasil):
            self.all_data[i]["CEK_DATA"] = status

        # === Commit ke database (executemany super kilat) ===
        try:
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()
            cur.execute("PRAGMA synchronous = OFF;")
            cur.execute("PRAGMA journal_mode = MEMORY;")
            cur.execute("PRAGMA temp_store = MEMORY;")

            data_update = [
                (d["CEK_DATA"], d.get("rowid"))
                for d in self.all_data
                if d.get("rowid") is not None
            ]

            cur.executemany(
                "UPDATE data_pemilih SET CEK_DATA = ? WHERE rowid = ?",
                data_update
            )

            conn.commit()
            conn.close()
        except Exception as e:
            show_modern_error(self, "Gagal Commit", f"Gagal menyimpan hasil ke database:\n{e}")
            return

        # === Refresh halaman aktif ===
        self.show_page(self.current_page)
        self._warnai_baris_berdasarkan_ket()

            # === Sinkronkan hasil ke file terenkripsi utama (.enc) ===
        try:
            if hasattr(self, "enc_path") and os.path.exists(self.db_name):
                _encrypt_file(self.db_name, self.enc_path)
                print(f"[INFO] Sinkronisasi hasil pemeriksaan ke {self.enc_path} berhasil.")
        except Exception as e:
            print(f"[WARN] Gagal menyinkronkan ke database terenkripsi: {e}")

        show_modern_info(
            self,
            "Selesai",
            f"Pemeriksaan {len(self.all_data):,} data selesai dilakukan!"
        )

    def _warnai_baris_berdasarkan_ket(self):
        """Warnai baris di halaman aktif berdasar kolom KET."""
        for row in range(self.table.rowCount()):
            ket = str(self.table.item(row, self._col_index("KET")).text()).strip()
            if ket in ("1","2","3","4","5","6","7","8"):
                color = QColor("red")
            elif ket.lower() == "u":
                color = QColor("yellow")
            elif ket.lower() == "b":
                color = QColor("green")
            else:
                color = QColor("white" if self.load_theme() == "dark" else "black")

            for c in range(self.table.columnCount()):
                item = self.table.item(row, c)
                if item:
                    item.setForeground(color)

    def _col_index(self, name):
        """Helper untuk ambil index kolom berdasar nama."""
        for i in range(self.table.columnCount()):
            if self.table.horizontalHeaderItem(i).text() == name:
                return i
        return -1

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

                # 🔹 Verifikasi baris ke-15
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

                # ⚡ Cache index header agar tidak bolak balik mencari
                header_idx = {col: i for i, col in enumerate(header)}
                idx_status = header_idx.get("STATUS", None)
                if idx_status is None:
                    show_modern_warning(self, "Error", "Kolom STATUS tidak ditemukan di CSV.")
                    return

                # 🚀 Buka koneksi dan percepat pragma
                conn = sqlite3.connect(self.db_name)
                cur = conn.cursor()
                cur.execute("PRAGMA synchronous = OFF")
                cur.execute("PRAGMA journal_mode = MEMORY")
                cur.execute("PRAGMA temp_store = MEMORY")

                # Buat tabel jika belum ada
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
                        CEK_DATA TEXT
                    )
                """)
                cur.execute("DELETE FROM data_pemilih")

                from datetime import datetime
                self.all_data = []
                batch_values = []

                for row in reader[1:]:
                    if not row or len(row) < len(header):
                        continue

                    status_val = row[idx_status].strip().upper()
                    if status_val not in ("AKTIF", "UBAH", "BARU"):
                        continue

                    data_dict, values = {}, []
                    for csv_col, app_col in mapping.items():
                        if csv_col in header_idx:
                            val = row[header_idx[csv_col]].strip()

                            # Kolom KET harus 0
                            if app_col == "KET":
                                val = "0"

                            # Format tanggal
                            if app_col == "LastUpdate" and val:
                                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                                    try:
                                        val = datetime.strptime(val, fmt).strftime("%d/%m/%Y")
                                        break
                                    except Exception:
                                        continue

                            data_dict[app_col] = val
                            values.append(val)

                    self.all_data.append(data_dict)
                    batch_values.append(tuple(values))

                # 🔥 Super cepat: insert semua sekaligus
                placeholders = ",".join(["?"] * len(mapping))
                cur.executemany(
                    f"INSERT INTO data_pemilih ({','.join(mapping.values())}) VALUES ({placeholders})",
                    batch_values
                )

                # ✅ Pastikan semua KET = 0
                cur.execute("UPDATE data_pemilih SET KET='0'")
                conn.commit()
                conn.close()

                # Pagination dan tampilkan
                self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
                self.show_page(1)

                # Header & sort ulang
                self.connect_header_events()
                self.sort_data(auto=True)

                show_modern_info(self, "Sukses", "Import CSV selesai!")

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal import CSV: {e}")

    # =================================================
    # Load data dari database saat login ulang
    # =================================================
    def load_data_from_db(self):
        from datetime import datetime
        import sqlite3

        # ✅ Gunakan context manager biar auto-close walau ada error
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
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
                    CEK_DATA TEXT
                )
            """)

            # ✅ Ambil data sekaligus (langsung jadi list of dict)
            cur.execute("SELECT rowid, * FROM data_pemilih")
            rows = [dict(row) for row in cur.fetchall()]

        # ✅ Ambil semua header kolom dari tabel GUI hanya sekali
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]

        # ✅ Cache hasil konversi tanggal agar parsing tidak berulang
        _tgl_cache = {}

        def format_tgl(val):
            if not val:
                return ""
            if val in _tgl_cache:  # gunakan cache jika sudah pernah diproses
                return _tgl_cache[val]
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    hasil = datetime.strptime(val, fmt).strftime("%d/%m/%Y")
                    _tgl_cache[val] = hasil
                    return hasil
                except:
                    continue
            _tgl_cache[val] = val
            return val

        # ✅ Proses massal super cepat dengan dict comprehension
        self.all_data = [
            {
                **{col: ("" if row.get(col) is None else str(row[col])) for col in headers},
                "_rowid_": row.get("rowid"),
                "LastUpdate": format_tgl(str(row.get("LastUpdate", "")))
            }
            for row in rows
        ]

        # ✅ Hitung total halaman
        total = len(self.all_data)
        self.total_pages = max(1, (total + self.rows_per_page - 1) // self.rows_per_page)

        # ✅ Tampilkan halaman pertama
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
                    CEK_DATA TEXT
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
            chk_item.setCheckState(Qt.CheckState.Unchecked)
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
        QTimer.singleShot(0, self.sync_header_checkbox_state)
        
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

    def lookup_pemilih(self, row):
        """Lookup cepat berdasarkan baris terpilih (stub aman, tidak crash)."""
        try:
            # Ambil beberapa kolom penting
            idx_nik  = self.col_index("NIK")
            idx_nama = self.col_index("NAMA")
            idx_dpid = self.col_index("DPID")

            nik  = self.table.item(row, idx_nik).text()  if idx_nik  != -1 and self.table.item(row, idx_nik)  else ""
            nama = self.table.item(row, idx_nama).text() if idx_nama != -1 and self.table.item(row, idx_nama) else ""
            dpid = self.table.item(row, idx_dpid).text() if idx_dpid != -1 and self.table.item(row, idx_dpid) else ""

            # Tampilkan info sederhana dulu (anti-crash)
            show_modern_info(self, "Lookup",
                            f"NIK: {nik}<br>Nama: {nama}<br>DPID: {dpid}<br><br>(Fungsi lookup belum diimplementasikan.)")
            return True
        except Exception as e:
            show_modern_error(self, "Lookup Gagal", f"Gagal melakukan lookup:<br>{e}")
            return False
        
    def style_menu(self, menu: QMenu, theme: str):
        if theme == "dark":
            menu.setStyleSheet("""
                QMenu {
                    background-color: #121212;
                    border: 1px solid #333;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::separator {
                    height: 1px;
                    background: #2a2a2a;
                    margin: 6px 8px;
                }
                QMenu::item {
                    padding: 6px 12px;
                    border-radius: 6px;
                    color: #eaeaea;
                    background: transparent;
                }
                QMenu::item:selected {
                    background: #ff9900;
                    color: #000;
                }
                QMenu::item:disabled {
                    color: #777;
                    background: transparent;
                }
                QMenu::icon { padding-left: 6px; }
            """)
            shadow_color = QColor(0, 0, 0, 200)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    border: 1px solid #000;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::separator {
                    height: 1px;
                    background: #e5e5e5;
                    margin: 6px 8px;
                }
                QMenu::item {
                    padding: 6px 12px;
                    border-radius: 6px;
                    color: #111;
                    background: transparent;
                }
                QMenu::item:selected {
                    background: #ff9900;
                    color: #000;
                }
                QMenu::item:disabled {
                    color: #9a9a9a;
                    background: transparent;
                }
                QMenu::icon { padding-left: 6px; }
            """)
            shadow_color = QColor(0, 0, 0, 140)

        eff = QGraphicsDropShadowEffect(menu)
        eff.setBlurRadius(24)
        eff.setOffset(0, 6)
        eff.setColor(shadow_color)
        menu.setGraphicsEffect(eff)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _install_safe_shutdown_hooks(self):
        # Pastikan flag & pointer ada
        if not hasattr(self, "_in_batch_mode"):
            self._in_batch_mode = False
        self._shared_conn = getattr(self, "_shared_conn", None)
        self._shared_cur  = getattr(self, "_shared_cur", None)

        app = QApplication.instance()
        if app:
            # Dipanggil saat app akan keluar "normal"
            app.aboutToQuit.connect(lambda: self._flush_db("aboutToQuit"))

        # Panggil saat proses berakhir (nyaris selalu terpanggil)
        atexit.register(lambda: self._flush_db("atexit"))

        # Tangani Ctrl+C / kill jika tersedia (di Windows sebagian sinyal terbatas)
        try:
            import signal
            signal.signal(signal.SIGINT,  lambda s, f: self._graceful_terminate("SIGINT"))
            signal.signal(signal.SIGTERM, lambda s, f: self._graceful_terminate("SIGTERM"))
        except Exception:
            pass  # aman dilewati jika tidak didukung

    def _graceful_terminate(self, source):
        """Commit dulu, lalu keluar rapi."""
        try:
            self._flush_db(source)
        finally:
            app = QApplication.instance()
            if app:
                app.quit()

    def closeEvent(self, event):
        """Klik tombol X di kanan atas juga lewat sini."""
        self._flush_db("closeEvent")
        super().closeEvent(event)

    def _flush_db(self, where=""):
        """
        Pastikan semua perubahan tersimpan sebelum keluar.
        - Commit transaksi batch (shared cursor) bila masih terbuka
        - Tutup cursor & koneksi bersama
        - Aktifkan kembali UI supaya tidak blank saat keluar
        """
        try:
            # Pastikan UI terlihat
            if hasattr(self, "table") and self.table:
                try:
                    self.table.setUpdatesEnabled(True)
                    self.table.viewport().update()
                    QApplication.processEvents()
                except Exception:
                    pass

            # Kalau sedang batch dan ada shared connection → commit sekali
            if getattr(self, "_in_batch_mode", False) and getattr(self, "_shared_conn", None):
                try:
                    self._shared_conn.commit()
                except Exception:
                    # Jangan agresif pas shutdown
                    pass
                finally:
                    try:
                        if getattr(self, "_shared_cur", None):
                            self._shared_cur.close()
                    except Exception:
                        pass
                    try:
                        self._shared_conn.close()
                    except Exception:
                        pass
                    self._shared_cur  = None
                    self._shared_conn = None
                    self._in_batch_mode = False
        except Exception as e:
            # Hindari popup saat shutdown; cukup log ke stderr
            print(f"[WARN] _flush_db({where}) error: {e}", file=sys.stderr)

    def _init_db_pragmas(self):
        try:
            import sqlite3
            with sqlite3.connect(self.db_name) as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL;")
                cur.execute("PRAGMA synchronous=NORMAL;")
                cur.execute("PRAGMA busy_timeout=3000;")  # 3 detik
                conn.commit()
        except Exception as e:
            print(f"[WARN] init pragmas: {e}", file=sys.stderr)

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
                    CEK_DATA TEXT
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

        # === Setelah user klik "Saya Sudah Scan" → verifikasi OTP dulu ===
        if qr_dialog.result() == QDialog.DialogCode.Accepted:
            totp = pyotp.TOTP(otp_secret)

            # Maks 3 percobaan
            verified = False
            for attempt in range(3):
                code = self._prompt_otp_code_dialog()
                if code is None:
                    # User batal → hentikan flow, jangan pindah ke Login
                    show_modern_warning(self, "Dibatalkan", "Verifikasi OTP dibatalkan.")
                    return

                # Allow ±1 step drift (±30 detik) supaya toleran
                if totp.verify(code, valid_window=1):
                    verified = True
                    break
                else:
                    show_modern_warning(self, "OTP Salah", "Kode OTP tidak valid atau sudah kedaluwarsa. Coba lagi.")

            if not verified:
                show_modern_error(self, "Gagal", "Verifikasi OTP gagal 3 kali. Silakan scan ulang QR atau coba lagi.")
                return
        else:
            # Dialog QR ditutup bukan dengan 'accept' → hentikan flow
            return

        dlg = ModernMessage("Sukses", "Akun berhasil dibuat!", "success")
        dlg.exec()
        self.close()
        self.login_window = LoginWindow()
        self.login_window.show()

    def _prompt_otp_code_dialog(self):
        """
        Tampilkan dialog kecil untuk input 6 digit OTP.
        Return: string 'NNNNNN' jika OK, atau None jika batal.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Verifikasi OTP")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setFixedSize(380, 200)
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)

        # Tema ringan/gelap mengikuti parent
        bg_is_dark = True
        try:
            bg_color = self.palette().color(self.backgroundRole()).lightness()
            bg_is_dark = bg_color < 128
        except Exception:
            pass

        bg = "#111" if bg_is_dark else "#f7f7f7"
        fg = "white" if bg_is_dark else "#222"
        accent = "#ff6600" if bg_is_dark else "#d35400"

        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {fg};
                border-radius: 12px;
                border: 1px solid {"#444" if bg_is_dark else "#ccc"};
            }}
            QLabel {{
                font-family: 'Segoe UI';
                font-size: 11pt;
            }}
            QLineEdit {{
                font-family: 'Segoe UI';
                font-size: 16pt;
                padding: 8px 12px;
                border: 1px solid {"#555" if bg_is_dark else "#bbb"};
                border-radius: 8px;
                background: {"#1a1a1a" if bg_is_dark else "white"};
                color: {fg};
                letter-spacing: 2px;
            }}
            QPushButton {{
                background-color: {accent};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 10.5pt;
                min-width: 110px;
            }}
            QPushButton:hover {{
                background-color: #ff8533;
            }}
            QPushButton#btnCancel {{
                background-color: {"#333" if bg_is_dark else "#ddd"};
                color: {fg};
            }}
            QPushButton#btnCancel:hover {{
                background-color: {"#444" if bg_is_dark else "#ccc"};
            }}
        """)

        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(22, 20, 22, 18)
        vbox.setSpacing(14)

        info = QLabel("Masukkan 6 digit kode OTP dari aplikasi authenticator Anda.")
        info.setWordWrap(True)
        vbox.addWidget(info)

        otp_edit = QLineEdit()
        otp_edit.setMaxLength(6)
        otp_edit.setPlaceholderText("123456")
        otp_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        otp_edit.setClearButtonEnabled(True)
        # Hanya angka 6 digit
        otp_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,6}$")))
        vbox.addWidget(otp_edit)

        # Tombol
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        btn_ok = QPushButton("Verifikasi")
        btn_cancel = QPushButton("Batal")
        btn_cancel.setObjectName("btnCancel")
        hbox.addWidget(btn_cancel)
        hbox.addWidget(btn_ok)
        vbox.addLayout(hbox)

        # Enter untuk submit
        otp_edit.returnPressed.connect(btn_ok.click)

        # Aksi
        code_holder = {"val": None}

        def do_ok():
            code = otp_edit.text().strip().replace(" ", "")
            if len(code) == 6 and code.isdigit():
                code_holder["val"] = code
                dlg.accept()
            else:
                show_modern_warning(self, "Format Salah", "Kode OTP harus 6 digit angka.")

        def do_cancel():
            code_holder["val"] = None
            dlg.reject()

        btn_ok.clicked.connect(do_ok)
        btn_cancel.clicked.connect(do_cancel)

        # Tampilkan di tengah
        screen_geo = QApplication.primaryScreen().geometry()
        dlg.move(screen_geo.center() - dlg.rect().center())

        dlg.exec()

        return code_holder["val"]

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
                        TPS TEXT, LastUpdate DATETIME, CEK_DATA TEXT
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
                    TPS TEXT, LastUpdate DATETIME, CEK_DATA TEXT
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
#    app = QApplication(sys.argv)
#    login = LoginWindow()
#    login.show()
#    sys.exit(app.exec())


##################################################**************************############################################
##################################################**************************############################################
##################################################**************************############################################

if __name__ == "__main__":
    app = QApplication(sys.argv)

    if getattr(sys, "frozen", False):
        os.environ.pop("NEXVO_DEV_MODE", None)
        os.environ.pop("NEXVO_DEV_PASSWORD", None)

    # Jika kamu punya fungsi untuk tema, panggil di sini
    # apply_global_palette(app, "dark")

    # === MODE DEV ===
    if is_dev_mode_requested():
        ok = confirm_dev_mode(None)
        if ok:
            dev_nama = "ARI ARDIANA"
            dev_kecamatan = "TANJUNGJAYA"
            dev_desa = "SUKASENANG"
            dev_tahapan = "DPHP"
            dev_dbname = "dphp.db"  # sesuaikan dengan DB default kamu

            # langsung buka MainWindow
            mw = MainWindow(dev_nama, dev_kecamatan, dev_desa, dev_dbname, dev_tahapan)
            mw.show()
            sys.exit(app.exec())
        # jika batal, lanjut ke login normal

    # === NORMAL MODE ===
    login = LoginWindow()
    login.show()
    sys.exit(app.exec())