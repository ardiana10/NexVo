## -*- coding: utf-8 -*-
r"""
NexVo 2.0 (SQLCipher edition)
--------------------------------
• Satu database terenkripsi penuh: nexvo.db
• Lokasi DB: %APPDATA%\NexVo\nexvo.db (contoh: C:\\Users\\<nama_user>\\AppData\\Roaming\\NexVo)
• Kunci unik per‑komputer: %APPDATA%\Aplikasi\nexvo.key (binary 32 byte)
• 5 tabel: user, kecamatan, dphp, dpshp, dpshpa
• UI: Form Login full screen, tema putih lembut + hover oranye

Catatan:
- Butuh paket: PyQt6, sqlcipher3-wheels (Windows) / sqlcipher3 (Linux/Mac dengan SQLCipher terpasang)
- Jalankan: python nexvo.py
"""

import os, sys, subprocess, csv, hashlib, random, string, re, locale
from pathlib import Path
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from collections import defaultdict
from typing import Optional
from io import BytesIO
import pyotp, qrcode
import datetime  # jika ada kode yang memakai gaya: datetime.date.today()

# =========================
# Database / SQLCipher
# =========================
from db_manager import (
    close_connection, get_connection, with_safe_db, bootstrap,
    connect_encrypted, hapus_semua_data,
)
try:
    from sqlcipher3 import dbapi2 as sqlcipher
except Exception as e:
    print("[ERROR] sqlcipher3 belum terpasang. Install: pip install sqlcipher3-wheels (Windows) atau sqlcipher3.")
    raise

# =========================
# PyQt6
# =========================
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer, QRegularExpression, QPointF, QRectF,
    QRect, QEvent, QMargins, QVariantAnimation, QAbstractAnimation, QPoint, QSize, QIODevice, QBuffer, QDate
)
from PyQt6.QtGui import (
    QIcon, QFont, QColor, QPixmap, QPainter, QAction,
    QPalette, QBrush, QPen, QRegularExpressionValidator,
    QRadialGradient, QPolygon, QKeyEvent, QTextCursor, QPageLayout
)
from PyQt6.QtCharts import QChart, QChartView, QPieSeries, QLegend
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QDockWidget, QMenu,
    QStackedWidget, QStatusBar, QToolBar, QToolButton, QHeaderView, QTableWidget,
    QTableWidgetItem, QStyledItemDelegate, QAbstractItemView, QStyle,
    QFileDialog, QScrollArea, QFormLayout, QInputDialog, QSlider, QGridLayout, QProgressBar,
    QVBoxLayout, QHBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QRadioButton, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QDialogButtonBox,
    QGraphicsSimpleTextItem, QSizePolicy, QSpacerItem, QStyleOptionButton, QDateEdit, QTextEdit, QStyleFactory, QCalendarWidget
)
from PyQt6.QtWidgets import QCompleter
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView

# =========================
# ReportLab (PDF)
# =========================
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage, LongTable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfgen import canvas

# ==========================================================
# Konstanta path Windows (AppData\Roaming)
# ==========================================================
APPDATA = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
NEXVO_DIR = Path(APPDATA) / "NexVo"
APLIKASI_DIR = Path(APPDATA) / "Aplikasi"
DB_PATH = NEXVO_DIR / "nexvo.db"
KEY_PATH = APLIKASI_DIR / "nexvo.key"  # binary (32 byte)


# ==========================================================
# Util: Key management (kunci unik per-komputer)
# ==========================================================
def ensure_dirs() -> None:
    r"""Pastikan folder NexVo dan Aplikasi ada di AppData\Roaming."""
    NEXVO_DIR.mkdir(parents=True, exist_ok=True)
    APLIKASI_DIR.mkdir(parents=True, exist_ok=True)


def load_or_create_key() -> bytes:
    """Buat atau baca kunci biner 32-byte yang disimpan di %APPDATA%/Aplikasi/nexvo.key.
    Disimpan sebagai BINARY (bukan teks)."""
    ensure_dirs()
    if KEY_PATH.exists():
        data = KEY_PATH.read_bytes()
        if len(data) != 32:
            # Jika format lama/invalid, regenerasi aman
            data = os.urandom(32)
            KEY_PATH.write_bytes(data)
        return data
    # Generate baru (32 byte)
    key = os.urandom(32)
    KEY_PATH.write_bytes(key)
    try:
        # Set permission file konservatif (Windows tidak 100% sama POSIX, tapi tetap berguna)
        os.chmod(KEY_PATH, 0o600)
    except Exception:
        pass
    return key


# ==========================================================
# DB: koneksi terenkripsi & inisialisasi schema
# ==========================================================
def connect_encrypted_db(db_path: Path, key_bytes: bytes):
    """Buka/buat DB terenkripsi dengan raw key (32 byte) via SQLCipher.
    Kita gunakan PRAGMA key dengan format hex raw key: x'...'
    """
    conn = sqlcipher.connect(str(db_path))

    # Pakai raw key (32 byte) → hex
    hexkey = key_bytes.hex()
    conn.execute(f"PRAGMA key = \"x'{hexkey}'\";")

    # Hardening opsional
    conn.execute("PRAGMA cipher_page_size = 4096;")
    conn.execute("PRAGMA kdf_iter = 64000;")
    conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
    conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Sanity check: pastikan kunci benar (akan error jika tidak cocok)
    conn.execute("SELECT count(*) FROM sqlite_master;")
    return conn


def init_schema(conn) -> None:
    """
    Membuat semua tabel utama (users, kecamatan, dphp, dpshp, dpshpa, dan tabel rekap)
    jika belum ada. Aman dijalankan berulang kali.
    """
    import os, sys, subprocess
    cur = conn.cursor()

    # --- Tabel users ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT,
            email TEXT,
            kecamatan TEXT,
            desa TEXT,
            password TEXT,
            otp_secret TEXT
        );
    """)

    # --- Tabel kecamatan ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kecamatan (
            kecamatan TEXT,
            desa TEXT
        );
    """)

    # --- Tabel tahapan (DPHP, DPSHP, DPSHPA) ---
    common_schema = """
        (
            checked INTEGER DEFAULT 0,
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
            LastUpdate TEXT,
            CEK_DATA TEXT
        )
    """
    for tbl in ("dphp", "dpshp", "dpshpa"):
        cur.execute(f"CREATE TABLE IF NOT EXISTS {tbl} {common_schema};")

    # =========================================================
    # 🧾 Tambahan: tabel-tabel rekapitulasi
    # =========================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rekap (
            "NAMA TPS" TEXT,
            "JUMLAH KK" INTEGER,
            "LAKI-LAKI" INTEGER,
            "PEREMPUAN" INTEGER,
            "JUMLAH" INTEGER
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS baru (
            "NAMA TPS" TEXT,
            "JUMLAH KK" INTEGER,
            "LAKI-LAKI" INTEGER,
            "PEREMPUAN" INTEGER,
            "JUMLAH" INTEGER
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ubah (
            "NAMA TPS" TEXT,
            "JUMLAH KK" INTEGER,
            "LAKI-LAKI" INTEGER,
            "PEREMPUAN" INTEGER,
            "JUMLAH" INTEGER
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS saring (
            "NAMA TPS" TEXT,
            "1L" INTEGER, "1P" INTEGER,
            "2L" INTEGER, "2P" INTEGER,
            "3L" INTEGER, "3P" INTEGER,
            "4L" INTEGER, "4P" INTEGER,
            "5L" INTEGER, "5P" INTEGER,
            "6L" INTEGER, "6P" INTEGER,
            "7L" INTEGER, "7P" INTEGER,
            "8L" INTEGER, "8P" INTEGER,
            "TMS L" INTEGER, "TMS P" INTEGER,
            "JUMLAH" INTEGER
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ktpel (
            "NAMA TPS" TEXT,
            "JUMLAH KK" INTEGER,
            "LAKI-LAKI" INTEGER,
            "PEREMPUAN" INTEGER,
            "JUMLAH" INTEGER
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS difabel (
            "NAMA TPS" TEXT,
            "JUMLAH KK" INTEGER,
            "FISIK" INTEGER,
            "INTELEKTUAL" INTEGER,
            "MENTAL" INTEGER,
            "DIF. WICARA" INTEGER,
            "DIF. RUNGU" INTEGER,
            "DIF. NETRA" INTEGER,
            "JUMLAH" INTEGER
        );
    """)

    conn.commit()

    # --- Isi kecamatan otomatis jika kosong ---
    try:
        cur.execute("SELECT COUNT(*) FROM kecamatan")
        count = cur.fetchone()[0]
    except Exception:
        count = 0

    if count == 0:
        print("[INFO] Tabel 'kecamatan' kosong → menjalankan init_db.py ...")
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(base_dir, "init_db.py")
            if os.path.exists(script_path):
                subprocess.run([sys.executable, script_path], check=True)
                print("[✅] Data kecamatan berhasil diinisialisasi otomatis.")
            else:
                print(f"[PERINGATAN] File init_db.py tidak ditemukan di {script_path}")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] init_db.py gagal dijalankan: {e}")
        except Exception as e:
            print(f"[ERROR] Gagal menjalankan init_db.py: {e}")


def hapus_semua_data(conn):
    """Hapus semua data dinamis tanpa mengganggu tabel master atau metadata internal."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [
            r[0] for r in cur.fetchall()
            if r[0] not in ("sqlite_sequence", "kecamatan")
        ]

        for tbl in tables:
            cur.execute(f"DELETE FROM {tbl};")

        conn.commit()
        print("[INFO] Semua data berhasil dihapus.")

    except Exception as e:
        print(f"[PERINGATAN] Gagal hapus data: {e}")



def show_modern_warning(parent, title, text):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)

    msg.setWindowModality(Qt.WindowModality.NonModal)              # ✅ perbaikan
    msg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    _apply_modern_style(msg, accent="#ff6600")
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
    _apply_modern_style(msg, accent="#ff6600")
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
    _apply_modern_style(msg, accent="#ff6600")
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
            background-color: #EFEFEF;
            color: black;
            font-family: 'Segoe UI';
            font-size: 11pt;
            border-radius: 12px;
        }
        QLabel {
            background: transparent;     /* ✅ Hilangkan background hitam */
            color: black;
            font-size: 11pt;
            padding: 4px 2px;
        }
        QPushButton {
            background-color: #ff6600;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: bold;
            font-size: 10.5pt;
            min-width: 120px;
        }
        QPushButton:hover {
            background-color: #d71d1d;
        }
    """)

    msg.button(QMessageBox.StandardButton.Yes).setText("Ya")
    msg.button(QMessageBox.StandardButton.No).setText("Tidak")

    result = msg.exec()
    return result == QMessageBox.StandardButton.Yes

# ===================================================
# 🎨 Gaya Universal Modern QMessageBox
# ===================================================
def _apply_modern_style(msg, accent="#d71d1d"):
    lighter = _lighten_color(accent)
    msg.setStyleSheet(f"""
        QMessageBox {{
            background-color: #EFEFEF;
            color: white;
            font-family: 'Segoe UI';
            font-size: 11pt;
            border-radius: 12px;
            border: 1px solid #444;
        }}
        QLabel {{
            background: transparent;     /* ✅ Hilangkan background hitam */
            color: black;
            font-size: 11pt;
            margin: 4px;
        }}
        QPushButton {{
            background-color: #d71d1d;
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
                background-color: #EFEFEF;
                border-radius: 12px;
                border: 1px solid #444;
            }
            QLabel {
                color: black;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            QPushButton {
                background-color: #d71d1d;
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 🌈 Style utama (tanpa warna hitam di luar)
        self.setStyleSheet("""
            QLabel {
                color: black;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            QLineEdit {
                background-color: #F0F0F0;
                color: black;
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
                background-color: #d71d1d;
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        color = QColor(255, 255, 255, 255)  # Putih solid
        painter.setBrush(color)
        painter.setPen(QPen(QColor(180, 180, 180, 200)))  # Border abu lembut
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 12, 12)

    def center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center() - self.rect().center())

    def getText(self):
        """Kembalikan teks input jika OK ditekan."""
        if self.exec() == QDialog.DialogCode.Accepted:
            return self.line_edit.text(), True
        return "", False    

@with_safe_db
def get_kecamatan(conn=None):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT kecamatan FROM kecamatan ORDER BY kecamatan")
    return [row[0] for row in cur.fetchall()]


@with_safe_db
def get_desa(kecamatan, conn=None):
    cur = conn.cursor()
    cur.execute("SELECT desa FROM kecamatan WHERE kecamatan = ? ORDER BY desa", (kecamatan,))
    return [row[0] for row in cur.fetchall()]

class CheckboxDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        # 🛡️ Abaikan jika tabel kosong atau index tidak valid
        model = index.model()
        if not model or index.row() >= model.rowCount() or index.column() != 0:
            return

        value = index.data(Qt.ItemDataRole.CheckStateRole)
        if value is None:
            return  # jangan gambar apa-apa

        try:
            state = Qt.CheckState(value)
        except Exception:
            state = Qt.CheckState.Unchecked

        option.state &= ~QStyle.StateFlag.State_Selected
        option.state &= ~QStyle.StateFlag.State_HasFocus

        rect = self.get_checkbox_rect(option)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Gambar checkbox
        if state == Qt.CheckState.Unchecked:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#A0A0A0"), 1.2))
            painter.drawRoundedRect(rect, 3, 3)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#000000"), 1.2))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QPen(QColor("#C42525"), 2))
            painter.drawLine(rect.left() + 3, rect.center().y(),
                             rect.center().x() - 1, rect.bottom() - 4)
            painter.drawLine(rect.center().x() - 1, rect.bottom() - 4,
                             rect.right() - 3, rect.top() + 3)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if not index.flags() & Qt.ItemFlag.ItemIsUserCheckable or not index.flags() & Qt.ItemFlag.ItemIsEnabled:
            return False

        if event.type() == event.Type.MouseButtonRelease:
            raw = index.data(Qt.ItemDataRole.CheckStateRole)
            try:
                current = Qt.CheckState(raw)
            except Exception:
                current = Qt.CheckState.Unchecked

            new_state = (Qt.CheckState.Unchecked
                         if current == Qt.CheckState.Checked
                         else Qt.CheckState.Checked)
            model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
            return True
        return False

    def get_checkbox_rect(self, option):
        size = 13
        x = option.rect.x() + (option.rect.width() - size) // 2
        y = option.rect.y() + (option.rect.height() - size) // 2
        return QRect(x, y, size, size)

# =====================================================
# Dialog Setting Aplikasi
# =====================================================
class SettingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tampilan Pemutakhiran")
        self.setFixedSize(280, 400)

        # === Ambil info dari MainWindow ===
        self.parent_window = parent
        self._tahapan = getattr(parent, "_tahapan", "DPHP")
        self._active_table = parent._active_table() if parent else "dphp"

        layout = QVBoxLayout(self)

        # === Style checkbox ===
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
                background-color: #ff9900;
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
            ("KET", "Keterangan"),
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

        # === Tombol ===
        btn_layout = QHBoxLayout()
        btn_tutup = QPushButton("Tutup")
        btn_simpan = QPushButton("Simpan")

        btn_tutup.setStyleSheet("background:#444; color:white; min-width:100px; min-height:30px; border-radius:6px;")
        btn_simpan.setStyleSheet("background:#ff6600; color:white; font-weight:bold; min-width:100px; min-height:30px; border-radius:6px;")

        btn_tutup.clicked.connect(self.reject)
        btn_simpan.clicked.connect(lambda: (self.save_settings(), self.parent_window.apply_column_visibility()))

        btn_layout.addWidget(btn_tutup)
        btn_layout.addWidget(btn_simpan)
        layout.addLayout(btn_layout)

        # Muat status awal
        self.load_settings()

    # =========================================================
    # 🔹 Load & Save Setting ke tabel setting_aplikasi_{TAHAPAN}
    # =========================================================
    @with_safe_db
    def load_settings(self, *args, conn=None):
        """Memuat status checkbox kolom dari tabel setting_aplikasi_<tahapan>."""
        cur = conn.cursor()

        tbl_name = f"setting_aplikasi_{self._tahapan.lower()}"
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_name} (
                nama_kolom TEXT PRIMARY KEY,
                tampil INTEGER
            )
        """)
        cur.execute(f"SELECT nama_kolom, tampil FROM {tbl_name}")
        rows = dict(cur.fetchall())

        for col, _ in self.columns:
            checked = bool(rows.get(col, 1))  # default tampil
            if col in self.checks:
                self.checks[col].setChecked(checked)


    @with_safe_db
    def save_settings(self, checked: bool = False, conn=None):
        cur = conn.cursor()

        tbl_name = f"setting_aplikasi_{self._tahapan.lower()}"
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_name} (
                nama_kolom TEXT PRIMARY KEY,
                tampil INTEGER
            )
        """)

        for col, _ in self.columns:
            val = 1 if self.checks[col].isChecked() else 0
            cur.execute(
                f"INSERT OR REPLACE INTO {tbl_name} (nama_kolom, tampil) VALUES (?, ?)",
                (col, val)
            )

        # Tidak perlu conn.commit(); decorator sudah commit.
        self.accept()


# =========================================================
# 🔹 FUNGSI GLOBAL: PALET TEMA
# =========================================================
def apply_global_palette(app, mode: str):
    """Atur palet global (QPalette) agar semua widget ikut tema aktif."""
    palette = QPalette()
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
    app.setPalette(palette)

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
    
    PERUBAHAN: Widget otomatis non-aktif ketika kehilangan focus
    """
    
    def __init__(self, minimum=0, maximum=100, parent=None):
        super().__init__(parent)
        
        # === Pengaturan Nilai Rentang ===
        self._min = minimum
        self._max = maximum
        self._lower = minimum
        self._upper = maximum
        
        # === Pengaturan Visual ===
        self._bar_height = 4
        self._handle_radius = 7
        
        # === State Management ===
        self._active_handle = None
        self._hover_lower = False
        self._hover_upper = False
        self._hover_track = False
        self._hover_active_track = False
        
        # Persistent states
        self._persistent_lower = False
        self._persistent_upper = False
        
        # === Sistem Animasi ===
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._update_handle_animation)
        self._animation_timer.setInterval(16)
        
        self._target_lower = minimum
        self._target_upper = maximum
        self._animation_speed = 0.18
        
        self._label_fade_timer = QTimer(self)
        self._label_fade_timer.timeout.connect(self._update_label_fade)
        self._label_fade_timer.setInterval(25)
        
        self._label_opacity = {'lower': 0.0, 'upper': 0.0}
        self._target_opacity = {'lower': 0.0, 'upper': 0.0}
        
        # === Pengaturan Widget ===
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # === Tema dan Warna ===
        self._dark_theme = False
        self._accent_color = QColor('#ff9900')
        
        self.setFixedHeight(self._handle_radius * 2 + 50)

    # ============================================================
    # METODE BARU: Focus Event Handler
    # ============================================================
    
    def focusOutEvent(self, event):
        """
        Menangani event ketika widget kehilangan focus.
        
        Otomatis menonaktifkan semua persistent state dan fade out label
        ketika user mengklik widget lain atau area di luar.
        """
        # Nonaktifkan semua persistent state
        self._persistent_lower = False
        self._persistent_upper = False
        self._active_handle = None
        
        # Fade out semua label
        self._target_opacity['lower'] = 0.0
        self._target_opacity['upper'] = 0.0
        
        # Start fade animation
        if not self._label_fade_timer.isActive():
            self._label_fade_timer.start()
        
        self.update()
        super().focusOutEvent(event)
    
    def mousePressEvent(self, event):
        """
        Menangani event klik mouse.
        
        PERUBAHAN: Sekarang otomatis set focus ke widget ini saat diklik
        """
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        # Set focus ke widget ini ketika diklik
        self.setFocus()
        
        # Kalkulasi area track
        left_bound = self._handle_radius
        right_bound = self.width() - self._handle_radius
        
        left_handle_x = self._value_to_x_position(self._lower, left_bound, right_bound)
        right_handle_x = self._value_to_x_position(self._upper, left_bound, right_bound)
        
        mouse_x = event.position().x()
        mouse_y = event.position().y()
        
        click_tolerance = self._handle_radius + 4
        
        clicked_on_lower = abs(mouse_x - left_handle_x) <= click_tolerance
        clicked_on_upper = abs(mouse_x - right_handle_x) <= click_tolerance
        
        if clicked_on_lower:
            if self._persistent_lower:
                self._persistent_lower = False
                self._active_handle = None
            else:
                self._active_handle = 'lower'
                self._persistent_upper = False
                
        elif clicked_on_upper:
            if self._persistent_upper:
                self._persistent_upper = False
                self._active_handle = None
            else:
                self._active_handle = 'upper'
                self._persistent_lower = False
                
        else:
            center_y = self.height() // 2 + 5
            side_margin = 8
            track_left = side_margin + self._handle_radius
            track_right = self.width() - (side_margin + self._handle_radius)
            
            is_in_track = (track_left <= mouse_x <= track_right) and (abs(mouse_y - center_y) <= 15)
            
            if is_in_track:
                self._persistent_lower = False
                self._persistent_upper = False
                
                if abs(mouse_x - left_handle_x) < abs(mouse_x - right_handle_x):
                    self._active_handle = 'lower'
                else:
                    self._active_handle = 'upper'
            else:
                self._persistent_lower = False
                self._persistent_upper = False
                self._active_handle = None
        
        if self._active_handle:
            self.mouseMoveEvent(event)
            
        self.update()

    # ============================================================
    # METODE UTILITY
    # ============================================================

    def sizeHint(self):
        return QSize(160, self._handle_radius * 2 + 10)

    def setDark(self, dark_mode: bool):
        self._dark_theme = dark_mode
        self.update()

    def setRange(self, minimum, maximum):
        self._min, self._max = minimum, maximum
        self._lower = max(self._min, min(self._lower, self._max))
        self._upper = max(self._min, min(self._upper, self._max))
        if self._lower > self._upper:
            self._lower, self._upper = self._upper, self._lower
        self.update()

    def lowerValue(self):
        return self._lower
        
    def upperValue(self):
        return self._upper
        
    def values(self):
        return self._lower, self._upper

    def setValues(self, lower_val, upper_val):
        self._target_lower = max(self._min, min(lower_val, upper_val))
        self._target_upper = min(self._max, max(upper_val, self._target_lower))
        
        if not hasattr(self, '_animation_timer'):
            self._lower = self._target_lower
            self._upper = self._target_upper
        else:
            self._animation_timer.start()
            
        self.update()
        self._emit_value_changed()

    def _update_handle_animation(self):
        animation_active = False
        
        lower_difference = self._target_lower - self._lower
        if abs(lower_difference) > 0.1:
            self._lower += lower_difference * self._animation_speed
            animation_active = True
        else:
            self._lower = self._target_lower
            
        upper_difference = self._target_upper - self._upper
        if abs(upper_difference) > 0.1:
            self._upper += upper_difference * self._animation_speed
            animation_active = True
        else:
            self._upper = self._target_upper
            
        if animation_active:
            self.update()
        else:
            self._animation_timer.stop()

    def _update_label_fade(self):
        animation_active = False
        fade_speed = 0.25
        
        for handle_type in ['lower', 'upper']:
            opacity_difference = self._target_opacity[handle_type] - self._label_opacity[handle_type]
            
            if abs(opacity_difference) > 0.01:
                self._label_opacity[handle_type] += opacity_difference * fade_speed
                animation_active = True
            else:
                self._label_opacity[handle_type] = self._target_opacity[handle_type]
                
        if animation_active:
            self.update()
        else:
            self._label_fade_timer.stop()

    def _emit_value_changed(self):
        if hasattr(self.parent(), 'on_age_range_changed'):
            try:
                self.parent().on_age_range_changed(int(self._lower), int(self._upper))
            except Exception:
                pass

    # ============================================================
    # PAINTING METHODS
    # ============================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        widget_width = self.width()
        widget_height = self.height()
        center_y = widget_height // 2 + 5
        
        side_margin = 8
        track_left = side_margin + self._handle_radius
        track_right = widget_width - (side_margin + self._handle_radius)
        
        self._draw_background_track(painter, track_left, track_right, center_y)
        
        left_handle_x = self._value_to_x_position(self._lower, track_left, track_right)
        right_handle_x = self._value_to_x_position(self._upper, track_left, track_right)
        self._draw_selection_area(painter, left_handle_x, right_handle_x, center_y)
        
        self._draw_handle_and_label(painter, 'lower', left_handle_x, center_y)
        self._draw_handle_and_label(painter, 'upper', right_handle_x, center_y)
        
        painter.end()

    def _draw_background_track(self, painter, left, right, center_y):
        if self._hover_track:
            track_color = QColor('#444') if self._dark_theme else QColor('#bbb')
        else:
            track_color = QColor('#333') if self._dark_theme else QColor('#dcdcdc')
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        
        track_rect = QRect(left, center_y - self._bar_height // 2, 
                          right - left, self._bar_height)
        painter.drawRoundedRect(track_rect, 2, 2)

    def _draw_selection_area(self, painter, left_x, right_x, center_y):
        selection_rect = QRect(int(left_x), center_y - self._bar_height // 2, 
                              int(right_x - left_x), self._bar_height)
        
        if self._hover_active_track:
            hover_accent = QColor(self._accent_color)
            hover_accent.setAlpha(180)
            painter.setBrush(hover_accent)
        else:
            painter.setBrush(self._accent_color)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(selection_rect, 2, 2)

    def _draw_handle_and_label(self, painter, handle_type, x_position, center_y):
        is_hover = (handle_type == 'lower' and self._hover_lower) or \
                   (handle_type == 'upper' and self._hover_upper)
        is_pressed = self._active_handle == handle_type
        is_persistent = (handle_type == 'lower' and self._persistent_lower) or \
                       (handle_type == 'upper' and self._persistent_upper)
        
        is_active = is_hover or is_pressed or is_persistent
        
        if is_pressed or is_persistent:
            self._draw_glow_effect(painter, x_position, center_y)
        
        self._draw_handle_circle(painter, x_position, center_y, is_active)
        self._draw_handle_label(painter, handle_type, x_position, center_y, is_active)

    def _draw_glow_effect(self, painter, x_position, center_y):
        glow_color = QColor('#ff9900')
        
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
        if self._dark_theme:
            face_color = QColor('#3a3a3a') if is_active else QColor('#2a2a2a')
        else:
            face_color = QColor('#f8f8f8') if is_active else QColor('#ffffff')
            
        border_color = QColor('#ff9900')
        
        painter.setBrush(face_color)
        
        border_pen = QPen(border_color)
        border_pen.setWidth(2)
        painter.setPen(border_pen)
        
        handle_rect = QRect(int(x_position - self._handle_radius), 
                           int(center_y - self._handle_radius),
                           2 * self._handle_radius, 2 * self._handle_radius)
        painter.drawEllipse(handle_rect)
        
        if is_active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(border_color)
            center_dot = QRect(int(x_position - 2), int(center_y - 2), 4, 4)
            painter.drawEllipse(center_dot)

    def _draw_handle_label(self, painter, handle_type, x_position, center_y, is_active):
        opacity = self._label_opacity.get(handle_type, 0.0)
        should_show_label = is_active or opacity > 0.01
        
        if not should_show_label or opacity <= 0.01:
            return
            
        value = int(self._lower) if handle_type == 'lower' else int(self._upper)
        label_text = str(value)
        
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        
        font_metrics = painter.fontMetrics()
        padding_horizontal = 8
        padding_vertical = 4
        text_width = font_metrics.horizontalAdvance(label_text) + padding_horizontal
        text_height = font_metrics.height() + padding_vertical
        
        distance_from_center = 35 if (is_active and self._active_handle == handle_type) else 25
        label_top_y = int(center_y - distance_from_center - text_height)
        
        if label_top_y < 2:
            label_top_y = 2
            
        bubble_rect = QRect(int(x_position - text_width / 2), label_top_y, 
                           int(text_width), int(text_height))
        
        alpha = int(240 * opacity)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(60, 60, 60, alpha))
        painter.drawRoundedRect(bubble_rect, 4, 4)
        
        self._draw_label_pointer(painter, x_position, label_top_y + text_height, alpha)
        
        text_alpha = int(255 * opacity)
        painter.setPen(QColor(255, 255, 255, text_alpha))
        painter.drawText(bubble_rect, Qt.AlignmentFlag.AlignCenter, label_text)

    def _draw_label_pointer(self, painter, x_position, bottom_y, alpha):
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
        if self._max == self._min:
            return left_bound
        ratio = (value - self._min) / (self._max - self._min)
        return left_bound + ratio * (right_bound - left_bound)

    def _x_position_to_value(self, x_position, left_bound, right_bound):
        ratio = (x_position - left_bound) / (right_bound - left_bound)
        value = self._min + ratio * (self._max - self._min)
        return int(round(max(self._min, min(value, self._max))))

    # ============================================================
    # MOUSE EVENT HANDLERS
    # ============================================================

    def mouseMoveEvent(self, event):
        left_bound = self._handle_radius
        right_bound = self.width() - self._handle_radius
        left_handle_x = self._value_to_x_position(self._lower, left_bound, right_bound)
        right_handle_x = self._value_to_x_position(self._upper, left_bound, right_bound)
        
        mouse_x = event.position().x()
        mouse_y = event.position().y()
        
        prev_hover_lower = self._hover_lower
        prev_hover_upper = self._hover_upper
        self._hover_lower = False
        self._hover_upper = False
        self._hover_track = False
        self._hover_active_track = False
        
        hit_radius = self._handle_radius + 6
        
        if abs(mouse_x - left_handle_x) <= hit_radius:
            self._hover_lower = True
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._target_opacity['lower'] = 1.0
            if self._label_opacity['lower'] < 0.3:
                self._label_opacity['lower'] = 0.4
                
        elif abs(mouse_x - right_handle_x) <= hit_radius:
            self._hover_upper = True
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._target_opacity['upper'] = 1.0
            if self._label_opacity['upper'] < 0.3:
                self._label_opacity['upper'] = 0.4
                
        else:
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
        
        if not self._hover_lower and not (self._active_handle == 'lower') and not self._persistent_lower:
            self._target_opacity['lower'] = 0.0
        if not self._hover_upper and not (self._active_handle == 'upper') and not self._persistent_upper:
            self._target_opacity['upper'] = 0.0
            
        if self._persistent_lower:
            self._target_opacity['lower'] = 1.0
        if self._persistent_upper:
            self._target_opacity['upper'] = 1.0
            
        if (prev_hover_lower != self._hover_lower or prev_hover_upper != self._hover_upper):
            if not self._label_fade_timer.isActive():
                self._label_fade_timer.start()
        
        if self._active_handle:
            self._hover_track = True
            self._hover_active_track = True
            
            if self._active_handle == 'lower':
                self._target_opacity['lower'] = 1.0
            elif self._active_handle == 'upper':
                self._target_opacity['upper'] = 1.0
        
        self.update()
        
        if self._active_handle:
            new_value = self._x_position_to_value(mouse_x, left_bound, right_bound)
            
            if self._active_handle == 'lower': 
                clamped_value = min(new_value, self._upper)
                if abs(clamped_value - self._target_lower) > 0.3:
                    self._target_lower = clamped_value
                    self._animation_timer.start()
            else: 
                clamped_value = max(new_value, self._lower)
                if abs(clamped_value - self._target_upper) > 0.3:
                    self._target_upper = clamped_value
                    self._animation_timer.start()
                    
            self._emit_value_changed()

    def mouseReleaseEvent(self, event): 
        if self._active_handle == 'lower':
            self._persistent_lower = True
            self._persistent_upper = False
            self._target_opacity['lower'] = 1.0
        elif self._active_handle == 'upper':
            self._persistent_upper = True
            self._persistent_lower = False
            self._target_opacity['upper'] = 1.0
            
        self._active_handle = None
        
        if not self._label_fade_timer.isActive():
            self._label_fade_timer.start()
        
        self.update()
        
    def leaveEvent(self, event): 
        self._hover_lower = False
        self._hover_upper = False
        self._hover_track = False
        self._hover_active_track = False
        
        if not self._persistent_lower:
            self._target_opacity['lower'] = 0.0
        if not self._persistent_upper:
            self._target_opacity['upper'] = 0.0

        if not self._label_fade_timer.isActive():
            self._label_fade_timer.start()
            
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def keyPressEvent(self, e):
        step = 1
        if e.key() == Qt.Key.Key_Left:
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._lower = max(self._min, self._lower - step)
            else:
                self._upper = max(self._min, self._upper - step)
            self._emit_value_changed()
            self.update()
        elif e.key() == Qt.Key.Key_Right:
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._lower = min(self._upper, self._lower + step)
            else:
                self._upper = min(self._max, self._upper + step)
            self._emit_value_changed()
            self.update()
        else:
            super().keyPressEvent(e)
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
                    QLabel {{ color:{text}; font-size:10pt; background:transparent; }}
                    QLabel.title {{ font-weight:600; font-size:10pt; letter-spacing:.3px; }}
                    QPushButton.day {{ background:transparent; border:0; border-radius:0; min-width:30px; min-height:30px; font-size:9pt; color:{text}; }}
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
                        title_lbl.setStyleSheet("font-size:9pt; font-weight:600; margin:0; padding:0;")
                        wrap.addWidget(title_lbl)

                        if s_d == e_d:
                            sd = short(s_d)
                            dates_text = f"{sd} - {sd}"
                        else:
                            dates_text = f"{short(s_d)} - {short(e_d)}"
                        dates_lbl = QLabel(dates_text)
                        # Subtext color adapt (inline for clarity)
                        dates_lbl.setStyleSheet(f"font-size:7pt; color:{subtext}; margin-top:1px;")
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
        umur_container.setContentsMargins(0, 16, 0, 0)  # Beri jarak dari elemen di atas
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
        self.keterangan.addItems([
            "Keterangan", "1 (Meninggal)", "2 (Ganda)", "3 (Di Bawah Umur)",
            "4 (Pindah Domisili)", "5 (WNA)", "6 (TNI)", "7 (Polri)",
            "8 (Salah TPS)", "U (Ubah)", "90 (Keluar Loksus)", "91 (Meninggal)",
            "92 (Ganda)", "93 (Di Bawah Umur)", "94 (Pindah Domisili)",
            "95 (WNA)", "96 (TNI)", "97 (Polri)"
        ])
        self.kelamin.addItems(["Kelamin", "L", "P"])
        self.kawin.addItems(["Kawin", "S", "B", "P"])
        self.disabilitas.addItems([
            "Disabilitas", "0 (Normal)", "1 (Fisik)", "2 (Intelektual)",
            "3 (Mental)", "4 (Sensorik Wicara)", "5 (Sensorik Rungu)",
            "6 (Sensorik Netra)"
        ])
        self.ktp_el.addItems(["KTP-el", "B", "S"])

        # ✅ Ambil data SUMBER dari MainWindow
        self._populate_sumber_from_mainwindow()

        self.rank.addItems(["Rank", "Aktif", "Ubah", "TMS", "Baru"])

    def _populate_sumber_from_mainwindow(self):
        """Mengisi dropdown 'sumber' dari kolom DISTINCT SUMBER di tabel aktif (via MainWindow)."""
        try:
            main = self.parent()  # referensi ke MainWindow
            if not main or not hasattr(main, "get_distinct_sumber"):
                print("[FilterSidebar] MainWindow tidak punya get_distinct_sumber()")
                self.sumber.addItems(["Sumber"])
                return

            sumber_list = main.get_distinct_sumber()
            self.sumber.clear()
            self.sumber.addItems(sumber_list)

            # Nonaktifkan item pertama agar hanya jadi label
            if self.sumber.count() > 0:
                self.sumber.model().item(0).setEnabled(False)

        except Exception as e:
            print(f"[FilterSidebar._populate_sumber_from_mainwindow Error] {e}")
            self.sumber.clear()
            self.sumber.addItems(["Sumber"])

    
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
        self.btn_filter.clicked.connect(self._apply_filters)
        
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
        # Reset form fields terlebih dahulu
        self._reset_form_only()
        
        # Cari MainWindow dan panggil clear_filters
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'clear_filters') and callable(getattr(parent, 'clear_filters')):
                try:
                    parent.clear_filters()
                    break
                except Exception as e:
                    print(f"Error saat clear_filters: {e}")
                    break
            parent = parent.parent()
    
    def _reset_form_only(self):
        """Reset form fields saja tanpa mempengaruhi data."""
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
    
    def _apply_filters(self):
        """Method untuk menerapkan filter yang dipanggil dari tombol Filter.
        
        Method ini akan memanggil apply_filters di parent window (MainWindow).
        """
        # Cari MainWindow dari parent chain
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'apply_filters') and hasattr(parent, 'all_data'):
                parent.apply_filters()
                return
            parent = parent.parent()
        
        # Fallback jika tidak menemukan MainWindow
        print("ERROR: Tidak dapat menemukan MainWindow untuk apply_filters")
    
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
                font-family: 'Segoe UI', 'Segoe UI';
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
                background: #d71d1d;
                border: 1px solid #1177bb;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton#filterBtn:hover {
                background: #ff6600;
            }
        """)
    
    def _apply_light_theme(self):
        """Terapkan stylesheet untuk tema terang."""
        self.setStyleSheet("""
            /* Styling umum untuk widget */
            QWidget {
                font-family: 'Segoe UI', 'Segoe UI';
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
    # 🔹 Load & Save Setting ke tabel setting_aplikasi_{TAHAPAN}
    # =========================================================
    @with_safe_db
    def load_settings(self, *args, conn=None):
        """Memuat status checkbox kolom dari tabel setting_aplikasi_<tahapan>."""
        cur = conn.cursor()

        tbl_name = f"setting_aplikasi_{self._tahapan.lower()}"
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_name} (
                nama_kolom TEXT PRIMARY KEY,
                tampil INTEGER
            )
        """)
        cur.execute(f"SELECT nama_kolom, tampil FROM {tbl_name}")
        rows = dict(cur.fetchall())

        for col, _ in self.columns:
            checked = bool(rows.get(col, 1))  # default tampil
            if col in self.checks:
                self.checks[col].setChecked(checked)


    @with_safe_db
    def save_settings(self, checked: bool = False, conn=None):
        cur = conn.cursor()

        tbl_name = f"setting_aplikasi_{self._tahapan.lower()}"
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_name} (
                nama_kolom TEXT PRIMARY KEY,
                tampil INTEGER
            )
        """)

        for col, _ in self.columns:
            val = 1 if self.checks[col].isChecked() else 0
            cur.execute(
                f"INSERT OR REPLACE INTO {tbl_name} (nama_kolom, tampil) VALUES (?, ?)",
                (col, val)
            )

        # Tidak perlu conn.commit(); decorator sudah commit.
        self.accept()

