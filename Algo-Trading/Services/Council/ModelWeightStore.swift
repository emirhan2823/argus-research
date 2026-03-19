import Foundation

public struct ModelWeightSnapshot: Codable, Sendable {
    public var updatedAt: Date
    public var statsByModel: [String: ModelPerformanceStats]
    public var cfg: PerformanceWeightConfig

    public init(
        updatedAt: Date = Date(),
        statsByModel: [String: ModelPerformanceStats],
        cfg: PerformanceWeightConfig
    ) {
        self.updatedAt = updatedAt
        self.statsByModel = statsByModel
        self.cfg = cfg
    }
}

/// Simple JSON persistence for runner.
/// Uses Application Support on macOS.
/// For iOS, you'll adapt baseDir to FileManager.default.urls(for:in:).first
public final class ModelWeightStore {
    private let fm = FileManager.default
    private let fileURL: URL

    public init(filename: String = "model_weights.json") {
        // macOS runner location (works for command line runner)
        let base = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = base.appendingPathComponent("ArgusRunner", isDirectory: true)
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        self.fileURL = dir.appendingPathComponent(filename)
    }

    public func load() -> ModelWeightSnapshot? {
        guard fm.fileExists(atPath: fileURL.path) else { return nil }
        do {
            let data = try Data(contentsOf: fileURL)
            return try JSONDecoder().decode(ModelWeightSnapshot.self, from: data)
        } catch {
            return nil
        }
    }

    public func save(_ snap: ModelWeightSnapshot) {
        do {
            let enc = JSONEncoder()
            enc.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try enc.encode(snap)
            try data.write(to: fileURL, options: [.atomic])
        } catch {
            // intentionally swallow for runner stability
        }
    }

    public func pathString() -> String { fileURL.path }
}
