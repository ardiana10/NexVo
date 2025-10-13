﻿# -*- coding: utf-8 -*-
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

import os, sys, subprocess, csv, hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
import random, string, re
from io import BytesIO
import pyotp, qrcode
from PyQt6.QtGui import QPainter, QPen, QRegularExpressionValidator
from PyQt6.QtWidgets import QCompleter
from db_manager import (
    close_connection,
    get_connection,
    with_safe_db,
    bootstrap,
    connect_encrypted,
    hapus_semua_data,
)

# --- DB ---
try:
    from sqlcipher3 import dbapi2 as sqlcipher
except Exception as e:
    print("[ERROR] sqlcipher3 belum terpasang. Install: pip install sqlcipher3-wheels (Windows) atau sqlcipher3.")
    raise

# --- UI ---
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QRegularExpression, QRect, QEvent
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPainter, QAction, QPalette
from PyQt6.QtWidgets import (QSizePolicy, QToolBar, QStatusBar, QHeaderView, QTableWidget, QFileDialog, QScrollArea, QFormLayout, 
    QApplication, QWidget, QMainWindow, QLabel, QLineEdit, QPushButton, QComboBox, QDialog, QGraphicsOpacityEffect, QCheckBox, 
    QVBoxLayout, QHBoxLayout, QFrame, QMessageBox, QGraphicsDropShadowEffect, QInputDialog, QTableWidgetItem, QStyledItemDelegate, 
    QSlider, QGridLayout, QRadioButton, QDockWidget, QMenu, QStackedWidget, QAbstractItemView, QStyle
)

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
    Membuat semua tabel utama (users, kecamatan, dphp, dpshp, dpshpa)
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

    conn.commit()

    # --- Cek tabel kecamatan ---
    try:
        cur.execute("SELECT COUNT(*) FROM kecamatan")
        count = cur.fetchone()[0]
    except Exception:
        count = 0  # kalau tabel belum siap, abaikan tapi log

    # --- Isi tabel kecamatan jika kosong ---
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

    # ✅ Tidak menutup koneksi


