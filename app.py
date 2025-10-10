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
from PyQt6.QtCore import Qt, QTimer, QRect, QPropertyAnimation, QSize, QPoint, QVariantAnimation, QEasingCurve, QAbstractAnimation
from io import BytesIO
from cryptography.fernet import Fernet


# ===================== ENKRIPSI/DEKRIPSI DB (pakai nexvo.key) =====================

# --- Konstanta format file terenkripsi ---
MAGIC = b"NEXVOENC1"                 # header format/versi berkas terenkripsi
SQLITE_HEADER = b"SQLite format 3"   # header DB SQLite

# --- Manajemen lokasi key (portable + per-user) ---
APP_NAME = "NexVo"
KEY_FILENAME = "nexvo.key"

def _user_key_dir() -> str:
    """Folder default untuk menyimpan key yang pasti writable per-user."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return os.path.join(base, APP_NAME)
    elif sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    else:
        return os.path.join(os.path.expanduser("~/.config"), APP_NAME)

def _portable_key_path() -> str:
    """Coba cari nexvo.key di lokasi yang sama dengan EXE/skrip (portable mode)."""
    base = os.path.dirname(getattr(sys, "frozen", False) and sys.executable or os.path.abspath(__file__))
    return os.path.join(base, KEY_FILENAME)

def _default_key_path() -> str:
    """Lokasi fallback per-user (writable)."""
    d = _user_key_dir()
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, KEY_FILENAME)

def _resolve_key_path() -> str:
    """
    Urutan pencarian:
      1) nexvo.key di folder EXE/skrip (portable mode)
      2) nexvo.key di folder per-user (dibuat otomatis kalau belum ada)
    """
    p_portable = _portable_key_path()
    if os.path.exists(p_portable):
        return p_portable
    return _default_key_path()

def _generate_key_at(path: str) -> bytes:
    key = Fernet.generate_key()
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(key)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return key

def load_key() -> bytes:
    """
    Muat key:
      - Jika ada di folder EXE/skrip -> pakai itu (portable)
      - Kalau tidak ada -> pakai folder per-user; buat baru jika belum ada
    """
    p = _resolve_key_path()
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        #####print(f"[INFO] Key enkripsi belum ada, membuat baru di: {p}")####
        return _generate_key_at(p)
    with open(p, "rb") as f:
        return f.read()

# --- Helper I/O atomic (aman dari file setengah jadi) ---
def _atomic_write(path: str, data: bytes):
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_enc_", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def _sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def _encrypt_file(plain_path: str, enc_path: str):
    """Enkripsi DB SQLite -> file .enc (MAGIC + checksum + ciphertext)."""
    if not os.path.exists(plain_path):
        raise FileNotFoundError(f"Plain DB tidak ditemukan: {plain_path}")
    with open(plain_path, "rb") as f:
        db = f.read()
    if not db.startswith(SQLITE_HEADER):
        raise ValueError("File plaintext bukan database SQLite yang valid.")

    key = load_key()
    fernet = Fernet(key)
    checksum = _sha256(db)
    ciphertext = fernet.encrypt(db)

    payload = MAGIC + checksum + ciphertext
    _atomic_write(enc_path, payload)

def _decrypt_file(enc_path: str, dec_path: str):
    """Dekripsi file .enc -> plaintext DB (verifikasi MAGIC + checksum + header)."""
    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"Encrypted DB tidak ditemukan: {enc_path}")

    with open(enc_path, "rb") as f:
        blob = f.read()

    min_len = len(MAGIC) + 32 + 1
    if len(blob) < min_len:
        raise ValueError("File .enc terlalu pendek / corrupt.")
    if not blob.startswith(MAGIC):
        raise ValueError("MAGIC header tidak cocok (bukan format NEXVOENC1).")

    hdr_len = len(MAGIC)
    checksum = blob[hdr_len:hdr_len+32]
    ciphertext = blob[hdr_len+32:]

    key = load_key()
    fernet = Fernet(key)
    db = fernet.decrypt(ciphertext)

    if _sha256(db) != checksum:
        raise ValueError("Checksum plaintext tidak cocok. File terenkripsi rusak.")
    if not db.startswith(SQLITE_HEADER):
        raise ValueError("Hasil dekripsi bukan database SQLite yang valid.")

    _atomic_write(dec_path, db)
# =====================================================================
class ProtectedWindow(QMainWindow):
    """Base class agar semua window tidak bisa ditutup lewat tombol X, 
    kecuali lewat menu File → Keluar."""
    def closeEvent(self, event):
        # ✅ Jika window diberi izin keluar oleh MainWindow, izinkan
        if hasattr(self, "_izin_keluar") and self._izin_keluar:
            event.accept()
            super().closeEvent(event)
            return

        # ❌ Selain itu, blokir
        event.ignore()
        QMessageBox.warning(
            self,
            "Tindakan Diblokir",
            "Gunakan menu <b>File → Keluar</b> untuk menutup aplikasi.",
            QMessageBox.StandardButton.Ok
        )

# ===================================================
# 🚀 MEMUAT VARIABEL LINGKUNGAN DARI FILE .env
# ===================================================
from dotenv import load_dotenv # 👈 Tambahkan import ini
load_dotenv()
# ===================================================


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
        # Track popup open state to flip chevron
        self._popup_open = False
        # Animated arrow (rotation angle 0..180)
        self._arrow_angle = 0.0
        self._arrow_anim: QVariantAnimation | None = None

    def setPopupDirection(self, mode: str):
        if mode in ("down", "up", "auto"):
            self._popup_direction_mode = mode

    def showPopup(self):  # type: ignore
        view = self.view()
        if view is None:
            super().showPopup()
            self._popup_open = True
            self._animate_arrow(True)
            self.update()
            return
        try:
            fm = view.fontMetrics()
            max_text_width = max((fm.horizontalAdvance(self.itemText(i)) for i in range(self.count())), default=0)
            padding = 56
            popup_width = max(self.width(), min(max_text_width + padding, self._max_popup_width))
        except Exception:
            popup_width = self.width()
        super().showPopup()
        self._popup_open = True
        self._animate_arrow(True)
        self.update()
        try:
            try:
                view.setTextElideMode(Qt.TextElideMode.ElideNone)  # type: ignore
            except Exception:
                pass
            view.setMinimumWidth(int(popup_width))
            view.setMaximumWidth(int(max(popup_width, self.width())))
        except Exception:
            pass
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

    def hidePopup(self):  # type: ignore
        try:
            super().hidePopup()
        finally:
            self._popup_open = False
            self._animate_arrow(False)
            self.update()

    def _animate_arrow(self, opening: bool):
        start = self._arrow_angle
        end = 180.0 if opening else 0.0
        if self._arrow_anim and self._arrow_anim.state() == QAbstractAnimation.State.Running:
            self._arrow_anim.stop()
        self._arrow_anim = QVariantAnimation(self)
        self._arrow_anim.setStartValue(start)
        self._arrow_anim.setEndValue(end)
        self._arrow_anim.setDuration(160)
        self._arrow_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._arrow_anim.valueChanged.connect(self._on_arrow_anim_value)
        self._arrow_anim.start()

    def _on_arrow_anim_value(self, val):
        try:
            self._arrow_angle = float(val)
            self.update()
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
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self._arrow_angle)
        # Base 'V' pointing down at 0 degrees
        half = arrow_size
        painter.drawLine(int(-half), int(-half/2), 0, int(half/2))
        painter.drawLine(0, int(half/2), int(half), int(-half/2))
        painter.restore()
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
        # Gunakan objectName khusus agar bisa dioverride oleh tema tanpa mengganggu QLineEdit lain
        self.tgl_update.setObjectName("DateRangeField")

        layout.addWidget(self.tgl_update)

        # Terapkan styling awal sesuai mode tema yang sudah terset (default light)
        initial_mode = getattr(self, "_current_theme_mode", "light")
        self._style_date_field(initial_mode)

        # --- Popup Date Range Picker (compact) ---------------------------------
        class CompactDateRangePopup(QFrame):
            def __init__(self, parent_field: QLineEdit, theme_mode: str = "light"):
                super().__init__(parent_field)
                self.parent_field = parent_field
                self.theme_mode = theme_mode.lower()
                self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
                self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                self.setObjectName("CompactDateRangePopup")
                # Triangle (notch) configuration
                self._notch_width = 18
                self._notch_height = 9
                self._anchor_x = 40  # will be adjusted in show_near

                # --- Dynamic color palette based on theme ---
                accent = "#ff8800"
                if self.theme_mode == "dark":
                    bg = "#1e1e1e"
                    text = "#dddddd"
                    subtext = "#aaaaaa"
                    border = "#444444"
                    # Hover lebih tebal (sedikit lebih terang + border accent di rule umum nanti)
                    preset_hover_bg = "#303030"
                    hover_bg = preset_hover_bg
                    sel_bg = accent
                    sel_text = "#ffffff"
                    # Warna mid range (tint hangat gelap)
                    mid_bg = "#3a2d20"
                    mid_hover_bg = "#4a3a28"
                    range_text = text
                    clear_color = "#bbbbbb"
                else:  # light
                    bg = "#ffffff"
                    text = "#222222"
                    subtext = "#555555"
                    border = "#d6d6d6"
                    # Hover lebih tebal (lebih gelap dibanding sebelumnya)
                    preset_hover_bg = "#ebebeb"  # sebelumnya #f7f7f7
                    hover_bg = preset_hover_bg
                    sel_bg = accent
                    sel_text = "#ffffff"
                    # Mid range tint terang
                    mid_bg = "#ffe9d1"
                    mid_hover_bg = "#ffdcb8"
                    range_text = text
                    clear_color = "#666666"

                # Simpan warna penting untuk dipakai ulang (highlight preset & today)
                self.accent = accent
                self.sel_bg = sel_bg
                self.sel_text = sel_text
                self.text_color = text
                self.subtext_color = subtext

                # Border will be custom-painted (avoid double border stacking)
                self.setStyleSheet(f"""
                    QFrame#CompactDateRangePopup {{ background:{bg}; border:0; border-radius:8px; }}
                    QFrame#PresetItem {{ background:{bg}; border-radius:4px; }}
                    QFrame#PresetItem:hover {{ background:{preset_hover_bg}; }}
                    QFrame#PresetItem:hover > QLabel:first-child {{ font-weight:700; }}
                    QFrame#MonthWrap {{ background:{bg}; border-radius:6px; }}
                    QLabel {{ color:{text}; font-size:9pt; background:transparent; }}
                    QLabel.title {{ font-weight:600; font-size:9pt; letter-spacing:.3px; }}
                    QPushButton.day {{ background:transparent; border:0; border-radius:0; min-width:30px; min-height:30px; font-size:8pt; color:{text}; }}
                    QPushButton.day:hover {{ background:{hover_bg}; }}
                    /* Pill styling */
                    QPushButton[state="start"] {{ background:{sel_bg}; color:{sel_text}; border-top-left-radius:6px; border-bottom-left-radius:6px; border-top-right-radius:0; border-bottom-right-radius:0; }}
                    QPushButton[state="end"] {{ background:{sel_bg}; color:{sel_text}; border-top-right-radius:6px; border-bottom-right-radius:6px; border-top-left-radius:0; border-bottom-left-radius:0; }}
                    QPushButton[state="single"] {{ background:{sel_bg}; color:{sel_text}; border-radius:6px; }}
                    QPushButton[state="mid"] {{ background:{mid_bg}; color:{range_text}; border-radius:0; }}
                    QPushButton[state="mid"]:hover {{ background:{mid_hover_bg}; }}
                    /* Legacy fallback */
                    QPushButton.day.start, QPushButton.day.end {{ background:{sel_bg}; color:{sel_text}; }}
                    QPushButton.day.single {{ background:{sel_bg}; color:{sel_text}; border-radius:6px; }}
                    QPushButton.day.mid {{ background:{mid_bg}; color:{range_text}; }}
                    QPushButton.day.mid:hover {{ background:{mid_hover_bg}; }}
                    QPushButton.day.sel {{ background:{sel_bg}; color:{sel_text}; }}
                    QPushButton.day.range {{ background:{mid_bg}; color:{range_text}; }}
                    /* Removed today border highlight intentionally */
                    QPushButton.nav {{ background:transparent; border:0; font-size:11pt; padding:2px 6px; color:{text}; }}
                    QPushButton.nav:hover {{ background:{hover_bg}; border-radius:4px; }}
                    QPushButton#applyBtn {{ background:{accent}; color:#fff; font-weight:600; border:0; border-radius:6px; padding:6px 14px; }}
                    QPushButton#applyBtn:hover {{ background:#ff9a26; }}
                    QPushButton#clearBtn {{ background:transparent; color:{clear_color}; border:0; padding:6px 10px; }}
                    QPushButton#clearBtn:hover {{ color:{accent}; }}
                    QScrollArea {{ border:0; }}
                """)

                # Store colors for custom painting (notch) reuse
                self._popup_bg_color = bg
                self._popup_border_color = border
                self.start_date: date | None = None
                self.end_date: date | None = None
                self.base_month = date.today().replace(day=1)

                # Root layout changed to vertical to allow a unified bottom action bar spanning both columns
                root = QVBoxLayout(self)
                # Tightened outer margins & spacing (was 10,10,10,10 and spacing 12)
                # Add horizontal margins for better breathing room (was 0,8,0,0)
                # Increase top margin to reserve space for notch area
                root.setContentsMargins(8, 8 + self._notch_height, 8, 0)
                root.setSpacing(6)
                top_row = QHBoxLayout()
                top_row.setSpacing(8)
                # Reduce overall width (was 560) to shrink horizontal footprint
                # Adjust width to allow day button horizontal gaps so rounded pill edges aren't visually clipped
                self.setFixedSize(620, 268)
                # Configurable day cell metrics
                self.day_size = 30
                self.day_gap = 3  # gap between day buttons (both directions)

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
                sep.setStyleSheet(f"background:{border}; width:1px;")
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

            def _build_month(self, month_date: date, index: int):
                box = QVBoxLayout()
                box.setSpacing(2)
                wrap = QFrame()
                wrap.setObjectName("MonthWrap")
                wrap.setLayout(box)
                header = QHBoxLayout()
                header.setSpacing(2)
                # Tambahkan tombol prev dan next di kedua bulan agar user bisa geser dari mana saja
                prev_btn = QPushButton("<")
                prev_btn.setProperty("class", "nav")
                prev_btn.clicked.connect(lambda _=False, idx=index: self._shift_single_month(idx, -1))
                header.addWidget(prev_btn)

                title = QLabel(month_date.strftime("%b %Y"))
                # Updated font size: month title to 8pt per latest request
                title.setStyleSheet("font-weight:600; font-size:8pt;")
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                header.addWidget(title, 1)

                next_btn = QPushButton(">")
                next_btn.setProperty("class", "nav")
                next_btn.clicked.connect(lambda _=False, idx=index: self._shift_single_month(idx, 1))
                header.addWidget(next_btn)
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
                grid = QGridLayout()
                # Horizontal & vertical spacing to create visible margins around each day cell
                grid.setHorizontalSpacing(self.day_gap)
                grid.setVerticalSpacing(self.day_gap)
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
                    btn.setFixedSize(self.day_size, self.day_size)
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

            def _add_months(self, mdate: date, delta: int) -> date:
                # Utility untuk geser bulan dengan aman (set day=1)
                total = (mdate.year * 12 + (mdate.month - 1)) + delta
                year = total // 12
                month = total % 12 + 1
                return date(year, month, 1)

            def _rebuild_month_grid(self, wrap: QFrame):
                # Bersihkan grid lama dan bangun ulang berdasarkan wrap.month_date
                mdate = wrap.month_date
                # clear old buttons
                while wrap.grid.count():
                    item = wrap.grid.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                first = mdate
                start_col = (first.weekday()+1) % 7
                if mdate.month == 12:
                    next_m = mdate.replace(year=mdate.year+1, month=1)
                else:
                    next_m = mdate.replace(month=mdate.month+1)
                days_in = (next_m - timedelta(days=1)).day
                row=0; col=0
                for _ in range(start_col):
                    spacer = QLabel(" ")
                    spacer.setFixedSize(self.day_size, self.day_size)
                    wrap.grid.addWidget(spacer,row,col)
                    col+=1
                for day in range(1, days_in+1):
                    btn = QPushButton(str(day))
                    btn.setProperty("class","day")
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.setFixedSize(self.day_size, self.day_size)
                    ddate = mdate.replace(day=day)
                    btn.clicked.connect(lambda _=False, dd=ddate: self._pick(dd))
                    wrap.grid.addWidget(btn,row,col); col+=1
                    if col>6: col=0; row+=1

            def _shift_single_month(self, index: int, delta: int):
                # Geser hanya bulan dengan index tertentu
                if index < 0 or index >= len(self.month_widgets):
                    return
                wrap = self.month_widgets[index]
                wrap.month_date = self._add_months(wrap.month_date, delta)
                wrap.title_label.setText(wrap.month_date.strftime("%b %Y"))
                self._rebuild_month_grid(wrap)
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
                            state = ""  # dynamic property 'state'
                            cls = "day"
                            if self.start_date and self.end_date and self.start_date <= ddate <= self.end_date:
                                if self.start_date == self.end_date:
                                    if ddate == self.start_date:
                                        state = "single"; cls = "day single"
                                else:
                                    if ddate == self.start_date:
                                        state = "start"; cls = "day start"
                                    elif ddate == self.end_date:
                                        state = "end"; cls = "day end"
                                    else:
                                        state = "mid"; cls = "day mid"
                            elif self.start_date and not self.end_date and ddate == self.start_date:
                                state = "start"; cls = "day start"
                            w.setProperty("class", cls)  # legacy fallback
                            w.setProperty("state", state)
                            # Today border highlight removed per request; property omitted
                            # Re-polish so new dynamic properties take effect
                            w.style().unpolish(w)
                            w.style().polish(w)
                            w.update()

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
                # Place notch near the right edge (ujung kanan) aligned with field's right side
                try:
                    half_notch = self._notch_width / 2
                    pad = 10  # minimal padding from rounded corner
                    self._anchor_x = popup_w - (pad + half_notch)
                    # Safety clamp
                    self._anchor_x = max(pad + half_notch, min(popup_w - pad - half_notch, self._anchor_x))
                except Exception:
                    pass
                self.show()
                self.raise_()
                self.update()

            def set_theme(self, mode: str):
                """Update palette & stylesheet tanpa membuat ulang popup."""
                self.theme_mode = mode.lower()
                accent = "#ff8800"
                if self.theme_mode == "dark":
                    bg = "#1e1e1e"; text = "#dddddd"; subtext = "#aaaaaa"; border = "#444444"; preset_hover_bg = "#252525"; hover_bg = preset_hover_bg; sel_bg = accent; sel_text = "#ffffff"; mid_bg = "#3a2d20"; mid_hover_bg = "#4a3a28"; range_text = text; clear_color = "#bbbbbb"
                else:
                    bg = "#ffffff"; text = "#222222"; subtext = "#555555"; border = "#d6d6d6"; preset_hover_bg = "#f7f7f7"; hover_bg = preset_hover_bg; sel_bg = accent; sel_text = "#ffffff"; mid_bg = "#ffe9d1"; mid_hover_bg = "#ffdcb8"; range_text = text; clear_color = "#666666"
                self.accent = accent; self.sel_bg = sel_bg; self.sel_text = sel_text; self.text_color = text; self.subtext_color = subtext
                # Remove native border; custom paint handles border + notch
                self.setStyleSheet(f"""
                    QFrame#CompactDateRangePopup {{ background:{bg}; border:0; border-radius:8px; }}
                    QFrame#PresetItem {{ background:{bg}; border-radius:4px; }}
                    QFrame#PresetItem:hover {{ background:{preset_hover_bg}; }}
                    QLabel {{ color:{text}; font-size:9pt; background:transparent; }}
                    QLabel.title {{ font-weight:600; font-size:9pt; letter-spacing:.3px; }}
                    QPushButton.day {{ background:transparent; border:0; border-radius:0; min-width:30px; min-height:30px; font-size:8pt; color:{text}; }}
                    QPushButton.day:hover {{ background:{hover_bg}; }}
                    QPushButton[state="start"] {{ background:{sel_bg}; color:{sel_text}; border-top-left-radius:6px; border-bottom-left-radius:6px; border-top-right-radius:0; border-bottom-right-radius:0; }}
                    QPushButton[state="end"] {{ background:{sel_bg}; color:{sel_text}; border-top-right-radius:6px; border-bottom-right-radius:6px; border-top-left-radius:0; border-bottom-left-radius:0; }}
                    QPushButton[state="single"] {{ background:{sel_bg}; color:{sel_text}; border-radius:6px; }}
                    QPushButton[state="mid"] {{ background:{mid_bg}; color:{range_text}; border-radius:0; }}
                    QPushButton[state="mid"]:hover {{ background:{mid_hover_bg}; }}
                    QPushButton.day.start, QPushButton.day.end {{ background:{sel_bg}; color:{sel_text}; }}
                    QPushButton.day.single {{ background:{sel_bg}; color:{sel_text}; border-radius:6px; }}
                    QPushButton.day.mid {{ background:{mid_bg}; color:{range_text}; }}
                    QPushButton.day.mid:hover {{ background:{mid_hover_bg}; }}
                    QPushButton.day.sel {{ background:{sel_bg}; color:{sel_text}; }}
                    QPushButton.day.range {{ background:{mid_bg}; color:{range_text}; }}
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

            def paintEvent(self, event):
                # Custom paint to add an upward triangle notch pointing to field
                try:
                    from PyQt6.QtGui import QPainter, QPainterPath, QPen, QColor
                except Exception:
                    return super().paintEvent(event)
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                w = self.width()
                h = self.height()
                notch_w = self._notch_width
                notch_h = self._notch_height
                ax = self._anchor_x
                radius = 8.0
                top_content_y = notch_h  # area below notch
                path = QPainterPath()
                # Start top-left after radius
                path.moveTo(radius, top_content_y)
                notch_left = ax - notch_w/2
                notch_right = ax + notch_w/2
                # Top edge up to notch
                path.lineTo(notch_left, top_content_y)
                # Notch apex
                path.lineTo(ax, 0)
                path.lineTo(notch_right, top_content_y)
                # Continue to top-right corner
                path.lineTo(w - radius, top_content_y)
                path.quadTo(w, top_content_y, w, top_content_y + radius)
                path.lineTo(w, h - radius)
                path.quadTo(w, h, w - radius, h)
                path.lineTo(radius, h)
                path.quadTo(0, h, 0, h - radius)
                path.lineTo(0, top_content_y + radius)
                path.quadTo(0, top_content_y, radius, top_content_y)
                # Fill
                fill_color = QColor(self._popup_bg_color)
                painter.fillPath(path, fill_color)
                # Border
                pen = QPen(QColor(self._popup_border_color))
                pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawPath(path)
                painter.end()
                # Let default painting draw children only (avoid overpainting background again)
                # Skip base class background by not calling super().paintEvent for QFrame to preserve custom shape
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
            # Tandai field punya popup terbuka agar border bawah transparan
            try:
                self.tgl_update.setProperty("popupOpen", True)
                self.tgl_update.style().unpolish(self.tgl_update)
                self.tgl_update.style().polish(self.tgl_update)
                self.tgl_update.update()
                # Hubungkan close event untuk reset property
                def _reset_popup_prop():
                    self.tgl_update.setProperty("popupOpen", False)
                    self.tgl_update.style().unpolish(self.tgl_update)
                    self.tgl_update.style().polish(self.tgl_update)
                    self.tgl_update.update()
                self._date_popup.destroyed.connect(lambda *_: _reset_popup_prop())
            except Exception:
                pass

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
        # Style khusus date range field
        self._style_date_field(mode)
        # Update popup jika sedang terbuka
        if hasattr(self, "_date_popup") and self._date_popup is not None:
            try:
                self._date_popup.set_theme(mode)
            except Exception:
                pass

    def _style_date_field(self, mode: str):
        """Set stylesheet khusus field tanggal agar konsisten dengan tema.
        Args:
            mode: 'dark' atau 'light'
        """
        accent = "#ff8800"
        if mode == "dark":
            bg = "#2d2d30"; border = "#555"; text = "#d4d4d4"; hover_border = accent
        else:
            bg = "#ffffff"; border = "#bbb"; text = "#222"; hover_border = accent
        self.tgl_update.setStyleSheet(f"""
            QLineEdit#DateRangeField {{
                background:{bg}; border:1px solid {border}; border-radius:6px;
                padding:6px 10px; color:{text}; font-size:10px;
            }}
            QLineEdit#DateRangeField:focus {{ border-color:{hover_border}; }}
            QLineEdit#DateRangeField[popupOpen="true"] {{ border-bottom-color: transparent; }}
        """)
    
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
                border: 1px solid #ff8800; /* accent border on focus */
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
                border: 1px solid #ff8800; /* accent border on focus */
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
class MainWindow(ProtectedWindow):
    def __init__(self, username, kecamatan, desa, db_name, tahapan):
        super().__init__()
        self.tahapan = tahapan.upper()   # ✅ simpan jenis tahapan (DPHP/DPSHP/DPSHPA)

        self.setWindowTitle("Sidalih Pilkada 2024 Desktop v2.2.29 - Pemutakhiran Data")
        self.resize(900, 550)

        # ✅ simpan info login (wajib ada agar import_csv tidak error)
        self.kecamatan_login = kecamatan.upper()
        self.desa_login = desa.upper()
        self.username = username

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
        self._init_db_pragmas()
        self._ensure_schema_and_migrate()
        self.all_data = []

        self.sort_lastupdate_asc = True  # ✅ toggle: True = dari terbaru ke lama, False = sebaliknya

        self.current_page = 1
        self.rows_per_page = 200
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
            # Lebar SUMBER diperlebar supaya seluruh teks pilihan (misal: "ubah_trw 2 _2025") tidak terpotong
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
        self.page_buttons = []

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
        action_keluar.triggered.connect(self.keluar_aplikasi)
        file_menu.addAction(action_keluar)

        generate_menu = menubar.addMenu("Generate")

        view_menu = menubar.addMenu("View")

        # ============================================================
        # 🧭 Tema Dark & Light — dengan style elegan & soft disabled
        # ============================================================
        ##self.action_dark = QAction("  Dark", self, shortcut="Ctrl+D")
        self.action_light = QAction("  Light", self, shortcut="Ctrl+L")

        # Hubungkan ke fungsi apply_theme
        ##self.action_dark.triggered.connect(lambda: self.apply_theme("dark"))
        self.action_light.triggered.connect(lambda: self.apply_theme("light"))

        ##view_menu.addAction(self.action_dark)
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
        self.load_data_from_db()
        self.update_pagination()
        self.apply_column_visibility()

        # ✅ Load theme terakhir dari database
        self.apply_theme("light")

        # ✅ Tambahkan ini biar auto resize kolom jalan setelah login
        QTimer.singleShot(0, self.auto_fit_columns)

        # ✅ Tampilkan jendela langsung dalam keadaan maximize
        self.showMaximized()

        # ✅ Jalankan fungsi urutkan data secara senyap setelah login
        QTimer.singleShot(200, lambda: self.sort_data(auto=True))

        # ✅ Initialize filter sidebar
        self.filter_sidebar = None
        self.filter_dock = None

    # --- Batch flags & stats (aman dari AttributeError) ---
        self._batch_stats = {"ok": 0, "rejected": 0, "skipped": 0}
        self._in_batch_mode = False
        self._warning_shown_in_batch = {}
        self._install_safe_shutdown_hooks()

    def keluar_aplikasi(self):
        """Keluar dari aplikasi lewat menu File → Keluar."""
        from PyQt6.QtWidgets import QApplication, QMessageBox

        tanya = QMessageBox.question(
            self,
            "Konfirmasi Keluar",
            "Apakah Anda yakin ingin keluar dari aplikasi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if tanya == QMessageBox.StandardButton.Yes:
            # 🔹 Izinkan closeEvent lewat menu
            self._izin_keluar = True
            QApplication.quit()


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
            # Gunakan FixedDockWidget agar lebar benar-benar fix dan tidak bisa digeser
            fixed_width = 320
            self.filter_dock = FixedDockWidget("Filter", self, fixed_width=fixed_width)
            self.filter_dock.setWidget(self.filter_sidebar)
            
            # Apply current theme to filter sidebar
            current_theme = self.load_theme()
            self.filter_sidebar.apply_theme(current_theme)

            # Tambahkan ke main window
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

    def _encrypt_and_cleanup(self):
        # Backward-compat saja: delegasikan ke satu pintu
        self._shutdown("_encrypt_and_cleanup")

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
        #self.action_dark.setEnabled(False)
        self.action_light.setEnabled(False)
        for act in [self.action_light]:
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
        ##self.action_dark.setEnabled(True)
        self.action_light.setEnabled(True)
        for act in [self.action_light]:
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
                    with sqlite3.connect(self.db_name) as conn:
                        conn.execute(
                            f"UPDATE data_pemilih SET {field_name}=? WHERE NIK=?",
                            (value, nik)
                        )

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
        # === KONFIRMASI AWAL ===
        reply = QMessageBox.question(
            self,
            "Konfirmasi",
            "Apakah kamu yakin ingin menjalankan proses <b>Cek Data</b>?<br><br>"
            "Proses ini akan memeriksa seluruh data dan mungkin memerlukan waktu beberapa detik.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            show_modern_info(self, "Dibatalkan", "Proses cek data dibatalkan oleh pengguna.")
            return

        target_date = datetime(2029, 6, 26)
        nik_seen = {}
        nik_count = {}
        hasil = ["Sesuai"] * len(self.all_data)  # default

        # === Hitung kemunculan NIK dan kelompokkan NKK & KET ===
        nkk_tps_map = {}   # {NKK: set(TPS)}
        nik_ket_map = {}   # {NIK: set(KET)}
        for d in self.all_data:
            nik = str(d.get("NIK", "")).strip()
            nkk = str(d.get("NKK", "")).strip()
            tps = str(d.get("TPS", "")).strip()
            ket = str(d.get("KET", "")).strip().upper()

            if nik:
                nik_count[nik] = nik_count.get(nik, 0) + 1
                nik_ket_map.setdefault(nik, set()).add(ket)
            if nkk:
                nkk_tps_map.setdefault(nkk, set()).add(tps)

        # === Loop utama validasi semua baris di self.all_data ===
        for i, d in enumerate(self.all_data):
            nkk = str(d.get("NKK", "")).strip()
            nik = str(d.get("NIK", "")).strip()
            tgl_lhr = str(d.get("TGL_LHR", "")).strip()
            ket = str(d.get("KET", "")).strip()
            sts = str(d.get("STS", "")).strip()
            tps = str(d.get("TPS", "")).strip()

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

        # === (1) Deteksi NKK sama – TPS berbeda ===
        for i, d in enumerate(self.all_data):
            nkk = str(d.get("NKK", "")).strip()
            ket = str(d.get("KET", "")).strip()
            if nkk and ket not in ("1","2","3","4","5","6","7","8"):
                if len(nkk_tps_map.get(nkk, [])) > 1:
                    hasil[i] = "Beda TPS"

        # === (2) Tandai Ganda ===
        for nik, idxs in nik_seen.items():
            if len(idxs) > 1:
                for j in idxs:
                    ket = str(self.all_data[j].get("KET", ""))
                    hasil[j] = "Sesuai" if ket in ("1","2","3","4","5","6","7","8") else "Ganda Aktif"

        # === (3) Pemilih Baru / Pemilih Pemula ===
        for i, d in enumerate(self.all_data):
            ket = str(d.get("KET", "")).upper()
            nik = str(d.get("NIK", "")).strip()
            if ket == "B":
                hasil[i] = "Pemilih Baru" if nik_count.get(nik, 0) > 1 else "Pemilih Pemula"

        # === (4) KET = 8 tanpa padanan B → Tidak Padan ===
        for i, d in enumerate(self.all_data):
            ket = str(d.get("KET", "")).strip().upper()
            nik = str(d.get("NIK", "")).strip()
            if ket == "8":
                if "B" not in nik_ket_map.get(nik, set()):
                    hasil[i] = "Tidak Padan"

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

            data_update = [(d.get("CEK_DATA", ""), d.get("rowid")) for d in self.all_data if d.get("rowid") is not None]

            cur.executemany("UPDATE data_pemilih SET CEK_DATA = ? WHERE rowid = ?", data_update)
            conn.commit()
            conn.close()
        except Exception as e:
            show_modern_error(self, "Gagal Commit", f"Gagal menyimpan hasil ke database:\n{e}")
            return

        try:
            if hasattr(self, "enc_path"):
                _encrypt_file(self.db_name, self.enc_path)
        except Exception as e:
            print(f"[WARN] Gagal menyinkronkan ke database terenkripsi: {e}")

        # === Refresh tampilan ===
        self.show_page(self.current_page)
        self._warnai_baris_berdasarkan_ket()
        self._terapkan_warna_ke_tabel_aktif()

        show_modern_info(self, "Selesai", f"Pemeriksaan {len(self.all_data):,} data selesai dilakukan!")

    def _warnai_baris_berdasarkan_ket(self):
        from PyQt6.QtGui import QColor, QBrush
        warna_cache = {
            "biru": QBrush(QColor("blue")),
            "merah": QBrush(QColor("red")),
            "kuning": QBrush(QColor("yellow")),
            "hijau": QBrush(QColor("green")),
            "hitam": QBrush(QColor("black")),
            "putih": QBrush(QColor("white")),
        }

        dark_mode = self.load_theme() == "dark"
        warna_default = warna_cache["putih" if dark_mode else "hitam"]
        idx_cekdata = self._col_index("CEK_DATA")
        idx_ket = self._col_index("KET")

        for d in self.all_data:
            cek_data_val = str(d.get("CEK_DATA", "")).strip()
            ket_val = str(d.get("KET", "")).strip()

            if cek_data_val in (
                "NKK Invalid", "Potensi NKK Invalid",
                "NIK Invalid", "Potensi NIK Invalid",
                "Potensi Dibawah Umur", "Dibawah Umur", "Ganda Aktif", "Beda TPS", "Tidak Padan"
            ):
                brush = warna_cache["biru"]
            elif ket_val in ("1", "2", "3", "4", "5", "6", "7", "8"):
                brush = warna_cache["merah"]
            elif ket_val.lower() == "u":
                brush = warna_cache["kuning"]
            elif ket_val.lower() == "b":
                brush = warna_cache["hijau"]
            else:
                brush = warna_default

            d["_warna_font"] = brush


    def _terapkan_warna_ke_tabel_aktif(self):
        from PyQt6.QtGui import QBrush
        start_index = (self.current_page - 1) * self.rows_per_page
        end_index = min(start_index + self.rows_per_page, len(self.all_data))
        page_data = self.all_data[start_index:end_index]

        for row, d in enumerate(page_data):
            brush = d.get("_warna_font", QBrush())
            for c in range(self.table.columnCount()):
                item = self.table.item(row, c)
                if item:
                    item.setForeground(brush)

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
                        if csv_col in header:
                            col_idx = header.index(csv_col)
                            val = row[col_idx].strip()
                            if app_col == "KET":
                                val = val.upper()

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
        """Memuat seluruh data dari database ke self.all_data dengan super ultra kilat dan hasil identik."""
        import sqlite3
        from datetime import datetime

        # ============================================================
        # 1️⃣ Ambil data mentah dari DB
        # ============================================================
        conn = sqlite3.connect(self.db_name, isolation_level=None)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ⚙️ Optimasi kecepatan baca SQLite (non-fatal PRAGMA)
        cur.executescript("""
            PRAGMA synchronous = OFF;
            PRAGMA journal_mode = MEMORY;
            PRAGMA temp_store = MEMORY;
            PRAGMA cache_size = 100000;
            PRAGMA page_size = 4096;
        """)

        # Pastikan tabel ada
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_pemilih (
                KECAMATAN TEXT, DESA TEXT, DPID TEXT, NKK TEXT, NIK TEXT, NAMA TEXT,
                JK TEXT, TMPT_LHR TEXT, TGL_LHR TEXT, STS TEXT, ALAMAT TEXT,
                RT TEXT, RW TEXT, DIS TEXT, KTPel TEXT, SUMBER TEXT, KET TEXT,
                TPS TEXT, LastUpdate DATETIME, CEK_DATA TEXT
            )
        """)

        # ⚡ Fetch super cepat tanpa konversi berulang
        rows = cur.fetchall() if (cur.execute("SELECT rowid, * FROM data_pemilih").description is None) else cur.fetchall()
        if not rows:
            self.all_data = []
            self.total_pages = 1
            self.show_page(1)
            conn.close()
            return

        data_fetch = cur.fetchall() if not rows else rows
        conn.close()

        # ============================================================
        # 2️⃣ Persiapan Header & Cache Formatter
        # ============================================================
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        _tgl_cache = {}

        def format_tgl(val):
            if not val:
                return ""
            v = _tgl_cache.get(val)
            if v:
                return v
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    v = datetime.strptime(val, fmt).strftime("%d/%m/%Y")
                    _tgl_cache[val] = v
                    return v
                except Exception:
                    continue
            _tgl_cache[val] = val
            return val

        # ============================================================
        # 3️⃣ Bangun all_data (list of dict) super cepat
        # ============================================================
        append = list.append
        all_data = []
        for r in data_fetch:
            d = {c: ("" if r[c] is None else str(r[c])) for c in headers if c in r.keys()}
            d["rowid"] = r["rowid"]
            if "LastUpdate" in r.keys() and r["LastUpdate"]:
                d["LastUpdate"] = format_tgl(str(r["LastUpdate"]))
            all_data.append(d)
        self.all_data = all_data
        import gc
        gc.collect()

        # ============================================================
        # 4️⃣ Hitung halaman & tampilkan page 1
        # ============================================================
        total = len(all_data)
        self.total_pages = max(1, (total + self.rows_per_page - 1) // self.rows_per_page)
        self.show_page(1)


        # ==========================================================
        # ⚡ Jalankan pewarnaan setelah GUI tampil (non-blocking, super cepat)
        # ==========================================================
        def apply_colors_safely():
            try:
                # Hindari hitung ulang warna jika sudah pernah
                if not hasattr(self, "_warna_sudah_dihitung") or not self._warna_sudah_dihitung:
                    self._warnai_baris_berdasarkan_ket()
                    self._warna_sudah_dihitung = True

                # Terapkan warna ke halaman aktif (setelah GUI siap)
                self._terapkan_warna_ke_tabel_aktif()
            except Exception as e:
                print(f"[WARN] Gagal menerapkan warna otomatis: {e}")

        # 🔹 Jalankan pewarnaan setelah 100ms (supaya login langsung tampil)
        QTimer.singleShot(100, apply_colors_safely)


    def _ensure_schema_and_migrate(self):
        """
        Pastikan tabel data_pemilih ada, kolom CEK_DATA tersedia,
        dan (jika ada) salin nilai dari kolom lama 'CEK DATA' -> CEK_DATA.
        Idempotent: aman dipanggil berulang.
        """
        import sqlite3

        with sqlite3.connect(self.db_name) as conn:
            cur = conn.cursor()

            # 1) Buat tabel kalau belum ada (versi skema terbaru)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS data_pemilih (
                    KECAMATAN  TEXT,
                    DESA       TEXT,
                    DPID       TEXT,
                    NKK        TEXT,
                    NIK        TEXT,
                    NAMA       TEXT,
                    JK         TEXT,
                    TMPT_LHR   TEXT,
                    TGL_LHR    TEXT,
                    STS        TEXT,
                    ALAMAT     TEXT,
                    RT         TEXT,
                    RW         TEXT,
                    DIS        TEXT,
                    KTPel      TEXT,
                    SUMBER     TEXT,
                    KET        TEXT,
                    TPS        TEXT,
                    LastUpdate DATETIME,
                    CEK_DATA   TEXT
                )
            """)

            # 2) Cek kolom yang ada saat ini
            cur.execute("PRAGMA table_info(data_pemilih)")
            cols = {row[1] for row in cur.fetchall()}  # row[1] = nama kolom

            # 3) Tambahkan CEK_DATA jika belum ada
            if "CEK_DATA" not in cols:
                cur.execute("ALTER TABLE data_pemilih ADD COLUMN CEK_DATA TEXT")

            # 4) Jika ada kolom lama "CEK DATA", salin nilainya sekali
            if "CEK DATA" in cols:
                cur.execute("UPDATE data_pemilih SET CEK_DATA = COALESCE(CEK_DATA, `CEK DATA`)")

            conn.commit()

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
        Urutkan data seluruh halaman (super cepat):
        1️⃣ CEK_DATA = 'Beda TPS' → urut NKK, NIK, NAMA
        2️⃣ CEK_DATA = 'Ganda Aktif' → urut NIK, NAMA
        3️⃣ CEK_DATA = 'Potensi NKK Invalid', 'NIK Invalid', 'Potensi NIK Invalid',
                    'Potensi Dibawah Umur', 'Dibawah Umur', 'Tidak Padan'
            → tetap urutan normal, tapi muncul setelah (1) dan (2)
        4️⃣ Selain itu → urut normal seperti biasa (TPS, RW, RT, NKK, NAMA)
        """
        # ✅ Konfirmasi jika bukan mode otomatis
        if not auto:
            if not show_modern_question(self, "Konfirmasi", "Apakah Anda ingin mengurutkan data?"):
                return

        # 🔹 Kelompok berdasarkan prioritas
        prioritas_0 = {"Beda TPS"}
        prioritas_1 = {"Ganda Aktif"}
        prioritas_2 = {
            "Potensi NKK Invalid",
            "NIK Invalid",
            "Potensi NIK Invalid",
            "Potensi Dibawah Umur",
            "Dibawah Umur",
            "Tidak Padan"
        }

        # 🔹 Fungsi kunci sortir super cepat
        def kunci_sortir(d):
            cek = str(d.get("CEK_DATA", "")).strip()

            # Level prioritas
            if cek in prioritas_0:
                prior = 0
                subkey = (
                    str(d.get("NKK", "")),
                    str(d.get("NIK", "")),
                    str(d.get("NAMA", "")),
                )
            elif cek in prioritas_1:
                prior = 1
                subkey = (
                    str(d.get("NIK", "")),
                    str(d.get("TPS", "")),
                    str(d.get("NAMA", "")),
                )
            elif cek in prioritas_2:
                prior = 2
                subkey = (
                    str(d.get("TPS", "")),
                    str(d.get("RW", "")),
                    str(d.get("RT", "")),
                    str(d.get("NKK", "")),
                    str(d.get("NAMA", "")),
                )
            else:
                prior = 3
                subkey = (
                    str(d.get("TPS", "")),
                    str(d.get("RW", "")),
                    str(d.get("RT", "")),
                    str(d.get("NKK", "")),
                    str(d.get("NAMA", "")),
                )

            return (prior, *subkey)

        # 🔹 Jalankan pengurutan (seluruh halaman, 1-pass, super cepat)
        self.all_data.sort(key=kunci_sortir)

        # 🔹 Refresh tampilan
        self.show_page(1)

        # 🔹 Terapkan ulang warna (non-blocking)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

        # ✅ Popup selesai
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
        """Versi super kilat dengan hasil identik (optimal untuk 10.000+ baris)."""
        if page < 1 or page > self.total_pages:
            return

        self.current_page = page
        self.table.blockSignals(True)

        start = (page - 1) * self.rows_per_page
        end = min(start + self.rows_per_page, len(self.all_data))
        data_rows = self.all_data[start:end]

        # =========================================================
        # 🧹 Clear isi lama tanpa reset struktur tabel
        # =========================================================
        self.table.clearContents()
        self.table.setRowCount(len(data_rows) or 1)

        # =========================================================
        # 🚫 Jika kosong, tampilkan pesan
        # =========================================================
        if not data_rows:
            item = QTableWidgetItem("Data Tidak Ditemukan")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setItalic(True)
            font.setBold(True)
            item.setFont(font)
            item.setForeground(QColor("gray"))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(0, 0, item)
            self.table.setSpan(0, 0, 1, self.table.columnCount())
            self.table.blockSignals(False)
            if hasattr(self, "lbl_selected"):
                self.lbl_selected.setText("0 selected")
            self.update_statusbar()
            self.update_pagination()
            return

        # =========================================================
        # 📋 Persiapan variabel agar loop cepat
        # =========================================================
        setItem = self.table.setItem
        newItem = QTableWidgetItem
        colCount = self.table.columnCount()
        headerItems = [self.table.horizontalHeaderItem(i).text() for i in range(colCount)]
        center_cols = {"DPID", "JK", "STS", "TGL_LHR", "RT", "RW", "DIS", "KTPel", "KET", "TPS"}
        ket_index = self.col_index("KET")

        # =========================================================
        # 🎨 Mapping warna super kilat
        # =========================================================
        warna_map = {
            "B": QColor("green"),   # BARU
            "U": QColor("orange"),  # UBAH
        }
        tms_vals = {"1", "2", "3", "4", "5", "6", "7", "8"}  # TMS
        warna_default = QColor("black")

        # =========================================================
        # 🧮 Isi tabel dengan loop minimalis
        # =========================================================
        for i, d in enumerate(data_rows):
            # Checkbox
            chk = newItem("")
            chk.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            chk.setCheckState(Qt.CheckState.Unchecked)
            setItem(i, 0, chk)

            # Kolom lain
            for j, col in enumerate(headerItems[1:], start=1):
                if col == "_rowid_":
                    continue
                val = d.get(col, "")
                if col == "LastUpdate" and val:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            val = datetime.strptime(val, fmt).strftime("%d/%m/%Y")
                            break
                        except Exception:
                            pass
                cell = newItem(val)
                if col in center_cols:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                setItem(i, j, cell)

            # Pewarnaan baris berdasarkan kolom KET
            ket_val = str(d.get("KET", "")).strip().upper()
            warna = warna_map.get(ket_val, warna_default)
            if ket_val in tms_vals:
                warna = QColor("red")

            for c in range(colCount):
                cell = self.table.item(i, c)
                if cell:
                    cell.setForeground(warna)

        # =========================================================
        # 🔁 Update tampilan & pagination
        # =========================================================
        self.table.blockSignals(False)
        if hasattr(self, "lbl_selected"):
            self.lbl_selected.setText("0 selected")
        self.update_statusbar()
        self.update_pagination()
        self.table.horizontalHeader().setSortIndicatorShown(False)

        QTimer.singleShot(0, self.auto_fit_columns)
        QTimer.singleShot(0, self.sync_header_checkbox_state)
        self._terapkan_warna_ke_tabel_aktif()

        
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
            try:
                app.aboutToQuit.disconnect()
            except Exception:
                pass
            app.aboutToQuit.connect(lambda: self._shutdown("aboutToQuit"))

        # atexit (nyaris selalu terpanggil)
        try:
            atexit.unregister(lambda: self._shutdown("atexit"))
        except Exception:
            pass
        atexit.register(lambda: self._shutdown("atexit"))

        # Sinyal OS (Windows terbatas untuk SIGTERM)
        try:
            import signal
            signal.signal(signal.SIGINT,  lambda s, f: self._shutdown("SIGINT"))
            signal.signal(signal.SIGTERM, lambda s, f: self._shutdown("SIGTERM"))
        except Exception:
            pass

    def _graceful_terminate(self, source):
        """Commit + encrypt lalu keluar rapi."""
        try:
            self._shutdown(source)
        finally:
            app = QApplication.instance()
            if app:
                app.quit()

    def closeEvent(self, event):
        """Cegah keluar lewat tombol X, kecuali lewat menu File → Keluar."""
        # 🔹 Jika keluar lewat menu resmi, izinkan & jalankan shutdown
        if hasattr(self, "_izin_keluar") and self._izin_keluar:
            try:
                self._shutdown("closeEvent")  # tetap jalankan proses tutup yang kamu punya
            except Exception as e:
                print(f"[WARN] Gagal menjalankan _shutdown: {e}")
            event.accept()
            super().closeEvent(event)
            return

        # 🔹 Jika bukan lewat menu, blokir
        event.ignore()
        QMessageBox.warning(
            self,
            "Tindakan Diblokir",
            "Gunakan menu <b>File → Keluar</b> untuk menutup aplikasi.",
            QMessageBox.StandardButton.Ok
        )


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

    def _shutdown(self, source: str = ""):
        if getattr(self, "_did_shutdown", False):
            return
        self._did_shutdown = True

        # 1) Pastikan transaksi beres
        try:
            self._flush_db(source or "_shutdown")
        except Exception as e:
            print(f"[WARN] _flush_db({source}) gagal: {e}")

        # 2) Enkripsi plaintext -> final .enc
        try:
            if hasattr(self, "plain_db_path") and hasattr(self, "enc_path"):
                if self.plain_db_path and os.path.exists(self.plain_db_path):
                    _encrypt_file(self.plain_db_path, self.enc_path)
                    #####print(f"[INFO] Shutdown: terenkripsi ke {self.enc_path}")#####
        except Exception as e:
            print(f"[WARN] Encrypt on shutdown ({source}) gagal: {e}")

        # 3) Bersihkan artefak temp (plaintext & temp .enc)
        for p in (getattr(self, "plain_db_path", ""), getattr(self, "plain_db_path", "") + ".enc"):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception as ee:
                print(f"[WARN] Gagal menghapus artefak {p}: {ee}")


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