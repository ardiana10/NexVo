# otp_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget, QApplication, QGraphicsBlurEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QColor, QPixmap
import pyotp
import sys


# ======================================
#  Ambil OTP secret dari MainWindow
# ======================================
def get_otp_secret():
    from db_manager import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT otp_secret FROM users LIMIT 1")
        row = cur.fetchone()
        if row:
            return row[0]
    except:
        pass
    return None

# ======================================
#  Overlay + Blur (Reusable)
# ======================================
class BlurOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        # Ambil screenshot background
        win = parent.windowHandle()
        if win:
            px = win.screen().grabWindow(parent.winId())
        else:
            px = parent.grab()

        img = px.toImage()

        # Lakukan blur manual
        blurred = self._blur_image(img, radius=18)

        # Pasang ke label
        from PyQt6.QtWidgets import QLabel
        self.label = QLabel(self)
        self.label.setPixmap(QPixmap.fromImage(blurred))
        self.label.setGeometry(0, 0, parent.width(), parent.height())

        # Tint gelap di atas blur
        self.setStyleSheet("background-color: rgba(0, 0, 0, 120);")

        self.setGeometry(parent.rect())
        self.show()

    def _blur_image(self, img, radius=12):
        """Blur aman menggunakan QPainter tanpa bentrok QGraphicsBlurEffect."""
        from PyQt6.QtGui import QImage, QPainter
        from PyQt6.QtCore import QRect

        blurred = QImage(img.size(), QImage.Format.Format_ARGB32)
        blurred.fill(Qt.GlobalColor.transparent)

        painter = QPainter(blurred)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawImage(0, 0, img)

        # Blur primitive (fast gaussian approximation)
        for _ in range(radius):
            painter.drawImage(QRect(1, 0, img.width()-1, img.height()), blurred, QRect(0, 0, img.width()-1, img.height()))
            painter.drawImage(QRect(0, 1, img.width(), img.height()-1), blurred, QRect(0, 0, img.width(), img.height()-1))

        painter.end()
        return blurred

# ======================================
#  OTP Dialog Premium NexVo
# ======================================
class OTPDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.ok = False
        self.attempts = 0  # jumlah percobaan OTP salah

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setFixedSize(420, 250)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # ==== WRAPPER UI ====
        self.wrapper = QWidget(self)
        self.wrapper.setGeometry(0, 0, 420, 250)
        self.wrapper.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 220);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self.wrapper)
        layout.setContentsMargins(22, 25, 22, 22)
        layout.setSpacing(15)

        title = QLabel("🔒 Aplikasi Terkunci")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 17pt;
                font-weight: 700;
                color: #ff6600;
            }
        """)
        layout.addWidget(title)

        info = QLabel(
            "<b>Masukkan kode OTP untuk melanjutkan</b><br>"
            "<b><span style='color:#cc0000;'>Aplikasi akan ditutup jika 3x salah memasukkan OTP</span></b>"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("font-size: 10pt; color: #555;")
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        # INPUT OTP
        self.inp = QLineEdit()
        self.inp.setMaxLength(6)
        self.inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inp.setPlaceholderText("●●●●●●")
        self.inp.setStyleSheet("""
            QLineEdit {
                border: 2px solid #bbbbbb;
                border-radius: 10px;
                padding: 10px;
                font-size: 18px;
                letter-spacing: 5px;
            }
            QLineEdit:focus {
                border-color: #ff6600;
            }
        """)
        layout.addWidget(self.inp)

        # TOMBOL VERIFIKASI
        btn = QPushButton("Verifikasi OTP")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                padding: 10px;
                border-radius: 10px;
                font-size: 12pt;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e65c00;
            }
        """)
        layout.addWidget(btn)
        btn.clicked.connect(self.verify)

    # ==========================
    #  VERIFIKASI OTP
    # ==========================
    def verify(self):
        code = self.inp.text().strip()
        secret = get_otp_secret()  # TANPA parent
            
        try:
            totp = pyotp.TOTP(secret)
            if totp.verify(code):
                self.ok = True
                self.accept()
                return
        except:
            pass

        # OTP salah → shake
        self.attempts += 1
        self._shake()

        if self.attempts >= 3:
            QApplication.quit()
            sys.exit()

    # ==========================
    #  ANIMASI SHAKE
    # ==========================
    def _shake(self):
        anim = QPropertyAnimation(self.wrapper, b"geometry")
        rect = self.wrapper.geometry()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        anim.setDuration(300)
        anim.setKeyValueAt(0.0, QRect(x, y, w, h))
        anim.setKeyValueAt(0.25, QRect(x - 15, y, w, h))
        anim.setKeyValueAt(0.50, QRect(x + 15, y, w, h))
        anim.setKeyValueAt(0.75, QRect(x - 15, y, w, h))
        anim.setKeyValueAt(1.0, QRect(x, y, w, h))
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()
        self._shake_anim = anim

# ======================================
#  Fungsi Global untuk memanggil OTP
# ======================================
def show_otp_dialog(parent):
    overlay = BlurOverlay(parent)
    dlg = OTPDialog(parent)
    dlg.exec()
    overlay.close()
    return dlg.ok