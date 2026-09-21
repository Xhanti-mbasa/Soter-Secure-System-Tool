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
    for dir in ["root", "overlay/upper", "overlay/work", "runtime"] {
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

pub fn enter_or_run(name: &str, command: &[String]) -> Result<i32, String> {
    if !exists(name)? { return Err(format!("soterspace '{name}' does not exist")); }

    let space = root().map_err(|e| e.to_string())?.join(name);
    let merged = space.join("root");
    let upper = space.join("overlay/upper");
    let work = space.join("overlay/work");

    // A Soterspace gets its own user, mount, PID, UTS, IPC and network namespaces.
    // Its filesystem is a persistent overlay: the host root is the read-only lower
    // layer and every write lands in this Soterspace's private upper layer.
    let shell = env::var("SHELL").unwrap_or_else(|_| "/bin/sh".into());
    let uid = Command::new("id").arg("-u").output().map_err(|e| e.to_string())?;
    let gid = Command::new("id").arg("-g").output().map_err(|e| e.to_string())?;
    let uid = String::from_utf8_lossy(&uid.stdout).trim().to_owned();
    let gid = String::from_utf8_lossy(&gid.stdout).trim().to_owned();

    let mut script = String::from("set -eu; mount --make-rprivate /; ");
    script.push_str(&format!(
        "mount -t overlay overlay -o userxattr,lowerdir=/,upperdir={},workdir={} {}; ",
        upper.display(), work.display(), merged.display()
    ));
    script.push_str(&format!(
        "mount --bind {0} {0}; mount -o remount,bind,rw {0}; ",
        merged.display()
    ));
    script.push_str(&format!(
        "mkdir -p {0}/proc {0}/tmp {0}/run; mount -t proc proc {0}/proc; ",
        merged.display()
    ));
    script.push_str(&format!("hostname soter-{name}; "));
    script.push_str(&format!(
        "cd {0}; exec chroot --userspec={1}:{2} . /usr/bin/env -i HOME=/home/{3} USER={3} LOGNAME={3} PATH=/usr/local/sbin:/usr/local/bin:/usr/bin:/bin SHELL={4} SOTERSPACE={5} ",
        merged.display(), uid, gid,
        env::var("USER").unwrap_or_else(|_| "user".into()),
        shell, name
    ));

    if command.is_empty() {
        script.push_str(&format!("{shell} -l"));
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
