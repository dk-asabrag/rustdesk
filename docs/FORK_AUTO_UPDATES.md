# Automatic updates for dk-asabrag/rustdesk

The fork-updates Cargo feature is enabled by default. Disabling it preserves the original upstream update discovery and trust policy.

The custom client queries only the latest published stable release of dk-asabrag/rustdesk. It rejects official RustDesk/other repository URLs, prereleases, mismatching tags and unstable version identifiers. The existing Windows/macOS updater verifies an Ed25519 manifest, file size and SHA-256 before installation. Active remote sessions postpone installation. The existing schedule is 30 seconds after startup, then daily, with retry intervals after failures.

On the first launch of the new client, automatic updates are enabled once in the local configuration. Later user changes to this setting are respected. No server address, server key or hbb_common revision changes are required.

## One-time signing setup

Only the repository owner can configure Actions secrets. The connected GitHub tool cannot administer repository secrets. Never paste the private seed into a chat or commit it.

In a GitHub Codespace opened on the feature branch (all commands run in GitHub's cloud), sign in with GitHub CLI if needed, then run:

```sh
python -m pip install --only-binary=:all: --require-hashes -r res/update/update_metadata_requirements.txt
python res/update/configure_fork_signing.py --apply
```

The tool generates a fresh Ed25519 key in memory and writes:
- Actions secret RUSTDESK_UPDATE_ED25519_SEED (private seed).
- Actions variable RUSTDESK_UPDATE_ED25519_PUBLIC_KEY (public key compiled into clients).

It never prints the seed or saves it to disk. It refuses to overwrite an existing key. Do not rotate this key casually: clients already installed trust the key compiled into them.

## Builds and publication

Use a new numeric stable tag matching Cargo.toml, Cargo.lock, flutter/pubspec.yaml and the release workflow VERSION. The first client with this feature is personalized version 1.5.2, based on official RustDesk stable 1.5.1.

The tag workflow validates the key pair before building. It stages releases as drafts. After successful Windows builds and completion of the macOS jobs, a fork-specific signer downloads the exact-source Windows EXE/MSI files and available macOS DMGs, verifies GitHub's SHA-256 digests and freshness, signs rustdesk-update.json and uploads its signature before the manifest. Missing Windows packages stop signing; unavailable macOS architectures are omitted.

Review validations and packages before publishing a draft. Clients discover only published stable releases. Do not replace assets or signed manifests after publication; release a newer version. New clients refuse unsigned updates or updates signed with the official upstream key.

The existing 1.5.1 client does not know this fork update channel. Install 1.5.2 once to enable future automatic updates. Existing Windows installation/elevation requirements still apply. On macOS the service must be installed; the existing custom-client exclusions remain. Linux and mobile retain their existing package-manager/manual installation behavior; this change does not add a new automatic installer for them.

## Regression surface

- src/common.rs: selects fork discovery and release owner only with fork-updates.
- src/updater/artifact.rs: restricts signed metadata and download URLs to the selected owner.
- src/update_metadata.rs: uses the fork key and package identity for automatic updates; missing build-time public keys fail closed.
- src/core_main.rs and src/lib.rs: thin initialization/module hooks; existing installation and session safeguards are reused.
- src/fork_updates.rs: isolated discovery, key validation and one-time setting initialization.
- Signing/release workflows and scripts: stage signed exact-source metadata; the existing official signing path remains available.
- Version files: distinguish the new client from the already published 1.5.1.
