import Foundation

enum Mode: String { case backtest, paper, health }

struct Args {
    let mode: Mode
    let symbol: String
    let tf: String
    let tfs: [String]
    let loopSeconds: Int
    let tradeTF: String
}

func parseCSVList(_ s: String) -> [String] {
    s.split(separator: ",")
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
}

func parseArgs() -> Args {
    var mode: Mode = .health
    var symbol = "BTCUSDT"
    var tf = "15m"
    var tfs: [String] = []
    var loopSeconds = 60
    var tradeTF = "15m"

    let a = CommandLine.arguments
    var i = 1
    while i < a.count {
        switch a[i] {
        case "--mode":
            if i + 1 < a.count, let m = Mode(rawValue: a[i+1]) { mode = m; i += 1 }
        case "--symbol":
            if i + 1 < a.count { symbol = a[i+1]; i += 1 }
        case "--tf":
            if i + 1 < a.count { tf = a[i+1]; i += 1 }
        case "--tfs":
            if i + 1 < a.count { tfs = parseCSVList(a[i+1]); i += 1 }
        case "--trade-tf":
            if i + 1 < a.count { tradeTF = a[i+1]; i += 1 }
        case "--loop":
            if i + 1 < a.count, let v = Int(a[i+1]) { loopSeconds = v; i += 1 }
        default:
            break
        }
        i += 1
    }

    if tfs.isEmpty { tfs = [tf] }
    if !tfs.contains(tradeTF) { tfs.append(tradeTF) }

    return Args(mode: mode, symbol: symbol, tf: tf, tfs: tfs, loopSeconds: loopSeconds, tradeTF: tradeTF)
}

func log(_ s: String) {
    let ts = ISO8601DateFormatter().string(from: Date())
    print("[\(ts)] \(s)")
}

// MARK: - TF helpers
func tfMinutes(_ tf: String) -> Int? {
    let s = tf.lowercased()
    if s.hasSuffix("m"), let n = Int(s.dropLast()) { return n }
    if s.hasSuffix("h"), let n = Int(s.dropLast()) { return n * 60 }
    if s.hasSuffix("d"), let n = Int(s.dropLast()) { return n * 1440 }
    return nil
}

func classifyTFs(all: [String], tradeTF: String) -> (lower: [String], trade: String, upper: [String]) {
    let tMin = tfMinutes(tradeTF) ?? 15
    var lower: [(String, Int)] = []
    var upper: [(String, Int)] = []

    for tf in all {
        let m = tfMinutes(tf) ?? 0
        if tf == tradeTF { continue }
        if m < tMin { lower.append((tf, m)) }
        if m > tMin { upper.append((tf, m)) }
    }

    lower.sort { $0.1 < $1.1 }
    upper.sort { $0.1 < $1.1 }

    return (lower.map{$0.0}, tradeTF, upper.map{$0.0})
}

// MARK: - Setup rating
enum SetupQuality: String { case skip = "SKIP", ok = "OK", good = "GOOD", great = "GREAT" }

struct TFSignal {
    let tf: String
    let signal: AegeanSignal
    let expRsi: Double
    let upper: Double
    let lower: Double
    let lastClose: Double
    let lastCloseTime: Int64
}

func rateSetup(tradeSig: AegeanSignal, lower: [TFSignal], upper: [TFSignal]) -> SetupQuality {
    guard tradeSig != .none else { return .skip }
    let desired = tradeSig

    let lowerTotal = lower.count
    let lowerConfirm = lower.filter { $0.signal == desired }.count
    let lowerOppose = lower.filter { $0.signal != .none && $0.signal != desired }.count

    let upperOppose = upper.filter { $0.signal != .none && $0.signal != desired }.count

    if upperOppose >= 1 && lowerConfirm == 0 { return .skip }
    if lowerOppose >= 2 { return .skip }

    let confirmRatio = lowerTotal == 0 ? 0.0 : Double(lowerConfirm) / Double(lowerTotal)

    if upperOppose >= 2 { return .ok }
    if confirmRatio >= 0.75 && upperOppose == 0 { return .great }
    if confirmRatio >= 0.5 && upperOppose <= 1 { return .good }
    return .ok
}

