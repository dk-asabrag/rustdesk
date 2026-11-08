#!/usr/bin/env python3
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from generate_update_metadata import decode_env, SEED_ENV, PUBLIC_KEY_ENV, fail


def main():
    seed = decode_env(SEED_ENV, 32)
    configured = decode_env(PUBLIC_KEY_ENV, 32)
    actual = ed25519.Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    if actual != configured:
        fail("fork update signing seed does not match the compiled public key")
    if actual == bytes([
        52, 214, 32, 65, 191, 134, 137, 75, 157, 74, 67, 221, 150, 161, 118, 215,
        218, 35, 236, 156, 127, 120, 133, 156, 197, 141, 37, 22, 47, 106, 181, 177,
    ]):
        fail("fork updates must use their own signing key")
    print("Fork signing key matches the public key used by the client build.")


if __name__ == "__main__":
    main()