def hapus_semua_data(conn):
    """Kosongkan seluruh tabel di nexvo.db (users, dphp, dpshp, dpshpa)."""
    cur = conn.cursor()
    for tbl in ("users", "dphp", "dpshp", "dpshpa"):
        cur.execute(f"DELETE FROM {tbl};")
    conn.commit()

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
        value = index.data(Qt.ItemDataRole.CheckStateRole)
        if value is None:
            super().paint(painter, option, index)
            return

        # 🔹 Konversi nilai
        try:
            state = Qt.CheckState(value)
        except Exception:
            state = Qt.CheckState.Unchecked

        # 🔹 Matikan highlight seleksi (hilangkan abu gelap)
        option.state &= ~QStyle.StateFlag.State_Selected
        option.state &= ~QStyle.StateFlag.State_HasFocus

        rect = self.get_checkbox_rect(option)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # === Checkbox belum dicentang ===
        if state == Qt.CheckState.Unchecked:
            painter.setBrush(Qt.BrushStyle.NoBrush)      # transparan
            painter.setPen(QPen(QColor("#A0A0A0"), 1.2)) # border hitam tipis
            painter.drawRoundedRect(rect, 3, 3)

        # === Checkbox dicentang ===
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)      # tetap transparan
            painter.setPen(QPen(QColor("#000000"), 1.2)) # border hitam
            painter.drawRoundedRect(rect, 3, 3)

            # gambar centang merah
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
        btn_simpan.clicked.connect(self.save_settings)

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
            font.setPointSize(font.pointSize() - 1)
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
                padding: 1px 0px;
                margin-top: 1px;
            }

            QMenu::item {
                background-color: transparent;
                padding: 3px 3px;              /* pas proporsional */
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

        btn_rekap = QPushButton("Rekap")
        self.style_button(btn_rekap, bg="#d71d1d", fg="white", bold=True)
        toolbar.addWidget(btn_rekap)

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
        btn_urutkan = QPushButton("Urutkan")
        self.style_button(btn_urutkan, bg="#d71d1d", fg="white", bold=True)
        btn_urutkan.clicked.connect(self.sort_data) #belum ada fungsi
        toolbar.addWidget(btn_urutkan)
        add_spacer()

        btn_cekdata = QPushButton("Cek Data")
        self.style_button(btn_cekdata, bg="#d71d1d", fg="white", bold=True)
        btn_cekdata.clicked.connect(self.cek_data) #belum ada fungsi
        toolbar.addWidget(btn_cekdata)
        add_spacer()

        btn_tools = QPushButton("Tools")
        self.style_button(btn_tools, bg="#d71d1d", fg="white", bold=True)
        toolbar.addWidget(btn_tools)
        add_spacer()

        btn_filter = QPushButton("Filter")
        self.style_button(btn_filter, bg="#d71d1d", fg="white", bold=True)
        btn_filter.setIcon(QIcon.fromTheme("view-filter")) # type: ignore
        btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        #btn_filter.clicked.connect(self.toggle_filter_sidebar)
        toolbar.addWidget(btn_filter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # === Style tipis elegan ===
        self.status.setStyleSheet("""
            QStatusBar {
                background-color: #fbfbfa;
                border-top: 1px solid #fbfbfa;
                padding: 0px 8px;
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

        # --- Batch flags & stats (aman dari AttributeError) ---
        self._batch_stats = {"ok": 0, "rejected": 0, "skipped": 0}
        self._in_batch_mode = False
        self._warning_shown_in_batch = {}
        self._install_safe_shutdown_hooks()
        self.sort_lastupdate_asc = True

        self.current_page = 1
        self.rows_per_page = 300
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

        # 🔹 Hilangkan highlight seleksi permanen
        #self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.make_table_text_selectable()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        #self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
                font-size: 9pt;
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
        #QTimer.singleShot(0, self.init_header_checkbox)

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
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = self.mapFromGlobal(event.globalPosition().toPoint())
            if not self.table.geometry().contains(pos):
                self._safe_clear_selection()

        if obj == self.table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                index = self.table.indexAt(event.pos())
                if not index.isValid():
                    self._safe_clear_selection()
            elif event.type() == QEvent.Type.Leave:
                self._safe_clear_selection()

        return super().eventFilter(obj, event)


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
    
    # =========================================================
    # DASHBOARD PAGE
    # =========================================================
    def show_dashboard_page(self):
        """Tampilkan Dashboard elegan (dengan animasi, tanpa status bar)."""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect, QToolBar
        from PyQt6.QtGui import QIcon
        import os

        # === Pastikan self.stack masih valid ===
        if not hasattr(self, "stack") or self.stack is None:
            show_modern_error(self, "Error", "Elemen utama (stack) telah dihapus. Mohon restart aplikasi.")
            return

        # === Pastikan ikon aplikasi (KPU.png) muncul di kiri atas ===
        icon_path = os.path.join(os.path.dirname(__file__), "KPU.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # === Siapkan dashboard ===
        if not hasattr(self, "dashboard_page") or self.dashboard_page is None:
            self.dashboard_page = self._build_dashboard_widget()
            self.stack.addWidget(self.dashboard_page)

        elif self.stack.indexOf(self.dashboard_page) == -1:
            # Jika dashboard_page pernah dihapus, tambahkan lagi
            print("STACK:", self.stack)
            print("DASHBOARD:", getattr(self, "dashboard_page", None))
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
        if hasattr(self, "action_light"):
            self.action_light.setEnabled(False)
            f = self.action_light.font()
            f.setItalic(True)
            self.action_light.setFont(f)

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

        #self.header_checkbox.blockSignals(True)
        #if checked_cnt == 0:
        #    self.header_checkbox.setCheckState(Qt.CheckState.Unchecked)
        #elif checked_cnt == total:
        #    self.header_checkbox.setCheckState(Qt.CheckState.Checked)
        #else:
        #    self.header_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        #self.header_checkbox.blockSignals(False)

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
            ("✏️ Lookup", lambda: self._context_action_wrapper(checked_rows, self.lookup_pemilih)),
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

    # =========================================================
    # 🔹 1. AKTIFKAN PEMILIH (versi batch optimized)
    # =========================================================
    def aktifkan_pemilih(self, row):
        from datetime import datetime
        from db_manager import get_connection

        dpid_item = self.table.item(row, self.col_index("DPID"))
        ket_item  = self.table.item(row, self.col_index("KET"))
        nama_item = self.table.item(row, self.col_index("NAMA"))

        dpid = dpid_item.text().strip() if dpid_item else ""
        ket  = ket_item.text().strip().upper() if ket_item else ""
        nama = nama_item.text().strip() if nama_item else ""

        # ⚠️ Validasi
        if not dpid or dpid == "0" or ket not in ("1", "2", "3", "4", "5", "6", "7", "8"):
            if getattr(self, "_in_batch_mode", False):
                if not self._warning_shown_in_batch.get("aktifkan_pemilih", False):
                    self._warning_shown_in_batch["aktifkan_pemilih"] = True
            else:
                show_modern_warning(self, "Ditolak", f"{nama} adalah Pemilih Aktif atau tidak bisa diubah.")
            self._batch_add("rejected", "aktifkan_pemilih")
            return

        # ✅ Update kolom KET jadi 0
        ket_item.setText("0")
        self.update_database_field(row, "KET", "0")

        gi = self._global_index(row)
        if 0 <= gi < len(self.all_data):
            self.all_data[gi]["KET"] = "0"

        # 🕓 Isi kolom LastUpdate (DD/MM/YYYY)
        today_str = datetime.now().strftime("%d/%m/%Y")
        last_update_col = self.col_index("LastUpdate")
        if last_update_col != -1:
            lu_item = self.table.item(row, last_update_col)
            if not lu_item:
                lu_item = QTableWidgetItem()
                self.table.setItem(row, last_update_col, lu_item)
            lu_item.setText(today_str)

        if 0 <= gi < len(self.all_data):
            self.all_data[gi]["LastUpdate"] = today_str

        # 🔹 Update ke database sesuai tahapan aktif (batch aware)
        try:
            tbl = self._active_table()
            if not tbl:
                return

            # === Mode batch: gunakan shared cursor ===
            if getattr(self, "_in_batch_mode", False):
                if not hasattr(self, "_shared_cur") or not self._shared_cur:
                    conn = get_connection()
                    self._shared_conn = conn
                    self._shared_cur = conn.cursor()
                    conn.execute("PRAGMA busy_timeout = 3000;")
                    self._shared_query_count = 0

                cur = self._shared_cur
                cur.execute(f"UPDATE {tbl} SET LastUpdate = ? WHERE DPID = ?", (today_str, dpid))
                self._shared_query_count += 1

                # Commit tiap 1000 baris (agar aman)
                if self._shared_query_count % 1000 == 0:
                    self._shared_conn.commit()

            else:
                # === Mode normal (non-batch): commit langsung ===
                conn = get_connection()
                cur = conn.cursor()
                conn.execute("PRAGMA busy_timeout = 3000;")
                cur.execute(f"UPDATE {tbl} SET LastUpdate = ? WHERE DPID = ?", (today_str, dpid))
                conn.commit()

        except Exception as e:
            print("[DB ERROR] aktifkan_pemilih:", e)

        # 🌗 Warna sesuai tema
        self._warnai_baris_berdasarkan_ket()
        self._terapkan_warna_ke_tabel_aktif()

        # ✅ Catat batch sukses
        self._batch_add("ok", "aktifkan_pemilih")

        # ✅ Non-batch mode → langsung simpan & tampilkan info
        if not getattr(self, "_in_batch_mode", False):
            self._flush_db("aktifkan_pemilih")
            show_modern_info(self, "Aktifkan", f"{nama} telah diaktifkan kembali.")


    # =========================================================
    # 🔹 2. HAPUS PEMILIH (versi batch-optimized)
    # =========================================================
    @with_safe_db
    def hapus_pemilih(self, row, conn=None):
        """Menghapus baris pemilih dari tabel sesuai tahapan aktif (aman & super cepat)."""
        from db_manager import get_connection

        # --- Ambil item dari tabel
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
        rowid = self.all_data[gi].get("rowid") or self.all_data[gi].get("_rowid_")
        if not rowid:
            show_modern_error(self, "Error", "ROWID tidak ditemukan — data tidak dapat dihapus.")
            self._batch_add("skipped", "hapus_pemilih")
            return

        last_update = sig.get("LastUpdate", "").strip()  # biarkan tetap DD/MM/YYYY

        # ✅ Tentukan tabel sesuai tahapan aktif
        tbl = self._active_table()
        if not tbl:
            show_modern_error(self, "Error", "Tahapan tidak valid — tabel tujuan tidak ditemukan.")
            self._batch_add("skipped", "hapus_pemilih")
            return

        try:
            # ===========================================
            # 🟢 1. Batch Mode → Simpan ke cursor bersama
            # ===========================================
            if getattr(self, "_in_batch_mode", False):
                if not hasattr(self, "_shared_cur") or not self._shared_cur:
                    # Buat shared cursor baru untuk batch
                    conn = get_connection()
                    self._shared_conn = conn
                    self._shared_cur = conn.cursor()
                    conn.execute("PRAGMA busy_timeout = 3000;")
                    self._shared_query_count = 0

                cur = self._shared_cur
                cur.execute(f"""
                    DELETE FROM {tbl}
                    WHERE rowid = ?
                    AND IFNULL(NIK,'') = ?
                    AND IFNULL(NKK,'') = ?
                    AND (IFNULL(DPID,'') = ? OR DPID IS NULL)
                    AND IFNULL(TGL_LHR,'') = ?
                    AND IFNULL(LastUpdate,'') = ?
                """, (
                    rowid,
                    sig.get("NIK", ""),
                    sig.get("NKK", ""),
                    sig.get("DPID", ""),
                    sig.get("TGL_LHR", ""),
                    last_update
                ))

                self._shared_query_count += 1

                # Commit otomatis tiap 1000 operasi (supaya cepat tapi tetap aman)
                if self._shared_query_count % 1000 == 0:
                    self._shared_conn.commit()

            # ===========================================
            # 🔹 2. Mode Normal (Non-batch)
            # ===========================================
            else:
                conn = get_connection()
                cur = conn.cursor()
                conn.execute("PRAGMA busy_timeout = 3000;")

                cur.execute(f"""
                    DELETE FROM {tbl}
                    WHERE rowid = ?
                    AND IFNULL(NIK,'') = ?
                    AND IFNULL(NKK,'') = ?
                    AND (IFNULL(DPID,'') = ? OR DPID IS NULL)
                    AND IFNULL(TGL_LHR,'') = ?
                    AND IFNULL(LastUpdate,'') = ?
                """, (
                    rowid,
                    sig.get("NIK", ""),
                    sig.get("NKK", ""),
                    sig.get("DPID", ""),
                    sig.get("TGL_LHR", ""),
                    last_update
                ))

                conn.commit()

            # ✅ Hapus dari memori
            del self.all_data[gi]

            # Mundurkan halaman jika kosong
            if (self.current_page > 1) and ((self.current_page - 1) * self.rows_per_page >= len(self.all_data)):
                self.current_page -= 1

            if not getattr(self, "_in_batch_mode", False):
                show_modern_info(self, "Selesai", f"{nama} berhasil dihapus dari {tbl.upper()}!")

            self._batch_add("ok", "hapus_pemilih")

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal menghapus data:\n{e}")
            self._batch_add("skipped", "hapus_pemilih")

        # ===========================================
        # 🔚 3. Tutup batch di akhir proses massal
        # ===========================================
        if not getattr(self, "_in_batch_mode", False) and hasattr(self, "_shared_conn"):
            try:
                self._shared_conn.commit()
                self._shared_conn.close()
                self._shared_cur = None
                self._shared_conn = None
            except Exception:
                pass


    # =========================================================
    # 🔹 3. STATUS PEMILIH (versi batch optimized)
    # =========================================================
    def set_ket_status(self, row, new_value: str, label: str):
        from datetime import datetime
        from db_manager import get_connection

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

        # --- Update kolom KET
        ket_item = self.table.item(row, self.col_index("KET"))
        if ket_item and ket_item.text().strip() == new_value:
            return

        if ket_item:
            ket_item.setText(new_value)
            self.update_database_field(row, "KET", new_value)

        gi = self._global_index(row)
        if 0 <= gi < len(self.all_data):
            self.all_data[gi]["KET"] = new_value

        # --- Jika KET hasilnya 1–8 → isi LastUpdate
        if new_value in ("1", "2", "3", "4", "5", "6", "7", "8"):
            today_str = datetime.now().strftime("%d/%m/%Y")
            last_update_col = self.col_index("LastUpdate")
            if last_update_col != -1:
                lu_item = self.table.item(row, last_update_col)
                if not lu_item:
                    lu_item = QTableWidgetItem()
                    self.table.setItem(row, last_update_col, lu_item)
                lu_item.setText(today_str)

            if 0 <= gi < len(self.all_data):
                self.all_data[gi]["LastUpdate"] = today_str

            # 🔹 Update database (batch-aware)
            try:
                tbl = self._active_table()
                if not tbl:
                    return

                dpid = dpid_item.text().strip()

                if getattr(self, "_in_batch_mode", False):
                    # === MODE BATCH: shared cursor ===
                    if not hasattr(self, "_shared_cur") or not self._shared_cur:
                        conn = get_connection()
                        self._shared_conn = conn
                        self._shared_cur = conn.cursor()
                        conn.execute("PRAGMA busy_timeout = 3000;")
                        self._shared_query_count = 0

                    cur = self._shared_cur
                    cur.execute(f"UPDATE {tbl} SET LastUpdate = ? WHERE DPID = ?", (today_str, dpid))
                    self._shared_query_count += 1

                    # Commit setiap 1000 baris biar aman
                    if self._shared_query_count % 1000 == 0:
                        self._shared_conn.commit()

                else:
                    # === MODE NORMAL: commit langsung ===
                    conn = get_connection()
                    cur = conn.cursor()
                    conn.execute("PRAGMA busy_timeout = 3000;")
                    cur.execute(f"UPDATE {tbl} SET LastUpdate = ? WHERE DPID = ?", (today_str, dpid))
                    conn.commit()

            except Exception as e:
                print("[DB ERROR] set_ket_status:", e)

        # 🎨 Warnai merah (status TMS)
        self._warnai_baris_berdasarkan_ket()
        self._terapkan_warna_ke_tabel_aktif()

        # ✅ Catat batch sukses
        self._batch_add("ok", f"set_ket_status_{label}")

        # ✅ Non-batch mode → langsung simpan dan tampilkan notifikasi
        if not getattr(self, "_in_batch_mode", False):
            self._flush_db("set_ket_status")
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
                "Apakah kamu yakin ingin menjalankan proses <b>Cek Data</b>?<br><br>"
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
            self.sort_data()

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

            elif cek_data_val in (
                "NKK Invalid", "Potensi NKK Invalid",
                "NIK Invalid", "Potensi NIK Invalid",
                "Potensi Dibawah Umur", "Dibawah Umur",
                "Ganda Aktif", "Beda TPS", "Tidak Padan"
            ):
                # 4️⃣ CEK_DATA bermasalah → biru
                brush = warna_cache["biru"]

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
                print(f"[DEBUG] Jumlah baris di tabel {tbl_name.upper()}: {total}")

                # === Refresh tampilan ===
                try:
                    self.load_data_from_db()    
                    self.update_pagination()
                    self.show_page(1)
                    self.connect_header_events()
                    self.sort_data(auto=True)
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
        """Memuat seluruh data dari database ke self.all_data (SQLCipher-safe)."""

        # 1️⃣ Pastikan tabel dan skema valid
        self._ensure_schema_and_migrate()

        conn = get_connection()
        conn.row_factory = sqlcipher.Row
        cur = conn.cursor()

        tahap = self._tahapan.strip().upper()
        tabel_map = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}
        tbl_name = tabel_map.get(tahap, "data_pemilih")

        # Optimasi baca tanpa mengorbankan keamanan
        cur.executescript("""
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;
            PRAGMA temp_store = MEMORY;
            PRAGMA cache_size = 100000;
        """)

        # 2️⃣ Ambil seluruh data dari tabel sesuai tahapan
        try:
            cur.execute(f"SELECT rowid, * FROM {tbl_name}")
            rows = cur.fetchall()
            print(f"[DEBUG] load_data_from_db: {len(rows)} baris dimuat dari {tbl_name.upper()}")
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

        # 3️⃣ Formatter tanggal
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

        # 4️⃣ Bangun list of dict
        headers = [col[1] for col in cur.execute(f"PRAGMA table_info({tbl_name})").fetchall()]
        all_data = []
        for r in rows:
            d = {c: ("" if r[c] is None else str(r[c])) for c in headers if c in r.keys()}
            d["rowid"] = r["rowid"]
            if "LastUpdate" in r.keys() and r["LastUpdate"]:
                d["LastUpdate"] = format_tgl(str(r["LastUpdate"]))
            all_data.append(d)

        self.all_data = all_data

        import gc
        gc.collect()

        # 5️⃣ Pagination & tampilkan halaman pertama
        total = len(all_data)
        self.total_pages = max(1, (total + self.rows_per_page - 1) // self.rows_per_page)
        self.show_page(1)

        # 6️⃣ Terapkan warna otomatis
        def apply_colors_safely():
            try:
                if not hasattr(self, "_warna_sudah_dihitung") or not self._warna_sudah_dihitung:
                    self._warnai_baris_berdasarkan_ket()
                    self._warna_sudah_dihitung = True
                self._terapkan_warna_ke_tabel_aktif()

            except Exception as e:
                print(f"[WARN] Gagal menerapkan warna otomatis: {e}")

        QTimer.singleShot(100, apply_colors_safely)


    @with_safe_db
    def _ensure_schema_and_migrate(self, conn=None):
        """Pastikan tabel sesuai tahapan aktif eksis dan skema aman."""
        conn = get_connection()
        cur = conn.cursor()

        tahap = self._tahapan.strip().upper()
        tabel_map = {"DPHP": "dphp", "DPSHP": "dpshp", "DPSHPA": "dpshpa"}
        tbl_name = tabel_map.get(tahap, "data_pemilih")

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

        # Tambahkan CEK_DATA jika belum ada
        if "CEK_DATA" not in cols:
            cur.execute(f"ALTER TABLE {tbl_name} ADD COLUMN CEK_DATA TEXT")

        # Jika ada kolom lama "CEK DATA", salin nilainya
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
        #from PyQt6.QtCore import QTimer
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

    def load_theme(self):
        return "light"

    # =================================================
    # Hapus Seluruh Data Pemilih (sub-menu Help)
    # =================================================
    def hapus_data_pemilih(self):
        """
        Menghapus seluruh isi tabel data_pemilih dengan aman.
        Menggunakan koneksi SQLCipher dari db_manager.
        """
        # 🔸 Konfirmasi pengguna
        if not show_modern_question(
            self,
            "Konfirmasi",
            (
                "Apakah Anda yakin ingin menghapus <b>SELURUH data</b> di database ini?<br>"
                "Tindakan ini <b>tidak dapat dibatalkan!</b>"
            )
        ):
            show_modern_info(self, "Dibatalkan", "Proses penghapusan data dibatalkan.")
            return

        try:
            # 🔸 Koneksi aman ke SQLCipher
            conn = get_connection()
            cur = conn.cursor()

            # Pastikan tabel ada (agar tidak error saat DELETE)
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

            # 🔸 Hapus seluruh data dengan aman
            cur.execute("DELETE FROM data_pemilih")
            conn.commit()

            # 🔸 Kosongkan tampilan GUI
            self.all_data.clear()
            self.table.setRowCount(0)
            self.lbl_total.setText("0 total")
            self.lbl_selected.setText("0 selected")

            # 🔸 Reset pagination
            self.total_pages = 1
            self.current_page = 1
            self.update_pagination()
            self.show_page(1)

            # 🔸 Notifikasi sukses
            show_modern_info(
                self,
                "Selesai",
                "Seluruh data pemilih telah berhasil dihapus dari database!"
            )

        except Exception as e:
            show_modern_error(self, "Error", f"Gagal menghapus data:\n{e}")
            
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

        start = (page - 1) * self.rows_per_page
        end = min(start + self.rows_per_page, len(self.all_data))
        data_rows = self.all_data[start:end]
        print(f"[DEBUG] Menampilkan {len(data_rows)} baris dari index {start}–{end}")

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
        """
        Prosedur shutdown aman untuk SQLCipher:
        - Pastikan transaksi tersimpan
        - Tutup koneksi global SQLCipher
        - Hapus artefak sementara (jika ada)
        """
        if getattr(self, "_did_shutdown", False):
            return
        self._did_shutdown = True

        print(f"[INFO] Shutdown dipanggil dari {source or '(tidak diketahui)'}")

        # 1️⃣ Simpan transaksi terakhir jika ada
        try:
            if hasattr(self, "_flush_db"):
                self._flush_db(source or "_shutdown")
        except Exception as e:
            print(f"[WARN] _flush_db({source}) gagal: {e}")

        # 2️⃣ Tutup koneksi SQLCipher dengan aman
        try:
            close_connection()
            print("[INFO] Koneksi SQLCipher ditutup dengan aman.")
        except Exception as e:
            print(f"[WARN] Gagal menutup koneksi: {e}")

        # 3️⃣ Bersihkan artefak sementara (misal file temp_* .db)
        try:
            if hasattr(self, "db_name"):
                base = os.path.basename(self.db_name)
                temp_files = [
                    os.path.join(os.path.dirname(self.db_name), f"temp_{base}"),
                    os.path.join(os.path.dirname(self.db_name), f"temp_{base}.enc")
                ]
                for p in temp_files:
                    if os.path.exists(p):
                        os.remove(p)
                        print(f"[INFO] Artefak sementara dihapus: {p}")
        except Exception as ee:
            print(f"[WARN] Gagal menghapus file sementara: {ee}")

        print("[INFO] Shutdown selesai.\n")


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
#    bootstrap()   
#    app = QApplication(sys.argv)
#    app.setApplicationName("NexVo")

    # 🔹 Inisialisasi database terenkripsi
#    conn = bootstrap()
#    if conn is None:
#        QMessageBox.critical(None, "Kesalahan Fatal", "Gagal inisialisasi database. Aplikasi akan keluar.")
#        sys.exit(1)

    # 🔹 Jalankan halaman login
#    win = LoginWindow(conn)
#    win.show()  # showMaximize sudah di dalam __init__

    # 🔹 Tangani penutupan koneksi saat aplikasi ditutup
#    exit_code = app.exec()
#    close_connection()
#    sys.exit(exit_code)


# ==========================================================
# 🚀 Entry point dengan Mode DEV opsional
# ==========================================================
if __name__ == "__main__":
    bootstrap()
    app = QApplication(sys.argv)
    app.setApplicationName("NexVo")

    # 🔹 Inisialisasi database terenkripsi
    conn = bootstrap()
    if conn is None:
        QMessageBox.critical(None, "Kesalahan Fatal", "Gagal inisialisasi database. Aplikasi akan keluar.")
        sys.exit(1)

    # ===================================================
    # 🔹 Cek apakah mode DEV diaktifkan
    # ===================================================
    if is_dev_mode_requested():
        if confirm_dev_mode(None):
            print("[DEV MODE] Melewati proses login & OTP...")
            dev_nama = "ARI ARDIANA"
            dev_kecamatan = "TANJUNGJAYA"
            dev_desa = "SUKASENANG"
            dev_tahapan = "DPHP"

            mw = MainWindow(dev_nama, dev_kecamatan, dev_desa, str(DB_PATH), dev_tahapan)
            mw.show()
            sys.exit(app.exec())
        else:
            print("[INFO] Mode DEV dibatalkan oleh user.")

    # Normal mode → tampilkan login
    win = LoginWindow(conn)
    win.show()
    sys.exit(app.exec())