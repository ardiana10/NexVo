# -*- coding: utf-8 -*-
"""
db_manager.py – Pengelola koneksi database terenkripsi \\NexVo
Kompatibel dengan SQLCipher3 dan fallback otomatis ke SQLite.
Versi ini stabil untuk dijalankan di VSCode dan hasil build (.exe)
tanpa looping init_db.py berulang.
"""

import os, sys, sqlite3, subprocess, time, functools
from threading import Lock
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox

# =========================================================
# 🔐 GLOBAL VARIABLE
# =========================================================
_connection = None
_connection_lock = Lock()

# =========================================================
# 🗂️ PATH KONFIGURASI (STABIL UNTUK DEV & BUILD)
# =========================================================
def get_persistent_path():
    """
    Tentukan folder penyimpanan database & key:
    - Jika dijalankan di EXE (PyInstaller), gunakan AppData\\NexVo.
    - Jika dijalankan dari VSCode, gunakan folder skrip (lokal proyek).
    """
    if getattr(sys, 'frozen', False):
        # 🔒 Saat dijalankan dari hasil build (PyInstaller)
        base_dir = Path(os.getenv("APPDATA")) / "NexVo"
    else:
        # 💻 Saat dijalankan dari source code (VSCode)
        base_dir = Path(__file__).resolve().parent
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


# --- Tentukan direktori utama ---
APPDATA_DIR = Path(os.getenv("APPDATA"))
DB_DIR = APPDATA_DIR / "NexVo"
KEY_DIR = APPDATA_DIR / "Aplikasi"           # Folder khusus untuk kunci
DB_DIR.mkdir(parents=True, exist_ok=True)
KEY_DIR.mkdir(parents=True, exist_ok=True)

# --- Path lengkap file ---
DB_PATH = DB_DIR / "nexvo.db"
KEY_PATH = KEY_DIR / "nexvo.key"


# =========================================================
# 🔑 MUAT ATAU BUAT KUNCI ENKRIPSI
# =========================================================
def load_or_create_key():
    """Buat atau baca kunci biner 32-byte (format raw, bukan base64)."""
    if not KEY_PATH.exists():
        key = os.urandom(32)
        KEY_PATH.write_bytes(key)
        try:
            os.chmod(KEY_PATH, 0o600)  # batasi permission
        except Exception:
            pass
        return key
    data = KEY_PATH.read_bytes()
    # Jika panjang tidak 32 byte (versi lama), regenerasi otomatis
    if len(data) != 32:
        key = os.urandom(32)
        KEY_PATH.write_bytes(key)
        return key
    return data


# =========================================================
# 🧱 INISIALISASI SCHEMA UTAMA (VERSI AMAN UNTUK ONEFILE)
# =========================================================
def init_schema(conn) -> None:
    """Membuat semua tabel utama dan tabel rekap jika belum ada (aman dijalankan berulang kali)."""
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

    # --- Tabel tahapan utama ---
    common_schema = """
        (
            checked     INTEGER DEFAULT 0,
            KECAMATAN   TEXT,
            DESA        TEXT,
            DPID        TEXT,
            NKK         TEXT,
            NIK         TEXT,
            NAMA        TEXT,
            JK          TEXT,
            TMPT_LHR    TEXT,
            TGL_LHR     TEXT,
            STS         TEXT,
            ALAMAT      TEXT,
            RT          TEXT,
            RW          TEXT,
            DIS         TEXT,
            KTPel       TEXT,
            SUMBER      TEXT,
            KET         TEXT,
            TPS         TEXT,
            LastUpdate  DATETIME,
            CEK_DATA    TEXT,
            JK_ASAL     TEXT,
            TPS_ASAL    TEXT
        )
    """
    for tbl in ("dphp", "dpshp", "dpshpa"):
        cur.execute(f"CREATE TABLE IF NOT EXISTS {tbl} {common_schema};")

    # --- Tabel tambahan (rekap, saring, dsb) ---
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

    # =========================================================
    # 🧩 Isi kecamatan otomatis jika kosong
    # =========================================================
    try:
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='kecamatan'")
        table_exists = cur.fetchone()[0] > 0
        if table_exists:
            cur.execute("SELECT COUNT(*) FROM kecamatan")
            count = cur.fetchone()[0]
        else:
            count = 0
    except Exception:
        count = 0

    if count == 0:
        print("[INFO] Tabel 'kecamatan' kosong → menjalankan init_db.py ...")
        try:
            # 🔍 Tentukan lokasi file init_db.py
            base_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(base_dir, "init_db.py")

            # 🔧 Mode adaptif — aman untuk VSCode, onedir, dan onefile
            if getattr(sys, 'frozen', False):
                print("[WARN] Mode EXE terdeteksi — jalankan init_db.init_kecamatan() langsung (tanpa spawn).")
                from init_db import init_kecamatan
                init_kecamatan()
            else:
                if os.path.exists(script_path):
                    subprocess.run([sys.executable, script_path], check=True)
                else:
                    print(f"[PERINGATAN] File init_db.py tidak ditemukan di {script_path}")

            print("[✅] Data kecamatan berhasil diinisialisasi otomatis.")
        except Exception as e:
            print(f"[ERROR] Gagal inisialisasi data kecamatan: {e}")


