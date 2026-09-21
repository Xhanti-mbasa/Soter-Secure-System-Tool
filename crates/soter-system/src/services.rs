//! Service configuration boundary.

#[derive(Debug, Clone)]
pub enum ServiceState { Enabled, Disabled, Running, Stopped }

#[derive(Debug, Clone)]
pub struct ServicePolicy {
    pub name: String,
    pub state: ServiceState,
}

pub trait ServiceManager {
    fn apply(&self, policy: &ServicePolicy) -> Result<(), String>;
    fn verify(&self, policy: &ServicePolicy) -> Result<bool, String>;
}
