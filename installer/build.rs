use std::{env, fs, path::PathBuf};
fn main() {
    println!("cargo:rerun-if-env-changed=ALICE_PAYLOAD");
    let out = PathBuf::from(env::var_os("OUT_DIR").unwrap()).join("payload.akp");
    if let Some(path) = env::var_os("ALICE_PAYLOAD") {
        let path = PathBuf::from(path).canonicalize().expect("payload path");
        println!("cargo:rerun-if-changed={}", path.display());
        fs::copy(path, out).expect("copy embedded payload");
    } else {
        fs::write(out, []).unwrap();
    }
}
