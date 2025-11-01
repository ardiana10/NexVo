# -*- coding: utf-8 -*-
"""
init_db.py – Inisialisasi tabel 'kecamatan' di NexVo.
Dipanggil otomatis dari db_manager.py atau manual via terminal.
"""

import os
import sys
import sqlite3
from pathlib import Path

try:
    # 🔹 Jika dijalankan dari dalam NexVo (sudah ada db_manager)
    from db_manager import DB_PATH, load_or_create_key, get_connection
    USE_GLOBAL_CONN = True
except ImportError:
    # 🔹 Jika dijalankan manual (tanpa NexVo)
    from db_manager import DB_PATH, load_or_create_key
    USE_GLOBAL_CONN = False


def init_kecamatan():
    """Isi tabel 'kecamatan' hanya jika kosong (adaptif: global atau lokal)."""
    print("[INFO] Inisialisasi tabel 'kecamatan'...")

    try:
        # ===============================================================
        # 🔐 1. Dapatkan koneksi
        # ===============================================================
        if USE_GLOBAL_CONN:
            conn = get_connection()  # gunakan koneksi global aktif
            print("[INFO] Menggunakan koneksi global dari db_manager.")
        else:
            try:
                from sqlcipher3 import dbapi2 as sqlcipher
                conn = sqlcipher.connect(DB_PATH)
                hexkey = load_or_create_key().hex()
                conn.execute(f"PRAGMA key = \"x'{hexkey}'\";")
                print("[INFO] Menggunakan koneksi SQLCipher3 lokal.")
            except ImportError:
                conn = sqlite3.connect(DB_PATH)
                print("[WARN] sqlcipher3 tidak ditemukan, fallback ke SQLite biasa.")

        cur = conn.cursor()

        # ===============================================================
        # 🧱 2. Pastikan tabel ada
        # ===============================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kecamatan (
                kecamatan TEXT,
                desa TEXT
            )
        """)

        cur.execute("SELECT COUNT(*) FROM kecamatan")
        count = cur.fetchone()[0]
        if count > 0:
            print(f"[INFO] Tabel 'kecamatan' sudah berisi {count} data. Tidak ada yang ditambahkan.")
            if not USE_GLOBAL_CONN:
                conn.close()
            return

        print("[INFO] Mengisi tabel 'kecamatan'...")

        # ===============================================================
        # 📋 3. Data kecamatan
        # ===============================================================
        data = [
            ("CIPATUJAH","CIHERAS"),
            ("CIPATUJAH","CIPATUJAH"),
            ("CIPATUJAH","SINDANGKERTA"),
            ("CIPATUJAH","CIKAWUNGADING"),
            ("CIPATUJAH","BANTARKALONG"),
            ("CIPATUJAH","DARAWATI"),
            ("CIPATUJAH","NAGROG"),
            ("CIPATUJAH","PAMEUTINGAN"),
            ("CIPATUJAH","TOBONGJAYA"),
            ("CIPATUJAH","CIPANAS"),
            ("CIPATUJAH","KERTASARI"),
            ("CIPATUJAH","CIANDUM"),
            ("CIPATUJAH","NANGELASARI"),
            ("CIPATUJAH","PADAWARAS"),
            ("CIPATUJAH","SUKAHURIP"),
            ("KARANGNUNGGAL","CIDADAP"),
            ("KARANGNUNGGAL","CIAWI"),
            ("KARANGNUNGGAL","CIKUPA"),
            ("KARANGNUNGGAL","KARANGNUNGGAL"),
            ("KARANGNUNGGAL","KARANGMEKAR"),
            ("KARANGNUNGGAL","CIKUKULU"),
            ("KARANGNUNGGAL","CIBATUIRENG"),
            ("KARANGNUNGGAL","CIBATU"),
            ("KARANGNUNGGAL","SARIMANGGU"),
            ("KARANGNUNGGAL","SUKAWANGUN"),
            ("KARANGNUNGGAL","CINTAWANGI"),
            ("KARANGNUNGGAL","CIKAPINIS"),
            ("KARANGNUNGGAL","SARIMUKTI"),
            ("KARANGNUNGGAL","KUJANG"),
            ("CIKALONG","CIKALONG"),
            ("CIKALONG","KALAPAGENEP"),
            ("CIKALONG","CIKANCRA"),
            ("CIKALONG","SINGKIR"),
            ("CIKALONG","PANYIARAN"),
            ("CIKALONG","CIBEBER"),
            ("CIKALONG","CIKADU"),
            ("CIKALONG","MANDALAJAYA"),
            ("CIKALONG","CIDADALI"),
            ("CIKALONG","CIMANUK"),
            ("CIKALONG","SINDANGJAYA"),
            ("CIKALONG","KUBANGSARI"),
            ("CIKALONG","TONJONGSARI"),
            ("PANCATENGAH","CIBUNIASIH"),
            ("PANCATENGAH","PANGLIARAN"),
            ("PANCATENGAH","TONJONG"),
            ("PANCATENGAH","CIBONGAS"),
            ("PANCATENGAH","TAWANG"),
            ("PANCATENGAH","NEGLASARI"),
            ("PANCATENGAH","CIKAWUNG"),
            ("PANCATENGAH","JAYAMUKTI"),
            ("PANCATENGAH","MARGALUYU"),
            ("PANCATENGAH","MEKARSARI"),
            ("PANCATENGAH","PANCAWANGI"),
            ("CIKATOMAS","GUNUNGSARI"),
            ("CIKATOMAS","CILUMBA"),
            ("CIKATOMAS","PAKEMITAN"),
            ("CIKATOMAS","COGREG"),
            ("CIKATOMAS","CAYUR"),
            ("CIKATOMAS","LENGKONGBARANG"),
            ("CIKATOMAS","SINDANGASIH"),
            ("CIKATOMAS","TANJUNGBARANG"),
            ("CIKATOMAS","LINGGALAKSANA"),
            ("CIBALONG","CISEMPUR"),
            ("CIBALONG","SETIAWARAS"),
            ("CIBALONG","EUREUNPALAY"),
            ("CIBALONG","CIBALONG"),
            ("CIBALONG","SINGAJAYA"),
            ("CIBALONG","PARUNG"),
            ("PARUNGPONTENG","PARUNGPONTENG"),
            ("PARUNGPONTENG","CIGUNUNG"),
            ("PARUNGPONTENG","CIBANTENG"),
            ("PARUNGPONTENG","BARUMEKAR"),
            ("PARUNGPONTENG","CIBUNGUR"),
            ("PARUNGPONTENG","BURUJULJAYA"),
            ("PARUNGPONTENG","GIRIKENCANA"),
            ("PARUNGPONTENG","KARYABAKTI"),
            ("BANTARKALONG","SIMPANG"),
            ("BANTARKALONG","PARAKANHONJE"),
            ("BANTARKALONG","PAMIJAHAN"),
            ("BANTARKALONG","SUKAMAJU"),
            ("BANTARKALONG","WANGUNSARI"),
            ("BANTARKALONG","HEGARWANGI"),
            ("BANTARKALONG","WAKAP"),
            ("BANTARKALONG","SIRNAGALIH"),
            ("BOJONGASIH","MERTAJAYA"),
            ("BOJONGASIH","CIKADONGDONG"),
            ("BOJONGASIH","BOJONGASIH"),
            ("BOJONGASIH","SINDANGSARI"),
            ("BOJONGASIH","GIRIJAYA"),
            ("BOJONGASIH","TOBLONGAN"),
            ("CULAMEGA","CIKUYA"),
            ("CULAMEGA","CINTABODAS"),
            ("CULAMEGA","CIPICUNG"),
            ("CULAMEGA","BOJONGSARI"),
            ("CULAMEGA","MEKARLAKSANA"),
            ("BOJONGGAMBIR","BOJONGKAPOL"),
            ("BOJONGGAMBIR","PEDANGKAMULYAN"),
            ("BOJONGGAMBIR","BOJONGGAMBIR"),
            ("BOJONGGAMBIR","CIROYOM"),
            ("BOJONGGAMBIR","WANDASARI"),
            ("BOJONGGAMBIR","CAMPAKASARI"),
            ("BOJONGGAMBIR","MANGKONJAYA"),
            ("BOJONGGAMBIR","KERTANEGLA"),
            ("BOJONGGAMBIR","PURWARAHARJA"),
            ("BOJONGGAMBIR","GIRIMUKTI"),
            ("SODONGHILIR","PARUMASAN"),
            ("SODONGHILIR","CUKANGKAWUNG"),
            ("SODONGHILIR","SODONGHILIR"),
            ("SODONGHILIR","CIKALONG"),
            ("SODONGHILIR","CIPAINGEUN"),
            ("SODONGHILIR","LEUWIDULANG"),
            ("SODONGHILIR","MUNCANG"),
            ("SODONGHILIR","SEPATNUNGGAL"),
            ("SODONGHILIR","CUKANGJAYAGUNA"),
            ("SODONGHILIR","RAKSAJAYA"),
            ("SODONGHILIR","PAKALONGAN"),
            ("SODONGHILIR","SUKABAKTI"),
            ("TARAJU","TARAJU"),
            ("TARAJU","CIKUBANG"),
            ("TARAJU","DEUDEUL"),
            ("TARAJU","PURWARAHAYU"),
            ("TARAJU","SINGASARI"),
            ("TARAJU","BANYUASIH"),
            ("TARAJU","RAKSASARI"),
            ("TARAJU","KERTARAHARJA"),
            ("TARAJU","PAGERALAM"),
            ("SALAWU","JAHIANG"),
            ("SALAWU","SERANG"),
            ("SALAWU","SALAWU"),
            ("SALAWU","NEGLASARI"),
            ("SALAWU","TANJUNGSARI"),
            ("SALAWU","TENJOWARINGIN"),
            ("SALAWU","SUNDAWENANG"),
            ("SALAWU","KAWUNGSARI"),
            ("SALAWU","SUKARASA"),
            ("SALAWU","KUTAWARINGIN"),
            ("SALAWU","KARANGMUKTI"),
            ("SALAWU","MARGALAKSANA"),
            ("PUSPAHIANG","MANDALASARI"),
            ("PUSPAHIANG","SUKASARI"),
            ("PUSPAHIANG","PUSPASARI"),
            ("PUSPAHIANG","PUSPAHIANG"),
            ("PUSPAHIANG","LUYUBAKTI"),
            ("PUSPAHIANG","PUSPARAHAYU"),
            ("PUSPAHIANG","CIMANGGU"),
            ("PUSPAHIANG","PUSPAJAYA"),
            ("TANJUNGJAYA","CIKEUSAL"),
            ("TANJUNGJAYA","CIBALANARIK"),
            ("TANJUNGJAYA","SUKANAGARA"),
            ("TANJUNGJAYA","TANJUNGJAYA"),
            ("TANJUNGJAYA","CILOLOHAN"),
            ("TANJUNGJAYA","CINTAJAYA"),
            ("TANJUNGJAYA","SUKASENANG"),
            ("SUKARAJA","SUKAPURA"),
            ("SUKARAJA","LEUWIBUDAH"),
            ("SUKARAJA","SIRNAJAYA"),
            ("SUKARAJA","MEKARJAYA"),
            ("SUKARAJA","LINGGARAJA"),
            ("SUKARAJA","JANGGALA"),
            ("SUKARAJA","MARGALAKSANA"),
            ("SUKARAJA","TARUNAJAYA"),
            ("SALOPA","MANDALAHAYU"),
            ("SALOPA","MULYASARI"),
            ("SALOPA","KAWITAN"),
            ("SALOPA","MANDALAWANGI"),
            ("SALOPA","KARYAWANGI"),
            ("SALOPA","TANJUNGSARI"),
            ("SALOPA","MANDALAGUNA"),
            ("SALOPA","KARYAMANDALA"),
            ("SALOPA","BANJARWARINGIN"),
            ("JATIWARAS","KAPUTIHAN"),
            ("JATIWARAS","SETIAWANGI"),
            ("JATIWARAS","SUKAKERTA"),
            ("JATIWARAS","NEGLASARI"),
            ("JATIWARAS","JATIWARAS"),
            ("JATIWARAS","PAPAYAN"),
            ("JATIWARAS","CIWARAK"),
            ("JATIWARAS","KERSAGALIH"),
            ("JATIWARAS","MANDALAMEKAR"),
            ("JATIWARAS","KERTARAHAYU"),
            ("JATIWARAS","MANDALAHURIP"),
            ("CINEAM","CISARUA"),
            ("CINEAM","CIKONDANG"),
            ("CINEAM","CIJULANG"),
            ("CINEAM","CIAMPANAN"),
            ("CINEAM","CINEAM"),
            ("CINEAM","RAJADATU"),
            ("CINEAM","ANCOL"),
            ("CINEAM","NAGARATENGAH"),
            ("CINEAM","PASIRMUKTI"),
            ("CINEAM","MADIASARI"),
            ("KARANGJAYA","SIRNAJAYA"),
            ("KARANGJAYA","KARANGJAYA"),
            ("KARANGJAYA","KARANGLAYUNG"),
            ("KARANGJAYA","CITALAHAB"),
            ("MANONJAYA","CIHAUR"),
            ("MANONJAYA","CILANGKAP"),
            ("MANONJAYA","PASIRPANJANG"),
            ("MANONJAYA","CIBEBER"),
            ("MANONJAYA","KAMULYAN"),
            ("MANONJAYA","MANONJAYA"),
            ("MANONJAYA","MARGALUYU"),
            ("MANONJAYA","PASIRBATANG"),
            ("MANONJAYA","KALIMANGGIS"),
            ("MANONJAYA","MARGAHAYU"),
            ("MANONJAYA","BATUSUMUR"),
            ("MANONJAYA","GUNAJAYA"),
            ("GUNUNGTANJUNG","CINUNJANG"),
            ("GUNUNGTANJUNG","GUNUNGTANJUNG"),
            ("GUNUNGTANJUNG","BOJONGSARI"),
            ("GUNUNGTANJUNG","JATIJAYA"),
            ("GUNUNGTANJUNG","TANJUNGSARI"),
            ("GUNUNGTANJUNG","GIRIWANGI"),
            ("GUNUNGTANJUNG","MALATISUKA"),
            ("SINGAPARNA","CIKUNTEN"),
            ("SINGAPARNA","SINGAPARNA"),
            ("SINGAPARNA","CIPAKAT"),
            ("SINGAPARNA","CINTARAJA"),
            ("SINGAPARNA","CIKUNIR"),
            ("SINGAPARNA","CIKADONGDONG"),
            ("SINGAPARNA","SUKAASIH"),
            ("SINGAPARNA","SUKAMULYA"),
            ("SINGAPARNA","SINGASARI"),
            ("SINGAPARNA","SUKAHERANG"),
            ("MANGUNREJA","SUKASUKUR"),
            ("MANGUNREJA","SALEBU"),
            ("MANGUNREJA","MANGUNREJA"),
            ("MANGUNREJA","MARGAJAYA"),
            ("MANGUNREJA","PASIRSALAM"),
            ("MANGUNREJA","SUKALUYU"),
            ("SUKARAME","SUKARAME"),
            ("SUKARAME","SUKAMENAK"),
            ("SUKARAME","SUKAKARSA"),
            ("SUKARAME","PADASUKA"),
            ("SUKARAME","SUKARAPIH"),
            ("SUKARAME","WARGAKERTA"),
            ("CIGALONTANG","KERSAMAJU"),
            ("CIGALONTANG","NANGTANG"),
            ("CIGALONTANG","PUSPARAJA"),
            ("CIGALONTANG","JAYAPURA"),
            ("CIGALONTANG","LENGKONGJAYA"),
            ("CIGALONTANG","NANGGERANG"),
            ("CIGALONTANG","SUKAMANAH"),
            ("CIGALONTANG","SIRNARAJA"),
            ("CIGALONTANG","CIDUGALEUN"),
            ("CIGALONTANG","PARENTAS"),
            ("CIGALONTANG","PUSPAMUKTI"),
            ("CIGALONTANG","TENJONAGARA"),
            ("CIGALONTANG","CIGALONTANG"),
            ("CIGALONTANG","SIRNAGALIH"),
            ("CIGALONTANG","TANJUNGKARANG"),
            ("CIGALONTANG","SIRNAPUTRA"),
            ("LEUWISARI","ARJASARI"),
            ("LEUWISARI","CIAWANG"),
            ("LEUWISARI","CIGADOG"),
            ("LEUWISARI","LINGGAWANGI"),
            ("LEUWISARI","JAYAMUKTI"),
            ("LEUWISARI","MANDALAGIRI"),
            ("LEUWISARI","LINGGAMULYA"),
            ("PADAKEMBANG","CILAMPUNGHILIR"),
            ("PADAKEMBANG","RANCAPAKU"),
            ("PADAKEMBANG","MEKARJAYA"),
            ("PADAKEMBANG","CISARUNI"),
            ("PADAKEMBANG","PADAKEMBANG"),
            ("SARIWANGI","SARIWANGI"),
            ("SARIWANGI","SUKAHARJA"),
            ("SARIWANGI","JAYARATU"),
            ("SARIWANGI","LINGGASIRNA"),
            ("SARIWANGI","SIRNASARI"),
            ("SARIWANGI","SUKAMULIH"),
            ("SARIWANGI","SELAWANGI"),
            ("SARIWANGI","JAYAPUTRA"),
            ("SUKARATU","LINGGAJATI"),
            ("SUKARATU","TAWANGBANTENG"),
            ("SUKARATU","SINAGAR"),
            ("SUKARATU","GUNUNGSARI"),
            ("SUKARATU","SUKAMAHI"),
            ("SUKARATU","SUKAGALIH"),
            ("SUKARATU","SUKARATU"),
            ("SUKARATU","INDRAJAYA"),
            ("CISAYONG","CISAYONG"),
            ("CISAYONG","SUKAJADI"),
            ("CISAYONG","SUKASUKUR"),
            ("CISAYONG","SUKAMUKTI"),
            ("CISAYONG","NUSAWANGI"),
            ("CISAYONG","CIKADU"),
            ("CISAYONG","CILEULEUS"),
            ("CISAYONG","JATIHURIP"),
            ("CISAYONG","SUKASETIA"),
            ("CISAYONG","PURWASARI"),
            ("CISAYONG","SUKARAHARJA"),
            ("CISAYONG","MEKARWANGI"),
            ("CISAYONG","SANTANAMEKAR"),
            ("SUKAHENING","BANYURASA"),
            ("SUKAHENING","CALINGCING"),
            ("SUKAHENING","SUKAHENING"),
            ("SUKAHENING","KIARAJANGKUNG"),
            ("SUKAHENING","KUDADEPA"),
            ("SUKAHENING","BANYURESMI"),
            ("SUKAHENING","SUNDAKERTA"),
            ("RAJAPOLAH","DAWAGUNG"),
            ("RAJAPOLAH","RAJAPOLAH"),
            ("RAJAPOLAH","MANGGUNGJAYA"),
            ("RAJAPOLAH","MANGGUNGSARI"),
            ("RAJAPOLAH","SUKARAJA"),
            ("RAJAPOLAH","RAJAMANDALA"),
            ("RAJAPOLAH","SUKANAGALIH"),
            ("RAJAPOLAH","TANJUNGPURA"),
            ("JAMANIS","CONDONG"),
            ("JAMANIS","BOJONGGAOK"),
            ("JAMANIS","SINDANGRAJA"),
            ("JAMANIS","KARANGMULYA"),
            ("JAMANIS","GERESIK"),
            ("JAMANIS","KARANGSEMBUNG"),
            ("JAMANIS","TANJUNGMEKAR"),
            ("JAMANIS","KARANGRESIK"),
            ("CIAWI","GOMBONG"),
            ("CIAWI","BUGEL"),
            ("CIAWI","MARGASARI"),
            ("CIAWI","PAKEMITAN"),
            ("CIAWI","CIAWI"),
            ("CIAWI","SUKAMANTRI"),
            ("CIAWI","PASIRHUNI"),
            ("CIAWI","CITAMBA"),
            ("CIAWI","KERTAMUKTI"),
            ("CIAWI","KURNIABAKTI"),
            ("CIAWI","PAKEMITANKIDUL"),
            ("KADIPATEN","KADIPATEN"),
            ("KADIPATEN","DIRGAHAYU"),
            ("KADIPATEN","CIBAHAYU"),
            ("KADIPATEN","MEKARSARI"),
            ("KADIPATEN","BUNIASIH"),
            ("KADIPATEN","PAMOYANAN"),
            ("PAGERAGEUNG","CIPACING"),
            ("PAGERAGEUNG","PAGERAGEUNG"),
            ("PAGERAGEUNG","SUKAMAJU"),
            ("PAGERAGEUNG","TANJUNGKERTA"),
            ("PAGERAGEUNG","PUTERAN"),
            ("PAGERAGEUNG","GURANTENG"),
            ("PAGERAGEUNG","NANGGEWER"),
            ("PAGERAGEUNG","SUKAPADA"),
            ("PAGERAGEUNG","PAGERSARI"),
            ("PAGERAGEUNG","SUKADANA"),
            ("SUKARESIK","CIPONDOK"),
            ("SUKARESIK","SUKAMENAK"),
            ("SUKARESIK","SUKARATU"),
            ("SUKARESIK","BANJARSARI"),
            ("SUKARESIK","TANJUNGSARI"),
            ("SUKARESIK","SUKAPANCAR"),
            ("SUKARESIK","SUKARESIK"),
            ("SUKARESIK","MARGAMULYA"),
        ]

        cur.executemany("INSERT INTO kecamatan (kecamatan, desa) VALUES (?, ?)", data)
        conn.commit()

        print("[✅] Data kecamatan berhasil dimasukkan ke nexvo.db")

        if not USE_GLOBAL_CONN:
            conn.close()

    except Exception as e:
        print(f"[ERROR] Gagal inisialisasi tabel kecamatan: {e}")
        if not USE_GLOBAL_CONN:
            sys.exit(1)


if __name__ == "__main__":
    print("[RUN] Menjalankan init_kecamatan() manual...")
    init_kecamatan()
    print("[DONE] Selesai.")