from datetime import timedelta
import os

# Flask Configuration
SECRET_KEY = 'your-secret-key-change-this-in-production'
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

# File Upload Configuration
UPLOAD_FOLDER = 'static/uploads/bukti_terima'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Buat folder upload jika belum ada
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
