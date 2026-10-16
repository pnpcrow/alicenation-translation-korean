pub mod engine;
pub mod package;
pub mod platform;

pub const EMBEDDED: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/payload.akp"));
