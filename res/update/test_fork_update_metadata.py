import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

ROOT = Path(__file__).parent
KEY_ID = "dk-asabrag-2026-ed25519-main"


class ForkUpdateTests(unittest.TestCase):
    def test_custom_release_signs_verifies_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            artifact = directory / "rustdesk-1.5.2-x86_64.exe"
            artifact.write_bytes(b"fixture for signed fork update")
            private = ed25519.Ed25519PrivateKey.generate()
            seed = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
            public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            env = dict(os.environ,
                       RUSTDESK_UPDATE_ED25519_SEED=base64.b64encode(seed).decode(),
                       RUSTDESK_UPDATE_ED25519_PUBLIC_KEY=base64.b64encode(public).decode())
            identity = ["--key-id", KEY_ID, "--version", "1.5.2", "--release-id", "1.5.2",
                        "--package-id", "rustdesk.dk-asabrag", "--release-base-url",
                        "https://github.com/dk-asabrag/rustdesk/releases/download"]
            metadata, signature = directory / "update.json", directory / "update.sig"
            subprocess.run([sys.executable, str(ROOT / "generate_update_metadata.py"), "sign",
                            *identity, "--artifact", "windows", "x86_64", "exe", str(artifact),
                            "--published-at", "2026-11-08T00:00:00Z", "--metadata-out", str(metadata),
                            "--signature-out", str(signature)], env=env, check=True)
            verify = [sys.executable, str(ROOT / "generate_update_metadata.py"), "verify", *identity,
                      "--metadata", str(metadata), "--signature", str(signature), "--artifact", str(artifact)]
            subprocess.run(verify, env=env, check=True)
            data = json.loads(metadata.read_bytes())
            self.assertEqual(data["signature_key_id"], KEY_ID)
            self.assertTrue(data["artifacts"][0]["url"].startswith("https://github.com/dk-asabrag/rustdesk/releases/download/1.5.2/"))
            data["artifacts"][0]["url"] = data["artifacts"][0]["url"].replace("dk-asabrag", "rustdesk")
            metadata.write_text(json.dumps(data))
            self.assertNotEqual(subprocess.run(verify, env=env, capture_output=True).returncode, 0)

    def test_key_preflight_rejects_missing_and_mismatched_keys(self):
        command = [sys.executable, str(ROOT / "check_fork_update_key.py")]
        env = dict(os.environ)
        env.pop("RUSTDESK_UPDATE_ED25519_SEED", None)
        env.pop("RUSTDESK_UPDATE_ED25519_PUBLIC_KEY", None)
        self.assertNotEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)
        seed = b"z" * 32
        public = ed25519.Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        env.update(RUSTDESK_UPDATE_ED25519_SEED=base64.b64encode(seed).decode(),
                   RUSTDESK_UPDATE_ED25519_PUBLIC_KEY=base64.b64encode(public).decode())
        subprocess.run(command, env=env, check=True)
        env["RUSTDESK_UPDATE_ED25519_PUBLIC_KEY"] = base64.b64encode(b"x" * 32).decode()
        self.assertNotEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)
