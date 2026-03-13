"""
Utility functions untuk password hashing dan verification
"""
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password):
    """
    Hash password menggunakan Werkzeug
    """
    return generate_password_hash(password)


def verify_password(password_hash, password):
    """
    Verifikasi password dengan hash yang tersimpan
    """
    return check_password_hash(password_hash, password)
