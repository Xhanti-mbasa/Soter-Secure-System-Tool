//! Persistent Soterspace state and lifecycle operations.

use std::{env, fs, io, path::{Path, PathBuf}, process::Command};

#[derive(Debug, Clone)]
pub struct Soterspace {
    pub name: String,
    pub path: PathBuf,
}

fn root() -> io::Result<PathBuf> {
    let base = env::var_os("XDG_STATE_HOME").map(PathBuf::from)
        .or_else(|| env::var_os("HOME").map(|h| PathBuf::from(h).join(".local/state")))
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "HOME is not set"))?;
    Ok(base.join("soter/spaces"))
}

fn valid_name(name: &str) -> bool {
    !name.is_empty() && name.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_'))
}

pub fn create(name: &str, empty: bool, temporary: bool) -> Result<Soterspace, String> {
    if !valid_name(name) { return Err("soterspace names may contain only letters, numbers, '-' and '_'".into()); }
    let path = root().map_err(|e| e.to_string())?.join(name);
    if path.exists() { return Err(format!("soterspace '{name}' already exists")); }
    for dir in ["root", "runtime"] {
        fs::create_dir_all(path.join(dir)).map_err(|e| e.to_string())?;
    }
    let metadata = format!("name={name}\nempty={empty}\ntemporary={temporary}\n");
    fs::write(path.join("space.conf"), metadata).map_err(|e| e.to_string())?;
    Ok(Soterspace { name: name.into(), path })
}

pub fn remove(name: &str) -> Result<(), String> {
    let path = root().map_err(|e| e.to_string())?.join(name);
    if !path.exists() { return Err(format!("soterspace '{name}' does not exist")); }
    fs::remove_dir_all(path).map_err(|e| e.to_string())
}

pub fn list() -> Result<Vec<String>, String> {
    let root = root().map_err(|e| e.to_string())?;
    if !root.exists() { return Ok(Vec::new()); }
    let mut names = fs::read_dir(root).map_err(|e| e.to_string())?
        .filter_map(Result::ok).filter(|e| e.path().is_dir())
        .filter_map(|e| e.file_name().into_string().ok()).collect::<Vec<_>>();
    names.sort();
    Ok(names)
}

pub fn exists(name: &str) -> Result<bool, String> {
    Ok(root().map_err(|e| e.to_string())?.join(name).is_dir())
}

pub fn set_value(name: &str, key: &str, value: &str) -> Result<(), String> {
    let dir = root().map_err(|e| e.to_string())?.join(name);
    if !dir.exists() { return Err(format!("soterspace '{name}' does not exist")); }
    fs::write(dir.join(key), value).map_err(|e| e.to_string())
}

pub fn remove_value(name: &str, key: &str) -> Result<(), String> {
    let path = root().map_err(|e| e.to_string())?.join(name).join(key);
    if path.exists() { fs::remove_file(path).map_err(|e| e.to_string())?; }
    Ok(())
}

fn provision_rootfs(rootfs: &Path) -> Result<(), String> {
    if rootfs.join("usr/bin/env").exists() { return Ok(()); }

    let status = Command::new("pacstrap")
        .args(["-c", "-G", "-M"])
        .arg(rootfs)
        .args(["base", "bash", "coreutils", "util-linux", "iproute2"])
        .status()
        .map_err(|e| format!("failed to start pacstrap: {e}; install arch-install-scripts to provision Soterspaces"))?;

    if status.success() {
        Ok(())
    } else {
        Err(format!("root filesystem provisioning failed with status {status}"))
    }
}

pub fn enter_or_run(name: &str, command: &[String]) -> Result<i32, String> {
    if !exists(name)? { return Err(format!("soterspace '{name}' does not exist")); }

    let space = root().map_err(|e| e.to_string())?.join(name);
    let rootfs = space.join("root");
    let shell = env::var("SHELL").unwrap_or_else(|_| "/bin/sh".into());
    provision_rootfs(&rootfs)?;

    let mut script = String::from("set -eu; mount --make-rprivate /; ");
    script.push_str(&format!(
        "mkdir -p {0}/proc {0}/tmp {0}/run {0}/dev {0}/nix/store; mount -t proc proc {0}/proc; ",
        rootfs.display()
    ));
    if Path::new("/nix/store").is_dir() {
        script.push_str(&format!(
            "mount --bind /nix/store {0}/nix/store; mount -o remount,bind,ro {0}/nix/store; ",
            rootfs.display()
        ));
    }
    script.push_str(&format!("hostname soter-{name}; "));
    script.push_str(&format!(
        "cd {0}; exec chroot . /usr/bin/env -i HOME=/root USER=root LOGNAME=root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin SHELL={1} SOTERSPACE={2} ",
        rootfs.display(), shell, name
    ));

    if command.is_empty() {
        let inside_shell = if rootfs.join(shell.trim_start_matches('/')).exists() {
            shell.clone()
        } else {
            "/bin/sh".into()
        };
        script.push_str(&format!("{inside_shell} -l"));
    } else {
        script.push_str(&command.iter().map(|a| shell_quote(a)).collect::<Vec<_>>().join(" "));
    }

    let status = Command::new("unshare")
        .args(["--user", "--map-root-user", "--mount", "--pid", "--fork", "--uts", "--ipc", "--net"])
        .arg("sh").arg("-c").arg(script)
        .status()
        .map_err(|e| format!("failed to start namespace runtime: {e}"))?;

    Ok(status.code().unwrap_or(1))
}

fn shell_quote(value: &str) -> String {
    let escaped = value.replace("'", "'\\''");
    format!("'{escaped}'")
}

pub fn backup(name: &str, destination: &Path) -> Result<(), String> {
    let source = root().map_err(|e| e.to_string())?.join(name);
    if !source.exists() { return Err(format!("soterspace '{name}' does not exist")); }
    let status = Command::new("tar").arg("-cf").arg(destination).arg("-C")
        .arg(source.parent().unwrap()).arg(name).status().map_err(|e| e.to_string())?;
    if status.success() { Ok(()) } else { Err("tar backup failed".into()) }
}

pub fn restore(archive: &Path) -> Result<(), String> {
    let root = root().map_err(|e| e.to_string())?;
    fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    let status = Command::new("tar").arg("-xf").arg(archive).arg("-C").arg(root)
        .status().map_err(|e| e.to_string())?;
    if status.success() { Ok(()) } else { Err("tar restore failed".into()) }
}
