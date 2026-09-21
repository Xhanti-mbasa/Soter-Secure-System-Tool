//! Host and distribution discovery.

use std::{fs, process::Command};

#[derive(Debug, Clone, Default)]
pub struct SystemInfo {
    pub distro: String,
    pub package_manager: Option<String>,
    pub kernel: Option<String>,
    pub init_system: Option<String>,
}

fn command_exists(name: &str) -> bool {
    Command::new("sh").args(["-c", &format!("command -v {name} >/dev/null 2>&1")])
        .status().map(|s| s.success()).unwrap_or(false)
}

pub fn inspect() -> SystemInfo {
    let distro = fs::read_to_string("/etc/os-release").ok()
        .and_then(|s| s.lines().find_map(|l| l.strip_prefix("ID=").map(|v| v.trim_matches('"').to_owned())))
        .unwrap_or_else(|| "unknown".into());
    let package_manager = ["pacman","apt-get","dnf","yum","zypper","apk"]
        .into_iter().find(|m| command_exists(m)).map(str::to_owned);
    let kernel = Command::new("uname").arg("-r").output().ok()
        .filter(|o| o.status.success()).map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned());
    let init_system = command_exists("systemctl").then(|| "systemd".to_owned());
    SystemInfo { distro, package_manager, kernel, init_system }
}