# =========================================================
# 🔒 DAPATKAN KONEKSI GLOBAL DENGAN SQLCIPHER / SQLITE
# =========================================================
def get_connection():
    """
    Mengembalikan koneksi global yang aman, terenkripsi (SQLCipher),
    dan dioptimalkan untuk NexVo Desktop.
    Mode sinkronisasi: langsung (tanpa WAL) → semua koneksi membaca hasil terbaru.
    """
    global _connection
    with _connection_lock:
        if _connection is not None:
            return _connection

        try:
            # ======================================================
            # 🔐 Gunakan SQLCipher jika tersedia
            # ======================================================
            try:
                from sqlcipher3 import dbapi2 as sqlcipher
                _connection = sqlcipher.connect(DB_PATH, isolation_level=None)  # autocommit aktif
                hexkey = load_or_create_key().hex()
                _connection.execute(f"PRAGMA key = \"x'{hexkey}'\";")

                # 🔒 PRAGMA keamanan tambahan
                _connection.execute("PRAGMA cipher_page_size = 4096;")
                _connection.execute("PRAGMA kdf_iter = 64000;")
                _connection.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
                _connection.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
                # print("[INFO] SQLCipher mode aktif.")

            except ImportError:
                # ==================================================
                # 🪶 Fallback ke SQLite biasa (non-enkripsi)
                # ==================================================
                import sqlite3
                _connection = sqlite3.connect(DB_PATH, isolation_level=None)
                # print("[PERINGATAN] SQLCipher3 tidak tersedia, menggunakan SQLite biasa.")

            # ======================================================
            # ⚙️ PRAGMA — Mode sinkronisasi langsung (tanpa WAL)
            # ======================================================
            cur = _connection.cursor()
            cur.execute("PRAGMA journal_mode = DELETE;")   # 💡 langsung tulis ke file utama (tidak ada .wal)
            cur.execute("PRAGMA synchronous = FULL;")      # jamin data tersimpan 100% aman
            cur.execute("PRAGMA temp_store = MEMORY;")     # operasi sementara di RAM
            cur.execute("PRAGMA cache_size = 10000;")      # cache besar untuk performa
            cur.execute("PRAGMA foreign_keys = ON;")       # aktifkan relasi antar tabel
            cur.execute("PRAGMA busy_timeout = 8000;")     # hindari error locked
            cur.close()

            # print("[DB] Koneksi SQLCipher siap (sinkron penuh, tanpa WAL).")
            return _connection

        except Exception as e:
            print(f"[DB ERROR] Gagal inisialisasi database: {e}")
            raise

def connect_encrypted():
    """Koneksi langsung untuk modul lain (misal NexVo)"""
    try:
        from sqlcipher3 import dbapi2 as sqlcipher
        conn = sqlcipher.connect(str(DB_PATH))
        hexkey = load_or_create_key().hex()
        conn.execute(f"PRAGMA key = \"x'{hexkey}'\";")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        init_schema(conn)
        return conn
    except Exception as e:
        QMessageBox.critical(None, "Koneksi Gagal", f"Database terenkripsi gagal dibuka:\n{e}")
        raise

