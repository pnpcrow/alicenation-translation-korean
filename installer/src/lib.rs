pub mod engine;
pub mod package;
pub mod platform;

pub static EMBEDDED: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/payload.akp"));