# ==========================================================
# UI: Login Window (fullscreen, putih lembut, hover oranye)
# ==========================================================
class LoginWindow(QMainWindow):
    def __init__(self, conn=None):
        super().__init__()
        self.conn = conn
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
        form_layout.setSpacing(8)
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
                color: black;
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
        self.toggle_pw = QPushButton("😍")  ###😎😒👁️🤪😝🙄😙😄
        self.toggle_pw.setFixedWidth(30)
        self.toggle_pw.clicked.connect(lambda: self.toggle_password(self.pass_input))
        pw_layout.addWidget(self.pass_input)
        pw_layout.addWidget(self.toggle_pw)
        form_layout.addWidget(self.pass_label)
        form_layout.addLayout(pw_layout)
        self.toggle_pw.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_pw.installEventFilter(self)


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
                background-color: #d71d1d;
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
        self.buat_akun = QPushButton("Buat Akun Disini")
        self.buat_akun.setStyleSheet("""
            QPushButton {
                color: #d71d1d;
                font-weight: bold;
                text-decoration: underline;
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: transparent;
                color: #ff6600;
            }
        """)

        self.buat_akun.clicked.connect(self.konfirmasi_buat_akun)
        form_layout.addWidget(self.buat_akun, alignment=Qt.AlignmentFlag.AlignCenter)

        # === Tombol Reset Password ===
        self.reset_pw = QPushButton("Lupa Password?")
        self.reset_pw.setStyleSheet("""
            QPushButton {
                color: #0078d7;
                font-weight: bold;
                text-decoration: underline;
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                color: #ff6600;
            }
        """)
        self.reset_pw.clicked.connect(self.show_reset_password)
        form_layout.addWidget(self.reset_pw, alignment=Qt.AlignmentFlag.AlignCenter)

        # === Tempel layout ke frame & frame ke tampilan utama ===
        form_frame.setLayout(form_layout)
        outer_layout.addWidget(form_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        central_widget = QWidget()
        central_widget.setLayout(outer_layout)
        self.setCentralWidget(central_widget)

        # === Style global ===
        self.setStyleSheet("""
            QWidget {
                font-size: 11pt;
                color: black;
                background-color: #ffffff;
            }
            QFrame#FormFrame {
                background-color: #F0F0F0;
                border: 1px solid rgba(255, 255, 255, 0.25);  /* 🔹 Border hanya di frame utama */
                border-radius: 10px;
                padding: 30px 40px;
            }
            QLabel {
                background-color: transparent;  /* 🔹 Hilangkan background hitam label */
                color: black;
            }
            QLineEdit, QComboBox {
                min-height: 28px;
                font-size: 11pt;
                border: 1px solid #222;
                border-radius: 4px;
                padding-left: 8px;
                background-color: #ffffff;
                color: black;
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

    def show_reset_password(self):
        """Tampilkan dialog reset password."""
        dlg = ResetPasswordDialog(self)
        dlg.exec()

    def eventFilter(self, obj, event):
        if obj == self.toggle_pw:
            if event.type() == QEvent.Type.Enter:
                self.toggle_pw.setStyleSheet("""
                    QPushButton {
                        font-size: 18pt;
                        color: #ff6600;
                        background: transparent;
                        border: none;
                        border-radius: 6px;
                    }
                """)
            elif event.type() == QEvent.Type.Leave:
                self.toggle_pw.setStyleSheet("""
                    QPushButton {
                        font-size: 14pt;
                        color: #000000;
                        background: transparent;
                        border: none;
                    }
                """)
        return super().eventFilter(obj, event)

    # === Proses login ===
    def check_login(self):
        email = self.email_input.text().strip()
        pw = self.pass_input.text().strip()
        tahapan = self.tahapan_combo.currentText()

        if not email or not pw or tahapan == "-- Pilih Tahapan --":
            show_modern_warning(self, "Login Gagal", "Semua field harus diisi!")
            return

        try:
            # 🔒 Gunakan koneksi SQLCipher terenkripsi dari db_manager
            from db_manager import connect_encrypted
            conn = connect_encrypted()
            cur = conn.cursor()

            # Pastikan tabel users ada (jika belum)
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

            # 🔹 Hitung hash dengan salt (email)
            salted_input = (pw + email).encode("utf-8")
            hashed_pw = hashlib.sha256(salted_input).hexdigest()

            cur.execute(
                "SELECT id, nama, kecamatan, desa, otp_secret FROM users WHERE email=? AND password=?",
                (email, hashed_pw)
            )
            row = cur.fetchone()

            if not row:
                show_modern_warning(self, "Login Gagal", "Email atau password salah!")
                conn.commit()
                return

            user_id, nama, kecamatan, desa, otp_secret = row
            conn.commit()

        except Exception as e:
            show_modern_error(self, "Error", f"Terjadi kesalahan saat login:\n{e}")
            return



        # ============================================================
        # 1️⃣ Jika OTP belum dibuat (login pertama)
        # ============================================================
        if not otp_secret:
            import pyotp, qrcode  # type: ignore
            from io import BytesIO

            otp_secret = pyotp.random_base32()

            # 🔹 Simpan secret baru tanpa menutup koneksi
            cur.execute("UPDATE users SET otp_secret=? WHERE id=?", (otp_secret, user_id))
            conn.commit()

            # 🔹 Buat QR Code OTP dengan label NexVo: email
            totp = pyotp.TOTP(otp_secret)
            account_label = f"NexVo: {email}"

            # Gunakan parameter 'name' yang sudah diformat penuh, dan issuer_name terpisah
            totp_uri = totp.provisioning_uri(
                name=account_label,
                issuer_name="NexVo KPU Kab. Tasikmalaya"
            )


            qr = qrcode.make(totp_uri)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())

            # 🔹 Tampilkan QR code untuk aktivasi OTP
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
            # ❌ Jangan tutup koneksi manual di sini
            conn.commit()


        # ============================================================
        # 2️⃣ Verifikasi OTP Modern
        # ============================================================
        otp_dialog = QDialog(self)
        otp_dialog.setWindowTitle("Verifikasi OTP")
        otp_dialog.setFixedSize(340, 220)
        otp_dialog.setStyleSheet("""
            QDialog {
                background-color: #dddddd;
                color: black;
                border-radius: 10px;
            }
            QLabel { color: black; font-size: 12pt; }
            QLineEdit {
                border: 2px solid #555;
                border-radius: 6px;
                padding: 6px;
                font-size: 16pt;
                letter-spacing: 4px;
                background-color: #666666;
                color: #ffffff;
                qproperty-alignment: AlignCenter;
            }
            QPushButton {
                background-color: #ff6600;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #d71d1d; }
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
        hapus_semua_data(self.conn)

        # ✅ Tampilkan form RegisterWindow sebagai window utama
        self.register_window = RegisterWindow(None)
        self.register_window.show()

        # ✅ Tutup login window setelah register window muncul
        self.close()

    # === Masuk ke MainWindow ===
    def accept_login(self, nama, kecamatan, desa, tahapan):
        """Masuk ke halaman utama setelah login sukses."""
        tahapan = tahapan.upper()

        # ✅ Pastikan koneksi database aktif
        if self.conn is None:
            try:
                self.conn = get_connection()
            except Exception as e:
                show_modern_error(self, "Error DB", f"Gagal membuka koneksi database:\n{e}")
                return

        # Pastikan tabel tahapan sudah ada
        valid_tbl = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}
        tbl_name = valid_tbl.get(tahapan, "dphp")

        try:
            cur = self.conn.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {tbl_name} (
                    checked INTEGER DEFAULT 0,
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
                    LastUpdate TEXT,
                    CEK_DATA TEXT
                )
            """)
            self.conn.commit()
        except Exception as e:
            show_modern_error(self, "Error DB", f"Gagal menyiapkan tabel tahapan:\n{e}")
            return

        # === Tampilkan jendela utama ===
        try:
            self.main_window = MainWindow(
                nama.upper(), kecamatan.upper(), desa.upper(), str(DB_PATH), tahapan.upper()
            )
            self.main_window.show()

            self.main_window.create_filter_sidebar()

            # ✅ Tunda sedikit agar fullscreen bekerja sempurna di Windows
            QTimer.singleShot(100, self.main_window.showMaximized)

            self.close()
        except Exception as e:
            show_modern_error(self, "Error", f"Gagal membuka halaman utama:\n{e}")

class ResetPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reset Password")
        self.setFixedSize(420, 520)
        self.setStyleSheet("""
            QDialog { background-color: #f2f2f2; color: black; border-radius: 10px; }
            QLabel { font-size: 11pt; }
            QLineEdit {
                border: 1px solid #666;
                border-radius: 5px;
                padding: 5px;
                background: white;
                font-size: 11pt;
            }
            QPushButton {
                background-color: #d71d1d;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #ff6600; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(30, 25, 30, 25)

        # === Email ===
        layout.addWidget(QLabel("Email Terdaftar:"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Masukkan email Anda")
        layout.addWidget(self.email_input)

        # === Password baru ===
        layout.addWidget(QLabel("Password Baru:"))
        self.new_pw = QLineEdit()
        self.new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.new_pw)

        # === Ulangi Password ===
        layout.addWidget(QLabel("Ulangi Password Baru:"))
        self.re_pw = QLineEdit()
        self.re_pw.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.re_pw)

        # === OTP ===
        layout.addWidget(QLabel("Kode OTP (6 digit dari aplikasi Authenticator):"))
        self.otp_input = QLineEdit()
        self.otp_input.setMaxLength(6)
        self.otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.otp_input)

        # === Captcha (bergaya seperti RegisterWindow, dengan jarak rapi) ===
        layout.addWidget(QLabel("Captcha Keamanan:"))

        self.captcha_code = self.generate_captcha()
        self.captcha_label = QLabel()
        self.captcha_label.setFixedHeight(60)
        self.captcha_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.refresh_captcha_image()

        self.refresh_btn = QPushButton("🔄️")
        self.refresh_btn.setFixedWidth(36)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_captcha_image)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                font-size: 14pt;
                font-weight: bold;
                color: #000;
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                color: #ff6600;
                background-color: rgba(255,102,0,0.15);
                border-radius: 6px;
            }
        """)

        captcha_layout = QHBoxLayout()
        captcha_layout.addWidget(self.captcha_label)
        captcha_layout.addWidget(self.refresh_btn)
        layout.addLayout(captcha_layout)

        # 🔹 Tambahkan jarak bawah agar tidak menempel ke field input
        spacer = QWidget()
        spacer.setFixedHeight(10)
        layout.addWidget(spacer)

        self.captcha_input = QLineEdit()
        self.captcha_input.setPlaceholderText("Tulis ulang captcha di atas")
        layout.addWidget(self.captcha_input)

        # === Tombol Reset ===
        btn_reset = QPushButton("Reset Password")
        btn_reset.clicked.connect(self.reset_password)
        layout.addWidget(btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)

    # ===================================================
    # 🔹 Captcha generator bergaya RegisterWindow
    # ===================================================
    def generate_captcha(self, length=5):
        import random, string
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))

    def generate_captcha_image(self, text):
        from PyQt6.QtGui import QPainter, QColor, QFont, QPixmap
        import random
        width, height = 160, 50
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#f5f5f5"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Segoe UI", 22, QFont.Weight.Bold)
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

        # Noise garis acak
        for _ in range(6):
            pen = QColor(random.randint(120, 200), random.randint(120, 200), random.randint(120, 200))
            painter.setPen(pen)
            x1, y1, x2, y2 = [random.randint(0, width) for _ in range(4)]
            painter.drawLine(x1, y1, x2, y2)

        painter.end()
        return pixmap

    def refresh_captcha_image(self):
        self.captcha_code = self.generate_captcha()
        pixmap = self.generate_captcha_image(self.captcha_code)
        self.captcha_label.setPixmap(pixmap)

    # ===================================================
    # 🔐 Validasi & Reset Password Aman (SHA256 + salt)
    # ===================================================
    def reset_password(self):
        email = self.email_input.text().strip()
        new_pw = self.new_pw.text().strip()
        re_pw = self.re_pw.text().strip()
        otp_code = self.otp_input.text().strip()
        captcha_in = self.captcha_input.text().strip().upper()

        if not email or not new_pw or not re_pw or not otp_code or not captcha_in:
            show_modern_warning(self, "Gagal", "Semua field harus diisi.")
            return
        if new_pw != re_pw:
            show_modern_error(self, "Gagal", "Password baru tidak sama.")
            return
        if captcha_in != self.captcha_code:
            show_modern_error(self, "Gagal", "Captcha salah, reset ditolak.")
            self.refresh_captcha_image()
            return

        try:
            from db_manager import connect_encrypted
            conn = connect_encrypted()
            cur = conn.cursor()
            cur.execute("SELECT otp_secret FROM users WHERE email=?", (email,))
            row = cur.fetchone()
            if not row:
                show_modern_error(self, "Gagal", "Email tidak terdaftar.")
                return

            otp_secret = row[0]
            import pyotp, hashlib  # type: ignore
            totp = pyotp.TOTP(otp_secret)
            if not totp.verify(otp_code):
                show_modern_error(self, "Gagal", "Kode OTP salah atau sudah kedaluwarsa.")
                return

            # 🔒 Hash password baru + salt (email)
            salted_input = (new_pw + email).encode("utf-8")
            hashed_pw = hashlib.sha256(salted_input).hexdigest()

            cur.execute("UPDATE users SET password=? WHERE email=?", (hashed_pw, email))
            conn.commit()
            show_modern_info(self, "Berhasil", "Reset password berhasil dilakukan!")
            self.accept()

        except Exception as e:
            show_modern_error(self, "Error", f"Terjadi kesalahan:\n{e}")

class HoverDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_row = -1
        parent.viewport().installEventFilter(self)
        self.parent = parent  # jangan installEventFilter ke parent utama lagi!

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseMove:
            index = self.parent.indexAt(event.pos())
            if index.isValid() and index.row() != self.hovered_row:
                self.hovered_row = index.row()
                self.parent.viewport().update()
        elif event.type() == QEvent.Type.Leave:
            if self.hovered_row != -1:
                self.hovered_row = -1
                self.parent.viewport().update()
        return super().eventFilter(obj, event)

    def paint(self, painter, option, index):
        font = option.font
        if index.row() == self.hovered_row and index.column() != 0:
            font.setBold(True)
            font.setPointSize(font.pointSize() - 2)
        painter.setFont(font)
        super().paint(painter, option, index)

class CustomTable(QTableWidget):
    def focusOutEvent(self, event):
        # ⚡️ Abaikan hilangnya fokus supaya warna seleksi/hover tidak berubah
        event.ignore()

class MainWindow(QMainWindow):
    """Halaman utama sederhana sementara (dengan ikon di title bar bawaan)."""
    def __init__(self, nama, kecamatan, desa, db_name, tahapan):
        super().__init__()

        self._nama = nama
        self._kecamatan = kecamatan
        self._desa = desa
        self._tahapan = tahapan.upper()

        # ======================================================
        # 🔸 Helper pemilih tabel aktif
        # ======================================================
        def _active_table():
            tabel_map = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}
            tbl = tabel_map.get(self._tahapan)
            if not tbl:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", f"Tahapan tidak dikenal: {self._tahapan}")
            return tbl

        self._active_table = _active_table

        # ====== Pastikan file KPU.png ada ======
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "KPU.png")

        if not os.path.exists(icon_path):
            print(f"[PERINGATAN] File ikon tidak ditemukan: {icon_path}")
        else:
            # ✅ Set icon ke title bar bawaan Windows
            self.setWindowIcon(QIcon(icon_path))

        # Title bar default bawaan
        self.setWindowTitle(f"Desa {desa.title()} – Tahap {tahapan.upper()}")

        # ===== Style =====
        self.setStyleSheet("""
            QMainWindow { background-color: #fafafa; }
            QLabel {
                font-family: 'Segoe UI';
                font-size: 12pt;
                color: #333;
                font-weight: 600;
            }
        """)

        menubar = self.menuBar()
        menubar.setStyleSheet("""
            /* ======== Menu Bar ======== */
            QMenuBar {
                background-color: #ffffff;
                color: #000000;
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: reguler;              /* 🟢 teks tebal */
                padding: 2px 6px;               /* rapat atas-bawah */
                border: none;
            }

            QMenuBar::item {
                background: transparent;
                padding: 3px 5px;                /* jarak antar item lebih kecil */
                margin: 0px 2px;                 /* rapat horizontal */
                border-radius: 3px;
                color: #000000;
            }

            /* Hover elegan */
            QMenuBar::item:selected {
                background-color: #d71d1d;
                color: white;
                border-radius: 3px;
                padding: 3px 6px;
            }

            QMenuBar::item:pressed {
                background-color: #d71d1d;
            }

            /* ======== Popup Menu (contoh: View menu) ======== */
            QMenu {
                background-color: #EAEAEA;      /* putih lembut */
                color: #000000;                 /* font hitam */
                border: 1px solid #000000;      /* border tipis hitam */
                border-radius: 5px;             /* membulat lembut */
                padding: 5px 8px;
                margin-top: 1px;
            }

            QMenu::item {
                background-color: transparent;
                padding: 5px 5px;              /* pas proporsional */
                border-radius: 3px;
                color: #000000;
                font-family: 'Segoe UI';
                font-size: 12px;
            }

            QMenu::item:selected {
                background-color: #d71d1d;      /* hover oranye */
                color: white;
                border-radius: 3px;
            }

            QMenu::separator {
                height: 2px;
                background-color: #d71d1d;
                margin: 4px 10px;
            }
        """)

        file_menu = menubar.addMenu("File")
        action_dashboard = QAction(" Dashboard", self)
        action_dashboard.setShortcut("Alt+H")
        action_dashboard.triggered.connect(self.show_dashboard_page)
        file_menu.addAction(action_dashboard)

        action_pemutakhiran = QAction(" Pemutakhiran Data", self)
        action_pemutakhiran.setShortcut("Alt+C")
        action_pemutakhiran.triggered.connect(self.show_data_page)
        file_menu.addAction(action_pemutakhiran)

        action_unggah_reguler = QAction(" Unggah Webgrid TPS Reguler", self)
        action_unggah_reguler.setShortcut("Alt+I")
        file_menu.addAction(action_unggah_reguler)
        action_rekap = QAction(" Rekapitulasi", self)
        action_rekap.setShortcut("Alt+R")
        file_menu.addAction(action_rekap)
        action_import = QAction(" Import CSV", self)
        action_import.setShortcut("Alt+M")
        action_import.triggered.connect(self.import_csv)
        file_menu.addAction(action_import)
        file_menu.addSeparator()
        action_keluar = QAction(" Keluar", self)
        action_keluar.setShortcut("Ctrl+W")
        action_keluar.triggered.connect(self.keluar_aplikasi)
        file_menu.addAction(action_keluar)

        generate_menu = menubar.addMenu("Generate")
        action_berita_acara = QAction(" Berita Acara", self)
        action_berita_acara.triggered.connect(self.generate_berita_acara)
        generate_menu.addAction(action_berita_acara)

        action_lamp_adpp = QAction(" A-Daftar Perubahan Pemilih", self)
        action_lamp_adpp.triggered.connect(self.generate_adpp)
        generate_menu.addAction(action_lamp_adpp)

        view_menu = menubar.addMenu("View")
        view_menu.addAction(QAction(" Actual Size", self, shortcut="Ctrl+0"))
        view_menu.addAction(QAction(" Zoom In", self, shortcut="Ctrl+Shift+="))
        view_menu.addAction(QAction(" Zoom Out", self, shortcut="Ctrl+-"))
        view_menu.addAction(QAction(" Toggle Full Screen", self, shortcut="F11"))

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(QAction(" Shortcut", self, shortcut="Alt+Z"))

        action_setting = QAction(" Setting Aplikasi", self)
        action_setting.setShortcut("Alt+T")
        action_setting.triggered.connect(self.show_setting_dialog)
        help_menu.addAction(action_setting)

        action_hapus_data = QAction(" Hapus Data Pemilih", self)
        action_hapus_data.triggered.connect(self.hapus_data_pemilih)
        help_menu.addAction(action_hapus_data)

        help_menu.addAction(QAction(" Backup", self))
        help_menu.addAction(QAction(" Restore", self))
        help_menu.addAction(QAction(" About", self))

        # ==========================================================
        # ✅ Tampilkan menu "Import Ecoklit" hanya jika tahapan = DPHP
        # ==========================================================
        if self._tahapan == "DPHP":
            import_ecoklit_menu = menubar.addMenu("Import Ecoklit")

            action_import_baru = QAction(" Import Pemilih Baru", self)
            action_import_tms = QAction(" Import Pemilih TMS", self)
            action_import_ubah = QAction(" Import Pemilih Ubah Data ", self)

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
        def add_spacer(width=4):
            spacer = QWidget()
            spacer.setFixedWidth(width)
            toolbar.addWidget(spacer)

        # === Tombol kiri ===
        btn_baru = QPushButton("Baru")
        self.style_button(btn_baru, bg="#d71d1d", fg="white", bold=True)
        toolbar.addWidget(btn_baru)
        add_spacer()

        # === Tombol Rekap (QToolButton, tapi tampil identik dengan QPushButton) ===
        btn_rekap = QToolButton()
        btn_rekap.setText(" Rekap ")
        btn_rekap.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_rekap.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        # Gunakan stylesheet yang sama dengan tombol lain (style_button)
        btn_rekap.setStyleSheet(f"""
            QToolButton {{
                background-color: #d71d1d;
                color: white;
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: {'normal' if True else 'normal'};
                border: none;
                border-radius: 5px;
                padding: 4px 9px;
                margin: 3px 1px;
                min-height: 17px;   /* tinggi seragam dengan QPushButton */
            }}
            QToolButton:hover {{
                background-color: #3B3B3B;
            }}
            QToolButton:pressed {{
                background-color: #8c1010;
            }}
            /* 🔥 Hilangkan ikon dropdown bawaan sepenuhnya */
            QToolButton::menu-indicator {{
                image: none;
                width: 0px;
                height: 0px;
            }}
        """)

        # === Menu di dalam tombol ===
        menu_rekap = QMenu(btn_rekap)
        menu_rekap.addAction(QAction("Pemilih Aktif", self, triggered=self.cek_rekapaktif))
        menu_rekap.addAction(QAction("Pemilih Baru", self, triggered=self.cek_rekapbaru))
        menu_rekap.addAction(QAction("Ubah Data", self, triggered=self.cek_rekapubah))
        menu_rekap.addAction(QAction("Saring TMS", self, triggered=self.cek_rekaptms))
        menu_rekap.addAction(QAction("Pemilih Non KTPel", self, triggered=self.cek_rekapktp))
        menu_rekap.addAction(QAction("Disabilitas", self, triggered=self.cek_rekapdifabel))
        btn_rekap.setMenu(menu_rekap)
        toolbar.addWidget(btn_rekap)
        add_spacer()

        # === Gaya popup menu elegan ===
        menu_rekap.setStyleSheet("""
            QMenu {
                background-color: #EAEAEA;
                color: #000000;
                border: 1px solid #000000;
                border-radius: 5px;
                padding: 1px 4px;
                margin-top: 1px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 3px 6px;
                border-radius: 3px;
                color: #000000;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #d71d1d;
                color: white;
                border-radius: 3px;
            }
            QMenu::separator {
                height: 2px;
                background-color: #d71d1d;
                margin: 4px 10px;
            }
        """)

        # === Spacer kiri ke tengah ===
        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_left)

        # === Label User di tengah ===
        self.user_label = QLabel(nama)
        self.user_label.setStyleSheet("font-family: Segoe UI; font-weight: bold; font-size: 14px;")
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.user_label)

        # === Spacer tengah ke kanan ===
        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_right)

        # === Tombol kanan ===
        #btn_urutkan = QPushButton("Urutkan")
        #self.style_button(btn_urutkan, bg="#d71d1d", fg="white", bold=True)
        #btn_urutkan.clicked.connect(self.sort_data) #belum ada fungsi
        #toolbar.addWidget(btn_urutkan)
        #add_spacer()

        # === Tombol Cek Data (QToolButton, tapi tampil identik dengan QPushButton) ===
        btn_cekdata = QToolButton()
        btn_cekdata.setText("Cek Data")
        btn_cekdata.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_cekdata.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        # Gunakan stylesheet yang sama dengan tombol lain (style_button)
        btn_cekdata.setStyleSheet(f"""
            QToolButton {{
                background-color: #d71d1d;
                color: white;
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: {'normal' if True else 'normal'};
                border: none;
                border-radius: 5px;
                padding: 4px 9px;
                margin: 3px 1px;
                min-height: 17px;   /* tinggi seragam dengan QPushButton */
            }}
            QToolButton:hover {{
                background-color: #3B3B3B;
            }}
            QToolButton:pressed {{
                background-color: #8c1010;
            }}
            /* 🔥 Hilangkan ikon dropdown bawaan sepenuhnya */
            QToolButton::menu-indicator {{
                image: none;
                width: 0px;
                height: 0px;
            }}
        """)

        # === Menu di dalam tombol ===
        menu_cekdata = QMenu(btn_cekdata)
        menu_cekdata.addAction(QAction("Potensi NKK Invalid", self, triggered=self.cek_potensi_nkk_invalid))
        menu_cekdata.addAction(QAction("Potensi NIK Invalid", self, triggered=self.cek_potensi_nik_invalid))
        menu_cekdata.addAction(QAction("Potensi Dibawah Umur", self, triggered=self.cek_potensi_dibawah_umur))
        menu_cekdata.addAction(QAction("Potensi Beda TPS", self, triggered=self.cek_beda_tps))
        menu_cekdata.addAction(QAction("Pemilih Tidak Padan", self, triggered=self.cek_tidak_padan))
        menu_cekdata.addAction(QAction("Ganda NIK", self, triggered=self.cek_ganda_nik))
        menu_cekdata.addAction(QAction("Pemilih Pemula", self, triggered=self.cek_pemilih_pemula))
        btn_cekdata.setMenu(menu_cekdata)
        toolbar.addWidget(btn_cekdata)
        add_spacer()

        # === Gaya popup menu elegan ===
        menu_cekdata.setStyleSheet("""
            QMenu {
                background-color: #EAEAEA;
                color: #000000;
                border: 1px solid #000000;
                border-radius: 5px;
                padding: 1px 4px;
                margin-top: 1px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 3px 6px;
                border-radius: 3px;
                color: #000000;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #d71d1d;
                color: white;
                border-radius: 3px;
            }
            QMenu::separator {
                height: 2px;
                background-color: #d71d1d;
                margin: 4px 10px;
            }
        """)

        btn_reset = QPushButton("Reset")
        self.style_button(btn_reset, bg="#d71d1d", fg="white", bold=True)
        btn_reset.clicked.connect(self.reset_tampilkan_semua_data)
        toolbar.addWidget(btn_reset)
        add_spacer()

        btn_filter = QPushButton("Filter")
        self.style_button(btn_filter, bg="#d71d1d", fg="white", bold=True)
        btn_filter.setIcon(QIcon.fromTheme("view-filter")) # type: ignore
        btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_filter.clicked.connect(self.toggle_filter_sidebar)
        toolbar.addWidget(btn_filter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # === Style tipis elegan ===
        self.status.setStyleSheet("""
            QStatusBar {
                background-color: #fbfbfa;
                border-top: 1px solid #fbfbfa;
                padding: 0px 8px;
                margin: 3px 1px;
                min-height: 20px;                     /* tinggi bar dikontrol */
            }
            QStatusBar QLabel {
                font-family: 'Segoe UI';
                font-size: 10px;                      /* kecil elegan */
                color: #222;
                padding: 0px 4px;
            }
        """)

        # === Label isi ===
        self.lbl_selected = QLabel("0 selected")
        self.lbl_total = QLabel("0 total")
        self.lbl_version = QLabel("NexVo v1.0")
        self.lbl_version.setStyleSheet("color:#222; font-weight:600;")

        # === Tambahkan ke status bar ===
        self.status.addWidget(self.lbl_selected)
        self.status.addWidget(self.lbl_total)
        self.status.addPermanentWidget(self.lbl_version)

        # ✅ Tambahkan ini biar auto resize kolom jalan setelah login
        QTimer.singleShot(0, self.auto_fit_columns)

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
        self.sort_lastupdate_asc = True

        self.current_page = 1
        self.rows_per_page = 100
        self.total_pages = 1

        self.table = CustomTable()
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
        self.checkbox_delegate = CheckboxDelegate(self.table)
        self.table.setItemDelegateForColumn(0, self.checkbox_delegate)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.installEventFilter(self)
        self.menuBar().installEventFilter(self)
        for tb in self.findChildren(QToolBar):
            tb.installEventFilter(self)
        pal = self.table.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor("transparent"))     # hilangkan warna biru saat seleksi
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))   # teks tetap hitam
        self.table.setPalette(pal)

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

        # 🔒 Sembunyikan kolom CEK_DATA tanpa menghapus datanya
        col_index_cekdata = columns.index("CEK_DATA")
        self.table.setColumnHidden(col_index_cekdata, True)

        # 🔹 Hilangkan highlight seleksi permanen
        #self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.make_table_text_selectable()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        #self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.hover_delegate = HoverDelegate(self.table)
        self.table.setItemDelegate(self.hover_delegate)
        self._setup_table_auto_deselect()
        self.table.setStyleSheet("""
            QTableWidget {
                background: #ececec;
                alternate-background-color: #f7f7f7;
                border: 1px solid #4E4E4E;
                color: #000000;
                font-family: Segoe UI;
                font-size: 10pt;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                color: #ffffff;
                padding: 4px;
                font-weight: 600;
            }
            QTableView::item:focus {
                outline: none;              /* hilangkan outline fokus hitam */
            }
        """)
        
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

        # --- Stack utama
        self.stack = QStackedWidget()
        self.stack.addWidget(self.data_page)
        self.setCentralWidget(self.stack)

        # Flag halaman
        self._is_on_dashboard = False
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.setEnabled(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Load awal
        self.load_data_from_db()
        self.update_pagination()
        self.apply_column_visibility()

        # ✅ Tampilkan setelah siap sepenuhnya
        QTimer.singleShot(0, self.showMaximized)

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Text, QColor("#000000"))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#000000"))
        self.setPalette(pal)

    def _safe_clear_selection(self):
        """Hilangkan seleksi dengan aman tanpa memicu warning editor Qt."""
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, lambda: (
            self.table.clearFocus(),
            self.table.clearSelection()
        ))


    def _setup_table_auto_deselect(self):
        """Hilangkan seleksi otomatis saat kursor meninggalkan baris."""
        self.table.setMouseTracking(True)
        self.table.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        # === 🩶 Menangani klik luar tabel untuk clear selection ===
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = self.mapFromGlobal(event.globalPosition().toPoint())
            if not self.table.geometry().contains(pos):
                self._safe_clear_selection()

        # === 🩶 Area viewport tabel ===
        if obj == self.table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                index = self.table.indexAt(event.pos())
                if not index.isValid():
                    self._safe_clear_selection()
            elif event.type() == QEvent.Type.Leave:
                self._safe_clear_selection()
            elif event.type() == QEvent.Type.Resize:
                # Pastikan overlay “Data Tidak Ditemukan” tetap di tengah
                if hasattr(self, "_empty_overlay") and self._empty_overlay:
                    self._empty_overlay.resize(self.table.viewport().size())

        return super().eventFilter(obj, event)

    
    def reset_tampilkan_semua_data(self, silent=False):
        """
        🔁 Menampilkan kembali seluruh data dari tabel aktif (reset hasil filter/pemeriksaan)
        Data diurutkan kembali berdasar TPS, RW, RT, NKK, NAMA.
        
        Jika silent=True → tidak menampilkan popup sama sekali (digunakan oleh import_csv / batch).
        """
        from db_manager import get_connection
        try:
            tahap = getattr(self, "_tahapan", "").strip().upper()
            tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {tbl_name}")
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            # Jika tabel kosong
            if not rows:
                if not silent:  # hanya tampilkan popup bila tidak silent
                    show_modern_info(self, "Info", "Tabel kosong — tidak ada data untuk ditampilkan.")
                return

            # Muat semua data ke memori
            all_data = []
            for r in rows:
                d = {col_names[i]: ("" if r[i] is None else str(r[i])) for i in range(len(col_names))}
                all_data.append(d)

            # Urutkan kembali ke urutan standar
            all_data.sort(key=lambda d: (
                d.get("TPS", ""),
                d.get("RW", ""),
                d.get("RT", ""),
                d.get("NKK", ""),
                d.get("NAMA", "")
            ))

            # Tampilkan kembali di tabel utama
            with self.freeze_ui():
                self._refresh_table_with_new_data(all_data)
                self._warnai_baris_berdasarkan_ket()
                QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())
                

            # 🔹 Warnai kembali baris-baris
            self._warnai_baris_berdasarkan_ket()
            QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

        except Exception as e:
            if not silent:
                show_modern_error(self, "Error", f"Gagal menampilkan ulang data:\n{e}")
            else:
                print(f"[Silent Reset Warning] {e}")


    def keluar_aplikasi(self):
        """Keluar dari aplikasi lewat menu File → Keluar (dengan dialog modern)."""
        try:
            # 🔹 Tampilkan konfirmasi modern
            if not show_modern_question(
                self,
                "Konfirmasi Keluar",
                "Apakah Anda yakin menutup aplikasi?"
            ):
                return  # ❌ User pilih Tidak → batalkan keluar

            # ✅ Jika user menekan Ya → tutup aplikasi
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal keluar dari aplikasi:\n{e}")


    def make_table_text_selectable(self):
        """Izinkan seleksi teks tapi tetap non-edit."""
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item:
                    flags = item.flags()
                    item.setFlags((flags | Qt.ItemFlag.ItemIsSelectable) & ~Qt.ItemFlag.ItemIsEditable)

    def keyPressEvent(self, event):
        """Menangani Ctrl+C untuk menyalin teks dari cell/table."""
        if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            selected_items = self.table.selectedItems()
            if not selected_items:
                return
            # Ambil semua teks dari cell yang dipilih
            text = "\n".join([item.text() for item in selected_items])
            QApplication.clipboard().setText(text)
        else:
            super().keyPressEvent(event)

    def _on_row_checkbox_changed_for_header_sync(self, item):
        # Hanya respons kalau kolom checkbox (kolom 0) yang berubah
        if item and item.column() == 0 and not getattr(self, "_header_bulk_toggling", False):
            QTimer.singleShot(0, self.sync_header_checkbox_state)


    def show_setting_dialog(self):
        dlg = SettingDialog(self)
        if dlg.exec():
            self.apply_column_visibility()
            self.auto_fit_columns()


    @with_safe_db
    def apply_column_visibility(self, *args, conn=None):
        """Terapkan visibilitas kolom sesuai pengaturan di tabel setting_aplikasi_<tahapan>."""
        cur = conn.cursor()

        # Gunakan tabel setting berdasarkan tahapan aktif
        tbl_name = f"setting_aplikasi_{self._tahapan.lower()}"

        # Pastikan tabel ada
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_name} (
                nama_kolom TEXT PRIMARY KEY,
                tampil INTEGER
            )
        """)

        # Ambil semua pengaturan visibilitas
        cur.execute(f"SELECT nama_kolom, tampil FROM {tbl_name}")
        settings = dict(cur.fetchall())

        # Terapkan ke tabel tampilan
        for i in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(i)
            if not header_item:
                continue  # skip kolom tanpa header label
            col_name = header_item.text().strip()
            if col_name in settings:
                hidden = (settings[col_name] == 0)
                self.table.setColumnHidden(i, hidden)
            else:
                # default: kolom terlihat
                self.table.setColumnHidden(i, False)


    def showEvent(self, event):
        """Otomatis maximize saat pertama kali tampil."""
        super().showEvent(event)
        QTimer.singleShot(0, self.showMaximized)

    def style_button(self, btn, width=70, height=28, bg="#2d2d30", fg="white", bold=False):
        btn.setFixedSize(width, height)
        style = f"""
            QPushButton {{
                font-family: Segoe UI;
                font-size: 12px;
                {"font-weight: reguler;" if bold else ""}
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
        self.update_pagination()
        self.show_page(1)
        
        # Update status bar with filter info
        self.lbl_total.setText(f"{len(filtered_data)} dari {len(self.original_data)} total (filtered)")
        self.update_statusbar()
    
    def clear_filters(self):
        """Clear all filters and restore original data"""
        if hasattr(self, 'original_data') and self.original_data is not None:
            self.all_data = self.original_data.copy()
            self.original_data = None
            
            # Update pagination and display
            self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
            self.current_page = 1
            self.update_pagination()
            self.show_page(1)
            
            # Update status bar
            self.lbl_total.setText(f"{len(self.all_data)} total")
            self.update_statusbar()
        
        # Reset filter form only (to avoid infinite loop)
        if self.filter_sidebar:
            self.filter_sidebar._reset_form_only()
    
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
        
        # Age filter based on birth date
        if "umur_min" in filters and "umur_max" in filters:
            umur_min = filters["umur_min"]
            umur_max = filters["umur_max"]
            
            # Skip if age range is default (0-100)
            if not (umur_min == 0 and umur_max == 100):
                tgl_lahir_str = item.get("TGL_LHR", "").strip()
                if tgl_lahir_str:
                    try:
                        # Try different date formats
                        birth_date = None
                        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                            try:
                                birth_date = datetime.strptime(tgl_lahir_str, fmt).date()
                                break
                            except ValueError:
                                continue
                        
                        if birth_date:
                            today = date.today()
                            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                            
                            if age < umur_min or age > umur_max:
                                return False
                    except Exception:
                        # If we can't parse the date, don't filter by age
                        pass
            
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
    
    # =========================================================
    # DASHBOARD PAGE
    # =========================================================
    def show_dashboard_page(self):
        """Tampilkan Dashboard elegan (dengan animasi, tanpa status bar)."""
        import os
        from PyQt6.QtGui import QIcon

        # === Pastikan self.stack masih valid ===
        if not hasattr(self, "stack") or self.stack is None:
            show_modern_error(self, "Error", "Elemen utama (stack) telah dihapus. Mohon restart aplikasi.")
            return

        # === Pastikan ikon aplikasi (KPU.png) muncul di kiri atas ===
        icon_path = os.path.join(os.path.dirname(__file__), "KPU.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # === Siapkan dashboard (bangun baru atau refresh jika sudah ada) ===
        if hasattr(self, "dashboard_page") and self.dashboard_page is not None:
            # Dashboard sudah pernah dibuat → cukup refresh saja
            if hasattr(self, "refresh_dashboard_on_show"):
                try:
                    self.refresh_dashboard_on_show()
                except Exception as e:
                    print(f"[Dashboard Refresh Error] {e}")
        else:
            # Dashboard belum pernah dibuat → bangun baru
            self.dashboard_page = self._build_dashboard_widget()
            self.stack.addWidget(self.dashboard_page)

        # === Ambil ulang data dari DB aktif (pasti sinkron dengan tabel utama) ===
        @with_safe_db
        def _get_header_stats(self, conn=None):
            cur = conn.cursor()
            tbl = self._active_table()
            where_filter = "WHERE CAST(KET AS INTEGER) NOT IN (1,2,3,4,5,6,7,8)"

            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter}")
            total = cur.fetchone()[0] or 0

            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter} AND JK='L'")
            laki = cur.fetchone()[0] or 0

            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter} AND JK='P'")
            perempuan = cur.fetchone()[0] or 0

            cur.execute(f"SELECT COUNT(DISTINCT DESA) FROM {tbl} {where_filter}")
            desa = cur.fetchone()[0] or 0

            cur.execute(f"SELECT COUNT(DISTINCT TPS) FROM {tbl} {where_filter}")
            tps = cur.fetchone()[0] or 0

            return {"total": total, "laki": laki, "perempuan": perempuan, "desa": desa, "tps": tps}

        stats = _get_header_stats(self)

        # === Update label atas (pastikan sesuai nama label yang anda gunakan) ===
        try:
            if hasattr(self, "lbl_total_pemilih"):
                self.lbl_total_pemilih.setText(f"{stats['total']:,}".replace(",", "."))
            if hasattr(self, "lbl_total_laki"):
                self.lbl_total_laki.setText(f"{stats['laki']:,}".replace(",", "."))
            if hasattr(self, "lbl_total_perempuan"):
                self.lbl_total_perempuan.setText(f"{stats['perempuan']:,}".replace(",", "."))
            if hasattr(self, "lbl_total_desa"):
                self.lbl_total_desa.setText(f"{stats['desa']:,}".replace(",", "."))
            if hasattr(self, "lbl_total_tps"):
                self.lbl_total_tps.setText(f"{stats['tps']:,}".replace(",", "."))
            print("[Dashboard Header] Label atas diperbarui sukses.")
        except Exception as e:
            print(f"[Dashboard Header Error] {e}")

        # === Pastikan sudah terdaftar di stack ===
        if self.stack.indexOf(self.dashboard_page) == -1:
            self.stack.addWidget(self.dashboard_page)

        # Tandai bahwa posisi user sedang di dashboard
        self._is_on_dashboard = True

        # === Sembunyikan toolbar & filter ===
        for tb in self.findChildren(QToolBar):
            tb.hide()
        if hasattr(self, "filter_dock") and self.filter_dock:
            self.filter_dock.hide()

        # === Status bar tetap ada tapi hanya menampilkan versi NexVo ===
        if self.statusBar():
            self.statusBar().showMessage("NexVo v1.0")

        # === Tampilkan dashboard dengan animasi Fade-in ===
        self._stack_fade_to(self.dashboard_page, duration=600)


    def _build_dashboard_widget(self) -> QWidget:
        """Bangun halaman Dashboard modern dinamis dari database aktif."""
        # === Widget utama ===
        dash_widget = QWidget()
        dash_layout = QVBoxLayout(dash_widget)
        dash_layout.setContentsMargins(30, 0, 30, 10)
        dash_layout.setSpacing(25)

        # === Header ===
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

        title_lbl = QLabel("NexVo Pemilu 2029 Desktop – Pemutakhiran Data")
        title_lbl.setStyleSheet("font-size:14pt; font-weight:600; color:#333;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        header.addWidget(logo)
        header.addWidget(title_lbl)
        header.addStretch()

        header_frame = QFrame()
        header_frame.setLayout(header)
        dash_layout.addWidget(header_frame)
        dash_layout.addSpacing(-50)

        # === Fade-in ===
        header_effect = QGraphicsOpacityEffect(header_frame)
        header_frame.setGraphicsEffect(header_effect)
        header_anim = QPropertyAnimation(header_effect, b"opacity")
        header_anim.setDuration(800)
        header_anim.setStartValue(0.0)
        header_anim.setEndValue(1.0)
        header_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        header_anim.start()

        # ======================================================
        # 🧮 Ambil Data Statistik dari Database Aktif
        # ======================================================
        @with_safe_db
        def get_dashboard_data(self, conn=None):
            cur = conn.cursor()
            tbl = self._active_table()

            where_filter = "WHERE CAST(KET AS INTEGER) NOT IN (1,2,3,4,5,6,7,8)"

            # Total pemilih
            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter}")
            total = cur.fetchone()[0] or 0

            # 🧩 Jika tabel kosong, langsung kembalikan nilai 0 semua
            if total == 0:
                return {
                    "desa": self._desa.title(),
                    "total": 0,
                    "laki": 0,
                    "perempuan": 0,
                    "desa_distinct": 0,
                    "tps": 0,
                    "bars": {
                        "MENINGGAL": 0,
                        "GANDA": 0,
                        "DI BAWAH UMUR": 0,
                        "PINDAH DOMISILI": 0,
                        "WNA": 0,
                        "TNI": 0,
                        "POLRI": 0,
                        "SALAH TPS": 0,
                    },
                }

            # Laki-laki & Perempuan
            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter} AND JK='L'")
            laki = cur.fetchone()[0] or 0
            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter} AND JK='P'")
            perempuan = cur.fetchone()[0] or 0

            # Distinct desa & TPS
            cur.execute(f"SELECT COUNT(DISTINCT DESA) FROM {tbl} {where_filter}")
            desa_distinct = cur.fetchone()[0] or 0
            cur.execute(f"SELECT COUNT(DISTINCT TPS) FROM {tbl} {where_filter}")
            tps_distinct = cur.fetchone()[0] or 0

            # Status-statistik (KET 1–8)
            bars = {}
            kode_map = {
                1: "MENINGGAL",
                2: "GANDA",
                3: "DI BAWAH UMUR",
                4: "PINDAH DOMISILI",
                5: "WNA",
                6: "TNI",
                7: "POLRI",
                8: "SALAH TPS"
            }
            for kode, label in kode_map.items():
                cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE CAST(KET AS INTEGER)=?", (kode,))
                bars[label] = cur.fetchone()[0] or 0

            return {
                "desa": self._desa.title(),
                "total": total,
                "laki": laki,
                "perempuan": perempuan,
                "desa_distinct": desa_distinct,
                "tps": tps_distinct,
                "bars": bars,
            }

        stats = get_dashboard_data(self)

        # ======================================================
        # 🪪 Kartu Ringkasan
        # ======================================================
        top_row = QHBoxLayout()
        top_row.setSpacing(15)

        def make_card(icon, title, value):
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

        fmt = lambda x: f"{x:,}".replace(",", ".")
        cards = [
            ("🏦", "Nama Desa", stats["desa"]),
            ("🚻", "Pemilih", fmt(stats["total"])),
            ("🚹", "Laki-laki", fmt(stats["laki"])),
            ("🚺", "Perempuan", fmt(stats["perempuan"])),
            ("🏠", "Kelurahan", fmt(stats["desa_distinct"])),
            ("🚩", "TPS", fmt(stats["tps"])),
        ]
        for icon, title, value in cards:
            top_row.addWidget(make_card(icon, title, value))
        dash_layout.addLayout(top_row)

        # === PIE DONUT + BAR ===
        middle_row = QHBoxLayout()
        middle_row.setSpacing(40)

        # === PIE DONUT ===
        total = max(stats["total"], 1)
        pct_laki = (stats["laki"] / total) * 100
        pct_perempuan = (stats["perempuan"] / total) * 100

        series = QPieSeries()
        slice_laki = series.append("Laki-laki", pct_laki)
        slice_perempuan = series.append("Perempuan", pct_perempuan)

        # Warna
        color_laki = QColor("#6b4e71")      # ungu
        color_perempuan = QColor("#ff6600") # oranye
        slice_laki.setBrush(color_laki)
        slice_perempuan.setBrush(color_perempuan)

        for s in series.slices():
            s.setLabelVisible(False)
            s.setBorderColor(Qt.GlobalColor.transparent)
        series.setHoleSize(0.60)

        chart = QChart()
        chart.addSeries(series)
        chart.setBackgroundVisible(False)
        chart.legend().setVisible(False)  # sembunyikan legend bawaan
        chart.setMargins(QMargins(-15, -15, -15, -15))

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumSize(330, 260)
        chart_view.setStyleSheet("background:#fff; border-radius:12px;")

        # Container donut
        chart_container = QFrame()
        chart_container.setMinimumSize(330, 260)
        chart_container.setStyleSheet("background:#fff; border-radius:12px;")

        cc_layout = QVBoxLayout(chart_container)
        cc_layout.setContentsMargins(0, 0, 0, 0)
        cc_layout.setSpacing(0)
        cc_layout.addWidget(chart_view)

        # Label tengah di chart
        center_label = QGraphicsSimpleTextItem()
        chart.scene().addItem(center_label)
        center_label.setText(f"{pct_laki:.1f}%")
        center_label.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        center_label.setBrush(QColor("#222"))

        def reposition_label():
            rect = chart.plotArea()
            text_rect = center_label.boundingRect()
            x = rect.center().x() - text_rect.width() / 2
            y = rect.center().y() - text_rect.height() / 2
            center_label.setPos(x, y)

        chart.plotAreaChanged.connect(lambda _: reposition_label())
        reposition_label()

        # Label bawah custom (rapat di bawah donut)
        label_row = QHBoxLayout()
        label_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_row.setSpacing(25)
        label_row.setContentsMargins(0, -30, 0, 0)  # dorong ke atas

        # Hover → ubah angka
        def update_center_text(slice_obj=None):
            """Perbarui teks tengah."""
            if slice_obj is None:
                center_label.setText("100%")
            else:
                center_label.setText(f"{slice_obj.value():.1f}%")
            reposition_label()

        def animate_explode(slice_obj, target_factor):
            """Animasi lembut saat slice dihover."""
            anim = QPropertyAnimation(slice_obj, b"explodeDistanceFactor", chart)
            anim.setDuration(180)  # durasi 0.18 detik → halus & cepat
            anim.setStartValue(slice_obj.explodeDistanceFactor())
            anim.setEndValue(target_factor)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            # simpan referensi kecil supaya tidak langsung di-GC
            if not hasattr(chart, "_slice_anims"):
                chart._slice_anims = []
            chart._slice_anims.append(anim)

        def handle_hover(state, slice_obj):
            """Efek hover dengan animasi dan teks dinamis."""
            if state:
                slice_obj.setExploded(True)
                animate_explode(slice_obj, 0.08)
                update_center_text(slice_obj)
            else:
                animate_explode(slice_obj, 0.0)
                # tunda un-explode sedikit agar animasi tidak abrupt
                def restore():
                    slice_obj.setExploded(False)
                    update_center_text(None)
                QTimer.singleShot(160, restore)

        for sl in series.slices():
            sl.setExploded(False)
            sl.setExplodeDistanceFactor(0.0)
            sl.hovered.connect(lambda state, s=sl: handle_hover(state, s))


        def make_color_label(color, text):
            box = QLabel()
            box.setFixedSize(14, 14)
            box.setStyleSheet(f"background:{color.name()}; border-radius:3px;")

            lbl = QLabel(text)
            lbl.setStyleSheet("font-size:12pt; color:#444; background:transparent;")

            lay = QHBoxLayout()
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            container = QWidget()
            container.setLayout(lay)
            lay.addWidget(box)
            lay.addWidget(lbl)

            container.label = lbl  # simpan referensi
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            return container

        item_perempuan = make_color_label(color_perempuan, "Perempuan")
        item_laki = make_color_label(color_laki, "Laki-laki")
        label_row.addWidget(item_perempuan)
        label_row.addWidget(item_laki)
        cc_layout.addLayout(label_row)


        toggle_state = {"laki": False, "perempuan": False}

        def toggle_label(label_name):
            nonlocal toggle_state
            if label_name == "laki":
                toggle_state["laki"] = not toggle_state["laki"]
                lbl = item_laki.label
                if toggle_state["laki"]:
                    lbl.setStyleSheet("font-size:12pt; color:#444; text-decoration: line-through;")
                    center_label.setText(f"{pct_perempuan:.1f}%")
                else:
                    lbl.setStyleSheet("font-size:12pt; color:#444; text-decoration: none;")
                    center_label.setText("100%")
            elif label_name == "perempuan":
                toggle_state["perempuan"] = not toggle_state["perempuan"]
                lbl = item_perempuan.label
                if toggle_state["perempuan"]:
                    lbl.setStyleSheet("font-size:12pt; color:#444; text-decoration: line-through;")
                    center_label.setText(f"{pct_laki:.1f}%")
                else:
                    lbl.setStyleSheet("font-size:12pt; color:#444; text-decoration: none;")
                    center_label.setText("100%")
            reposition_label()

        item_laki.mousePressEvent = lambda e: toggle_label("laki")
        item_perempuan.mousePressEvent = lambda e: toggle_label("perempuan")

        # Bayangan halus
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 50))
        chart_container.setGraphicsEffect(shadow)

        middle_row.addWidget(chart_container, 0)

        # ======================================================
        # 📊 BAR CHART (Statistik CEK_DATA)
        # ======================================================
        bar_frame = QFrame()
        bar_layout = QVBoxLayout(bar_frame)
        bar_layout.setSpacing(14)
        bar_layout.setContentsMargins(5, 35, 20, 35)

        total_bars = sum(stats["bars"].values()) or 1

        for label, val in stats["bars"].items():
            ratio = val / total_bars
            row = QHBoxLayout()
            row.setSpacing(0)

            # Gunakan format upper-case hanya untuk label tertentu
            if label.upper() in ["WNA", "TNI", "POLRI"]:
                label_text = label.upper()
            elif label.upper() == "SALAH TPS":
                label_text = "Salah TPS"
            else:
                label_text = label.title()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size:11pt; color:#555; min-width:115px;")

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
            stretch_val = max(1, min(int(ratio * 100 * base_ratio), 80))
            inner.addWidget(fg, stretch_val)
            inner.addStretch(100 - stretch_val)

            pct = QLabel(f"{val:,}".replace(",", "."))
            pct.setStyleSheet("font-size:11pt; color:#333; min-width:55px; text-align:right;")

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
            QWidget { background:#f9f9f9; color:#333; font-family:'Segoe UI','Segoe UI'; }
            QLabel { color:#333; }
        """)

        # === Simpan referensi elemen untuk refresh cepat ===
        self.card_labels = {
            "total": top_row.itemAt(1).widget().findChildren(QLabel)[1],
            "laki": top_row.itemAt(2).widget().findChildren(QLabel)[1],
            "perempuan": top_row.itemAt(3).widget().findChildren(QLabel)[1],
            "desa": top_row.itemAt(4).widget().findChildren(QLabel)[1],
            "tps": top_row.itemAt(5).widget().findChildren(QLabel)[1],
        }
        self.slice_laki = slice_laki
        self.slice_perempuan = slice_perempuan

        # 🔹 Simpan referensi bar chart: label tampil → {value_label, layout_inner, fg_widget}
        self.bar_labels = {}
        for i in range(bar_layout.count()):
            row_item = bar_layout.itemAt(i)
            row_hbox = row_item.layout()  # ← ambil layout-nya, bukan item mentah

            if row_hbox is None or row_hbox.count() < 2:
                continue

            lbl_widget = row_hbox.itemAt(0).widget()       # QLabel kategori (kiri)
            wrapper    = row_hbox.itemAt(1).widget()       # QFrame (kanan, pembungkus bar_group)
            if lbl_widget is None or wrapper is None:
                continue

            wrapper_layout = wrapper.layout()               # QHBoxLayout pada wrapper
            if wrapper_layout is None or wrapper_layout.count() < 1:
                continue

            # bar_group adalah layout yang anda add dengan wrapper_layout.addLayout(bar_group)
            bar_group_layout = wrapper_layout.itemAt(0).layout()
            if bar_group_layout is None or bar_group_layout.count() < 2:
                continue

            # [0] = bg (QFrame berisi layout 'inner'), [1] = pct (QLabel angka kanan)
            bg_frame    = bar_group_layout.itemAt(0).widget()
            value_label = bar_group_layout.itemAt(1).widget()
            if bg_frame is None or value_label is None:
                continue

            inner_layout = bg_frame.layout()               # HBox 'inner' (berisi fg + stretch)
            if inner_layout is None or inner_layout.count() < 1:
                continue

            # item ke-0 dari inner_layout adalah batang oranye (fg)
            fg_widget = inner_layout.itemAt(0).widget()

            display_label = lbl_widget.text()              # gunakan label tampil sebagai key
            self.bar_labels[display_label] = {
                "value": value_label,   # QLabel angka kanan
                "inner": inner_layout,  # HBox di dalam bg
                "fg": fg_widget,        # batang oranye (QFrame)
            }

        return dash_widget

    
    def refresh_dashboard_on_show(self):
        """Refresh data dashboard setiap kali halaman dashboard ditampilkan."""
        try:
            # Jika dashboard belum pernah dibuat, keluar diam-diam
            if not hasattr(self, "bar_labels") or not hasattr(self, "slice_laki") or not hasattr(self, "slice_perempuan"):
                print("[Dashboard Refresh] Dashboard belum siap → dilewati.")
                return

            if hasattr(self, "dashboard_page") and getattr(self, "current_page", "") == "dashboard":
                if hasattr(self, "refresh_dashboard"):
                    self.refresh_dashboard()
        except Exception as e:
            print(f"[Dashboard Refresh Error] {e}")

        # === Ambil ulang data dari DB aktif ===
        @with_safe_db
        def get_dashboard_data(self, conn=None):
            cur = conn.cursor()
            tbl = self._active_table()
            where_filter = "WHERE CAST(KET AS INTEGER) NOT IN (1,2,3,4,5,6,7,8)"

            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter}")
            total = cur.fetchone()[0] or 0

            if total == 0:
                bars = {
                    "MENINGGAL": 0, "GANDA": 0, "DI BAWAH UMUR": 0, "PINDAH DOMISILI": 0,
                    "WNA": 0, "TNI": 0, "POLRI": 0, "SALAH TPS": 0
                }
                return {"total": 0, "laki": 0, "perempuan": 0,
                        "desa_distinct": 0, "tps": 0, "bars": bars}

            # Data valid → lanjut hitung
            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter} AND JK='L'")
            laki = cur.fetchone()[0] or 0
            cur.execute(f"SELECT COUNT(*) FROM {tbl} {where_filter} AND JK='P'")
            perempuan = cur.fetchone()[0] or 0
            cur.execute(f"SELECT COUNT(DISTINCT DESA) FROM {tbl} {where_filter}")
            desa_distinct = cur.fetchone()[0] or 0
            cur.execute(f"SELECT COUNT(DISTINCT TPS) FROM {tbl} {where_filter}")
            tps_distinct = cur.fetchone()[0] or 0

            kode_map = {
                1: "MENINGGAL", 2: "GANDA", 3: "DI BAWAH UMUR", 4: "PINDAH DOMISILI",
                5: "WNA", 6: "TNI", 7: "POLRI", 8: "SALAH TPS"
            }
            bars = {}
            for kode, label in kode_map.items():
                cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE CAST(KET AS INTEGER)=?", (kode,))
                bars[label] = cur.fetchone()[0] or 0

            return {"total": total, "laki": laki, "perempuan": perempuan,
                    "desa_distinct": desa_distinct, "tps": tps_distinct, "bars": bars}

        stats = get_dashboard_data(self)

        # === Kalau dashboard belum siap, keluar aman ===
        if not hasattr(self, "bar_labels"):
            print("[Dashboard Refresh] Tidak ada bar_labels → dilewati.")
            return
        
        # === Update bar chart ===
        total_safe = max(stats["total"], 1)

        # === Helper untuk ubah panjang batang ===
        def _set_bar_stretch(ref, stretch_0_100: int):
            inner = ref["inner"]
            fg = ref["fg"]
            while inner.count():
                item = inner.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
            inner.addWidget(fg, max(1, min(stretch_0_100, 100)))
            inner.addStretch(max(0, 100 - stretch_0_100))

        def _display_label(name: str) -> str:
            u = name.upper()
            if u in ("WNA", "TNI", "POLRI"):
                return u
            if u == "SALAH TPS":
                return "Salah TPS"
            return name.title()

        for raw_label, val in stats["bars"].items():
            key = _display_label(raw_label)
            if key in self.bar_labels:
                ref = self.bar_labels[key]
                ref["value"].setText(f"{val:,}".replace(",", "."))
                stretch = int((val / total_safe) * 100)
                stretch = max(1, min(stretch, 90))
                _set_bar_stretch(ref, stretch)

        # === Update pie chart ===
        total = max(stats["total"], 1)
        pct_laki = (stats["laki"] / total) * 100
        pct_perempuan = (stats["perempuan"] / total) * 100
        self.slice_laki.setValue(pct_laki)
        self.slice_perempuan.setValue(pct_perempuan)

        # === Refresh label ringkasan atas (Pemilih, Laki-laki, Perempuan, Desa, TPS) ===
        try:
            if hasattr(self, "card_labels"):
                if "total" in self.card_labels:
                    self.card_labels["total"].setText(f"{stats['total']:,}".replace(",", "."))
                if "laki" in self.card_labels:
                    self.card_labels["laki"].setText(f"{stats['laki']:,}".replace(",", "."))
                if "perempuan" in self.card_labels:
                    self.card_labels["perempuan"].setText(f"{stats['perempuan']:,}".replace(",", "."))
                if "desa" in self.card_labels:
                    self.card_labels["desa"].setText(f"{stats['desa_distinct']:,}".replace(",", "."))
                if "tps" in self.card_labels:
                    self.card_labels["tps"].setText(f"{stats['tps']:,}".replace(",", "."))
                print("[Dashboard Header] card_labels diperbarui sukses.")
            else:
                print("[Dashboard Header] card_labels tidak ditemukan.")
        except Exception as e:
            print(f"[Dashboard Header Refresh Error] {e}")

        #print(f"[Dashboard Refresh] OK - total={stats['total']}, L={stats['laki']}, P={stats['perempuan']}")

    
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

       # 🧭 Jalankan animasi aman (clamp ke available screen untuk menghindari setGeometry warning di Windows)
        geo = self.centralWidget().geometry()
        w, h = geo.width(), geo.height()

        # Coba dapatkan screen yang relevan, fallback ke primary
        try:
            screen = QApplication.screenAt(self.mapToGlobal(self.rect().center())) or QApplication.primaryScreen()
        except Exception:
            screen = QApplication.primaryScreen()

        if screen:
            avail = screen.availableGeometry()
            clamped_w = min(w, avail.width())
            clamped_h = min(h, avail.height())
        else:
            clamped_w, clamped_h = w, h

        # Buat QRect yang diklamping, tetap gunakan posisi x/y lama tapi ukuran dikurangi bila perlu
        try:
            clamped_geo = QRect(geo.x(), geo.y(), clamped_w, clamped_h)
        except Exception:
            clamped_geo = QRect(0, 0, clamped_w, clamped_h)

        # Atur geometry awal dan posisi mulai animasi (aman dalam try/except)
        start_rect = QRect(0, 0, clamped_w, clamped_h)
        if direction == "left":
            start_rect.moveTo(clamped_w, 0)
        elif direction == "right":
            start_rect.moveTo(-clamped_w, 0)

        try:
            new_widget.setGeometry(start_rect)
        except Exception:
            # fallback setGeometry yang lebih aman
            try:
                new_widget.setGeometry(0, 0, clamped_w, clamped_h)
            except Exception:
                pass

        # Pasang widget baru sebagai central
        self.setCentralWidget(new_widget)

        # Animasi geser halus — gunakan clamped_geo sebagai target
        try:
            anim = QPropertyAnimation(new_widget, b"geometry")
            anim.setDuration(duration)
            anim.setStartValue(start_rect)
            anim.setEndValue(clamped_geo)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            # Simpan referensi supaya animasi tidak dihentikan premature
            self._slide_anim = anim
        except Exception:
            # Jika animasi gagal, pastikan widget berada di posisi akhir minimal
            try:
                new_widget.setGeometry(clamped_geo)
            except Exception:
                pass

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

        # 🧱 Tambahkan ini agar CEK_DATA tetap tersembunyi setiap saat
        try:
            idx = self.table.horizontalHeaderLabels().index("CEK_DATA")
        except AttributeError:
            # jika tidak ada method horizontalHeaderLabels() → fallback manual
            idx = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())].index("CEK_DATA")
        except ValueError:
            idx = None

        if idx is not None:
            self.table.setColumnHidden(idx, True)


    # === Checkbox di Header Kolom Pertama (Select All) ===
    def init_header_checkbox(self):
        header = self.table.horizontalHeader()
        self.header_checkbox = QCheckBox(header)
        self.header_checkbox.setToolTip("Centang semua / batalkan semua")
        self.header_checkbox.setTristate(False)
        self.header_checkbox.setChecked(False)

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

        # --- Buat Context Menu (tanpa deteksi tema)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #000000;
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
            #("✏️ Lookup", lambda: self._context_action_wrapper(checked_rows, self.lookup_pemilih)),
            ("🔁 Aktifkan Pemilih", lambda: self._context_action_wrapper(checked_rows, self.aktifkan_pemilih)),
            ("🔥 Hapus", lambda: self._context_action_wrapper(checked_rows, self.hapus_pemilih)),
            ("🚫 1. Meninggal", lambda: self._context_action_wrapper(checked_rows, self.meninggal_pemilih)),
            ("⚠️ 2. Ganda", lambda: self._context_action_wrapper(checked_rows, self.ganda_pemilih)),
            ("🧒 3. Di Bawah Umur", lambda: self._context_action_wrapper(checked_rows, self.bawah_umur_pemilih)),
            ("🏠 4. Pindah Domisili", lambda: self._context_action_wrapper(checked_rows, self.pindah_domisili)),
            ("🌍 5. WNA", lambda: self._context_action_wrapper(checked_rows, self.wna_pemilih)),
            ("🪖 6. TNI", lambda: self._context_action_wrapper(checked_rows, self.tni_pemilih)),
            ("👮‍♂️ 7. Polri", lambda: self._context_action_wrapper(checked_rows, self.polri_pemilih)),
            ("📍 8. Salah TPS", lambda: self._context_action_wrapper(checked_rows, self.salah_tps)),
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
        # Tetap dipertahankan agar kompatibel dengan fungsi lain
        if not hasattr(self, "_batch_stats"):
            self._batch_reset_stats()
        self._batch_stats[key] = self._batch_stats.get(key, 0) + 1

    @with_safe_db
    def _context_action_wrapper(self, rows, func, conn=None):
        """
        Menjalankan fungsi context untuk 1 atau banyak baris (versi super kilat penuh, SQLCipher-ready).
        Hanya menampilkan notifikasi sederhana bahwa data telah diproses.
        """

        if isinstance(rows, int):
            rows = [rows]

        # --- Inisialisasi atribut batch
        if not hasattr(self, "_batch_stats"):
            self._batch_reset_stats()
        if not hasattr(self, "_warning_shown_in_batch"):
            self._warning_shown_in_batch = {}
        if not hasattr(self, "_in_batch_mode"):
            self._in_batch_mode = False

        is_batch = len(rows) > 1

        # --- Konfirmasi batch (jika lebih dari satu data)
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
            self._batch_reset_stats()

        # --- Nonaktifkan update GUI sementara
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)

        # --- Gunakan koneksi aman dari db_manager (SQLCipher)
        from db_manager import get_connection
        conn = get_connection()
        cur = conn.cursor()
        conn.execute("PRAGMA busy_timeout = 3000;")

        if is_batch:
            conn.execute("PRAGMA synchronous = OFF;")
            conn.execute("PRAGMA journal_mode = WAL;")

        self._shared_conn = conn
        self._shared_cur = cur

        try:
            for r in rows:
                func(r)
            conn.commit()

        finally:
            # Bersihkan koneksi batch
            self._shared_conn = None
            self._shared_cur = None

            # Pulihkan GUI
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()

            # --- Pop-up sederhana (tanpa statistik)
            if is_batch:
                show_modern_info(self, "Selesai", f"✅ {len(rows)} data telah diproses.")

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

    def lookup_pemilih(self, rows):
        """Fungsi lookup pemilih — belum diimplementasikan."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Lookup Pemilih", "Fitur Lookup Pemilih belum diimplementasikan.")

    # =========================================================
    # 🔹 1. AKTIFKAN PEMILIH (versi batch optimized)
    # =========================================================
    def aktifkan_pemilih(self, row):
        """
        - Gunakan DPID (unik)
        - Satu query update (KET + LastUpdate)
        - Freeze UI selama proses
        - Batch-aware dan SQLCipher-safe
        """
        from datetime import datetime
        from db_manager import get_connection

        with self.freeze_ui():  # 🚀 Bekukan tampilan & event sementara
            try:
                # =====================================================
                # 🛡️ PROTEKSI & AUTO-RECOVERY UNTUK MODE BATCH
                # =====================================================
                if getattr(self, "_in_batch_mode", False):
                    if not hasattr(self, "_shared_conn"):
                        self._shared_conn = None
                    if not hasattr(self, "_shared_cur"):
                        self._shared_cur = None
                    if not hasattr(self, "_shared_query_count"):
                        self._shared_query_count = 0
                    if not hasattr(self, "_warning_shown_in_batch"):
                        self._warning_shown_in_batch = {}

                    try:
                        if self._shared_conn is None or self._shared_cur is None:
                            raise Exception("batch connection reset")
                        self._shared_cur.execute("SELECT 1;")
                    except Exception:
                        conn = get_connection()
                        conn.execute("PRAGMA busy_timeout = 3000;")
                        self._shared_conn = conn
                        self._shared_cur = conn.cursor()
                        self._shared_query_count = 0
                        print("[Batch Recovery] Koneksi SQLCipher diperbaiki.")

                # =====================================================
                # 🧩 Ambil data baris
                # =====================================================
                dpid_item = self.table.item(row, self.col_index("DPID"))
                ket_item  = self.table.item(row, self.col_index("KET"))
                nama_item = self.table.item(row, self.col_index("NAMA"))

                dpid = dpid_item.text().strip() if dpid_item else ""
                ket  = ket_item.text().strip().upper() if ket_item else ""
                nama = nama_item.text().strip() if nama_item else ""

                # ⚠️ Validasi: hanya boleh aktifkan yang KET=1–8
                if not dpid or dpid == "0" or ket not in ("1","2","3","4","5","6","7","8"):
                    if getattr(self, "_in_batch_mode", False):
                        if not self._warning_shown_in_batch.get("aktifkan_pemilih", False):
                            self._warning_shown_in_batch["aktifkan_pemilih"] = True
                    else:
                        show_modern_warning(self, "Ditolak", f"{nama} adalah Pemilih Aktif atau tidak bisa diubah.")
                    self._batch_add("rejected", "aktifkan_pemilih")
                    return

                # =====================================================
                # 🧠 Update di memori dan tampilan
                # =====================================================
                today_str = datetime.now().strftime("%d/%m/%Y")
                if ket_item:
                    ket_item.setText("0")

                gi = self._global_index(row)
                if 0 <= gi < len(self.all_data):
                    self.all_data[gi]["KET"] = "0"
                    self.all_data[gi]["LastUpdate"] = today_str

                last_update_col = self.col_index("LastUpdate")
                if last_update_col != -1:
                    lu_item = self.table.item(row, last_update_col)
                    if not lu_item:
                        lu_item = QTableWidgetItem()
                        self.table.setItem(row, last_update_col, lu_item)
                    lu_item.setText(today_str)

                # =====================================================
                # ⚙️ Query ultra ringan (KET+LastUpdate sekaligus)
                # =====================================================
                tbl = self._active_table()
                if not tbl:
                    return

                sql_update = f"UPDATE {tbl} SET KET = 0, LastUpdate = ? WHERE DPID = ?"
                params = (today_str, dpid)

                if getattr(self, "_in_batch_mode", False):
                    cur = self._shared_cur
                    cur.execute(sql_update, params)
                    self._shared_query_count += 1

                    if self._shared_query_count % 1000 == 0:
                        self._shared_conn.commit()
                else:
                    conn = get_connection()
                    cur = conn.cursor()
                    conn.execute("PRAGMA busy_timeout = 3000;")
                    cur.execute(sql_update, params)
                    conn.commit()

                # =====================================================
                # 🎨 Warnai ulang baris dan tandai sukses
                # =====================================================
                self._warnai_baris_berdasarkan_ket()
                self._terapkan_warna_ke_tabel_aktif()
                self._batch_add("ok", "aktifkan_pemilih")

                # =====================================================
                # 💾 Non-batch mode: simpan & info
                # =====================================================
                if not getattr(self, "_in_batch_mode", False):
                    self._flush_db("aktifkan_pemilih")
                    show_modern_info(self, "Aktifkan", f"{nama} telah diaktifkan kembali.")

            except Exception as e:
                print(f"[DB ERROR] aktifkan_pemilih (fast): {e}")


    # =========================================================
    # 🔹 2. HAPUS PEMILIH (versi batch-optimized)
    # =========================================================
    @with_safe_db
    def hapus_pemilih(self, row, conn=None):
        """Menghapus baris pemilih dari tabel sesuai tahapan aktif (super cepat & aman)."""
        from db_manager import get_connection

        with self.freeze_ui():  # 🚀 Bekukan GUI sementara agar tidak flicker
            try:
                # =====================================================
                # 🛡️ PROTEKSI & AUTO-RECOVERY UNTUK MODE BATCH
                # =====================================================
                if getattr(self, "_in_batch_mode", False):
                    if not hasattr(self, "_shared_conn"):
                        self._shared_conn = None
                    if not hasattr(self, "_shared_cur"):
                        self._shared_cur = None
                    if not hasattr(self, "_shared_query_count"):
                        self._shared_query_count = 0
                    if not hasattr(self, "_warning_shown_in_batch"):
                        self._warning_shown_in_batch = {}

                    # Reconnect jika perlu
                    try:
                        if self._shared_conn is None or self._shared_cur is None:
                            raise Exception("batch connection reset")
                        self._shared_cur.execute("SELECT 1;")
                    except Exception:
                        conn = get_connection()
                        conn.execute("PRAGMA busy_timeout = 3000;")
                        self._shared_conn = conn
                        self._shared_cur = conn.cursor()
                        self._shared_query_count = 0
                        print("[Batch Recovery] Koneksi SQLCipher diperbaiki.")

                # =====================================================
                # 🧩 Ambil data baris
                # =====================================================
                dpid_item = self.table.item(row, self.col_index("DPID"))
                nik_item  = self.table.item(row, self.col_index("NIK"))
                nkk_item  = self.table.item(row, self.col_index("NKK"))
                nama_item = self.table.item(row, self.col_index("NAMA"))

                dpid = dpid_item.text().strip() if dpid_item else ""
                nik  = nik_item.text().strip() if nik_item else ""
                nkk  = nkk_item.text().strip() if nkk_item else ""
                nama = nama_item.text().strip() if nama_item else ""

                # ⚠️ Hanya boleh hapus jika DPID kosong / 0
                if dpid and dpid != "0":
                    if getattr(self, "_in_batch_mode", False):
                        if not self._warning_shown_in_batch.get("hapus_pemilih", False):
                            self._warning_shown_in_batch["hapus_pemilih"] = True
                    else:
                        show_modern_warning(
                            self, "Ditolak",
                            f"{nama} tidak dapat dihapus dari Daftar Pemilih.<br>"
                            f"Hanya Pemilih Baru di tahap ini yang bisa dihapus!"
                        )
                    self._batch_add("rejected", "hapus_pemilih")
                    return

                # 🔸 Konfirmasi (non-batch saja)
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
                rowid = self.all_data[gi].get("rowid") or self.all_data[gi].get("_rowid_")
                if not rowid:
                    show_modern_error(self, "Error", "ROWID tidak ditemukan — data tidak dapat dihapus.")
                    self._batch_add("skipped", "hapus_pemilih")
                    return

                last_update = sig.get("LastUpdate", "").strip()
                tbl = self._active_table()
                if not tbl:
                    show_modern_error(self, "Error", "Tahapan tidak valid — tabel tujuan tidak ditemukan.")
                    self._batch_add("skipped", "hapus_pemilih")
                    return

                # =====================================================
                # ⚙️ Single-query DELETE ultra ringan
                # =====================================================
                sql_delete = f"""
                    DELETE FROM {tbl}
                    WHERE rowid = ?
                    AND IFNULL(NIK,'') = ?
                    AND IFNULL(NKK,'') = ?
                    AND (IFNULL(DPID,'') = ? OR DPID IS NULL)
                    AND IFNULL(TGL_LHR,'') = ?
                    AND IFNULL(LastUpdate,'') = ?
                """
                params = (
                    rowid,
                    sig.get("NIK", ""),
                    sig.get("NKK", ""),
                    sig.get("DPID", ""),
                    sig.get("TGL_LHR", ""),
                    last_update
                )

                if getattr(self, "_in_batch_mode", False):
                    cur = self._shared_cur
                    cur.execute(sql_delete, params)
                    self._shared_query_count += 1

                    # ✅ Commit otomatis setiap 1000 baris
                    if self._shared_query_count % 1000 == 0:
                        self._shared_conn.commit()
                else:
                    conn = get_connection()
                    cur = conn.cursor()
                    conn.execute("PRAGMA busy_timeout = 3000;")
                    cur.execute(sql_delete, params)
                    conn.commit()

                # =====================================================
                # 🧹 Hapus dari memori
                # =====================================================
                del self.all_data[gi]
                if (self.current_page > 1) and ((self.current_page - 1) * self.rows_per_page >= len(self.all_data)):
                    self.current_page -= 1

                # =====================================================
                # 💬 Info sukses & catat batch
                # =====================================================
                if not getattr(self, "_in_batch_mode", False):
                    show_modern_info(self, "Selesai", f"{nama} berhasil dihapus dari {tbl.upper()}!")

                self._batch_add("ok", "hapus_pemilih")

            except Exception as e:
                show_modern_error(self, "Error", f"Gagal menghapus data:\n{e}")
                self._batch_add("skipped", "hapus_pemilih")

            # =====================================================
            # 🔚 Tutup koneksi batch di akhir proses massal
            # =====================================================
            if not getattr(self, "_in_batch_mode", False) and hasattr(self, "_shared_conn"):
                try:
                    self._shared_conn.commit()
                    self._shared_cur = None
                    self._shared_conn = None
                except Exception:
                    pass

    # =========================================================
    # 🔹 3. STATUS PEMILIH (versi batch optimized)
    # =========================================================
    def set_ket_status(self, row, new_value: str, label: str):
        """
        - Update berdasar DPID (unik)
        - Gunakan shared connection bila batch
        - Freeze UI selama proses (tanpa redraw berulang)
        """
        from datetime import datetime
        from db_manager import get_connection

        with self.freeze_ui():  # 🚀 Bekukan tampilan sementara
            try:
                # =====================================================
                # 🧱 Inisialisasi batch environment aman
                # =====================================================
                if getattr(self, "_in_batch_mode", False):
                    if not hasattr(self, "_shared_conn"):
                        self._shared_conn = None
                    if not hasattr(self, "_shared_cur"):
                        self._shared_cur = None
                    if not hasattr(self, "_shared_query_count"):
                        self._shared_query_count = 0
                    if not hasattr(self, "_warning_shown_in_batch"):
                        self._warning_shown_in_batch = {}

                    # Reconnect jika perlu
                    try:
                        if self._shared_conn is None or self._shared_cur is None:
                            raise Exception("batch connection reset")
                        self._shared_cur.execute("SELECT 1;")
                    except Exception:
                        conn = get_connection()
                        conn.execute("PRAGMA busy_timeout = 3000;")
                        self._shared_conn = conn
                        self._shared_cur = conn.cursor()
                        self._shared_query_count = 0
                        print("[Batch Recovery] Koneksi SQLCipher diperbaiki.")

                # =====================================================
                # 🧩 Ambil data baris
                # =====================================================
                dpid_item = self.table.item(row, self.col_index("DPID"))
                nama_item = self.table.item(row, self.col_index("NAMA"))
                nama = nama_item.text().strip() if nama_item else ""

                if not dpid_item or dpid_item.text().strip() in ("", "0"):
                    if getattr(self, "_in_batch_mode", False):
                        if not self._warning_shown_in_batch.get("set_ket_status", False):
                            show_modern_warning(self, "Ditolak", "Data Pemilih Baru tidak bisa di-TMS-kan.")
                            self._warning_shown_in_batch["set_ket_status"] = True
                    else:
                        show_modern_warning(self, "Ditolak", f"{nama} adalah Pemilih Baru dan tidak bisa di-TMS-kan.")
                    self._batch_add("rejected", f"set_ket_status_{label}")
                    return

                dpid = dpid_item.text().strip()
                tbl = self._active_table()
                if not tbl:
                    return

                # =====================================================
                # 🧠 Update cepat di memori
                # =====================================================
                gi = self._global_index(row)
                if 0 <= gi < len(self.all_data):
                    self.all_data[gi]["KET"] = new_value

                ket_item = self.table.item(row, self.col_index("KET"))
                if ket_item:
                    ket_item.setText(new_value)

                # =====================================================
                # ⚙️ Query ultra ringan
                # =====================================================
                today_str = datetime.now().strftime("%d/%m/%Y")

                # Single update untuk dua kolom (sekali query)
                sql_update = f"UPDATE {tbl} SET KET = ?, LastUpdate = ? WHERE DPID = ?"
                params = (new_value, today_str, dpid)

                if getattr(self, "_in_batch_mode", False):
                    cur = self._shared_cur
                    cur.execute(sql_update, params)
                    self._shared_query_count += 1

                    if self._shared_query_count % 1000 == 0:
                        self._shared_conn.commit()
                else:
                    conn = get_connection()
                    cur = conn.cursor()
                    conn.execute("PRAGMA busy_timeout = 3000;")
                    cur.execute(sql_update, params)
                    conn.commit()

                # =====================================================
                # 🧩 Perbarui tampilan (langsung di memori)
                # =====================================================
                last_update_col = self.col_index("LastUpdate")
                if last_update_col != -1:
                    lu_item = self.table.item(row, last_update_col)
                    if not lu_item:
                        lu_item = QTableWidgetItem()
                        self.table.setItem(row, last_update_col, lu_item)
                    lu_item.setText(today_str)
                    if 0 <= gi < len(self.all_data):
                        self.all_data[gi]["LastUpdate"] = today_str

                # =====================================================
                # 🎨 Warnai dan tandai hasil
                # =====================================================
                self._warnai_baris_berdasarkan_ket()
                self._terapkan_warna_ke_tabel_aktif()
                self._batch_add("ok", f"set_ket_status_{label}")

                # =====================================================
                # 💾 Non-batch mode: simpan & info
                # =====================================================
                if not getattr(self, "_in_batch_mode", False):
                    self._flush_db("set_ket_status")
                    show_modern_info(self, label, f"{nama} disaring sebagai Pemilih {label}.")

            except Exception as e:
                print(f"[DB ERROR] set_ket_status (fast): {e}")


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


    @with_safe_db
    def update_database_field(self, row, field_name, value, conn=None):
        try:
            nik_col = self.col_index("NIK")
            nik = self.table.item(row, nik_col).text().strip() if nik_col != -1 else None
            if not nik:
                return

            tbl = self._active_table()
            if not tbl:
                return

            # batch mode → jangan commit
            if getattr(self, "_in_batch_mode", False) and hasattr(self, "_shared_cur") and self._shared_cur:
                self._shared_cur.execute(f"UPDATE {tbl} SET {field_name}=? WHERE NIK=?", (value, nik))
                return

            cur = conn.cursor()
            conn.execute("PRAGMA busy_timeout = 3000;")
            cur.execute(f"UPDATE {tbl} SET {field_name}=? WHERE NIK=?", (value, nik))
            conn.commit()

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memperbarui kolom <b>{field_name}</b>:\n{e}")


    def apply_shadow(self, widget, blur=24, dx=0, dy=6, rgba=(0,0,0,180)):
        eff = QGraphicsDropShadowEffect(widget)
        eff.setBlurRadius(blur)
        eff.setOffset(dx, dy)
        eff.setColor(QColor(*rgba))
        widget.setGraphicsEffect(eff)

    @with_safe_db
    def cek_data(self, auto: bool = False, *, conn=None):
        """
        🔍 Pemeriksaan data super kilat (SQLCipher-safe)
        Memeriksa seluruh self.all_data dan menulis hasil ke kolom CEK_DATA.
        - Pemeriksaan 'Beda TPS' hanya menghitung baris dengan KET bukan 1–8.
        """
        from collections import defaultdict
        from datetime import datetime

        tahap = getattr(self, "_tahapan", "").strip().upper()
        tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

        if not auto:
            if not show_modern_question(
                self,
                "Konfirmasi",
                "Apakah anda yakin ingin menjalankan proses <b>Cek Data</b>?<br><br>"
                "Proses ini akan memeriksa seluruh data dan mungkin memerlukan waktu beberapa detik."
            ):
                show_modern_info(self, "Dibatalkan", "Proses cek data dibatalkan oleh pengguna.")
                return

        # === Muat data bila belum ada ===
        if not getattr(self, "all_data", None):
            try:
                self.load_data_from_db()
            except Exception as e:
                show_modern_error(self, "Error", f"Gagal memuat data awal:\n{e}")
                return
            if not self.all_data:
                show_modern_info(self, "Info", "Tidak ada data untuk diperiksa.")
                return

        # === Struktur cepat ===
        target_date = datetime(2029, 6, 26)
        hasil = ["Sesuai"] * len(self.all_data)
        nik_count, nik_ket_map = defaultdict(int), defaultdict(set)
        nik_seen = defaultdict(list)

        get = lambda d, k: str(d.get(k, "")).strip()

        # === Pass 1 – kumpulkan pola dasar ===
        for i, d in enumerate(self.all_data):
            nik = get(d, "NIK")
            nkk = get(d, "NKK")
            tps = get(d, "TPS")
            ket = get(d, "KET").upper()
            if nik:
                nik_count[nik] += 1
                nik_ket_map[nik].add(ket)
            if nik and ket not in ("1","2","3","4","5","6","7","8"):
                nik_seen[nik].append(i)

        # === Pass 2 – validasi dasar cepat ===
        for i, d in enumerate(self.all_data):
            nik = get(d, "NIK")
            nkk = get(d, "NKK")
            tgl = get(d, "TGL_LHR")
            ket = get(d, "KET").upper()
            sts = get(d, "STS").upper()

            # NKK
            if len(nkk) != 16:
                hasil[i] = "NKK Invalid"; continue
            try:
                dd, mm = int(nkk[6:8]), int(nkk[8:10])
                if not (1 <= dd <= 31 and 1 <= mm <= 12):
                    hasil[i] = "Potensi NKK Invalid"; continue
            except Exception:
                hasil[i] = "Potensi NKK Invalid"; continue

            # NIK
            if len(nik) != 16:
                hasil[i] = "NIK Invalid"; continue
            try:
                dd, mm = int(nik[6:8]), int(nik[8:10])
                if not (1 <= dd <= 71 and 1 <= mm <= 12):
                    hasil[i] = "Potensi NIK Invalid"; continue
            except Exception:
                hasil[i] = "Potensi NIK Invalid"; continue

            # Umur
            if "|" in tgl:
                try:
                    dd, mm, yy = map(int, tgl.split("|"))
                    umur = (target_date - datetime(yy, mm, dd)).days / 365.25
                    if umur < 0 or umur < 13:
                        hasil[i] = "Potensi Dibawah Umur"; continue
                    elif umur < 17 and sts == "B":
                        hasil[i] = "Dibawah Umur"; continue
                except Exception:
                    pass

        # === Pass 3 – Deteksi BEDA TPS (skip baris KET 1–8) ===
        from collections import defaultdict
        getv = lambda idx, key: str(self.all_data[idx].get(key, "")).strip()
        nkk_groups = defaultdict(list)
        for i, d in enumerate(self.all_data):
            ket = get(d, "KET")
            if ket in ("1","2","3","4","5","6","7","8"):
                continue  # ⛔ skip baris KET 1–8
            nkk = get(d, "NKK")
            if nkk:
                nkk_groups[nkk].append(i)

        for nkk, idxs in nkk_groups.items():
            if len(idxs) <= 1:
                continue
            tps_set = {getv(i, "TPS") for i in idxs}
            if len(tps_set) <= 1:
                continue
            # Semua baris yang tersisa (non-1-8) punya NKK sama & TPS beda → Beda TPS
            for i in idxs:
                hasil[i] = "Beda TPS"

        # === Pass 4 – Ganda Aktif ===
        for nik, idxs in nik_seen.items():
            if len(idxs) > 1:
                for j in idxs:
                    hasil[j] = "Ganda Aktif"

        # === Pass 5 – Pemilih Baru / Pemula ===
        for i, d in enumerate(self.all_data):
            ket = get(d, "KET").upper()
            nik = get(d, "NIK")
            if ket == "B":
                hasil[i] = "Pemilih Baru" if nik_count[nik] > 1 else "Pemilih Pemula"

        # === Pass 6 – Tidak Padan ===
        for i, d in enumerate(self.all_data):
            ket = get(d, "KET").upper()
            nik = get(d, "NIK")
            if ket == "8" and "B" not in nik_ket_map[nik]:
                hasil[i] = "Tidak Padan"

        # === Commit hasil ke memori & database ===
        for i, val in enumerate(hasil):
            self.all_data[i]["CEK_DATA"] = val

        try:
            cur = conn.cursor()
            cur.executescript("""
                PRAGMA synchronous = OFF;
                PRAGMA journal_mode = WAL;
                PRAGMA temp_store = MEMORY;
            """)
            cur.executemany(
                f"UPDATE {tbl_name} SET CEK_DATA = ? WHERE rowid = ?",
                [(d.get("CEK_DATA", ""), d.get("rowid"))
                for d in self.all_data if d.get("rowid")]
            )
            conn.commit()
        except Exception as e:
            show_modern_error(self, "Gagal Commit", f"Gagal menyimpan hasil ke database:\n{e}")
            return
        
        try:
            # ============================================================
            # 📴 Matikan semua popup sementara (modern + QMessageBox)
            # ============================================================
            def no_popup(*a, **kw):
                return QMessageBox.StandardButton.No  # default "tidak" untuk pertanyaan

            import types
            old_info = globals().get("show_modern_info")
            old_warn = globals().get("show_modern_warning")
            old_ques = globals().get("show_modern_question")
            old_qwarn = QMessageBox.warning
            old_qques = QMessageBox.question

            globals()["show_modern_info"] = no_popup
            globals()["show_modern_warning"] = no_popup
            globals()["show_modern_question"] = no_popup
            QMessageBox.warning = no_popup
            QMessageBox.question = no_popup

            # Jalankan sort_data tanpa gangguan popup
            #self.sort_data()

        finally:
            # ============================================================
            # 🔁 Pulihkan fungsi asli setelah selesai
            # ============================================================
            if old_info: globals()["show_modern_info"] = old_info
            if old_warn: globals()["show_modern_warning"] = old_warn
            if old_ques: globals()["show_modern_question"] = old_ques
            QMessageBox.warning = old_qwarn
            QMessageBox.question = old_qques


        # === Refresh tampilan ===
        self.show_page(self.current_page)
        try:
            self._warnai_baris_berdasarkan_ket()
            self._terapkan_warna_ke_tabel_aktif()
        except Exception as e:
            print(f"[WARN] Gagal menerapkan warna otomatis: {e}")

        show_modern_info(self, "Selesai",
            f"Pemeriksaan {len(self.all_data):,} data selesai dilakukan!")
        
    def cek_potensi_nkk_invalid(self):
        """🔍 Pemeriksaan Potensi NKK Invalid di seluruh data (full DB)."""
        from db_manager import get_connection
        from PyQt6.QtCore import QTimer

        try:
            tahap = getattr(self, "_tahapan", "").strip().upper()
            tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {tbl_name}")
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            if not rows:
                show_modern_info(self, "Info", "Tabel kosong — tidak ada data untuk diperiksa.")
                with self.freeze_ui():
                    self._refresh_table_with_new_data([])
                return

            all_data = [{col_names[i]: ("" if r[i] is None else str(r[i])) for i in range(len(col_names))} for r in rows]

            hasil_data = []
            for d in all_data:
                nkk = d.get("NKK", "").strip()
                ket = d.get("KET", "").strip().upper()
                if ket in ("1","2","3","4","5","6","7","8"):
                    continue
                if len(nkk) != 16:
                    hasil_data.append(d)
                    continue
                try:
                    dd, mm = int(nkk[6:8]), int(nkk[8:10])
                    if not (1 <= dd <= 31 and 1 <= mm <= 12):
                        hasil_data.append(d)
                except Exception:
                    hasil_data.append(d)

            # tampilkan walau kosong
            with self.freeze_ui():
                self._refresh_table_with_new_data(hasil_data)
                self._warnai_baris_berdasarkan_ket()
                QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

            if hasil_data:
                show_modern_info(self, "Selesai", 
                    f"{len(hasil_data)} Data Potensi NKK Invalid Ditemukan.\n"
                    f"Harap segera periksa data anda!")
            else:
                show_modern_info(self, "Selesai", "Tidak Ada Data Potensi NKK Invalid.")

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memeriksa data Potensi NKK Invalid:\n{e}")


    def cek_potensi_nik_invalid(self):
        """🔍 Pemeriksaan Potensi NIK Invalid di seluruh data (full DB)."""
        from db_manager import get_connection
        from PyQt6.QtCore import QTimer

        try:
            tahap = getattr(self, "_tahapan", "").strip().upper()
            tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {tbl_name}")
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            if not rows:
                show_modern_info(self, "Info", "Tabel kosong — tidak ada data untuk diperiksa.")
                with self.freeze_ui():
                    self._refresh_table_with_new_data([])
                return

            all_data = [{col_names[i]: ("" if r[i] is None else str(r[i])) for i in range(len(col_names))} for r in rows]

            hasil_data = []
            for d in all_data:
                nik = d.get("NIK", "").strip()
                ket = d.get("KET", "").strip().upper()
                if ket in ("1","2","3","4","5","6","7","8"):
                    continue
                if len(nik) != 16:
                    hasil_data.append(d)
                    continue
                try:
                    dd, mm = int(nik[6:8]), int(nik[8:10])
                    if not (1 <= dd <= 71 and 1 <= mm <= 12):
                        hasil_data.append(d)
                except Exception:
                    hasil_data.append(d)

            with self.freeze_ui():
                self._refresh_table_with_new_data(hasil_data)
                self._warnai_baris_berdasarkan_ket()
                QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

            if hasil_data:
                show_modern_info(self, "Selesai", 
                    f"{len(hasil_data)} Data Potensi NIK Invalid Ditemukan.\n"
                    f"Harap segera periksa data anda!")
            else:
                show_modern_info(self, "Selesai", "Tidak Ada Data Potensi NIK Invalid.")

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memeriksa data Potensi NIK Invalid:\n{e}")


    def cek_potensi_dibawah_umur(self):
        """🔍 Pemeriksaan Potensi Dibawah Umur di seluruh data (full DB)."""
        from db_manager import get_connection
        from datetime import datetime
        from PyQt6.QtCore import QTimer

        target_date = datetime(2029, 6, 26)

        try:
            tahap = getattr(self, "_tahapan", "").strip().upper()
            tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {tbl_name}")
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            if not rows:
                show_modern_info(self, "Info", "Tabel kosong — tidak ada data untuk diperiksa.")
                with self.freeze_ui():
                    self._refresh_table_with_new_data([])
                return

            all_data = [{col_names[i]: ("" if r[i] is None else str(r[i])) for i in range(len(col_names))} for r in rows]
            hasil_data = []

            for d in all_data:
                tgl = d.get("TGL_LHR", "").strip()
                ket = d.get("KET", "").strip().upper()
                sts = d.get("STS", "").strip().upper()
                if ket in ("1","2","3","4","5","6","7","8"):
                    continue
                if not tgl:
                    continue

                for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        tgl_lhr = datetime.strptime(tgl, fmt)
                        break
                    except Exception:
                        tgl_lhr = None
                if not tgl_lhr:
                    continue

                umur = (target_date - tgl_lhr).days / 365.25
                if umur < 13 or (umur < 17 and sts == "B"):
                    d["CEK_DATA"] = "Potensi Dibawah Umur"
                    hasil_data.append(d)

            with self.freeze_ui():
                self._refresh_table_with_new_data(hasil_data)
                self._warnai_baris_berdasarkan_ket()
                QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

            if hasil_data:
                show_modern_info(self, "Selesai", f"{len(hasil_data)} Data Potensi Dibawah Umur Ditemukan.")
            else:
                show_modern_info(self, "Selesai", "Tidak Ada Pemilih Potensi Dibawah Umur.")

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memeriksa data Potensi Dibawah Umur:\n{e}")


    def cek_beda_tps(self):
        """
        🔍 Pemeriksaan Pemilih Beda TPS di seluruh data (full DB)
        - Mendeteksi pemilih dengan NKK sama tapi TPS berbeda
        - Melewati baris dengan KET = 1–8
        - Menampilkan hasil ke tabel tanpa menghapus kolom apa pun
        """
        from collections import defaultdict
        from db_manager import get_connection
        from PyQt6.QtCore import QTimer

        try:
            tahap = getattr(self, "_tahapan", "").strip().upper()
            tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {tbl_name}")
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            # === Jika tabel kosong ===
            if not rows:
                show_modern_info(self, "Info", "Tabel kosong — tidak ada data untuk diperiksa.")
                with self.freeze_ui():
                    self._refresh_table_with_new_data([])  # tampilkan tabel kosong
                return

            # === Muat seluruh data ke memori ===
            all_data = [
                {col_names[i]: ("" if r[i] is None else str(r[i])) for i in range(len(col_names))}
                for r in rows
            ]

            # === Kelompokkan berdasarkan NKK ===
            nkk_groups = defaultdict(list)
            for d in all_data:
                nkk = d.get("NKK", "").strip()
                ket = d.get("KET", "").strip()
                if not nkk:
                    continue
                if ket in ("1", "2", "3", "4", "5", "6", "7", "8"):
                    continue  # ⛔ lewati baris dengan KET 1–8
                nkk_groups[nkk].append(d)

            # === Deteksi NKK yang muncul di TPS berbeda ===
            hasil_data = []
            for nkk, daftar in nkk_groups.items():
                if len(daftar) <= 1:
                    continue
                tps_set = {d.get("TPS", "").strip() for d in daftar}
                if len(tps_set) > 1:
                    for d in daftar:
                        d["CEK_DATA"] = "Beda TPS"
                        hasil_data.append(d)

            # === Urutkan hasil (meski kosong tetap aman) ===
            hasil_data.sort(key=lambda d: (
                d.get("NKK", ""),
                d.get("TPS", ""),
                d.get("RW", ""),
                d.get("RT", ""),
                d.get("NAMA", "")
            ))

            # === Tampilkan hasil ke tabel (termasuk jika kosong) ===
            with self.freeze_ui():
                self._refresh_table_with_new_data(hasil_data)
                self._warnai_baris_berdasarkan_ket()
                QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

            # === Popup hasil ===
            if hasil_data:
                show_modern_info(
                    self,
                    "Selesai",
                    f"{len(hasil_data)} Data Pemilih Beda TPS Ditemukan.\n"
                    f"Harap segera pindahkan ke TPS yang seharusnya!"
                )
            else:
                show_modern_info(
                    self,
                    "Selesai",
                    "Tidak Ditemukan Data Pemilih Beda TPS."
                )

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memeriksa data Pemilih Beda TPS:\n{e}")


    def cek_tidak_padan(self):
        """
        🔍 Pemeriksaan Pemilih Tidak Padan di seluruh data (full DB)
        - Mendeteksi pemilih dengan KET = 8 yang tidak memiliki pasangan KET = 'B'
        - Melewati baris dengan KET = 1–8 selain 8
        - Menampilkan hasil ke tabel tanpa menghapus kolom apa pun
        """
        from collections import defaultdict
        from db_manager import get_connection
        from PyQt6.QtCore import QTimer

        try:
            tahap = getattr(self, "_tahapan", "").strip().upper()
            tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {tbl_name}")
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            # === Jika tabel kosong ===
            if not rows:
                show_modern_info(self, "Info", "Tabel kosong — tidak ada data untuk diperiksa.")
                with self.freeze_ui():
                    self._refresh_table_with_new_data([])  # tampilkan tabel kosong
                return

            # === Muat seluruh data ===
            all_data = [
                {col_names[i]: ("" if r[i] is None else str(r[i])) for i in range(len(col_names))}
                for r in rows
            ]

            # === Kelompokkan berdasarkan NIK ===
            nik_ket_map = defaultdict(set)
            for d in all_data:
                nik = d.get("NIK", "").strip()
                ket = d.get("KET", "").strip().upper()
                if nik:
                    nik_ket_map[nik].add(ket)

            # === Pemeriksaan: KET=8 tanpa pasangan B ===
            hasil_data = []
            for d in all_data:
                ket = d.get("KET", "").strip().upper()
                nik = d.get("NIK", "").strip()
                if not nik:
                    continue
                if ket == "8" and "B" not in nik_ket_map[nik]:
                    d["CEK_DATA"] = "Tidak Padan"
                    hasil_data.append(d)

            # === Urutkan hasil (tetap aman meski kosong) ===
            hasil_data.sort(key=lambda d: (
                d.get("TPS", ""),
                d.get("RW", ""),
                d.get("RT", ""),
                d.get("NKK", ""),
                d.get("NAMA", "")
            ))

            # === Tampilkan hasil ke tabel ===
            with self.freeze_ui():
                self._refresh_table_with_new_data(hasil_data)
                self._warnai_baris_berdasarkan_ket()
                QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

            # === Popup hasil ===
            if hasil_data:
                show_modern_info(
                    self,
                    "Selesai",
                    f"{len(hasil_data)} Data Pemilih Tidak Padan Ditemukan.\n"
                    f"Harap dimasukkan sebagai Pemilih Baru di TPS yang seharusnya!"
                )
            else:
                show_modern_info(
                    self,
                    "Selesai",
                    "Tidak Ditemukan Data Pemilih Tidak Padan."
                )

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memeriksa data Pemilih Tidak Padan:\n{e}")


    def cek_ganda_nik(self):
        """
        🔍 Pemeriksaan Pemilih Ganda NIK di seluruh data (full DB)
        - Mendeteksi NIK yang muncul lebih dari satu kali
        - Melewati baris dengan KET = 1–8
        - Menampilkan hasil ke tabel tanpa menghapus kolom apa pun
        """
        from collections import defaultdict
        from db_manager import get_connection
        from PyQt6.QtCore import QTimer

        try:
            tahap = getattr(self, "_tahapan", "").strip().upper()
            tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {tbl_name}")
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            # === Jika tabel kosong ===
            if not rows:
                show_modern_info(self, "Info", "Tabel kosong — tidak ada data untuk diperiksa.")
                with self.freeze_ui():
                    self._refresh_table_with_new_data([])  # tampilkan tabel kosong
                return

            # === Muat seluruh data ===
            all_data = [
                {col_names[i]: ("" if r[i] is None else str(r[i])) for i in range(len(col_names))}
                for r in rows
            ]

            # === Kelompokkan berdasarkan NIK ===
            nik_groups = defaultdict(list)
            for d in all_data:
                nik = d.get("NIK", "").strip()
                ket = d.get("KET", "").strip().upper()
                if nik and ket not in ("1", "2", "3", "4", "5", "6", "7", "8"):
                    nik_groups[nik].append(d)

            # === Deteksi NIK yang muncul lebih dari satu kali ===
            hasil_data = []
            for nik, daftar in nik_groups.items():
                if len(daftar) > 1:
                    for d in daftar:
                        d["CEK_DATA"] = "Ganda Aktif"
                        hasil_data.append(d)

            # === Urutkan hasil (tetap aman meski kosong) ===
            hasil_data.sort(key=lambda d: (
                d.get("TPS", ""),
                d.get("RW", ""),
                d.get("RT", ""),
                d.get("NKK", ""),
                d.get("NAMA", "")
            ))

            # === Tampilkan hasil ke tabel ===
            with self.freeze_ui():
                self._refresh_table_with_new_data(hasil_data)
                self._warnai_baris_berdasarkan_ket()
                QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

            # === Popup hasil ===
            if hasil_data:
                show_modern_info(
                    self,
                    "Selesai",
                    f"{len(hasil_data)} Data Pemilih Ganda NIK Ditemukan.\n"
                    f"Harap segera periksa data anda!"
                )
            else:
                show_modern_info(
                    self,
                    "Selesai",
                    "Tidak Ditemukan Data Pemilih Ganda NIK."
                )

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memeriksa data Pemilih Ganda NIK:\n{e}")


    def cek_pemilih_pemula(self):
        """
        🔍 Pemilih Pemula:
        - Baris dengan KET = 'B'
        - NIK hanya muncul sekali di SELURUH tabel aktif (tanpa melewatkan KET 1–8)
        - Tampilkan hasil ke tabel (urut: TPS, RW, RT, NKK, NAMA)
        - Jika tidak ditemukan → tampilkan tabel kosong
        """
        from db_manager import get_connection
        from collections import defaultdict
        from PyQt6.QtCore import QTimer

        try:
            tahap = getattr(self, "_tahapan", "").strip().upper()
            tbl_name = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}.get(tahap, "dphp")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {tbl_name}")
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            if not rows:
                show_modern_info(self, "Info", "Tabel kosong — tidak ada data untuk diperiksa.")
                with self.freeze_ui():
                    self._refresh_table_with_new_data([])  # tampilkan tabel kosong
                return

            # === Muat semua data ===
            all_data = [
                {col_names[i]: ("" if r[i] is None else str(r[i])) for i in range(len(col_names))}
                for r in rows
            ]

            # === Hitung kemunculan NIK (semua data, tanpa skip KET 1–8) ===
            nik_count = defaultdict(int)
            for d in all_data:
                nik = d.get("NIK", "").strip()
                if nik:
                    nik_count[nik] += 1

            # === Ambil baris dengan KET='B' dan NIK unik (count==1) ===
            hasil_data = []
            for d in all_data:
                if d.get("KET", "").strip().upper() == "B":
                    nik = d.get("NIK", "").strip()
                    if nik and nik_count[nik] == 1:
                        d["CEK_DATA"] = "Pemilih Pemula"
                        hasil_data.append(d)

            # === Urutkan hasil ===
            hasil_data.sort(key=lambda d: (
                d.get("TPS", ""),
                d.get("RW", ""),
                d.get("RT", ""),
                d.get("NKK", ""),
                d.get("NAMA", "")
            ))

            # === Tampilkan hasil (termasuk kosong) ===
            with self.freeze_ui():
                self._refresh_table_with_new_data(hasil_data)
                self._warnai_baris_berdasarkan_ket()
                QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())

            # === Info hasil ===
            if hasil_data:
                show_modern_info(
                    self,
                    "Selesai",
                    f"{len(hasil_data)} Data Pemilih Pemula Ditemukan.\n"
                    f"Ini hanya untuk keperluan verifikasi anda."
                )
            else:
                show_modern_info(
                    self,
                    "Selesai",
                    "Tidak Ditemukan Data Pemilih Pemula."
                )

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memeriksa data Pemilih Pemula:\n{e}")


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
        warna_default = warna_cache["hitam"]

        idx_cekdata = self._col_index("CEK_DATA")
        idx_ket = self._col_index("KET")

        for d in self.all_data:
            cek_data_val = str(d.get("CEK_DATA", "")).strip()
            ket_val = str(d.get("KET", "")).strip()

            # === PRIORITAS WARNA ===
            if ket_val in ("1", "2", "3", "4", "5", "6", "7", "8"):
                # 1️⃣ KET bernilai 1–8 → merah
                brush = warna_cache["merah"]

            elif ket_val.lower() == "b":
                # 2️⃣ KET = "B" → hijau
                brush = warna_cache["hijau"]

            elif ket_val.lower() == "u":
                # 3️⃣ KET = "U" → kuning
                brush = warna_cache["kuning"]

            else:
                # 5️⃣ Default → hitam
                brush = warna_default

            # Simpan warna ke cache data
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
    # Import CSV Function
    # =================================================
    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        # 🧹 Pastikan semua data tampil dulu sebelum import baru
        try:
            with self.freeze_ui():
                self.reset_tampilkan_semua_data(silent=True)
        except Exception as e:
            print(f"[Warning] Gagal reset tampilan sebelum import: {e}")

        try:
            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = list(csv.reader(csvfile, delimiter="#"))
                if len(reader) < 15:
                    show_modern_warning(self, "Error", "File CSV tidak valid atau terlalu pendek.")
                    return

                # 🔹 Verifikasi baris ke-15
                kecamatan_csv = reader[14][1].strip().upper()
                desa_csv = reader[14][3].strip().upper()
                if kecamatan_csv != self._kecamatan or desa_csv != self._desa:
                    show_modern_warning(
                        self, "Error",
                        f"Import CSV gagal!\n"
                        f"Harap Import CSV untuk Desa {self._desa.title()} yang bersumber dari Sidalih"
                    )
                    return

                # 🔹 Tentukan nama tabel berdasarkan tahapan login
                tahap = self._tahapan.strip().upper()
                tabel_map = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}
                tbl_name = tabel_map.get(tahap)
                if not tbl_name:
                    show_modern_warning(self, "Error", f"Tahapan tidak dikenal: {tahap}")
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

                # ⚡ Cache index header agar cepat
                header_idx = {col: i for i, col in enumerate(header)}
                idx_status = header_idx.get("STATUS", None)
                if idx_status is None:
                    show_modern_warning(self, "Error", "Kolom STATUS tidak ditemukan di CSV.")
                    return

                # 🚀 Ambil koneksi global
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("PRAGMA busy_timeout = 8000")
                cur.execute("PRAGMA synchronous = OFF")
                cur.execute("PRAGMA temp_store = 2")
                cur.execute("PRAGMA journal_mode = WAL")

                # ✅ Pastikan tabel ada
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {tbl_name} (
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
                        LastUpdate TEXT,
                        CEK_DATA TEXT
                    )
                """)

                # === Siapkan batch super cepat ===
                from datetime import datetime
                batch_values = []

                for row in reader[1:]:
                    if not row or len(row) < len(header):
                        continue
                    status_val = row[idx_status].strip().upper()
                    if status_val not in ("AKTIF", "UBAH", "BARU"):
                        continue

                    values = []
                    for csv_col, app_col in mapping.items():
                        if csv_col in header_idx:
                            val = row[header_idx[csv_col]].strip()
                            if app_col == "KET":
                                val = "0"
                            if app_col == "LastUpdate" and val:
                                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                                    try:
                                        val = datetime.strptime(val, fmt).strftime("%d/%m/%Y")
                                        break
                                    except Exception:
                                        pass
                            values.append(val)
                    batch_values.append(tuple(values))

                if not batch_values:
                    show_modern_warning(self, "Kosong", "Tidak ada data aktif untuk diimport.")
                    return

                # === Eksekusi ultra cepat ===
                cur.execute(f"DELETE FROM {tbl_name}")
                placeholders = ",".join(["?"] * len(mapping))
                cur.executemany(
                    f"INSERT INTO {tbl_name} ({','.join(mapping.values())}) VALUES ({placeholders})",
                    batch_values
                )
                cur.execute(f"UPDATE {tbl_name} SET KET='0'")
                conn.commit()

                # === Cek isi tabel setelah commit ===
                cur.execute(f"SELECT COUNT(*) FROM {tbl_name}")
                total = cur.fetchone()[0]
                #print(f"[DEBUG] Jumlah baris di tabel {tbl_name.upper()}: {total}")

                # === Refresh tampilan (tanpa flicker, tanpa event) ===
                try:
                    with self.freeze_ui():  # 🧊 mirip EnableEvents=False + ScreenUpdating=False
                        self.load_data_from_db()
                        self.update_pagination()
                        self.show_page(1)
                        self.connect_header_events()
                        self.sort_data(auto=True)
                        self.filter_sidebar._populate_sumber_from_mainwindow()

                    show_modern_info(
                        self, "Sukses",
                        f"Import CSV ke tabel {tbl_name.upper()} selesai!\n"
                        f"{len(batch_values)} baris berhasil dimuat."
                    )

                except Exception as e:
                    show_modern_error(
                        self, "Error",
                        f"Data tersimpan tapi gagal dimuat ke tabel:\n{e}"
                    )

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal import CSV:\n{e}")


    @with_safe_db
    def load_data_from_db(self, conn=None):
        """Memuat seluruh data dari tabel aktif ke self.all_data (SQLCipher-safe)."""
        self._ensure_schema_and_migrate()

        conn = get_connection()
        conn.row_factory = sqlcipher.Row
        cur = conn.cursor()

        tbl_name = self._active_table()  # ✅ gunakan tabel aktif langsung

        # Optimasi baca
        cur.executescript("""
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;
            PRAGMA temp_store = MEMORY;
            PRAGMA cache_size = 100000;
        """)

        try:
            cur.execute(f"SELECT rowid, * FROM {tbl_name}")
            rows = cur.fetchall()
            #print(f"[DEBUG] load_data_from_db: {len(rows)} baris dimuat dari {tbl_name}")
        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memuat data dari tabel {tbl_name}:\n{e}")
            self.all_data = []
            self.show_page(1)
            return

        if not rows:
            self.all_data = []
            self.total_pages = 1
            self.show_page(1)
            return

        # Formatter tanggal
        _tgl_cache = {}
        def format_tgl(val):
            if not val:
                return ""
            if val in _tgl_cache:
                return _tgl_cache[val]
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    v = datetime.strptime(val, fmt).strftime("%d/%m/%Y")
                    _tgl_cache[val] = v
                    return v
                except Exception:
                    continue
            _tgl_cache[val] = val
            return val

        # List of dict
        headers = [col[1] for col in cur.execute(f"PRAGMA table_info({tbl_name})").fetchall()]
        all_data = []
        for r in rows:
            d = {c: ("" if r[c] is None else str(r[c])) for c in headers if c in r.keys()}
            d["rowid"] = r["rowid"]
            if "LastUpdate" in r.keys() and r["LastUpdate"]:
                d["LastUpdate"] = format_tgl(str(r["LastUpdate"]))
            all_data.append(d)

        self.all_data = all_data
        import gc; gc.collect()

        total = len(all_data)
        self.total_pages = max(1, (total + self.rows_per_page - 1) // self.rows_per_page)
        self.show_page(1)

        # Terapkan warna otomatis
        def apply_colors_safely():
            try:
                if not hasattr(self, "_warna_sudah_dihitung") or not self._warna_sudah_dihitung:
                    self._warnai_baris_berdasarkan_ket()
                    self._warna_sudah_dihitung = True
                self._terapkan_warna_ke_tabel_aktif()
            except Exception as e:
                print(f"[WARN] Gagal menerapkan warna otomatis: {e}")

        QTimer.singleShot(100, apply_colors_safely)

    @contextmanager
    def freeze_ui(self):
        """Bekukan event & tampilan GUI sementara (seperti EnableEvents=False + ScreenUpdating=False)."""
        try:
            self.setUpdatesEnabled(False)
            self.table.blockSignals(True)
            yield
        finally:
            self.table.blockSignals(False)
            self.setUpdatesEnabled(True)
            self.repaint()


    @with_safe_db
    def _ensure_schema_and_migrate(self, conn=None):
        """Pastikan tabel aktif eksis dan skemanya sesuai."""
        conn = get_connection()
        cur = conn.cursor()

        tbl_name = self._active_table()  # ✅ gunakan tabel aktif

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_name} (
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

        cur.execute(f"PRAGMA table_info({tbl_name})")
        cols = {row[1] for row in cur.fetchall()}

        if "CEK_DATA" not in cols:
            cur.execute(f"ALTER TABLE {tbl_name} ADD COLUMN CEK_DATA TEXT")
        if "CEK DATA" in cols:
            cur.execute(f"UPDATE {tbl_name} SET CEK_DATA = COALESCE(CEK_DATA, `CEK DATA`)")
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
        Urutkan data seluruh halaman (super cepat, prioritas 3 saja):
        🔹 Urut berdasarkan TPS, RW, RT, NKK, NAMA
        Tanpa popup konfirmasi atau notifikasi.
        """

        # 🔹 Fungsi kunci sortir sederhana
        def kunci_sortir(d):
            return (
                str(d.get("TPS", "")),
                str(d.get("RW", "")),
                str(d.get("RT", "")),
                str(d.get("NKK", "")),
                str(d.get("NAMA", "")),
            )

        # 🔹 Jalankan pengurutan
        self.all_data.sort(key=kunci_sortir)

        # 🔹 Refresh tampilan tabel ke halaman pertama
        self.show_page(1)

        # 🔹 Terapkan ulang warna tabel (non-blocking)
        QTimer.singleShot(100, lambda: self._terapkan_warna_ke_tabel_aktif())


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

    def load_theme(self):
        return "light"

    # =================================================
    # Hapus Seluruh Data Pemilih (sub-menu Help)
    # =================================================
    def hapus_data_pemilih(self):
        """
        🧹 Menghapus seluruh isi tabel aktif (sesuai tahapan saat ini) dengan aman.
        SQLCipher-safe.
        """
        # 🔸 Konfirmasi pengguna
        if not show_modern_question(
            self,
            "Konfirmasi",
            (
                "Apakah Anda yakin ingin menghapus <b>SELURUH data</b> di tabel aktif ini?<br>"
                "Tindakan ini <b>tidak dapat dibatalkan!</b>"
            )
        ):
            show_modern_info(self, "Dibatalkan", "Proses penghapusan data dibatalkan.")
            return

        # 🔹 Langkah awal: pastikan semua data tampil (jangan dalam keadaan terfilter)
        try:
            with self.freeze_ui():  # 🧊 sama seperti Application.EnableEvents = False
                self.reset_tampilkan_semua_data(silent=True)
        except Exception as e:
            print(f"[Warning] Gagal reset tampilan sebelum hapus: {e}")

        try:
            # 🔸 Koneksi aman ke database terenkripsi
            conn = get_connection()
            cur = conn.cursor()

            # 🔸 Ambil nama tabel aktif (otomatis tergantung tahapan)
            tbl = self._active_table()  # contoh: 'dphp', 'dpshp', atau 'dpshpa'

            # 🔸 Hapus seluruh data di tabel aktif
            cur.execute(f"DELETE FROM {tbl}")
            conn.commit()

            # 🔸 Kosongkan data di memori dan tabel GUI
            self.all_data.clear()
            self.table.setRowCount(0)

            # 🔸 Reset label status
            if hasattr(self, "lbl_total"):
                self.lbl_total.setText("0 total")
            if hasattr(self, "lbl_selected"):
                self.lbl_selected.setText("0 selected")

            # 🔸 Reset pagination
            self.total_pages = 1
            self.current_page = 1
            if hasattr(self, "update_pagination"):
                self.update_pagination()
            if hasattr(self, "show_page"):
                self.show_page(1)

            # 🔸 Refresh Dashboard (kalau sedang di dashboard)
            if hasattr(self, "refresh_dashboard_on_show"):
                try:
                    self.refresh_dashboard_on_show()
                except Exception as e:
                    print(f"[Dashboard Refresh Error after delete] {e}")

            # 🔸 Notifikasi sukses
            show_modern_info(
                self,
                "Selesai",
                f"Seluruh data telah dihapus dari tabel <b>{tbl}</b>!"
            )

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal menghapus data:\n{e}")

    def _refresh_table_with_new_data(self, new_data: list[dict]):
        """Memperbarui tabel dan pagination setelah self.all_data diganti."""
        import math
        self.all_data = new_data
        self.total_pages = max(1, math.ceil(len(new_data) / self.rows_per_page))
        self.current_page = 1
        self.update_pagination()
        self.show_page(1)
            
    # =================================================
    # Tampilkan Data tabel dari database
    # =================================================
    def show_page(self, page):
        if not hasattr(self, "table") or self.table is None:
            print("[WARN] Table belum dibuat, show_page dibatalkan sementara.")
            return

        if page < 1 or page > self.total_pages:
            return

        self.current_page = page
        self.table.blockSignals(True)
        old_overlay = getattr(self, "_empty_overlay", None)
        if old_overlay:
            old_overlay.deleteLater()
            self._empty_overlay = None

        start = (page - 1) * self.rows_per_page
        end = min(start + self.rows_per_page, len(self.all_data))
        data_rows = self.all_data[start:end]
        #print(f"[DEBUG] Menampilkan {len(data_rows)} baris dari index {start}–{end}")

        # =========================================================
        # 🧹 Clear isi lama tanpa reset struktur tabel
        # =========================================================
        self.table.clearContents()
        self.table.setRowCount(len(data_rows))

        # =========================================================
        # 🚫 Jika kosong, tampilkan pesan
        # =========================================================
        if not data_rows:
            self.table.setRowCount(0)

            # Hapus overlay lama jika ada
            old_overlay = getattr(self, "_empty_overlay", None)
            if old_overlay:
                old_overlay.deleteLater()
                self._empty_overlay = None

            # Buat label overlay di tengah viewport tabel
            overlay = QLabel("Tidak Ada Data Yang Ditampilkan", self.table.viewport())
            overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            overlay.setStyleSheet("""
                color: gray;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-style: italic;
                font-weight: bold;
                background: transparent;
            """)
            overlay.resize(self.table.viewport().size())
            overlay.show()
            self._empty_overlay = overlay

            # Pastikan overlay ikut event resize
            self.table.viewport().installEventFilter(self)

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

        # =========================================================
        # 🎨 Mapping warna super kilat
        # =========================================================
        warna_map = {
            "B": QColor("green"),   # BARU
            "U": QColor("orange"),  # UBAH
        }
        tms_vals = {"1", "2", "3", "4", "5", "6", "7", "8"}  # TMS
        warna_default = QColor("black")

        # 🔵 Daftar KET yang membuat font biru
        ket_biru_vals = {
            "NKK INVALID", "POTENSI NKK INVALID",
            "NIK INVALID", "POTENSI NIK INVALID",
            "POTENSI DIBAWAH UMUR", "DIBAWAH UMUR",
            "GANDA AKTIF", "BEDA TPS", "TIDAK PADAN"
        }

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

                # 👉 Set flag lengkap SEBELUM dimasukkan ke tabel
                cell.setFlags(
                    Qt.ItemFlag.ItemIsEnabled |
                    Qt.ItemFlag.ItemIsSelectable
                )

                # Alignment & warna default
                if col in center_cols:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setForeground(QColor("#000000"))

                # Masukkan ke tabel
                setItem(i, j, cell)

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
        self.table.setEnabled(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setFocus()
        self.table.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.table.viewport().update()
        self.table.repaint()

        # Setelah isi tabel selesai dibuat, langsung terapkan warna hasil cache
        try:
            self._terapkan_warna_ke_tabel_aktif()
        except Exception as e:
            print(f"[WARN] Gagal menerapkan warna otomatis di show_page: {e}")

    # =========================================================
    # 🔹 CEK REKAP PEMILIH AKTIF (MENU → Rekap → Pemilih Aktif)
    # =========================================================
    def cek_rekapaktif(self):
        """Menampilkan rekap pemilih aktif per TPS (maximize window)."""
        try:
            from db_manager import get_connection

            tbl_name = self._active_table()
            conn = get_connection()
            cur = conn.cursor()

            # 🔹 Pastikan tabel rekap ada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rekap (
                    "NAMA TPS" TEXT,
                    "JUMLAH KK" INTEGER,
                    "LAKI-LAKI" INTEGER,
                    "PEREMPUAN" INTEGER,
                    "JUMLAH" INTEGER
                )
            """)
            cur.execute("DELETE FROM rekap")

            # 🔹 Ambil distinct TPS (abaikan KET 1–8)
            cur.execute(f"""
                SELECT DISTINCT TPS FROM {tbl_name}
                WHERE COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                ORDER BY CAST(TPS AS INTEGER)
            """)
            tps_list = [r[0] for r in cur.fetchall() if r[0]]

            # 🔹 Isi data rekap per TPS
            for tps in tps_list:
                nama_tps = f"TPS {int(tps):03d}"

                cur.execute(f"""
                    SELECT COUNT(DISTINCT NKK)
                    FROM {tbl_name}
                    WHERE TPS=? AND COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                nkk = cur.fetchone()[0] or 0

                cur.execute(f"""
                    SELECT COUNT(*) FROM {tbl_name}
                    WHERE TPS=? AND JK='L' AND COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                jml_L = cur.fetchone()[0] or 0

                cur.execute(f"""
                    SELECT COUNT(*) FROM {tbl_name}
                    WHERE TPS=? AND JK='P' AND COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                jml_P = cur.fetchone()[0] or 0

                total = jml_L + jml_P
                cur.execute("INSERT INTO rekap VALUES (?, ?, ?, ?, ?)", (nama_tps, nkk, jml_L, jml_P, total))

            conn.commit()

            # 🔹 Sembunyikan MainWindow dan tampilkan jendela rekap
            self.rekap_window = self.show_window_with_transition(RekapWindow)

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal membuka Rekap Aktif:\n{e}")

    def cek_rekapbaru(self):
        """Menampilkan rekap pemilih baru per TPS (maximize window)."""
        try:
            from db_manager import get_connection

            tbl_name = self._active_table()
            conn = get_connection()
            cur = conn.cursor()

            # 🔹 Pastikan tabel baru ada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS baru (
                    "NAMA TPS" TEXT,
                    "JUMLAH KK" INTEGER,
                    "LAKI-LAKI" INTEGER,
                    "PEREMPUAN" INTEGER,
                    "JUMLAH" INTEGER
                )
            """)
            cur.execute("DELETE FROM baru")

            # 🔹 Ambil distinct TPS (abaikan KET 1–8)
            cur.execute(f"""
                SELECT DISTINCT TPS FROM {tbl_name}
                WHERE COALESCE(KET,'') IN ('b')
                ORDER BY CAST(TPS AS INTEGER)
            """)
            tps_list = [r[0] for r in cur.fetchall() if r[0]]

            # 🔹 Isi data rekap per TPS
            for tps in tps_list:
                nama_tps = f"TPS {int(tps):03d}"

                cur.execute(f"""
                    SELECT COUNT(DISTINCT NKK)
                    FROM {tbl_name}
                    WHERE TPS=? AND COALESCE(KET,'') IN ('b')
                """, (tps,))
                nkk = cur.fetchone()[0] or 0

                cur.execute(f"""
                    SELECT COUNT(*) FROM {tbl_name}
                    WHERE TPS=? AND JK='L' AND COALESCE(KET,'') IN ('b')
                """, (tps,))
                jml_L = cur.fetchone()[0] or 0

                cur.execute(f"""
                    SELECT COUNT(*) FROM {tbl_name}
                    WHERE TPS=? AND JK='P' AND COALESCE(KET,'') IN ('b')
                """, (tps,))
                jml_P = cur.fetchone()[0] or 0

                total = jml_L + jml_P
                cur.execute("INSERT INTO rekap VALUES (?, ?, ?, ?, ?)", (nama_tps, nkk, jml_L, jml_P, total))

            conn.commit()

            # 🔹 Sembunyikan MainWindow dan tampilkan jendela rekap
            self.baru_window = self.show_window_with_transition(BaruWindow)

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal membuka Rekap Baru:\n{e}")


    def cek_rekapubah(self):
        """Menampilkan rekap pemilih ubah per TPS (maximize window)."""
        try:
            from db_manager import get_connection

            tbl_name = self._active_table()
            conn = get_connection()
            cur = conn.cursor()

            # 🔹 Pastikan tabel ubah ada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ubah (
                    "NAMA TPS" TEXT,
                    "JUMLAH KK" INTEGER,
                    "LAKI-LAKI" INTEGER,
                    "PEREMPUAN" INTEGER,
                    "JUMLAH" INTEGER
                )
            """)
            cur.execute("DELETE FROM ubah")

            # 🔹 Ambil distinct TPS (abaikan KET 1–8)
            cur.execute(f"""
                SELECT DISTINCT TPS FROM {tbl_name}
                WHERE COALESCE(KET,'') IN ('b')
                ORDER BY CAST(TPS AS INTEGER)
            """)
            tps_list = [r[0] for r in cur.fetchall() if r[0]]

            # 🔹 Isi data rekap ubah per TPS
            for tps in tps_list:
                nama_tps = f"TPS {int(tps):03d}"

                cur.execute(f"""
                    SELECT COUNT(DISTINCT NKK)
                    FROM {tbl_name}
                    WHERE TPS=? AND COALESCE(KET,'') IN ('u')
                """, (tps,))
                nkk = cur.fetchone()[0] or 0

                cur.execute(f"""
                    SELECT COUNT(*) FROM {tbl_name}
                    WHERE TPS=? AND JK='L' AND COALESCE(KET,'') IN ('u')
                """, (tps,))
                jml_L = cur.fetchone()[0] or 0

                cur.execute(f"""
                    SELECT COUNT(*) FROM {tbl_name}
                    WHERE TPS=? AND JK='P' AND COALESCE(KET,'') IN ('u')
                """, (tps,))
                jml_P = cur.fetchone()[0] or 0

                total = jml_L + jml_P
                cur.execute("INSERT INTO rekap VALUES (?, ?, ?, ?, ?)", (nama_tps, nkk, jml_L, jml_P, total))

            conn.commit()

            # 🔹 Sembunyikan MainWindow dan tampilkan jendela rekap
            self.ubah_window = self.show_window_with_transition(UbahWindow)

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal membuka Rekap Ubah Data:\n{e}")

    def cek_rekaptms(self):
        """Menampilkan rekap pemilih TMS per TPS (maximize window)."""
        try:
            from db_manager import get_connection

            tbl_name = self._active_table()
            conn = get_connection()
            cur = conn.cursor()

            # 🔹 Pastikan tabel TMS ada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS saring (
                    "NAMA TPS" TEXT,
                    "1L" INTEGER, "1P" INTEGER,
                    "2L" INTEGER, "2P" INTEGER,
                    "3L" INTEGER, "3P" INTEGER,
                    "4L" INTEGER, "4P" INTEGER,
                    "5L" INTEGER, "5P" INTEGER,
                    "6L" INTEGER, "6P" INTEGER,
                    "7L" INTEGER, "7P" INTEGER,
                    "8L" INTEGER, "8P" INTEGER,
                    "TMS L" INTEGER, "TMS P" INTEGER,
                    "JUMLAH" INTEGER
                )
            """)
            cur.execute("DELETE FROM saring")

            # 🔹 Ambil distinct TPS
            cur.execute(f"""
                SELECT DISTINCT TPS FROM {tbl_name}
                WHERE COALESCE(KET,'') IN ('1','2','3','4','5','6','7','8')
                ORDER BY CAST(TPS AS INTEGER)
            """)
            tps_list = [r[0] for r in cur.fetchall() if r[0]]

            # 🔹 Isi data rekap per TPS
            for tps in tps_list:
                nama_tps = f"TPS {int(tps):03d}"

                # Hitung masing-masing kategori (1–8)
                counts = {}
                for ket in range(1, 9):
                    for jk in ('L', 'P'):
                        cur.execute(f"""
                            SELECT COUNT(*) FROM {tbl_name}
                            WHERE TPS=? AND JK=? AND COALESCE(KET,'')=?
                        """, (tps, jk, str(ket)))
                        counts[f"{ket}{jk}"] = cur.fetchone()[0] or 0

                # Hitung total TMS per jenis kelamin
                cur.execute(f"""
                    SELECT COUNT(*) FROM {tbl_name}
                    WHERE TPS=? AND JK='L' AND COALESCE(KET,'') IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                TMS_L = cur.fetchone()[0] or 0

                cur.execute(f"""
                    SELECT COUNT(*) FROM {tbl_name}
                    WHERE TPS=? AND JK='P' AND COALESCE(KET,'') IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                TMS_P = cur.fetchone()[0] or 0

                total = TMS_L + TMS_P

                # Simpan ke tabel saring (20 kolom)
                cur.execute("""
                    INSERT INTO saring VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    nama_tps,
                    counts["1L"], counts["1P"],
                    counts["2L"], counts["2P"],
                    counts["3L"], counts["3P"],
                    counts["4L"], counts["4P"],
                    counts["5L"], counts["5P"],
                    counts["6L"], counts["6P"],
                    counts["7L"], counts["7P"],
                    counts["8L"], counts["8P"],
                    TMS_L, TMS_P, total
                ))

            conn.commit()

            # 🔹 Sembunyikan MainWindow dan tampilkan jendela SARING
            self.saring_window = self.show_window_with_transition(SaringWindow)

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal membuka Rekap TMS:\n{e}")

    def cek_rekapktp(self):
        """Menampilkan rekap pemilih KTPel per TPS (maximize window)."""
        try:
            from db_manager import get_connection

            tbl_name = self._active_table()
            conn = get_connection()
            cur = conn.cursor()

            # 🔹 Pastikan tabel ktpel ada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ktpel (
                    "NAMA TPS" TEXT,
                    "JUMLAH KK" INTEGER,
                    "LAKI-LAKI" INTEGER,
                    "PEREMPUAN" INTEGER,
                    "JUMLAH" INTEGER
                )
            """)
            cur.execute("DELETE FROM ktpel")

            # 🔹 Ambil distinct TPS (abaikan KET 1–8, hanya KTPel='b')
            cur.execute(f"""
                SELECT DISTINCT TPS FROM {tbl_name}
                WHERE COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                AND LOWER(COALESCE(KTPel,'')) = 'b'
                ORDER BY CAST(TPS AS INTEGER)
            """)
            tps_list = [r[0] for r in cur.fetchall() if r[0]]

            # 🔹 Isi data rekap per TPS
            for tps in tps_list:
                nama_tps = f"TPS {int(tps):03d}"

                # Hitung jumlah KK unik
                cur.execute(f"""
                    SELECT COUNT(DISTINCT NKK)
                    FROM {tbl_name}
                    WHERE TPS=?
                    AND LOWER(COALESCE(KTPel,''))='b'
                    AND COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                nkk = cur.fetchone()[0] or 0

                # Laki-laki
                cur.execute(f"""
                    SELECT COUNT(*)
                    FROM {tbl_name}
                    WHERE TPS=? AND JK='L'
                    AND LOWER(COALESCE(KTPel,''))='b'
                    AND COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                jml_L = cur.fetchone()[0] or 0

                # Perempuan
                cur.execute(f"""
                    SELECT COUNT(*)
                    FROM {tbl_name}
                    WHERE TPS=? AND JK='P'
                    AND LOWER(COALESCE(KTPel,''))='b'
                    AND COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                jml_P = cur.fetchone()[0] or 0

                total = jml_L + jml_P

                # Simpan ke tabel hasil
                cur.execute("INSERT INTO ktpel VALUES (?, ?, ?, ?, ?)",
                            (nama_tps, nkk, jml_L, jml_P, total))

            conn.commit()

            # 🔹 Sembunyikan MainWindow dan tampilkan jendela KTPel
            self.ktp_window = self.show_window_with_transition(KtpWindow)

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal membuka Rekap Pemilih KTPel:\n{e}")

    def cek_rekapdifabel(self):
        """Menampilkan rekap pemilih Disabilitas per TPS (maximize window)."""
        try:
            from db_manager import get_connection

            tbl_name = self._active_table()
            conn = get_connection()
            cur = conn.cursor()

            # 🔹 Pastikan tabel difabel ada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS difabel (
                    "NAMA TPS" TEXT,
                    "JUMLAH KK" INTEGER,
                    "FISIK" INTEGER,
                    "INTELEKTUAL" INTEGER,
                    "MENTAL" INTEGER,
                    "DIF. WICARA" INTEGER,
                    "DIF. RUNGU" INTEGER,
                    "DIF. NETRA" INTEGER,
                    "JUMLAH" INTEGER
                )
            """)
            cur.execute("DELETE FROM difabel")

            # 🔹 Ambil distinct TPS (hanya DIS = 1–6, abaikan KET 1–8)
            cur.execute(f"""
                SELECT DISTINCT TPS FROM {tbl_name}
                WHERE COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                AND COALESCE(DIS,'') IN ('1','2','3','4','5','6')
                ORDER BY CAST(TPS AS INTEGER)
            """)
            tps_list = [r[0] for r in cur.fetchall() if r[0]]

            # 🔹 Isi data rekap difabel per TPS
            for tps in tps_list:
                nama_tps = f"TPS {int(tps):03d}"

                # Jumlah KK unik
                cur.execute(f"""
                    SELECT COUNT(DISTINCT NKK)
                    FROM {tbl_name}
                    WHERE TPS=? 
                    AND COALESCE(DIS,'') IN ('1','2','3','4','5','6')
                    AND COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                """, (tps,))
                nkk = cur.fetchone()[0] or 0

                # Disabilitas kategori
                def hitung_dis(kode):
                    cur.execute(f"""
                        SELECT COUNT(*)
                        FROM {tbl_name}
                        WHERE TPS=? 
                        AND COALESCE(DIS,'') = ?
                        AND COALESCE(KET,'') NOT IN ('1','2','3','4','5','6','7','8')
                    """, (tps, kode))
                    return cur.fetchone()[0] or 0

                DIS_FIS = hitung_dis('1')
                DIS_INT = hitung_dis('2')
                DIS_MEN = hitung_dis('3')
                DIS_WIC = hitung_dis('4')
                DIS_RUN = hitung_dis('5')
                DIS_NET = hitung_dis('6')

                total = DIS_FIS + DIS_INT + DIS_MEN + DIS_WIC + DIS_RUN + DIS_NET

                # Simpan hasil
                cur.execute("""
                    INSERT INTO difabel VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nama_tps, nkk, DIS_FIS, DIS_INT, DIS_MEN, DIS_WIC, DIS_RUN, DIS_NET, total))

            conn.commit()

            # 🔹 Sembunyikan MainWindow dan tampilkan jendela difabel
            self.difabel_window = self.show_window_with_transition(DifabelWindow)

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal membuka Rekap Pemilih Disabilitas:\n{e}")

    def show_window_with_transition(self, window_class, delay_hide=150):
        """
        Menampilkan window baru (top-level) dengan efek transisi halus.
        ✅ Icon aplikasi tetap muncul di taskbar
        ✅ Data kecamatan/desa tetap terbaca
        ✅ Fade-in cepat
        """
        try:
            QTimer.singleShot(delay_hide, self.hide)

            # 🟢 Buat instance window baru, kirim self sebagai argumen manual
            new_window = window_class(self)

            # 🟢 Pastikan icon muncul di taskbar
            icon_path = os.path.join(os.path.dirname(__file__), "KPU.png")
            if os.path.exists(icon_path):
                new_window.setWindowIcon(QIcon(icon_path))
            new_window.setWindowFlags(
                Qt.WindowType.Window |
                Qt.WindowType.CustomizeWindowHint |
                Qt.WindowType.WindowTitleHint |
                Qt.WindowType.WindowMinMaxButtonsHint |
                Qt.WindowType.WindowCloseButtonHint
            )

            # Fade-in animasi
            effect = QGraphicsOpacityEffect(new_window)
            new_window.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(120)
            anim.setStartValue(0)
            anim.setEndValue(1)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            new_window._fade_anim = anim

            new_window.showMaximized()
            self._active_child_window = new_window

            return new_window
        except Exception as e:
            print(f"[UI ERROR] Gagal transisi window: {e}")


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
                border: 1px solid #aaa;
                border-radius: 6px;
                background-color: #ffffff;
                color: #000000;              /* 🟢 teks hitam */
            }
            QPushButton:checked {
                border: 2px solid #ffa047;
                font-weight: bold;
                background-color: #fff8ee;   /* 🟠 highlight lembut */
                color: #000000;
            }
            QPushButton:disabled {
                color: #999999;              /* abu untuk tombol tak aktif */
                border: 1px solid #ddd;
                background-color: #f5f5f5;
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

    def _install_safe_shutdown_hooks(self):
        """Pasang hook aman agar database dan koneksi tertutup dengan benar saat keluar."""
        import atexit, signal
        from db_manager import close_connection

        # Pastikan flag & pointer ada
        if not hasattr(self, "_in_batch_mode"):
            self._in_batch_mode = False
        self._shared_conn = getattr(self, "_shared_conn", None)
        self._shared_cur  = getattr(self, "_shared_cur", None)

        # === Qt aboutToQuit ===
        app = QApplication.instance()
        if app:
            try:
                app.aboutToQuit.disconnect()
            except Exception:
                pass
            app.aboutToQuit.connect(lambda: self._shutdown("aboutToQuit"))

        # === Atexit fallback ===
        try:
            atexit.unregister(lambda: self._shutdown("atexit"))
        except Exception:
            pass
        atexit.register(lambda: self._shutdown("atexit"))

        # === Signal OS (Windows hanya SIGTERM yang efektif) ===
        try:
            signal.signal(signal.SIGINT,  lambda s, f: self._shutdown("SIGINT"))
            signal.signal(signal.SIGTERM, lambda s, f: self._shutdown("SIGTERM"))
        except Exception:
            pass

        print("[HOOK] Safe shutdown hooks NexVo aktif ✅")

    def _graceful_terminate(self, source):
        """Commit + tutup koneksi SQLCipher dengan aman lalu keluar rapi."""
        try:
            self._shutdown(source)
        finally:
            try:
                from db_manager import close_connection
                close_connection()
            except Exception as e:
                print(f"[WARN] Gagal close_connection saat exit: {e}")

            app = QApplication.instance()
            if app:
                app.quit()


    def closeEvent(self, event):
        """Pastikan semua perubahan batch disimpan dan koneksi ditutup bersih."""
        try:
            # 🟢 Commit semua transaksi batch (jika masih terbuka)
            self._flush_db("closeEvent")

            # 🔒 Tutup koneksi database global (dari db_manager)
            close_connection()

        except Exception as e:
            print(f"[WARN] closeEvent: {e}")

        # 🧹 Lanjutkan proses penutupan jendela normal
        super().closeEvent(event)



    def _flush_db(self, where=""):
        """
        Pastikan semua perubahan tersimpan sebelum keluar.
        - Commit transaksi batch (shared cursor) bila masih terbuka
        - Jangan pernah menutup koneksi SQLCipher global (shared)
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
                    self._shared_conn.commit()  # ✅ hanya commit, jangan close
                except Exception as e:
                    print(f"[WARN] Commit gagal di _flush_db({where}): {e}")

                try:
                    if getattr(self, "_shared_cur", None):
                        self._shared_cur.close()  # cursor boleh ditutup
                except Exception:
                    pass

                # Jangan tutup koneksi shared!
                self._shared_cur = None
                self._in_batch_mode = False

        except Exception as e:
            print(f"[WARN] _flush_db({where}) error: {e}", file=sys.stderr)


    def _shutdown(self, source: str = ""):
        """
        🧹 Prosedur shutdown aman (khusus full SQLCipher):
        - Menyimpan transaksi terakhir
        - Menutup koneksi global SQLCipher
        - Membersihkan artefak sementara
        """
        import os
        from db_manager import close_connection

        # 🔒 Pastikan tidak dijalankan dua kali
        if getattr(self, "_did_shutdown", False):
            return
        self._did_shutdown = True

        print(f"[INFO] Shutdown dipanggil dari {source or '(tidak diketahui)'}")

        # 1️⃣ Pastikan semua transaksi tersimpan
        try:
            if hasattr(self, "_flush_db"):
                self._flush_db(source or "_shutdown")
            print("[INFO] Transaksi terakhir tersimpan.")
        except Exception as e:
            print(f"[WARN] _flush_db({source}) gagal: {e}")

        # 2️⃣ Tutup koneksi SQLCipher utama
        try:
            close_connection()
            print("[INFO] Koneksi SQLCipher utama ditutup dengan aman.")
        except Exception as e:
            print(f"[WARN] Gagal menutup koneksi SQLCipher: {e}")

        # 3️⃣ Hapus artefak sementara (jika ada)
        try:
            db_path = getattr(self, "db_path", None) or getattr(self, "db_name", "")
            if db_path:
                folder = os.path.dirname(db_path)
                for name in os.listdir(folder):
                    if name.startswith("temp_") and name.endswith(".db"):
                        temp_file = os.path.join(folder, name)
                        os.remove(temp_file)
                        print(f"[INFO] Artefak sementara dihapus: {temp_file}")
        except Exception as e:
            print(f"[WARN] Gagal membersihkan file sementara: {e}")

        # 4️⃣ Konfirmasi shutdown selesai
        print("[INFO] Shutdown selesai (SQLCipher mode tunggal aktif). ✅\n")


    def _init_db_pragmas(self):
        """
        Terapkan PRAGMA untuk optimasi performa SQLCipher.
        Dipanggil di awal startup.
        """
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.executescript("""
                PRAGMA journal_mode = WAL;
                PRAGMA synchronous = NORMAL;
                PRAGMA temp_store = MEMORY;
                PRAGMA cache_size = 8000;
                PRAGMA busy_timeout = 4000;
                PRAGMA foreign_keys = ON;
            """)

            conn.commit()
            print("[INFO] PRAGMA SQLCipher diinisialisasi (WAL mode).")

        except Exception as e:
            print(f"[WARN] init_db_pragmas gagal: {e}", file=sys.stderr)

    def get_distinct_sumber(self):
        """Mengambil daftar DISTINCT SUMBER dari tabel aktif (SQLCipher)."""
        from db_manager import get_connection
        sumber_list = ["Sumber"]

        try:
            conn = get_connection()
            if conn is None:
                print("[get_distinct_sumber] Koneksi belum siap.")
                return sumber_list

            cur = conn.cursor()
            tbl = self._active_table()
            cur.execute(f"""
                SELECT DISTINCT SUMBER
                FROM {tbl}
                WHERE SUMBER IS NOT NULL AND TRIM(SUMBER) != ''
                ORDER BY SUMBER
            """)
            rows = cur.fetchall()
            sumber_list += [r[0] for r in rows if r[0]]

        except Exception as e:
            print(f"[MainWindow.get_distinct_sumber Error] {e}")

        finally:
            if 'conn' in locals():
                try:
                    conn.commit()
                except:
                    pass

        return sumber_list

    
    def create_filter_sidebar(self):
        """Membuat dan menempelkan Filter Sidebar di sisi kiri window."""
        self.filter_sidebar = FilterSidebar(self)

        # Hapus sidebar lama kalau ada
        if self.filter_dock:
            self.removeDockWidget(self.filter_dock)

        # Buat sidebar baru
        self.filter_sidebar = FilterSidebar(self)

        self.filter_dock = QDockWidget("Filter", self)
        self.filter_dock.setWidget(self.filter_sidebar)
        self.filter_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.filter_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.filter_dock.setFixedWidth(self.filter_sidebar._dock_width)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.filter_dock)


    def generate_berita_acara(self):
        """Fungsi utama untuk membuka jendela Berita Acara (versi super cepat & ringan)."""
        try:
            from db_manager import get_connection
            conn = get_connection()
            cur = conn.cursor()
            tbl = self._active_table()

            # ⚡ Gunakan satu query agregasi besar (lebih cepat dari 4 query terpisah)
            cur.execute(f"""
                SELECT
                    COUNT(DISTINCT TPS) AS jml_tps,
                    SUM(CASE WHEN JK='L' AND (KET NOT IN ('1','2','3','4','5','6','7','8') OR KET IS NULL) THEN 1 ELSE 0 END) AS jml_laki,
                    SUM(CASE WHEN JK='P' AND (KET NOT IN ('1','2','3','4','5','6','7','8') OR KET IS NULL) THEN 1 ELSE 0 END) AS jml_perempuan,
                    SUM(CASE WHEN (KET NOT IN ('1','2','3','4','5','6','7','8') OR KET IS NULL) THEN 1 ELSE 0 END) AS jml_total
                FROM {tbl};
            """)
            hasil = cur.fetchone() or (0, 0, 0, 0)
            conn.commit()

            # ⚡ Simpan ke atribut (akses cepat di class BeritaAcara)
            self._jumlah_tps, self._jumlah_laki, self._jumlah_perempuan, self._jumlah_pemilih = hasil

            # ⚡ Langsung buka jendela Berita Acara tanpa query tambahan
            self.berita_acara = self.show_window_with_transition(BeritaAcara)

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal membuka Berita Acara:\n{e}")

    def generate_adpp(self, tps_filter=None):
        """Ambil data ADPP dari database SQLCipher aktif secara real-time, super cepat, dan aman."""
        from db_manager import get_connection

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.executescript("""
                PRAGMA temp_store = MEMORY;
                PRAGMA cache_size = 200000;
            """)

            tbl = self._active_table()
            if not tbl:
                show_modern_error(self, "Error", "Tabel aktif tidak ditemukan.")
                return

            # 🔹 Query cepat sesuai filter TPS (jika ada)
            if tps_filter:
                cur.execute(f"""
                    SELECT NKK, NIK, NAMA, TMPT_LHR, TGL_LHR, STS, JK,
                        ALAMAT, RT, RW, DIS, KTPel, KET, TPS
                    FROM {tbl}
                    WHERE KET IS NOT NULL AND KET <> '0' AND TPS=?
                    ORDER BY RW, RT, NKK, NAMA;
                """, (tps_filter,))
            else:
                cur.execute(f"""
                    SELECT NKK, NIK, NAMA, TMPT_LHR, TGL_LHR, STS, JK,
                        ALAMAT, RT, RW, DIS, KTPel, KET, TPS
                    FROM {tbl}
                    WHERE KET IS NOT NULL AND KET <> '0'
                    ORDER BY TPS, RW, RT, NKK, NAMA;
                """)

            # 🔹 Batch fetch (super cepat)
            rows = []
            fetch = cur.fetchmany
            while True:
                batch = fetch(5000)
                if not batch:
                    break
                rows.extend(batch)

            conn.commit()
            self._adpp_data = rows
            print(f"[ADPP] Berhasil memuat {len(rows):,} baris data real-time ✅")

            # 🔹 Buka jendela PDF langsung
            self.show_window_with_transition(LampAdpp)

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal memuat data ADPP:\n{e}")


    def get_distinct_tps(self):
        """Ambil daftar distinct TPS dari tabel aktif, abaikan baris dengan KET=0."""
        try:
            conn = get_connection()
            cur = conn.cursor()
            tbl = self._active_table()

            cur.execute(f"""
                SELECT DISTINCT TPS FROM {tbl}
                WHERE (KET IS NULL OR KET <> '0')
                ORDER BY TPS ASC
            """)
            result = [str(r[0]) for r in cur.fetchall() if r[0] not in (None, "")]
            conn.commit()

            self._distinct_tps_list = result or ["-"]
            self._current_tps_index = 0
            print(f"[TPS List] Ditemukan {len(result)} TPS aktif: {result}")
            return result
        except Exception as e:
            print(f"[TPS Error] {e}")
            return []


# =========================================================
# 🔹 KELAS TAMPILAN REKAP
# =========================================================
class RekapWindow(QMainWindow):
    def __init__(self, parent_window):
        super().__init__()  # tidak pakai parent Qt

        self.parent_window = parent_window  # simpan referensi manual
        self.setWindowTitle("Rekap Pemilih Aktif")
        self.setStyleSheet("background-color: #ffffff;")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        self.setCentralWidget(central)

        # =========================================================
        # 🧭 Ambil info dari parent_window
        # =========================================================
        nama_user = getattr(parent_window, "_nama", "PENGGUNA").upper()
        tahap = getattr(parent_window, "_tahapan", "DPHP").upper()
        kecamatan = getattr(parent_window, "_kecamatan", "").upper()
        desa = getattr(parent_window, "_desa", "").upper()

        # =========================================================
        # 🧾 Tentukan teks tahapan
        # =========================================================
        if tahap == "DPHP":
            nama_tahapan = "DAFTAR PEMILIH HASIL PEMUTAKHIRAN PEMILU TAHUN 2029"
        elif tahap == "DPSHP":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN PEMILU TAHUN 2029"
        elif tahap == "DPSHPA":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN AKHIR PEMILU TAHUN 2029"
        else:
            nama_tahapan = "DAFTAR PEMILIH PEMILU TAHUN 2029"

        lokasi_str = f"KECAMATAN {kecamatan} DESA {desa}"

        # =========================================================
        # 🧍 Header User
        # =========================================================
        lbl_user = QLabel(nama_user)
        lbl_user.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Segoe UI", 11)
        font.setBold(True)             
        lbl_user.setFont(font)

        lbl_user.setStyleSheet("""
            color: #000000;
            border-bottom: 3px solid #ff6600;
            padding-bottom: 8px;
        """)

        layout.addWidget(lbl_user)

        # =========================================================
        # 🏷️ Judul utama (3 baris)
        # =========================================================
        judul_layout = QVBoxLayout()
        judul_layout.setSpacing(2)

        lbl1 = QLabel("REKAP PEMILIH AKTIF")
        lbl1.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl1.setStyleSheet("color: #000000;")

        lbl2 = QLabel(nama_tahapan)
        lbl2.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl2.setStyleSheet("color: #000000;")

        lbl3 = QLabel(lokasi_str)
        lbl3.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl3.setStyleSheet("color: #000000;")

        judul_layout.addWidget(lbl1)
        judul_layout.addWidget(lbl2)
        judul_layout.addWidget(lbl3)

        layout.addLayout(judul_layout)

        # =========================================================
        # 📋 Tabel rekap
        # =========================================================
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["NAMA TPS", "JUMLAH KK", "LAKI-LAKI", "PEREMPUAN", "JUMLAH"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                font-weight: bold;
                font-family: Segoe UI;
                font-size: 11pt;
                padding: 6px;
            }
            QTableWidget {
                gridline-color: #dddddd;
                background-color: white;
                alternate-background-color: #f6f6f6;
                color: #000000;
                font-size: 11pt;
                font-family: Segoe UI;
                selection-background-color: #d9d9d9;    /* ✅ abu lembut saat dipilih */
                selection-color: #000000;
            }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # === Ambil data dari tabel rekap ===
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM rekap ORDER BY CAST(substr(\"NAMA TPS\", 5) AS INTEGER)")
        rows = cur.fetchall()
        self.table.setRowCount(len(rows) + 1)  # +1 untuk total

        total_nkk = total_L = total_P = total_all = 0

        for i, row in enumerate(rows):
            nkk, L, P, total = row[1], row[2], row[3], row[4]
            total_nkk += nkk
            total_L += L
            total_P += P
            total_all += total

            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = item.font()
                if j in (0, 1, 2, 3, 4):
                    font.setBold(True)
                item.setFont(font)
                self.table.setItem(i, j, item)

        # === Baris total ===
        total_labels = ["TOTAL", str(total_nkk), str(total_L), str(total_P), str(total_all)]
        for j, val in enumerate(total_labels):
            item = QTableWidgetItem(val)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setBold(True)
            font.setPointSize(11)
            item.setFont(font)
            item.setBackground(QBrush(QColor("#B0AEAD")))  # abu lembut
            self.table.setItem(len(rows), j, item)

        layout.addWidget(self.table)

        # =========================================================
        # 🔸 Tombol Tutup
        # =========================================================
        btn_tutup = QPushButton("Tutup")
        btn_tutup.setFixedSize(120, 40)
        btn_tutup.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #d71d1d;
            }
        """)
        btn_tutup.clicked.connect(self.kembali_ke_main)
        layout.addWidget(btn_tutup, alignment=Qt.AlignmentFlag.AlignCenter)


    # === Fungsi kembali ke main window ===
    def kembali_ke_main(self):
        """Tutup jendela rekap dan tampilkan kembali MainWindow dengan tampilan normal."""
        if self.parent_window:
            self.parent_window.showNormal()
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            self.parent_window.repaint()
            QTimer.singleShot(150, self.parent_window.repaint)
        self.close()

class BaruWindow(QMainWindow):
    """Jendela maximize untuk rekap pemilih baru per TPS."""

    def __init__(self, parent_window):
        super().__init__()  # tidak pakai parent Qt

        self.parent_window = parent_window  # simpan referensi manual
        self.setWindowTitle("Rekap Pemilih Baru")
        self.setStyleSheet("background-color: #ffffff;")

        # === Layout utama ===
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        self.setCentralWidget(central)

        # =========================================================
        # 🧭 Ambil info dari parent_window
        # =========================================================
        nama_user = getattr(parent_window, "_nama", "PENGGUNA").upper()
        tahap = getattr(parent_window, "_tahapan", "DPHP").upper()
        kecamatan = getattr(parent_window, "_kecamatan", "").upper()
        desa = getattr(parent_window, "_desa", "").upper()

        # =========================================================
        # 🧾 Tentukan teks tahapan
        # =========================================================
        if tahap == "DPHP":
            nama_tahapan = "DAFTAR PEMILIH HASIL PEMUTAKHIRAN PEMILU TAHUN 2029"
        elif tahap == "DPSHP":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN PEMILU TAHUN 2029"
        elif tahap == "DPSHPA":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN AKHIR PEMILU TAHUN 2029"
        else:
            nama_tahapan = "DAFTAR PEMILIH PEMILU TAHUN 2029"

        lokasi_str = f"KECAMATAN {kecamatan} DESA {desa}"

        # =========================================================
        # 🧍 Header User
        # =========================================================
        lbl_user = QLabel(nama_user)
        lbl_user.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Segoe UI", 11)
        font.setBold(True)             
        lbl_user.setFont(font)

        lbl_user.setStyleSheet("""
            color: #000000;
            border-bottom: 3px solid #ff6600;
            padding-bottom: 8px;
        """)

        layout.addWidget(lbl_user)

        # =========================================================
        # 🏷️ Judul utama (3 baris)
        # =========================================================
        judul_layout = QVBoxLayout()
        judul_layout.setSpacing(2)

        lbl1 = QLabel("REKAP PEMILIH BARU")
        lbl1.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl1.setStyleSheet("color: #000000;")

        lbl2 = QLabel(nama_tahapan)
        lbl2.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl2.setStyleSheet("color: #000000;")

        lbl3 = QLabel(lokasi_str)
        lbl3.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl3.setStyleSheet("color: #000000;")

        judul_layout.addWidget(lbl1)
        judul_layout.addWidget(lbl2)
        judul_layout.addWidget(lbl3)

        layout.addLayout(judul_layout)

        # =========================================================
        # 📋 Tabel baru
        # =========================================================
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["NAMA TPS", "JUMLAH KK", "LAKI-LAKI", "PEREMPUAN", "JUMLAH"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                font-weight: bold;
                font-family: Segoe UI;
                font-size: 11pt;
                padding: 6px;
            }
            QTableWidget {
                gridline-color: #dddddd;
                background-color: white;
                alternate-background-color: #f6f6f6;
                color: #000000;
                font-size: 11pt;
                font-family: Segoe UI;
                selection-background-color: #d9d9d9;    /* ✅ abu lembut saat dipilih */
                selection-color: #000000;
            }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # === Ambil data dari tabel baru ===
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM baru ORDER BY CAST(substr(\"NAMA TPS\", 5) AS INTEGER)")
        rows = cur.fetchall()
        self.table.setRowCount(len(rows) + 1)  # +1 untuk total

        total_nkk = total_L = total_P = total_all = 0

        for i, row in enumerate(rows):
            nkk, L, P, total = row[1], row[2], row[3], row[4]
            total_nkk += nkk
            total_L += L
            total_P += P
            total_all += total

            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = item.font()
                if j in (0, 1, 2, 3, 4):
                    font.setBold(True)
                item.setFont(font)
                self.table.setItem(i, j, item)

        # === Baris total ===
        total_labels = ["TOTAL", str(total_nkk), str(total_L), str(total_P), str(total_all)]
        for j, val in enumerate(total_labels):
            item = QTableWidgetItem(val)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setBold(True)
            font.setPointSize(11)
            item.setFont(font)
            item.setBackground(QBrush(QColor("#B0AEAD")))  # abu lembut
            self.table.setItem(len(rows), j, item)

        layout.addWidget(self.table)

        # =========================================================
        # 🔸 Tombol Tutup
        # =========================================================
        btn_tutup = QPushButton("Tutup")
        btn_tutup.setFixedSize(120, 40)
        btn_tutup.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #d71d1d;
            }
        """)
        btn_tutup.clicked.connect(self.kembali_ke_main)
        layout.addWidget(btn_tutup, alignment=Qt.AlignmentFlag.AlignCenter)


    # === Fungsi kembali ke main window ===
    def kembali_ke_main(self):
        """Tutup jendela rekap dan tampilkan kembali MainWindow dengan tampilan normal."""
        if self.parent_window:
            self.parent_window.showNormal()
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            self.parent_window.repaint()
            QTimer.singleShot(150, self.parent_window.repaint)
        self.close()

class UbahWindow(QMainWindow):
    """Jendela maximize untuk rekap pemilih ubah per TPS."""

    def __init__(self, parent_window):
        super().__init__()  # tidak pakai parent Qt

        self.parent_window = parent_window  # simpan referensi manual
        self.setWindowTitle("Rekap Perubahan Data Pemilih")
        self.setStyleSheet("background-color: #ffffff;")

        # === Layout utama ===
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        self.setCentralWidget(central)

        # =========================================================
        # 🧭 Ambil info dari parent_window
        # =========================================================
        nama_user = getattr(parent_window, "_nama", "PENGGUNA").upper()
        tahap = getattr(parent_window, "_tahapan", "DPHP").upper()
        kecamatan = getattr(parent_window, "_kecamatan", "").upper()
        desa = getattr(parent_window, "_desa", "").upper()

        # =========================================================
        # 🧾 Tentukan teks tahapan
        # =========================================================
        if tahap == "DPHP":
            nama_tahapan = "DAFTAR PEMILIH HASIL PEMUTAKHIRAN PEMILU TAHUN 2029"
        elif tahap == "DPSHP":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN PEMILU TAHUN 2029"
        elif tahap == "DPSHPA":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN AKHIR PEMILU TAHUN 2029"
        else:
            nama_tahapan = "DAFTAR PEMILIH PEMILU TAHUN 2029"

        lokasi_str = f"KECAMATAN {kecamatan} DESA {desa}"

        # =========================================================
        # 🧍 Header User
        # =========================================================
        lbl_user = QLabel(nama_user)
        lbl_user.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Segoe UI", 11)
        font.setBold(True)             
        lbl_user.setFont(font)

        lbl_user.setStyleSheet("""
            color: #000000;
            border-bottom: 3px solid #ff6600;
            padding-bottom: 8px;
        """)

        layout.addWidget(lbl_user)

        # =========================================================
        # 🏷️ Judul utama (3 baris)
        # =========================================================
        judul_layout = QVBoxLayout()
        judul_layout.setSpacing(2)

        lbl1 = QLabel("REKAP PERUBAHAN DATA PEMILIH")
        lbl1.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl1.setStyleSheet("color: #000000;")

        lbl2 = QLabel(nama_tahapan)
        lbl2.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl2.setStyleSheet("color: #000000;")

        lbl3 = QLabel(lokasi_str)
        lbl3.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl3.setStyleSheet("color: #000000;")

        judul_layout.addWidget(lbl1)
        judul_layout.addWidget(lbl2)
        judul_layout.addWidget(lbl3)

        layout.addLayout(judul_layout)

        # =========================================================
        # 📋 Tabel UBAH
        # =========================================================
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["NAMA TPS", "JUMLAH KK", "LAKI-LAKI", "PEREMPUAN", "JUMLAH"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                font-weight: bold;
                font-family: Segoe UI;
                font-size: 11pt;
                padding: 6px;
            }
            QTableWidget {
                gridline-color: #dddddd;
                background-color: white;
                alternate-background-color: #f6f6f6;
                color: #000000;
                font-size: 11pt;
                font-family: Segoe UI;
                selection-background-color: #d9d9d9;    /* ✅ abu lembut saat dipilih */
                selection-color: #000000;
            }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # === Ambil data dari tabel ubah ===
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM ubah ORDER BY CAST(substr(\"NAMA TPS\", 5) AS INTEGER)")
        rows = cur.fetchall()
        self.table.setRowCount(len(rows) + 1)  # +1 untuk total

        total_nkk = total_L = total_P = total_all = 0

        for i, row in enumerate(rows):
            nkk, L, P, total = row[1], row[2], row[3], row[4]
            total_nkk += nkk
            total_L += L
            total_P += P
            total_all += total

            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = item.font()
                if j in (0, 1, 2, 3, 4):
                    font.setBold(True)
                item.setFont(font)
                self.table.setItem(i, j, item)

        # === Baris total ===
        total_labels = ["TOTAL", str(total_nkk), str(total_L), str(total_P), str(total_all)]
        for j, val in enumerate(total_labels):
            item = QTableWidgetItem(val)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setBold(True)
            font.setPointSize(11)
            item.setFont(font)
            item.setBackground(QBrush(QColor("#B0AEAD")))  # abu lembut
            self.table.setItem(len(rows), j, item)

        layout.addWidget(self.table)

        # =========================================================
        # 🔸 Tombol Tutup
        # =========================================================
        btn_tutup = QPushButton("Tutup")
        btn_tutup.setFixedSize(120, 40)
        btn_tutup.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #d71d1d;
            }
        """)
        btn_tutup.clicked.connect(self.kembali_ke_main)
        layout.addWidget(btn_tutup, alignment=Qt.AlignmentFlag.AlignCenter)


    # === Fungsi kembali ke main window ===
    def kembali_ke_main(self):
        """Tutup jendela rekap dan tampilkan kembali MainWindow dengan tampilan normal."""
        if self.parent_window:
            self.parent_window.showNormal()
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            self.parent_window.repaint()
            QTimer.singleShot(150, self.parent_window.repaint)
        self.close()

class SaringWindow(QMainWindow):
    """Jendela maximize untuk rekap pemilih TMS per TPS."""
    def __init__(self, parent_window):
        super().__init__()  # tidak pakai parent Qt

        self.parent_window = parent_window  # simpan referensi manual
        self.setWindowTitle("Rekap Pemilih TMS")
        self.setStyleSheet("background-color: #ffffff;")

        # === Layout utama ===
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        self.setCentralWidget(central)

        # =========================================================
        # 🧭 Ambil info dari parent_window
        # =========================================================
        nama_user = getattr(parent_window, "_nama", "PENGGUNA").upper()
        tahap = getattr(parent_window, "_tahapan", "DPHP").upper()
        kecamatan = getattr(parent_window, "_kecamatan", "").upper()
        desa = getattr(parent_window, "_desa", "").upper()

        if tahap == "DPHP":
            nama_tahapan = "DAFTAR PEMILIH HASIL PEMUTAKHIRAN PEMILU TAHUN 2029"
        elif tahap == "DPSHP":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN PEMILU TAHUN 2029"
        elif tahap == "DPSHPA":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN AKHIR PEMILU TAHUN 2029"
        else:
            nama_tahapan = "DAFTAR PEMILIH PEMILU TAHUN 2029"

        lokasi_str = f"KECAMATAN {kecamatan} DESA {desa}"

        lbl_user = QLabel(nama_user)
        lbl_user.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Segoe UI", 11)
        font.setBold(True)             
        lbl_user.setFont(font)

        lbl_user.setStyleSheet("""
            color: #000000;
            border-bottom: 3px solid #ff6600;
            padding-bottom: 8px;
        """)

        layout.addWidget(lbl_user)

        judul_layout = QVBoxLayout()
        judul_layout.setSpacing(2)
        for text, size, weight in [
            ("REKAP PEMILIH TIDAK MEMENUHI SYARAT (TMS)", 13, QFont.Weight.Bold),
            (nama_tahapan, 13, QFont.Weight.Bold),
            (lokasi_str, 13, QFont.Weight.Bold)
        ]:
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", size, weight))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #000000;" if size > 13 else "color: #000000;")
            judul_layout.addWidget(lbl)
        layout.addLayout(judul_layout)

        # === Tabel utama ===
        headers = [
            "NAMA TPS", "1L", "1P", "2L", "2P", "3L", "3P", "4L", "4P",
            "5L", "5P", "6L", "6P", "7L", "7P", "8L", "8P", "TMS L", "TMS P", "JUMLAH"
        ]
        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(19, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet("""
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                font-weight: bold;
                font-family: Segoe UI;
                font-size: 11pt;
                padding: 6px;
            }
            QTableWidget {
                gridline-color: #dddddd;
                background-color: white;
                alternate-background-color: #f6f6f6;
                color: #000000;
                font-size: 11pt;
                font-family: Segoe UI;
                selection-background-color: #d9d9d9;
                selection-color: #000000;
            }
        """)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM saring ORDER BY CAST(substr(\"NAMA TPS\", 5) AS INTEGER)")
        rows = cur.fetchall()
        self.table.setRowCount(len(rows) + 1)

        # === Hitung total setiap kolom ===
        num_cols = len(headers)
        col_totals = [0] * num_cols

        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                if j > 0:
                    try:
                        col_totals[j] += int(val or 0)
                    except ValueError:
                        pass
                item = QTableWidgetItem(str(val))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                self.table.setItem(i, j, item)

        # === Baris total ===
        total_labels = ["TOTAL"] + [str(col_totals[j]) for j in range(1, num_cols)]
        for j, val in enumerate(total_labels):
            item = QTableWidgetItem(val)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setBold(True)
            font.setPointSize(11)
            item.setFont(font)
            item.setBackground(QBrush(QColor("#B0AEAD")))
            self.table.setItem(len(rows), j, item)

        layout.addWidget(self.table)

        # === Tombol Tutup ===
        btn_tutup = QPushButton("Tutup")
        btn_tutup.setFixedSize(120, 40)
        btn_tutup.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #d71d1d; }
        """)
        btn_tutup.clicked.connect(self.kembali_ke_main)
        layout.addWidget(btn_tutup, alignment=Qt.AlignmentFlag.AlignCenter)

    def kembali_ke_main(self):
        """Kembalikan ke jendela utama."""
        if self.parent_window:
            self.parent_window.showNormal()
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            self.parent_window.repaint()
            QTimer.singleShot(150, self.parent_window.repaint)
        self.close()