// MARK: - Format
func fmtPrice(_ x: Double) -> String { String(format: "%.8f", x) }
func fmt2(_ x: Double) -> String { String(format: "%.2f", x) }

let args = parseArgs()

log("=== ARGUS RUNNER START ===")
log("mode=\(args.mode.rawValue) symbol=\(args.symbol) tfs=\(args.tfs.joined(separator: ",")) tradeTF=\(args.tradeTF) loop=\(args.loopSeconds)s")

do {
    let base = try DataStore.baseDir()
    log("dataDir=\(base.path)")
} catch {
    log("dataDir error: \(error)")
}

switch args.mode {

case .health:
    log("health=ok")
    exit(0)

case .backtest:
    log("backtest: TODO")
    exit(0)

case .paper:
    log("paper: starting loop (Ctrl+C to stop)")
    let client = BinanceClient()

    let DEBUG_LOWER_UPPER_LOGS = true

    var lastSignals: [String: TFSignal] = [:]

    let (lowerTFs, tradeTF, upperTFs) = classifyTFs(all: args.tfs, tradeTF: args.tradeTF)
    log("TF split -> lower=\(lowerTFs.joined(separator: ",")) trade=\(tradeTF) upper=\(upperTFs.joined(separator: ","))")

    Task {
        while true {
            for tf in args.tfs {
                do {
                    let candles = try await client.fetchKlines(symbol: args.symbol, interval: tf, limit: 300)
                    let newRows = try DataStore.appendCandlesCSV(symbol: args.symbol, tf: tf, candles: candles)

                    guard newRows > 0, let last = candles.last else { continue }

                    guard let out = AegeanIndicator.compute(candles: candles) else {
                        if tf == tradeTF {
                            log("TRADE_TF NEW \(args.symbol) \(tradeTF) (Aegean: insufficient bars)")
                        } else if DEBUG_LOWER_UPPER_LOGS {
                            log("TF NEW \(args.symbol) \(tf) (Aegean: insufficient bars)")
                        }
                        continue
                    }

                    let sig = TFSignal(
                        tf: tf,
                        signal: out.signal,
                        expRsi: out.expRsi,
                        upper: out.upper,
                        lower: out.lower,
                        lastClose: last.close,
                        lastCloseTime: last.closeTime
                    )
                    lastSignals[tf] = sig

                    if tf != tradeTF {
                        if DEBUG_LOWER_UPPER_LOGS {
                            log("TF NEW \(args.symbol) \(tf) sig=\(sig.signal.rawValue.uppercased()) close=\(fmtPrice(sig.lastClose)) expRsi=\(fmt2(sig.expRsi)) upper=\(fmt2(sig.upper)) lower=\(fmt2(sig.lower)) at \(msToISO(sig.lastCloseTime))")
                        }
                        continue
                    }

                    let lower = lowerTFs.compactMap { lastSignals[$0] }
                    let upper = upperTFs.compactMap { lastSignals[$0] }
                    let quality = rateSetup(tradeSig: sig.signal, lower: lower, upper: upper)

                    func compact(_ xs: [TFSignal]) -> String {
                        xs.map { "\($0.tf)=\($0.signal.rawValue.uppercased())" }.joined(separator: " ")
                    }

                    log("TRADE_TF NEW \(args.symbol) \(tradeTF) sig=\(sig.signal.rawValue.uppercased()) q=\(quality.rawValue) close=\(fmtPrice(sig.lastClose)) expRsi=\(fmt2(sig.expRsi)) upper=\(fmt2(sig.upper)) lower=\(fmt2(sig.lower)) at \(msToISO(sig.lastCloseTime))")
                    if !lower.isEmpty { log("  lower: \(compact(lower))") }
                    if !upper.isEmpty { log("  upper: \(compact(upper))") }

                } catch {
                    log("ERROR \(args.symbol) \(tf) -> \(error)")
                }
            }

            try? await Task.sleep(nanoseconds: UInt64(args.loopSeconds) * 1_000_000_000)
        }
    }

    RunLoop.main.run()
}

