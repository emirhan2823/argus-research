import XCTest
@testable import Algo_Trading

final class ArgusDecisionEngineTests: XCTestCase {
    
    var engine: ArgusDecisionEngine!
    
    override func setUp() {
        super.setUp()
        // Singleton is shared, but state is stateless mostly except internal logs?
        // Logic in makeDecision is pure function of inputs + context.
        engine = ArgusDecisionEngine.shared
    }
    
    // MARK: - Phase 2: Churn Tests
    
    func testCooldownBlock() {
        // Arrange
        let now = Date()
        let recentTradeTime = now.addingTimeInterval(-100) // 100 seconds ago (< 5 mins)
        let portfolioContext = (isInPosition: false, lastTradeTime: recentTradeTime, lastAction: SignalAction.sell)
        
        // Act: Strong Buy Score (80), but inside Cooldown
        let decision = engine.makeDecision(
            symbol: "TEST",
            assetType: .stock,
            atlas: 80, orion: 80, orionDetails: nil, aether: 50, hermes: 50, cronos: 50, athena: 50, phoenixAdvice: nil,
            traceContext: (100.0, 10.0),
            portfolioContext: portfolioContext
        )
        
        // Assert
        XCTAssertEqual(decision.finalActionCore, .hold, "Cooldown should block action.")
        XCTAssertTrue(decision.standardizedOutputs?.keys.contains("Orion") ?? false)
    }
    
    func testHysteresisBlock() {
        // Arrange
        let now = Date()
        let recentSellTime = now.addingTimeInterval(-600) // 10 mins ago (< 15 mins)
        // We sold recently. Trying to re-enter.
        let portfolioContext = (isInPosition: false, lastTradeTime: recentSellTime, lastAction: SignalAction.sell)
        
        // Act: Good Score (65), normally a Buy (>60). But Hysteresis requires 75.
        let decision = engine.makeDecision(
            symbol: "TEST",
            assetType: .stock,
            atlas: 65, orion: 65, orionDetails: nil, aether: 50, hermes: 50, cronos: 50, athena: 50, phoenixAdvice: nil,
            traceContext: (100.0, 10.0),
            portfolioContext: portfolioContext
        )
        
        // Assert
        XCTAssertEqual(decision.finalActionCore, .hold, "Hysteresis should block score 65 (Need 75).")
    }
    
    func testHysteresisPass() {
        // Arrange
        let now = Date()
        let recentSellTime = now.addingTimeInterval(-600)
        let portfolioContext = (isInPosition: false, lastTradeTime: recentSellTime, lastAction: SignalAction.sell)
        
        // Act: Super Score (80) > 75
        let decision = engine.makeDecision(
            symbol: "TEST",
            assetType: .stock,
            atlas: 80, orion: 80, orionDetails: nil, aether: 50, hermes: 50, cronos: 50, athena: 50, phoenixAdvice: nil,
            traceContext: (100.0, 10.0),
            portfolioContext: portfolioContext
        )
        
        // Assert
        XCTAssertEqual(decision.finalActionCore, .buy, "Hysteresis should allow score 80.")
    }
    
    // MARK: - Phase 3: Gating Tests
    
    func testRiskGate() {
        // Arrange
        // Orion Volatility 90 (Extreme Risk) -> Risk Score 10. Gate check is < 15.
        let components = OrionComponentScores(trend: 50, momentum: 50, volatility: 90, volume: 50, support: 50)
        let orionResult = OrionScoreResult(score: 70, components: components)
        
        // Act: Score 70 (Buy), but Volatility High
        let decision = engine.makeDecision(
            symbol: "TEST",
            assetType: .stock,
            atlas: 70, orion: 70, orionDetails: orionResult, aether: 50, hermes: 50, cronos: 50, athena: 50, phoenixAdvice: nil,
            traceContext: (100.0, 10.0)
        )
        
        // Assert
        XCTAssertEqual(decision.finalActionCore, .hold, "Risk Gate (Vol 90) should block Buy.")
    }
    
    // MARK: - Phase 4: Phoenix Override Tests
    
    func testPhoenixOverride() {
        // Arrange
        // Core Score Weak (40) -> SELL/HOLD
        // Phoenix Confidence 80 -> BUY
        let phoenix = PhoenixAdvice(
            id: UUID(), timestamp: Date(), symbol: "TEST", timeframe: .h1, status: .active,
            lookback: 100, regressionSlope: 0, channelUpper: 110, channelMid: 100, channelLower: 90, sigma: 2,
            entryZoneLow: 88, entryZoneHigh: 92, invalidationLevel: 85, targets: [],
            triggers: PhoenixAdvice.Triggers(touchLowerBand: true, rsiReversal: true, bullishDivergence: false, trendOk: false),
            confidence: 80, reasonShort: "Dip found", atr: 1.0
        )
        
        // Act
        let decision = engine.makeDecision(
            symbol: "TEST",
            assetType: .stock,
            atlas: 40, orion: 40, orionDetails: nil, aether: 40, hermes: 40, cronos: 40, athena: 40,
            phoenixAdvice: phoenix,
            traceContext: (100.0, 10.0) // Fresh data
        )
        
        // Assert
        XCTAssertEqual(decision.finalActionCore, .buy, "Phoenix should override weak Core Score.")
    }
}
