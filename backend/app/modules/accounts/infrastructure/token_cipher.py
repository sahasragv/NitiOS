"""Symmetric encryption for third-party tokens stored in the database."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    """Encrypt and decrypt tokens with a key derived from the application secret."""

    def __init__(self, secret: str) -> None:
        self._fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))

    def encrypt(self, token: str) -> str:
        """Return an authenticated ciphertext for ``token``."""
        return self._fernet.encrypt(token.encode()).decode()

    def decrypt(self, ciphertext: str) -> str | None:
        """Return the token, or ``None`` if it was encrypted with a different secret or tampered with."""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            return None
