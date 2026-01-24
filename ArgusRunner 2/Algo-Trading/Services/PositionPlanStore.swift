import Foundation
import Combine

// MARK: - Position Plan Store
/// Pozisyon planlarını yöneten ve persist eden store

class PositionPlanStore: ObservableObject {
    static let shared = PositionPlanStore()
    
    @Published private(set) var plans: [UUID: PositionPlan] = [:]  // tradeId -> plan
    
    private let persistenceKey = "ArgusPositionPlansVortex" // New Key for V2
    
    private init() {
        loadPlans()
    }
    
    // MARK: - Sync with Portfolio
    
    /// Mevcut açık trade'ler için eksik planları oluştur
    func syncWithPortfolio(trades: [Trade], grandDecisions: [String: ArgusGrandDecision]) {
        let openTrades = trades.filter { $0.isOpen }
        var createdCount = 0
        
        for trade in openTrades {
            // Plan zaten varsa atla
            if hasPlan(for: trade.id) { continue }
            
            // Varsayılan karar oluştur
            let decision: ArgusGrandDecision
            if let gd = grandDecisions[trade.symbol] {
                decision = gd
            } else {
                // Varsayılan accumulate kararı
                decision = ArgusGrandDecision(
                    id: UUID(),
                    symbol: trade.symbol,
                    action: .accumulate,
                    strength: .normal,
                    confidence: 0.5,
                    reasoning: "Mevcut pozisyon için varsayılan plan",
                    contributors: [],
                    vetoes: [],
                    orionDecision: CouncilDecision(
                        symbol: trade.symbol,
                        action: .hold,
                        netSupport: 0.5,
                        approveWeight: 0,
                        vetoWeight: 0,
                        isStrongSignal: false,
                        isWeakSignal: false,
                        winningProposal: nil,
                        allProposals: [],
                        votes: [],
                        vetoReasons: [],
                        timestamp: Date()
                    ),
                    atlasDecision: nil,
                    aetherDecision: AetherDecision(
                        stance: .cautious,
                        marketMode: .neutral,
                        netSupport: 0.5,
                        isStrongSignal: false,
                        winningProposal: nil,
                        votes: [],
                        warnings: [],
                        timestamp: Date()
                    ),
                    hermesDecision: nil,
                    orionDetails: nil,
                    financialDetails: nil,
                    bistDetails: nil,
                    patterns: nil,
                    timestamp: Date()
                )
            }
            
            createPlan(for: trade, decision: decision)
            createdCount += 1
        }
        
        if createdCount > 0 {
            print("📋 \(createdCount) mevcut trade için plan oluşturuldu")
        }
    }
    
    // MARK: - Public API
    
    /// Trade için plan var mı?
    func hasPlan(for tradeId: UUID) -> Bool {
        return plans[tradeId] != nil
    }
    
    /// Trade için plan getir
    func getPlan(for tradeId: UUID) -> PositionPlan? {
        return plans[tradeId]
    }
    
    /// Yeni plan oluştur
    @discardableResult
    func createPlan(
        for trade: Trade,
        decision: ArgusGrandDecision,
        thesis: String? = nil
    ) -> PositionPlan {
        // 1. Create Snapshot from Decision
        // OrionScoreResult uses 'score' (0-100)
        let orionScore = decision.orionDecision.netSupport * 100 // Use netSupport (0-1) and convert to 0-100
        let atlasScore = 50.0 // Default
        
        // Varsayılan tez
        let defaultThesis = generateThesis(for: trade.symbol, decision: decision)
        let defaultInvalidation = generateInvalidation(for: trade.symbol, decision: decision)
        let finalThesis = thesis ?? defaultThesis
        
        let techData = TechnicalSnapshotData(
            rsi: nil, // Metrics not available in OrionScoreResult directly
            atr: nil,
            sma20: nil, sma50: nil, sma200: nil, distanceFromATH: nil, distanceFrom52WeekLow: nil, nearestSupport: nil, nearestResistance: nil, trend: nil
        )
        
        let snapshot = EntrySnapshot(
            tradeId: trade.id,
            symbol: trade.symbol,
            entryPrice: trade.entryPrice,
            grandDecision: decision,
            orionScore: orionScore,
            atlasScore: atlasScore,
            technicalData: techData,
            macroData: nil,
            fundamentalData: nil
        )
        
        // 2. Delegate to Vortex Engine
        let plan = VortexEngine.shared.createPlan(for: trade, snapshot: snapshot, decision: decision, thesis: finalThesis, invalidation: defaultInvalidation)
        
        plans[trade.id] = plan
        savePlans()
        
        print("📋 Yeni VORTEX planı oluşturuldu: \(trade.symbol)")
        return plan
    }
    
