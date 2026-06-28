import Testing
import Foundation
@testable import mmdview

@Suite
@MainActor
struct ViewerStoreIntegrationTests {
    private func makeTempDir() throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("mmdview-store-it-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    @Test(.timeLimit(.minutes(1)))
    func deletingWatchedFileMarksDeleted() async throws {
        let tempDir = try makeTempDir()
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let file = tempDir.appendingPathComponent("test.mmd")
        try "graph TD; A-->B".write(to: file, atomically: true, encoding: .utf8)

        let store = ViewerStore()
        store.openFile(file)
        #expect(!store.isDeleted)

        try await Task.sleep(for: .seconds(0.3))

        try FileManager.default.removeItem(at: file)

        try await Task.sleep(for: .seconds(3))
        #expect(store.isDeleted)

        store.close()
    }

    @Test(.timeLimit(.minutes(1)))
    func closeStopsWatching() async throws {
        let tempDir = try makeTempDir()
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let file = tempDir.appendingPathComponent("test.mmd")
        try "graph TD; A-->B".write(to: file, atomically: true, encoding: .utf8)

        let store = ViewerStore()
        store.openFile(file)
        #expect(store.content == "graph TD; A-->B")

        store.close()
        #expect(store.filePath == file)

        try "graph TD; X-->Y".write(to: file, atomically: true, encoding: .utf8)

        try await Task.sleep(for: .seconds(1))
        #expect(store.content == "graph TD; A-->B")
    }
}