class KtpWindow(QMainWindow):
    """Jendela maximize untuk rekap pemilih KTPel per TPS."""
    def __init__(self, parent_window):
        super().__init__()  # tidak pakai parent Qt

        self.parent_window = parent_window  # simpan referensi manual
        self.setWindowTitle("Rekap Pemilih KTPel")
        self.setStyleSheet("background-color: #ffffff;")

        # === Layout utama ===
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        self.setCentralWidget(central)

        # =========================================================
        # 🧭 Ambil info dari parent_window
        # =========================================================
        nama_user = getattr(parent_window, "_nama", "PENGGUNA").upper()
        tahap = getattr(parent_window, "_tahapan", "DPHP").upper()
        kecamatan = getattr(parent_window, "_kecamatan", "").upper()
        desa = getattr(parent_window, "_desa", "").upper()

        if tahap == "DPHP":
            nama_tahapan = "DAFTAR PEMILIH HASIL PEMUTAKHIRAN PEMILU TAHUN 2029"
        elif tahap == "DPSHP":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN PEMILU TAHUN 2029"
        elif tahap == "DPSHPA":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN AKHIR PEMILU TAHUN 2029"
        else:
            nama_tahapan = "DAFTAR PEMILIH PEMILU TAHUN 2029"

        lokasi_str = f"KECAMATAN {kecamatan} DESA {desa}"

        lbl_user = QLabel(nama_user)
        lbl_user.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Segoe UI", 11)
        font.setBold(True)             
        lbl_user.setFont(font)

        lbl_user.setStyleSheet("""
            color: #000000;
            border-bottom: 3px solid #ff6600;
            padding-bottom: 8px;
        """)

        layout.addWidget(lbl_user)

        judul_layout = QVBoxLayout()
        judul_layout.setSpacing(2)
        for text, size, weight in [
            ("REKAP PEMILIH NON KTP-EL", 13, QFont.Weight.Bold),
            (nama_tahapan, 13, QFont.Weight.Bold),
            (lokasi_str, 13, QFont.Weight.Bold)
        ]:
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", size, weight))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #000000;" if size > 13 else "color: #000000;")
            judul_layout.addWidget(lbl)
        layout.addLayout(judul_layout)

        # === Tabel utama ===
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["NAMA TPS", "JUMLAH KK", "LAKI-LAKI", "PEREMPUAN", "JUMLAH"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                font-weight: bold;
                font-family: Segoe UI;
                font-size: 11pt;
                padding: 6px;
            }
            QTableWidget {
                gridline-color: #dddddd;
                background-color: white;
                alternate-background-color: #f6f6f6;
                color: #000000;
                font-size: 11pt;
                font-family: Segoe UI;
                selection-background-color: #d9d9d9;    /* ✅ abu lembut saat dipilih */
                selection-color: #000000;
            }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # === Ambil data dari tabel ktpel ===
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM ktpel ORDER BY CAST(substr(\"NAMA TPS\", 5) AS INTEGER)")
        rows = cur.fetchall()
        self.table.setRowCount(len(rows) + 1)

        total_nkk = total_L = total_P = total_all = 0
        for i, row in enumerate(rows):
            nkk, L, P, total = row[1], row[2], row[3], row[4]
            total_nkk += nkk
            total_L += L
            total_P += P
            total_all += total

            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                self.table.setItem(i, j, item)

        # === Baris total ===
        total_labels = ["TOTAL", str(total_nkk), str(total_L), str(total_P), str(total_all)]
        for j, val in enumerate(total_labels):
            item = QTableWidgetItem(val)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setBold(True)
            font.setPointSize(11)
            item.setFont(font)
            item.setBackground(QBrush(QColor("#B0AEAD")))
            self.table.setItem(len(rows), j, item)

        layout.addWidget(self.table)

        # === Tombol Tutup ===
        btn_tutup = QPushButton("Tutup")
        btn_tutup.setFixedSize(120, 40)
        btn_tutup.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #d71d1d; }
        """)
        btn_tutup.clicked.connect(self.kembali_ke_main)
        layout.addWidget(btn_tutup, alignment=Qt.AlignmentFlag.AlignCenter)

    def kembali_ke_main(self):
        """Tutup jendela rekap dan tampilkan kembali MainWindow."""
        if self.parent_window:
            self.parent_window.showNormal()
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            self.parent_window.repaint()
            QTimer.singleShot(150, self.parent_window.repaint)
        self.close()

class DifabelWindow(QMainWindow):
    """Jendela maximize untuk rekap pemilih Disabilitas per TPS."""
    def __init__(self, parent_window):
        super().__init__()  # tidak pakai parent Qt

        self.parent_window = parent_window  # simpan referensi manual
        self.setWindowTitle("Rekap Pemilih Disabilitas")
        self.setStyleSheet("background-color: #ffffff;")

        # === Layout utama ===
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        self.setCentralWidget(central)

        # =========================================================
        # 🧭 Ambil info dari parent_window
        # =========================================================
        nama_user = getattr(parent_window, "_nama", "PENGGUNA").upper()
        tahap = getattr(parent_window, "_tahapan", "DPHP").upper()
        kecamatan = getattr(parent_window, "_kecamatan", "").upper()
        desa = getattr(parent_window, "_desa", "").upper()

        if tahap == "DPHP":
            nama_tahapan = "DAFTAR PEMILIH HASIL PEMUTAKHIRAN PEMILU TAHUN 2029"
        elif tahap == "DPSHP":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN PEMILU TAHUN 2029"
        elif tahap == "DPSHPA":
            nama_tahapan = "DAFTAR PEMILIH SEMENTARA HASIL PERBAIKAN AKHIR PEMILU TAHUN 2029"
        else:
            nama_tahapan = "DAFTAR PEMILIH PEMILU TAHUN 2029"

        lokasi_str = f"KECAMATAN {kecamatan} DESA {desa}"

        lbl_user = QLabel(nama_user)
        lbl_user.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Segoe UI", 11)
        font.setBold(True)             
        lbl_user.setFont(font)

        lbl_user.setStyleSheet("""
            color: #000000;
            border-bottom: 3px solid #ff6600;
            padding-bottom: 8px;
        """)

        layout.addWidget(lbl_user)

        judul_layout = QVBoxLayout()
        judul_layout.setSpacing(2)
        for text, size, weight in [
            ("REKAP PEMILIH DISABILITAS", 13, QFont.Weight.Bold),
            (nama_tahapan, 13, QFont.Weight.Bold),
            (lokasi_str, 13, QFont.Weight.Bold)
        ]:
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", size, weight))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #000000;" if size > 13 else "color: #000000;")
            judul_layout.addWidget(lbl)
        layout.addLayout(judul_layout)

        # === Tabel utama ===
        headers = [
            "NAMA TPS", "JUMLAH KK", "FISIK", "INTELEKTUAL",
            "MENTAL", "DIF. WICARA", "DIF. RUNGU", "DIF. NETRA", "JUMLAH"
        ]
        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("""
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                font-weight: bold;
                font-family: Segoe UI;
                font-size: 11pt;
                padding: 6px;
            }
            QTableWidget {
                gridline-color: #dddddd;
                background-color: white;
                alternate-background-color: #f6f6f6;
                color: #000000;
                font-size: 11pt;
                font-family: Segoe UI;
                selection-background-color: #d9d9d9;
                selection-color: #000000;
            }
        """)

        # === Ambil data dari tabel difabel ===
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM difabel ORDER BY CAST(substr(\"NAMA TPS\", 5) AS INTEGER)")
        rows = cur.fetchall()
        self.table.setRowCount(len(rows) + 1)

        # === Hitung total kolom ===
        col_totals = [0] * len(headers)
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                if j > 0:
                    try:
                        col_totals[j] += int(val or 0)
                    except ValueError:
                        pass
                item = QTableWidgetItem(str(val))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                self.table.setItem(i, j, item)

        # === Baris total otomatis ===
        total_labels = ["TOTAL"] + [str(col_totals[j]) for j in range(1, len(headers))]
        for j, val in enumerate(total_labels):
            item = QTableWidgetItem(val)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setBold(True)
            font.setPointSize(11)
            item.setFont(font)
            item.setBackground(QBrush(QColor("#B0AEAD")))
            self.table.setItem(len(rows), j, item)

        layout.addWidget(self.table)

        # === Tombol Tutup ===
        btn_tutup = QPushButton("Tutup")
        btn_tutup.setFixedSize(120, 40)
        btn_tutup.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #d71d1d; }
        """)
        btn_tutup.clicked.connect(self.kembali_ke_main)
        layout.addWidget(btn_tutup, alignment=Qt.AlignmentFlag.AlignCenter)

    def kembali_ke_main(self):
        """Tutup jendela rekap dan tampilkan kembali MainWindow."""
        if self.parent_window:
            self.parent_window.showNormal()
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            self.parent_window.repaint()
            QTimer.singleShot(150, self.parent_window.repaint)
        self.close()


