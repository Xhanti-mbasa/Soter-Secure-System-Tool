//! Network and firewall configuration boundary.

#[derive(Debug, Clone, Default)]
pub struct NetworkPolicy {
    pub wifi_ssid: Option<String>,
    pub firewall_enabled: bool,
    pub default_deny: bool,
}

pub trait NetworkManager {
    fn apply(&self, policy: &NetworkPolicy) -> Result<(), String>;
    fn verify(&self, policy: &NetworkPolicy) -> Result<bool, String>;
}