    /// Planı güncelle
    func updatePlan(_ plan: PositionPlan) {
        var updatedPlan = plan
        updatedPlan.lastUpdated = Date()
        plans[plan.tradeId] = updatedPlan
        savePlans()
    }
    
    /// Adımı tamamlandı olarak işaretle
    func markStepCompleted(tradeId: UUID, stepId: UUID) {
        guard var plan = plans[tradeId] else { return }
        
        if !plan.executedSteps.contains(stepId) {
            plan.executedSteps.append(stepId)
            plan.lastUpdated = Date()
            plans[tradeId] = plan
            savePlans()
            
            print("✅ Plan adımı tamamlandı: \(plan.originalSnapshot.symbol) - Step \(stepId.uuidString.prefix(8))")
        }
    }
    
    /// Plan durumunu güncelle
    func updatePlanStatus(tradeId: UUID, status: PlanStatus) {
        guard var plan = plans[tradeId] else { return }
        plan.status = status
        plan.lastUpdated = Date()
        plans[tradeId] = plan
        savePlans()
    }
    
    /// Trade kapatıldığında planı tamamla
    func completePlan(tradeId: UUID) {
        updatePlanStatus(tradeId: tradeId, status: .completed)
    }
    
    // MARK: - Trigger Checking
    
    /// Tetiklenen aksiyonu bul
    func checkTriggers(
        trade: Trade,
        currentPrice: Double,
        grandDecision: ArgusGrandDecision?
    ) -> PlannedAction? {
        guard let plan = plans[trade.id], plan.isActive else { return nil }
        
        // PnL hesapla
        // Use Original Snapshot Entry Price
        let entryPrice = plan.originalSnapshot.entryPrice
        let pnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100
        let daysHeld = Calendar.current.dateComponents([.day], from: plan.dateCreated, to: Date()).day ?? 0
        
        // Iterate ALL scenarios (Bullish, Bearish, Neutral)
        let activeScenarios = [plan.bullishScenario, plan.bearishScenario, plan.neutralScenario].compactMap { $0 }.filter { $0.isActive }
        
        for scenario in activeScenarios {
            for step in scenario.steps {
                // ÖNCE: Bu adım zaten tamamlandı mı kontrol et
                if plan.executedSteps.contains(step.id) {
                    continue // ATLA - tekrar tetikleme
                }
                
                let triggered = checkTrigger(
                    trigger: step.trigger,
                    currentPrice: currentPrice,
                    entryPrice: entryPrice,
                    pnlPercent: pnlPercent,
                    daysHeld: daysHeld,
                    grandDecision: grandDecision
                )
                
                if triggered {
                    print("🎯 Tetiklendi: \(plan.originalSnapshot.symbol) - \(step.description)")
                    return step
                }
            }
        }
        
        return nil
    }
    
    private func checkTrigger(
        trigger: ActionTrigger,
        currentPrice: Double,
        entryPrice: Double,
        pnlPercent: Double,
        daysHeld: Int,
        grandDecision: ArgusGrandDecision?
    ) -> Bool {
        switch trigger {
        // BASIC
        case .priceAbove(let target):
            return currentPrice > target
            
        case .priceBelow(let target):
            return currentPrice < target
            
        case .gainPercent(let target):
            return pnlPercent >= target
            
        case .lossPercent(let target):
            return pnlPercent <= -target
            
        case .daysElapsed(let days):
            return daysHeld >= days
            
        case .councilSignal(let signal):
            guard let gd = grandDecision else { return false }
            switch signal {
            case .trim: return gd.action == .trim
            case .liquidate: return gd.action == .liquidate
            case .accumulate: return gd.action == .accumulate
            case .aggressive: return gd.action == .aggressiveBuy
            }
            
        case .priceAndTime(let price, let days):
            return currentPrice >= price && daysHeld <= days
            
        // ADVANCED - Fiyat bazlı
        case .priceAboveEntry(let percent):
            return pnlPercent >= percent
            
        case .priceBelowEntry(let percent):
            return pnlPercent <= -percent
            
        // ADVANCED - Zaman bazlı
        case .maxHoldingDays(let days):
            return daysHeld >= days
            
        case .daysWithoutProgress(let days, let minGain):
            // X gün geçti ve kâr minGain altında
            return daysHeld >= days && pnlPercent < minGain
            
        // ADVANCED - Bu tetikleyiciler daha fazla veri gerektirir (snapshot, vb.)
        // Şimdilik false dönüyoruz, Delta Tracker ile implemente edilecek
        case .trailingStop, .atrMultiple, .entryAtrStop:
            // Trailing stop mantığı TrailingStopManager'da ele alınacak
            return false
            
        case .rsiOverbought, .rsiOversold, .crossBelow, .crossAbove:
            // Teknik göstergeler anlık hesaplanmalı
            return false
            
        case .earningsWithin(let days):
            // EventCalendarService ile kontrol edilmeli
            let check = EventCalendarService.shared.hasEarningsWithin(symbol: grandDecision?.symbol ?? "", days: days)
            return check.hasEarnings
            
        case .councilActionChanged, .councilConfidenceDropped, .orionScoreDropped, .deltaExceeds:
            // Delta Tracker ile kontrol edilecek
            return false
            
        case .marketModeChanged, .vixAbove, .vixBelow, .spyDropped:
            // Piyasa verileri gerekli
            return false
        }
    }
    
