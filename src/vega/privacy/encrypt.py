"""Optional local encryption utilities for Vega.

Not for provable privacy — just a convenience wrapper around
``cryptography.fernet`` so users can encrypt/decrypt sensitive local
data at rest if they choose.

All functions accept ``bytes | str`` and return ``bytes``.
"""

from __future__ import annotations

import base64
import os
from typing import Optional, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def generate_key() -> bytes:
    """Generate a fresh Fernet key (32 URL-safe base64-encoded bytes).

    Returns:
        A Fernet-compatible key as bytes.
    """
    return Fernet.generate_key()


def derive_key(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """Derive a Fernet key from a password using PBKDF2.

    Args:
        password: The user-supplied passphrase.
        salt: Optional salt (16 bytes).  A random one is generated if omitted.

    Returns:
        A ``(key, salt)`` tuple.  The salt must be stored alongside the
        encrypted data to allow decryption later.
    """
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    return key, salt


def encrypt(data: Union[str, bytes], key: bytes) -> bytes:
    """Encrypt *data* with a Fernet *key*.

    Args:
        data: Plaintext (``str`` or ``bytes``).
        key: A 32-byte URL-safe base64 key (from ``generate_key`` or
            ``derive_key``).

    Returns:
        Fernet token (bytes) containing the ciphertext.
    """
    f = Fernet(key)
    if isinstance(data, str):
        data = data.encode("utf-8")
    return f.encrypt(data)


def decrypt(token: bytes, key: bytes) -> bytes:
    """Decrypt a Fernet *token* with *key*.

    Args:
        token: The ciphertext produced by ``encrypt``.
        key: The same key used for encryption.

    Returns:
        Decrypted plaintext as bytes.
    """
    f = Fernet(key)
    return f.decrypt(token)


def encrypt_file(src_path: str, dst_path: Optional[str] = None, key: Optional[bytes] = None) -> bytes:
    """Encrypt a file on disk.

    Args:
        src_path: Path to the plaintext file.
        dst_path: Destination path for the encrypted file.  If omitted,
            ``src_path + ".encrypted"`` is used.
        key: Fernet key.  If omitted, a random key is generated **and printed**
            to stdout — suitable only for ad-hoc use.

    Returns:
        The key used (bytes).  Caller is responsible for storing it safely.
    """
    if key is None:
        key = generate_key()
        print(f"[vega encrypt] Generated key (save this!): {key.decode()}")

    dst = dst_path or src_path + ".encrypted"

    with open(src_path, "rb") as f:
        plaintext = f.read()

    token = encrypt(plaintext, key)

    with open(dst, "wb") as f:
        f.write(token)

    return key


def decrypt_file(src_path: str, key: bytes, dst_path: Optional[str] = None) -> bytes:
    """Decrypt a file on disk.

    Args:
        src_path: Path to the encrypted file.
        key: The Fernet key used for encryption.
        dst_path: Destination for the decrypted output.  If omitted, the
            result is returned but not written to disk.

    Returns:
        Decrypted content as bytes.
    """
    with open(src_path, "rb") as f:
        token = f.read()

    plaintext = decrypt(token, key)

    if dst_path:
        with open(dst_path, "wb") as f:
            f.write(plaintext)

    return plaintext
