import Foundation

// MARK: - Aether Council Protocol & Models
// The Macro Council - evaluates market conditions and macro environment

// MARK: - Macro Council Member Protocol

protocol MacroCouncilMember: Sendable {
    var id: String { get }
    var name: String { get }
    
    func analyze(macro: MacroSnapshot) async -> MacroProposal?
    func vote(on proposal: MacroProposal, macro: MacroSnapshot) -> MacroVote
}

// MARK: - Macro Snapshot

struct MacroSnapshot: Sendable, Codable {
    let timestamp: Date
    
    // Market Sentiment
    let vix: Double?                    // Fear index
    let fearGreedIndex: Double?         // CNN Fear & Greed (0-100)
    let putCallRatio: Double?
    
    // Fed & Rates
    let fedFundsRate: Double?
    let tenYearYield: Double?
    let twoYearYield: Double?
    let yieldCurveInverted: Bool
    
    // Market Breadth
    let advanceDeclineRatio: Double?    // NYSE A/D
    let percentAbove200MA: Double?      // % of stocks above 200MA
    let newHighsNewLows: Double?        // NH-NL difference
    
    // Economic
    let gdpGrowth: Double?
    let unemploymentRate: Double?
    let inflationRate: Double?
    let consumerConfidence: Double?
    
    // Sector
    let sectorRotation: SectorRotationPhase?
    let leadingSectors: [String]
    let laggingSectors: [String]
    
    // Market Mode
    var marketMode: MarketMode {
        if let vix = vix {
            if vix > 30 { return .panic }
            if vix > 20 { return .fear }
            if vix < 12 { return .complacency }
        }
        if let fg = fearGreedIndex {
            if fg < 25 { return .extremeFear }
            if fg > 75 { return .extremeGreed }
        }
        return .neutral
    }
    
    static let empty = MacroSnapshot(
        timestamp: Date(),
        vix: nil, fearGreedIndex: nil, putCallRatio: nil,
        fedFundsRate: nil, tenYearYield: nil, twoYearYield: nil, yieldCurveInverted: false,
        advanceDeclineRatio: nil, percentAbove200MA: nil, newHighsNewLows: nil,
        gdpGrowth: nil, unemploymentRate: nil, inflationRate: nil, consumerConfidence: nil,
        sectorRotation: nil, leadingSectors: [], laggingSectors: []
    )
    
    /// Build MacroSnapshot from cached MacroRegimeService data
    static func fromCached() -> MacroSnapshot {
        // Get VIX from MacroRegimeService cache
        let vixValue = MacroRegimeService.shared.getCurrentVix()
        
        // Get cached rating for more data
        let cachedRating = MacroRegimeService.shared.getCachedRating()
        
        return MacroSnapshot(
            timestamp: Date(),
            vix: vixValue,
            fearGreedIndex: nil, // Not tracked separately
            putCallRatio: nil,
            fedFundsRate: nil,
            tenYearYield: nil,
            twoYearYield: nil,
            yieldCurveInverted: (cachedRating?.interestRateScore ?? 50) < 40, // Low rate score = inverted
            advanceDeclineRatio: nil,
            percentAbove200MA: nil,
            newHighsNewLows: nil,
            gdpGrowth: nil,
            unemploymentRate: cachedRating?.laborScore.map { 10 - ($0 / 10) }, // Inverse: high score = low unemployment
            inflationRate: cachedRating?.inflationScore.map { (100 - $0) / 10 }, // Inverse: high score = low inflation
            consumerConfidence: nil,
            sectorRotation: nil,
            leadingSectors: [],
            laggingSectors: []
        )
    }
}

enum MarketMode: String, Sendable, Codable {
    case panic = "PANİK"
    case extremeFear = "AŞIRI KORKU"
    case fear = "KORKU"
    case neutral = "NÖTR"
    case greed = "AÇGÖZLÜLÜK"
    case extremeGreed = "AŞIRI AÇGÖZLÜLÜK"
    case complacency = "REHAVET"
}

enum SectorRotationPhase: String, Codable, Sendable {
    case earlyExpansion = "Erken Genişleme"     // Financials, Tech lead
    case lateExpansion = "Geç Genişleme"        // Energy, Materials lead
    case earlyRecession = "Erken Resesyon"      // Utilities, Healthcare lead
    case lateRecession = "Geç Resesyon"         // Consumer Staples lead
}

// MARK: - Macro Proposal

struct MacroProposal: Sendable, Identifiable, Codable {
    let id = UUID()
    let proposer: String
    let proposerName: String
    let stance: MacroStance
    let confidence: Double
    let reasoning: String
    let timestamp: Date = Date()
}

enum MacroStance: String, Sendable, Codable {
    case riskOn = "RİSK AL"
    case cautious = "DİKKATLİ"
    case defensive = "SAVUN"
    case riskOff = "RİSK KAPAT"
    
    var emoji: String {
        switch self {
        case .riskOn: return "🟢"
        case .cautious: return "🟡"
        case .defensive: return "🟠"
        case .riskOff: return "🔴"
        }
    }
}

// MARK: - Macro Vote

struct MacroVote: Sendable, Codable {
    let voter: String
    let voterName: String
    let decision: VoteDecision
    let reasoning: String?
    let weight: Double
}

// MARK: - Aether Decision

struct AetherDecision: Sendable, Codable {
    let stance: MacroStance
    let marketMode: MarketMode
    let netSupport: Double
    let isStrongSignal: Bool
    let winningProposal: MacroProposal?
    let votes: [MacroVote]
    let warnings: [String]
    let timestamp: Date
    
    /// Should we block all buys?
    var blockBuys: Bool {
        stance == .riskOff || stance == .defensive
    }
    
    /// Position size multiplier (0.0 - 1.0)
    var positionMultiplier: Double {
        switch stance {
        case .riskOn: return 1.0
        case .cautious: return 0.7
        case .defensive: return 0.4
        case .riskOff: return 0.0
        }
    }
    
    var summary: String {
        "Makro: \(stance.rawValue) | Mod: \(marketMode.rawValue) | Destek: \(String(format: "%.0f", netSupport * 100))%"
    }
}

// MARK: - Aether Member Weights

struct AetherMemberWeights: Codable, Sendable {
    var fedMaster: Double
    var sentimentMaster: Double
    var sectorMaster: Double
    var cycleMaster: Double
    var correlationMaster: Double
    var updatedAt: Date
    var confidence: Double
    
    static let defaultWeights = AetherMemberWeights(
        fedMaster: 0.25,
        sentimentMaster: 0.25,
        sectorMaster: 0.20,
        cycleMaster: 0.15,
        correlationMaster: 0.15,
        updatedAt: Date(),
        confidence: 0.5
    )
    
    func weight(for memberId: String) -> Double {
        switch memberId {
        case "fed_master": return fedMaster
        case "sentiment_master": return sentimentMaster
        case "sector_master": return sectorMaster
        case "cycle_master": return cycleMaster
        case "correlation_master": return correlationMaster
        default: return 0.1
        }
    }
}
