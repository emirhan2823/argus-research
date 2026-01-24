import Foundation

actor RunnerCSVMarketData {
    static let shared = RunnerCSVMarketData()

    struct OHLCV {
        let closeTimeMs: Int64
        let open: Double
        let high: Double
        let low: Double
        let close: Double
        let volume: Double
    }

    private let fm = FileManager.default
    private var lastCache: (path: String, fileSize: UInt64, lastLineHash: Int, bar: OHLCV)?

    private var baseDir: URL {
        let fm = FileManager.default

        #if os(macOS)
        // macOS: ~/Library/Application Support/ArgusRunner/data
        let home = fm.homeDirectoryForCurrentUser
        return home
            .appendingPathComponent("Library")
            .appendingPathComponent("Application Support")
            .appendingPathComponent("ArgusRunner")
            .appendingPathComponent("data")

        #else
        // iOS: App sandbox (Documents)
        let docs = fm.urls(for: .documentDirectory, in: .userDomainMask).first!

        return docs
            .appendingPathComponent("ArgusRunner")
            .appendingPathComponent("data")
        #endif
    }

    func latestClose(symbol: String, tf: String, now: Date = Date()) -> Double? {
        return latestOHLCV(symbol: symbol, tf: tf, now: now)?.close
    }

    func latestOHLCV(symbol: String, tf: String, now: Date = Date()) -> OHLCV? {
        let path = csvPath(symbol: symbol, tf: tf, now: now).path
        guard fm.fileExists(atPath: path) else {
            print("⚠️ RunnerCSV: file not found: \(path)")
            return nil
        }

        if let attrs = try? fm.attributesOfItem(atPath: path),
           let fileSize = attrs[.size] as? UInt64
        {
            if let cached = lastCache, cached.path == path, cached.fileSize == fileSize {
                return cached.bar
            }
        }

        guard let lastLine = readLastNonEmptyLine(path: path) else {
            print("⚠️ RunnerCSV: could not read last line: \(path)")
            return nil
        }

        let h = lastLine.hashValue
        if let cached = lastCache, cached.path == path, cached.lastLineHash == h {
            return cached.bar
        }

        guard let bar = parseLine(lastLine) else {
            print("⚠️ RunnerCSV: parse failed for last line: \(lastLine)")
            return nil
        }

        let fileSize = (try? fm.attributesOfItem(atPath: path)[.size] as? UInt64) ?? 0
        lastCache = (path: path, fileSize: fileSize, lastLineHash: h, bar: bar)

        return bar
    }

    private func csvPath(symbol: String, tf: String, now: Date) -> URL {
        let df = DateFormatter()
        df.calendar = Calendar(identifier: .gregorian)
        df.locale = Locale(identifier: "en_US_POSIX")
        df.timeZone = TimeZone(secondsFromGMT: 0)
        df.dateFormat = "yyyy-MM"
        let ym = df.string(from: now)

        return baseDir
            .appendingPathComponent(symbol.uppercased())
            .appendingPathComponent(tf)
            .appendingPathComponent("\(ym).csv")
    }

    private func parseLine(_ line: String) -> OHLCV? {
        let parts = line.split(separator: ",", omittingEmptySubsequences: false).map { String($0) }
        guard parts.count >= 6 else { return nil }

        guard let ms = Int64(parts[0].trimmingCharacters(in: .whitespacesAndNewlines)) else { return nil }

        let tail = Array(parts.suffix(5)).map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }

        guard
            let open = Double(tail[0]),
            let high = Double(tail[1]),
            let low  = Double(tail[2]),
            let close = Double(tail[3]),
            let vol = Double(tail[4])
        else { return nil }

        return OHLCV(closeTimeMs: ms, open: open, high: high, low: low, close: close, volume: vol)
    }

    private func readLastNonEmptyLine(path: String) -> String? {
        guard let fh = FileHandle(forReadingAtPath: path) else { return nil }
        defer { try? fh.close() }

        let chunkSize = 64 * 1024

        do {
            let size = try fh.seekToEnd()
            if size == 0 { return nil }

            let start = max(Int64(0), Int64(size) - Int64(chunkSize))
            try fh.seek(toOffset: UInt64(start))

            let data = try fh.readToEnd() ?? Data()
            guard let text = String(data: data, encoding: .utf8) else {
                return readLastLineFallback(path: path)
            }

            let lines = text.split(whereSeparator: \.isNewline).map { String($0) }
            for line in lines.reversed() {
                let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                if trimmed.isEmpty { continue }
                if trimmed.lowercased().hasPrefix("closetimems") { continue }
                return trimmed
            }
            return nil
        } catch {
            return readLastLineFallback(path: path)
        }
    }

    private func readLastLineFallback(path: String) -> String? {
        guard let text = try? String(contentsOfFile: path, encoding: .utf8) else { return nil }
        let lines = text.split(whereSeparator: \.isNewline).map { String($0) }
        for line in lines.reversed() {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty { continue }
            if trimmed.lowercased().hasPrefix("closetimems") { continue }
            return trimmed
        }
        return nil
    }
}
