import hashlib
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

MASTER_KEY = "SI_BANSOS_DESA_NGENGOR_SECURE_KEY"
CAESAR_SHIFT = 13
VIGENERE_KEY = "BANSOS"

def caesar_cipher(text, shift):
    hasil = ""
    for karakter in text:
        if karakter.isalpha():
            basis = 'A' if karakter.isupper() else 'a'
            posisi = (ord(karakter) - ord(basis) + shift) % 26
            hasil += chr(posisi + ord(basis))
        elif karakter.isdigit():
            hasil += str((int(karakter) + shift) % 10)
        else:
            hasil += karakter
    return hasil

def vigenere_cipher(text, key):
    hasil = ""
    key = key.upper()
    key_index = 0

    for char in text:
        if char.isalpha():
            key_char = key[key_index % len(key)]
            shift = ord(key_char) - ord('A')

            base = 'A' if char.isupper() else 'a'
            pos = (ord(char) - ord(base) + shift) % 26

            hasil += chr(pos + ord(base))
            key_index += 1

        elif char.isdigit():
            key_char = key[key_index % len(key)]
            shift = ord(key_char) - ord('A')

            hasil += str((int(char) + shift) % 10)
            key_index += 1

        else:
            hasil += char

    return hasil

def generate_derived_key_1(master_key):
    caesar_result = caesar_cipher(master_key, CAESAR_SHIFT)
    return hashlib.sha256(caesar_result.encode()).hexdigest()

def generate_aes_key_from_vigenere(master_key):
    vigenere_result = vigenere_cipher(master_key, VIGENERE_KEY)
    return hashlib.sha256(vigenere_result.encode()).digest()

def rc4_decrypt(data_bytes, key):
    S = list(range(256))
    j = 0
    key_bytes = key.encode()

    # KSA
    for i in range(256):
        j = (j + S[i] + key_bytes[i % len(key_bytes)]) % 256
        S[i], S[j] = S[j], S[i]

    # PRGA
    i = j = 0
    hasil = bytearray()

    for byte in data_bytes:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]

        K = S[(S[i] + S[j]) % 256]
        hasil.append(byte ^ K)

    return bytes(hasil)

def aes_cbc_decrypt(data, key):
    iv = data[:16]              # ambil IV dari depan
    ciphertext = data[16:]      # sisanya ciphertext

    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )

    decryptor = cipher.decryptor()
    padded_plain = decryptor.update(ciphertext) + decryptor.finalize()

    # unpadding PKCS7
    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded_plain) + unpadder.finalize()

    return plain

def decrypt_data(ciphertext_base64):
    if not ciphertext_base64:
        return ""
    encrypted_bytes = base64.b64decode(ciphertext_base64)
    aes_key = generate_aes_key_from_vigenere(MASTER_KEY)
    rc4_bytes = aes_cbc_decrypt(encrypted_bytes, aes_key)
    rc4_key = generate_derived_key_1(MASTER_KEY)
    plain_bytes = rc4_decrypt(rc4_bytes, rc4_key)

    return plain_bytes.decode('utf-8')

