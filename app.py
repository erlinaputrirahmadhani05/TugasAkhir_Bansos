from flask import Flask, render_template, request, redirect, url_for, session, flash
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
from lib.data_penerima_service import get_all_data_penerima_decrypted
from lib.decryption import decrypt_data
from flask import send_from_directory
from datetime import datetime
import time
import os
import io
import pandas as pd
from flask import send_file
from datetime import datetime

# Import utilities
from lib.password_utils import verify_password
from lib.utils import save_uploaded_file

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
        if 'username' not in session:
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
    if 'username' in session:
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
        
        # Validasi input
        if not email or not password:
            flash('Email dan password harus diisi!', 'error')
            return render_template('login.html')
        
        # Cek kredensial berdasarkan email dari database
        try:
            user = get_user_by_email(email)
        except Exception as e:
            flash(f'Error koneksi database: {str(e)}. Pastikan database sudah diinisialisasi!', 'error')
            return render_template('login.html')
        
        if user:
            # Cek password menggunakan hash verification
            if verify_password(user['password'], password):
                if user['status_akun'] == 'aktif':
                    # Simpan data user ke session
                    session['user_id'] = user['id']
                    session['username'] = user['username']
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
    
    # Jika sudah login, redirect ke dashboard
    if 'username' in session:
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
    jumlah_warga = 0
    jumlah_penyaluran = 0
    jumlah_warga_aktif = 0
    jumlah_warga_nonaktif = 0

    try:
        role = session.get('role', '').lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        data_per_bulan = [0] * 12  # Jan - Des
        cursor.execute("""
            SELECT MONTH(created_at) as bulan, COUNT(*) as jumlah
            FROM data_penerima
            GROUP BY MONTH(created_at)
        """)
        
        hasil = cursor.fetchall()

        for row in hasil:
            bulan = row[0]
            jumlah = row[1]
            data_per_bulan[bulan - 1] = jumlah

        # TOTAL SEMUA WARGA
        cursor.execute("SELECT COUNT(*) FROM warga_penerima")
        jumlah_warga = cursor.fetchone()[0]

        # TOTAL WARGA AKTIF
        cursor.execute("SELECT COUNT(*) FROM warga_penerima WHERE status='aktif'")
        jumlah_warga_aktif = cursor.fetchone()[0]

        # TOTAL WARGA NONAKTIF
        cursor.execute("SELECT COUNT(*) FROM warga_penerima WHERE status='tidak_aktif'")
        jumlah_warga_nonaktif = cursor.fetchone()[0]

        if role == 'petugas lapangan':
            user_id = session.get('user_id')
            if user_id:
                cursor.execute("SELECT COUNT(*) FROM data_penerima WHERE input_by = %s", (user_id,))
                jumlah_penyaluran = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM data_penerima")
            jumlah_penyaluran = cursor.fetchone()[0]

        cursor.close()
        conn.close()

    except Exception as e:
        traceback.print_exc()

    return render_template(
        'dashboard.html',
        jumlah_warga=jumlah_warga,
        jumlah_penyaluran=jumlah_penyaluran,
        jumlah_warga_aktif=jumlah_warga_aktif,
        jumlah_warga_nonaktif=jumlah_warga_nonaktif,
        data_per_bulan=data_per_bulan
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
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role', 'user')
            status_akun = request.form.get('status_akun', 'aktif')
            
            # Validasi
            if not all([nama_lengkap, username, email, password]):
                flash('Semua field harus diisi!', 'error')
                return render_template('tambah_akun.html')
            
            # Buat user baru
            create_user(nama_lengkap, username, password, email, role, status_akun)
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
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role')
            status_akun = request.form.get('status_akun')
            
            # Validasi
            if not all([nama_lengkap, username, email, role, status_akun]):
                flash('Semua field harus diisi!', 'error')
                user = get_user_by_id(user_id)
                return render_template('edit_akun.html', user=user)
            
            # Update user
            update_user(user_id, nama_lengkap, username, email, role, status_akun, 
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
        # Cek apakah user yang login mencoba hapus dirinya sendiri
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
        ORDER BY w.id DESC
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

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if role == 'petugas lapangan':
        # Hanya data yang diinput oleh petugas ini
        cursor.execute("""
            SELECT p.id, p.tanggal_terima, p.tahap, p.tahun, 
                p.bukti_terima_path AS bukti,
                w.nama_encrypted, w.nik_encrypted, w.rt_encrypted,
                u.nama_lengkap AS petugas_lapangan
            FROM data_penerima p
            JOIN warga_penerima w ON p.warga_id = w.id
            LEFT JOIN users u ON p.input_by = u.id
            WHERE p.input_by = %s
            ORDER BY p.tahap ASC, p.tanggal_terima DESC
        """, (user_id,))
    else:
        # Admin / superadmin: semua data
        cursor.execute("""
            SELECT p.id, p.tanggal_terima, p.tahap, p.tahun, 
                p.bukti_terima_path AS bukti,
                w.nama_encrypted, w.nik_encrypted, w.rt_encrypted,
                u.nama_lengkap AS petugas_lapangan
            FROM data_penerima p
            JOIN warga_penerima w ON p.warga_id = w.id
            LEFT JOIN users u ON p.input_by = u.id
            ORDER BY p.tahap ASC, p.tanggal_terima DESC
        """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Decrypt nama & NIK
    grouped_data = {}

    for r in rows:
        tahap = r["tahap"] or "Tidak ada tahap"

        item = {
            "id": r["id"],
            "nama": decrypt_data(r["nama_encrypted"]),
            "nik": decrypt_data(r["nik_encrypted"]),
            "rt": decrypt_data(r["rt_encrypted"]),
            "petugas_lapangan": r["petugas_lapangan"],
            "tanggal_terima": r["tanggal_terima"].strftime("%Y-%m-%d") if r["tanggal_terima"] else "",
            "tahap": r["tahap"],
            "tahun": r["tahun"],
            "bukti": r["bukti"] if r["bukti"] else None
        }

        if tahap not in grouped_data:
            grouped_data[tahap] = []

        grouped_data[tahap].append(item)
        grouped_data = dict(sorted(grouped_data.items()))

    return render_template('data_penerima.html', grouped_data=grouped_data)

@app.route('/data-penerima/input', methods=['GET', 'POST'])
@require_login
def input_data_penerima():
    if session.get('role','').lower() != 'petugas lapangan':
        flash("Hanya petugas lapangan yang bisa menginput data", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    user_id = session.get('user_id')

    # Ambil daftar warga yang bisa dipilih oleh petugas ini (belum pernah diinput olehnya)
    cursor.execute("""
        SELECT id, nama_encrypted, rt_encrypted
        FROM warga_penerima
        WHERE status = 'aktif' AND petugas_id = %s
        ORDER BY nama_encrypted
    """, (user_id,))
    warga_list = cursor.fetchall()

    # Dekripsi nama supaya template tidak error
    for w in warga_list:
        w['nama'] = decrypt_data(w['nama_encrypted'])
        w['rt'] = decrypt_data(w['rt_encrypted'])

    current_year = datetime.now().year
    cursor.execute("SELECT nama_lengkap FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    nama_petugas = user["nama_lengkap"] if user else "-"

    if request.method == 'POST':
        try:
            warga_id = request.form.get('warga_id')
            tahun = request.form.get('tahun')
            tahap = request.form.get('tahap') 
            tanggal_terima = request.form.get('tanggal_terima')
            file = request.files.get('bukti_terima')

            filename = None
            if file:
                filename = f"{int(time.time())}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            cursor.execute("""
                SELECT id FROM data_penerima 
                WHERE warga_id = %s AND tahun = %s AND tahap = %s
            """, (warga_id, tahun, tahap))

            existing = cursor.fetchone()

            if existing:
                flash("Data sudah pernah diinput untuk warga, tahun, dan tahap ini!", "warning")
                return redirect(url_for('input_data_penerima'))
               
            
            # INSERT ke data_penerima
            cursor.execute("""
                INSERT INTO data_penerima
                (warga_id, tahun, tahap, tanggal_terima, created_at, input_by, bukti_terima_path)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s)
            """, (warga_id, tahun, tahap, tanggal_terima, user_id, filename))

            conn.commit()
            flash("Data penerima berhasil disimpan", "success")
            return redirect(url_for('data_penerima'))

        except Exception as e:
            traceback.print_exc()
            flash(f"Gagal menyimpan data: {e}", "danger")

    cursor.close()
    conn.close()
    return render_template(
        'input_data_penerima.html',
        warga_list=warga_list,
        current_year=current_year,
        nama_petugas=nama_petugas,
        user_id=user_id
    )
    
@app.route('/bukti/<filename>')
@require_login
def get_bukti(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/data-penerima/evaluasi')
@require_login
def evaluasi_penyaluran():
    if session.get('role','').lower() != 'admin':
        flash("Hanya admin yang dapat melihat evaluasi", "danger")
        return redirect(url_for('dashboard'))

    tahun = request.args.get('tahun')
    tahap = request.args.get('tahap')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Ambil daftar warga
    cursor.execute("SELECT * FROM warga_penerima ORDER BY nama_encrypted")
    warga_list = cursor.fetchall()

    # decrypt langsung
    for w in warga_list:
        w['nama'] = decrypt_data(w['nama_encrypted'])
        w['nik'] = decrypt_data(w['nik_encrypted'])

    # Ambil data penyaluran di periode tersebut
    cursor.execute("""
        SELECT warga_id, COUNT(*) as jumlah_penyaluran
        FROM data_penerima
        WHERE tahun=%s AND tahap=%s
        GROUP BY warga_id
    """, (tahun, tahap))
    penyaluran = {r['warga_id']: r['jumlah_penyaluran'] for r in cursor.fetchall()}

    hasil = []
    for w in warga_list:
        if w['id'] not in penyaluran:
            status = "Tidak menerima"
        else:
            status = "Menerima"

        hasil.append({
            "id": w['id'],
            "nama": decrypt_data(w['nama_encrypted']),
            "nik": decrypt_data(w['nik_encrypted']),
            "rt": decrypt_data(w["rt_encrypted"]),
            "status": status
        })

    return render_template('data_penerima.html', data=hasil)

@app.route('/download_laporan')
@require_login
@require_superadmin
def download_laporan():
    """
    Export laporan PKH per tahap dalam 1 file Excel
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    tahun = datetime.now().year

    # Ambil semua warga
    cursor.execute("SELECT * FROM warga_penerima")
    semua_warga = cursor.fetchall()

    # Ambil data penyaluran tahun berjalan
    cursor.execute("""
        SELECT warga_id, tahap, tanggal_terima, bukti_terima_path
        FROM data_penerima
        WHERE tahun = %s
        ORDER BY tahap ASC
    """, (tahun,))
    penyaluran = cursor.fetchall()

    cursor.close()
    conn.close()

    # Kelompokkan penerimaan per tahap
    tahap_dict = {1: [], 2: [], 3: [], 4: []}
    warga_menerima = set()

    for p in penyaluran:
        tahap = int(p['tahap'])
        tahap_dict[tahap].append(p)
        warga_menerima.add(p['warga_id'])

    # ====== DATA TIDAK MENERIMA ======
    tidak_menerima = []
    for w in semua_warga:
        if w['id'] not in warga_menerima:
            tidak_menerima.append({
                "Nama": decrypt_data(w["nama_encrypted"]),
                "NIK": decrypt_data(w["nik_encrypted"]),
                "RT": decrypt_data(w["rt_encrypted"])
            })

    df_tidak = pd.DataFrame(tidak_menerima)

    # ====== EXPORT MULTI SHEET EXCEL ======
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        # ===== FORMAT HEADER =====
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })
        cell_center_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        bukti_border_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        for tahap in [1, 2, 3, 4]:
            worksheet = workbook.add_worksheet(f"Tahap {tahap}")
            writer.sheets[f"Tahap {tahap}"] = worksheet

            # Atur lebar kolom
            worksheet.set_column(0, 0, 25)
            worksheet.set_column(1, 1, 22)
            worksheet.set_column(2, 2, 8)
            worksheet.set_column(3, 3, 18)
            worksheet.set_column(4, 4, 40)

            # Header
            headers = ["Nama", "NIK", "RT", "Tanggal Terima", "Bukti"]
            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)

            worksheet.set_row(0, 25)
            worksheet.freeze_panes(1, 0)

            row_idx = 1

            for p in tahap_dict[tahap]:
                warga = next((w for w in semua_warga if w['id'] == p['warga_id']), None)
                if not warga:
                    continue

                worksheet.write(row_idx, 0, decrypt_data(warga["nama_encrypted"]), cell_center_format)
                worksheet.write(row_idx, 1, decrypt_data(warga["nik_encrypted"]), cell_center_format)
                worksheet.write(row_idx, 2, decrypt_data(warga["rt_encrypted"]), cell_center_format)
                worksheet.write(row_idx, 3, str(p["tanggal_terima"]), cell_center_format)
                worksheet.write_blank(row_idx, 4, None, bukti_border_format)

                # ===== MASUKKAN GAMBAR =====
                if p["bukti_terima_path"]:
                    image_path = os.path.join(
                        app.config['UPLOAD_FOLDER'],
                        p['bukti_terima_path']
                    )

                    if os.path.exists(image_path):
                        worksheet.set_row(row_idx, 120)  # tinggi row

                        # Ambil ukuran gambar
                        img = Image.open(image_path)
                        img_width, img_height = img.size

                        # Scale gambar
                        scale = 0.4
                        scaled_width = img_width * scale
                        scaled_height = img_height * scale

                        # Ukuran cell (approx Excel)
                        cell_width = 220   # px (kolom 30 kira2 segini)
                        cell_height = 120  # sama dengan set_row

                        # Hitung posisi tengah
                        x_offset = int((cell_width - scaled_width) / 2)
                        y_offset = int((cell_height - scaled_height) / 2)

                        worksheet.insert_image(row_idx, 4, image_path, {
                            'x_scale': scale,
                            'y_scale': scale,
                            'x_offset': x_offset,
                            'y_offset': y_offset,
                            'object_position': 1
                        })
                    else:
                        print("Gambar tidak ditemukan:", image_path)

                row_idx += 1
                
        # ===== SHEET TIDAK MENERIMA =====
        worksheet_tidak = workbook.add_worksheet("Tidak Menerima")
        writer.sheets["Tidak Menerima"] = worksheet_tidak

        # Atur lebar kolom (samakan style Tahap)
        worksheet_tidak.set_column(0, 0, 25)
        worksheet_tidak.set_column(1, 1, 22)
        worksheet_tidak.set_column(2, 2, 8)

        # Header
        headers_tidak = ["Nama", "NIK", "RT"]
        for col, header in enumerate(headers_tidak):
            worksheet_tidak.write(0, col, header, header_format)

        worksheet_tidak.set_row(0, 25)
        worksheet_tidak.freeze_panes(1, 0)

        # Isi data
        row_idx = 1
        for row in tidak_menerima:
            worksheet_tidak.write(row_idx, 0, row["Nama"], cell_center_format)
            worksheet_tidak.write(row_idx, 1, row["NIK"], cell_center_format)
            worksheet_tidak.write(row_idx, 2, row["RT"], cell_center_format)
            row_idx += 1
    output.seek(0)

    return send_file(
        output,
        download_name=f"Laporan_PKH_{tahun}.xlsx",
        as_attachment=True
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)