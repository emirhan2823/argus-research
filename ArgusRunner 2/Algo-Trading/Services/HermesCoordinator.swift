import Foundation

/// Main Coordinator for Hermes Integration.
/// Manages fetching news, checking cache, batching AI calls, and fallback to Lite mode.
final class HermesCoordinator: Sendable {
    static let shared = HermesCoordinator()
    
    private let cache = HermesCacheStore.shared
    private let llmService = HermesLLMService.shared
    
    // State
    private var isLiteMode = false
    
    // P2: Rate Limiting & Weighted Average states
    private var lastRequestTime: [String: Date] = [:]
    private let rateLimitSeconds: TimeInterval = 60 // 1 dakika
    
    private init() {}
    
    func getHermesSummaries(for symbol: String) async -> [HermesSummary] {
        return []
    }
    
    /// On-Demand Analysis (Triggered by UI)
    /// Fetches news and runs AI analysis, returning average score.
    func analyzeOnDemand(symbol: String) async -> Double? {
        // Rate Limit Check
        if let last = lastRequestTime[symbol], Date().timeIntervalSince(last) < rateLimitSeconds {
            print("⏳ Hermes Rate Limit: \(symbol) için bekleme süresi dolmadı.")
            return nil
        }
        lastRequestTime[symbol] = Date()
        
        // 1. Fetch News
        do {
            let articles = try await HeimdallOrchestrator.shared.requestNews(symbol: symbol, context: .interactive)
            
            // 2. Process with AI
            let summaries = await processNews(articles: articles, allowAI: true)
            
            if summaries.isEmpty { return nil }
            
            // 3. Calculated Weighted Score (P2 Feature)
            return calculateWeightedScore(summaries: summaries, articles: articles)
        } catch {
            print("❌ Hermes On-Demand Error: \(error)")
            return nil
        }
    }
    
    /// Main Entry Point
    /// - Parameter isGeneral: Global feed için true geçin
    func processNews(articles: [NewsArticle], allowAI: Bool = false, isGeneral: Bool = false) async -> [HermesSummary] {
        var finalSummaries: [HermesSummary] = []
        var articlesToProcess: [NewsArticle] = []
        
        // 1. Check Cache
        for article in articles {
            if let cached = cache.getSummary(for: article.id) {
                // If we want to upgrade Lite to AI, we should check allowAI and cached.mode
                if allowAI && cached.mode == .lite {
                    articlesToProcess.append(article) // Re-process
                } else {
                    finalSummaries.append(cached)
                }
            } else {
                articlesToProcess.append(article)
            }
        }
        
        if articlesToProcess.isEmpty {
            return finalSummaries.sorted { $0.createdAt > $1.createdAt }
        }
        
        // 2. Decide Mode (Full vs Lite)
        if isLiteMode || !allowAI {
            // Skip AI. Per user request, we DO NOT fall back to Lite heuristics.
            // Only return already cached AI summaries (if any).
            // We do not save or generate Lite summaries anymore.
        } else {
            // Try Batch AI
            do {
                let batchedResults = try await llmService.analyzeBatch(articlesToProcess, isGeneral: isGeneral)
                finalSummaries.append(contentsOf: batchedResults)
                cache.saveSummaries(batchedResults)
            } catch {
                print("Hermes AI Error: \(error)")
                if case HermesError.quotaExhausted = error {
                    print("⚠️ Quota exhausted. Switching to Lite mode.")
                    // V2.3 FIX: Fallback to Lite mode instead of returning empty
                    isLiteMode = true
                }
                
                // V2.3 FIX: Fallback etkinleştirildi - Lite mode kullan
                let liteResults = runLiteMode(articles: articlesToProcess)
                finalSummaries.append(contentsOf: liteResults)
                cache.saveSummaries(liteResults)
            }
        }
        
        return finalSummaries.sorted { $0.createdAt > $1.createdAt }
    }
    
    // MARK: - Lite Mode Logic
    private func runLiteMode(articles: [NewsArticle]) -> [HermesSummary] {
        return articles.map { article in
            let text = (article.headline + " " + (article.summary ?? "")).lowercased()
            
            // Heuristics
            let positives = ["beats", "record", "all time high", "raises guidance", "strong demand", "profit", "up", "gain", "buy", "rekor", "kar", "büyüme"]
            let negatives = ["misses", "profit warning", "investigation", "downgrade", "cut", "loss", "down", "sell", "zarar", "düşüş", "kriz"]
            
            var score = 50
            var positiveCount = 0
            var negativeCount = 0
            
            for word in positives { if text.contains(word) { positiveCount += 1 } }
            for word in negatives { if text.contains(word) { negativeCount += 1 } }
            
            if positiveCount > negativeCount {
                score = Int.random(in: 60...80)
            } else if negativeCount > positiveCount {
                score = Int.random(in: 20...40)
            }
            
            // Messages
            let comment: String
            if score >= 60 { comment = "Hisse için kısa vadede olumlu bir haber (Lite Analiz)." }
            else if score <= 40 { comment = "Hisse için kısa vadede baskı oluşturabilecek olumsuz bir haber (Lite Analiz)." }
            else { comment = "Kısa vadede nötr bir haber (Lite Analiz)." }
            
            return HermesSummary(
                id: article.id,
                symbol: article.symbol,
                summaryTR: article.headline, // Lite mode uses headline as summary
                impactCommentTR: comment,
                impactScore: score,
                createdAt: Date(),
                mode: .lite,
                publishedAt: article.publishedAt,
                sourceReliability: article.sourceReliability
            )
        }
    }
    
    // Helper to get current mode
    func getCurrentMode() -> HermesMode {
        return isLiteMode ? .lite : .full
    }
    
    // P2: Public Accessor for Argus Engine
    func getStoredWeightedScore(for symbol: String) -> Double? {
        let summaries = cache.getSummaries(for: symbol)
        if summaries.isEmpty { return nil }
        // Calculate based on cached metadata
        return calculateWeightedScore(summaries: summaries, articles: [])
    }

    func resetQuota() {
        self.isLiteMode = false
    }
    
    // MARK: - Weighted Average Logic (Hermes P2)
    
    private func calculateWeightedScore(summaries: [HermesSummary], articles: [NewsArticle]) -> Double {
        var totalWeightedScore = 0.0
        var totalWeight = 0.0
        let now = Date()
        
        // Map for O(1) fallback access
        let articleMap = Dictionary(uniqueKeysWithValues: articles.map { ($0.id, $0) })
        
        for summary in summaries {
            // Priority: Summary Fields (New Cache) > Article Map (Fallback)
            var pDate: Date? = summary.publishedAt
            var sRel: Double? = summary.sourceReliability
            
            if pDate == nil || sRel == nil {
                if let article = articleMap[summary.id] {
                    pDate = article.publishedAt
                    sRel = article.sourceReliability
                }
            }
            
            // Defaults
            let publishedAt = pDate ?? now
            let sourceReliability = sRel ?? 0.5
            
            // 1. Time Decay (Half-Life: 24h)
            let hoursOld = max(0, now.timeIntervalSince(publishedAt) / 3600.0)
            let timeWeight = 1.0 / (1.0 + (hoursOld / 24.0))
            
            // 2. Source Reliability
            // Time is dominant, Source is modifier (min 0.4 impact)
            let finalWeight = timeWeight * (0.4 + (sourceReliability * 0.6))
            
            totalWeightedScore += Double(summary.impactScore) * finalWeight
            totalWeight += finalWeight
        }
        
        guard totalWeight > 0 else { return 50.0 }
        return totalWeightedScore / totalWeight
    }
}
