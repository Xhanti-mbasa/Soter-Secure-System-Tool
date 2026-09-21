//! Configuration verification primitives.

#[derive(Debug, Clone)]
pub struct CheckResult {
    pub control: String,
    pub passed: bool,
    pub detail: String,
}

pub trait Verifier {
    fn verify(&self) -> Result<Vec<CheckResult>, String>;
}
