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
    let display = env::var("DISPLAY").ok();
    let wayland_display = env::var("WAYLAND_DISPLAY").ok();
    let xdg_runtime_dir = env::var("XDG_RUNTIME_DIR").ok();
    provision_rootfs(&rootfs)?;

    // Resolve Soter's Nix browser wrappers without hard-coding store hashes.
    let nix_profile = rootfs.join("opt/soter/bin");
    fs::create_dir_all(&nix_profile).map_err(|e| e.to_string())?;
    for (package, binary) in [
        ("firefox-pentesting", "firefox"),
        ("chromium-pentesting", "chromium"),
    ] {
        let output = Command::new("nix")
            .args(["build", "--no-link", "--print-out-paths"])
            .arg(format!(".#{package}"))
            .output()
            .map_err(|e| format!("failed to resolve Nix package '{package}': {e}"))?;
        if !output.status.success() {
            return Err(format!(
                "failed to build Nix package '{package}': {}",
                String::from_utf8_lossy(&output.stderr).trim()
            ));
        }
        let store_path = String::from_utf8_lossy(&output.stdout)
            .lines().next()
            .ok_or_else(|| format!("Nix returned no store path for '{package}'"))?
            .trim().to_string();
        let link = nix_profile.join(binary);
        if link.exists() || link.is_symlink() {
            fs::remove_file(&link).map_err(|e| e.to_string())?;
        }
        #[cfg(unix)]
        std::os::unix::fs::symlink(
            format!("{store_path}/bin/{binary}"),
            &link,
        ).map_err(|e| e.to_string())?;
    }

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
    // Expose the Wayland socket by bind-mounting it before entering the
    // user namespace. Some kernels reject bind mounts sourced from the host's
    // per-user runtime directory after CLONE_NEWUSER has taken effect.
    let mut pre_unshare_mounts: Vec<(PathBuf, PathBuf)> = Vec::new();
    if let (Some(runtime), Some(wayland)) = (&xdg_runtime_dir, &wayland_display) {
        let host_socket = Path::new(runtime).join(wayland);
        if host_socket.exists() {
            let guest_runtime = rootfs.join(runtime.trim_start_matches('/'));
            fs::create_dir_all(&guest_runtime).map_err(|e| e.to_string())?;
            let guest_socket = guest_runtime.join(wayland);
            if !guest_socket.exists() {
                fs::File::create(&guest_socket).map_err(|e| e.to_string())?;
            }
            pre_unshare_mounts.push((host_socket, guest_socket));
        }
    }
    if Path::new("/tmp/.X11-unix").is_dir() {
        let guest_x11 = rootfs.join("tmp/.X11-unix");
        fs::create_dir_all(&guest_x11).map_err(|e| e.to_string())?;
        script.push_str(&format!(
            "mount --bind /tmp/.X11-unix {0}; mount -o remount,bind,ro {0}; ",
            shell_quote(&guest_x11.display().to_string())
        ));
    }

    script.push_str(&format!("hostname soter-{name}; "));
    script.push_str(&format!("cd {0}; exec chroot . /usr/bin/env -i HOME=/root USER=root LOGNAME=root PATH=/opt/soter/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin SHELL={1} SOTERSPACE={2} ",
        rootfs.display(), shell, name
    ));
    if let Some(value) = &display {
        script.push_str(&format!("DISPLAY={} ", shell_quote(value)));
    }
    if let Some(value) = &wayland_display {
        script.push_str(&format!("WAYLAND_DISPLAY={} ", shell_quote(value)));
    }
    if let Some(value) = &xdg_runtime_dir {
        script.push_str(&format!("XDG_RUNTIME_DIR={} ", shell_quote(value)));
    }

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

    for (source, target) in &pre_unshare_mounts {
        let status = Command::new("mount")
            .args(["--bind"])
            .arg(source)
            .arg(target)
            .status()
            .map_err(|e| format!("failed to expose GUI socket: {e}"))?;
        if !status.success() {
            return Err(format!("failed to expose GUI socket '{}'", source.display()));
        }
    }

    let status = Command::new("unshare")
        .args(["--user", "--map-root-user", "--mount", "--pid", "--fork", "--uts", "--ipc", "--net"])
        .arg("sh").arg("-c").arg(script)
        .status()
        .map_err(|e| format!("failed to start namespace runtime: {e}"));

    for (_, target) in &pre_unshare_mounts {
        let _ = Command::new("umount").arg(target).status();
    }

    let status = status?;
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
