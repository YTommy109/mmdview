import Foundation

/// ビューアの表示状態を管理する。
/// ファイルの読み込み・監視・削除検知を行い、UI にバインドされるプロパティを更新する。
@MainActor
@Observable
final class ViewerStore {
    typealias WatcherFactory = @MainActor @Sendable (URL, @escaping @MainActor @Sendable () -> Void) -> FileWatching

    private(set) var content: String = ""
    private(set) var fileType: FileType = .mmd
    private(set) var isDeleted: Bool = false
    private(set) var filePath: URL?

    private var fileWatcher: FileWatching?
    private let makeWatcher: WatcherFactory

    init(watcherFactory: WatcherFactory? = nil) {
        self.makeWatcher = watcherFactory ?? { url, onChange in FileWatcher(path: url, onChange: onChange) }
    }

    /// 指定 URL のファイルを開き、ファイル監視を開始する。
    /// 既に別のファイルを開いている場合は、先に監視を停止してから切り替える。
    func openFile(_ url: URL) {
        fileWatcher?.stop()
        filePath = url
        fileType = FileType(url: url)
        loadContent()

        fileWatcher = makeWatcher(url) { [weak self] in
            self?.loadContent()
        }
    }

    private func loadContent() {
        guard let filePath else { return }
        let resolved = filePath.resolvingSymlinksInPath()
        if FileManager.default.fileExists(atPath: resolved.path) {
            content = (try? String(contentsOf: resolved, encoding: .utf8)) ?? ""
            isDeleted = false
        } else {
            isDeleted = true
        }
    }

    /// ファイル監視を停止し、リソースを解放する。
    func close() {
        fileWatcher?.stop()
        fileWatcher = nil
    }
}