class BeritaAcara(QMainWindow):
    """Jendela Berita Acara lengkap sesuai template resmi (2 halaman, dengan logo, input, navigasi, dan viewer)."""
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.desa = getattr(parent_window, "_desa", "").upper()
        self.kecamatan = getattr(parent_window, "_kecamatan", "").upper()
        self.tahap = getattr(parent_window, "_tahapan", "DPHP").upper()

        self.setWindowTitle(f"Berita Acara Desa {self.desa.title()} – Tahap {self.tahap}")
        self.setStyleSheet("background-color:#ffffff;")
        self.showMaximized()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)
        self.setCentralWidget(central)

        # ====================== PDF VIEWER ==========================
        self.viewer = QPdfView(self)
        #self.viewer.setZoomMode(QPdfView.ZoomMode.FitInView)
        #self.viewer.setPageMode(QPdfView.PageMode.SinglePage)
        layout.addWidget(self.viewer, stretch=1)

        # ====================== BARIS BAWAH (INPUT + TUTUP) =====================
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 10, 0, 0)

        self.btn_input1 = QPushButton("📄 Data Berita Acara", self)
        self.btn_input1.setStyleSheet("""
            QPushButton{background:#ff6600;color:white;border-radius:8px;font-weight:bold;padding:10px 16px;}
            QPushButton:hover{background:#d94f00;}
        """)
        self.btn_input1.clicked.connect(self.open_dialog_ba)

        self.btn_input2 = QPushButton("🗒 Masukan/Tanggapan", self)
        self.btn_input2.setStyleSheet("""
            QPushButton{background:#0099cc;color:white;border-radius:8px;font-weight:bold;padding:10px 16px;}
            QPushButton:hover{background:#0077aa;}
        """)
        self.btn_input2.clicked.connect(self.open_dialog_masukan)

        self.btn_hapus = QPushButton("🗑️ Hapus Tanggapan")
        self.btn_hapus.setFixedHeight(34)
        self.btn_hapus.setStyleSheet("""
            QPushButton {
                background-color: #cc0000;
                color: white;
                border-radius: 6px;
                font-weight: bold;
                padding: 4px 10px;
            }
            QPushButton:hover { background-color: #ff3333; }
        """)
        self.btn_hapus.clicked.connect(self.konfirmasi_hapus_masukan)

        self.btn_tutup = QPushButton("Tutup", self)
        self.btn_tutup.setFixedSize(120, 40)
        self.btn_tutup.setStyleSheet("""
            QPushButton{background:#888;color:white;border-radius:8px;font-weight:bold;}
            QPushButton:hover{background:#666;}
        """)
        self.btn_tutup.clicked.connect(self.kembali_ke_main)

        bottom.addWidget(self.btn_input1)
        bottom.addWidget(self.btn_input2)
        bottom.addWidget(self.btn_hapus)
        bottom.addStretch()
        bottom.addWidget(self.btn_tutup)
        layout.addLayout(bottom)

        # ====================== TOOLBAR ATAS (SAVE & PRINT) ======================
        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background: #f8f8f8;
                spacing: 6px;
                border: none;
            }
            QToolButton {
                background: transparent;
                border-radius: 6px;
                padding: 6px 10px;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: 600;
                color: #333333;
            }
            QToolButton:hover {
                background-color: #ff6600;
                color: #ffffff;
            }
        """)

        # === Tombol Save ===
        btn_save = QAction("💾 Simpan", self)
        btn_save.triggered.connect(self.simpan_pdf_ke_disk)
        toolbar.addAction(btn_save)

        # === Tombol Print ===
        btn_print = QAction("🖨 Cetak", self)
        btn_print.triggered.connect(self.print_pdf)
        toolbar.addAction(btn_print)

        # Tambahkan toolbar di sisi atas window
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # register font
        try:
            pdfmetrics.registerFont(TTFont("Arial", "arial.ttf"))
        except Exception:
            pass

        # buat tampilan awal kosong
        self.create_placeholder_pdf()

    # ======================= DIALOGS ========================
    def open_dialog_ba(self):
        dlg = _DialogDataBA(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.get_values()
            self.generate_berita_acara_pdf(**vals)

    def open_dialog_masukan(self):
        """Buka dialog input masukan/tanggapan dan perbarui dokumen langsung bila sudah tampil."""
        dlg = _DialogMasukan(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            teks = dlg.get_text().strip()
            if teks:
                self._masukan_points = [ln.strip() for ln in teks.splitlines() if ln.strip()]

                # Jika dokumen sudah tampil → update langsung
                if hasattr(self, "document") and self.document.pageCount() > 0:
                    self.update_masukan_section()
                else:
                    print("[Masukan] Dokumen belum dibuat; data akan dimasukkan saat generate.")

    # ======================= PDF STYLES ========================
    def _styles(self):
        styles = getSampleStyleSheet()

        # 🔹 Paragraf menjorok (paragraf pembuka dan narasi umum)
        if "JustifyArial" not in styles:
            styles.add(ParagraphStyle(
                name="JustifyArial",
                fontName="Arial",
                fontSize=12,
                leading=16,
                alignment=4,           # justify
                firstLineIndent=20,    # ✅ menjorok ke dalam 20 pt (~0.7 cm)
                textColor=colors.black,
                spaceBefore=0,
                spaceAfter=10
            ))

        # 🔹 Paragraf rata kiri-kanan tanpa menjorok (untuk poin, daftar, atau penutup)
        if "JustifyNoIndent" not in styles:
            styles.add(ParagraphStyle(
                name="JustifyNoIndent",
                fontName="Arial",
                fontSize=12,
                leading=16,
                alignment=4,           # justify
                firstLineIndent=0,     # 🚫 tanpa indentasi
                textColor=colors.black,
                spaceBefore=0,
                spaceAfter=10
            ))

        # 🔹 Paragraf tengah tebal (judul dan subjudul)
        if "CenterBold" not in styles:
            styles.add(ParagraphStyle(
                name="CenterBold",
                fontName="Arial",
                fontSize=12,
                alignment=1,           # center
                leading=16,
                spaceAfter=10,
                textColor=colors.black
            ))
        # 🔹 Paragraf tengah tebal (judul dan subjudul)
        if "ttdstyle" not in styles:
            styles.add(ParagraphStyle(
                name="ttdstyle",
                fontName="Arial",
                fontSize=12,
                alignment=1,           # center
                firstLineIndent=250, 
                leading=16,
                spaceAfter=10,
                textColor=colors.black
            ))
        if "JustifyHanging" not in styles:
            styles.add(ParagraphStyle(
                name="JustifyHanging",
                fontName="Arial",
                fontSize=12,
                leading=16,
                alignment=4,          # justify
                leftIndent=25,        # jarak seluruh paragraf
                firstLineIndent=-15,  # baris pertama menjorok ke kiri (buat efek gantung)
                textColor=colors.black,
                spaceBefore=0,
                spaceAfter=8
            ))

        return styles

    # ======================= TEMPLATE PDF ========================
    def generate_berita_acara_pdf(self, nomor: str, tanggal_qdate, ketua: str, anggota1: str, anggota2: str):
        if self.tahap == "DPHP":
            judul_tahapan = "Daftar Pemilih Hasil Pemutakhiran"
        elif self.tahap == "DPSHP":
            judul_tahapan = "Daftar Pemilih Hasil Perbaikan <b>DPS</b>"
        elif self.tahap == "DPSHPA":
            judul_tahapan = "Daftar Pemilih Hasil Perbaikan <b>DPSHP</b>"
        else:
            judul_tahapan = "Daftar Pemilih Hasil Pemutakhiran"  # fallback
            
        def terbilang_bilangan(n: int) -> str:
            angka = ["", "satu", "dua", "tiga", "empat", "lima", "enam",
                    "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"]
            if n < 12:
                return angka[n]
            elif n < 20:
                return terbilang_bilangan(n - 10) + " belas"
            elif n < 100:
                return terbilang_bilangan(n // 10) + " puluh " + terbilang_bilangan(n % 10)
            elif n < 200:
                return "seratus " + terbilang_bilangan(n - 100)
            elif n < 1000:
                return terbilang_bilangan(n // 100) + " ratus " + terbilang_bilangan(n % 100)
            elif n < 2000:
                return "seribu " + terbilang_bilangan(n - 1000)
            elif n < 1_000_000:
                return terbilang_bilangan(n // 1000) + " ribu " + terbilang_bilangan(n % 1000)
            else:
                return str(n)
            
        def format_angka(n):
            """Ubah angka menjadi format ribuan dengan titik (contoh: 1234567 → 1.234.567)."""
            return f"{int(n):,}".replace(",", ".")    
        
        # Ambil data dari parent_window
        jumlah_tps = int(getattr(self.parent_window, "_jumlah_tps", 0) or 0)
        jumlah_laki = int(getattr(self.parent_window, "_jumlah_laki", 0) or 0)
        jumlah_perempuan = int(getattr(self.parent_window, "_jumlah_perempuan", 0) or 0)
        jumlah_pemilih = int(getattr(self.parent_window, "_jumlah_pemilih", 0) or 0)

        # Format angka
        tps_fmt = format_angka(jumlah_tps)
        laki_fmt = format_angka(jumlah_laki)
        perempuan_fmt = format_angka(jumlah_perempuan)
        pemilih_fmt = format_angka(jumlah_pemilih)

        # =============================
        # 🔹 Siapkan PDF buffer & style
        # =============================
        buf = BytesIO()
        styles = self._styles()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=60, rightMargin=60, topMargin=60, bottomMargin=50
        )

        nomor = (nomor or "...").strip()
        points = getattr(self, "_masukan_points", None)

        # =============================
        # 🔹 Format hari & tanggal terbilang
        # =============================
        try:
            locale.setlocale(locale.LC_TIME, "id_ID.utf8")
        except:
            try:
                locale.setlocale(locale.LC_TIME, "Indonesian_indonesia.1252")
            except:
                pass

        pydate = tanggal_qdate.toPyDate()
        hari = pydate.strftime("%A").capitalize()              # contoh: jumat
        bulan = pydate.strftime("%B").capitalize()             # contoh: september
        tanggal_angka = pydate.day
        tahun_angka = pydate.year

        tanggal_terbilang = terbilang_bilangan(tanggal_angka).strip().title()
        tahun_terbilang = terbilang_bilangan(tahun_angka).strip().title()
        tanggal_lengkap_terbilang = f"{tanggal_terbilang} bulan {bulan} tahun {tahun_terbilang}"

        # =============================
        # 🔹 Mulai isi dokumen
        # =============================
        story = []

        # === Logo KPU di atas judul ===
        try:
            import os
            from reportlab.platypus import Image as RLImage
            base_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.join(base_dir, "KPU.png")

            if os.path.exists(logo_path):
                logo = RLImage(logo_path, width=2.2 * cm, height=2.2 * cm)
                logo.hAlign = "CENTER"
                story.append(logo)
                story.append(Spacer(1, 10))  # jarak 10–12 mm
        except Exception as e:
            print(f"[Logo Warning] Tidak dapat memuat logo: {e}")

        # === Judul utama ===
        story.append(Paragraph("<b><u>BERITA ACARA</u></b>", styles["CenterBold"]))
        story.append(Spacer(1, -12))
        story.append(Paragraph(f"Nomor: {nomor}", styles["CenterBold"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"<b>REKAPITULASI {judul_tahapan.upper()}<br/>"
            f"TINGKAT DESA {self.desa.upper()}<br/>"
            "PEMILIHAN UMUM TAHUN 2029</b>", styles["CenterBold"]))
        story.append(Spacer(1, 8))

        # === Paragraf pembuka ===
        story.append(Paragraph(
            f"Pada hari {hari} tanggal {tanggal_lengkap_terbilang} "
            f"bertempat di Desa {self.desa.title()}, PPS {self.desa.title()} "
            f"telah melaksanakan Rapat Pleno Terbuka Rekapitulasi {judul_tahapan.title()} Tingkat Desa "
            f"{self.desa.title()} untuk Pemilihan Umum Tahun 2029.",
            styles["JustifyArial"]))
        story.append(Spacer(1, 4))

        story.append(Paragraph(
            f"Dalam Rapat tersebut, PPS {self.desa.title()} menetapkan Rekapitulasi {judul_tahapan.title()} "
            f"Desa {self.desa.title()} dengan rincian sebagai berikut:",
            styles["JustifyArial"]))
        story.append(Spacer(1, 4))

        # === Poin 1 ===
        story.append(Paragraph(f"1. Rekapitulasi {judul_tahapan.title()}", styles["JustifyNoIndent"]))
        story.append(Spacer(1, -6))

        # === Style paragraf tengah (lebih rapat) ===
        style_center = ParagraphStyle(
            name="Center",
            fontName="Arial",
            fontSize=12,
            alignment=1,   # center
            leading=14,    # jarak antar baris lebih rapat (default 14)
            spaceBefore=0,
            spaceAfter=0,
        )

        # === Header tabel (1 cell gabungan, 2 baris teks) ===
        judul_header = Paragraph(
            f"REKAPITULASI {judul_tahapan.upper()}<br/>DESA {self.desa.upper()}",
            style_center
        )

        data_tabel = [
            [judul_header, "", "", ""],
            ["JUMLAH TPS", "LAKI-LAKI", "PEREMPUAN", "JUMLAH PEMILIH"],
            [f"{tps_fmt}", f"{laki_fmt}", f"{perempuan_fmt}", f"{pemilih_fmt}"]
            #[".....", ".....", ".....", "....."]
        ]

        tbl = Table(data_tabel, colWidths=[110, 110, 110, 110])

        tbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
            ("SPAN", (0, 0), (-1, 0)),          # gabungkan header 1 cell
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), "Arial"),
            ("FONTSIZE", (0, 0), (-1, -1), 12),

            # 🔹 Perkecil jarak vertikal header biar tidak tinggi
            ("TOPPADDING", (0, 0), (-1, 0), 2),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),

            # 🔹 Normal padding untuk baris lain
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ]))

        story.append(tbl)
        story.append(Spacer(1, 12))

        # === Poin 2 ===
        story.append(Paragraph("2. Menerima masukan data dari:", styles["JustifyNoIndent"]))
        story.append(Spacer(1, -10))
        if points:
            # Hapus baris kosong
            points = [p.strip() for p in points if p.strip()]

            # Jika hanya satu poin dan isinya mulai dengan "a."
            if len(points) == 1 and points[0].lower().startswith("a."):
                teks = points[0][2:].strip()  # ambil isi setelah "a."
                if teks:  # kalau ada isi setelah "a."
                    story.append(Paragraph(f"- {teks}", styles["JustifyHanging"]))
                else:  # kalau cuma "a." tanpa isi
                    story.append(Paragraph("-", styles["JustifyHanging"]))
                    story.append(Spacer(1, -2))
            else:
                # Normal: tampilkan semua poin apa adanya
                for p in points:
                    story.append(Paragraph(p, styles["JustifyHanging"]))
        else:
            story.append(Paragraph("- Tidak ada masukan/tanggapan data", styles["JustifyArial"]))

        story.append(Spacer(1, 4))

        # === Paragraf penutup ===
        story.append(Paragraph(
            f"Rekapitulasi {judul_tahapan.title()} tersebut selanjutnya ditetapkan secara lebih rinci "
            f"dalam dokumen Rekapitulasi Tingkat Desa {self.desa.title()} sebagaimana terlampir yang merupakan bagian tidak terpisahkan dari Berita Acara ini.",
            styles["JustifyArial"]))
        story.append(Spacer(1, 4))

        story.append(Paragraph(
            "Demikian Berita Acara ini dibuat untuk digunakan sebagaimana mestinya.",
            styles["JustifyArial"]))
        story.append(Spacer(1, -2))

        # === Blok lokasi dan tanggal dibuat dalam tabel dua kolom agar titik dua sejajar ===
        data_ttd = [
            ["Dibuat di", f": {self.desa.title()}"],
            ["Pada Tanggal", f": {pydate.strftime('%d %B %Y')}"]
        ]

        tbl_ttd = Table(data_ttd, colWidths=[80, 100])  # kolom 1 label, kolom 2 isi
        tbl_ttd.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Arial"),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 120),  # geser tabel ke kanan
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            # Tidak ada garis, jadi tabel transparan
        ]))
        story.append(tbl_ttd)
        story.append(Spacer(1, 20))
        #story.append(PageBreak())

        # === Halaman 2 - tanda tangan ===
        story.append(Paragraph(f"<b>PANITIA PEMUNGUTAN SUARA {self.desa.upper()}</b>", styles["CenterBold"]))
        story.append(Spacer(1, 20))
        data = [
            [f"1. {ketua or '............................'}", "KETUA", "1. ......................"],
            [f"2. {anggota1 or '............................'}", "ANGGOTA", "                  2. ......................"],
            [f"3. {anggota2 or '............................'}", "ANGGOTA", "3. ......................"],
        ]
        tbl_ttd = Table(data, colWidths=[180, 100, 180])
        tbl_ttd.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Arial"),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 35),
        ]))
        story.append(tbl_ttd)

        # simpan ke atribut agar bisa digunakan update_masukan_section
        self._nomor_berita = nomor
        self._tanggal_pleno = tanggal_qdate
        self._ketua_pps = ketua
        self._anggota1 = anggota1
        self._anggota2 = anggota2

        # === Bangun PDF ===
        doc.build(story)
        self._show_pdf_bytes(buf.getvalue())

    def update_masukan_section(self):
        """Perbarui dokumen lengkap (tetapi ringan) agar masukan baru langsung muncul di PDF viewer."""
        try:
            if not hasattr(self, "_masukan_points"):
                self._masukan_points = []

            # Ambil semua data terakhir dari instance
            nomor = getattr(self, "_nomor_berita", "...")
            tanggal_qdate = getattr(self, "_tanggal_pleno", None)
            ketua = getattr(self, "_ketua_pps", "")
            anggota1 = getattr(self, "_anggota1", "")
            anggota2 = getattr(self, "_anggota2", "")
            if not tanggal_qdate:
                print("[Update Masukan] Dokumen belum memiliki tanggal pleno.")
                return

            # ==============================
            # 🔹 Rebuild ulang full dokumen
            # ==============================
            buf = BytesIO()
            styles = self._styles()
            doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=60, rightMargin=60, topMargin=60, bottomMargin=50)

            # Data jumlah dari parent
            jumlah_tps = int(getattr(self.parent_window, "_jumlah_tps", 0))
            jumlah_laki = int(getattr(self.parent_window, "_jumlah_laki", 0))
            jumlah_perempuan = int(getattr(self.parent_window, "_jumlah_perempuan", 0))
            jumlah_pemilih = int(getattr(self.parent_window, "_jumlah_pemilih", 0))

            def format_angka(n):
                return f"{int(n):,}".replace(",", ".")

            tps_fmt = format_angka(jumlah_tps)
            laki_fmt = format_angka(jumlah_laki)
            perempuan_fmt = format_angka(jumlah_perempuan)
            pemilih_fmt = format_angka(jumlah_pemilih)

            # Tentukan judul tahapan
            if self.tahap == "DPHP":
                judul_tahapan = "Daftar Pemilih Hasil Pemutakhiran"
            elif self.tahap == "DPSHP":
                judul_tahapan = "Daftar Pemilih Hasil Perbaikan <b>DPS</b>"
            elif self.tahap == "DPSHPA":
                judul_tahapan = "Daftar Pemilih Hasil Perbaikan <b>DPSHP</b>"
            else:
                judul_tahapan = "Daftar Pemilih Hasil Pemutakhiran"

            # Bangun story baru (full dokumen)
            story = []

            # === Logo KPU ===
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                logo_path = os.path.join(base_dir, "KPU.png")
                if os.path.exists(logo_path):
                    logo = RLImage(logo_path, width=2.2 * cm, height=2.2 * cm)
                    logo.hAlign = "CENTER"
                    story.append(logo)
                    story.append(Spacer(1, 10))
            except Exception as e:
                print(f"[Logo Warning] {e}")

            # === Header utama ===
            story.append(Paragraph("<b><u>BERITA ACARA</u></b>", styles["CenterBold"]))
            story.append(Spacer(1, -12))
            story.append(Paragraph(f"Nomor: {nomor}", styles["CenterBold"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph(
                f"<b>REKAPITULASI {judul_tahapan.upper()}<br/>"
                f"TINGKAT DESA {self.desa.upper()}<br/>"
                "PEMILIHAN UMUM TAHUN 2029</b>", styles["CenterBold"]))
            story.append(Spacer(1, 8))

            # === Paragraf 1 ===
            pydate = tanggal_qdate.toPyDate()
            hari = pydate.strftime("%A").capitalize()
            bulan = pydate.strftime("%B").capitalize()
            tanggal_angka = pydate.day
            tahun_angka = pydate.year
            tanggal_terbilang = str(tanggal_angka)
            tahun_terbilang = str(tahun_angka)

            tanggal_lengkap_terbilang = f"{tanggal_terbilang} bulan {bulan} tahun {tahun_terbilang}"

            story.append(Paragraph(
                f"Pada hari {hari} tanggal {tanggal_lengkap_terbilang} "
                f"bertempat di Desa {self.desa.title()}, PPS {self.desa.title()} "
                f"telah melaksanakan Rapat Pleno Terbuka Rekapitulasi {judul_tahapan.title()} Tingkat Desa "
                f"{self.desa.title()} untuk Pemilihan Umum Tahun 2029.",
                styles["JustifyArial"]))
            story.append(Spacer(1, 4))

            story.append(Paragraph(
                f"Dalam Rapat tersebut, PPS {self.desa.title()} menetapkan Rekapitulasi {judul_tahapan.title()} "
                f"Desa {self.desa.title()} dengan rincian sebagai berikut:",
                styles["JustifyArial"]))
            story.append(Spacer(1, 6))

            # === Tabel rekap ===
            judul_header = Paragraph(
                f"REKAPITULASI {judul_tahapan.upper()}<br/>DESA {self.desa.upper()}",
                ParagraphStyle("centered", parent=styles["CenterBold"], alignment=1, leading=14)
            )

            data_tabel = [
                [judul_header, "", "", ""],
                ["JUMLAH TPS", "LAKI-LAKI", "PEREMPUAN", "JUMLAH PEMILIH"],
                [tps_fmt, laki_fmt, perempuan_fmt, pemilih_fmt]
            ]

            tbl = Table(data_tabel, colWidths=[110, 110, 110, 110])
            tbl.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
                ("SPAN", (0, 0), (-1, 0)),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, -1), "Arial"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, 0), 2),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 10))

            # === Poin (2) — Masukan ===
            story.append(Paragraph("2. Menerima masukan data dari:", styles["JustifyNoIndent"]))
            story.append(Spacer(1, -6))
            if self._masukan_points:
                # Hapus baris kosong
                self._masukan_points = [p.strip() for p in self._masukan_points if p.strip()]

                # Jika hanya satu poin dan isinya mulai dengan "a."
                if len(self._masukan_points) == 1 and self._masukan_points[0].lower().startswith("a."):
                    teks = self._masukan_points[0][2:].strip()  # ambil isi setelah "a."
                    if teks:  # kalau ada isi setelah "a."
                        story.append(Paragraph(f"- {teks}", styles["JustifyHanging"]))
                    else:  # kalau cuma "a." tanpa isi
                        story.append(Paragraph("-", styles["JustifyHanging"]))
                        story.append(Spacer(1, -2))
                else:
                    # Normal: tampilkan semua poin apa adanya
                    for p in self._masukan_points:
                        story.append(Paragraph(p, styles["JustifyHanging"]))
            else:
                story.append(Paragraph("- Tidak ada masukan/tanggapan data", styles["JustifyArial"]))
            story.append(Spacer(1, 8))

            # === Paragraf penutup ===
            story.append(Paragraph(
                f"Rekapitulasi {judul_tahapan.title()} tersebut selanjutnya ditetapkan secara lebih rinci "
                f"dalam dokumen Rekapitulasi Tingkat Desa {self.desa.title()} sebagaimana terlampir yang merupakan bagian tidak terpisahkan dari Berita Acara ini.",
                styles["JustifyArial"]))
            story.append(Spacer(1, 4))
            story.append(Paragraph("Demikian Berita Acara ini dibuat untuk digunakan sebagaimana mestinya.", styles["JustifyArial"]))
            story.append(Spacer(1, -2))
            # === Blok lokasi dan tanggal dibuat dalam tabel dua kolom agar titik dua sejajar ===
            data_ttd = [
                ["Dibuat di", f": {self.desa.title()}"],
                ["Pada Tanggal", f": {pydate.strftime('%d %B %Y')}"]
            ]

            tbl_ttd = Table(data_ttd, colWidths=[80, 100])  # kolom 1 label, kolom 2 isi
            tbl_ttd.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Arial"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 120),  # geser tabel ke kanan
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                # Tidak ada garis, jadi tabel transparan
            ]))
            story.append(tbl_ttd)
            story.append(Spacer(1, 20))
            #story.append(PageBreak())

            # === Halaman 2 - Tanda tangan ===
            story.append(Paragraph(f"<b>PANITIA PEMUNGUTAN SUARA {self.desa.upper()}</b>", styles["CenterBold"]))
            story.append(Spacer(1, 20))
            data_ttd = [
                [f"1. {ketua or '............................'}", "KETUA", "1. ......................"],
                [f"2. {anggota1 or '............................'}", "ANGGOTA", "2. ......................"],
                [f"3. {anggota2 or '............................'}", "ANGGOTA", "3. ......................"],
            ]
            tbl_ttd = Table(data_ttd, colWidths=[180, 100, 180])
            tbl_ttd.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Arial"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 35),
            ]))
            story.append(tbl_ttd)

            doc.build(story)
            self._show_pdf_bytes(buf.getvalue())

            #print("[Masukan Update] Dokumen lengkap diperbarui (ringan).")
        except Exception as e:
            print(f"[Masukan Update Error] {e}")

    def create_placeholder_pdf(self):
        buf = BytesIO()
        styles = self._styles()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        doc.build([Paragraph("Belum ada dokumen yang dibuat.", styles["CenterBold"])])
        self._show_pdf_bytes(buf.getvalue())

    def konfirmasi_hapus_masukan(self):
        """Tampilkan dialog konfirmasi hapus dengan tema merah NexVo."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Konfirmasi Hapus")
        msg.setText("Yakin ingin menghapus seluruh masukan/tanggapan dari dokumen?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)

        # === Styling dialog & tombol ===
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
                color: #000000;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }

            QMessageBox QLabel {
                color: #000000;
                font-size: 11pt;
                font-weight: 500;
            }

            QPushButton {
                min-width: 80px;
                min-height: 30px;
                border-radius: 6px;
                font-weight: bold;
                color: white;
                background-color: #cc0000;        /* 🔴 warna dasar */
            }

            QPushButton:hover {
                background-color: #ff3333;        /* 🟠 hover terang */
            }

            QPushButton:pressed {
                background-color: #b30000;        /* 🔴 efek ditekan */
            }

            QPushButton:disabled {
                background-color: #aaaaaa;
                color: #f0f0f0;
            }
        """)

        # Eksekusi dialog dan ambil hasilnya
        reply = msg.exec()

        if reply == QMessageBox.StandardButton.Yes:
            # 🔹 Logika hapus asli kamu tetap sama
            self._masukan_points = []
            if hasattr(self, "document") and self.document.pageCount() > 0:
                self.update_masukan_section()


    # ======================= NAVIGASI HALAMAN (ANTI CRASH) =======================
    from PyQt6.QtCore import QTimer, QPointF

    def _clear_layout(self, layout):
        """Hapus semua widget di dalam layout dengan aman."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def rebuild_pager(self, total=None):
        """Bangun ulang pagination PDF seperti tabel (dinamis & profesional)."""
        cw = self.centralWidget()
        if not cw:
            return
        main_layout = cw.layout()
        if not main_layout:
            return

        # Siapkan layout navigasi jika belum ada
        if not hasattr(self, "_nav_layout"):
            self._nav_layout = QHBoxLayout()
            self._nav_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._nav_layout.setSpacing(6)
            main_layout.insertLayout(1, self._nav_layout)

        # Bersihkan layout lama
        for i in reversed(range(self._nav_layout.count())):
            w = self._nav_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        # Dapatkan total halaman PDF
        if total is None:
            total = int(self.document.pageCount() if hasattr(self, "document") and self.document else 0)
        if total <= 0:
            return

        current_page = getattr(self, "current_page_index", 0) + 1  # ubah ke 1-based
        self.total_pages = total
        window = 3  # jumlah tombol numerik yang terlihat
        half = window // 2

        # === Utility untuk membuat tombol ===
        def make_page_button(text, handler, checked=False, enabled=True):
            btn = QPushButton(text)
            btn.setEnabled(enabled)
            btn.setCheckable(True)
            btn.setChecked(checked)
            btn.clicked.connect(handler)
            btn.setFixedSize(25, 25)  # 🔸 bentuk persegi
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #aaa;
                    border-radius: 6px;
                    background-color: #ffffff;
                    color: #000000;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #ffeed9;    /* 🟠 lembut saat hover */
                    border: 1px solid #ff9900;
                    color: #000000;
                }
                QPushButton:checked {
                    border: 2px solid #ff9900;
                    background-color: #fff5e6;
                    font-weight: bold;
                    color: #000000;
                }
                QPushButton:disabled {
                    color: #999999;
                    border: 1px solid #ddd;
                    background-color: #f5f5f5;
                }
            """)
            return btn


        # === Tombol sebelumnya ===
        prev_btn = make_page_button("‹", lambda: self.safe_jump_to_page(current_page - 2),
                                    checked=False, enabled=(current_page > 1))
        self._nav_layout.addWidget(prev_btn)

        # === Hitung jendela tampilan halaman ===
        start = max(1, current_page - half)
        end = min(total, start + window - 1)
        start = max(1, end - window + 1)

        # Jika masih ada halaman sebelum start
        if start > 1:
            self._nav_layout.addWidget(make_page_button("1", lambda: self.safe_jump_to_page(0)))
            if start > 2:
                self._nav_layout.addWidget(QLabel("..."))

        # === Tombol halaman utama ===
        for p in range(start, end + 1):
            btn = make_page_button(
                str(p),
                lambda _, x=p: self.safe_jump_to_page(x - 1),
                checked=(p == current_page)
            )
            self._nav_layout.addWidget(btn)

        # Jika masih ada halaman setelah end
        if end < total:
            if end < total - 1:
                self._nav_layout.addWidget(QLabel("..."))
            self._nav_layout.addWidget(
                make_page_button(str(total), lambda: self.safe_jump_to_page(total - 1))
            )

        # === Tombol berikutnya ===
        next_btn = make_page_button("›", lambda: self.safe_jump_to_page(current_page),
                                    checked=False, enabled=(current_page < total))
        self._nav_layout.addWidget(next_btn)

        # === Label kecil status halaman (opsional)
        lbl_info = QLabel(f"Halaman {current_page} / {total}")
        lbl_info.setStyleSheet("color:#444; font-size:11px; padding-left:10px;")
        self._nav_layout.addWidget(lbl_info)



    def _show_pdf_bytes(self, pdf_bytes: bytes):
        """Tampilkan PDF langsung di QPdfView, stabil untuk dokumen multi-halaman."""
        try:
            # simpan buffer ke atribut agar tidak dihapus Python GC
            self._pdf_buffer = QBuffer()
            self._pdf_buffer.setData(pdf_bytes)
            self._pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly)

            # buat dokumen dan load dari buffer yang persistent
            self.document = QPdfDocument(self)
            status = self.document.load(self._pdf_buffer)

            if status != QPdfDocument.Status.Ready:
                print(f"[PDF Warning] Status dokumen: {status}")

            # tampilkan di viewer
            self.viewer.setDocument(self.document)

            total_pages = int(self.document.pageCount() or 0)
            #print(f"[PDF OK] Dokumen siap dengan {total_pages} halaman.")

            # rebuild navigasi sesuai jumlah halaman aktual
            self.rebuild_pager(total_pages)

            # tampilkan halaman pertama
            self.safe_jump_to_page(0)

        except Exception as e:
            print(f"[PDF Load Error] {e}")



    def update_page_label(self):
        """Highlight tombol aktif sesuai halaman saat ini."""
        if not getattr(self, "document", None):
            return

        total = int(self.document.pageCount() or 0)
        if total <= 0 or not hasattr(self, "page_buttons"):
            return

        current = self.viewer.pageNavigator().currentPage()
        for i, b in enumerate(self.page_buttons):
            if i == current:
                b.setStyleSheet("""
                    QPushButton {
                        background-color: #ff6600;
                        color: white;
                        font-weight: bold;
                        border-radius: 6px;
                    }
                """)
            else:
                b.setStyleSheet("""
                    QPushButton {
                        background-color: #999;
                        color: white;
                        border-radius: 6px;
                    }
                    QPushButton:hover {background-color: #ff6600;}
                """)


    # ---------------- SAFE NAVIGATION ----------------

    def safe_jump_to_page(self, page_index):
        if not getattr(self, "document", None):
            return
        total = int(self.document.pageCount() or 0)
        if page_index < 0 or page_index >= total:
            return
        self.current_page_index = page_index
        QTimer.singleShot(200, lambda: self._do_jump(page_index))
        self.rebuild_pager()  # 🔸 update navigasi juga saat loncat langsung



    def jump_to_page(self, page_index):
        """Wrapper cepat untuk melompat halaman (gunakan versi aman)."""
        self.safe_jump_to_page(page_index)



    def _do_jump(self, page_index):
        """Melompat ke halaman tertentu, aman dan sinkron dengan pagination."""
        try:
            if not hasattr(self, "document") or not self.document:
                print("[Jump] Dokumen belum siap.")
                return

            total = int(self.document.pageCount() or 0)
            if total <= 0 or page_index < 0 or page_index >= total:
                print(f"[Jump] Halaman {page_index} tidak valid (total {total}).")
                return

            nav = self.viewer.pageNavigator()

            # Proteksi ekstra: tunggu dokumen benar-benar siap
            if self.document.status() != QPdfDocument.Status.Ready:
                print("[Jump] Dokumen belum fully loaded, retry dalam 150ms...")
                QTimer.singleShot(150, lambda: self._do_jump(page_index))
                return

            # Lakukan lompatan yang aman
            nav.jump(page_index, QPointF(0, 0), 0)

            # Update status halaman aktif
            self.current_page_index = page_index

            # Refresh label & navigasi pagination agar warna aktif berpindah
            QTimer.singleShot(100, self.update_page_label)
            if hasattr(self, "rebuild_pager"):
                QTimer.singleShot(120, self.rebuild_pager)

            # Log opsional
            # print(f"[Jump] Pindah ke halaman {page_index + 1}/{total}")

        except Exception as e:
            print(f"[Jump Error] {e}")

    def next_page(self):
        if not getattr(self, "document", None):
            return
        total = int(self.document.pageCount() or 0)
        cur = getattr(self, "current_page_index", 0)
        if cur < total - 1:
            self.safe_jump_to_page(cur + 1)
            self.rebuild_pager()  # 🔸 update navigasi

    def prev_page(self):
        if not getattr(self, "document", None):
            return
        cur = getattr(self, "current_page_index", 0)
        if cur > 0:
            self.safe_jump_to_page(cur - 1)
            self.rebuild_pager()  # 🔸 update navigasi

        # ======================== SIMPAN & CETAK ========================

    def simpan_pdf_ke_disk(self):
        """Simpan dokumen PDF ke C:/NexVo/<tahapan> dengan nama otomatis."""
        try:
            # === 1️⃣ Pastikan sudah ada dokumen PDF yang valid ===
            if not hasattr(self, "_pdf_buffer") or self._pdf_buffer.size() == 0:
                QMessageBox.warning(
                    self,
                    "Tidak Ada Dokumen",
                    "Belum ada dokumen Berita Acara yang bisa disimpan.\n"
                    "Silakan buat dokumen Berita Acara terlebih dahulu."
                )
                return

            if not hasattr(self, "_nomor_berita"):
                QMessageBox.warning(
                    self,
                    "Belum Ada Dokumen",
                    "Dokumen Berita Acara belum dibuat.\n"
                    "Silakan isi dan buat Berita Acara sebelum menyimpannya."
                )
                return

            # === 2️⃣ Pastikan folder tujuan ada ===
            import os, datetime
            tahap = getattr(self, "tahap", "TAHAPAN")
            desa = getattr(self, "desa", "DESA").title()
            base_dir = os.path.join("C:/NexVo", tahap)
            os.makedirs(base_dir, exist_ok=True)

            # === 3️⃣ Format nama file ===
            waktu_str = datetime.datetime.now().strftime("%d%m%Y %H%M")  # ada spasi
            nama_file = f"BA {tahap} Desa {desa} Pemilu 2029 {waktu_str}.pdf"
            path_file = os.path.join(base_dir, nama_file)

            # === 4️⃣ Konfirmasi sebelum menyimpan (custom style) ===
            msg = QMessageBox(self)
            msg.setWindowTitle("Konfirmasi Simpan")
            msg.setText(
                f"Apakah Anda yakin ingin menyimpan Berita Acara tahap <b>{tahap}</b>?<br><br>"
                f"<b>Lokasi penyimpanan:</b><br>{path_file}"
            )
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            msg.button(QMessageBox.StandardButton.Yes).setText("Simpan")
            msg.button(QMessageBox.StandardButton.No).setText("Batal")

            # === Gaya khas NexVo (title bar gelap, tombol oranye & abu) ===
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #ffffff;
                    color: #000000;
                    font-family: 'Segoe UI';
                    font-size: 10.5pt;
                }

                QMessageBox QLabel {
                    color: #000000;
                    font-size: 11pt;
                    font-weight: 500;
                }

                /* Title bar hitam */
                QMessageBox QDialogButtonBox {
                    background-color: #000000;
                    border-top: 1px solid #222;
                }

                QPushButton {
                    min-width: 80px;
                    min-height: 32px;
                    border-radius: 6px;
                    font-weight: bold;
                    color: white;
                    background-color: #ff6600;    /* tombol default oranye */
                }
                QPushButton:hover {
                    background-color: #e65c00;
                }
                QPushButton:pressed {
                    background-color: #cc5200;
                }
                QPushButton[text="Batal"] {
                    background-color: #777777;
                }
                QPushButton[text="Batal"]:hover {
                    background-color: #555555;
                }
            """)

            jawab = msg.exec()

            if jawab != QMessageBox.StandardButton.Yes:
                return

            # === 5️⃣ Simpan buffer PDF ke file ===
            with open(path_file, "wb") as f:
                f.write(self._pdf_buffer.data())

        except Exception as e:
            QMessageBox.critical(self, "Gagal Menyimpan", f"Terjadi kesalahan:\n{e}")

    def print_pdf(self):
        """Cetak PDF langsung ke printer (fit-to-page sesuai DPI, auto orientasi, tanpa notifikasi)."""
        try:
            # 1️⃣ Validasi dokumen
            if not hasattr(self, "_pdf_buffer") or self._pdf_buffer.size() == 0:
                QMessageBox.warning(self, "Tidak Ada Dokumen",
                                    "Belum ada dokumen Berita Acara yang bisa dicetak.\n"
                                    "Silakan buat dokumen Berita Acara terlebih dahulu.")
                return
            if not hasattr(self, "_nomor_berita"):
                QMessageBox.warning(self, "Belum Ada Dokumen",
                                    "Dokumen Berita Acara belum dibuat.\n"
                                    "Silakan isi dan buat Berita Acara sebelum mencetaknya.")
                return

            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt6.QtGui import QPainter, QPageLayout
            from PyQt6.QtCore import QSize, QRectF

            tahap = getattr(self, "tahap", "TAHAPAN")

            # 2️⃣ Konfirmasi
            msg = QMessageBox(self)
            msg.setWindowTitle("Konfirmasi Cetak")
            msg.setText(f"Apakah Anda yakin ingin mencetak Berita Acara tahap <b>{tahap}</b>?")
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.button(QMessageBox.StandardButton.Yes).setText("Cetak")
            msg.button(QMessageBox.StandardButton.No).setText("Batal")
            msg.setStyleSheet("""
                QMessageBox { background:#fff; color:#000; font-family:'Segoe UI'; font-size:10.5pt; }
                QMessageBox QLabel { color:#000; font-size:11pt; font-weight:500; }
                QPushButton { min-width:80px; min-height:32px; border-radius:6px; font-weight:bold; color:#fff; background:#ff6600; }
                QPushButton:hover { background:#e65c00; }
                QPushButton[text="Batal"] { background:#777; }
                QPushButton[text="Batal"]:hover { background:#555; }
            """)
            if msg.exec() != QMessageBox.StandardButton.Yes:
                return

            # 3️⃣ Siapkan printer + orientasi otomatis
            first_size = self.document.pagePointSize(0)
            orient = (QPageLayout.Orientation.Landscape
                    if first_size.width() > first_size.height()
                    else QPageLayout.Orientation.Portrait)

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPageOrientation(orient)
            # (opsional) paksa A4:
            # from PyQt6.QtGui import QPageSize
            # printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

            dlg = QPrintDialog(printer, self)
            dlg.setWindowTitle("Cetak Berita Acara")
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            # 4️⃣ Render dengan DPI penyesuaian
            painter = QPainter()
            if not painter.begin(printer):
                raise Exception("Tidak dapat memulai printer.")

            total_pages = self.document.pageCount()
            page_rect = printer.pageRect(QPrinter.Unit.Point)

            printer_dpi = printer.resolution()
            pdf_dpi = 72  # titik per inci bawaan PDF
            scale_dpi = printer_dpi / pdf_dpi  # konversi ke resolusi printer

            for i in range(total_pages):
                pdf_sz = self.document.pagePointSize(i)
                if not pdf_sz.isValid():
                    continue

                # Ukuran halaman pada resolusi printer
                scaled_width = pdf_sz.width() * scale_dpi
                scaled_height = pdf_sz.height() * scale_dpi

                # Hitung skala proporsional agar pas halaman
                scale_x = (page_rect.width() * scale_dpi) / scaled_width
                scale_y = (page_rect.height() * scale_dpi) / scaled_height
                scale = min(scale_x, scale_y)

                target_w = scaled_width * scale
                target_h = scaled_height * scale
                off_x = (page_rect.width() * scale_dpi - target_w) / 2
                off_y = (page_rect.height() * scale_dpi - target_h) / 2

                # Render halaman sesuai skala dan DPI
                img = self.document.render(
                    i,
                    QSize(int(target_w), int(target_h))
                )
                if img:
                    painter.drawImage(QRectF(off_x, off_y, target_w, target_h), img)
                    if i < total_pages - 1:
                        printer.newPage()

            painter.end()

        except Exception as e:
            QMessageBox.critical(self, "Gagal Mencetak", f"Terjadi kesalahan:\n{e}")
         

    def kembali_ke_main(self):
        if self.parent_window:
            self.parent_window.showNormal()
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            self.parent_window.repaint()
            QTimer.singleShot(150, self.parent_window.repaint)
        self.close()

