// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "mmdview",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/SimplyDanny/SwiftLintPlugins", from: "0.58.0"),
        .package(url: "https://github.com/nicklockwood/SwiftFormat", from: "0.55.0"),
    ],
    targets: [
        .executableTarget(
            name: "mmdview",
            path: "mmdview",
            exclude: ["Info.plist", "mmdview.entitlements", "Resources/__tests__"],
            resources: [
                .copy("Resources/viewer.html"),
                .copy("Resources/viewer.js"),
                .copy("Resources/style.css"),
                .copy("Resources/mermaid.min.js"),
                .copy("Resources/markdown-it.min.js"),
            ],
            plugins: [
                .plugin(name: "SwiftLintBuildToolPlugin", package: "SwiftLintPlugins"),
            ]
        ),
        .testTarget(
            name: "mmdviewTests",
            dependencies: ["mmdview"],
            path: "mmdviewTests",
            plugins: [
                .plugin(name: "SwiftLintBuildToolPlugin", package: "SwiftLintPlugins"),
            ]
        ),
    ]
)
