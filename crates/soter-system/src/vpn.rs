//! VPN and network-isolation boundary.

#[derive(Debug, Clone)]
pub struct VpnPolicy {
    pub profile: String,
    pub fail_closed: bool,
}

impl VpnPolicy {
    pub fn strict(profile: impl Into<String>) -> Self {
        Self { profile: profile.into(), fail_closed: true }
    }
}

pub trait VpnManager {
    fn connect(&self, policy: &VpnPolicy) -> Result<(), String>;
    fn disconnect(&self) -> Result<(), String>;
    fn healthy(&self) -> Result<bool, String>;
}
