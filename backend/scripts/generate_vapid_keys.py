"""
Script to generate a fresh VAPID key pair for Web Push.

Usage:
    python scripts/generate_vapid_keys.py

Output:
    VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY values ready to paste into .env
"""

import base64

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from py_vapid import Vapid


def generate() -> None:
    v = Vapid()
    v.generate_keys()

    pub = (
        base64.urlsafe_b64encode(
            v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        )
        .rstrip(b"=")
        .decode()
    )
    priv = (
        base64.urlsafe_b64encode(
            v.private_key.private_bytes(
                Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
            )
        )
        .rstrip(b"=")
        .decode()
    )

    print("Add these to your .env file:\n")
    print(f"VAPID_PUBLIC_KEY={pub}")
    print(f"VAPID_PRIVATE_KEY={priv}")
    print("\nNEVER commit VAPID_PRIVATE_KEY to source control.")


if __name__ == "__main__":
    generate()
