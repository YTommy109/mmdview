import AppKit
import UniformTypeIdentifiers

@main
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    static private(set) var shared: AppDelegate?
    private var windowControllers: [String: ViewerWindowController] = [:]

    nonisolated static func main() {
        MainActor.assumeIsolated {
            let app = NSApplication.shared
            app.setActivationPolicy(.regular)
            let delegate = AppDelegate()
            app.delegate = delegate
            AppDelegate.shared = delegate
            app.run()
        }
    }

    // MARK: - NSApplicationDelegate

    func applicationWillFinishLaunching(_ notification: Notification) {
        _ = DocumentController()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = MainMenuBuilder.build(openAction: #selector(showOpenPanel))
        NSApp.activate()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            showOpenPanel()
        }
        return true
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls {
            openViewer(for: url)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    // MARK: - Window Management

    /// 指定 URL のファイルをビューアウィンドウで開く。
    /// 同じファイルが既に開かれている場合は既存ウィンドウを前面に表示する。
    func openViewer(for url: URL) {
        let key = url.resolvingSymlinksInPath().path
        if let existing = windowControllers[key] {
            existing.window?.makeKeyAndOrderFront(nil)
            return
        }

        let controller = ViewerWindowController(fileURL: url)
        windowControllers[key] = controller
        controller.onClose = { [weak self] in
            self?.windowControllers.removeValue(forKey: key)
        }
        controller.showWindow(nil)
        NSDocumentController.shared.noteNewRecentDocumentURL(url)
    }

    /// ファイル選択パネルを表示し、選択されたファイルをビューアで開く。
    @objc func showOpenPanel() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = Self.supportedContentTypes
        panel.allowsMultipleSelection = true
        panel.begin { [weak self] response in
            guard response == .OK else { return }
            for url in panel.urls {
                self?.openViewer(for: url)
            }
        }
    }

    // MARK: - Supported Types

    private static let supportedContentTypes: [UTType] = {
        var types: [UTType] = []
        if let mmd = UTType(filenameExtension: "mmd") { types.append(mmd) }
        if let mermaid = UTType(filenameExtension: "mermaid") { types.append(mermaid) }
        if let md = UTType(filenameExtension: "md") { types.append(md) }
        return types
    }()

}
