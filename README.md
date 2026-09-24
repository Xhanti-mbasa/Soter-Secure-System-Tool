# Soter

**Secure Linux System Configuration & Baseline Management**

Soter (Σωτήρ), Greek for **“savior”** or **“preserver,”** is a Linux security configuration tool designed to create, maintain, and verify secure workstation environments.

Soter inspects the host system, determines its current configuration, compares it against a defined security baseline, and applies supported configuration changes in a reproducible and auditable way.

The project is built around four core operations:

```text
inspect → plan → apply → verify
```

## What Soter Does

Soter is intended to manage security-focused Linux workstation configuration, including:

* System and distribution discovery
* Package and package-manager configuration
* Network and firewall configuration
* Kernel and system hardening
* Service configuration
* Security-focused browser environments
* VPN and network-isolation tooling
* Security and penetration-testing tooling
* Configuration verification
* System recovery and rollback

Different security profiles can eventually provide configurations for environments such as:

```text
minimal
developer
pentest
privacy
server
```

Soter can therefore be used to configure both **fresh Linux installations** and **existing systems** against a known security baseline.

## What Soter Is Not

Soter is **not an antivirus, EDR, SIEM, or active threat-detection platform**.

Its primary purpose is **system configuration and baseline enforcement**.

Rather than continuously searching for malicious activity, Soter aims to answer:

```text
What is the current state of this system?
        ↓
What should its configuration be?
        ↓
What needs to change?
        ↓
Apply those changes.
        ↓
Verify the resulting configuration.
```

Optional inspection and scanning functionality may be introduced where it supports this workflow.

## Nix

Soter currently experiments with **Nix** for reproducible package and environment configuration.

### Install Nix

On Arch-based systems:

```bash
yay -S nix
```

Enable the required Nix experimental features:

```bash
mkdir -p ~/.config/nix
nvim ~/.config/nix/nix.conf
```

Add:

```ini
experimental-features = nix-command flakes
```

### Test the Installation

Create a test flake:

```bash
mkdir -p ~/myflake
cd ~/myflake

nix flake init
nix run
```

Nix is currently an implementation component of Soter rather than a requirement for the entire architecture.

## Project Status

> 🚧 **Active Development**

Soter is currently in the early development and architecture phase.

The project structure, configuration format, modules, and CLI are expected to change significantly while the core system is developed.

Current development is focused on:

```text
System Discovery
      ↓
Security Profiles
      ↓
Configuration Planning
      ↓
Configuration Application
      ↓
Verification
```

Features documented in the project may represent planned functionality and should not necessarily be considered production-ready.

## Project Verification

**WeThinkCode_ verification code:** `WTC-3YALQEH6`

## License

See the `LICENSE` file for licensing information.

## Soterspace quick start (Arch or CachyOS)

Install Rust, `arch-install-scripts`, and `pacman` on an Arch-based host. Install the release binary on your PATH to launch it as `soter`. Workspace entry and app installation need root:

```bash
cargo build --release
sudo install -Dm755 target/release/soter /usr/local/bin/soter
sudo soter -c lab
sudo soter -l
sudo soter --apps curl,jq lab
sudo soter lab -- curl --version
sudo soter --network isolate lab -- ip route
sudo soter -r lab
```

Creation records the workspace without entering it. The first app installation or entry provisions a fresh Arch root with `pacstrap` and copies the host's pacman configuration and repository files into it. Subsequent `--apps` and `--tools` installs run pacman through `arch-chroot` in that workspace, so pacman's downloader can write to its package database and cache. They do not install host packages. If an earlier failed bootstrap left files without package database records, Soter preserves the incomplete root and asks you to create a fresh Soterspace. Reinstalling packages with `yay` changes only the host; it cannot repair the workspace database. `--tools` offers an interactive menu for selected security tools. `--flakes firefox lab` explicitly builds a Nix browser and adds a launcher; ordinary entry leaves existing launchers in place and does not invoke Nix. The Nix browser workflow requires Nix and must be run from this repository so its `flake.nix` is available.

Default networking shares the host network, including its DNS resolver. `--network isolate` creates an offline namespace with no veth or NAT; it does not provide a routed isolated Internet connection. This is a demonstration feature and has not been validated as a containment boundary for untrusted programs. The older routed-network DNS and veth cleanup issue describes a design that is no longer the default.

See [the spoken demo script](docs/demo-script.md) for a presentation under five minutes.
