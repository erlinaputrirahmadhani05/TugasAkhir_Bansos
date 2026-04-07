import hashlib
import base64
import time
import math
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

MASTER_KEY = "SI_BANSOS_DESA_NGENGOR_SECURE_KEY"
CAESAR_SHIFT = 13          # nilai geser Caesar
VIGENERE_KEY = "BANSOS"    # kunci Vigenere

def caesar_cipher(text, shift):
    hasil_enkripsi = ""

    for karakter in text:
        if karakter.isalpha():
            if karakter.isupper():
                basis = 'A'
            else:
                basis = 'a'

            posisi_awal = ord(karakter) - ord(basis)
            posisi_baru = (posisi_awal + shift) % 26
            karakter_baru = chr(posisi_baru + ord(basis))
            hasil_enkripsi += karakter_baru

        elif karakter.isdigit():
            angka_awal = int(karakter)
            angka_baru = (angka_awal + shift) % 10
            hasil_enkripsi += str(angka_baru)

        else:
            hasil_enkripsi += karakter

    return hasil_enkripsi

def vigenere_cipher(text, key):
    hasil_enkripsi = ""
    kunci_upper = key.upper()  
    indeks_kunci = 0  

    for karakter in text:
        if karakter.isalpha():
            karakter_kunci = kunci_upper[indeks_kunci % len(kunci_upper)]
            nilai_shift = ord(karakter_kunci) - ord('A')
            
            if karakter.isupper():
                basis = 'A'
            else:
                basis = 'a'
            
            posisi_awal = ord(karakter) - ord(basis)
            posisi_baru = (posisi_awal + nilai_shift) % 26
            karakter_baru = chr(posisi_baru + ord(basis))
            hasil_enkripsi += karakter_baru
            
            indeks_kunci += 1  
        
        elif karakter.isdigit():
            karakter_kunci = kunci_upper[indeks_kunci % len(kunci_upper)]
            nilai_shift = ord(karakter_kunci) - ord('A')

            angka_awal = int(karakter)
            angka_baru = (angka_awal + nilai_shift) % 10
            hasil_enkripsi += str(angka_baru)
            
            indeks_kunci += 1 
        
        else:
            hasil_enkripsi += karakter

    return hasil_enkripsi

def rc4_encrypt(data, key):
    array_S = list(range(256))

    kunci_bytes = key.encode()

    j = 0  

    # --- KSA (Key Scheduling Algorithm) ---
    for i in range(256):
        posisi_kunci = i % len(kunci_bytes)
        j = (j + array_S[i] + kunci_bytes[posisi_kunci]) % 256
        array_S[i], array_S[j] = array_S[j], array_S[i]

    # --- PRGA (Pseudo Random Generation) ---
    i = 0
    j = 0
    hasil_enkripsi = bytearray()
    data_bytes = data.encode()

    for byte_data in data_bytes:
        i = (i + 1) % 256
        j = (j + array_S[i]) % 256

        array_S[i], array_S[j] = array_S[j], array_S[i]

        indeks_byte_acak = (array_S[i] + array_S[j]) % 256
        byte_acak = array_S[indeks_byte_acak]

        byte_terenkripsi = byte_data ^ byte_acak
        hasil_enkripsi.append(byte_terenkripsi)

    return bytes(hasil_enkripsi)

def blum_blum_shub_generate_iv(length_bytes=16):
    # 1. Pilih bilangan prima (≡ 3 mod 4)
    p = 383
    q = 503

    # 2. Hitung n = p * q
    n = p * q

    # 3. Pilih seed (s)
    seed = int(time.time() * 1000000) % n

    # Pastikan seed valid: 2 ≤ s < n
    if seed < 2:
        seed = 2

    # Pastikan relatif prima dengan n (gcd = 1)
    while math.gcd(seed, n) != 1:
        seed = (seed + 1) % n
        if seed < 2:
            seed = 2

    # 4. Hitung x0 = s^2 mod n
    x = (seed * seed) % n

    # 5. Generate bit acak
    jumlah_bit = length_bytes * 8
    iv_bits = []

    for _ in range(jumlah_bit):
        # xi = xi-1^2 mod n
        x = (x * x) % n

        # ambil LSB
        bit = x & 1
        iv_bits.append(bit)

    # 6. Konversi bit → byte
    iv_bytes = bytearray()
    for i in range(0, len(iv_bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(iv_bits):
                byte |= (iv_bits[i + j] << j)
        iv_bytes.append(byte)

    return bytes(iv_bytes[:length_bytes])

def aes_cbc_encrypt(data_bytes, key):
    iv = blum_blum_shub_generate_iv(16)
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    
    padder = padding.PKCS7(128).padder()  # 128 bit = 16 bytes
    data_padded = padder.update(data_bytes)
    data_padded += padder.finalize()
    
    ciphertext = encryptor.update(data_padded) + encryptor.finalize()
    hasil_enkripsi = iv + ciphertext
    
    return hasil_enkripsi

# kunci turunan
def generate_derived_key_1(master_key):
    caesar_result = caesar_cipher(master_key, CAESAR_SHIFT)
    return hashlib.sha256(caesar_result.encode()).hexdigest()

def generate_aes_key_from_vigenere(master_key):
    vigenere_result = vigenere_cipher(master_key, VIGENERE_KEY)
    aes_key = hashlib.sha256(vigenere_result.encode()).digest()

    return aes_key

# enkripsi layer utama
def encrypt_data(data):
    if not data:
        return ""
    kunci_rc4 = generate_derived_key_1(MASTER_KEY)
    data_terenkripsi_rc4 = rc4_encrypt(str(data), kunci_rc4)
    kunci_aes = generate_aes_key_from_vigenere(MASTER_KEY)
    data_terenkripsi_aes = aes_cbc_encrypt(data_terenkripsi_rc4, kunci_aes)
    
    return base64.b64encode(data_terenkripsi_aes).decode()

def encrypt_dict(data_dict):
    return {
        key: encrypt_data(value) if value else None
        for key, value in data_dict.items()
    }
