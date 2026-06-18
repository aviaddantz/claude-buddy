import Foundation
import ServiceManagement

final class DaemonController: ObservableObject {
    @Published var isRunning = false
    @Published var launchAtLogin = false

    private let scriptDir: String
    private var pollTimer: Timer?

    init() {
        scriptDir = NSString("~/Development/nudge").expandingTildeInPath
        if #available(macOS 13.0, *) {
            launchAtLogin = SMAppService.mainApp.status == .enabled
        }
        checkStatusSync()
        if !isRunning { startDaemon() }
        startPolling()
    }

    deinit { pollTimer?.invalidate() }

    func startDaemon() {
        runBackground("rm -f /tmp/claude-buddy-disabled && bash '\(scriptDir)/start-daemon.sh'")
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { self.checkStatusSync() }
    }

    func stopDaemon() {
        runBackground("bash '\(scriptDir)/stop-daemon.sh'")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.checkStatusSync() }
    }

    func restart() {
        runBackground("rm -f /tmp/claude-buddy-disabled && bash '\(scriptDir)/start-daemon.sh'")
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { self.checkStatusSync() }
    }

    func toggleLaunchAtLogin() {
        guard #available(macOS 13.0, *) else { return }
        do {
            if launchAtLogin {
                try SMAppService.mainApp.unregister()
                launchAtLogin = false
            } else {
                try SMAppService.mainApp.register()
                launchAtLogin = true
            }
        } catch {
            print("Login item toggle error: \(error)")
        }
    }

    private func startPolling() {
        pollTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.checkStatusSync()
        }
    }

    private func checkStatusSync() {
        let output = shell("pgrep -f 'buddy.py daemon'")
        let running = !output.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        DispatchQueue.main.async { self.isRunning = running }
    }

    @discardableResult
    private func shell(_ cmd: String) -> String {
        let p = Process()
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = Pipe()
        p.launchPath = "/bin/bash"
        p.arguments = ["-c", cmd]
        try? p.run()
        p.waitUntilExit()
        return String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
    }

    private func runBackground(_ cmd: String) {
        DispatchQueue.global(qos: .background).async { [self] in _ = shell(cmd) }
    }
}
