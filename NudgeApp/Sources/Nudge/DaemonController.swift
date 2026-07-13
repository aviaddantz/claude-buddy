import Foundation
import ServiceManagement

final class DaemonController: ObservableObject {
    @Published var isRunning = false
    @Published var launchAtLogin = false
    @Published var autoApproveLow: Bool
    @Published var idleVisible: Bool

    private let scriptDir: String
    private var pollTimer: Timer?
    private let autoApproveFlagPath: String
    private let idleVisibleFlagPath: String

    init() {
        scriptDir = NSString("~/Development/nudge").expandingTildeInPath
        autoApproveFlagPath = NSString("~/.nudge-autoapprove-disabled").expandingTildeInPath
        autoApproveLow = !FileManager.default.fileExists(atPath: NSString("~/.nudge-autoapprove-disabled").expandingTildeInPath)
        idleVisibleFlagPath = NSString("~/.nudge-idle-visible").expandingTildeInPath
        idleVisible = FileManager.default.fileExists(atPath: NSString("~/.nudge-idle-visible").expandingTildeInPath)
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

    func testNudge() {
        let payload = #"{"tool_name":"Bash","tool_input":{"command":"curl https://example.com/nudge-test"},"cwd":"/tmp","transcript_path":"","permission_suggestions":[],"_test":true}"#
        runBackground("printf '%s' '\(payload)' | bash '\(scriptDir)/notify.sh' approval")
    }

    func toggleAutoApproveLow() {
        if autoApproveLow {
            FileManager.default.createFile(atPath: autoApproveFlagPath, contents: nil)
        } else {
            try? FileManager.default.removeItem(atPath: autoApproveFlagPath)
        }
        autoApproveLow.toggle()
    }

    func toggleIdleVisible() {
        if idleVisible {
            try? FileManager.default.removeItem(atPath: idleVisibleFlagPath)
            runBackground("bash '\(scriptDir)/notify.sh' idle_off")
        } else {
            FileManager.default.createFile(atPath: idleVisibleFlagPath, contents: nil)
            runBackground("bash '\(scriptDir)/notify.sh' idle_on")
        }
        idleVisible.toggle()
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