# =========================================================
# 🔁 AUTO-RECONNECT HANDLER
# =========================================================
def ensure_connection_alive():
    """Pastikan koneksi global masih aktif; auto-reconnect jika rusak."""
    global _connection
    with _connection_lock:
        try:
            if _connection is None:
                print("[RECONNECT] Membuka koneksi baru...")
                _connection = get_connection()
                return _connection

            _connection.execute("SELECT 1;")
            return _connection

        except (sqlite3.ProgrammingError, sqlite3.OperationalError) as e:
            print(f"[RECONNECT] Koneksi error: {e}")
            try:
                _connection.close()
            except Exception:
                pass
            _connection = None
            print("[RECONNECT] Membuat ulang koneksi database...")
            _connection = get_connection()
            return _connection

        except Exception as e:
            print(f"[RECONNECT] Error tak terduga: {e}")
            return get_connection()


# =========================================================
# 🛡️ DECORATOR: SAFE DATABASE ACCESS
# =========================================================
def with_safe_db(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        delay = 0.3  # detik
        for attempt in range(1, max_retries + 1):
            try:
                conn = ensure_connection_alive()
                # ⬇️ penting: conn disuntik sebagai keyword di paling kanan
                result = func(*args, **kwargs, conn=conn)
                conn.commit()
                return result
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() or "busy" in str(e).lower():
                    print(f"[WARN] DB terkunci, retry {attempt}/{max_retries} ...")
                    time.sleep(delay * attempt)
                    continue
                else:
                    print(f"[DB ERROR] {func.__name__}: {e}")
                    conn.rollback()
                    raise
            except Exception as e:
                print(f"[DB ERROR] {func.__name__}: {e}")
                conn.rollback()
                raise
        raise sqlite3.OperationalError("Database masih terkunci setelah beberapa percobaan.")
    return wrapper

# =========================================================
# 🚀 BOOTSTRAP SISTEM DATABASE
# =========================================================
_db_initialized = False

def bootstrap():
    """Inisialisasi awal database terenkripsi dan pastikan semua schema lengkap (hanya sekali)."""
    global _db_initialized
    if _db_initialized:
        return get_connection()
    _db_initialized = True

    try:
        if not os.path.exists(DB_PATH):
            print("[INFO] Membuat database baru terenkripsi...")
            conn = get_connection()
            init_schema(conn)
            conn.commit()
            print("[INFO] Inisialisasi schema selesai (database baru dibuat).")
        else:
            print("[INFO] Database ditemukan, memeriksa struktur...")
            conn = get_connection()
            init_schema(conn)
            print("[INFO] Struktur database OK.")

        print("[BOOTSTRAP] Database siap digunakan.")
        return conn

    except Exception as e:
        print(f"[DB ERROR] Gagal inisialisasi database: {e}")
        import traceback
        traceback.print_exc()
        return None


# =========================================================
# 🚪 TUTUP KONEKSI GLOBAL DENGAN AMAN
# =========================================================
def close_connection():
    """Commit dan tutup koneksi global dengan aman."""
    global _connection
    with _connection_lock:
        if _connection is not None:
            try:
                _connection.commit()
                _connection.close()
                print("[INFO] Koneksi database ditutup.")
            except Exception:
                pass
            finally:
                _connection = None


# =========================================================
# 🧹 HAPUS SEMUA DATA (untuk fitur 'Buat Akun Baru')
# =========================================================
def hapus_semua_data(conn=None):
    """Menghapus seluruh isi tabel kecuali tabel users."""
    if conn is None:
        conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall() if r[0] != "sqlite_sequence"]
        for tbl in tables:
            cur.execute(f"DELETE FROM {tbl}")
        conn.commit()
        print("[INFO] Semua data berhasil dihapus (kecuali struktur tabel).")
    except Exception as e:
        print(f"[PERINGATAN] Gagal hapus semua data: {e}")