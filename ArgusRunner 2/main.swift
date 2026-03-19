import Foundation

enum Mode: String { case backtest, paper, health }

struct Args {
    let mode: Mode
    let symbol: String
    let tf: String
    let tfs: [String]
    let loopSeconds: Int
    let tradeTF: String
    let startingBalance: Double
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
    var startingBalance = 30.0

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
        case "--start-balance":
            if i + 1 < a.count, let v = Double(a[i+1]) { startingBalance = v; i += 1 }
        default:
            break
        }
        i += 1
    }

    if tfs.isEmpty { tfs = [tf] }
    if !tfs.contains(tradeTF) { tfs.append(tradeTF) }

    return Args(mode: mode, symbol: symbol, tf: tf, tfs: tfs, loopSeconds: loopSeconds, tradeTF: tradeTF, startingBalance: startingBalance)
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

    let pos: Double
    let zone: AegeanZone
    let slope: Double
    let slopeDir: String

    let lastClose: Double
    let lastCloseTime: Int64
}

// AegeanZone'da .mid yok => sadece dip/top üzerinden.
func rateSetup(tradeSig: AegeanSignal, lower: [TFSignal], upper: [TFSignal]) -> SetupQuality {
    guard tradeSig != .none else { return .skip }

    func isUpReady(_ s: TFSignal) -> Bool {
        (s.zone == .dip) && (s.slopeDir == "UP")
    }
    func isDownReady(_ s: TFSignal) -> Bool {
        (s.zone == .top) && (s.slopeDir == "DOWN")
    }
    func upperBlocksLong(_ s: TFSignal) -> Bool {
        if s.zone == .top { return true }
        if s.slopeDir == "DOWN" && s.pos > 0.70 { return true }
        return false
    }
    func upperBlocksShort(_ s: TFSignal) -> Bool {
        if s.zone == .dip { return true }
        if s.slopeDir == "UP" && s.pos < 0.30 { return true }
        return false
    }

    let lowerCount = max(lower.count, 1)

    if tradeSig == .buy {
        let ready = lower.filter(isUpReady).count
        let blocks = upper.filter(upperBlocksLong).count
        if blocks >= 1 && ready == 0 { return .skip }
        let ratio = Double(ready) / Double(lowerCount)
        if blocks == 0 && ratio >= 0.75 { return .great }
        if blocks <= 1 && ratio >= 0.50 { return .good }
        return .ok
    }

    if tradeSig == .sell {
        let ready = lower.filter(isDownReady).count
        let blocks = upper.filter(upperBlocksShort).count
        if blocks >= 1 && ready == 0 { return .skip }
        let ratio = Double(ready) / Double(lowerCount)
        if blocks == 0 && ratio >= 0.75 { return .great }
        if blocks <= 1 && ratio >= 0.50 { return .good }
        return .ok
    }

    return .ok
}

// NEW: tradeTF sinyali gelmeden “setup hazır mı?” kontrolü (log için)
func setupReadyForLong(lower: [TFSignal], upper: [TFSignal]) -> (readyCount: Int, lowerCount: Int, blocked: Bool) {
    func isReady(_ s: TFSignal) -> Bool { (s.zone == .dip) && (s.slopeDir == "UP") }
    func upperBlocks(_ s: TFSignal) -> Bool {
        if s.zone == .top { return true }
        if s.slopeDir == "DOWN" && s.pos > 0.70 { return true }
        return false
    }
    let ready = lower.filter(isReady).count
    let blocked = upper.contains(where: upperBlocks)
    return (ready, max(lower.count, 1), blocked)
}

func setupReadyForShort(lower: [TFSignal], upper: [TFSignal]) -> (readyCount: Int, lowerCount: Int, blocked: Bool) {
    func isReady(_ s: TFSignal) -> Bool { (s.zone == .top) && (s.slopeDir == "DOWN") }
    func upperBlocks(_ s: TFSignal) -> Bool {
        if s.zone == .dip { return true }
        if s.slopeDir == "UP" && s.pos < 0.30 { return true }
        return false
    }
    let ready = lower.filter(isReady).count
    let blocked = upper.contains(where: upperBlocks)
    return (ready, max(lower.count, 1), blocked)
}

// MARK: - Paper portfolio
enum PositionSide: String { case none = "NONE", long = "LONG", short = "SHORT" }

