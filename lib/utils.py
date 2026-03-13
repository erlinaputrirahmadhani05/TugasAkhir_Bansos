"""
Utility functions untuk aplikasi
"""
import os
import time
from werkzeug.utils import secure_filename
from lib.config_app import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, UPLOAD_FOLDER


def allowed_file(filename):
    """
    Cek apakah ekstensi file diizinkan
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, upload_folder=UPLOAD_FOLDER):
    """
    Menyimpan file upload dan mengembalikan path RELATIVE (untuk ditampilkan di web)
    """
    if not file or file.filename == '':
        return None

    if not allowed_file(file.filename):
        return None

    # cek ukuran file
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return None

    # buat nama unik
    filename = secure_filename(file.filename)
    filename = f"{int(time.time())}_{filename}"

    # pastikan folder ada
    os.makedirs(upload_folder, exist_ok=True)

    # simpan file ke folder static/uploads/bukti_terima
    save_path = os.path.join(upload_folder, filename)
    file.save(save_path)

    # ❗ RETURN PATH RELATIVE (INI YANG PENTING)
    # supaya bisa dipakai url_for('static', ...)
    return f"bukti_terima/{filename}"

