import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    import pymysql
    from config import DB_CONFIG
    PYMySQL_AVAILABLE = True
except ImportError:
    try:
        import mysql.connector as pymysql
        from config import DB_CONFIG
        PYMySQL_AVAILABLE = True
    except ImportError:
        PYMySQL_AVAILABLE = False
        print("Warning: PyMySQL atau mysql-connector-python tidak terinstall!")
        print("Install dengan: pip install pymysql")

from werkzeug.security import generate_password_hash, check_password_hash

def get_db_connection():
    """
    Membuat koneksi ke database MySQL
    """
    if not PYMySQL_AVAILABLE:
        return None
    
    try:
        # Coba menggunakan pymysql (PyMySQL)
        try:
            connection = pymysql.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset=DB_CONFIG['charset'],
                cursorclass=pymysql.cursors.DictCursor
            )
        except AttributeError:
            # Jika menggunakan mysql-connector-python
            connection = pymysql.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset=DB_CONFIG['charset']
            )
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def _get_cursor(connection):
    """
    Helper function untuk mendapatkan cursor dengan tipe yang sesuai
    Returns: (cursor, use_dict)
    """
    try:
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        use_dict = True
    except (AttributeError, TypeError):
        try:
            cursor = connection.cursor(dictionary=True)
            use_dict = True
        except TypeError:
            cursor = connection.cursor()
            use_dict = False
    return cursor, use_dict