struct Position {
    var side: PositionSide
    var qty: Double
    var entry: Double
    var entryTime: Date
}

final class PaperPortfolio {
    var cash: Double
    var position: Position?

    init(cash: Double) {
        self.cash = cash
        self.position = nil
    }

    func equity(mark: Double) -> Double {
        guard let p = position else { return cash }
        switch p.side {
        case .long:
            return cash + p.qty * (mark - p.entry)
        case .short:
            return cash + p.qty * (p.entry - mark)
        case .none:
            return cash
        }
    }

    func open(side: PositionSide, price: Double, notional: Double, now: Date) -> Bool {
        guard position == nil else { return false }
        guard price > 0, notional > 0 else { return false }
        let qty = notional / price
        position = Position(side: side, qty: qty, entry: price, entryTime: now)
        return true
    }

    func close(price: Double, now: Date) -> Double? {
        guard let p = position else { return nil }
        let pnl: Double
        switch p.side {
        case .long:
            pnl = p.qty * (price - p.entry)
        case .short:
            pnl = p.qty * (p.entry - price)
        case .none:
            pnl = 0
        }
        cash += pnl
        position = nil
        return pnl
    }
}

// MARK: - Format
func fmtPrice(_ x: Double) -> String { String(format: "%.8f", x) }
func fmt2(_ x: Double) -> String { String(format: "%.2f", x) }
func fmt3(_ x: Double) -> String { String(format: "%.3f", x) }

// ---- MAIN
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

    let portfolio = PaperPortfolio(cash: args.startingBalance)
    let riskCfg = ArgusRisk.Config(
        perTradeNotionalPct: 0.10,
        dailyLossCapPct: 0.03,
        cooldownSeconds: 60 * 10,
        maxTradesPerDay: 6,
        requireQualityAtLeast: SetupQuality.ok   // <- .good yerine .ok
    )
    
    let risk = ArgusRisk.Engine(cfg: riskCfg, now: Date(), startingEquity: portfolio.cash)

    log("risk: perTradeNotional=\(Int(riskCfg.perTradeNotionalPct*100))% dailyLossCap=\(Int(riskCfg.dailyLossCapPct*100))% cooldown=\(riskCfg.cooldownSeconds)s maxTrades=\(riskCfg.maxTradesPerDay) require>=\(riskCfg.requireQualityAtLeast.rawValue)")

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
                        pos: out.pos,
                        zone: out.zone,
                        slope: out.slope,
                        slopeDir: out.slopeDir,
                        lastClose: last.close,
                        lastCloseTime: last.closeTime
                    )
                    lastSignals[tf] = sig

                    if tf != tradeTF {
                        if DEBUG_LOWER_UPPER_LOGS {
                            log("TF NEW \(args.symbol) \(tf) sig=\(sig.signal.rawValue.uppercased()) close=\(fmtPrice(sig.lastClose)) expRsi=\(fmt2(sig.expRsi)) upper=\(fmt2(sig.upper)) lower=\(fmt2(sig.lower)) pos=\(fmt3(sig.pos)) zone=\(sig.zone.rawValue.uppercased()) slope=\(fmt2(sig.slope)) \(sig.slopeDir) at \(ArgusTime.msToISO(sig.lastCloseTime))")
                        }
                        continue
                    }

                    let lower = lowerTFs.compactMap { lastSignals[$0] }
                    let upper = upperTFs.compactMap { lastSignals[$0] }
                    let quality = rateSetup(tradeSig: sig.signal, lower: lower, upper: upper)

                    func compact(_ xs: [TFSignal]) -> String {
                        xs.map { "\($0.tf)=\($0.signal.rawValue.uppercased())/\($0.zone.rawValue.uppercased())/\($0.slopeDir)" }
                          .joined(separator: " ")
                    }

                    let mark = sig.lastClose
                    let eq = portfolio.equity(mark: mark)
                    risk.onNewTick(now: Date(), equity: eq)

                    log("TRADE_TF NEW \(args.symbol) \(tradeTF) sig=\(sig.signal.rawValue.uppercased()) q=\(quality.rawValue) close=\(fmtPrice(sig.lastClose)) expRsi=\(fmt2(sig.expRsi)) upper=\(fmt2(sig.upper)) lower=\(fmt2(sig.lower)) pos=\(fmt3(sig.pos)) zone=\(sig.zone.rawValue.uppercased()) slope=\(fmt2(sig.slope)) \(sig.slopeDir) equity=\(fmt2(eq)) at \(ArgusTime.msToISO(sig.lastCloseTime))")
                    // --- DEBUG: explain SKIP reasons (why no trade) ---
                    let riskDecision = risk.canEnter(now: Date(), equity: eq, quality: quality)
                    var reasons: [String] = []
                    if sig.signal.rawValue.uppercased() == "NONE" { reasons.append("SIGNAL_NONE") }
                    if quality == .skip { reasons.append("SETUP_QUALITY_SKIP") }
                    if !riskDecision.allowed { reasons.append("RISK:\(riskDecision.reason)") }
                    if !reasons.isEmpty {
                        log("  SKIP_REASONS -> \(reasons.joined(separator: ", "))")
                    }
