import Foundation

public struct ClosedTradeOutcome: Codable, Sendable {
    public var tradeId: String
    public var symbol: String
    public var pnl: Double          // >0 win, <=0 loss
    public var closedAt: Date

    /// Which models contributed to opening this trade
    public var creditedModelIds: [String]

    public init(tradeId: String, symbol: String, pnl: Double, closedAt: Date, creditedModelIds: [String]) {
        self.tradeId = tradeId
        self.symbol = symbol
        self.pnl = pnl
        self.closedAt = closedAt
        self.creditedModelIds = creditedModelIds
    }

    public var isWin: Bool { pnl > 0 }
}

public final class CouncilPerformanceEngine {
    private var statsByModel: [String: ModelPerformanceStats]
    private var cfg: PerformanceWeightConfig
    private let store: ModelWeightStore

    public init(store: ModelWeightStore = ModelWeightStore(), cfg: PerformanceWeightConfig = PerformanceWeightConfig()) {
        self.store = store
        if let snap = store.load() {
            self.statsByModel = snap.statsByModel
            self.cfg = snap.cfg
        } else {
            self.statsByModel = [:]
            self.cfg = cfg
        }
    }

    public func getStats() -> [String: ModelPerformanceStats] { statsByModel }
    public func getConfig() -> PerformanceWeightConfig { cfg }

    public func setConfig(_ newCfg: PerformanceWeightConfig) {
        self.cfg = newCfg
        persist()
    }

    public func onTradeClosed(_ out: ClosedTradeOutcome) {
        for id in out.creditedModelIds {
            var s = statsByModel[id] ?? ModelPerformanceStats(modelId: id)
            s.update(win: out.isWin)
            statsByModel[id] = s
        }
        persist()
    }

    private func persist() {
        let snap = ModelWeightSnapshot(
            updatedAt: Date(),
            statsByModel: statsByModel,
            cfg: cfg
        )
        store.save(snap)
    }

    public func debugDumpTop(_ n: Int = 10) -> String {
        let items = statsByModel.values.sorted { a, b in
            let wa = PerformanceWeightCalculator.perfWeight(stats: a, cfg: cfg)
            let wb = PerformanceWeightCalculator.perfWeight(stats: b, cfg: cfg)
            return wa > wb
        }
        let top = items.prefix(n)
        var lines: [String] = []
        lines.append("ModelWeightStore: \(store.pathString())")
        for s in top {
            let w = PerformanceWeightCalculator.perfWeight(stats: s, cfg: cfg)
            lines.append("\(s.modelId)  emaP=\(String(format: "%.3f", s.emaP)) betaP=\(String(format: "%.3f", s.betaP)) n=\(s.evaluatedTrades) w=\(String(format: "%.3f", w))")
        }
        return lines.joined(separator: "\n")
    }
}
