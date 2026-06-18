// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Nudge",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "Nudge",
            path: "Sources/Nudge"
        )
    ]
)
