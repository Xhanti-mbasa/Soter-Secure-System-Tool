//! Security-focused browser environment boundary.

#[derive(Debug, Clone)]
pub struct BrowserEnvironment {
    pub package: String,
    pub ephemeral: bool,
    pub extra_args: Vec<String>,
}

pub trait BrowserLauncher {
    fn launch(&self, env: &BrowserEnvironment) -> Result<(), String>;
}
