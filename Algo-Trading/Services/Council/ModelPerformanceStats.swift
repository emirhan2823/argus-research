import Foundation

/// Keeps rolling performance stats per model.
/// - EMA: fast adaptation
/// - Beta: bayesian smoothing for small samples
public struct ModelPerformanceStats: Codable, Sendable {
    public var modelId: String

    // EMA
    public var emaP: Double          // 0..1
    public var emaAlpha: Double      // e.g. 0.05

    // Beta(a,b)
    public var a: Double
    public var b: Double

    // Counts
    public var evaluatedTrades: Int

    public init(
        modelId: String,
        emaP: Double = 0.5,
        emaAlpha: Double = 0.05,
        a: Double = 1.0,
        b: Double = 1.0,
        evaluatedTrades: Int = 0
    ) {
        self.modelId = modelId
        self.emaP = emaP
        self.emaAlpha = emaAlpha
        self.a = a
        self.b = b
        self.evaluatedTrades = evaluatedTrades
    }

    public var betaP: Double {
        let denom = (a + b)
        if denom <= 0 { return 0.5 }
        return a / denom
    }

    /// Update stats with outcome: true=win, false=loss
    public mutating func update(win: Bool) {
        let y: Double = win ? 1.0 : 0.0
        emaP = (1.0 - emaAlpha) * emaP + emaAlpha * y

        if win { a += 1.0 } else { b += 1.0 }
        evaluatedTrades += 1
    }
}
