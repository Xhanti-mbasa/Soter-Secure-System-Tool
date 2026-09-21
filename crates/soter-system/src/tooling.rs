//! Disposable security and penetration-testing tooling boundary.

#[derive(Debug, Clone)]
pub struct ToolEnvironment {
    pub packages: Vec<String>,
    pub ephemeral: bool,
}

pub trait ToolProvider {
    fn prepare(&self, env: &ToolEnvironment) -> Result<(), String>;
    fn run(&self, tool: &str, args: &[String]) -> Result<i32, String>;
}