class EmptyDateEdit(QDateEdit):
    """QDateEdit yang bisa benar-benar kosong sampai user pilih tanggal."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hasDate = False
        self.setDisplayFormat("dd MMMM yyyy")
        self.setCalendarPopup(True)
        self.lineEdit().setReadOnly(True)
        self.setDate(QDate.currentDate())   # tetap butuh internal date valid
        self.lineEdit().clear()              # tapi tampilan dikosongkan
        self.setSpecialValueText("")
        self.dateChanged.connect(self._on_date_selected)

    def _on_date_selected(self, qdate):
        """Aktifkan tampilan tanggal saat user memilih dari kalender."""
        if qdate.isValid():
            self._hasDate = True
            # perbarui tampilan teks
            self.lineEdit().setText(qdate.toString(self.displayFormat()))

    def textFromDateTime(self, dt):
        # kalau belum ada tanggal dipilih, tampilkan kosong
        if not self._hasDate:
            return ""
        return super().textFromDateTime(dt)

    def clear(self):
        """Kosongkan field kembali seperti semula."""
        self._hasDate = False
        self.lineEdit().clear()

# ===================== Dialog Input =====================
class _DialogDataBA(QDialog):
    """Form input untuk data Berita Acara (semua kolom wajib diisi)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Input Data Berita Acara")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet("""
            QDialog {
                background-color: #f9f9f9;
                font-family: 'Segoe UI', sans-serif;
            }

            QLineEdit, QDateEdit {
                border: 1px solid #dcdcdc;
                border-radius: 5px;
                padding: 8px;
                font-size: 10pt;
                background-color: #ffffff;
                color: #000000;
            }

            QDateEdit QLineEdit {
                color: #000000;
                background-color: #ffffff;
            }

            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border-left: 1px solid #000000;
                background-color: #ff6600;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }

            QDateEdit::down-arrow {
                image: url(:/qt-project.org/styles/commonstyle/images/calendar-16.png);
                width: 16px;
                height: 16px;
                margin-right: 4px;
            }
            QDateEdit::down-arrow:hover {
                background-color: #9b59b6;
            }

            QLabel {
                color: #000000;
                font-size: 10pt;
            }

            /* === KALENDER STYLING === */
            QCalendarWidget {
                background-color: #000000;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }

            /* Navigation bar atas kalender */
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #9b59b6;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 4px 10px;
            }

            /* Styling dropdown bulan pada navigation bar */
            QCalendarWidget QComboBox {
                color: #000000;                 /* Pastikan dropdown bulan font-nya hitam */
                background-color: #ffffff;      /* Background putih pada tombol dropdown bulan */
                border: none;
                font-size: 12pt;
                font-weight: bold;
            }

            /* Hilangkan panah kecil pada tombol dropdown bulan */
            QCalendarWidget QComboBox::drop-down {
                image: none;
                border: none;
                width: 0px;
                height: 0px;
            }

            /* Styling daftar bulan (popup) */
            QCalendarWidget QComboBox QAbstractItemView {
                background-color: #ffffff;       /* Background popup daftar bulan */
                color: #000000;                  /* Font item default hitam */
                border: 1px solid #9b59b6;
                selection-background-color: #9b59b6; 
                selection-color: #000000;        /* Font jadi putih saat dipilih/hover */
                padding: 5px;
            }

            /* Item daftar bulan, default hitam */
            QCalendarWidget QComboBox QAbstractItemView::item {
                color: #000000;
                background-color: #ffffff;
                padding: 5px;
            }

            /* Item dipilih/hover, font putih di atas latar ungu */
            QCalendarWidget QComboBox QAbstractItemView::item:selected {
                background-color: #9b59b6; 
                color: #ffffff;
            }

            /* Tombol navigasi bulan */
            QCalendarWidget QToolButton {
                color: #ffffff;
                font-size: 12pt;
                font-weight: bold;
                background-color: transparent;
                border: none;
                margin: 5px;
            }

            QCalendarWidget QToolButton:hover {
                background-color: #8e44ad;
                border-radius: 15px;
            }

            QCalendarWidget QToolButton#qt_calendar_prevmonth,
            QCalendarWidget QToolButton#qt_calendar_nextmonth {
                width: 30px;
                height: 30px;
                border-radius: 15px;
                icon-size: 18px;
            }

            /* Teks bulan-tahun pada navigation bar */
            QCalendarWidget QWidget#qt_calendar_monthyear {
                color: #ffffff;
                font-size: 12pt;
                font-weight: bold;
            }

            /* Hari-hari kalender */
            QCalendarWidget QTableView {
                background-color: #ffffff;
                border: none;
                selection-background-color: #9b59b6;
                selection-color: #000000;
            }

            QCalendarWidget QTableView QHeaderView::section {
                background-color: #ffffff;
                padding: 8px;
                color: #7f8c8d;
                font-weight: bold;
                text-transform: uppercase;
                border: none;
            }

            QCalendarWidget QTableView::item {
                border-radius: 16px;
                background-color: transparent;
                color: #34495e;
                padding: 2px;
                margin: 2px;
            }

            QCalendarWidget QTableView::item:hover {
                background-color: #ecf0f1;
                color: #2c3e50;
            }

            QCalendarWidget QTableView::item:selected {
                background-color: #9b59b6;
                color: #ffffff;
                font-weight: bold;
            }

            QCalendarWidget QTableView::item#qt_calendar_today {
                border: 2px solid #9b59b6;
                color: #ffffff;
                font-weight: bold;
                background-color: transparent;
            }

            QCalendarWidget QTableView::item#qt_calendar_today:selected {
                background-color: #9b59b6;
                color: #000000;
                border: none;
            }

            QCalendarWidget QTableView::item:disabled {
                color: #dcdcdc;
            }
        """)


        layout = QVBoxLayout(self)
        form = QFormLayout()

        # --- Input fields ---
        self.nomor = QLineEdit()
        self.tanggal = EmptyDateEdit()
        self.tanggal.setDisplayFormat("dd MMMM yyyy")
        self.tanggal.setCalendarPopup(True)
        self.tanggal.lineEdit().setReadOnly(True)
        self.tanggal.setStyle(QStyleFactory.create("Fusion"))
        self.tanggal.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # === Kosongkan total tanpa tanggal default ===
        # Jangan pakai setDate() sama sekali
        self.tanggal.clear()
        self.tanggal.lineEdit().clear()
        self.tanggal.setSpecialValueText("")  # pastikan tidak ada teks default

        # === Mencegah QDateEdit mengisi otomatis setelah show() ===
        def eventFilter(obj, event):
            if obj == self.tanggal and event.type() == QEvent.Type.Show:
                self.tanggal.clear()
                self.tanggal.lineEdit().clear()
            return super(type(self), self).eventFilter(obj, event)

        self.tanggal.installEventFilter(self)

        # === Jika user hapus tanggal secara manual (tidak mungkin karena readOnly)
        # tapi jika reset programatik, kosongkan kembali
        def on_date_changed(qdate):
            if not qdate.isValid():
                self.tanggal.clear()
                self.tanggal.lineEdit().clear()
        self.tanggal.dateChanged.connect(on_date_changed)

        self.ketua = QLineEdit()
        self.anggota1 = QLineEdit()
        self.anggota2 = QLineEdit()

        # === Input Ketua dan Anggota otomatis kapital ===
        self.ketua.textChanged.connect(lambda text: self.ketua.setText(text.upper()))
        self.anggota1.textChanged.connect(lambda text: self.anggota1.setText(text.upper()))
        self.anggota2.textChanged.connect(lambda text: self.anggota2.setText(text.upper()))
        form.addRow("Nomor Berita Acara:", self.nomor)
        form.addRow("Tanggal Pleno:", self.tanggal)
        form.addRow("Ketua PPS:", self.ketua)
        form.addRow("Anggota 1:", self.anggota1)
        form.addRow("Anggota 2:", self.anggota2)
        layout.addLayout(form)

        # --- Tombol OK & Batal ---
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_ok = btns.button(QDialogButtonBox.StandardButton.Ok)
        btn_cancel = btns.button(QDialogButtonBox.StandardButton.Cancel)

        btn_ok.setText("Simpan")
        btn_cancel.setText("Batal")

        # 🎨 Styling tombol dengan efek hover
        style_buttons = """
        QPushButton {
            background-color: #ff6600;
            color: white;
            font-weight: bold;
            border-radius: 6px;
            padding: 6px 14px;
            border: none;
        }
        QPushButton:hover {
            background-color: #e65c00; /* oranye sedikit lebih gelap */
        }
        QPushButton:pressed {
            background-color: #cc5200; /* efek ditekan */
        }
        """

        style_cancel = """
        QPushButton {
            background-color: #999999;
            color: white;
            border-radius: 6px;
            padding: 6px 14px;
            border: none;
        }
        QPushButton:hover {
            background-color: #7f7f7f; /* abu-abu lebih gelap saat hover */
        }
        QPushButton:pressed {
            background-color: #666666; /* efek ditekan */
        }
        """

        btn_ok.setStyleSheet(style_buttons)
        btn_cancel.setStyleSheet(style_cancel)

        btns.accepted.connect(self.validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def validate_and_accept(self):
        """Validasi wajib isi semua kolom sebelum menutup dialog."""
        if not self.nomor.text().strip():
            self.show_warning("Nomor Berita Acara wajib diisi.")
            return

        # 🔹 Validasi tanggal wajib diisi
        # Cek apakah user sudah memilih tanggal di EmptyDateEdit
        if hasattr(self.tanggal, "_hasDate") and not self.tanggal._hasDate:
            self.show_warning("Tanggal Pleno wajib diisi.")
            return

        if not self.ketua.text().strip():
            self.show_warning("Nama Ketua PPS wajib diisi.")
            return
        if not self.anggota1.text().strip():
            self.show_warning("Nama Anggota 1 wajib diisi.")
            return
        if not self.anggota2.text().strip():
            self.show_warning("Nama Anggota 2 wajib diisi.")
            return

        self.accept()


    def show_warning(self, pesan):
        """Tampilkan popup peringatan modern."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Peringatan")
        msg.setText(pesan)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 10.5pt;
            }
            QPushButton {
                background-color: #ff6600;
                color: white;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e65c00;
            }
        """)
        msg.exec()

    def get_values(self):
        return dict(
            nomor=self.nomor.text().strip(),
            tanggal_qdate=self.tanggal.date(),
            ketua=self.ketua.text().strip(),
            anggota1=self.anggota1.text().strip(),
            anggota2=self.anggota2.text().strip(),
        )


class _DialogMasukan(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Input Masukan / Tanggapan")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setStyleSheet("""
            QLabel, QTextEdit {
                color: #000000;
                font-family: Arial;
                font-size: 11pt;
            }
            QTextEdit {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 6px;
                background-color: #ffffff;
            }
            QDialogButtonBox QPushButton {
                min-width: 90px;
                min-height: 32px;
                border-radius: 6px;
                font-weight: bold;
                color: white;
                background-color: #ff6600;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #ff9900;
            }
            QDialogButtonBox QPushButton:disabled {
                background-color: #aaaaaa;
            }
        """)

        layout = QVBoxLayout(self)
        lbl = QLabel("Tulis setiap masukan/tanggapan di baris baru (otomatis jadi a., b., c., ...):")
        lbl.setStyleSheet("font-weight: bold; margin-bottom: 4px;")

        self.text = QTextEdit()
        self.text.setPlaceholderText("Isi dari tanggapan/masukkan data ........")
        self.text.keyPressEvent = self.handle_keypress

        layout.addWidget(lbl)
        layout.addWidget(self.text)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Simpan")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Batal")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Awali otomatis dengan "a. " dan kursor langsung di posisi setelahnya
        self.text.setText("a. ")
        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text.setTextCursor(cursor)
        self.text.setFocus()

    def handle_keypress(self, event: QKeyEvent):
        """Tangani Enter agar otomatis menambah huruf a., b., c., ..."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            text = self.text.toPlainText().strip().split("\n")
            next_char = chr(ord('a') + len(text)) + ". "
            cursor = self.text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText("\n" + next_char)
        else:
            QTextEdit.keyPressEvent(self.text, event)

    def get_text(self):
        return self.text.toPlainText()
    
