//! System recovery, backup, and rollback boundary.

#[derive(Debug, Clone)]
pub struct Backup {
    pub source: String,
    pub destination: String,
    pub compressed: bool,
}

pub trait RecoveryManager {
    fn backup(&self, request: &Backup) -> Result<(), String>;
    fn restore(&self, backup: &str) -> Result<(), String>;
    fn rollback(&self) -> Result<(), String>;
}
