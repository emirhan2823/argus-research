import Foundation

enum ArgusRisk {

    struct Config {
        let perTradeNotionalPct: Double     // equity'nin kaç %'si ile işlem açacağız (paper sizing)
        let dailyLossCapPct: Double         // gün içi max kayıp (equity bazlı)
        let cooldownSeconds: Int            // trade arası minimum süre
        let maxTradesPerDay: Int            // günlük max trade sayısı
        let requireQualityAtLeast: SetupQuality

        init(
            perTradeNotionalPct: Double = 0.10,   // %10 notional (paper)
            dailyLossCapPct: Double = 0.03,       // %3 daily cap
            cooldownSeconds: Int = 60 * 10,       // 10 dk cooldown
            maxTradesPerDay: Int = 6,             // günde max 6 trade
            requireQualityAtLeast: SetupQuality = .good
        ) {
            self.perTradeNotionalPct = perTradeNotionalPct
            self.dailyLossCapPct = dailyLossCapPct
            self.cooldownSeconds = cooldownSeconds
            self.maxTradesPerDay = maxTradesPerDay
            self.requireQualityAtLeast = requireQualityAtLeast
        }
    }

    struct State {
        var dayKeyUTC: String               // "YYYY-MM-DD"
        var dayStartEquity: Double
        var realizedPnl: Double             // gün içi realized pnl (USD)
        var tradesToday: Int
        var lastTradeTime: Date?

        init(now: Date, dayStartEquity: Double) {
            self.dayKeyUTC = State.utcDayKey(now)
            self.dayStartEquity = dayStartEquity
            self.realizedPnl = 0
            self.tradesToday = 0
            self.lastTradeTime = nil
        }

        static func utcDayKey(_ d: Date) -> String {
            let cal = Calendar(identifier: .gregorian)
            var utc = cal
            utc.timeZone = TimeZone(secondsFromGMT: 0)!
            let y = utc.component(.year, from: d)
            let m = utc.component(.month, from: d)
            let day = utc.component(.day, from: d)
            return String(format: "%04d-%02d-%02d", y, m, day)
        }
    }

    struct Decision {
        let allowed: Bool
        let reason: String
    }

    final class Engine {
        let cfg: Config
        private(set) var state: State

        init(cfg: Config, now: Date, startingEquity: Double) {
            self.cfg = cfg
            self.state = State(now: now, dayStartEquity: startingEquity)
        }

        func onNewTick(now: Date, equity: Double) {
            rollDayIfNeeded(now: now, equity: equity)
        }

        func canEnter(now: Date, equity: Double, quality: SetupQuality) -> Decision {
            rollDayIfNeeded(now: now, equity: equity)

            // Quality gate
            if !meetsQuality(quality) {
                return Decision(allowed: false, reason: "QUALITY(\(quality.rawValue)<\(cfg.requireQualityAtLeast.rawValue))")
            }

            // Daily loss cap (realized)
            let cap = -abs(state.dayStartEquity * cfg.dailyLossCapPct)
            if state.realizedPnl <= cap {
                return Decision(allowed: false, reason: "DAILY_LOSS_CAP_HIT(pnl=\(fmt2(state.realizedPnl)) cap=\(fmt2(cap)))")
            }

            // Trade limit
            if state.tradesToday >= cfg.maxTradesPerDay {
                return Decision(allowed: false, reason: "MAX_TRADES_PER_DAY(\(state.tradesToday))")
            }

            // Cooldown
            if let last = state.lastTradeTime {
                let dt = now.timeIntervalSince(last)
                if dt < Double(cfg.cooldownSeconds) {
                    return Decision(allowed: false, reason: "COOLDOWN(\(Int(dt))s/\(cfg.cooldownSeconds)s)")
                }
            }

            return Decision(allowed: true, reason: "OK")
        }

        func recordTrade(now: Date) {
            state.tradesToday += 1
            state.lastTradeTime = now
        }

        func recordRealizedPnl(_ pnl: Double) {
            state.realizedPnl += pnl
        }

        private func rollDayIfNeeded(now: Date, equity: Double) {
            let key = State.utcDayKey(now)
            if key != state.dayKeyUTC {
                state.dayKeyUTC = key
                state.dayStartEquity = equity
                state.realizedPnl = 0
                state.tradesToday = 0
                state.lastTradeTime = nil
            }
        }

        private func meetsQuality(_ q: SetupQuality) -> Bool {
            func rank(_ x: SetupQuality) -> Int {
                switch x {
                case .skip: return 0
                case .ok: return 1
                case .good: return 2
                case .great: return 3
                }
            }
            return rank(q) >= rank(cfg.requireQualityAtLeast)
        }

        private func fmt2(_ x: Double) -> String {
            String(format: "%.2f", x)
        }
    }
}