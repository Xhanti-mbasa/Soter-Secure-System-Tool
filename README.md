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
