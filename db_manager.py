# -*- coding: utf-8 -*-
"""
db_manager.py – Pengelola koneksi database terenkripsi NexVo
Versi stabil & aman (anti-lock, auto-reconnect, full schema, OTP-ready)
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
_db_initialized = False

# =========================================================
# 🗂️ PATH KONFIGURASI
# =========================================================
APPDATA = Path(os.getenv("APPDATA"))
NEXVO_DIR = APPDATA / "NexVo"
KEY_DIR = NEXVO_DIR / "Key"         # 🔒 Key dipindahkan ke folder NexVo/Key
DB_PATH = NEXVO_DIR / "nexvo.db"
KEY_PATH = KEY_DIR / "nexvo.key"

NEXVO_DIR.mkdir(parents=True, exist_ok=True)
KEY_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# 🔑 MUAT ATAU BUAT KUNCI ENKRIPSI
# =========================================================
def load_or_create_key():
    """Buat atau baca kunci biner 32-byte (raw)."""
    if not KEY_PATH.exists():
        key = os.urandom(32)
        KEY_PATH.write_bytes(key)
        try:
            os.chmod(KEY_PATH, 0o600)
        except Exception:
            pass
        return key
    data = KEY_PATH.read_bytes()
    if len(data) != 32:
        key = os.urandom(32)
        KEY_PATH.write_bytes(key)
        return key
    return data


# =========================================================
# 🧱 INISIALISASI SCHEMA UTAMA
# =========================================================
def init_schema(conn):
    """Buat semua tabel utama dan tambahan (idempotent)."""
    cur = conn.cursor()

    # === USERS ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT,
            email TEXT,
            kabupaten TEXT,
            kecamatan TEXT,
            desa TEXT,
            password TEXT,
            otp_secret TEXT
        )
    """)

    # === KECAMATAN ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kecamatan (
            kabupaten TEXT,
            kecamatan TEXT,
            desa TEXT
        )
    """)

    # === TABEL TAHAPAN (DPHP, DPSHP, DPSHPA) ===
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
            LastUpdate DATETIME,
            CEK_DATA TEXT,
            NKK_ASAL TEXT,
            NIK_ASAL TEXT,
            NAMA_ASAL TEXT,
            JK_ASAL TEXT,
            TMPT_LHR_ASAL TEXT,
            TGL_LHR_ASAL TEXT,
            STS_ASAL TEXT,
            ALAMAT_ASAL TEXT,
            RT_ASAL TEXT,
            RW_ASAL TEXT,
            DIS_ASAL TEXT,
            KTPel_ASAL TEXT,
            SUMBER_ASAL TEXT,
            TPS_ASAL TEXT
        )
    """
    for tbl in ("dphp", "dpshp", "dpshpa"):
        cur.execute(f"CREATE TABLE IF NOT EXISTS {tbl} {common_schema}")

    # === TABEL TAMBAHAN ===
    for tbl in ("rekap", "baru", "ubah", "ktpel"):
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl} (
                "NAMA TPS" TEXT,
                "JUMLAH KK" INTEGER,
                "LAKI-LAKI" INTEGER,
                "PEREMPUAN" INTEGER,
                "JUMLAH" INTEGER
            )
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
        )
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
        )
    """)

    conn.commit()

    # === Isi data kecamatan otomatis jika kosong ===
    try:
        cur.execute("SELECT COUNT(*) FROM kecamatan")
        count = cur.fetchone()[0]
        if count == 0:
            print("[INFO] Mengisi tabel 'kecamatan'...")
            from init_db import init_kecamatan
            init_kecamatan()
            print("[✅] Tabel kecamatan selesai diisi otomatis.")
    except Exception as e:
        print(f"[WARN] Gagal isi data kecamatan otomatis: {e}")


# =========================================================
# 🔒 KONEKSI GLOBAL SQLCIPHER
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
# =========================================================
# 🔁 AUTO-RECONNECT HANDLER
# =========================================================
def ensure_connection_alive():
    """Pastikan koneksi global masih aktif, auto-reconnect jika perlu."""
    global _connection
    with _connection_lock:
        try:
            if _connection is None:
                _connection = get_connection()
                return _connection
            _connection.execute("SELECT 1;")
            return _connection
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            try:
                _connection.close()
            except Exception:
                pass
            _connection = None
            return get_connection()


# =========================================================
# 🛡️ DECORATOR: SAFE DATABASE ACCESS
# =========================================================
def with_safe_db(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(3):
            try:
                conn = ensure_connection_alive()
                result = func(*args, **kwargs, conn=conn)
                conn.commit()
                return result
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() or "busy" in str(e).lower():
                    print(f"[WARN] DB locked, retry {attempt + 1}/3 ...")
                    time.sleep(0.3)
                    continue
                else:
                    conn.rollback()
                    raise
            except Exception as e:
                conn.rollback()
                raise
        raise sqlite3.OperationalError("DB locked setelah 3 percobaan.")
    return wrapper

# =========================================================
# 🧩 KONEKSI SEMENTARA UNTUK BACKUP / RESTORE
# =========================================================
def get_temp_connection():
    """Koneksi sementara independen (tidak memakai global _connection).
    Digunakan hanya untuk backup/restore agar tidak bentrok dengan koneksi utama.
    """
    try:
        from sqlcipher3 import dbapi2 as sqlcipher
        conn = sqlcipher.connect(str(DB_PATH))
        hexkey = load_or_create_key().hex()
        conn.execute(f"PRAGMA key = \"x'{hexkey}'\";")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = DELETE;")
        conn.execute("PRAGMA synchronous = FULL;")
        return conn
    except ImportError:
        # fallback ke sqlite biasa
        return sqlite3.connect(DB_PATH)

# =========================================================
# 🚀 BOOTSTRAP
# =========================================================
def bootstrap():
    """Inisialisasi awal database NexVo."""
    global _db_initialized
    if _db_initialized:
        return get_connection()
    _db_initialized = True

    conn = get_connection()
    init_schema(conn)
    print("[BOOTSTRAP] Database siap digunakan.")
    return conn


# =========================================================
# 🚪 TUTUP KONEKSI
# =========================================================
def close_connection():
    global _connection
    with _connection_lock:
        if _connection is not None:
            try:
                _connection.commit()
                _connection.close()
                print("[INFO] Koneksi database ditutup dengan aman.")
            except Exception:
                pass
            finally:
                _connection = None

# =========================================================
# 🧹 HAPUS SEMUA DATA
# =========================================================
def hapus_semua_data(conn=None):
    """
    Hapus seluruh isi tabel selain 'users' dan 'kecamatan'.
    Struktur dan data wilayah (kabupaten, kecamatan, desa) dipertahankan selamanya.
    """
    if conn is None:
        conn = get_connection()
    cur = conn.cursor()
    try:
        # Ambil daftar semua tabel kecuali yang tidak boleh disentuh
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [
            r[0]
            for r in cur.fetchall()
            if r[0] not in ("sqlite_sequence", "users", "kecamatan")
        ]

        # Hapus isi tiap tabel
        for tbl in tables:
            cur.execute(f"DELETE FROM {tbl}")
        conn.commit()

        print("[INFO] Semua data berhasil dihapus (kecuali tabel 'users' dan 'kecamatan').")

    except Exception as e:
        print(f"[WARN] Gagal hapus data: {e}")

# =========================================================
# 🧹 HAPUS SEMUA DATA
# =========================================================
def hapus_buat_akun(conn=None):
    """
    Hapus seluruh isi tabel selain 'users' dan 'kecamatan'.
    Struktur dan data wilayah (kabupaten, kecamatan, desa) dipertahankan selamanya.
    """
    if conn is None:
        conn = get_connection()
    cur = conn.cursor()
    try:
        # Ambil daftar semua tabel kecuali yang tidak boleh disentuh
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [
            r[0]
            for r in cur.fetchall()
            if r[0] not in ("sqlite_sequence", "kecamatan")
        ]

        # Hapus isi tiap tabel
        for tbl in tables:
            cur.execute(f"DELETE FROM {tbl}")
        conn.commit()

    except Exception as e:
        print(f"[WARN] Gagal hapus data: {e}")