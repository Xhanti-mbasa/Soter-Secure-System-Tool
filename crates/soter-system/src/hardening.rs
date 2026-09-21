//! Kernel and host hardening boundary.

#[derive(Debug, Clone)]
pub struct SysctlSetting {
    pub key: String,
    pub value: String,
}

#[derive(Debug, Clone, Default)]
pub struct HardeningPolicy {
    pub sysctls: Vec<SysctlSetting>,
}

pub trait Hardener {
    fn apply(&self, policy: &HardeningPolicy) -> Result<(), String>;
    fn verify(&self, policy: &HardeningPolicy) -> Result<bool, String>;
}
