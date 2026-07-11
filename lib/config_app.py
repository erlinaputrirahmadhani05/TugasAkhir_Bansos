from datetime import timedelta
import os

SECRET_KEY = 'your-secret-key-change-this-in-production'
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

UPLOAD_FOLDER = 'static/uploads/bukti_terima'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
