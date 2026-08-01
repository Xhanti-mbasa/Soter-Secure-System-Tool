use std::fs;
use std::process::Command;

fn detect_distro() -> String {
    if let Ok(content) = fs::read_to_string("/etc/os-release") {
        for line in content.lines() {
            if line.starts_with("ID=") {
                return line.replace("ID=", "").trim_matches('"').to_string();
            }
        }
    }
    "unknown".to_string()
}

fn detect_package_manager() -> String {
    let managers = vec!["apt-get", "pacman", "dnf", "yum"];
    
    for manager in managers {
        if Command::new("sh")
            .arg("-c")
            .arg(format!("command -v {}", manager))
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            return manager.to_string();
        }
    }
    "unknown".to_string()
}

fn main() {
    let distro = detect_distro();
    let pkg_manager = detect_package_manager();
    
    println!("DISTRO={}", distro);
    println!("PKG_MANAGER={}", pkg_manager);
}
