// Prevents a console window from appearing on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;

mod sidecar;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let app_handle = app.handle().clone();

            // Spawn sidecar management on a background thread
            tauri::async_runtime::spawn(async move {
                match sidecar::start_and_wait(&app_handle).await {
                    Ok(port) => {
                        let url = format!("http://127.0.0.1:{}", port);
                        eprintln!("[SirHENRY] API sidecar ready at {}", url);

                        // Inject API URL into the webview.
                        // This is a safe, controlled string injection — the URL is
                        // always http://127.0.0.1:{port} from our own sidecar.
                        if let Some(window) = app_handle.get_webview_window("main") {
                            let js = format!(
                                "window.__SIRHENRY_API_URL__ = '{}';",
                                url
                            );
                            let _ = window.eval(&js);
                        }
                    }
                    Err(e) => {
                        eprintln!("[SirHENRY] Failed to start API sidecar: {}", e);
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running SirHENRY");
}
