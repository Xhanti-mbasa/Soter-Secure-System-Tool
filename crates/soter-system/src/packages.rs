//! Package and package-manager configuration boundary.

#[derive(Debug, Clone)]
pub enum PackageAction { Install, Remove, Upgrade }

#[derive(Debug, Clone)]
pub struct PackageRequest {
    pub action: PackageAction,
    pub packages: Vec<String>,
}

pub trait PackageManager {
    fn name(&self) -> &str;
    fn plan(&self, request: &PackageRequest) -> Result<Vec<String>, String>;
}
