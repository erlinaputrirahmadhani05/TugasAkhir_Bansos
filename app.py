from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import traceback
from lib.config_app import SECRET_KEY, PERMANENT_SESSION_LIFETIME, UPLOAD_FOLDER, MAX_FILE_SIZE
from lib.database import (
    get_user_by_email, get_all_users,
    create_user, get_user_by_id, update_user, delete_user,
)
# koneksi database
from config import DB_CONFIG
import mysql.connector
from PIL import Image

# enkripsi dan dekripsi
from lib.encryption import encrypt_data
from lib.decryption import decrypt_data
from lib.decryption import decrypt_data
from flask import send_from_directory
from datetime import datetime
import time
import os
import io
import pandas as pd
from flask import send_file
from datetime import datetime

# import laporan excel
import io
import os
import pandas as pd
from datetime import datetime
from flask import send_file
from reportlab.lib import colors 

# import laporan PDF
import io
import os
from datetime import datetime
from flask import send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# import utilities
from lib.password_utils import verify_password

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(app.root_path, "private_uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = SECRET_KEY
app.permanent_session_lifetime = PERMANENT_SESSION_LIFETIME
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def require_login(f):
    """
    Decorator untuk memastikan user sudah login
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu!', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_superadmin(f):
    """
    Decorator untuk memastikan hanya role superadmin yang bisa akses.
    Admin yang mengakses akan diarahkan ke dashboard.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role', '').lower() != 'superadmin':
            flash('Akses ditolak. Halaman ini hanya untuk Super Administrator.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """
    Redirect ke halaman login jika belum login
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Halaman login
    """
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Email dan password harus diisi!', 'error')
            return render_template('login.html')
        
        try:
            user = get_user_by_email(email)
        except Exception as e:
            flash(f'Error koneksi database: {str(e)}. Pastikan database sudah diinisialisasi!', 'error')
            return render_template('login.html')
        
        if user:
            if verify_password(user['password'], password):
                if user['status_akun'] == 'aktif':
                    session['user_id'] = user['id']
                    session['nama_lengkap'] = user['nama_lengkap']
                    session['email'] = user['email']
                    session['role'] = user['role']
                    session['status_akun'] = user['status_akun']
                    session.permanent = True
                    
                    flash('Login berhasil!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Akun Anda tidak aktif!', 'error')
                    return render_template('login.html')
            else:
                flash('Email atau password salah!', 'error')
                return render_template('login.html')
        else:
            flash('Email atau password salah!', 'error')
            return render_template('login.html')

    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Logout dan hapus session
    """
    session.clear()
    flash('Anda telah logout!', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@require_login
def dashboard():
    jumlah_warga_aktif = 0
    jumlah_warga_nonaktif = 0
    jumlah_penyaluran = 0
    jumlah_akun_aktif = 0
    persentase_bantuan = 0
    persentase_bantuan_petugas = 0
    penerima_terbaru = []
    status_warga = {}
    data_per_bulan = [0] * 12
    penerima_per_kuartal = [0, 0, 0, 0]
    penerima_per_kuartal_petugas = [0, 0, 0, 0]

    try:
        role = session.get('role', '').lower()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                QUARTER(tanggal_terima) as kuartal,
                COUNT(*) as jumlah
            FROM data_penerima
            GROUP BY QUARTER(tanggal_terima)
        """)
        hasil_kuartal = cursor.fetchall()
        print("DEBUG KUARTAL:", hasil_kuartal)

        penerima_per_kuartal = [0, 0, 0, 0]
        for row in hasil_kuartal:
            kuartal = row[0]
            jumlah = row[1]
            if 1 <= kuartal <= 4:
                penerima_per_kuartal[kuartal - 1] = jumlah

        # TOTAL WARGA
        cursor.execute("SELECT COUNT(*) FROM warga_penerima WHERE status='aktif'")
        jumlah_warga_aktif = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM warga_penerima WHERE status='tidak_aktif'")
        jumlah_warga_nonaktif = cursor.fetchone()[0]

        # TOTAL PENERIMA BANTUAN
        if role == 'petugas lapangan':
            user_id = session.get('user_id')
            if user_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM data_penerima WHERE input_by = %s",
                    (user_id,)
                )
                jumlah_penyaluran = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(DISTINCT warga_id)
                    FROM data_penerima
                    WHERE input_by = %s
                      AND warga_id IN (SELECT id FROM warga_penerima WHERE status = 'aktif')
                """, (user_id,))
                jumlah_warga_petugas_dapat_bantuan = cursor.fetchone()[0] or 0

                cursor.execute("""
                    SELECT COUNT(DISTINCT id) FROM warga_penerima
                    WHERE status = 'aktif'
                      AND id IN (
                          SELECT DISTINCT warga_id FROM data_penerima WHERE input_by = %s
                      )
                """, (user_id,))
                total_warga_tanganan = cursor.fetchone()[0] or 1
                persentase_bantuan_petugas = round(
                    (jumlah_warga_petugas_dapat_bantuan / total_warga_tanganan) * 100, 1
                )

                cursor.execute("""
                    SELECT QUARTER(tanggal_terima) as kuartal, COUNT(*) as jumlah
                    FROM data_penerima
                    WHERE input_by = %s
                    GROUP BY QUARTER(tanggal_terima)
                """, (user_id,))
                penerima_per_kuartal_petugas = [0, 0, 0, 0]
                for row in cursor.fetchall():
                    k, j = row[0], row[1]
                    if 1 <= k <= 4:
                        penerima_per_kuartal_petugas[k - 1] = j
        else:
            cursor.execute("SELECT COUNT(*) FROM data_penerima")
            jumlah_penyaluran = cursor.fetchone()[0]

        # TOTAL AKUN AKTIF
        cursor.execute("SELECT COUNT(*) FROM users WHERE status_akun = 'Aktif'")
        jumlah_akun_aktif = cursor.fetchone()[0]

        # PERSENTASE PENYALURAN (admin & superadmin) 
        total_warga_aktif = jumlah_warga_aktif or 1
        cursor.execute("""
            SELECT COUNT(DISTINCT warga_id) 
            FROM data_penerima 
            WHERE warga_id IN (SELECT id FROM warga_penerima WHERE status='aktif')
        """)
        jumlah_warga_yang_mendapat_bantuan = cursor.fetchone()[0] or 0
        persentase_bantuan = round(
            (jumlah_warga_yang_mendapat_bantuan / total_warga_aktif) * 100, 1
        )

        # DATA PENERIMA TERBARU
        cursor.execute("""
            SELECT 
                w.nama_encrypted,
                w.nik_encrypted,
                u.nama_lengkap AS nama_petugas,
                dp.created_at
            FROM data_penerima dp
            JOIN warga_penerima w ON dp.warga_id = w.id
            LEFT JOIN users u ON dp.input_by = u.id
            ORDER BY dp.created_at DESC
            LIMIT 5
        """)

        rows = cursor.fetchall()

        penerima_terbaru = []
        for row in rows:
            penerima_terbaru.append({
                "nama": decrypt_data(row[0]) if row[0] else "-",
                "nik": decrypt_data(row[1]) if row[1] else "-",
                "nama_petugas": row[2],
                "created_at": row[3]
            })

        # STATUS WARGA
        cursor.execute("""
            SELECT status, COUNT(*) as jumlah 
            FROM warga_penerima 
            GROUP BY status
        """)
        status_warga = dict(cursor.fetchall())

        cursor.close()
        conn.close()

    except Exception as e:
        traceback.print_exc()

    return render_template(
        'dashboard.html',
        jumlah_akun_aktif=jumlah_akun_aktif,
        jumlah_warga_aktif=jumlah_warga_aktif,
        jumlah_warga_nonaktif=jumlah_warga_nonaktif,
        jumlah_penyaluran=jumlah_penyaluran,
        persentase_bantuan=persentase_bantuan,
        persentase_bantuan_petugas=persentase_bantuan_petugas,
        penerima_terbaru=penerima_terbaru,
        data_per_bulan=data_per_bulan,
        status_warga=status_warga,
        penerima_per_kuartal=penerima_per_kuartal,
        penerima_per_kuartal_petugas=penerima_per_kuartal_petugas,
    )
        
@app.route('/kelola-akun')
@require_login
@require_superadmin
def kelola_akun():
    """
    Halaman kelola akun
    """
    try:
        users = get_all_users()
        return render_template('kelola_akun.html', users=users or [])
    except Exception as e:
        traceback.print_exc()
        flash(f'Error mengambil data user: {str(e)}', 'error')
        return render_template('kelola_akun.html', users=[])

@app.route('/tambah-akun', methods=['GET', 'POST'])
@require_login
@require_superadmin
def tambah_akun():
    """
    Halaman tambah akun baru
    """
    if request.method == 'POST':
        try:
            nama_lengkap = request.form.get('nama_lengkap')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role', 'user')
            status_akun = request.form.get('status_akun', 'aktif')
            
            if not all([nama_lengkap, email, password]):
                flash('Semua field harus diisi!', 'error')
                return render_template('tambah_akun.html')
            
            create_user(nama_lengkap, password, email, role, status_akun)
            flash('User berhasil ditambahkan!', 'success')
            return redirect(url_for('kelola_akun'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            return render_template('tambah_akun.html')
    
    return render_template('tambah_akun.html')

@app.route('/edit-akun/<int:user_id>', methods=['GET', 'POST'])
@require_login
@require_superadmin
def edit_akun(user_id):
    """
    Halaman edit akun
    """
    if request.method == 'POST':
        try:
            nama_lengkap = request.form.get('nama_lengkap')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role')
            status_akun = request.form.get('status_akun')
            
            if not all([nama_lengkap, email, role, status_akun]):
                flash('Semua field harus diisi!', 'error')
                user = get_user_by_id(user_id)
                return render_template('edit_akun.html', user=user)
            
            update_user(user_id, nama_lengkap, email, role, status_akun, 
                       password if password else None)
            flash('User berhasil diupdate!', 'success')
            return redirect(url_for('kelola_akun'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            user = get_user_by_id(user_id)
            return render_template('edit_akun.html', user=user)
    
    try:
        user = get_user_by_id(user_id)
        if not user:
            flash('User tidak ditemukan!', 'error')
            return redirect(url_for('kelola_akun'))
        return render_template('edit_akun.html', user=user)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('kelola_akun'))

@app.route('/hapus-akun/<int:user_id>', methods=['POST'])
@require_login
@require_superadmin
def hapus_akun(user_id):
    """
    Hapus akun
    """
    try:
        if session.get('user_id') == user_id:
            flash('Anda tidak bisa menghapus akun sendiri!', 'error')
            return redirect(url_for('kelola_akun'))
        
        delete_user(user_id)
        flash('User berhasil dihapus!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('kelola_akun'))

@app.route('/warga-penerima')
@require_login
def warga_penerima():

    if session.get('role','').lower() != 'admin':
        flash("Hanya admin yang dapat mengakses halaman ini", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT w.*, u.nama_lengkap AS nama_petugas
        FROM warga_penerima w
        LEFT JOIN users u ON w.petugas_id = u.id
        ORDER BY w.id ASC
    """)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    hasil = []
    for r in rows:
        hasil.append({
            "id": r["id"],
            "nik": decrypt_data(r["nik_encrypted"]),
            "nama": decrypt_data(r["nama_encrypted"]),
            "tanggal_lahir": decrypt_data(r["tanggal_lahir_encrypted"]),
            "nomor_hp": decrypt_data(r["nomor_hp_encrypted"]) if r["nomor_hp_encrypted"] else "",
            "rt": decrypt_data(r["rt_encrypted"]),
            "status": r["status"].capitalize(),
            "nama_petugas": r["nama_petugas"]
        })

    return render_template('warga_penerima.html', data_warga=hasil)

@app.route('/warga-penerima/dekripsi/<int:warga_id>', methods=['POST'])
@require_login
def dekripsi_warga(warga_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT nik_encrypted, nomor_hp_encrypted 
            FROM warga_penerima 
            WHERE id = %s
        """, (warga_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "message": "Data tidak ditemukan."})

        nik = decrypt_data(row["nik_encrypted"]) if row["nik_encrypted"] else "-"
        nomor_hp = decrypt_data(row["nomor_hp_encrypted"]) if row["nomor_hp_encrypted"] else "-"

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "nik": nik,
            "nomor_hp": nomor_hp
        })

    except Exception as e:
        print("Dekripsi Error:", str(e))
        return jsonify({"success": False, "message": str(e)})

@app.route('/warga-penerima/tambah', methods=['GET', 'POST'])
@require_login
def tambah_warga():

    if session.get('role','').lower() != 'admin':
        flash("Hanya admin yang dapat mengakses halaman ini", "danger")
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT id, nama_lengkap 
        FROM users 
        WHERE LOWER(role) LIKE '%petugas%'
        AND LOWER(status_akun) = 'aktif'
    """)
    petugas = cursor.fetchall()

    if request.method == 'POST':
        try:
            nik = request.form.get('nik')
            nama = request.form.get('nama')
            tanggal_lahir = request.form.get('tanggal_lahir')
            nomor_hp = request.form.get('nomor_hp')
            rt = request.form.get('rt') 
            status = request.form.get('status')
            petugas_id = request.form.get('petugas_id')
            user_id = session.get('user_id')

            nik_enc = encrypt_data(nik)
            nama_enc = encrypt_data(nama)
            tanggal_lahir_enc = encrypt_data(tanggal_lahir)
            rt_enc = encrypt_data(rt)
            nomor_hp_enc = encrypt_data(nomor_hp) if nomor_hp else None

            conn = get_db_connection()
            cursor = conn.cursor()

            query = """
                INSERT INTO warga_penerima
                (nik_encrypted, nama_encrypted, tanggal_lahir_encrypted,
                nomor_hp_encrypted, rt_encrypted, status, created_by, petugas_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """

            cursor.execute(query, (
                nik_enc,
                nama_enc,
                tanggal_lahir_enc,
                nomor_hp_enc,
                rt_enc,
                status,
                user_id,
                petugas_id
            ))

            conn.commit()

            flash("Data warga berhasil disimpan", "success")
            return redirect(url_for('warga_penerima'))

        except Exception as e:
            traceback.print_exc()
            flash(f"Gagal menyimpan data: {e}", "danger")
    
    cursor.close()
    conn.close()

    return render_template('tambah_warga.html', petugas=petugas)

@app.route('/warga-penerima/edit/<int:id>', methods=['GET', 'POST'])
@require_login
def edit_warga(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, nama_lengkap 
        FROM users 
        WHERE LOWER(role) LIKE '%petugas%'
        AND LOWER(status_akun) = 'aktif'
    """)
    petugas = cursor.fetchall()

    if request.method == 'POST':
        nik = request.form.get('nik')
        nama = request.form.get('nama')
        tanggal_lahir = request.form.get('tanggal_lahir')
        nomor_hp = request.form.get('nomor_hp')
        rt = request.form.get('rt')
        status = request.form.get('status')
        petugas_id = request.form.get('petugas_id')

        data_encrypted = {
            "nik": encrypt_data(nik),
            "nama": encrypt_data(nama),
            "tanggal_lahir": encrypt_data(tanggal_lahir),
            "nomor_hp": encrypt_data(nomor_hp),
            "rt": encrypt_data(rt),
        }

        cursor.execute("""
            UPDATE warga_penerima 
            SET nik_encrypted=%s, nama_encrypted=%s, tanggal_lahir_encrypted=%s,
                nomor_hp_encrypted=%s, rt_encrypted=%s, status=%s, petugas_id=%s
            WHERE id=%s
        """, (
            data_encrypted["nik"],
            data_encrypted["nama"],
            data_encrypted["tanggal_lahir"],
            data_encrypted["nomor_hp"],
            data_encrypted["rt"],
            status,
            petugas_id,
            id
        ))

        conn.commit()
        
        flash("Data warga berhasil diubah", "success")
        cursor.close()
        conn.close()

        return redirect(url_for('warga_penerima'))

    cursor.execute("SELECT * FROM warga_penerima WHERE id=%s", (id,))
    warga = cursor.fetchone()

    warga = {
        "nik": decrypt_data(warga["nik_encrypted"]),
        "nama": decrypt_data(warga["nama_encrypted"]),
        "tanggal_lahir": decrypt_data(warga["tanggal_lahir_encrypted"]),
        "nomor_hp": decrypt_data(warga["nomor_hp_encrypted"]),
        "rt": decrypt_data(warga["rt_encrypted"]),
        "status": warga["status"],
        "petugas_id": warga["petugas_id"]
    }

    cursor.close()
    conn.close()

    return render_template("tambah_warga.html", warga=warga, petugas=petugas)

@app.route('/warga-penerima/hapus/<int:id>', methods=['POST'])
@require_login
def hapus_warga(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM warga_penerima WHERE id=%s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Data warga berhasil dihapus", "success")
    except Exception as e:
        traceback.print_exc()
        flash(f"Gagal menghapus data: {e}", "danger")
    return redirect(url_for('warga_penerima'))

@app.route('/data-penerima')
@require_login
def data_penerima():
    role = session.get('role', '').lower()
    user_id = session.get('user_id')

    tahap = request.args.get('tahap')
    tahun = request.args.get('tahun')
    tahap_filter = request.args.get('tahap')
    tahun_filter = request.args.get('tahun')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT p.id, p.tanggal_terima,
            pr.tahap, pr.tahun,
            p.bukti_terima_path AS bukti,
            w.nama_encrypted, w.nik_encrypted, w.rt_encrypted,
            u.nama_lengkap AS petugas_lapangan
        FROM data_penerima p
        JOIN warga_penerima w ON p.warga_id = w.id
        JOIN periode pr ON p.periode_id = pr.id
        LEFT JOIN users u ON p.input_by = u.id
    """

    conditions = []
    params = []

    if role == 'petugas lapangan':
        conditions.append("p.input_by = %s")
        params.append(user_id)

    if tahap:
        conditions.append("pr.tahap = %s")
        params.append(tahap)

    if tahun:
        conditions.append("pr.tahun = %s")
        params.append(tahun)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY p.tanggal_terima DESC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    cursor.execute("SELECT DISTINCT tahun FROM periode ORDER BY tahun DESC")
    tahun_list = cursor.fetchall()
    
    cursor.execute("""
        SELECT id, tahun, tahap
        FROM periode
        ORDER BY tahun DESC, tahap ASC
    """)
    periode_list = cursor.fetchall()
        
    cursor.close()
    conn.close()

    data = []
    for r in rows:
        data.append({
            "id": r["id"],     
            "nama": decrypt_data(r["nama_encrypted"]) if r["nama_encrypted"] else "",
            "nik": decrypt_data(r["nik_encrypted"]) if r["nik_encrypted"] else "•••••••••••",
            "rt": decrypt_data(r["rt_encrypted"]) if r["rt_encrypted"] else "-",
            "petugas_lapangan": r["petugas_lapangan"] or "-",
            "tanggal_terima": r["tanggal_terima"].strftime("%Y-%m-%d") if r["tanggal_terima"] else "-",
            "tahap": r["tahap"],
            "tahun": r["tahun"],
            "bukti": r["bukti"]
        })

    return render_template('data_penerima.html', data=data, tahap_selected=tahap_filter, tahun_selected=tahun_filter, tahun_list=tahun_list, periode_list=periode_list)

@app.route('/data-penerima/dekripsi/<int:data_id>', methods=['POST'])
@require_login
def dekripsi_data_penerima(data_id):
    """
    Endpoint AJAX: dekripsi NIK dan No HP dari satu baris data_penerima.
    Hanya bisa diakses oleh user yang sudah login.
    """
    from flask import jsonify

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT w.nik_encrypted, w.nomor_hp_encrypted
            FROM data_penerima dp
            JOIN warga_penerima w ON dp.warga_id = w.id
            WHERE dp.id = %s
        """, (data_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row:
            return jsonify({"success": False, "message": "Data tidak ditemukan."}), 404

        nik      = decrypt_data(row["nik_encrypted"])
        nomor_hp = decrypt_data(row["nomor_hp_encrypted"]) if row["nomor_hp_encrypted"] else "-"

        return jsonify({"success": True, "nik": nik, "nomor_hp": nomor_hp})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/data-penerima/input', methods=['GET', 'POST'])
@require_login
def input_data_penerima():
    if session.get('role','').lower() != 'petugas lapangan':
        flash("Hanya petugas lapangan yang bisa menginput data", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    user_id = session.get('user_id')

    cursor.execute("""
        SELECT id, nama_encrypted, rt_encrypted
        FROM warga_penerima
        WHERE status = 'aktif' AND petugas_id = %s
        ORDER BY nama_encrypted
    """, (user_id,))
    warga_list = cursor.fetchall()

    for w in warga_list:
        w['nama'] = decrypt_data(w['nama_encrypted'])
        w['rt'] = decrypt_data(w['rt_encrypted'])

    cursor.execute("SELECT * FROM periode WHERE status='aktif'")
    periode_list = cursor.fetchall()
    
    print("DATA PERIODE:", periode_list)
    
    for p in periode_list:
        if str(p['tahap']) == '1':
            p['label'] = "Tahap 1: Januari - Maret"
        elif str(p['tahap']) == '2':
            p['label'] = "Tahap 2: April - Juni"
        elif str(p['tahap']) == '3':
            p['label'] = "Tahap 3: Juli - September"
        elif str(p['tahap']) == '4':
            p['label'] = "Tahap 4: Oktober - Desember"
        else:
            p['label'] = f"Tahap {p['tahap']}"

    current_year = datetime.now().year

    cursor.execute("SELECT nama_lengkap FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    nama_petugas = user["nama_lengkap"] if user else "-"

    if request.method == 'POST':
        try:
            warga_id = request.form.get('warga_id')
            periode_id = request.form.get('periode_id')
            tanggal_terima = request.form.get('tanggal_terima')
            file = request.files.get('bukti_terima')

            filename = None
            if file:
                filename = f"{int(time.time())}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            cursor.execute("""
                SELECT dp.id
                FROM data_penerima dp
                JOIN periode p ON dp.periode_id = p.id
                WHERE dp.warga_id = %s
                AND p.tahun = (SELECT tahun FROM periode WHERE id = %s)
                AND p.tahap = (SELECT tahap FROM periode WHERE id = %s)
            """, (warga_id, periode_id, periode_id))

            if cursor.fetchone():
                flash("Warga sudah pernah menerima bantuan di tahun & tahap ini!", "warning")
                return redirect(url_for('input_data_penerima'))

            existing = cursor.fetchone()

            if existing:
                flash("Data sudah pernah diinput untuk warga dan periode ini!", "warning")
                return redirect(url_for('input_data_penerima'))

            cursor.execute("""
                INSERT INTO data_penerima
                (warga_id, periode_id, tanggal_terima, created_at, input_by, bukti_terima_path)
                VALUES (%s, %s, %s, NOW(), %s, %s)
            """, (warga_id, periode_id, tanggal_terima, user_id, filename))

            conn.commit()
            flash("Data penerima berhasil disimpan", "success")
            return redirect(url_for('data_penerima'))

        except Exception as e:
            traceback.print_exc()
            flash(f"Gagal menyimpan data: {e}", "danger")

            filename = None
        if file:
            filename = f"{int(time.time())}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor.execute("""
            INSERT INTO data_penerima
            (warga_id, periode_id, tanggal_terima, created_at, input_by, bukti_terima_path)
            VALUES (%s, %s, %s, NOW(), %s, %s)
        """, (warga_id, periode_id, tanggal_terima, user_id, filename))

        conn.commit()
    cursor.close()
    conn.close()

    return render_template(
        'input_data_penerima.html',
        warga_list=warga_list,
        periode=periode_list,
        current_year=current_year,
        nama_petugas=nama_petugas,
        user_id=user_id
    )
            
@app.route('/generate-periode', methods=['POST'])
@require_login
def generate_periode():
    if session.get('role','').lower() != 'superadmin':
        flash("Hanya superadmin yang bisa generate periode", "danger")
        return redirect(url_for('dashboard'))

    tahun = request.form.get('tahun')
    if not tahun:
        flash("Tahun harus diisi", "danger")
        return redirect(url_for('form_generate_periode'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT MAX(tahap) as tahap_terakhir 
            FROM periode 
            WHERE tahun = %s
        """, (tahun,))
        
        result = cursor.fetchone()
        
        tahap_terakhir = 0
        if result and result['tahap_terakhir'] is not None:
            tahap_terakhir = int(result['tahap_terakhir'])

        if tahap_terakhir >= 4:
            flash(f"Periode di tahun {tahun} sudah mencapai batas!", "swal-warning")
            cursor.close()
            conn.close()
            return redirect(url_for('form_generate_periode'))

        tahap_baru = tahap_terakhir + 1

        cursor.execute("""
            INSERT INTO periode (tahun, tahap, status, created_at)
            VALUES (%s, %s, 'nonaktif', NOW())
        """, (tahun, tahap_baru))

        conn.commit()
        flash(f"Periode tahun {tahun} Tahap {tahap_baru} berhasil dibuat!", "swal-success")

    except Exception as e:
        conn.rollback()
        flash(f"Gagal generate periode: {e}", "danger")

    cursor.close()
    conn.close()

    return redirect(url_for('form_generate_periode'))

@app.route('/form-generate-periode')
@require_login
def form_generate_periode():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM periode
        ORDER BY tahun DESC, tahap ASC
    """)

    periode_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'generate_periode.html',
        periode_list=periode_list
    )
    
@app.route('/periode/status/<int:id>')
@require_login
def ubah_status_periode(id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT status FROM periode WHERE id=%s",
        (id,)
    )

    data = cursor.fetchone()

    if data:

        status_baru = (
            'aktif'
            if data['status'] == 'nonaktif'
            else 'nonaktif'
        )

        cursor.execute("""
            UPDATE periode
            SET status=%s
            WHERE id=%s
        """, (status_baru, id))

        conn.commit()

    cursor.close()
    conn.close()

    flash("Status periode berhasil diperbarui", "success")

    return redirect(url_for('form_generate_periode'))

@app.route('/periode/edit/<int:id>', methods=['GET', 'POST'])
@require_login
def edit_periode(id):

    if session.get('role','').lower() != 'superadmin':
        flash("Hanya superadmin yang dapat mengubah periode", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':

        tahun = request.form.get('tahun')
        tahap = request.form.get('tahap')

        cursor.execute("""
            SELECT id
            FROM periode
            WHERE tahun=%s
            AND tahap=%s
            AND id != %s
        """, (tahun, tahap, id))

        if cursor.fetchone():
            flash("Periode dengan tahun dan tahap tersebut sudah ada", "danger")
            return redirect(url_for('edit_periode', id=id))

        cursor.execute("""
            UPDATE periode
            SET tahun=%s,
                tahap=%s
            WHERE id=%s
        """, (tahun, tahap, id))

        conn.commit()

        flash("Periode berhasil diperbarui", "success")

        cursor.close()
        conn.close()

        return redirect(url_for('form_generate_periode'))

    cursor.execute(
        "SELECT * FROM periode WHERE id=%s",
        (id,)
    )

    periode = cursor.fetchone()

    if not periode:
        flash("Data periode tidak ditemukan", "danger")
        return redirect(url_for('form_generate_periode'))

    cursor.close()
    conn.close()

    return render_template(
        'edit_periode.html',
        periode=periode
    )
    
@app.route('/periode/hapus/<int:id>')
@require_login
def hapus_periode(id):

    if session.get('role', '').lower() != 'superadmin':
        flash("Hanya superadmin yang dapat menghapus periode", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM periode
            WHERE id = %s
        """, (int(id),))

        conn.commit()
        flash("Periode berhasil dihapus dari database.", "swal-success")

    except Exception as e:
        conn.rollback()
        flash(f"Database menolak penghapusan: {e}", "danger")

    cursor.close()
    conn.close()

    return redirect(url_for('form_generate_periode'))

@app.route('/periode/hapus-massal', methods=['POST'])
@require_login
def hapus_periode_massal():
    if session.get('role', '').lower() != 'superadmin':
        flash("Hanya superadmin yang dapat menghapus periode", "danger")
        return redirect(url_for('dashboard'))

    ids_terpilih = request.form.getlist('ids_periode')

    if not ids_terpilih:
        flash("Tidak ada periode yang dipilih untuk dihapus.", "danger")
        return redirect(url_for('form_generate_periode'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        format_strings = ','.join(['%s'] * len(ids_terpilih))
        
        query = f"DELETE FROM periode WHERE id IN ({format_strings})"
        
        cursor.execute(query, tuple(ids_terpilih))
        conn.commit()

        flash(f"Berhasil menghapus {len(ids_terpilih)} periode yang terpilih.", "swal-success")

    except Exception as e:
        conn.rollback()
        flash(f"Gagal melakukan hapus massal: {e}", "danger")

    cursor.close()
    conn.close()

    return redirect(url_for('form_generate_periode'))

@app.route('/bukti/<filename>')
@require_login
def get_bukti(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download_laporan')
@require_login
@require_superadmin
def download_laporan():
    tahun = request.args.get('tahun')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
       SELECT
            id,
            nama_encrypted,
            nik_encrypted,
            rt_encrypted
        FROM warga_penerima
    """)
    semua_warga = cursor.fetchall()

    cursor.execute("""
    SELECT
            dp.warga_id,
            p.tahap,
            dp.tanggal_terima,
            dp.bukti_terima_path,
            p.tahun
        FROM data_penerima dp
        JOIN periode p
            ON dp.periode_id = p.id
        WHERE p.tahun = %s
        ORDER BY p.tahap ASC
    """, (tahun,))

    penyaluran = cursor.fetchall()

    tahun = request.args.get('tahun')

    tahun_laporan = tahun if tahun else 'Tidak_Diketahui'

    tahap_dict = {1: [], 2: [], 3: [], 4: []}
    warga_menerima = set()

    for p in penyaluran:
        try:
            tahap = int(p['tahap']) if p['tahap'] else 0
            if tahap in tahap_dict:
                tahap_dict[tahap].append(p)
                warga_menerima.add(p['warga_id'])
        except (ValueError, TypeError):
            continue

    tidak_menerima = []
    for w in semua_warga:
        if w['id'] not in warga_menerima:
            tidak_menerima.append({
                "Nama": decrypt_data(w.get("nama_encrypted")),
                "NIK": decrypt_data(w.get("nik_encrypted")),
                "RT": decrypt_data(w.get("rt_encrypted"))
            })

    # EXPORT EXCEL
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        warna_header = "#2078AF"
        warna_zebra = '#F9F9F9'
        warna_border = '#D3D3D3'

        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'bg_color': warna_header, 'font_color': 'white', 
            'border': 1, 'border_color': warna_border, 'font_name': 'Arial', 'font_size': 10
        })
        
        cell_center = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 
            'border': 1, 'border_color': warna_border, 'font_name': 'Arial', 'font_size': 10
        })
        cell_center_zebra = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'bg_color': warna_zebra,
            'border': 1, 'border_color': warna_border, 'font_name': 'Arial', 'font_size': 10
        })

        cell_left = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 
            'border': 1, 'border_color': warna_border, 'font_name': 'Arial', 'font_size': 10
        })
        cell_left_zebra = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'bg_color': warna_zebra,
            'border': 1, 'border_color': warna_border, 'font_name': 'Arial', 'font_size': 10
        })

        for tahap in [1, 2, 3, 4]:
            sheet_name = f"Tahap {tahap}"
            ws = workbook.add_worksheet(sheet_name)
            writer.sheets[sheet_name] = ws

            ws.set_column(0, 0, 6)
            ws.set_column(1, 1, 12)  
            ws.set_column(2, 2, 10)  
            ws.set_column(3, 3, 30)  
            ws.set_column(4, 4, 22)   
            ws.set_column(5, 5, 10)   
            ws.set_column(6, 6, 20)   
            ws.set_column(7, 7, 40)   

            headers = ["No", "Tahun","Tahap","Nama Lengkap", "NIK", "RT", "Tanggal Terima", "Bukti Terima"]
            for col, header in enumerate(headers):
                ws.write(0, col, header, header_format)

            ws.set_row(0, 28) 
            ws.freeze_panes(1, 0) 
            row_idx = 1
            for idx, p in enumerate(tahap_dict.get(tahap, []), 1):
                warga = next((w for w in semua_warga if w['id'] == p['warga_id']), None)
                if not warga:
                    continue
                fmt_left = cell_left_zebra if row_idx % 2 == 0 else cell_left
                fmt_center = cell_center_zebra if row_idx % 2 == 0 else cell_center

                nama_warga = decrypt_data(warga.get("nama_encrypted", ""))
                nik_warga = decrypt_data(warga.get("nik_encrypted", ""))
                rt_warga = decrypt_data(warga.get("rt_encrypted", ""))
                tgl_terima = str(p.get("tanggal_terima") or "-")

                ws.write(row_idx, 0, idx, fmt_center)
                ws.write(row_idx, 1, p['tahun'], fmt_center)
                ws.write(row_idx, 2, p['tahap'], fmt_center)
                ws.write(row_idx, 3, nama_warga, fmt_left)
                ws.write_string(row_idx, 4, nik_warga, fmt_center)
                ws.write_string(row_idx, 5, rt_warga, fmt_center)
                ws.write(row_idx, 6, tgl_terima, fmt_center)
                ws.write_blank(row_idx, 7, None, fmt_center)

                image_path = None
                if p.get("bukti_terima_path"):
                    image_path = os.path.join(
                        app.config['UPLOAD_FOLDER'],
                        p['bukti_terima_path']
                    )
                    if os.path.exists(image_path):
                        try:
                            ws.set_row(row_idx, 110)
                            ws.insert_image(row_idx, 7, image_path, {
                                'x_scale': 0.65,
                                'y_scale': 0.65,
                                'x_offset': 12,
                                'y_offset': 8,
                                'object_position': 1
                            })
                        except Exception as img_err:
                            ws.write(row_idx, 7, "Gbr Rusak", fmt_center)
                else:
                    ws.write(row_idx, 7, "-", fmt_center)

                if not p.get("bukti_terima_path") or not os.path.exists(image_path):
                    ws.set_row(row_idx, 22)

                row_idx += 1

        ws_tidak = workbook.add_worksheet("Tidak Menerima")
        writer.sheets["Tidak Menerima"] = ws_tidak

        ws_tidak.set_column(0, 0, 6)   
        ws_tidak.set_column(1, 1, 32)  
        ws_tidak.set_column(2, 2, 24)  
        ws_tidak.set_column(3, 3, 12)  

        headers_tidak = ["No", "Nama Lengkap", "NIK", "RT"]
        for col, header in enumerate(headers_tidak):
            ws_tidak.write(0, col, header, header_format)

        ws_tidak.set_row(0, 28)
        ws_tidak.freeze_panes(1, 0)

        row_idx = 1
        for idx, row in enumerate(tidak_menerima, 1):
            fmt_left = cell_left_zebra if row_idx % 2 == 0 else cell_left
            fmt_center = cell_center_zebra if row_idx % 2 == 0 else cell_center

            ws_tidak.set_row(row_idx, 22)
            ws_tidak.write(row_idx, 0, idx, fmt_center)
            ws_tidak.write(row_idx, 1, row["Nama"], fmt_left)
            ws_tidak.write_string(row_idx, 2, row["NIK"], fmt_center)
            ws_tidak.write_string(row_idx, 3, row["RT"], fmt_center)
            row_idx += 1

    output.seek(0)
    cursor.close()
    conn.close()

    return send_file(
        output,
        download_name=f"Laporan_PKH_{tahun_laporan}.xlsx",
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/download_laporan_pdf')
@require_login
@require_superadmin
def download_laporan_pdf():
    tahun = datetime.now().year
    
    bulan_id = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    now = datetime.now()
    nama_bulan = bulan_id[now.month]
    current_time_id = f"{now.day} {nama_bulan} {now.year}, {now.strftime('%H:%M')}"
    tanggal_ttd = f"{now.day} {nama_bulan} {now.year}"

    warna_header_biru = colors.HexColor('#1a5276')
    warna_header_abu = colors.HexColor('#7f8c8d')
    warna_zebra = colors.HexColor('#f2f2f2')

    tahun = request.args.get('tahun')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM warga_penerima ORDER BY nama_encrypted")
    semua_warga = cursor.fetchall()

    cursor.execute("""
        SELECT
            dp.warga_id,
            p.tahun,
            p.tahap,
            dp.tanggal_terima,
            dp.bukti_terima_path
        FROM data_penerima dp
        JOIN periode p
            ON dp.periode_id = p.id
        WHERE p.tahun = %s
        ORDER BY p.tahap ASC
    """, (tahun,))
    penyaluran = cursor.fetchall()
    cursor.close()
    conn.close()
    
    tahun = request.args.get('tahun')

    tahun_laporan = tahun if tahun else 'Tidak_Diketahui'
    tahap_dict = {1: [], 2: [], 3: [], 4: []}
    warga_menerima = set()

    for p in penyaluran:
        tahap = int(p.get('tahap') or 0)
        if tahap in tahap_dict:
            warga = next((w for w in semua_warga if w['id'] == p['warga_id']), None)
            if warga:
                tahap_dict[tahap].append({
                    "nama": decrypt_data(warga.get("nama_encrypted", "")),
                    "nik": decrypt_data(warga.get("nik_encrypted", "")),
                    "rt": decrypt_data(warga.get("rt_encrypted", "")),
                    "tanggal_terima": p.get("tanggal_terima"),
                    "bukti_terima_path": p.get("bukti_terima_path")
                })
                warga_menerima.add(p['warga_id'])

    tidak_menerima = []
    for w in semua_warga:
        if w['id'] not in warga_menerima:
            tidak_menerima.append({
                "nama": decrypt_data(w.get("nama_encrypted", "")),
                "nik": decrypt_data(w.get("nik_encrypted", "")),
                "rt": decrypt_data(w.get("rt_encrypted", ""))
            })

    # pdf
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2*cm,
        leftMargin=1.2*cm,
        topMargin=1.2*cm,
        bottomMargin=1.5*cm,
        title=f"Laporan PKH Tahun {tahun_laporan}",
        author="Pemerintah Desa Ngengor",
        subject="Laporan Penyaluran Program Keluarga Harapan",
        creator="Sistem Informasi Kelola Bantuan PKH"
    )
    elements = []
    styles = getSampleStyleSheet()

    style_kop = ParagraphStyle('KopSurat', parent=styles['Normal'], alignment=TA_CENTER, leading=14)
    style_tahap = ParagraphStyle('Tahap', parent=styles['Heading2'], fontSize=11, color=warna_header_biru, spaceBefore=14, spaceAfter=6)
    
    style_cell = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=9, leading=12)
    style_cell_center = ParagraphStyle('CellCenter', parent=style_cell, alignment=TA_CENTER)
    
    style_th = ParagraphStyle('TableHeader', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.whitesmoke, alignment=TA_CENTER, leading=10)
    style_meta_ttd = ParagraphStyle('MetaTTD', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)

    logo_path = os.path.join(app.static_folder, 'images', 'logo_kab.png')
    logo = Image(logo_path, width=2.0*cm, height=2.0*cm) if os.path.exists(logo_path) else Paragraph("LOGO", styles['Normal'])

    txt_header = Paragraph(
        "<font size=13><b>PEMERINTAH KABUPATEN MADIUN</b></font><br/>"
        "<font size=14><b>KECAMATAN PILANGKENCENG</b></font><br/>"
        "<font size=16><b>DESA NGENGOR</b></font><br/>"
        "<font size=8.5 color='#333333'>Sekretariat : Jln. Poros, Nomor. 65 Tlp. &nbsp;Kode Pos. 63154</font>", 
        style_kop
    )
    
    header_table = Table([[logo, txt_header]], colWidths=[2.5*cm, 16.1*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0)
    ]))
    elements.append(header_table)
    
    elements.append(HRFlowable(width="100%", thickness=2.5, lineCap='square', color=colors.black, spaceBefore=6))
    elements.append(HRFlowable(width="100%", thickness=0.8, lineCap='square', color=colors.black, spaceBefore=1.5, spaceAfter=8))
    
    style_title_doc = ParagraphStyle('TitleDoc', parent=styles['Title'], fontSize=12, spaceAfter=10, alignment=TA_CENTER, leading=14)
    elements.append(
        Paragraph(
            f"<b>LAPORAN PENYALURAN PROGRAM KELUARGA HARAPAN (PKH)<br/>TAHUN {tahun_laporan}</b>",
            style_title_doc
        )
    )
    elements.append(Spacer(1, 5))

    for tahap in [1, 2, 3, 4]:
        elements.append(Paragraph(f"PENYALURAN TAHAP {tahap}", style_tahap))
        
        if tahap_dict[tahap]:
            data = [[
                Paragraph("No", style_th), 
                Paragraph("Nama Lengkap", style_th), 
                Paragraph("NIK", style_th), 
                Paragraph("RT", style_th), 
                Paragraph("Tanggal Terima", style_th), 
                Paragraph("Bukti", style_th)
            ]]
            
            for i, row in enumerate(tahap_dict[tahap], 1):
                bukti_img = "-"
                if row.get("bukti_terima_path"):
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], row["bukti_terima_path"])
                    if os.path.exists(image_path):
                        try:
                            bukti_img = Image(image_path, width=2.5*cm, height=1.6*cm)
                        except:
                            bukti_img = Paragraph("Gbr Rusak", style_cell_center)

                data.append([
                    Paragraph(str(i), style_cell_center),
                    Paragraph(f"<b>{row['nama']}</b>", style_cell),
                    Paragraph(row["nik"], style_cell_center),
                    Paragraph(row["rt"], style_cell_center),
                    Paragraph(str(row["tanggal_terima"] or "-"), style_cell_center),
                    bukti_img
                ])
            
            t = Table(data, colWidths=[1.1*cm, 5.8*cm, 3.8*cm, 1.3*cm, 3.8*cm, 2.8*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), warna_header_biru),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, warna_zebra])
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("<i>Belum ada data penyaluran pada tahap ini.</i>", styles["Normal"]))
        
        elements.append(Spacer(1, 5))

    elements.append(Spacer(1, 5))
    elements.append(Paragraph("DATA WARGA TIDAK MENERIMA BANTUAN", style_tahap))
    
    if tidak_menerima:
        data_tm = [[
            Paragraph("No", style_th), 
            Paragraph("Nama Lengkap", style_th), 
            Paragraph("NIK", style_th), 
            Paragraph("RT", style_th)
        ]]
        for i, row in enumerate(tidak_menerima, 1):
            data_tm.append([
                Paragraph(str(i), style_cell_center),
                Paragraph(row["nama"], style_cell),
                Paragraph(row["nik"], style_cell_center),
                Paragraph(row["rt"], style_cell_center)
            ])
        
        t_tm = Table(data_tm, colWidths=[1.1*cm, 8.2*cm, 5.3*cm, 4*cm])
        t_tm.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), warna_header_abu),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, warna_zebra])
        ]))
        elements.append(t_tm)
    else:
        elements.append(Paragraph("Semua warga telah menerima bantuan.", styles["Normal"]))

    elements.append(Spacer(1, 20))
    ttd_data = [
        ["", Paragraph(f"Dicetak pada: {current_time_id}", style_meta_ttd)],
        ["", f"Ngengor, {tanggal_ttd}"],
        ["", "Petugas Pelaksana PKH,"],
        ["", ""],
        ["", ""],
        ["", ""],
        ["", "( ________________________________ )"],
        ["", ""],
        ["", "NIP. ................................."]
    ]
    ttd_table = Table(ttd_data, colWidths=[11.6*cm, 7*cm])
    ttd_table.setStyle(TableStyle([
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(ttd_table)

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        download_name=f"Laporan_PKH_{tahun_laporan}.pdf",
        as_attachment=True,
        mimetype='application/pdf'
    )
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)