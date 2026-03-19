import Foundation

public enum PerformanceMode: String, Codable, Sendable {
    case emaOnly
    case betaOnly
    case hybridGeometric   // sqrt(ema * beta)
    case hybridWeighted    // λ*ema + (1-λ)*beta
}

public struct PerformanceWeightConfig: Codable, Sendable {
    public var mode: PerformanceMode = .hybridGeometric

    /// Map probabilities (0..1) into weight range [minW..maxW]
    public var minW: Double = 0.1
    public var maxW: Double = 2.0

    /// Hybrid weighted mean lambda
    public var lambda: Double = 0.5

    /// Safety: avoid big boosts with tiny sample sizes
    public var minTradesForFullBoost: Int = 20

    public init() {}
}

public enum PerformanceWeightCalculator {
    public static func clamp(_ x: Double, _ lo: Double, _ hi: Double) -> Double {
        return min(max(x, lo), hi)
    }

    /// Convert p in [0..1] -> w in [minW..maxW]
    public static func mapPtoW(p: Double, cfg: PerformanceWeightConfig) -> Double {
        let pClamped = clamp(p, 0.0, 1.0)
        // linear map: minW + (maxW-minW)*p
        return clamp(cfg.minW + (cfg.maxW - cfg.minW) * pClamped, cfg.minW, cfg.maxW)
    }

    public static func perfWeight(stats: ModelPerformanceStats, cfg: PerformanceWeightConfig) -> Double {
        let wEMA = mapPtoW(p: stats.emaP, cfg: cfg)
        let wBETA = mapPtoW(p: stats.betaP, cfg: cfg)

        let raw: Double
        switch cfg.mode {
        case .emaOnly:
            raw = wEMA
        case .betaOnly:
            raw = wBETA
        case .hybridGeometric:
            raw = sqrt(wEMA * wBETA)
        case .hybridWeighted:
            let λ = clamp(cfg.lambda, 0.0, 1.0)
            raw = λ * wEMA + (1.0 - λ) * wBETA
        }

        // Sample-size blend: below threshold, pull toward 1.0
        let n = stats.evaluatedTrades
        if cfg.minTradesForFullBoost <= 0 { return raw }

        let blend = clamp(Double(n) / Double(cfg.minTradesForFullBoost), 0.0, 1.0)
        return (1.0 - blend) * 1.0 + blend * raw
    }
}
