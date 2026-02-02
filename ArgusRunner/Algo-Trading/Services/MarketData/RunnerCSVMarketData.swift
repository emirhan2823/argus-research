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
    private var simulatedBar: OHLCV?
    
    // Explicit base directory (set by main.swift)
    private var explicitBaseDir: URL?

    func setCurrentBar(_ bar: OHLCV) {
        simulatedBar = bar
    }
    
    func configure(dataDir: String?) {
        if let d = dataDir {
            self.explicitBaseDir = URL(fileURLWithPath: d)
        }
    }

    private var baseDir: URL {
        // 1. Explicit Argument
        if let explicit = explicitBaseDir {
            return explicit
        }
        
        // 2. Relative ./data
        let cwd = URL(fileURLWithPath: fm.currentDirectoryPath).appendingPathComponent("data")
        var isDir: ObjCBool = false
        if fm.fileExists(atPath: cwd.path, isDirectory: &isDir) && isDir.boolValue {
           return cwd
        }

        // 3. MacOS/Default Fallback
        #if os(macOS)
        let home = fm.homeDirectoryForCurrentUser
        return home
            .appendingPathComponent("Library")
            .appendingPathComponent("Application Support")
            .appendingPathComponent("ArgusRunner")
            .appendingPathComponent("data")
        #else
        let docs = fm.urls(for: .documentDirectory, in: .userDomainMask).first!
        return docs
            .appendingPathComponent("ArgusRunner")
            .appendingPathComponent("data")
        #endif
    }
    
    func printDataPath() {
        print("Loading data from: \(baseDir.path)")
    }

    func latestClose(symbol: String, tf: String, now: Date = Date()) -> Double? {
        return latestOHLCV(symbol: symbol, tf: tf, now: now)?.close
    }

    func latestOHLCV(symbol: String, tf: String, now: Date = Date()) -> OHLCV? {
        // Deterministic Mode:
        if let s = simulatedBar { return s }
        
        // Live/Watcher Mode:
        let path = csvPath(symbol: symbol, tf: tf, now: now).path
        guard fm.fileExists(atPath: path) else {
            // print("⚠️ RunnerCSV: file not found: \(path)") // noisy
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
            return nil
        }

        let h = lastLine.hashValue
        if let cached = lastCache, cached.path == path, cached.lastLineHash == h {
            return cached.bar
        }

        guard let bar = parseLine(lastLine) else {
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
        // Simple full read fallback for MVP stability
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

    func loadAllBars(symbol: String, tf: String, date: Date = Date()) -> [OHLCV] {
        let dir = baseDir
            .appendingPathComponent(symbol.uppercased())
            .appendingPathComponent(tf)

        // 1. Check if directory exists
        var isDir: ObjCBool = false
        if !fm.fileExists(atPath: dir.path, isDirectory: &isDir) || !isDir.boolValue {
            print("⚠️ RunnerCSV: Directory not found: \(dir.path)")
            return []
        }

        // 2. List all .csv files
        guard let files = try? fm.contentsOfDirectory(atPath: dir.path) else {
            print("⚠️ RunnerCSV: Could not list files in: \(dir.path)")
            return []
        }

        let csvFiles = files.filter { $0.hasSuffix(".csv") }.sorted() // Sort by name (YYYY-MM)

        // 3. Read and parse
        var allBars: [OHLCV] = []

        for file in csvFiles {
            let path = dir.appendingPathComponent(file).path
            guard let content = try? String(contentsOfFile: path, encoding: .utf8) else {
                continue
            }

            let lines = content.split(whereSeparator: \.isNewline)
            for line in lines {
                let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                if trimmed.isEmpty { continue }
                if trimmed.lowercased().hasPrefix("closetimems") { continue } // Skip header

                if let bar = parseLine(trimmed) {
                    allBars.append(bar)
                }
            }
        }

        // 4. Sort by time (just to be safe)
        allBars.sort { $0.closeTimeMs < $1.closeTimeMs }

        // print("✅ RunnerCSV: Loaded \(allBars.count) bars for \(symbol) \(tf)")
        return allBars
    }
}
