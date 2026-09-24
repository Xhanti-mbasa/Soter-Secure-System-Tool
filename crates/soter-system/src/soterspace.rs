//! Persistent Soterspace state and lifecycle operations.

use std::{
    env, fs, io,
    os::unix::{fs::PermissionsExt, process::CommandExt},
    path::{Path, PathBuf},
    process::{Command, Stdio},
};

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
    fs::create_dir_all(path.parent().ok_or("invalid soterspace path")?).map_err(|e| e.to_string())?;
    fs::create_dir(&path).map_err(|e| e.to_string())?;
    let initialize = || -> io::Result<()> {
        fs::create_dir(path.join("root"))?;
        fs::create_dir(path.join("runtime"))?;
        let metadata = format!("name={name}\nempty={empty}\ntemporary={temporary}\n");
        fs::write(path.join("space.conf"), metadata)
    };
    if let Err(error) = initialize() {
        let _ = fs::remove_dir_all(&path);
        return Err(format!("failed to initialize soterspace '{name}': {error}"));
    }
    Ok(Soterspace { name: name.into(), path })
}

pub fn remove(name: &str) -> Result<(), String> {
    if !exists(name)? { return Err(format!("soterspace '{name}' does not exist")); }
    if is_running(name)? { return Err(format!("soterspace '{name}' is running; exit it before removing it")); }
    let path = root().map_err(|e| e.to_string())?.join(name);
    fs::remove_dir_all(path).map_err(|e| e.to_string())
}

pub fn list() -> Result<Vec<String>, String> {
    let root = root().map_err(|e| e.to_string())?;
    if !root.exists() { return Ok(Vec::new()); }
    let mut names = fs::read_dir(root).map_err(|e| e.to_string())?
        .filter_map(Result::ok).filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false) && e.path().join("space.conf").is_file())
        .filter_map(|e| e.file_name().into_string().ok()).collect::<Vec<_>>();
    names.sort();
    Ok(names)
}

pub fn exists(name: &str) -> Result<bool, String> {
    if !valid_name(name) { return Err("soterspace names may contain only letters, numbers, '-' and '_'".into()); }
    let path = root().map_err(|e| e.to_string())?.join(name);
    Ok(fs::symlink_metadata(&path).map(|m| m.file_type().is_dir()).unwrap_or(false)
        && path.join("space.conf").is_file())
}

pub fn rootfs_path(name: &str) -> Result<PathBuf, String> {
    if !exists(name)? {
        return Err(format!("soterspace '{name}' does not exist"));
    }
    Ok(root().map_err(|e| e.to_string())?.join(name).join("root"))
}

pub fn is_running(name: &str) -> Result<bool, String> {
    Ok(active_pid(name)?.is_some())
}

pub fn invalidate_core_hash(name: &str) -> Result<bool, String> {
    if !exists(name)? {
        return Err(format!("soterspace '{name}' does not exist"));
    }
    let baseline = root()
        .map_err(|e| e.to_string())?
        .join(name)
        .join("integrity/core.sha256");
    if baseline.exists() {
        fs::remove_file(baseline).map_err(|e| e.to_string())?;
        Ok(true)
    } else {
        Ok(false)
    }
}

pub fn set_value(name: &str, key: &str, value: &str) -> Result<(), String> {
    if !exists(name)? { return Err(format!("soterspace '{name}' does not exist")); }
    if !matches!(key, "password" | "openvpn.conf") { return Err("unsupported setting".into()); }
    let dir = root().map_err(|e| e.to_string())?.join(name);
    fs::write(dir.join(key), value).map_err(|e| e.to_string())
}

pub fn remove_value(name: &str, key: &str) -> Result<(), String> {
    if !exists(name)? { return Err(format!("soterspace '{name}' does not exist")); }
    if !matches!(key, "password" | "openvpn.conf") { return Err("unsupported setting".into()); }
    let path = root().map_err(|e| e.to_string())?.join(name).join(key);
    if path.exists() { fs::remove_file(path).map_err(|e| e.to_string())?; }
    Ok(())
}