def init_database():
    """
    Membuat tabel users dan data_penerima jika belum ada
    """
    if not PYMySQL_AVAILABLE:
        print("Database library tidak tersedia. Install PyMySQL terlebih dahulu.")
        return False
    
    connection = get_db_connection()
    if not connection:
        print("Failed to connect to database!")
        return False
    
    cursor = None
    try:
        cursor, use_dict = _get_cursor(connection)
        
        # Buat tabel users
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama_lengkap VARCHAR(255) NOT NULL,
            username VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            role ENUM('superadmin', 'admin', 'petugas lapangan') NOT NULL DEFAULT 'petugas lapangan',
            status_akun ENUM('aktif', 'nonaktif') NOT NULL DEFAULT 'aktif',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_table_query)
        
        # Insert superadmin jika belum ada
        check_user_query = "SELECT COUNT(*) as count FROM users WHERE username = 'superadmin'"
        cursor.execute(check_user_query)
        result = cursor.fetchone()
        
        # Handle different cursor return types
        if use_dict and isinstance(result, dict):
            count = result.get('count', 0)
        elif isinstance(result, tuple):
            count = result[0]
        else:
            count = 0
        
        if count == 0:
            # Hash password sebelum disimpan
            hashed_password = generate_password_hash('superadmin123')
            
            insert_user_query = """
            INSERT INTO users (nama_lengkap, username, password, email, role, status_akun)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_user_query, (
                'Super Administrator',
                'superadmin',
                hashed_password,
                'superadmin@gmail.com',
                'superadmin',
                'aktif'
            ))
            print("Superadmin berhasil ditambahkan ke database!")
            
        # tabel master warga
        create_warga_table = """
        CREATE TABLE IF NOT EXISTS warga_penerima (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nik_encrypted TEXT NOT NULL,
            nama_encrypted TEXT NOT NULL,
            tanggal_lahir_encrypted TEXT,
            nomor_hp_encrypted TEXT,
            rt_encrypted TEXT NOT NULL,
            status ENUM('aktif','tidak_aktif') DEFAULT 'aktif',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
            created_by INT,
            updated_by INT,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_warga_table)
        
        # tabel penyaluran penerima
        create_penyaluran_table = """
        CREATE TABLE IF NOT EXISTS penyaluran_bantuan (
            id INT AUTO_INCREMENT PRIMARY KEY,
            warga_id INT NOT NULL,
            tanggal_terima DATE NOT NULL,
            tahap VARCHAR(50) NOT NULL,
            bukti_terima_path VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (warga_id) REFERENCES warga_penerima(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_penyaluran_table)
        
        # Buat tabel data_penerima untuk menyimpan data penerima terenkripsi
        create_table_query = """
        CREATE TABLE IF NOT EXISTS data_penerima (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nik_encrypted TEXT NOT NULL,
            no_kk_encrypted TEXT NOT NULL,
            nama_encrypted TEXT NOT NULL,
            alamat_encrypted TEXT NOT NULL,
            jenis_kelamin_encrypted TEXT NOT NULL,
            tanggal_lahir_encrypted TEXT NOT NULL,
            tanggal_penerimaan_encrypted TEXT NOT NULL,
            keterangan_encrypted TEXT,
            no_hp_encrypted TEXT NULL,
            uang_terima_encrypted TEXT NULL,
            tanggungan_encrypted TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            bukti_terima_path VARCHAR(500),
            created_by INT NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_table_query)
        
        # Migrasi: tambah kolom baru jika tabel sudah ada (database lama)
        for col in ['no_hp_encrypted', 'uang_terima_encrypted', 'tanggungan_encrypted']:
            try:
                cursor.execute(f"ALTER TABLE data_penerima ADD COLUMN {col} TEXT NULL")
            except Exception:
                pass
        # Rename penghasilan_encrypted -> uang_terima_encrypted jika kolom lama masih ada
        try:
            cursor.execute("ALTER TABLE data_penerima CHANGE COLUMN penghasilan_encrypted uang_terima_encrypted TEXT NULL")
        except Exception:
            pass
        
        connection.commit()
        print("Database initialized successfully!")
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        if connection:
            connection.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_user_by_email(email):
    """
    Mengambil data user berdasarkan email
    """
    if not PYMySQL_AVAILABLE:
        raise Exception("Library MySQL belum terinstall. Install dengan: pip install pymysql")
    
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi ke database. Pastikan MySQL berjalan dan database 'kelola_bansos' sudah dibuat.")
    
    cursor = None
    try:
        cursor, use_dict = _get_cursor(connection)
        
        query = "SELECT * FROM users WHERE email = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        
        # Convert tuple to dict if needed
        if user and not isinstance(user, dict) and not use_dict:
            columns = [desc[0] for desc in cursor.description]
            user = dict(zip(columns, user))
        
        return user
    except Exception as e:
        raise Exception(f"Error fetching user: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_all_users():
    """
    Mengambil semua data user dari database
    """
    if not PYMySQL_AVAILABLE:
        raise Exception("Library MySQL belum terinstall. Install dengan: pip install pymysql")
    
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi ke database. Pastikan MySQL berjalan dan database 'kelola_bansos' sudah dibuat.")
    
    cursor = None
    try:
        cursor, use_dict = _get_cursor(connection)
        
        query = "SELECT id, nama_lengkap, username, email, role, status_akun, created_at FROM users ORDER BY created_at DESC"
        cursor.execute(query)
        users = cursor.fetchall()
        
        # Convert tuple to dict if needed
        if users and not isinstance(users[0], dict) and not use_dict:
            columns = [desc[0] for desc in cursor.description]
            users = [dict(zip(columns, user)) for user in users]
        
        return users
    except Exception as e:
        raise Exception(f"Error fetching users: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def create_user(nama_lengkap, username, password, email, role='petugas lapangan', status_akun='aktif'):
    """
    Membuat user baru di database
    """
    if not PYMySQL_AVAILABLE:
        raise Exception("Library MySQL belum terinstall. Install dengan: pip install pymysql")
    
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi ke database.")
    
    cursor = None
    try:
        try:
            cursor = connection.cursor(pymysql.cursors.DictCursor)
        except (AttributeError, TypeError):
            try:
                cursor = connection.cursor(dictionary=True)
            except TypeError:
                cursor = connection.cursor()
        
        # Hash password
        from lib.password_utils import hash_password
        hashed_password = hash_password(password)
        
        # Cek apakah username atau email sudah ada
        check_query = "SELECT COUNT(*) as count FROM users WHERE username = %s OR email = %s"
        cursor.execute(check_query, (username, email))
        result = cursor.fetchone()
        count = result.get('count', 0) if isinstance(result, dict) else result[0] if isinstance(result, tuple) else 0
        
        if count > 0:
            raise Exception("Username atau email sudah terdaftar!")
        
        # Insert user baru
        insert_query = """
        INSERT INTO users (nama_lengkap, username, password, email, role, status_akun)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (nama_lengkap, username, hashed_password, email, role, status_akun))
        connection.commit()
        return cursor.lastrowid
    except Exception as e:
        if connection:
            connection.rollback()
        raise Exception(f"Error creating user: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_user_by_id(user_id):
    """
    Mengambil data user berdasarkan ID
    """
    if not PYMySQL_AVAILABLE:
        raise Exception("Library MySQL belum terinstall.")
    
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi ke database.")
    
    cursor = None
    try:
        try:
            cursor = connection.cursor(pymysql.cursors.DictCursor)
            use_dict = True
        except (AttributeError, TypeError):
            try:
                cursor = connection.cursor(dictionary=True)
                use_dict = True
            except TypeError:
                cursor = connection.cursor()
                use_dict = False
        
        query = "SELECT * FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        
        if user and not isinstance(user, dict) and not use_dict:
            columns = [desc[0] for desc in cursor.description]
            user = dict(zip(columns, user))
        
        return user
    except Exception as e:
        raise Exception(f"Error fetching user: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def update_user(user_id, nama_lengkap, username, email, role, status_akun, password=None):
    """
    Update data user
    """
    if not PYMySQL_AVAILABLE:
        raise Exception("Library MySQL belum terinstall.")
    
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi ke database.")
    
    cursor = None
    try:
        try:
            cursor = connection.cursor(pymysql.cursors.DictCursor)
        except (AttributeError, TypeError):
            try:
                cursor = connection.cursor(dictionary=True)
            except TypeError:
                cursor = connection.cursor()
        
        # Cek apakah username atau email sudah digunakan user lain
        check_query = "SELECT COUNT(*) as count FROM users WHERE (username = %s OR email = %s) AND id != %s"
        cursor.execute(check_query, (username, email, user_id))
        result = cursor.fetchone()
        count = result.get('count', 0) if isinstance(result, dict) else result[0] if isinstance(result, tuple) else 0
        
        if count > 0:
            raise Exception("Username atau email sudah digunakan user lain!")
        
        # Update user
        if password:
            from lib.password_utils import hash_password
            hashed_password = hash_password(password)
            update_query = """
            UPDATE users 
            SET nama_lengkap = %s, username = %s, email = %s, role = %s, status_akun = %s, password = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (nama_lengkap, username, email, role, status_akun, hashed_password, user_id))
        else:
            update_query = """
            UPDATE users 
            SET nama_lengkap = %s, username = %s, email = %s, role = %s, status_akun = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (nama_lengkap, username, email, role, status_akun, user_id))
        
        connection.commit()
        return True
    except Exception as e:
        if connection:
            connection.rollback()
        raise Exception(f"Error updating user: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def delete_user(user_id):
    """
    Hapus user dari database
    """
    if not PYMySQL_AVAILABLE:
        raise Exception("Library MySQL belum terinstall.")
    
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi ke database.")
    
    cursor = None
    try:
        try:
            cursor = connection.cursor(pymysql.cursors.DictCursor)
        except (AttributeError, TypeError):
            try:
                cursor = connection.cursor(dictionary=True)
            except TypeError:
                cursor = connection.cursor()
        
        delete_query = "DELETE FROM users WHERE id = %s"
        cursor.execute(delete_query, (user_id,))
        connection.commit()
        return True
    except Exception as e:
        if connection:
            connection.rollback()
        raise Exception(f"Error deleting user: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def _ensure_data_penerima_extra_columns(cursor):
    """
    Tambah kolom no_hp_encrypted, uang_terima_encrypted, tanggungan_encrypted
    jika belum ada (untuk database yang dibuat sebelum kolom ini ditambahkan).
    """
    try:
        cursor.execute("ALTER TABLE data_penerima CHANGE COLUMN penghasilan_encrypted uang_terima_encrypted TEXT NULL")
    except Exception:
        pass
    for col in ['no_hp_encrypted', 'uang_terima_encrypted', 'tanggungan_encrypted']:
        try:
            cursor.execute(f"ALTER TABLE data_penerima ADD COLUMN {col} TEXT NULL")
        except Exception:
            pass  # Kolom sudah ada


def create_data_penerima(nik, no_kk, nama, alamat, jenis_kelamin, tanggal_lahir, 
                         tanggal_penerimaan, keterangan, bukti_terima_path, created_by,
                         no_hp=None, uang_terima=None, tanggungan=None):
    """
    Menyimpan data penerima terenkripsi ke database
    """
    if not PYMySQL_AVAILABLE:
        raise Exception("Library MySQL belum terinstall. Install dengan: pip install pymysql")
    
    from lib.encryption import encrypt_data
    
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi ke database.")
    
    cursor = None
    try:
        try:
            cursor = connection.cursor(pymysql.cursors.DictCursor)
            use_dict = True
        except (AttributeError, TypeError):
            try:
                cursor = connection.cursor(dictionary=True)
                use_dict = True
            except TypeError:
                cursor = connection.cursor()
                use_dict = False
        
        # Pastikan kolom opsional ada (migrasi untuk database lama)
        _ensure_data_penerima_extra_columns(cursor)
        connection.commit()
        
        # Enkripsi semua data
        nik_encrypted = encrypt_data(nik)
        no_kk_encrypted = encrypt_data(no_kk)
        nama_encrypted = encrypt_data(nama)
        alamat_encrypted = encrypt_data(alamat)
        jenis_kelamin_encrypted = encrypt_data(jenis_kelamin)
        tanggal_lahir_encrypted = encrypt_data(tanggal_lahir)
        tanggal_penerimaan_encrypted = encrypt_data(tanggal_penerimaan)
        keterangan_encrypted = encrypt_data(keterangan) if keterangan else None
        no_hp_encrypted = encrypt_data(no_hp) if no_hp else None
        uang_terima_encrypted = encrypt_data(uang_terima) if uang_terima else None
        tanggungan_encrypted = encrypt_data(tanggungan) if tanggungan else None
        
        # Insert data terenkripsi
        insert_query = """
        INSERT INTO data_penerima (
            nik_encrypted, no_kk_encrypted, nama_encrypted, alamat_encrypted,
            jenis_kelamin_encrypted, tanggal_lahir_encrypted, tanggal_penerimaan_encrypted,
            keterangan_encrypted, no_hp_encrypted, uang_terima_encrypted, tanggungan_encrypted,
            bukti_terima_path, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            nik_encrypted, no_kk_encrypted, nama_encrypted, alamat_encrypted,
            jenis_kelamin_encrypted, tanggal_lahir_encrypted, tanggal_penerimaan_encrypted,
            keterangan_encrypted, no_hp_encrypted, uang_terima_encrypted, tanggungan_encrypted,
            bukti_terima_path, created_by
        ))
        connection.commit()
        return cursor.lastrowid
    except Exception as e:
        if connection:
            connection.rollback()
        raise Exception(f"Error creating data penerima: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_all_data_penerima():
    """
    Mengambil semua data penerima terenkripsi
    """
    if not PYMySQL_AVAILABLE:
        raise Exception("Library MySQL belum terinstall. Install dengan: pip install pymysql")
    
    connection = get_db_connection()
    if not connection:
        raise Exception("Gagal koneksi ke database.")
    
    cursor = None
    try:
        try:
            cursor = connection.cursor(pymysql.cursors.DictCursor)
            use_dict = True
        except (AttributeError, TypeError):
            try:
                cursor = connection.cursor(dictionary=True)
                use_dict = True
            except TypeError:
                cursor = connection.cursor()
                use_dict = False
        
        query = """
        SELECT id, nik_encrypted, no_kk_encrypted, nama_encrypted, alamat_encrypted,
               jenis_kelamin_encrypted, tanggal_lahir_encrypted, tanggal_penerimaan_encrypted,
               keterangan_encrypted, no_hp_encrypted, uang_terima_encrypted, tanggungan_encrypted,
               bukti_terima_path, created_by, created_at
        FROM data_penerima
        ORDER BY created_at DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Convert tuple to dict if needed
        if results and not isinstance(results[0], dict) and not use_dict:
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in results]
        
        # Kembalikan data terenkripsi (tanpa dekripsi)
        return results
    except Exception as e:
        raise Exception(f"Error fetching data penerima: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_count_data_penerima_by_user(user_id):
    """
    Menghitung jumlah data penerima yang diinput oleh user tertentu (created_by = user_id).
    """
    if not PYMySQL_AVAILABLE:
        return 0
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return 0
    connection = get_db_connection()
    if not connection:
        return 0
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM data_penerima WHERE created_by = %s", (user_id,))
        row = cursor.fetchone()
        if row is None:
            return 0
        # PyMySQL returns tuple (count,); some drivers return dict
        return int(row[0]) if isinstance(row, (tuple, list)) else int(row.get('cnt', 0))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 0
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_count_all_data_penerima():
    """
    Menghitung jumlah total semua data penerima di database (untuk admin/superadmin).
    """
    if not PYMySQL_AVAILABLE:
        return 0
    connection = get_db_connection()
    if not connection:
        return 0
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM data_penerima")
        row = cursor.fetchone()
        if row is None:
            return 0
        # PyMySQL returns tuple (count,); some drivers return dict
        return int(row[0]) if isinstance(row, (tuple, list)) else int(row.get('cnt', 0))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 0
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
def create_warga(nik, nama, rt, created_by):
    from lib.encryption import encrypt_data

    connection = get_db_connection()
    cursor = connection.cursor()

    nik_encrypted = encrypt_data(nik)
    nama_encrypted = encrypt_data(nama)

    query = """
    INSERT INTO warga_penerima (nik_encrypted, nama_encrypted, rt_encrypted, created_by)
    VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (nik_encrypted, nama_encrypted, rt, created_by))

    connection.commit()
    connection.close()
    
def create_penyaluran(warga_id, tanggal_terima, tahap, bukti_path):
    connection = get_db_connection()
    cursor = connection.cursor()

    query = """
    INSERT INTO penyaluran_bantuan (warga_id, tanggal_terima, tahap, bukti_terima_path)
    VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (warga_id, tanggal_terima, tahap, bukti_path))

    connection.commit()
    connection.close()