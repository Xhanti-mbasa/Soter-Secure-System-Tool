//! On-demand security and penetration-testing tooling for Soterspaces.
//!
//! Soter deliberately does not ship a giant preinstalled pentest image.
//! Tools are installed only into the selected Soterspace, and package-cache
//! archives are removed afterwards to keep the workspace lean.

use std::{
    fs,
    io::{self, Write},
    os::unix::fs::PermissionsExt,
    path::Path,
    process::Command,
};

use crate::soterspace;

#[derive(Debug, Clone, Copy)]
struct ToolSpec {
    number: usize,
    name: &'static str,
    package: &'static str,
    command: &'static str,
    description: &'static str,
}

const TOOLS: &[ToolSpec] = &[
    ToolSpec { number: 1, name: "Nmap", package: "nmap", command: "nmap", description: "Network discovery and port scanning" },
    ToolSpec { number: 2, name: "FFUF", package: "ffuf", command: "ffuf", description: "Fast web content fuzzing" },
    ToolSpec { number: 3, name: "Gobuster", package: "gobuster", command: "gobuster", description: "Directory, DNS and virtual-host enumeration" },
    ToolSpec { number: 4, name: "Netcat", package: "openbsd-netcat", command: "nc", description: "TCP/UDP connectivity and debugging" },
    ToolSpec { number: 5, name: "curl", package: "curl", command: "curl", description: "HTTP/API requests and transfers" },
    ToolSpec { number: 6, name: "wget", package: "wget", command: "wget", description: "HTTP/HTTPS file retrieval" },
    ToolSpec { number: 7, name: "jq", package: "jq", command: "jq", description: "JSON inspection and transformation" },
    ToolSpec { number: 8, name: "ripgrep", package: "ripgrep", command: "rg", description: "Fast recursive text searching" },
    ToolSpec { number: 9, name: "DNS tools", package: "bind", command: "dig", description: "dig, host and nslookup" },
    ToolSpec { number: 10, name: "socat", package: "socat", command: "socat", description: "Bidirectional socket relay and testing" },
    ToolSpec { number: 11, name: "tcpdump", package: "tcpdump", command: "tcpdump", description: "Packet capture and traffic inspection" },
];

pub fn interactive_install() -> Result<(), String> {
    println!("Soter security tools");
    println!("Install only what this Soterspace needs. Multiple selections are supported.\n");
    for tool in TOOLS {
        println!("  {:>2}. {:<10} {}", tool.number, tool.name, tool.description);
    }

    print!("\nSelect tools (example: 1,2,3,8,10): ");
    io::stdout().flush().map_err(|e| e.to_string())?;
    let mut selection = String::new();
    io::stdin().read_line(&mut selection).map_err(|e| e.to_string())?;
    let selected = parse_selection(&selection)?;

    let spaces = soterspace::list()?;
    if spaces.is_empty() {
        return Err("no Soterspaces exist; create one first with 'soter -c <name>'".into());
    }

    println!("\nAvailable Soterspaces:");
    for (index, name) in spaces.iter().enumerate() {
        println!("  {}. {}", index + 1, name);
    }

    print!("\nInstall into which Soterspace? ");
    io::stdout().flush().map_err(|e| e.to_string())?;
    let mut workspace = String::new();
    io::stdin().read_line(&mut workspace).map_err(|e| e.to_string())?;
    let workspace = workspace.trim();

    let name = if let Ok(index) = workspace.parse::<usize>() {
        spaces
            .get(index.saturating_sub(1))
            .ok_or_else(|| format!("invalid Soterspace selection: {workspace}"))?
            .clone()
    } else if spaces.iter().any(|name| name == workspace) {
        workspace.to_string()
    } else {
        return Err(format!("unknown Soterspace '{workspace}'"));
    };

    install_selected(&name, &selected)
}

fn parse_selection(value: &str) -> Result<Vec<ToolSpec>, String> {
    let mut selected = Vec::new();

    for raw in value.split(|c: char| c == ',' || c.is_whitespace()) {
        let raw = raw.trim();
        if raw.is_empty() {
            continue;
        }

        let number = raw
            .parse::<usize>()
            .map_err(|_| format!("invalid tool selection '{raw}'"))?;
        let tool = TOOLS
            .iter()
            .find(|tool| tool.number == number)
            .copied()
            .ok_or_else(|| format!("unknown tool number {number}"))?;

        if !selected.iter().any(|existing: &ToolSpec| existing.number == number) {
            selected.push(tool);
        }
    }

    if selected.is_empty() {
        Err("no tools selected".into())
    } else {
        Ok(selected)
    }
}

fn install_selected(name: &str, selected: &[ToolSpec]) -> Result<(), String> {
    if soterspace::is_running(name)? {
        return Err(format!(
            "soterspace '{name}' is running; stop it before changing installed tools"
        ));
    }

    let rootfs = soterspace::rootfs_path(name)?;
    if !rootfs.join("usr/bin/env").exists() {
        return Err(format!(
            "soterspace '{name}' has not finished provisioning; enter it once before installing tools"
        ));
    }

    ensure_security_workspace(&rootfs)?;

    let packages = selected.iter().map(|tool| tool.package).collect::<Vec<_>>();
    println!(
        "\nInstalling {} into Soterspace '{}'...",
        selected.iter().map(|tool| tool.name).collect::<Vec<_>>().join(", "),
        name
    );

    with_host_resolver(&rootfs, || {
        let status = Command::new("arch-chroot")
            .arg(&rootfs)
            .arg("pacman")
            .args(["-S", "--needed", "--noconfirm"])
            .args(&packages)
            .status()
            .map_err(|e| format!("failed to start workspace package installation: {e}"))?;

        if status.success() {
            Ok(())
        } else {
            Err(format!("workspace package installation failed with status {status}"))
        }
    })?;

    clean_package_cache(&rootfs)?;
    let baseline_invalidated = soterspace::invalidate_core_hash(name)?;

    println!("\nInstalled:");
    for tool in selected {
        println!("  - {} ({})", tool.name, tool.command);
    }
    println!("Starter wordlist: /usr/share/wordlists/soter/common.txt");
    println!("Secure case directory: /root/soter/cases");
    if baseline_invalidated {
        println!("Integrity baseline cleared because this was an authorized system change.");
        println!("Run 'soter --hash {name}' after you finish installing tools.");
    }
    Ok(())
}

