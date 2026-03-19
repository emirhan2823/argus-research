import Foundation

public enum Direction: Int, Codable, Sendable {
    case sell = -1
    case none = 0
    case buy  = 1
}

public struct ModelVote: Codable, Sendable {
    public var modelId: String

    /// BUY/SELL/NONE -> +1/-1/0
    public var dir: Direction

    /// model’s own confidence 0..1 (if unknown use 0.5)
    public var modelConf: Double

    /// extra runtime trust 0..1 (data quality / regime / conflict penalty)
    public var trust: Double

    /// baseWeight, start 0.1
    public var baseWeight: Double

    public init(
        modelId: String,
        dir: Direction,
        modelConf: Double,
        trust: Double = 1.0,
        baseWeight: Double = 0.1
    ) {
        self.modelId = modelId
        self.dir = dir
        self.modelConf = modelConf
        self.trust = trust
        self.baseWeight = baseWeight
    }
}

public struct EnsembleDecision: Codable, Sendable {
    public var finalDir: Direction
    public var finalConfidence: Double   // 0..1
    public var score: Double             // signed
    public var weightsUsed: [String: Double]
}

public enum CouncilAggregator {

    public static func decide(
        votes: [ModelVote],
        statsByModel: [String: ModelPerformanceStats],
        perfCfg: PerformanceWeightConfig,
        minAbsScoreToAct: Double = 0.15
    ) -> EnsembleDecision {

        var weightsUsed: [String: Double] = [:]
        var S: Double = 0.0
        var den: Double = 0.0

        for v in votes {
            let stats = statsByModel[v.modelId] ?? ModelPerformanceStats(modelId: v.modelId)
            let perfW = PerformanceWeightCalculator.perfWeight(stats: stats, cfg: perfCfg)

            let baseW = max(0.0, v.baseWeight)
            let trust = PerformanceWeightCalculator.clamp(v.trust, 0.0, 1.0)
            let mconf = PerformanceWeightCalculator.clamp(v.modelConf, 0.0, 1.0)

            let w = baseW * trust * perfW
            weightsUsed[v.modelId] = w

            let voteVal = Double(v.dir.rawValue)
            S += w * mconf * voteVal
            den += w * mconf
        }

        let finalConf: Double = (den <= 0.0)
            ? 0.0
            : PerformanceWeightCalculator.clamp(abs(S) / den, 0.0, 1.0)

        let finalDir: Direction
        if abs(S) < minAbsScoreToAct {
            finalDir = .none
        } else {
            finalDir = (S > 0) ? .buy : .sell
        }

        return EnsembleDecision(
            finalDir: finalDir,
            finalConfidence: finalConf,
            score: S,
            weightsUsed: weightsUsed
        )
    }
}
