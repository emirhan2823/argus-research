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
    let dataDir: String?
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
    var dataDir: String? = nil

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
        case "--dataDir":
            if i + 1 < a.count { dataDir = a[i+1]; i += 1 }
        default:
            break
        }
        i += 1
    }

    if tfs.isEmpty { tfs = [tf] }
    if !tfs.contains(tradeTF) { tfs.append(tradeTF) }
    
    // Auto-switch to backtest if fast loop
    if loopSeconds == 0 {
        mode = .backtest
    }

    return Args(mode: mode, symbol: symbol, tf: tf, tfs: tfs, loopSeconds: loopSeconds, tradeTF: tradeTF, startingBalance: startingBalance, dataDir: dataDir)
}

struct BacktestStats {
    var totalTrades: Int = 0
    var winningTrades: Int = 0
    var losingTrades: Int = 0
    var totalPnL: Double = 0.0
    var maxDrawdown: Double = 0.0
    var biggestWin: Double = 0.0
    var biggestLoss: Double = 0.0
    var feesPaid: Double = 0.0
}

func log(_ s: String) {
    let ts = ISO8601DateFormatter().string(from: Date())
    print("[\(ts)] \(s)")
}

// MARK: - Format
func fmtPrice(_ x: Double) -> String { String(format: "%.8f", x) }
func fmt2(_ x: Double) -> String { String(format: "%.2f", x) }
func fmt3(_ x: Double) -> String { String(format: "%.3f", x) }

// ---- MAIN
let args = parseArgs()

log("=== ARGUS RUNNER START ===")
log("mode=\(args.mode.rawValue) symbol=\(args.symbol) tfs=\(args.tfs.joined(separator: ",")) tradeTF=\(args.tradeTF) loop=\(args.loopSeconds)s")

// 1. Configure Data & Broker
await RunnerCSVMarketData.shared.configure(dataDir: args.dataDir)
await RunnerCSVMarketData.shared.printDataPath()

await PaperBroker.shared.configure(initialCash: args.startingBalance, executionModel: .marketWrapper)
log("Brokers Configured. Initial Cash: \(fmt2(args.startingBalance))")

// 2. Load History
log("Loading bars for \(args.symbol) \(args.tradeTF)...")
let marketData = RunnerCSVMarketData.shared
let allBars = await marketData.loadAllBars(symbol: args.symbol, tf: args.tradeTF, date: Date())

if allBars.isEmpty {
    log("insufficient bars: 0")
    exit(1)
}

log("Loaded \(allBars.count) bars.")

// 3. Warmup Logic
// min(200, bars.count / 5), never exceed count-1
let warmupLimit = min(200, allBars.count / 5)
let finalWarmup = min(warmupLimit, allBars.count - 1)
log("Warmup set to: \(finalWarmup) bars")


// 4. Time Loop
var serviceHistory: [RunnerCandle] = []

// Risk Setup
let riskCfg = ArgusRisk.Config(
    perTradeNotionalPct: 0.10, // Phase-2 requirement
    dailyLossCapPct: 0.03,
    maxDrawdownPct: 0.06,
    maxConsecutiveLosses: 3,
    cooldownSeconds: 600,
    maxTradesPerDay: 10,
    requireQualityAtLeast: .ok
)
let risk = ArgusRisk.Engine(cfg: riskCfg, now: Date(), startingEquity: args.startingBalance)

log("Starting Loop. Risk: DayLoss=\(riskCfg.dailyLossCapPct*100)%, DD=\(riskCfg.maxDrawdownPct*100)%")

// Exits Configuration
enum ExitStrategy {
    case fixed(tp: Double, sl: Double)      // TP: 2.0%, SL: 1.0%
    case trailing(atrMult: Double)          // Chandelier / ATR Trail
    case time(bars: Int)                    // Exit after N bars
    case aegeanFlip                         // Exit if slope flips
}

let activeExitStrategy: ExitStrategy = .fixed(tp: 0.04, sl: 0.02) // Conservative starting point

