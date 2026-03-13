from .database import get_db_connection
from .decryption import decrypt_data
import pymysql.cursors


def _safe_decrypt(value):
    if value is None:
        return "-"

    try:
        if isinstance(value, bytes):
            value = value.decode()

        return decrypt_data(value)

    except Exception:
        print("WARNING: ditemukan data lama (belum terenkripsi)")
        return "[DATA LAMA]"


def get_all_data_penerima_decrypted():
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi database")

    # ✅ pakai DictCursor supaya bisa row["nama"]
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT id,
            nik_encrypted,
            no_kk_encrypted,
            nama_encrypted,
            alamat_encrypted,
            tanggal_penerimaan_encrypted,
            no_hp_encrypted,
            uang_terima_encrypted,
            tanggungan_encrypted,
            bukti_terima_path
        FROM data_penerima
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()

    hasil = []
    for row in rows:
        hasil.append({
            "id": row["id"],
            "nik": _safe_decrypt(row["nik_encrypted"]),
            "no_kk": _safe_decrypt(row["no_kk_encrypted"]),
            "nama": _safe_decrypt(row["nama_encrypted"]),
            "alamat": _safe_decrypt(row["alamat_encrypted"]),
            "tanggal_penerimaan": _safe_decrypt(row["tanggal_penerimaan_encrypted"]),
            "no_hp": _safe_decrypt(row["no_hp_encrypted"]),
            "uang_terima": _safe_decrypt(row["uang_terima_encrypted"]),
            "tanggungan": _safe_decrypt(row["tanggungan_encrypted"]),
            "bukti": row["bukti_terima_path"]  # file gambar
        })

    cursor.close()
    connection.close()

    return hasil
