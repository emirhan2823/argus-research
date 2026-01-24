import Foundation

/// Persists paper-mode portfolio + risk state so a restart doesn't reset everything.
/// Location: ~/Library/Application Support/ArgusRunner/state/paper/<SYMBOL>.json
enum PaperStateStore {

    struct PositionSnapshot: Codable {
        let side: String          // "LONG" | "SHORT"
        let qty: Double
        let entry: Double
        let entryTimeISO: String
    }

    struct RiskSnapshot: Codable {
        let dayKeyUTC: String
        let dayStartEquity: Double
        let realizedPnl: Double
        let tradesToday: Int
        let lastTradeTimeISO: String?
    }

    struct Snapshot: Codable {
        let schemaVersion: Int
        let symbol: String
        let updatedAtISO: String

        let cash: Double
        let position: PositionSnapshot?

        let risk: RiskSnapshot
    }

    static func load(symbol: String) -> Snapshot? {
        do {
            let url = try DataStore.paperStatePath(symbol: symbol)
            guard FileManager.default.fileExists(atPath: url.path) else { return nil }
            let data = try Data(contentsOf: url)
            return try JSONDecoder().decode(Snapshot.self, from: data)
        } catch {
            return nil
        }
    }

    static func save(_ snap: Snapshot, symbol: String) {
        do {
            let url = try DataStore.paperStatePath(symbol: symbol)
            let data = try JSONEncoder.prettySorted.encode(snap)
            try data.write(to: url, options: .atomic)
        } catch {
            // best-effort (paper mode should never crash on persistence)
        }
    }
}

private extension JSONEncoder {
    static var prettySorted: JSONEncoder {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        return enc
    }
}
