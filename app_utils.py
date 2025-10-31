# -*- coding: utf-8 -*-
"""
app_utils.py — Fungsi utilitas umum untuk NexVo Desktop.
Berisi helper yang kompatibel untuk mode VSCode (dev) dan mode build (PyInstaller).
"""

import os
import sys
from PyQt6.QtGui import QIcon

def resource_path(relative_path: str) -> str:
    """
    Mengembalikan path absolut ke file resource (gambar, ikon, font, dsb)
    agar kompatibel di mode development maupun hasil build (.exe).
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS  # Folder sementara PyInstaller
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def app_icon() -> QIcon:
    """
    Mengembalikan QIcon global aplikasi (iconKPU.ico).
    Aman dipakai di semua window (MainWindow, LoginWindow, dsb).
    """
    icon_path = resource_path("icons/iconKPU.ico")
    return QIcon(icon_path)