fn validate_rootfs(rootfs: &Path) -> Result<(), String> {
    // A failed pacstrap can leave package files behind without installing their
    // database records. Installing over that root produces thousands of file
    // conflicts, so refuse to reuse it and preserve the files for inspection.
    let mut packages = vec!["filesystem"];
    for (file, package) in [
        ("usr/share/man/man3/OSSL_PARAM_get_uint64.3ssl.gz", "openssl"),
        ("usr/bin/pcre2-config", "pcre2"),
    ] {
        if rootfs.join(file).exists() {
            packages.push(package);
        }
    }
    let output = Command::new("pacman")
        .arg("--root").arg(rootfs).arg("-Q").args(&packages)
        .output()
        .map_err(|e| format!("failed to inspect the workspace package database: {e}"))?;
    if !output.status.success() || !rootfs.join("usr/bin/env").is_file() {
        return Err(format!(
            "workspace root '{}' has files but its package database is incomplete; keep it for recovery and create a new Soterspace instead",
            rootfs.display()
        ));
    }
    Ok(())
}

fn configure_guest_pacman(rootfs: &Path) -> Result<(), String> {
    let guest_conf = rootfs.join("etc/pacman.conf");
    if !guest_conf.is_file() {
        fs::copy("/etc/pacman.conf", &guest_conf)
            .map_err(|e| format!("failed to configure workspace pacman: {e}"))?;
    }
    let guest_dir = rootfs.join("etc/pacman.d");
    fs::create_dir_all(&guest_dir).map_err(|e| e.to_string())?;
    // CachyOS and other Arch derivatives may include repository mirror files
    // beyond the single mirrorlist that pacstrap copies by default.
    let status = Command::new("cp")
        .args(["-a", "-n", "/etc/pacman.d/."])
        .arg(&guest_dir)
        .status()
        .map_err(|e| format!("failed to copy workspace pacman configuration: {e}"))?;
    if !status.success() { return Err("failed to copy workspace pacman configuration".into()); }
    Ok(())
}

fn provision_rootfs(rootfs: &Path) -> Result<(), String> {
    if fs::read_dir(rootfs).map_err(|e| e.to_string())?.next().is_some() {
        validate_rootfs(rootfs)?;
        return configure_guest_pacman(rootfs);
    }

    let status = Command::new("pacstrap")
        .args(["-c", "-P"])
        .arg(rootfs)
        .args(["base", "bash", "coreutils", "util-linux", "iproute2"])
        .status()
        .map_err(|e| format!("failed to start pacstrap: {e}; install arch-install-scripts to provision Soterspaces"))?;

    if !status.success() {
        return Err(format!("root filesystem provisioning failed with status {status}; keep the partial root for inspection"));
    }
    validate_rootfs(rootfs)?;
    configure_guest_pacman(rootfs)
}

/// Install native Arch packages into a Soterspace without touching the host package set.
pub fn install_apps(name: &str, packages: &[String]) -> Result<(), String> {
    if packages.is_empty() { return Err("choose at least one app".into()); }
    if is_running(name)? { return Err(format!("soterspace '{name}' is running; exit it before installing apps")); }
    for package in packages {
        if package.is_empty() || !package.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.' | '+' | '@')) {
            return Err(format!("invalid Arch package name '{package}'"));
        }
    }
    let rootfs = rootfs_path(name)?;
    provision_rootfs(&rootfs)?;
    // Run pacman inside the guest. Host pacman drops downloads to the alpm
    // user, which cannot traverse a Soterspace stored under /root.
    // arch-chroot also supplies /dev and /proc for package hooks and GPG.
    let status = Command::new("arch-chroot")
        .arg(&rootfs).arg("pacman")
        .args(["-Syu", "--needed", "--noconfirm"])
        .args(packages)
        .status()
        .map_err(|e| format!("failed to install workspace apps with arch-chroot: {e}"))?;
    if !status.success() { return Err(format!("app installation failed with status {status}")); }
    let _ = invalidate_core_hash(name)?;
    println!("Installed {} into Soterspace '{name}'.", packages.join(", "));
    Ok(())
}

