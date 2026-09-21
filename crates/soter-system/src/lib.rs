//! Linux system integration for Soter.
//!
//! Each subsystem exposes a small boundary that can be implemented and tested
//! independently as Soter grows.

pub mod discovery;
pub mod packages;
pub mod network;
pub mod hardening;
pub mod services;
pub mod browser;
pub mod vpn;
pub mod tooling;
pub mod verification;
pub mod recovery;

pub mod soterspace;
