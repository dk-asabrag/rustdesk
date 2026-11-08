#!/usr/bin/env python3
"""Sign exact-source fork release assets after the build; never replace published metadata."""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from check_fork_update_key import main as check_key

REPO = "dk-asabrag/rustdesk"
KEY_ID = "dk-asabrag-2026-ed25519-main"
PACKAGE_ID = "rustdesk.dk-asabrag"


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def main():
    if os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise SystemExit("unexpected repository")
    tag, version, sha = (os.environ[name] for name in ("TAG_NAME", "VERSION", "GITHUB_SHA"))
    if not re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+", tag) or tag.removeprefix("v") != version:
        raise SystemExit("fork automatic updates require a stable tag matching the client version")
    check_key()
    release = api(f"repos/{REPO}/releases/tags/{tag}")
    if release["tag_name"] != tag or not release["draft"] or release["target_commitish"] != sha:
        raise SystemExit("expected an unpublished draft at the exact built commit")
    assets = release["assets"]
    if any(a["name"] in ("rustdesk-update.json", "rustdesk-update.json.sig") for a in assets):
        raise SystemExit("update metadata already staged; use a new release tag instead of replacing it")
    run = api(f"repos/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    if run["head_sha"] != sha:
        raise SystemExit("workflow source changed")
    created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    specs = [
        ("windows", "x86_64", "exe", f"rustdesk-{version}-x86_64.exe"),
        ("windows", "x86_64", "msi", f"rustdesk-{version}-x86_64.msi"),
        ("windows", "aarch64", "exe", f"rustdesk-{version}-aarch64.exe"),
        ("windows", "aarch64", "msi", f"rustdesk-{version}-aarch64.msi"),
        ("windows", "x86", "exe", f"rustdesk-{version}-x86-sciter.exe"),
    ]
    for arch in ("aarch64", "x86_64"):
        name = f"rustdesk-{version}-{arch}.dmg"
        if any(a["name"] == name for a in assets):
            specs.append(("macos", arch, "dmg", name))
    directory = Path("fork-update-artifacts")
    directory.mkdir(exist_ok=True)
    sign_args, verify_args = [], []
    for platform, arch, kind, name in specs:
        matches = [a for a in assets if a["name"] == name]
        if len(matches) != 1:
            raise SystemExit(f"required update asset missing: {name}")
        asset = matches[0]
        digest = asset.get("digest", "")
        if asset["state"] != "uploaded" or asset["size"] <= 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise SystemExit(f"unverified release asset: {name}")
        if datetime.fromisoformat(asset["created_at"].replace("Z", "+00:00")) < created:
            raise SystemExit(f"refusing an old release asset: {name}")
        path = directory / name
        with path.open("wb") as output:
            subprocess.run(["gh", "api", f"repos/{REPO}/releases/assets/{asset['id']}",
                            "--header", "Accept: application/octet-stream"], stdout=output, check=True)
        with path.open("rb") as downloaded:
            actual_digest = hashlib.file_digest(downloaded, "sha256").hexdigest()
        if path.stat().st_size != asset["size"] or actual_digest != digest[7:]:
            raise SystemExit(f"downloaded asset differs: {name}")
        sign_args.extend(["--artifact", platform, arch, kind, str(path)])
        verify_args.extend(["--artifact", str(path)])
    script = str(Path(__file__).with_name("generate_update_metadata.py"))
    identity = ["--key-id", KEY_ID, "--version", version, "--release-id", tag,
                "--package-id", PACKAGE_ID, "--release-base-url", f"https://github.com/{REPO}/releases/download"]
    metadata, signature = "rustdesk-update.json", "rustdesk-update.json.sig"
    subprocess.run([sys.executable, script, "sign", *identity, *sign_args,
                    "--published-at", run["created_at"], "--metadata-out", metadata,
                    "--signature-out", signature], check=True)
    subprocess.run([sys.executable, script, "verify", *identity, *verify_args,
                    "--metadata", metadata, "--signature", signature], check=True)
    # Publish the manifest last. Clients cannot act on an incomplete signature upload.
    for file in (signature, metadata):
        subprocess.run(["gh", "release", "upload", tag, file, "--repo", REPO], check=True)
    print(f"Verified signed update metadata staged for {len(specs)} artifacts.")


if __name__ == "__main__":
    main()
