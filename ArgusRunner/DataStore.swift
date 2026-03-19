import Foundation

enum DataStore {

    // MARK: - Root Directory (Stable)
    static func rootDir() throws -> URL {
        let fm = FileManager.default

        let appSupport = fm.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first!

        let dir = appSupport
            .appendingPathComponent("ArgusRunner", isDirectory: true)

        try fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    // MARK: - Base Directory (Market Data)
    static func baseDir() throws -> URL {
        let fm = FileManager.default
        let dir = try rootDir()
            .appendingPathComponent("data", isDirectory: true)

        try fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    // MARK: - State Directory
    static func stateDir() throws -> URL {
        let fm = FileManager.default
        let dir = try rootDir()
            .appendingPathComponent("state", isDirectory: true)

        try fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static func paperStatePath(symbol: String) throws -> URL {
        let dir = try stateDir()
            .appendingPathComponent("paper", isDirectory: true)

        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("\(symbol.uppercased()).json")
    }

    // MARK: - Paths
    static func monthKey(fromCloseTimeMs ms: Int64) -> String {
        let sec = TimeInterval(ms) / 1000.0
        let d = Date(timeIntervalSince1970: sec)
        let cal = Calendar(identifier: .gregorian)
        let y = cal.component(.year, from: d)
        let m = cal.component(.month, from: d)
        return String(format: "%04d-%02d", y, m)
    }

    static func csvPath(symbol: String, tf: String, closeTimeMs: Int64) throws -> URL {
        let root = try baseDir()

        let symDir = root.appendingPathComponent(symbol.uppercased(), isDirectory: true)
        let tfDir  = symDir.appendingPathComponent(tf, isDirectory: true)

        try FileManager.default.createDirectory(at: tfDir, withIntermediateDirectories: true)

        let name = "\(monthKey(fromCloseTimeMs: closeTimeMs)).csv"
        return tfDir.appendingPathComponent(name)
    }

    // MARK: - CSV I/O
    static func ensureHeaderIfNeeded(fileURL: URL) throws {
        if !FileManager.default.fileExists(atPath: fileURL.path) {
            let header = "closeTimeMs,closeTimeISO,open,high,low,close,volume\n"
            try header.data(using: .utf8)!.write(to: fileURL, options: .atomic)
        }
    }

    /// Appends candles to CSV and returns how many NEW rows were written (dedup by closeTimeMs).
    @discardableResult
    static func appendRunnerCandlesCSV(
        symbol: String,
        tf: String,
        candles: [RunnerCandle]
    ) throws -> Int {

        guard let last = candles.last else { return 0 }

        let fileURL = try csvPath(
            symbol: symbol,
            tf: tf,
            closeTimeMs: last.closeTime
        )

        try ensureHeaderIfNeeded(fileURL: fileURL)

        let lastWritten = try readLastCloseTimeMs(fileURL: fileURL)

        var lines = ""
        lines.reserveCapacity(candles.count * 64)

        let iso = ISO8601DateFormatter()

        var written = 0

        for c in candles {
            if let lw = lastWritten, c.closeTime <= lw { continue }

            let isoStr = iso.string(from: Date(timeIntervalSince1970: TimeInterval(c.closeTime) / 1000.0))

            let line = String(
                format: "%lld,%@,%.8f,%.8f,%.8f,%.8f,%.6f\n",
                c.closeTime,
                isoStr,
                c.open, c.high, c.low, c.close,
                c.volume
            )

            lines += line
            written += 1
        }

        guard written > 0, !lines.isEmpty else { return 0 }

        let handle = try FileHandle(forWritingTo: fileURL)
        try handle.seekToEnd()

        if let data = lines.data(using: .utf8) {
            try handle.write(contentsOf: data)
        }

        try handle.close()

        return written
    }

    // MARK: - Tail read last closeTimeMs
    private static func readLastCloseTimeMs(fileURL: URL) throws -> Int64? {

        let handle = try FileHandle(forReadingFrom: fileURL)
        let size = try handle.seekToEnd()

        let chunk: UInt64 = 8192
        let start = size > chunk ? size - chunk : 0
        try handle.seek(toOffset: start)

        let data = try handle.readToEnd() ?? Data()
        try handle.close()

        guard let text = String(data: data, encoding: .utf8) else {
            return nil
        }

        let lines = text.split(whereSeparator: \.isNewline)
        guard let lastLine = lines.last else { return nil }

        let parts = lastLine.split(separator: ",")
        guard let first = parts.first, let ms = Int64(first) else { return nil }

        return ms
    }
}
