import SwiftUI
import AppKit

@main
struct NudgeApp: App {
    @StateObject private var daemon = DaemonController()

    private var menuBarImage: NSImage {
        if let img = NSImage(named: "MenuBarIcon") {
            img.isTemplate = true
            return img
        }
        // Fallback: draw a tiny Claude silhouette programmatically
        let img = NSImage(size: NSSize(width: 22, height: 22), flipped: false) { rect in
            NSColor.black.setFill()
            NSBezierPath(rect: NSMakeRect(4, 4, 14, 10)).fill()
            NSBezierPath(rect: NSMakeRect(2, 6, 2, 4)).fill()
            NSBezierPath(rect: NSMakeRect(18, 6, 2, 4)).fill()
            NSColor.clear.setFill()
            NSBezierPath(rect: NSMakeRect(6, 6, 2, 2)).fill()
            NSBezierPath(rect: NSMakeRect(14, 6, 2, 2)).fill()
            return true
        }
        img.isTemplate = true
        return img
    }

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
            Image(nsImage: menuBarImage)
        }
        .menuBarExtraStyle(.menu)
    }
}