pub fn enter_or_run(name: &str, command: &[String], shell_override: Option<&str>, flakes: &[String], network_mode: Option<&str>) -> Result<i32, String> {
    if !exists(name)? { return Err(format!("soterspace '{name}' does not exist")); }
    if active_pid(name)?.is_some() {
        return Err(format!("soterspace '{name}' is already running"));
    }

    let space = root().map_err(|e| e.to_string())?.join(name);
    let rootfs = space.join("root");
    let shell = match shell_override {
        Some(value) if value.starts_with('/') => value.to_string(),
        Some(value) => format!("/bin/{value}"),
        None => env::var("SHELL").unwrap_or_else(|_| "/bin/sh".into()),
    };
    let display = env::var("DISPLAY").ok();
    let wayland_display = env::var("WAYLAND_DISPLAY").ok();
    let xdg_runtime_dir = env::var("XDG_RUNTIME_DIR").ok();
    // Minimal root filesystems do not usually ship Ghostty's terminfo.
    // Use a widely available terminal entry for clear, editors, and prompts.
    let term = env::var("TERM").ok().map(|value| {
        if value == "xterm-ghostty" { "xterm-256color".into() } else { value }
    });
    // When Soter is started through sudo, recover the desktop user's identity.
    // That UID/GID must be mapped into the user namespace so Wayland's socket
    // remains owned by, and accessible to, the same user inside the Soterspace.
    let desktop_uid = env::var("SUDO_UID").ok().and_then(|v| v.parse::<u32>().ok());
    let desktop_gid = env::var("SUDO_GID").ok().and_then(|v| v.parse::<u32>().ok());
    provision_rootfs(&rootfs)?;

    // "open" shares the host network. "isolate" is deliberately simpler:
    // create a fresh network namespace with loopback only and no veth/NAT,
    // which makes the Soterspace offline rather than routing it separately.
    let offline_network = match network_mode.unwrap_or("open") {
        "open" => false,
        "isolate" => true,
        other => return Err(format!("unknown network mode '{other}'")),
    };

    // Resolve Soter's Nix browser wrappers without hard-coding store hashes.
    let nix_profile = rootfs.join("opt/soter/bin");
    fs::create_dir_all(&nix_profile).map_err(|e| e.to_string())?;
    let requested_flakes: Vec<(&str, &str)> = {
        flakes.iter().map(|name| match name.as_str() {
            "firefox" | "firefox-pentesting" => Ok(("firefox-pentesting", "firefox")),
            "chromium" | "chromium-pentesting" => Ok(("chromium-pentesting", "chromium")),
            other => Err(format!("unknown Soter flake '{other}'")),
        }).collect::<Result<Vec<_>, _>>()?
    };

    // Existing launchers remain available on later entries. Browser builds
    // happen only when --flakes explicitly requests them.

    for (package, binary) in requested_flakes {
        let output = Command::new("nix")
            // Soter uses flakes itself, so do not depend on the host having
            // these Nix features enabled globally.
            .args([
                "--extra-experimental-features",
                "nix-command flakes",
                "build",
                "--no-link",
                "--print-out-paths",
            ])
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

    // Host-network mode uses the host's active resolver. Offline mode keeps
    // the Soterspace resolver private and has no route to the host or Internet.
    let guest_resolv = rootfs.join("etc/resolv.conf");
    if !offline_network {
        fs::create_dir_all(rootfs.join("etc")).map_err(|e| e.to_string())?;
        if guest_resolv.is_symlink() {
            fs::remove_file(&guest_resolv).map_err(|e| e.to_string())?;
        }
        if !guest_resolv.exists() {
            fs::File::create(&guest_resolv).map_err(|e| e.to_string())?;
        }
    }

    let mut script = String::from("set -eu; mount --make-rprivate /; ");
    script.push_str(&format!(
        "mkdir -p {0}/proc {0}/tmp {0}/run {0}/dev {0}/nix/store; mount -t proc proc {0}/proc; mount --rbind /dev {0}/dev; mount --make-rslave {0}/dev; mount -t tmpfs -o mode=1777 tmpfs {0}/tmp; ",
        rootfs.display()
    ));
    if !offline_network {
        script.push_str(&format!(
            "mount --bind /etc/resolv.conf {0}; mount -o remount,bind,ro {0}; ",
            shell_quote(&guest_resolv.display().to_string())
        ));
    }
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
        // /tmp is mounted as a fresh tmpfs above, which hides any directory
        // created in the persistent rootfs before the namespace starts.
        // Recreate the X11 bind target inside that tmpfs before mounting it.
        script.push_str(&format!(
            "mkdir -p {0}; mount --bind /tmp/.X11-unix {0}; mount -o remount,bind,ro {0}; ",
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
    if let Some(value) = &term {
        script.push_str(&format!("TERM={} ", shell_quote(value)));
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

    // Start each Soterspace in its own process group so lifecycle commands
    // can signal the whole workspace (shell + child processes) without
    // creating a new session. A new session would detach the shell from the
    // terminal and break interactive job control.
    let mut runtime = Command::new("unshare");
    runtime.process_group(0);
    runtime.arg("--user");
    if let (Some(uid), Some(gid)) = (desktop_uid, desktop_gid) {
        // Keep namespace UID/GID 0 mapped to the privileged caller so mount,
        // chroot, hostname, etc. still work, and additionally map the desktop
        // user 1:1 so GUI sockets retain an accessible owner.
        runtime
            .arg("--map-users=0,0,1")
            .arg(format!("--map-users={uid},{uid},1"))
            .arg("--map-groups=0,0,1")
            .arg(format!("--map-groups={gid},{gid},1"));
    } else {
        runtime.arg("--map-root-user");
    }

    runtime.args(["--mount", "--pid", "--fork", "--uts", "--ipc"]);
    if offline_network {
        runtime.arg("--net");
    }

    let runtime_script = if offline_network {
        format!("set -eu; ip link set lo up; {script}")
    } else {
        script
    };

    let mut child = runtime
        .arg("sh").arg("-c").arg(runtime_script)
        .spawn()
        .map_err(|e| format!("failed to start namespace runtime: {e}"))?;

    let pid_file = space.join("runtime/session.pid");
    if let Err(error) = fs::write(&pid_file, format!("{}\n", child.id())) {
        let _ = child.kill();
        let _ = child.wait();
        for (_, target) in &pre_unshare_mounts {
            let _ = Command::new("umount").arg(target).status();
        }
        return Err(format!("failed to record Soterspace runtime pid: {error}"));
    }
    if let Err(error) = fs::set_permissions(&pid_file, fs::Permissions::from_mode(0o600)) {
        let group = format!("-{}", child.id());
        let _ = Command::new("kill").args(["-TERM", "--", &group]).status();
        let _ = child.wait();
        let _ = fs::remove_file(&pid_file);
        for (_, target) in &pre_unshare_mounts {
            let _ = Command::new("umount").arg(target).status();
        }
        return Err(format!("failed to protect Soterspace runtime pid: {error}"));
    }

    let status = child.wait().map_err(|e| format!("failed waiting for Soterspace: {e}"))?;
    let _ = fs::remove_file(&pid_file);

    for (_, target) in &pre_unshare_mounts {
        let _ = Command::new("umount").arg(target).status();
    }

    Ok(status.code().unwrap_or(1))
}

fn runtime_pid_path(name: &str) -> Result<PathBuf, String> {
    Ok(root().map_err(|e| e.to_string())?.join(name).join("runtime/session.pid"))
}

fn active_pid(name: &str) -> Result<Option<u32>, String> {
    if !exists(name)? {
        return Err(format!("soterspace '{name}' does not exist"));
    }

    let path = runtime_pid_path(name)?;
    if !path.exists() {
        return Ok(None);
    }

    let value = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let pid = value
        .trim()
        .parse::<u32>()
        .map_err(|_| format!("invalid runtime pid for soterspace '{name}'"))?;
    let group = format!("-{pid}");

    let running = Command::new("kill")
        .args(["-0", "--", &group])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map_err(|e| format!("failed to check soterspace '{name}' runtime: {e}"))?
        .success();

    // A stale pid file must never be allowed to signal an unrelated process
    // group if the kernel later reuses the same PID.
    let owned_runtime = fs::read(format!("/proc/{pid}/cmdline"))
        .ok()
        .map(|bytes| String::from_utf8_lossy(&bytes).replace('\0', " "))
        .map(|cmdline| cmdline.contains("unshare") && cmdline.contains(&format!("soter-{name}")))
        .unwrap_or(false);

    if running && owned_runtime {
        Ok(Some(pid))
    } else {
        let _ = fs::remove_file(path);
        Ok(None)
    }
}

fn signal_space(name: &str, signal: &str, action: &str, completed: &str) -> Result<(), String> {
    let pid = active_pid(name)?
        .ok_or_else(|| format!("soterspace '{name}' is not running"))?;
    let group = format!("-{pid}");

    let status = Command::new("kill")
        .args([signal, "--", &group])
        .status()
        .map_err(|e| format!("failed to {action} soterspace '{name}': {e}"))?;

    if status.success() {
        println!("{completed} soterspace '{name}'.");
        Ok(())
    } else {
        Err(format!("failed to {action} soterspace '{name}'"))
    }
}

pub fn kill(name: &str) -> Result<(), String> {
    signal_space(name, "-TERM", "kill", "Killed")
}

pub fn pause(name: &str) -> Result<(), String> {
    signal_space(name, "-STOP", "pause", "Paused")
}

pub fn resume(name: &str) -> Result<(), String> {
    signal_space(name, "-CONT", "resume", "Resumed")
}

fn shell_quote(value: &str) -> String {
    let escaped = value.replace("'", "'\\''");
    format!("'{escaped}'")
}


fn selected_spaces(target: Option<&str>) -> Result<Vec<String>, String> {
    if let Some(name) = target {
        if !exists(name)? {
            return Err(format!("soterspace '{name}' does not exist"));
        }
        Ok(vec![name.to_string()])
    } else {
        let spaces = list()?;
        if spaces.is_empty() {
            Err("no soterspaces found".into())
        } else {
            Ok(spaces)
        }
    }
}

fn compute_core_hash(rootfs: &Path) -> Result<String, String> {
    let candidates = ["etc", "usr", "bin", "sbin", "lib", "lib64"];
    let existing = candidates
        .iter()
        .copied()
        .filter(|path| rootfs.join(path).exists())
        .collect::<Vec<_>>();

    if existing.is_empty() {
        return Err("no core filesystem paths were found to hash".into());
    }

    let mut tar = Command::new("tar");
    tar.current_dir(rootfs)
        .args([
            "--sort=name",
            "--mtime=@0",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "--exclude=usr/share/wordlists/soter",
            "-cf",
            "-",
        ]);
    for path in &existing {
        tar.arg(path);
    }

    let mut tar_child = tar
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to start core hash archive: {e}"))?;
    let tar_stdout = tar_child
        .stdout
        .take()
        .ok_or_else(|| "failed to capture core hash archive".to_string())?;

    let digest = Command::new("sha256sum")
        .stdin(Stdio::from(tar_stdout))
        .output()
        .map_err(|e| format!("failed to run sha256sum: {e}"))?;
    let tar_status = tar_child
        .wait()
        .map_err(|e| format!("failed waiting for core hash archive: {e}"))?;

    if !tar_status.success() {
        return Err(format!("core hash archive failed with status {tar_status}"));
    }
    if !digest.status.success() {
        return Err(format!(
            "sha256sum failed: {}",
            String::from_utf8_lossy(&digest.stderr).trim()
        ));
    }

    String::from_utf8_lossy(&digest.stdout)
        .split_whitespace()
        .next()
        .map(str::to_string)
        .ok_or_else(|| "sha256sum returned no digest".into())
}

pub fn hash_core(target: Option<&str>) -> Result<(), String> {
    let mut mismatches = 0usize;

    for name in selected_spaces(target)? {
        let space = root().map_err(|e| e.to_string())?.join(&name);
        let rootfs = space.join("root");
        let digest = compute_core_hash(&rootfs)?;
        let integrity_dir = space.join("integrity");
        fs::create_dir_all(&integrity_dir).map_err(|e| e.to_string())?;
        fs::set_permissions(&integrity_dir, fs::Permissions::from_mode(0o700))
            .map_err(|e| e.to_string())?;
        let baseline = integrity_dir.join("core.sha256");

        if baseline.exists() {
            let expected = fs::read_to_string(&baseline)
                .map_err(|e| e.to_string())?
                .trim()
                .to_string();
            if expected == digest {
                println!("[PASS] {name}: core hash matches {digest}");
            } else {
                println!("[FAIL] {name}: core hash changed");
                println!("       expected: {expected}");
                println!("       current:  {digest}");
                mismatches += 1;
            }
        } else {
            fs::write(&baseline, format!("{digest}\n")).map_err(|e| e.to_string())?;
            fs::set_permissions(&baseline, fs::Permissions::from_mode(0o600))
                .map_err(|e| e.to_string())?;
            println!("[BASELINE] {name}: stored core hash {digest}");
        }
    }

    if mismatches == 0 {
        Ok(())
    } else {
        Err(format!("{mismatches} Soterspace core integrity check(s) failed"))
    }
}

pub fn prepare_flake_sessions(name: &str, flake: &str) -> Result<(), String> {
    if !exists(name)? {
        return Err(format!("soterspace '{name}' does not exist"));
    }

    let flake = match flake {
        "firefox" | "firefox-pentesting" => "firefox",
        "chromium" | "chromium-pentesting" => "chromium",
        other => return Err(format!("unknown Soter flake '{other}'")),
    };

    let sessions_root = root()
        .map_err(|e| e.to_string())?
        .join(name)
        .join("root/var/lib/soter/flake-sessions");
    let dir = sessions_root.join(flake);
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    fs::set_permissions(&sessions_root, fs::Permissions::from_mode(0o700))
        .map_err(|e| e.to_string())?;
    fs::set_permissions(&dir, fs::Permissions::from_mode(0o700))
        .map_err(|e| e.to_string())?;
    fs::write(
        dir.join(".soter-managed"),
        "version=1\nfull_sessions=true\nextension_sessions=true\n",
    )
    .map_err(|e| e.to_string())?;

    println!("Prepared persistent {flake} session storage for '{name}'.");
    println!("Use {flake} -s:<ID> for a full session, {flake} -se:<ID> for extension-only state.");
    println!("Use {flake} -l to list sessions and {flake} -rs:<ID> to remove one.");
    Ok(())
}

pub fn scan(target: Option<&str>) -> Result<(), String> {
    let mut failures = 0usize;

    for name in selected_spaces(target)? {
        let space = root().map_err(|e| e.to_string())?.join(&name);
        let rootfs = space.join("root");
        println!("Soterspace: {name}");

        let integrity = space.join("integrity/core.sha256");
        if integrity.exists() {
            let expected = fs::read_to_string(&integrity)
                .map_err(|e| e.to_string())?
                .trim()
                .to_string();
            let current = compute_core_hash(&rootfs)?;
            if expected == current {
                println!("  [PASS] core filesystem matches the stored SHA-256 baseline");
            } else {
                println!("  [FAIL] core filesystem differs from the stored SHA-256 baseline");
                failures += 1;
            }
        } else {
            println!("  [WARN] no core hash baseline; run 'soter --hash {name}'");
        }

        let launcher_dir = rootfs.join("opt/soter/bin");
        if launcher_dir.is_dir() {
            for entry in fs::read_dir(&launcher_dir).map_err(|e| e.to_string())? {
                let entry = entry.map_err(|e| e.to_string())?;
                let path = entry.path();
                let launcher = entry.file_name().to_string_lossy().to_string();
                let metadata = fs::symlink_metadata(&path).map_err(|e| e.to_string())?;
                if !metadata.file_type().is_symlink() {
                    println!("  [FAIL] launcher '{launcher}' is not a managed symlink");
                    failures += 1;
                    continue;
                }
                let destination = fs::read_link(&path).map_err(|e| e.to_string())?;
                if destination.starts_with("/nix/store/") {
                    println!("  [PASS] launcher '{launcher}' points into /nix/store");
                } else {
                    println!(
                        "  [FAIL] launcher '{launcher}' points outside /nix/store: {}",
                        destination.display()
                    );
                    failures += 1;
                }
            }
        }

        for (flake, path) in [
            ("firefox", rootfs.join("root/.mozilla/firefox")),
            ("chromium", rootfs.join("root/.config/chromium")),
        ] {
            if path.exists() {
                println!(
                    "  [WARN] unmanaged persistent {flake} profile data exists at {}",
                    path.strip_prefix(&rootfs).unwrap_or(&path).display()
                );
            }
        }

        let sessions = rootfs.join("var/lib/soter/flake-sessions");
        if sessions.exists() {
            let mode = fs::metadata(&sessions)
                .map_err(|e| e.to_string())?
                .permissions()
                .mode()
                & 0o777;
            if mode & 0o077 == 0 {
                println!("  [PASS] saved flake session storage is not group/world accessible");
            } else {
                println!("  [FAIL] saved flake session storage permissions are {:03o}", mode);
                failures += 1;
            }
        }

        if space.join("network.conf").exists() {
            println!("  [WARN] legacy network.conf remains from the old routed isolation design");
        }
        if space.join("runtime/net-ready").exists() {
            println!("  [WARN] stale runtime/net-ready marker remains from the old network design");
        }

        println!("  [INFO] default network mode is host-open");
        println!("  [INFO] '--network isolate' creates an offline network namespace with no veth/NAT");
        println!("  [INFO] hashes verify stored filesystem state; they cannot prove historical network traffic did not occur");
    }

    if failures == 0 {
        Ok(())
    } else {
        Err(format!("{failures} security check(s) failed"))
    }
}

pub fn backup(name: &str, destination: &Path) -> Result<(), String> {
    if !exists(name)? { return Err(format!("soterspace '{name}' does not exist")); }
    if is_running(name)? { return Err(format!("soterspace '{name}' is running; exit it before backing up")); }
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


pub fn list_wifi() -> Result<(), String> {
    let output = Command::new("nmcli")
        .args(["-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"])
        .output()
        .map_err(|e| format!("failed to list Wi-Fi networks with nmcli: {e}"))?;
    if !output.status.success() {
        return Err(format!(
            "failed to list Wi-Fi networks: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    let text = String::from_utf8_lossy(&output.stdout);
    if text.trim().is_empty() {
        println!("No Wi-Fi networks found.");
    } else {
        println!("SSID:SIGNAL:SECURITY");
        print!("{text}");
    }
    Ok(())
}