pub fn create_case(space: &str, case_name: &str) -> Result<(), String> {
    if case_name.is_empty()
        || !case_name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_'))
    {
        return Err("case names may contain only letters, numbers, '-' and '_'".into());
    }

    if soterspace::is_running(space)? {
        return Err(format!(
            "soterspace '{space}' is running; stop it before creating a case"
        ));
    }

    let rootfs = soterspace::rootfs_path(space)?;
    ensure_security_workspace(&rootfs)?;

    let case_root = rootfs.join("root/soter/cases").join(case_name);
    if case_root.exists() {
        return Err(format!("case '{case_name}' already exists in soterspace '{space}'"));
    }

    fs::create_dir_all(&case_root).map_err(|e| e.to_string())?;
    fs::set_permissions(&case_root, fs::Permissions::from_mode(0o700))
        .map_err(|e| e.to_string())?;

    for directory in ["recon", "scans", "findings", "evidence", "notes", "loot"] {
        let path = case_root.join(directory);
        fs::create_dir_all(&path).map_err(|e| e.to_string())?;
        fs::set_permissions(&path, fs::Permissions::from_mode(0o700))
            .map_err(|e| e.to_string())?;
    }

    fs::write(
        case_root.join("README.txt"),
        format!(
            "Soter case: {case_name}\n\nrecon/     discovery and enumeration notes\nscans/     scanner output\nfindings/  validated findings and writeups\nevidence/  screenshots and supporting artifacts\nnotes/     working notes\nloot/      authorized collected test data\n"
        ),
    )
    .map_err(|e| e.to_string())?;

    println!("Created case '{case_name}' in Soterspace '{space}'.");
    println!("Path inside Soter: /root/soter/cases/{case_name}");
    Ok(())
}

fn ensure_security_workspace(rootfs: &Path) -> Result<(), String> {
    let cases = rootfs.join("root/soter/cases");
    let shared_wordlists = rootfs.join("usr/share/wordlists/soter");
    let convenient_wordlists = rootfs.join("root/soter/wordlists");

    fs::create_dir_all(&cases).map_err(|e| e.to_string())?;
    fs::set_permissions(rootfs.join("root/soter"), fs::Permissions::from_mode(0o700))
        .map_err(|e| e.to_string())?;
    fs::set_permissions(&cases, fs::Permissions::from_mode(0o700))
        .map_err(|e| e.to_string())?;

    fs::create_dir_all(&shared_wordlists).map_err(|e| e.to_string())?;
    let starter = shared_wordlists.join("common.txt");
    if !starter.exists() {
        fs::write(
            &starter,
            concat!(
                "admin\napi\napp\nassets\nbackup\nconfig\ndashboard\ndev\n",
                "docs\nfiles\nimages\ninternal\nlogin\nold\nprivate\n",
                "robots.txt\nstatic\ntest\nupload\nuploads\n",
            ),
        )
        .map_err(|e| e.to_string())?;
    }

    if convenient_wordlists.exists() || convenient_wordlists.is_symlink() {
        if convenient_wordlists.is_symlink() {
            fs::remove_file(&convenient_wordlists).map_err(|e| e.to_string())?;
        }
    }
    if !convenient_wordlists.exists() {
        #[cfg(unix)]
        std::os::unix::fs::symlink("/usr/share/wordlists/soter", &convenient_wordlists)
            .map_err(|e| e.to_string())?;
    }

    Ok(())
}

fn with_host_resolver<F>(rootfs: &Path, operation: F) -> Result<(), String>
where
    F: FnOnce() -> Result<(), String>,
{
    let guest = rootfs.join("etc/resolv.conf");
    let original = fs::read(&guest).ok();
    let host = fs::read("/etc/resolv.conf")
        .map_err(|e| format!("failed to read host resolver configuration: {e}"))?;
    fs::write(&guest, host)
        .map_err(|e| format!("failed to provide host DNS to workspace installer: {e}"))?;

    let result = operation();

    match original {
        Some(bytes) => {
            let _ = fs::write(&guest, bytes);
        }
        None => {
            let _ = fs::remove_file(&guest);
        }
    }

    result
}

fn clean_package_cache(rootfs: &Path) -> Result<(), String> {
    let cache = rootfs.join("var/cache/pacman/pkg");
    if !cache.is_dir() {
        return Ok(());
    }

    for entry in fs::read_dir(cache).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if path.is_file() {
            fs::remove_file(path).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

#[derive(Debug, Clone)]
pub struct ToolEnvironment {
    pub packages: Vec<String>,
    pub ephemeral: bool,
}

pub trait ToolProvider {
    fn prepare(&self, env: &ToolEnvironment) -> Result<(), String>;
    fn run(&self, tool: &str, args: &[String]) -> Result<i32, String>;
}
