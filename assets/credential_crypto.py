import base64
import hashlib
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PREFIX = "aes256gcm:v2:"
CONTEXT = b"lifecycle:asset-credentials:v2"


def asset_key(secret):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=CONTEXT).derive(secret.encode())


def encrypt_payload(plaintext, secret):
    nonce = os.urandom(12)
    ciphertext = AESGCM(asset_key(secret)).encrypt(nonce, plaintext, CONTEXT)
    return PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_payload(encrypted, secret):
    if encrypted.startswith(PREFIX):
        payload = base64.b64decode(encrypted[len(PREFIX):], altchars=b"-_", validate=True)
        if len(payload) < 28:
            raise ValueError("Invalid asset credential payload")
        return AESGCM(asset_key(secret)).decrypt(payload[:12], payload[12:], CONTEXT)
    material = ("lifecycle:asset-credentials:v1:" + secret).encode()
    legacy_key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(legacy_key).decrypt(encrypted.encode())