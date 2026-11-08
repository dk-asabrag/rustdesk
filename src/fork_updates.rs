use hbb_common::{
    anyhow::{anyhow, Context},
    base64::{engine::general_purpose::STANDARD, Engine as _},
    ResultType,
};
use serde_derive::Deserialize;
use std::time::Duration;

pub(crate) const OWNER: &str = "dk-asabrag";
pub(crate) const KEY_ID: &str = "dk-asabrag-2026-ed25519-main";
pub(crate) const PACKAGE_ID: &str = "rustdesk.dk-asabrag";

pub(crate) fn configure_auto_update() {
    #[cfg(any(target_os = "windows", target_os = "macos"))]
    {
        use base::config::keys;
        use hbb_common::config::Config;
        const INITIALIZED: &str = "dk-asabrag-auto-update-initialized";
        if Config::get_option(INITIALIZED) != "Y" {
            Config::set_option(keys::OPTION_ALLOW_AUTO_UPDATE.to_owned(), "Y".to_owned());
            Config::set_option(INITIALIZED.to_owned(), "Y".to_owned());
        }
    }
}

pub(crate) fn public_key(encoded: &str) -> ResultType<[u8; 32]> {
    let bytes = STANDARD.decode(encoded).context("invalid fork update public key")?;
    if bytes.len() != 32 || STANDARD.encode(&bytes) != encoded || bytes.iter().all(|b| *b == 0) {
        return Err(anyhow!("fork update public key must be a valid 32-byte, canonically encoded key"));
    }
    let mut key = [0u8; 32];
    key.copy_from_slice(&bytes);
    Ok(key)
}

#[derive(Deserialize)]
struct Release {
    tag_name: String,
    html_url: String,
    draft: bool,
    prerelease: bool,
}

fn checked_release_url(bytes: &[u8]) -> ResultType<String> {
    let release: Release = serde_json::from_slice(bytes).context("invalid fork release response")?;
    if release.draft || release.prerelease {
        return Err(anyhow!("fork updates require a published stable release"));
    }
    let release_id = crate::common::release_id_from_update_url(&release.html_url)?;
    crate::common::display_version_from_release_id(&release_id)?;
    if release_id != release.tag_name {
        return Err(anyhow!("fork release tag and URL differ"));
    }
    Ok(release.html_url)
}

pub(crate) async fn latest_release_response() -> ResultType<bytes::Bytes> {
    let url = "https://api.github.com/repos/dk-asabrag/rustdesk/releases/latest";
    let client = crate::hbbs_http::create_http_client_async(hbb_common::tls::TlsType::Rustls, false);
    let response = client.get(url)
        .header(reqwest::header::USER_AGENT, "RustDesk-dk-asabrag")
        .header(reqwest::header::ACCEPT, "application/vnd.github+json")
        .timeout(Duration::from_secs(30))
        .send().await?.error_for_status()?;
    if response.content_length().is_some_and(|length| length > 1024 * 1024) {
        return Err(anyhow!("fork release response is too large"));
    }
    let bytes = response.bytes().await?;
    if bytes.len() > 1024 * 1024 {
        return Err(anyhow!("fork release response is too large"));
    }
    let url = checked_release_url(&bytes)?;
    Ok(serde_json::to_vec(&serde_json::json!({"url": url}))?.into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_published_fork_releases_are_discovered() {
        let mut release = serde_json::json!({
            "tag_name": "1.5.2",
            "html_url": "https://github.com/dk-asabrag/rustdesk/releases/tag/1.5.2",
            "draft": false, "prerelease": false
        });
        assert_eq!(checked_release_url(&serde_json::to_vec(&release).unwrap()).unwrap(), release["html_url"].as_str().unwrap());
        for (field, value) in [
            ("html_url", serde_json::json!("https://github.com/rustdesk/rustdesk/releases/tag/1.5.2")),
            ("tag_name", serde_json::json!("1.5.3")),
            ("draft", serde_json::json!(true)),
            ("prerelease", serde_json::json!(true)),
        ] {
            let mut invalid = release.clone();
            invalid[field] = value;
            assert!(checked_release_url(&serde_json::to_vec(&invalid).unwrap()).is_err());
        }
        release["html_url"] = serde_json::json!("https://github.com/dk-asabrag/rustdesk/releases/tag/nightly");
        release["tag_name"] = serde_json::json!("nightly");
        assert!(checked_release_url(&serde_json::to_vec(&release).unwrap()).is_err());
    }

    #[test]
    fn missing_or_invalid_update_keys_fail_closed() {
        for key in ["", "not-base64", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="] {
            assert!(public_key(key).is_err());
        }
        let encoded = STANDARD.encode([7u8; 32]);
        assert_eq!(public_key(&encoded).unwrap(), [7u8; 32]);
    }
}
