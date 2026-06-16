#!/usr/bin/env python3
import base64
import sys

def encrypt_password(plain_password, secret_key_b64):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        print("ERROR: 'cryptography' library is not installed. Install it using: pip install cryptography")
        sys.exit(1)
        
    try:
        key_bytes = base64.urlsafe_b64decode(secret_key_b64)
    except Exception as e:
        print(f"ERROR: Invalid base64 Secret Key: {e}")
        sys.exit(1)
        
    if len(key_bytes) != 32:
        print(f"ERROR: Secret Key must decode to 32 bytes (256-bit). Current length is {len(key_bytes)} bytes.")
        sys.exit(1)
        
    # PKCS7 padding manually
    pad_len = 16 - (len(plain_password) % 16)
    padded_plain = plain_password + chr(pad_len) * pad_len
    
    try:
        cipher = Cipher(algorithms.AES(key_bytes), modes.ECB(), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_bytes = encryptor.update(padded_plain.encode('utf-8')) + encryptor.finalize()
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
    except Exception as e:
        print(f"ERROR during encryption: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("  NSE Extranet Password Encrypter Utility")
    print("=" * 60)
    
    plain_pwd = input("Enter your New PLAIN TEXT Password: ").strip()
    sec_key = input("Enter your NSE AES Secret Key (from config.json ScrectKey): ").strip()
    
    if not plain_pwd or not sec_key:
        print("ERROR: Password and Secret Key cannot be empty.")
        sys.exit(1)
        
    enc_pwd = encrypt_password(plain_pwd, sec_key)
    print("\n" + "-" * 60)
    print(f"Your ENCRYPTED Password (to enter in GUI or config.json):")
    print(enc_pwd)
    print("-" * 60 + "\n")