    // MARK: - Thesis Generation
    
    private func generateThesis(for symbol: String, decision: ArgusGrandDecision) -> String {
        let actionText: String
        switch decision.action {
        case .aggressiveBuy: actionText = "Güçlü alım sinyali"
        case .accumulate: actionText = "Kademeli birikim"
        case .trim: actionText = "Azaltma"
        case .liquidate: actionText = "Çıkış"
        case .neutral: actionText = "Nötr bekleme"
        }
        
        return "\(actionText). \(decision.reasoning)"
    }
    
    private func generateInvalidation(for symbol: String, decision: ArgusGrandDecision) -> String {
        switch decision.action {
        case .aggressiveBuy, .accumulate:
            return "Konsey AZALT veya ÇIK sinyali verirse, ya da -%10 stop tetiklenirse"
        default:
            return "Beklenmedik negatif gelişme"
        }
    }
    
    // MARK: - Persistence
    
    private func savePlans() {
        do {
            let data = try JSONEncoder().encode(Array(plans.values))
            UserDefaults.standard.set(data, forKey: persistenceKey)
        } catch {
            print("❌ Plan kaydetme hatası: \(error)")
        }
    }
    
    private func loadPlans() {
        guard let data = UserDefaults.standard.data(forKey: persistenceKey) else { return }
        
        do {
            let loadedPlans = try JSONDecoder().decode([PositionPlan].self, from: data)
            for plan in loadedPlans {
                plans[plan.tradeId] = plan
            }
            print("📋 \(loadedPlans.count) plan yüklendi")
        } catch {
            print("❌ Plan yükleme hatası: \(error)")
        }
    }
    
    // MARK: - Debug
    
    func printPlanSummary(for tradeId: UUID) {
        guard let plan = plans[tradeId] else {
            print("❌ Plan bulunamadı: \(tradeId)")
            return
        }
        
        print("═══════════════════════════════════════")
        print("📋 POZİSYON PLANI: \(plan.originalSnapshot.symbol)")
        print("═══════════════════════════════════════")
        print("Tez: \(plan.thesis)")
        print("Giriş: \(String(format: "%.2f", plan.originalSnapshot.entryPrice)) @ \(plan.originalSnapshot.capturedAt.formatted())")
        print("Miktar: \(String(format: "%.2f", plan.initialQuantity))")
        // print("Durum: \(plan.status.rawValue)") // Optional if status enum exists
        print("Niyet: \(plan.intent.rawValue)")
        print("───────────────────────────────────────")
        
        let scenarios = [plan.bullishScenario, plan.bearishScenario, plan.neutralScenario].compactMap { $0 }
        
        for scenario in scenarios {
            print("\(scenario.type.rawValue) (\(scenario.isActive ? "AKTİF" : "PASİF")):")
            for step in scenario.steps {
                let completed = plan.executedSteps.contains(step.id) ? "✅" : "⏳"
                print("  \(completed) \(step.trigger.displayText) → \(step.action.displayText)")
            }
        }
        print("═══════════════════════════════════════")
        if !plan.journeyLog.isEmpty {
            print("📜 PLAN GEÇMİŞİ:")
            for rev in plan.journeyLog {
                print("  - \(rev.timestamp.formatted()): \(rev.changeDescription) (\(rev.reason))")
            }
            print("═══════════════════════════════════════")
        }
    }
}