// Simulation Loop
for (idx, bar) in allBars.enumerated() {
    let now = Date(timeIntervalSince1970: Double(bar.closeTimeMs) / 1000.0)
    
    // Set Current Bar (No Lookahead for Observer)
    await marketData.setCurrentBar(bar)
    
    // --- UPDATE POSITIONS & CHECK EXITS ---
    // This simulates "On Tick" for open positions
    let currentPrice = bar.close
    await PaperBroker.shared.updatePositions(currentPrice: currentPrice, time: now)
    
    // --- SIGNAL ---
    // Convert OHLCV to RunnerCandle
    // MVP approx: openTime = closeTime - 15m (since we know it's 15m)
    let durationMs: Int64 = 15 * 60 * 1000
    let sc = RunnerCandle(
        openTime: bar.closeTimeMs - durationMs,
        closeTime: bar.closeTimeMs,
        open: bar.open, high: bar.high, low: bar.low, close: bar.close, volume: bar.volume
    )
    serviceHistory.append(sc)
    // Keep enough history for Aegean (EMA 200 + buffer)
    if serviceHistory.count > 400 { serviceHistory.removeFirst() }

    if idx < finalWarmup { continue }
    
    // --- STRATEGY: AEGEAN MINIMAL ---
    // Run generic indicator
    if let aegean = AegeanIndicator.compute(candles: serviceHistory) {
        
        let equity = try await PaperBroker.shared.getAccountInfo().equity
        risk.onNewTick(now: now, equity: equity)
        
        // Log every bar (verbose debug for Phase 2)
        // log("BAR \(idx) | \(fmtPrice(bar.close)) | Slp:\(fmt3(aegean.slope))(\(aegean.slopeDir)) Pos:\(fmt2(aegean.pos)) Zn:\(aegean.zone)")
        
        // Entry Logic
        var signal: OrderSide? = nil
        var confidence = 0.55
        
        // Rule: LONG
        // slopeDir==UP AND pos<0.35 AND zone != TOP (OVERBOUGHT)
        if aegean.slopeDir == "UP" && aegean.pos < 0.35 && aegean.zone != .top {
            signal = .buy
            confidence += min(abs(aegean.slope) / 10.0, 0.25)
            if aegean.zone == .dip { confidence += 0.05 }
        }
        
        // Rule: SHORT
        // slopeDir==DOWN AND pos>0.65 AND zone != DIP (OVERSOLD)
        else if aegean.slopeDir == "DOWN" && aegean.pos > 0.65 && aegean.zone != .dip {
            signal = .sell
            confidence += min(abs(aegean.slope) / 10.0, 0.25)
            if aegean.zone == .top { confidence += 0.05 }
        }
        
        // If we have a signal, check Risk & Execute
        if let sig = signal {
            let existingPos = try await PaperBroker.shared.getPositions(symbol: args.symbol)
            
            // Only enter if flat (Simple MVP rule)
            if existingPos.isEmpty {
                let decision = risk.canEnter(now: now, equity: equity, quality: .ok)
                
                if decision.allowed {
                    // Sizing: risk per trade based on SL distance? 
                    // MVP: Fixed % of equity
                    let positionSize = equity * riskCfg.perTradeNotionalPct
                    let qty = positionSize / bar.close
                    let notional = qty * bar.close
                    
                    // Low Balance / Backtest Mode Rule
                    // In backtest/paper, allow smaller entries (down to $1 notional).
                    // In live, keep safety at $5.
                    let isBacktest = (args.loopSeconds == 0) || (args.mode == .backtest) || (args.mode == .paper)
                    let baseMinNotional = 5.0
                    // Allow down to 1.0 or 5% of start balance, whichever is higher (bounded by 5.0)
                    let minNotional = isBacktest ? max(1.0, min(baseMinNotional, args.startingBalance * 0.05)) : baseMinNotional

                    log("DEBUG ENTRY CHECK equity=\(fmt2(equity)) price=\(fmtPrice(bar.close)) notional=\(fmt2(notional)) minNotional=\(fmt2(minNotional)) qty=\(fmtPrice(qty))")

                    if qty <= 0 {
                         log("⛔️ SKIP ENTRY: qty=\(qty) rounded=0 price=\(bar.close)")
                    }
                    else if notional > minNotional { 
                        log("🚀 ENTRY \(sig) @ \(fmtPrice(bar.close)) | Aegean: \(aegean.slopeDir) Pos:\(fmt2(aegean.pos))")
                        
                        // Execute Entry
                        do {
                            _ = try await PaperBroker.shared.placeMarketOrder(symbol: args.symbol, side: sig, quantity: qty)
                            risk.recordTrade(now: now)
                            
                            // Setup Exits (Manual implementation for MVP)
                            // For Phase 2, we will Attach logic to the position in PaperBroker
                            var slPrice = 0.0
                            var tpPrice = 0.0
                            
                            switch activeExitStrategy {
                            case .fixed(let tp, let sl):
                                if sig == .buy {
                                    slPrice = bar.close * (1.0 - sl)
                                    tpPrice = bar.close * (1.0 + tp)
                                } else {
                                    slPrice = bar.close * (1.0 + sl)
                                    tpPrice = bar.close * (1.0 - tp)
                                }
                            default:
                                break
                            }
                            
                            await PaperBroker.shared.setBrackets(symbol: args.symbol, sl: slPrice, tp: tpPrice)
                            
                        } catch {
                            log("❌ Order Failed: \(error)")
                        }
                    } else {
                        log("⛔️ SKIP ENTRY: notional=\(fmt2(notional)) < minNotional=\(fmt2(minNotional)) equity=\(fmt2(equity))")
                    }
                } else {
                    // Log Risk Veto
                    log("🛡️ RISK BLOCK: \(decision.reason ?? "Unknown")")
                }
            }
        }
        
        // Check Exits for existing positions (if Logic-based like Aegean Flip)
        // ... (Optional Phase 2 extension)
    }
    
    // Loop Sleep
    if args.loopSeconds > 0 {
        try? await Task.sleep(nanoseconds: UInt64(args.loopSeconds) * 1_000_000_000)
    }
}

// 5. Final Report
let finalAccount = try await PaperBroker.shared.getAccountInfo()
let perf = try await PaperBroker.shared.calculatePerformance()

log("=== BACKTEST FINISHED ===")
log("Total Trades: \(perf.totalTrades)")
log("Win Rate:     \(fmt2(perf.winRate))%")
log("Final Equity: \(fmt2(finalAccount.equity))")
log("Total Comm:   \(fmt2(perf.totalCommission))")

// Risk Drawdown
let dd = ((risk.state.highWaterMark - finalAccount.equity) / risk.state.highWaterMark) * 100
log("Max Drawdown: \(fmt2(dd))%") // This is end-state DD, real max DD should be tracked in RiskEngine

