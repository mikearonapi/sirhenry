use std::fs;
use std::path::PathBuf;
use std::time::Duration;
use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;

/// Get the ~/.sirhenry/data/ directory path.
fn data_dir() -> PathBuf {
    let home = dirs::home_dir().expect("Could not determine home directory");
    home.join(".sirhenry").join("data")
}

/// Get the port file path.
fn port_file_path() -> PathBuf {
    data_dir().join(".api-port")
}

/// Delete stale port file from a previous run.
fn cleanup_port_file() {
    let path = port_file_path();
    if path.exists() {
        let _ = fs::remove_file(&path);
    }
}

/// Read port from the port file.
fn read_port() -> Option<u16> {
    let path = port_file_path();
    if !path.exists() {
        return None;
    }
    fs::read_to_string(&path)
        .ok()
        .and_then(|s| s.trim().parse().ok())
}

/// Check if the API is healthy at the given port.
async fn health_check(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{}/health", port);
    match reqwest::get(&url).await {
        Ok(resp) => resp.status().is_success(),
        Err(_) => false,
    }
}

/// Start the sidecar and wait until it's ready. Returns the port.
pub async fn start_and_wait(app: &AppHandle) -> Result<u16, String> {
    cleanup_port_file();

    // Spawn the sidecar process
    let shell = app.shell();
    let sidecar = shell
        .sidecar("sirhenry-api")
        .map_err(|e| format!("Failed to create sidecar command: {}", e))?;

    let (_rx, _child) = sidecar
        .spawn()
        .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

    // Wait for port file to appear (max 30 seconds)
    let mut port: Option<u16> = None;
    for _ in 0..150 {
        if let Some(p) = read_port() {
            port = Some(p);
            break;
        }
        tokio::time::sleep(Duration::from_millis(200)).await;
    }

    let port = port.ok_or_else(|| {
        "Sidecar did not write port file within 30 seconds".to_string()
    })?;

    // Wait for health check to pass (max 60 seconds for DB init + migrations)
    for _ in 0..120 {
        if health_check(port).await {
            return Ok(port);
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }

    Err(format!(
        "API sidecar on port {} did not pass health check within 60 seconds",
        port
    ))
}