if !lower.isEmpty { log("  lower: \(compact(lower))") }
                    if !upper.isEmpty { log("  upper: \(compact(upper))") }

                    // NEW: Eğer tradeTF NONE ama altlar hazırsa, bunu açıkça logla.
                    if sig.signal == .none {
                        let longReady = setupReadyForLong(lower: lower, upper: upper)
                        if !longReady.blocked && longReady.readyCount >= Int(ceil(Double(longReady.lowerCount) * 0.75)) {
                            log("SETUP READY (LONG) -> lowerReady=\(longReady.readyCount)/\(longReady.lowerCount) upperBlocked=false  waitingFor=15m BUY")
                        }
                        let shortReady = setupReadyForShort(lower: lower, upper: upper)
                        if !shortReady.blocked && shortReady.readyCount >= Int(ceil(Double(shortReady.lowerCount) * 0.75)) {
                            log("SETUP READY (SHORT) -> lowerReady=\(shortReady.readyCount)/\(shortReady.lowerCount) upperBlocked=false  waitingFor=15m SELL")
                        }
                    }

                    // Close on opposite signal
                    if let pos = portfolio.position {
                        if pos.side == .long && sig.signal == .sell {
                            if let pnl = portfolio.close(price: mark, now: Date()) {
                                risk.recordRealizedPnl(pnl)
                                risk.recordTrade(now: Date())
                                log("paper: CLOSE LONG @\(fmtPrice(mark)) pnl=\(fmt2(pnl)) cash=\(fmt2(portfolio.cash)) dayPnl=\(fmt2(risk.state.realizedPnl)) tradesToday=\(risk.state.tradesToday)")
                            }
                        } else if pos.side == .short && sig.signal == .buy {
                            if let pnl = portfolio.close(price: mark, now: Date()) {
                                risk.recordRealizedPnl(pnl)
                                risk.recordTrade(now: Date())
                                log("paper: CLOSE SHORT @\(fmtPrice(mark)) pnl=\(fmt2(pnl)) cash=\(fmt2(portfolio.cash)) dayPnl=\(fmt2(risk.state.realizedPnl)) tradesToday=\(risk.state.tradesToday)")
                            }
                        }
                    }

                    // Entry
                    if portfolio.position == nil && sig.signal != .none && quality != .skip {
                        let decision = risk.canEnter(now: Date(), equity: portfolio.equity(mark: mark), quality: quality)
                        if decision.allowed {
                            let notional = portfolio.equity(mark: mark) * riskCfg.perTradeNotionalPct
                            let side: PositionSide = (sig.signal == .buy) ? .long : .short
                            if portfolio.open(side: side, price: mark, notional: notional, now: Date()) {
                                risk.recordTrade(now: Date())
                                log("paper: OPEN \(side.rawValue) @\(fmtPrice(mark)) notional=\(fmt2(notional)) cash=\(fmt2(portfolio.cash)) reason=\(decision.reason)")
                            } else {
                                log("paper: OPEN FAILED reason=PORTFOLIO_BUSY")
                            }
                        } else {
                            log("paper: ENTRY_BLOCKED reason=\(decision.reason)")
                        }
                    }

                } catch {
                    log("ERROR \(args.symbol) \(tf) -> \(error)")
                }
            }

            try? await Task.sleep(nanoseconds: UInt64(args.loopSeconds) * 1_000_000_000)
        }
    }

    RunLoop.main.run()
}

