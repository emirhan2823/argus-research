from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Dict, Optional

try:
    from cryptography.fernet import Fernet as _Fernet
except ModuleNotFoundError:  # pragma: no cover
    _Fernet = None


class _SimpleFernet:
    """Fallback encryption primitive when cryptography is unavailable."""

    @staticmethod
    def generate_key() -> bytes:
        return base64.urlsafe_b64encode(os.urandom(32))

    def __init__(self, key: bytes):
        self._key = base64.urlsafe_b64decode(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(16)
        stream = hashlib.sha256(self._key + nonce).digest()
        data = bytes(p ^ stream[i % len(stream)] for i, p in enumerate(plaintext))
        sig = hmac.new(self._key, nonce + data, hashlib.sha256).digest()
        token = nonce + sig + data
        return base64.urlsafe_b64encode(token)

    def decrypt(self, ciphertext: bytes) -> bytes:
        raw = base64.urlsafe_b64decode(ciphertext)
        nonce, sig, data = raw[:16], raw[16:48], raw[48:]
        expected = hmac.new(self._key, nonce + data, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("Invalid ciphertext signature")
        stream = hashlib.sha256(self._key + nonce).digest()
        return bytes(c ^ stream[i % len(stream)] for i, c in enumerate(data))


class SecureVault:
    def __init__(self, key_file: Path = None):
        self.key_file = key_file or Path.home() / ".argus" / "vault.key"
        self._fernet = None

    def _get_fernet(self):
        if self._fernet is None:
            if self.key_file.exists():
                key = self.key_file.read_bytes()
            else:
                key = _Fernet.generate_key() if _Fernet else _SimpleFernet.generate_key()
                self.key_file.parent.mkdir(parents=True, exist_ok=True)
                self.key_file.write_bytes(key)
                os.chmod(self.key_file, 0o600)

            if _Fernet:
                self._fernet = _Fernet(key)
            else:
                self._fernet = _SimpleFernet(key)

        return self._fernet

    @property
    def secrets_file(self) -> Path:
        return self.key_file.parent / "secrets.enc"

    def encrypt(self, plaintext: str) -> str:
        return self._get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        return self._get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    def _load_secrets(self) -> Dict[str, str]:
        if not self.secrets_file.exists():
            return {}
        try:
            return json.loads(self.secrets_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def store_api_key(self, name: str, key: str):
        secrets = self._load_secrets()
        secrets[name] = self.encrypt(key)
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        self.secrets_file.write_text(json.dumps(secrets, indent=2), encoding="utf-8")
        try:
            os.chmod(self.secrets_file, 0o600)
        except OSError:
            pass

    def get_api_key(self, name: str) -> Optional[str]:
        secrets = self._load_secrets()
        if name not in secrets:
            return None
        return self.decrypt(secrets[name])
