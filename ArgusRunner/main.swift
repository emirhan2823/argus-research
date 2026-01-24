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

    // --- PIPELINE SETUP ---
    
    // 1. Risk Setup (Conservative)
    let riskCfg = ArgusRisk.Config(
        perTradeNotionalPct: 0.10,
        dailyLossCapPct: 0.03,
        maxDrawdownPct: 0.15,
        maxConsecutiveLosses: 3,
        cooldownSeconds: 60 * 5,
        maxTradesPerDay: 5,
        requireQualityAtLeast: .ok
    )
    let risk = ArgusRisk.Engine(cfg: riskCfg, now: Date(), startingEquity: 30000) // Default start if no state

    // 2. Load History for Backtest
    // For MVP, we load the current month's file. user can expand to load multiple months.
    log("Loading bars for \(args.symbol) \(args.tradeTF)...")
    let marketData = RunnerCSVMarketData.shared
    let allBars = marketData.loadAllBars(symbol: args.symbol, tf: args.tradeTF, date: Date())
    
    log("Loaded \(allBars.count) bars.")
    guard !allBars.isEmpty else {
        log("No data found. Exiting.")
        exit(0)
    }

    // 3. Adapter & State Helper
    func toServiceCandle(_ b: RunnerCSVMarketData.OHLCV) -> Candle {
        // Mapping Runner OHLCV to Algo-Trading Candle (shared name ambiguity fixed by context or matching struct)
        // Assuming 'Candle' in this context resolves to the one Orion expects. 
        // If 'Candle' is ambiguous, we'd need module prefix. 
        // Since we are in Main, we assume implicit visibility.
        return Candle(
            date: Date(timeIntervalSince1970: Double(b.closeTimeMs) / 1000.0),
            open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume
        )
    }
    
    func toBinanceCandle(_ b: RunnerCSVMarketData.OHLCV) -> BinanceClient.Candle {
        return BinanceClient.Candle(
            openTime: b.closeTimeMs - (15*60*1000), // Approx
            open: String(b.open),
            high: String(b.high),
            low: String(b.low),
            close: String(b.close),
            volume: String(b.volume),
            closeTime: b.closeTimeMs,
            quoteAssetVolume: "0", trades: 0, takerBuyBaseAssetVolume: "0", takerBuyQuoteAssetVolume: "0"
        )
    }

    // 4. Time Loop
    var serviceHistory: [Candle] = []
    
    // Warmup period
    let WARMUP = 50
    
    for (idx, bar) in allBars.enumerated() {
        // A. Update "Now"
        let now = Date(timeIntervalSince1970: Double(bar.closeTimeMs) / 1000.0)
        marketData.setCurrentBar(bar)
        
        let sc = toServiceCandle(bar)
        serviceHistory.append(sc)
        if serviceHistory.count > 300 { serviceHistory.removeFirst() }
        
        if idx < WARMUP { continue }
        
        // B. Orion Analysis
        // We need explicit Task context for async calls
        await withTaskGroup(of: Void.self) { group in
            group.addTask {
                let orionDecision = await OrionCouncil.shared.convene(symbol: args.symbol, candles: serviceHistory, engine: .pulse)
                
                // C. Aegean Analysis
                // Aegean works on [BinanceClient.Candle] usually, let's adapt a buffer
                // For efficiency, we can just use the latest values OR maintain a parallel buffer
                // Re-using serviceHistory map is valid
                let aegeanInput = (serviceHistory.suffix(100)).map { c in
                    BinanceClient.Candle(
                        openTime: Int64(c.date.timeIntervalSince1970 * 1000) - 900000,
                        open: String(c.open), high: String(c.high), low: String(c.low), close: String(c.close), volume: String(c.volume),
                        closeTime: Int64(c.date.timeIntervalSince1970 * 1000),
                        quoteAssetVolume: "0", trades: 0, takerBuyBaseAssetVolume: "0", takerBuyQuoteAssetVolume: "0"
                    )
                }
                
                guard let aegeanOut = AegeanIndicator.compute(candles: aegeanInput) else { return }
                
                // D. Prepare Votes
                // 1. Orion Vote
                let orionDir: CouncilAggregator.Direction
                if orionDecision.action == .buy { orionDir = .buy }
                else if orionDecision.action == .sell { orionDir = .sell }
                else { orionDir = .none }
                
                let voteOrion = CouncilAggregator.ModelVote(
                    modelId: "Orion",
                    dir: orionDir,
                    modelConf: orionDecision.netSupport, // already normalized? netSupport is -1 to 1? verify. netSupport 70% -> 0.7
                    trust: 1.0,
                    baseWeight: 0.4
                )
                
                // 2. Aegean Vote
                let aegeanDir: CouncilAggregator.Direction
                if aegeanOut.signal == .buy { aegeanDir = .buy }
                else if aegeanOut.signal == .sell { aegeanDir = .sell }
                else { aegeanDir = .none }
                
                let voteAegean = CouncilAggregator.ModelVote(
                    modelId: "Aegean",
                    dir: aegeanDir,
                    modelConf: (aegeanOut.signal == .none) ? 0.0 : 0.8, // Fixed confidence for signal
                    trust: 1.0,
                    baseWeight: 0.4
                )
                
                // E. Aggregate
                let ensemble = CouncilAggregator.decide(
                    votes: [voteOrion, voteAegean],
                    statsByModel: [:], // Empty stats for now (cold start)
                    perfCfg: CouncilAggregator.PerformanceWeightConfig(rankingWindow: 10, minWeight: 0.1, maxWeight: 0.6, winBonus: 0.05, lossPenalty: 0.1)
                )
                
                // F. Risk Gateway
                let equity = await PaperBroker.shared.getAccountInfo().equity
                risk.onNewTick(now: now, equity: equity) // Update HWM
                
                // Paper Broker Execution
                // Manage Exits first (Trailing Stops handled by Broker? Or us?)
                // PaperBroker doesn't auto-manage stops yet. We must trigger exits.
                
                let positions = (try? await PaperBroker.shared.getPositions()) ?? []
                for p in positions {
                    // Simple Exit Logic: If ensemble flips against us
                    if p.quantity > 0 && ensemble.finalDir == .sell {
                        _ = try? await PaperBroker.shared.placeMarketOrder(symbol: args.symbol, side: .sell, quantity: p.quantity)
                        risk.recordRealizedPnl((p.marketValue - (p.avgCost * p.quantity)))
                        risk.recordTrade(now: now)
                        log("⚠️ EXIT LONG (Ensemble SELL) \(args.symbol) @ \(bar.close)")
                    }
                    else if p.quantity < 0 && ensemble.finalDir == .buy {
                        _ = try? await PaperBroker.shared.placeMarketOrder(symbol: args.symbol, side: .buy, quantity: abs(p.quantity))
                        risk.recordRealizedPnl(((p.avgCost * abs(p.quantity)) - p.marketValue))
                        risk.recordTrade(now: now)
                        log("⚠️ EXIT SHORT (Ensemble BUY) \(args.symbol) @ \(bar.close)")
                    }
                }
                
                // Entry Logic
                if ensemble.finalDir != .none && positions.isEmpty {
                    // Check Risk
                    let quality: SetupQuality = (ensemble.finalConfidence > 0.7) ? .great : .ok
                    let decision = risk.canEnter(now: now, equity: equity, quality: quality)
                    
                    if decision.allowed {
                        let qty = (equity * riskCfg.perTradeNotionalPct) / bar.close
                        let side: BrokerProtocol.OrderSide = (ensemble.finalDir == .buy) ? .buy : .sell
                        
                        log("🚀 ENTER \(side) \(args.symbol) Conf=\(fmt2(ensemble.finalConfidence)) Reason=\(decision.reason)")
                        
                        do {
                            _ = try await PaperBroker.shared.placeMarketOrder(symbol: args.symbol, side: side, quantity: qty)
                            risk.recordTrade(now: now)
                        } catch {
                            log("Entry Failed: \(error)")
                        }
                    } else {
                         // log("Blocked: \(decision.reason)")
                    }
                }
                
                // Log periodic status
                if idx % 96 == 0 { // Every day approx (96 * 15m = 24h)
                    log("STATS Day=\(idx/96) Eq=\(fmt2(equity)) DD=\(fmt2((risk.state.highWaterMark - equity)/risk.state.highWaterMark * 100))%")
                }
            }
        }
    }
    
    // End report
    let finalEq = await PaperBroker.shared.getAccountInfo().equity
    log("=== BACKTEST FINISHED ===")
    log("Final Equity: \(fmt2(finalEq))")
    
    // Helper
    func fmt2(_ v: Double) -> String { String(format: "%.2f", v) }