from reportlab.pdfgen.canvas import Canvas

class PageNumCanvas(Canvas):
    """Canvas khusus dengan footer tengah 'Hal X dari Y' otomatis."""
    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            Canvas.showPage(self)
        Canvas.save(self)

    def draw_footer(self, total_pages):
        page = self._pageNumber
        text = f"Hal {page} dari {total_pages}"
        self.setFont(self._fontname, 9)
        self.drawCentredString(landscape(A4)[0] / 2.0, 1.2 * cm, text)

    
class LampAdpp(QMainWindow):
    """Tampilan langsung Model A – Daftar Perubahan Pemilih (PDF muncul otomatis)."""
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.desa = getattr(parent_window, "_desa", "").upper()
        self.kecamatan = getattr(parent_window, "_kecamatan", "").upper()
        self.tahap = getattr(parent_window, "_tahapan", "DPHP").upper()

        # === Ambil daftar TPS ===
        self.tps_list = self.parent_window.get_distinct_tps()
        self.current_tps_index = 0
        self.current_tps = self.tps_list[0] if self.tps_list else "-"

        self.setWindowTitle(f"Daftar Perubahan Pemilih Desa {self.desa.title()} – Tahap {self.tahap}")
        self.setStyleSheet("background-color:#ffffff;")

        # ====================== REGISTER FONT ==========================
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import os

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            font_dir = os.path.join(base_dir, "Fonts")
            pdfmetrics.registerFont(TTFont("calibri-regular", os.path.join(font_dir, "calibri-regular.ttf")))
            pdfmetrics.registerFont(TTFont("calibri-bold", os.path.join(font_dir, "calibri-bold.ttf")))
            #print("[Font OK] calibri-regular dan calibri-bold berhasil diregistrasi dari folder Fonts/")
            self._font_base = "calibri-regular"
            self._font_bold = "calibri-bold"
        except Exception as e:
            #print("[Font Warning] Gagal memuat Arial, fallback ke Helvetica:", e)
            self._font_base = "Helvetica"
            self._font_bold = "Helvetica-Bold"

        # ====================== LAYOUT UTAMA ==========================
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)
        self.setCentralWidget(central)

        # ====================== PDF VIEWER ==========================
        self.viewer = QPdfView(self)
        layout.addWidget(self.viewer, stretch=1)

        # === PROGRESS BAR FLOATING DI TENGAH ===
        self.progress_overlay = QWidget(self)
        self.progress_overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 210);
                border: 1px solid #bbb;
                border-radius: 12px;
            }
        """)
        self.progress_overlay.setFixedSize(280, 60)
        self.progress_overlay.hide()

        overlay_layout = QVBoxLayout(self.progress_overlay)
        overlay_layout.setContentsMargins(20, 10, 20, 10)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress = QProgressBar(self.progress_overlay)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Membuat PDF... %p%")
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #888;
                border-radius: 8px;
                background: #f2f2f2;
                text-align: center;
                height: 18px;
                color: #000000;
            }
            QProgressBar::chunk {
                background-color: #ff9900;
                border-radius: 7px;
            }
        """)
        overlay_layout.addWidget(self.progress)

        # ====================== BARIS BAWAH (NAVIGASI TPS) ======================
        nav_layout = QHBoxLayout()
        nav_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.btn_prev_tps = QPushButton("◀")
        self.btn_next_tps = QPushButton("▶")
        self.lbl_tps = QLabel(f"TPS: {self.current_tps}")

        for btn in (self.btn_prev_tps, self.btn_next_tps):
            btn.setFixedWidth(40)
            btn.setStyleSheet("""
                QPushButton {
                    font-family: 'Segoe UI';
                    font-size: 10pt;
                    padding: 4px;
                    border: 1px solid #aaa;
                    border-radius: 5px;
                    background-color: #ff6600;
                }
                QPushButton:hover {
                    background-color: #f8f8f8;
                }
            """)

        self.lbl_tps.setStyleSheet("font-family:'Segoe UI'; font-size:10pt; margin-left:8px;")

        nav_layout.addWidget(self.btn_prev_tps)
        nav_layout.addWidget(self.btn_next_tps)
        nav_layout.addWidget(self.lbl_tps)
        layout.addLayout(nav_layout)

        self.btn_prev_tps.clicked.connect(lambda: self.change_tps(-1))
        self.btn_next_tps.clicked.connect(lambda: self.change_tps(1))

        # ====================== TOMBOL TUTUP ======================
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 10, 0, 0)

        self.btn_tutup = QPushButton("Tutup", self)
        self.btn_tutup.setFixedSize(120, 40)
        self.btn_tutup.setStyleSheet("""
            QPushButton{background:#888;color:white;border-radius:8px;font-weight:bold;}
            QPushButton:hover{background:#666;}
        """)
        self.btn_tutup.clicked.connect(self.kembali_ke_main)

        bottom.addWidget(self.btn_tutup)
        layout.addLayout(bottom)

        # ====================== TAMPILKAN PDF AWAL ======================
        self.showMaximized()  # <== penting! harus terakhir
        self.generate_adpp_pdf(tps_filter=self.current_tps)


    # ===========================================================
    # STYLE PDF
    # ===========================================================
    def _styles(self):
        """Gaya umum untuk PDF berbasis font terdaftar (Arial / Helvetica)."""
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib import colors

        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name="CenterBold",
            fontName=self._font_bold,
            fontSize=12,
            alignment=1,
            leading=16,
            spaceAfter=10,
            textColor=colors.black
        ))

        styles.add(ParagraphStyle(
            name="LeftNormal",
            fontName=self._font_base,
            fontSize=10.5,
            alignment=0,
            leading=13,
            textColor=colors.black
        ))

        styles.add(ParagraphStyle(
            name="LeftRapat",
            fontName=self._font_base,
            fontSize=10.5,
            alignment=0,
            leading=12,
            textColor=colors.black
        ))

        styles.add(ParagraphStyle(
            name="HeaderTable",
            fontName=self._font_bold,
            fontSize=9,
            alignment=1,
            leading=11,
        ))

        styles.add(ParagraphStyle(
            name="TableCell",
            fontName=self._font_base,
            fontSize=9,
            alignment=1,
            leading=11,
        ))

        styles.add(ParagraphStyle(
            name="TableCellLeft",
            fontName=self._font_base,
            fontSize=9,
            alignment=0,
            leading=11,
        ))

        styles.add(ParagraphStyle(
            name="AngkaTabel",
            fontName=self._font_base,  # misal Arial atau Helvetica
            fontSize=9,
            leading=9,                 # tinggi baris disesuaikan biar vertikalnya pas
            alignment=1,               # 1 = center horizontal
            spaceBefore=0,
            spaceAfter=0,
        ))

        return styles
    
    def _center_progress_overlay(self):
        """Posisikan progress bar overlay di tengah viewer."""
        if not hasattr(self, "progress_overlay") or not self.progress_overlay:
            return
        if not hasattr(self, "viewer") or not self.viewer:
            return
        if not self.progress_overlay.isVisible():
            return

        rect = self.viewer.geometry()
        cx = rect.x() + rect.width() / 2 - self.progress_overlay.width() / 2
        cy = rect.y() + rect.height() / 2 - self.progress_overlay.height() / 2
        self.progress_overlay.move(int(cx), int(cy))


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "progress_overlay"):
            self._center_progress_overlay()


    def _increment_progress(self):
        """Naikkan progres secara halus hingga 95%."""
        val = self.progress.value()
        if val < 95:
            self.progress.setValue(val + 2)
        QApplication.processEvents()


    @contextmanager
    def freeze_ui(self):
        """Bekukan UI sementara dan tampilkan progress bar di tengah layar."""
        try:
            QApplication.processEvents()
            self.setUpdatesEnabled(False)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            self.progress.setValue(0)
            self.progress_overlay.show()
            self._center_progress_overlay()
            QApplication.processEvents()

            self._progress_timer = QTimer()
            self._progress_timer.timeout.connect(self._increment_progress)
            self._progress_timer.start(70)

            yield

        finally:
            if hasattr(self, "_progress_timer"):
                self._progress_timer.stop()

            self.progress.setValue(100)
            QApplication.processEvents()
            QTimer.singleShot(600, lambda: self.progress_overlay.hide())

            QApplication.restoreOverrideCursor()
            self.setUpdatesEnabled(True)
            self.repaint()

    def _load_adpp_fast(self, tps_filter=None):
        """Ambil data ADPP super cepat dari SQLCipher (cache per TPS)."""
        from db_manager import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.executescript("""
            PRAGMA temp_store = MEMORY;
            PRAGMA cache_size = 200000;
            PRAGMA synchronous = OFF;
        """)
        tbl_name = self.parent_window._active_table()

        # cache RAM per TPS
        cache_key = f"{tbl_name}_{tps_filter or 'ALL'}"
        self._cache_adpp = getattr(self, "_cache_adpp", {})
        if cache_key in self._cache_adpp:
            return self._cache_adpp[cache_key]

        if tps_filter:
            cur.execute(f"""
                SELECT NKK, NIK, NAMA, TMPT_LHR, TGL_LHR, STS, JK,
                    ALAMAT, RT, RW, DIS, KTPel, KET
                FROM {tbl_name}
                WHERE KET <> '0' AND TPS = ?
                ORDER BY RW, RT, NKK, NAMA;
            """, (tps_filter,))
        else:
            cur.execute(f"""
                SELECT NKK, NIK, NAMA, TMPT_LHR, TGL_LHR, STS, JK,
                    ALAMAT, RT, RW, DIS, KTPel, KET
                FROM {tbl_name}
                WHERE KET <> '0'
                ORDER BY TPS, RW, RT, NKK, NAMA;
            """)

        def stream_rows(cursor, size=800):
            while True:
                chunk = cursor.fetchmany(size)
                if not chunk:
                    break
                for row in chunk:
                    yield row

        rows = []
        for idx, r in enumerate(stream_rows(cur), start=1):
            safe = lambda x: str(x) if x not in (None, "None") else ""
            rows.append([str(idx), *[safe(v) for v in r]])

        self._cache_adpp[cache_key] = rows
        return rows

    # ===========================================================
    # GENERATE PDF
    # ===========================================================
    def generate_adpp_pdf(self, tps_filter=None):
        """Membuat PDF ADPP (KET ≠ 0) super cepat, dengan header dan footer 'Hal X dari Y'."""
        def draw_footer(canv: canvas.Canvas, doc):
            """Footer tengah: 'Hal X dari Y'."""
            page_num = canv.getPageNumber()
            text = f"Hal {page_num} dari {doc.page_count}"
            canv.saveState()
            canv.setFont(self._font_base, 7)
            canv.drawCentredString(
                landscape(A4)[0] / 2.0,  # posisi tengah (lebar kertas)
                0.5 * cm,               # jarak dari bawah
                text
            )
            canv.restoreState()

        if self.tahap == "DPHP":
            judul_tahapan = "DPS"
        elif self.tahap == "DPSHP":
            judul_tahapan = "DPSHP"
        elif self.tahap == "DPSHPA":
            judul_tahapan = "DPT"
        else:
            judul_tahapan = "DPHP"

        with self.freeze_ui():
            buf = BytesIO()
            doc = SimpleDocTemplate(
                buf,
                pagesize=landscape(A4),
                leftMargin=40, rightMargin=40, topMargin=20, bottomMargin=40,  # bottomMargin lebih besar untuk footer
            )

            # ---------- Locale ----------
            try:
                locale.setlocale(locale.LC_TIME, "id_ID.utf8")
            except Exception:
                try:
                    locale.setlocale(locale.LC_TIME, "Indonesian_indonesia.1252")
                except Exception:
                    pass

            story = []

            # ---------- Header Judul + Logo ----------
            base_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.join(base_dir, "KPU.png")
            if os.path.exists(logo_path):
                logo = RLImage(logo_path, width=1.5 * cm, height=1.6 * cm)
                judul_html = f"""
                    <b>DAFTAR PERUBAHAN PEMILIH UNTUK {judul_tahapan}</b><br/>
                    PEMILIHAN UMUM TAHUN 2029<br/>
                    OLEH PPS
                """
                teks_judul = Paragraph(judul_html, ParagraphStyle(
                    "TitleCenter",
                    fontName=self._font_bold,
                    fontSize=13,
                    alignment=TA_CENTER,
                    leading=14,
                ))

                tbl_title = Table([[logo, teks_judul, ""]],
                                colWidths=[3*cm, 20*cm, 3*cm],
                                hAlign="CENTER")
                tbl_title.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, 0), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 18),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                story.append(tbl_title)
                story.append(Spacer(1, 4))

            # ---------- Identitas Wilayah ----------
            nama_kec = self.kecamatan
            nama_desa = self.desa
            tps_text = f"{int(tps_filter):03d}" if (tps_filter and str(tps_filter).isdigit()) else str(tps_filter or "-")

            style_ident = ParagraphStyle(
                "IdentitasRapat",
                fontName=self._font_base,
                fontSize=10.5,
                leading=11,  # 🔹 lebih rapat dari default (biasanya 13)
                alignment=TA_LEFT,
            )

            data_identitas = [
                [Paragraph("PROVINSI", style_ident), Paragraph(":", style_ident), Paragraph("JAWA BARAT", style_ident),
                "", Paragraph("KECAMATAN", style_ident), Paragraph(":", style_ident), Paragraph(nama_kec, style_ident)],
                [Paragraph("KABUPATEN", style_ident), Paragraph(":", style_ident), Paragraph("TASIKMALAYA", style_ident),
                "", Paragraph("DESA", style_ident), Paragraph(":", style_ident), Paragraph(nama_desa, style_ident)],
                ["", "", "", "", Paragraph("TPS", style_ident), Paragraph(":", style_ident), Paragraph(tps_text, style_ident)],
            ]

            tabel_identitas = Table(
                data_identitas,
                colWidths=[3*cm, 0.3*cm, 5*cm, 11*cm, 3*cm, 0.3*cm, 4*cm],
                hAlign="CENTER",
            )
            tabel_identitas.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), self._font_base),
                ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),      # 🔹 lebih rapat
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),   # 🔹 lebih rapat
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(tabel_identitas)
            story.append(Spacer(1, 12))

            # ---------- Ambil data SQLCipher ----------
            from db_manager import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.executescript("""
                PRAGMA temp_store = MEMORY;
                PRAGMA cache_size = 200000;
                PRAGMA synchronous = OFF;
            """)
            cur.arraysize = 1000
            tbl_name = self.parent_window._active_table()

            cache_key = f"{tbl_name}_{tps_filter or 'ALL'}"
            self._cache_adpp = getattr(self, "_cache_adpp", {})
            if cache_key in self._cache_adpp:
                rows = self._cache_adpp[cache_key]
            else:
                if tps_filter:
                    cur.execute(f"""
                        SELECT NKK, NIK, NAMA, TMPT_LHR, TGL_LHR, STS, JK,
                            ALAMAT, RT, RW, DIS, KTPel, KET
                        FROM {tbl_name}
                        WHERE KET <> '0' AND TPS = ?
                        ORDER BY RW, RT, NKK, NAMA;
                    """, (tps_filter,))
                else:
                    cur.execute(f"""
                        SELECT NKK, NIK, NAMA, TMPT_LHR, TGL_LHR, STS, JK,
                            ALAMAT, RT, RW, DIS, KTPel, KET
                        FROM {tbl_name}
                        WHERE KET <> '0'
                        ORDER BY TPS, RW, RT, NKK, NAMA;
                    """)

                def stream_rows(cursor, size=800):
                    while True:
                        chunk = cursor.fetchmany(size)
                        if not chunk:
                            break
                        for r in chunk:
                            yield r

                rows = []
                for idx, r in enumerate(stream_rows(cur), start=1):
                    safe = lambda x: str(x) if x not in (None, "None") else ""
                    rows.append([str(idx), *[safe(v) for v in r]])
                self._cache_adpp[cache_key] = rows

            # ---------- Styles ----------
            wrap_left = ParagraphStyle("WrapLeft", fontName=self._font_base, fontSize=9, leading=10, alignment=TA_LEFT)
            center_header = ParagraphStyle("CenterHeader", fontName=self._font_bold, fontSize=9, leading=10, alignment=TA_CENTER)

            # ---------- Header ----------
            header_top = [
                [
                    Paragraph("<b>No</b>", center_header),
                    Paragraph("<b>No KK</b>", center_header),
                    Paragraph("<b>NIK</b>", center_header),
                    Paragraph("<b>Nama</b>", center_header),
                    Paragraph("<b>Tempat<br/>Lahir</b>", center_header),
                    Paragraph("<b>Tanggal<br/>Lahir</b>", center_header),
                    Paragraph("<b>Status<br/>Perkawinan<br/>B/S/P</b>", center_header),
                    Paragraph("<b>Jenis<br/>Kelamin<br/>L/P</b>", center_header),
                    Paragraph("<b>Alamat</b>", center_header),
                    Paragraph("<b>RT</b>", center_header),
                    Paragraph("<b>RW</b>", center_header),
                    Paragraph("<b>Disabilitas</b>", center_header),
                    Paragraph("<b>Status KTP-el</b>", center_header),
                    Paragraph("<b>Keterangan</b>", center_header),
                ],
                [Paragraph(str(i), center_header) for i in range(1, 15)],
            ]

            # ---------- Data ----------
            data_matrix = []
            for row in rows:
                new_row = []
                for i, val in enumerate(row):
                    text = val.strip().replace("\n", " ")
                    if i in (3, 4, 8):  # Nama, Tempat Lahir, Alamat wrap
                        new_row.append(Paragraph(text, wrap_left))
                    else:
                        new_row.append(text)
                data_matrix.append(new_row)

            table_matrix = header_top + (data_matrix if data_matrix else [[""] + [""]*13])

            t_data = LongTable(
                table_matrix,
                colWidths=[1*cm, 2.8*cm, 2.8*cm, 4.2*cm, 2.7*cm, 1.8*cm,
                        1.9*cm, 1.6*cm, 3.8*cm, 0.9*cm, 0.9*cm,
                        1*cm, 1.3*cm, 1.2*cm],
                repeatRows=2,
            )
            t_data.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.9, colors.black),
                ("BACKGROUND", (0, 0), (-1, 1), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, -1), self._font_base),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("WORDWRAP", (0, 0), (-1, -1), True),
            ]))
            story.append(t_data)

            # ---------- Build dua kali (agar dapat total halaman) ----------
            doc.build(story, canvasmaker=PageNumCanvas)
            pdf_bytes = buf.getvalue()
            buf.close()
            self._show_pdf_bytes(pdf_bytes)

    # ===========================================================
    # Navigasi TPS
    # ===========================================================
    def change_tps(self, step):
        if not self.tps_list:
            return
        self.current_tps_index = (self.current_tps_index + step) % len(self.tps_list)
        self.current_tps = self.tps_list[self.current_tps_index]
        self.lbl_tps.setText(f"TPS: {self.current_tps}")
        self.generate_adpp_pdf(tps_filter=self.current_tps)

    def create_placeholder_pdf(self):
        buf = BytesIO()
        styles = self._styles()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
        doc.build([Paragraph("Belum ada dokumen yang dibuat.", styles["CenterBold"])])
        self._show_pdf_bytes(buf.getvalue())

    def _show_pdf_bytes(self, pdf_bytes: bytes):
        """Tampilkan PDF langsung di QPdfView, bisa scroll semua halaman ke bawah."""
        try:
            # simpan buffer agar tidak hilang di garbage collector
            self._pdf_buffer = QBuffer()
            self._pdf_buffer.setData(pdf_bytes)
            self._pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly)

            # buat dokumen PDF
            self.document = QPdfDocument(self)
            status = self.document.load(self._pdf_buffer)

            # tampilkan di viewer
            self.viewer.setDocument(self.document)

            # ✅ mode scroll ke bawah semua halaman
            from PyQt6.QtPdfWidgets import QPdfView
            self.viewer.setPageMode(QPdfView.PageMode.MultiPage)
            #self.viewer.setZoomMode(QPdfView.ZoomMode.FitToWidth)

            total_pages = int(self.document.pageCount() or 0)
            #print(f"[PDF OK] Dokumen siap dengan {total_pages} halaman.")
        except Exception as e:
            print(f"[PDF Load Error] {e}")


    def kembali_ke_main(self):
        if self.parent_window:
            self.parent_window.showNormal()
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            self.parent_window.repaint()
            QTimer.singleShot(150, self.parent_window.repaint)
        self.close()

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

