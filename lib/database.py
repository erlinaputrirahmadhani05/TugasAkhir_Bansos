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
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama_lengkap VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            role ENUM('superadmin', 'admin', 'petugas lapangan') NOT NULL DEFAULT 'petugas lapangan',
            status_akun ENUM('aktif', 'nonaktif') NOT NULL DEFAULT 'aktif',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_table_query)
        
        check_user_query = "SELECT COUNT(*) as count FROM users WHERE email = 'superadmin@gmail.com'"
        cursor.execute(check_user_query)
        result = cursor.fetchone()
        
        if use_dict and isinstance(result, dict):
            count = result.get('count', 0)
        elif isinstance(result, tuple):
            count = result[0]
        else:
            count = 0
        
        if count == 0:
            hashed_password = generate_password_hash('superadmin123')
            
            insert_user_query = """
            INSERT INTO users (nama_lengkap, password, email, role, status_akun)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_user_query, (
                'Super Administrator',
                hashed_password,
                'superadmin@gmail.com',
                'superadmin',
                'aktif'
            ))
            print("Superadmin berhasil ditambahkan ke database!")
        
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
        
        query = "SELECT id, nama_lengkap, email, role, status_akun, created_at FROM users ORDER BY created_at ASC"
        cursor.execute(query)
        users = cursor.fetchall()

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

def create_user(nama_lengkap, password, email, role='petugas lapangan', status_akun='aktif'):
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

        from lib.password_utils import hash_password
        hashed_password = hash_password(password)
        
        check_query = "SELECT COUNT(*) as count FROM users WHERE email = %s"
        cursor.execute(check_query, (email))
        result = cursor.fetchone()
        count = result.get('count', 0) if isinstance(result, dict) else result[0] if isinstance(result, tuple) else 0
        
        if count > 0:
            raise Exception("Username atau email sudah terdaftar!")
        
        insert_query = """
        INSERT INTO users (nama_lengkap, password, email, role, status_akun)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (nama_lengkap, hashed_password, email, role, status_akun))
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

def update_user(user_id, nama_lengkap, email, role, status_akun, password=None):
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
        
        check_query = "SELECT COUNT(*) as count FROM users WHERE email = %s AND id != %s"
        cursor.execute(check_query, (email, user_id))
        result = cursor.fetchone()
        count = result.get('count', 0) if isinstance(result, dict) else result[0] if isinstance(result, tuple) else 0
        
        if count > 0:
            raise Exception("Email sudah digunakan user lain!")
        
        if password:
            from lib.password_utils import hash_password
            hashed_password = hash_password(password)
            update_query = """
            UPDATE users 
            SET nama_lengkap = %s, email = %s, role = %s, status_akun = %s, password = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (nama_lengkap, email, role, status_akun, hashed_password, user_id))
        else:
            update_query = """
            UPDATE users 
            SET nama_lengkap = %s, email = %s, role = %s, status_akun = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (nama_lengkap, email, role, status_akun, user_id))
        
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