import SwiftUI

@main
struct NudgeApp: App {
    @StateObject private var daemon = DaemonController()

    var body: some Scene {
        MenuBarExtra {
            Button(daemon.isRunning ? "● Active" : "○ Inactive") {}
                .disabled(true)

            Divider()

            Button(daemon.isRunning ? "Pause Nudge" : "Resume Nudge") {
                if daemon.isRunning {
                    daemon.stopDaemon()
                } else {
                    daemon.startDaemon()
                }
            }

            Button("Restart") { daemon.restart() }
                .disabled(!daemon.isRunning)

            Divider()

            Button {
                daemon.toggleLaunchAtLogin()
            } label: {
                Text(daemon.launchAtLogin ? "✓ Launch at Login" : "  Launch at Login")
            }

            Divider()

            Button("Quit Nudge") {
                daemon.stopDaemon()
                NSApp.terminate(nil)
            }
        } label: {
            Image(systemName: daemon.isRunning ? "circle.fill" : "circle")
        }
        .menuBarExtraStyle(.menu)
    }
}
