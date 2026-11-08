#!/usr/bin/env python3
"""Run interactively with the owner's GitHub CLI credentials, never in a PR workflow."""
import argparse
import base64
import json
import subprocess

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO = "dk-asabrag/rustdesk"
SECRET = "RUSTDESK_UPDATE_ED25519_SEED"
VARIABLE = "RUSTDESK_UPDATE_ED25519_PUBLIC_KEY"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", required=True,
                        help="Create the signing secret and public variable in dk-asabrag/rustdesk")
    parser.parse_args()
    for kind, name in [("secret", SECRET), ("variable", VARIABLE)]:
        result = subprocess.run(
            ["gh", kind, "list", "--repo", REPO, "--json", "name"],
            check=True, capture_output=True, text=True,
        )
        if any(item["name"] == name for item in json.loads(result.stdout)):
            raise SystemExit(f"{name} already exists; refusing automatic key rotation")
    private = ed25519.Ed25519PrivateKey.generate()
    seed = base64.b64encode(private.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )).decode("ascii")
    public = base64.b64encode(private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )).decode("ascii")
    print("Public update key:", public, flush=True)
    subprocess.run(["gh", "secret", "set", SECRET, "--repo", REPO],
                   input=seed + "\n", text=True, check=True)
    subprocess.run(["gh", "variable", "set", VARIABLE, "--repo", REPO],
                   input=public + "\n", text=True, check=True)
    print("Signing configuration saved to GitHub. No private key was printed or written to disk.")


if __name__ == "__main__":
    main()
