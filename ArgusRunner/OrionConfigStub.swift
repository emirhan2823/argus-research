import Foundation

// MARK: - Orion V2 Tuning Configuration
/// All tunable parameters for Orion V2 scoring and trading
struct OrionV2TuningConfig: Codable, Sendable {
    
    // MARK: - Component Weights (should sum to 1.0)
    var structureWeight: Double  // Default: 0.30
    var trendWeight: Double      // Default: 0.30
    var momentumWeight: Double   // Default: 0.25
    var patternWeight: Double    // Default: 0.10
    var volatilityWeight: Double // Default: 0.05
    
    // MARK: - Trading Thresholds
    var entryThreshold: Double   // Default: 70
    var exitThreshold: Double    // Default: 50
    var partialExitThreshold: Double // Default: 62
    
    // MARK: - Risk Parameters
    var stopLossPercent: Double  // Default: 5.0
    var takeProfitPercent: Double // Default: 15.0
    
    // MARK: - Metadata
    let updatedAt: Date
    let confidence: Double      // 0.0 - 1.0
    let reasoning: String       // Why these values were chosen
    let backtestWinRate: Double?
    let backtestReturn: Double?
    
    // MARK: - Defaults
    static var `default`: OrionV2TuningConfig {
        OrionV2TuningConfig(
            structureWeight: 0.30,
            trendWeight: 0.30,
            momentumWeight: 0.25,
            patternWeight: 0.10,
            volatilityWeight: 0.05,
            entryThreshold: 70,
            exitThreshold: 50,
            partialExitThreshold: 62,
            stopLossPercent: 5.0,
            takeProfitPercent: 15.0,
            updatedAt: Date(),
            confidence: 0.5,
            reasoning: "Varsayılan Orion V3 ağırlıkları",
            backtestWinRate: nil,
            backtestReturn: nil
        )
    }
    
    var weightsSummary: String {
        "S:\(Int(structureWeight * 100))% T:\(Int(trendWeight * 100))% M:\(Int(momentumWeight * 100))% P:\(Int(patternWeight * 100))% V:\(Int(volatilityWeight * 100))%"
    }
    
    var weightsTotal: Double {
        structureWeight + trendWeight + momentumWeight + patternWeight + volatilityWeight
    }
}

// MARK: - Orion V2 Tuning Store STUB (Non-Isolated)
class OrionV2TuningStore {
    static let shared = OrionV2TuningStore()
    
    // Stub just returns default config since we are in backtest/CLI mode
    func getConfig(symbol: String) -> OrionV2TuningConfig {
        return .default
    }
    
    func getGlobalConfig() -> OrionV2TuningConfig {
        return .default
    }
}
