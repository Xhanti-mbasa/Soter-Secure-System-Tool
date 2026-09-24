# Soter demo: spoken script (about 4 minutes)

## Before presenting

On an Arch or CachyOS host, install Rust and `arch-install-scripts`, then build from this branch:

```bash
cargo build --workspace
sudo ./target/debug/soter --version
```

Soter's workspace operations use `pacstrap`, mounts and namespaces. Run every demo command with `sudo` so it consistently uses the same workspace state directory. Package downloads may take longer than the spoken portion: run the create and app installation commands before the audience arrives if network speed is uncertain, then use another workspace name to demonstrate creation and removal. Do not claim this is a security boundary for hostile code.

## Spoken demo

"Hi, I'm Xhanti. This is Soter, a command line workspace manager for Linux. A Soterspace is a named directory containing an independent Arch root filesystem. The goal is to keep engagement tools and files together without installing every app into my host system."

"First I create an empty workspace record. This is fast because it doesn't download packages or launch a shell."

```bash
sudo ./target/debug/soter -c demo
sudo ./target/debug/soter -l
```

"The next command adds two real apps to this workspace. Soter provisions the root filesystem on first use, then installs curl and jq into that filesystem. This step needs an Arch host with pacstrap and an internet connection."

```bash
sudo ./target/debug/soter --apps curl,jq demo
sudo ./target/debug/soter demo -- curl --version
sudo ./target/debug/soter demo -- jq --version
```

"I can also enter an interactive shell with `sudo ./target/debug/soter demo`. When I exit, the workspace remains on disk. Named browser launchers can be added separately with `--flakes firefox` if Nix is installed; normal entry never builds Nix packages."

"Networking is a deliberate per-invocation choice. By default the workspace uses the host's network. With `--network isolate` it gets an offline network namespace. Here I inspect its routes. Empty output means it has no default route."

```bash
sudo ./target/debug/soter --network isolate demo -- ip route
```

"The workspace can hold an investigation folder, and Soter can back it up or check a stored filesystem hash. Those checks describe stored state; they do not prove that an application is safe or anonymous."

```bash
sudo ./target/debug/soter --case presentation demo
sudo ./target/debug/soter --hash demo
```

"Finally, I can remove the entire workspace after I exit it. Soter refuses to delete one while a session is still running."

```bash
sudo ./target/debug/soter -r demo
sudo ./target/debug/soter -l
```

"That's the working loop: create a Soterspace, install the apps it needs, run commands inside it, optionally use offline networking, and remove it when finished."