# =====================================================
# FORM BUAT AKUN BARU (REGISTER)
# =====================================================
class RegisterWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buat Akun Baru")
        self.conn = get_connection()
        self.showMaximized()

        # === Logo aplikasi di title bar ===
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "KPU.png")
        self.setWindowIcon(QIcon(logo_path))
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
        form_frame.setObjectName("FormFrame")
        form_frame.setFixedWidth(420)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(35)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 120))
        form_frame.setGraphicsEffect(shadow)

        # === Layout isi frame ===
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # === Logo KPU ===
        logo_label = QLabel()
        pixmap = QPixmap(logo_path)
        if pixmap.isNull():
            print(f"[PERINGATAN] Gambar tidak ditemukan di: {logo_path}")
        else:
            pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(logo_label)

        # === Teks judul atas ===
        title_label = QLabel("KOMISI PEMILIHAN UMUM<br>KABUPATEN TASIKMALAYA")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: black;
                font-size: 13pt;
                font-weight: bold;
                font-family: 'Segoe UI';
                margin-bottom: 10px;
            }
        """)
        form_layout.addWidget(title_label)

        # === Subjudul registrasi ===
        subtitle = QLabel("✨ Buat Akun Baru ✨")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size:16pt; font-weight:bold; color:#ff9900; margin:10px 0;")
        form_layout.addWidget(subtitle)

        # === Nama Lengkap ===
        self.nama = QLineEdit()
        self.nama.setPlaceholderText("Nama Lengkap")
        self.nama.textChanged.connect(lambda t: self.nama.setText(t.upper()) if t != t.upper() else None)
        form_layout.addWidget(self.nama)

        # === Email ===
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email Aktif")
        form_layout.addWidget(self.email)

        # === Kecamatan ===
        self.kecamatan = QLineEdit()
        self.kecamatan.setPlaceholderText("Ketik Kecamatan...")
        self.kecamatan.textChanged.connect(lambda t: self.kecamatan.setText(t.upper()) if t != t.upper() else None)
        kec_list = get_kecamatan()
        completer = QCompleter(kec_list, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.kecamatan.setCompleter(completer)
        self.kecamatan.textChanged.connect(self.update_desa)
        form_layout.addWidget(self.kecamatan)

        # === Desa ===
        self.desa = QComboBox()
        self.desa.addItem("-- Pilih Desa --")
        form_layout.addWidget(self.desa)

        # === Password & Konfirmasi ===
        for field, placeholder in [(1, "Password"), (2, "Tulis Ulang Password")]:
            hbox = QHBoxLayout()
            pw = QLineEdit()
            pw.setPlaceholderText(placeholder)
            pw.setEchoMode(QLineEdit.EchoMode.Password)

            toggle = QPushButton("👁")
            toggle.setFixedWidth(40)
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle.installEventFilter(self)
            toggle.setStyleSheet("""
                QPushButton {
                    font-size: 12pt;
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    color: #ff6600;
                    background-color: rgba(255,102,0,0.15);
                    border-radius: 6px;
                }
            """)
            toggle.clicked.connect(lambda _, f=pw: self.toggle_password(f))

            hbox.addWidget(pw)
            hbox.addWidget(toggle)
            form_layout.addLayout(hbox)

            if field == 1:
                self.password = pw
            else:
                self.password2 = pw

        # === Captcha ===
        self.captcha_code = self.generate_captcha()
        self.captcha_label = QLabel()
        self.captcha_label.setFixedHeight(60)
        self.captcha_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.refresh_captcha_image()

        self.refresh_btn = QPushButton("🔄️")    #🔃🔄️💫
        self.refresh_btn.setFixedWidth(40)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.installEventFilter(self)
        self.refresh_btn.clicked.connect(self.refresh_captcha_image)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                font-size: 14pt;
                font-weight: bold;
                color: #000;
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                color: #ff6600;
                background-color: rgba(255,102,0,0.15);
                border-radius: 6px;
            }
        """)


        captcha_layout = QHBoxLayout()
        captcha_layout.addWidget(self.captcha_label)
        captcha_layout.addWidget(self.refresh_btn)
        form_layout.addLayout(captcha_layout)

        self.captcha_input = QLineEdit()
        self.captcha_input.textChanged.connect(lambda t: self.captcha_input.setText(t.upper()) if t != t.upper() else None)
        self.captcha_input.setPlaceholderText("Tulis ulang captcha di atas")
        form_layout.addWidget(self.captcha_input)

        # === Tombol Buat Akun ===
        self.btn_buat = QPushButton("Buat Akun")
        self.btn_buat.clicked.connect(self.create_account)
        self.btn_buat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_buat.setStyleSheet("""
            QPushButton {
                background-color: #d71d1d;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #ff6600;
            }
        """)
        form_layout.addWidget(self.btn_buat)

        # === Tempel layout ke frame & frame ke tampilan utama ===
        form_frame.setLayout(form_layout)
        outer_layout.addWidget(form_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        central_widget = QWidget()
        central_widget.setLayout(outer_layout)
        self.setCentralWidget(central_widget)

        # === Style global ===
        self.setStyleSheet("""
            QWidget {
                font-size: 11pt;
                color: black;
                background-color: #ffffff;
            }
            QFrame#FormFrame {
                background-color: #F0F0F0;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 10px;
                padding: 30px 40px;
            }
            QLabel {
                background-color: transparent;
                color: black;
            }
            QLineEdit, QComboBox {
                min-height: 28px;
                font-size: 11pt;
                border: 1px solid #222;
                border-radius: 4px;
                padding-left: 8px;
                background-color: #ffffff;
                color: black;
            }
            /* === Style untuk dropdown ComboBox === */
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #ff9900;
                selection-color: #ffffff;
                border: 1px solid #666;
                outline: none;
            }
            /* === Style popup QCompleter agar sama === */
            QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #ff9900;
                selection-color: #ffffff;
                border: 1px solid #666;
                outline: none;
            }
        """)


    # ===================================================
    # 🔹 Helper untuk captcha dan interaksi UI
    # ===================================================
    def eventFilter(self, obj, event):
        if isinstance(obj, QPushButton) and obj.text() in ("👁", "🔄️"):
            if event.type() == QEvent.Type.Enter:
                obj.setStyleSheet("""
                    QPushButton {
                        font-size: 16pt;
                        font-weight: bold;
                        color: #ff6600;
                        background: transparent;
                        border: none;
                        border-radius: 6px;
                        transition: all 0.2s;
                    }
                """)
            elif event.type() == QEvent.Type.Leave:
                obj.setStyleSheet("""
                    QPushButton {
                        font-size: 13pt;
                        font-weight: bold;
                        color: #000;
                        background: transparent;
                        border: none;
                        transition: all 0.2s;
                    }
                """)
        return super().eventFilter(obj, event)


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
        font = QFont("Segoe UI", 22, QFont.Weight.Bold)
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

    # =========================================================
    # 🔐 Buat Akun + Aktivasi OTP (UX modern, anti-hang)
    # =========================================================
    def create_account(self):
        nama = self.nama.text().strip()
        email = self.email.text().strip()
        kecamatan = self.kecamatan.text().strip()
        desa = self.desa.currentText().strip()
        pw = self.password.text().strip()
        pw2 = self.password2.text().strip()
        captcha = self.captcha_input.text().strip()

        import re
        # 🔹 Validasi dasar
        if not all([nama, email, kecamatan, desa, pw, pw2, captcha]):
            show_modern_warning(self, "Error", "Semua kolom harus diisi!")
            return
        if "@" not in email or "." not in email:
            show_modern_warning(self, "Error", "Format email tidak valid!")
            return
        if pw != pw2:
            show_modern_warning(self, "Error", "Password tidak sama!")
            return
        if len(pw) < 8 or not re.search(r"[A-Z]", pw) or not re.search(r"[0-9]", pw) or not re.search(r"[^A-Za-z0-9]", pw):
            show_modern_warning(
                self, "Error",
                "Password harus minimal 8 karakter dan memuat minimal:\n"
                "- 1 huruf kapital\n- 1 angka\n- 1 simbol (!@#$%^&*)"
            )
            return
        if captcha != self.captcha_code:
            show_modern_warning(self, "Error", "Captcha salah! Coba lagi.")
            self.refresh_captcha_image()
            return
        
        # 🔒 Hash password + salt (email)
        salted_input = (pw + email).encode("utf-8")
        hashed_pw = hashlib.sha256(salted_input).hexdigest()

        # Simpan akun baru ke DB
        from db_manager import get_connection
        conn = get_connection()
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

        otp_secret = pyotp.random_base32()
        cur.execute("DELETE FROM users")
        cur.execute(
            "INSERT INTO users (nama, email, kecamatan, desa, password, otp_secret) VALUES (?, ?, ?, ?, ?, ?)",
            (nama, email, kecamatan, desa, hashed_pw, otp_secret)
        )
        conn.commit()

        # 🔹 Generate QR untuk OTP
        totp_uri = pyotp.TOTP(otp_secret).provisioning_uri(
            name=email,
            issuer_name="NexVo"
        )

        qr = qrcode.make(totp_uri)
        buf = BytesIO(); qr.save(buf, format="PNG")
        pix = QPixmap(); pix.loadFromData(buf.getvalue())

        # === Dialog QR ===
        qr_dialog = QDialog(self)
        qr_dialog.setWindowTitle("Aktivasi OTP")
        qr_dialog.setFixedSize(460, 600)
        qr_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        qr_dialog.setStyleSheet("""
            QDialog { background:#111; color:white; border-radius:16px; border:1px solid #444; }
            QLabel { font-family:'Segoe UI'; }
            QPushButton {
                background:#ff6600; color:white;
                border:none; border-radius:8px;
                padding:10px 22px; font-weight:bold; font-size:11pt;
            }
            QPushButton:hover { background:#d71d1d; }
        """)

        vbox = QVBoxLayout(qr_dialog)
        vbox.setContentsMargins(36, 36, 36, 36)
        vbox.setSpacing(18)

        title = QLabel("🔐 <b>Aktivasi Keamanan OTP</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:15pt; color:#ffcc66;")
        vbox.addWidget(title)

        desc = QLabel("Scan kode berikut menggunakan <b>Google Authenticator</b> atau <b>Authy</b>.")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("font-size:11pt; color:#ddd;")
        vbox.addWidget(desc)

        img = QLabel()
        img.setPixmap(pix.scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("background:#000; border-radius:10px; padding:10px;")
        vbox.addWidget(img)

        manual = QLabel(f"<i>Atau masukkan kode manual:</i><br><b>{otp_secret}</b>")
        manual.setAlignment(Qt.AlignmentFlag.AlignCenter)
        manual.setWordWrap(True)
        manual.setStyleSheet("color:#00ff99; font-size:11pt;")
        vbox.addWidget(manual)

        btn = QPushButton("✅ Saya Sudah Scan")
        btn.setFixedSize(240, 46)
        vbox.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # klik tombol langsung lanjut ke input OTP
        def lanjut_verifikasi():
            qr_dialog.accept()
            QTimer.singleShot(300, lambda: self._verify_otp_flow(otp_secret))
        btn.clicked.connect(lanjut_verifikasi)

        qr_dialog.exec()


    # =========================================================
    # 🔢 Alur Verifikasi OTP (tanpa popup ganda, UX halus)
    # =========================================================
    def _verify_otp_flow(self, otp_secret: str):
        """
        Menangani proses verifikasi OTP setelah user scan QR.
        Anti-hang, popup tunggal, dan bisa retry 3x.
        """
        totp = pyotp.TOTP(otp_secret)

        for attempt in range(3):
            code = self._prompt_otp_code_dialog()
            if code is None:
                show_modern_warning(self, "Dibatalkan", "Verifikasi OTP dibatalkan.")
                return

            # ✅ OTP valid
            if totp.verify(code, valid_window=1):
                show_modern_info(self, "Sukses", "Akun NexVo anda berhasil dibuat!")
                self.close()
                self.login_window = LoginWindow()
                self.login_window.show()
                return
        show_modern_error(self, "Gagal", "Verifikasi OTP gagal 3 kali. Silakan scan ulang QR dan coba lagi.")

    # =========================================================
    # 🧾 Dialog Input OTP (fokus ulang saat salah)
    # =========================================================
    def _prompt_otp_code_dialog(self):
        """
        Dialog kecil untuk input OTP 6 digit, tanpa tumpang tindih popup.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Verifikasi OTP")
        dlg.setFixedSize(360, 190)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        dlg.setStyleSheet("""
            QDialog { background:#FFFFFF; color:black; border-radius:10px; border:1px solid #444; }
            QLabel { font-family:'Segoe UI'; font-size:11pt; }
            QLineEdit {
                font-size:16pt; font-family:'Consolas';
                background:#DDDDDD; color:black;
                border:1px solid #555; border-radius:8px;
                padding:6px 12px; letter-spacing:2px;
            }
            QPushButton {
                background:#ff6600; color:white;
                border:none; border-radius:8px;
                padding:8px 16px; font-weight:bold; min-width:100px;
            }
            QPushButton:hover { background:#d71d1d; }
            QPushButton#cancel { background:#333; color:white; }
            QPushButton#cancel:hover { background:#444; }
        """)

        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(22, 20, 22, 18)
        vbox.setSpacing(14)

        info = QLabel("Masukkan 6 digit kode OTP dari aplikasi authenticator Anda.")
        info.setWordWrap(True)
        vbox.addWidget(info)

        otp_input = QLineEdit()
        otp_input.setMaxLength(6)
        otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        otp_input.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,6}$")))
        vbox.addWidget(otp_input)

        hbox = QHBoxLayout()
        btn_cancel = QPushButton("Batal")
        btn_cancel.setObjectName("cancel")
        btn_ok = QPushButton("Verifikasi")
        hbox.addWidget(btn_cancel)
        hbox.addWidget(btn_ok)
        vbox.addLayout(hbox)

        code_holder = {"val": None}

        def do_verify():
            code = otp_input.text().strip()
            if len(code) == 6 and code.isdigit():
                code_holder["val"] = code
                dlg.accept()
            else:
                # ❗ Tidak munculkan popup baru, cukup 1 per dialog
                show_modern_warning(dlg, "Format Salah", "Kode OTP harus 6 digit angka!")
                otp_input.setFocus()
                otp_input.selectAll()

        def do_cancel():
            dlg.reject()

        btn_ok.clicked.connect(do_verify)
        btn_cancel.clicked.connect(do_cancel)
        otp_input.returnPressed.connect(btn_ok.click)

        dlg.exec()
        return code_holder["val"]


#if __name__ == "__main__":
    # 🔹 Inisialisasi database terenkripsi (hanya sekali)
#    from db_manager import bootstrap, close_connection
#    conn = bootstrap()

#    if conn is None:
#        QMessageBox.critical(None, "Kesalahan Fatal", "Gagal inisialisasi database. Aplikasi akan keluar.")
#        sys.exit(1)

    # 🔹 Jalankan aplikasi Qt
#    app = QApplication(sys.argv)
#    app.setStyle(QStyleFactory.create("Fusion"))
#    apply_global_palette(app, mode="light")
#    app.setApplicationName("NexVo")

    # 🔹 Jalankan halaman login
#    win = LoginWindow(conn)
#    win.show()  # showMaximized sudah di dalam __init__

    # 🔹 Tangani penutupan koneksi saat aplikasi ditutup
#    exit_code = app.exec()
#    close_connection()
#    sys.exit(exit_code)



# ==========================================================
# 🚀 Entry point dengan Mode DEV opsional
# ==========================================================
if __name__ == "__main__":
    from db_manager import bootstrap, close_connection, DB_PATH
    from PyQt6.QtWidgets import QApplication, QMessageBox
    import sys

    # 🔹 Inisialisasi database terenkripsi (hanya sekali)
    conn = bootstrap()
    if conn is None:
        QMessageBox.critical(None, "Kesalahan Fatal", "Gagal inisialisasi database. Aplikasi akan keluar.")
        sys.exit(1)

    # 🔹 Bangun aplikasi Qt
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    apply_global_palette(app, mode="light")
    app.setApplicationName("NexVo")

    # ===================================================
    # 🔹 Cek apakah mode DEV diaktifkan
    # ===================================================
    try:
        if is_dev_mode_requested():
            if confirm_dev_mode(None):
                print("[DEV MODE] Melewati proses login & OTP...")
                dev_nama = "Riparip"
                dev_kecamatan = "SINGAPARNA"
                dev_desa = "CIKADONGDONG"
                dev_tahapan = "DPHP"

                mw = MainWindow(dev_nama, dev_kecamatan, dev_desa, str(DB_PATH), dev_tahapan)
                mw.show()

                # ✅ Tutup koneksi SQLCipher dengan aman saat keluar
                exit_code = app.exec()
                close_connection()
                sys.exit(exit_code)
            else:
                print("[INFO] Mode DEV dibatalkan oleh user.")
    except NameError:
        # fallback jika belum didefinisikan
        print("[WARN] Fungsi is_dev_mode_requested() / confirm_dev_mode() belum didefinisikan.")

    # ===================================================
    # 🔹 Mode normal → tampilkan login
    # ===================================================
    win = LoginWindow(conn)
    win.show()

    # ✅ Tutup koneksi SQLCipher dengan aman saat keluar
    exit_code = app.exec()
    close_connection()
    sys.exit(exit_code)