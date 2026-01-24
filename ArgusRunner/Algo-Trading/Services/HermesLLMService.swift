import Foundation

/// Handles interaction with AI (Groq/LLaMA 3) for Hermes News Analysis
/// Migrated from Gemini to Groq for centralized reliability.
final class HermesLLMService: Sendable {
    static let shared = HermesLLMService()
    
    // Cache: Article ID -> Summary
    private var cache: [String: HermesSummary] = [:]
    
    private init() {
        // Load cache
        Task {
            if let loaded: [String: HermesSummary] = await ArgusDataStore.shared.load(key: "argus_hermes_cache") {
                self.cache = loaded
                print("🧠 Hermes: Loaded \(loaded.count) items from disk cache.")
            }
        }
    }
    
    /// Batched Analysis using Groq
    /// - Parameter isGeneral: Global feed için true geçin, sembol tespiti yapılır
    func analyzeBatch(_ articles: [NewsArticle], isGeneral: Bool = false) async throws -> [HermesSummary] {
        if articles.isEmpty { return [] }
        
        var results: [HermesSummary] = []
        var articlesToProcess: [NewsArticle] = []
        
        // 1. Check Cache
        for article in articles {
            if let cached = cache[article.id] {
                // Check if cache entry is fresh (e.g. within 24 hours)? 
                // Currently indefinite cache for immutable news analysis.
                results.append(cached)
            } else {
                articlesToProcess.append(article)
            }
        }
        
        if articlesToProcess.isEmpty {
            return results
        }
        
        print("🧠 Hermes: Processing \(articlesToProcess.count) new articles (Cached: \(results.count))")
        
        // 2. Prepare Prompt for MISSING articles
        // Limit to 3 articles per batch (pagination logic should handle rest)
        let chunkedArticles = Array(articlesToProcess.prefix(3))
        let promptText = buildBatchPrompt(chunkedArticles, isGeneral: isGeneral)
        
        let messages: [GroqClient.ChatMessage] = [
            .init(role: "system", content: "You are a financial news analyst JSON generator. Always output valid JSON matching the schema."),
            .init(role: "user", content: promptText)
        ]
        
        // 3. Request via GroqClient
        do {
            let responseDTO: HermesBatchResponse = try await GroqClient.shared.generateJSON(
                messages: messages
            )
            
            // 4. Map to Model & Update Cache
            let newSummaries = responseDTO.results.compactMap { (item: HermesBatchItem) -> HermesSummary? in
                let originalArticle = chunkedArticles.first(where: { $0.id == item.id })
                
                let resolvedSymbol: String
                if isGeneral, let detectedSymbol = item.detected_symbol, !detectedSymbol.isEmpty {
                    resolvedSymbol = detectedSymbol
                } else {
                    resolvedSymbol = originalArticle?.symbol ?? "MARKET"
                }
                
                var correctedScore = item.impact_score
                if let sentiment = item.sentiment?.uppercased() {
                    if sentiment == "POSITIVE" && correctedScore < 55 {
                        correctedScore = min(65.0, correctedScore + 10.0)
                    } else if sentiment == "NEGATIVE" && correctedScore > 45 {
                        correctedScore = max(35.0, correctedScore - 10.0)
                    } else if sentiment == "NEUTRAL" && (correctedScore > 55 || correctedScore < 45) {
                        correctedScore = 50.0
                    }
                }
                
                let summary = HermesSummary(
                    id: item.id,
                    symbol: resolvedSymbol,
                    summaryTR: item.summary_tr,
                    impactCommentTR: item.impact_comment_tr,
                    impactScore: Int(correctedScore),
                    relatedSectors: item.related_sectors,
                    rippleEffectScore: Int(item.ripple_effect_score),
                    createdAt: Date(),
                    mode: .full,
                    publishedAt: originalArticle?.publishedAt,
                    sourceReliability: originalArticle?.sourceReliability
                )
                
                // Save to Cache
                self.cache[item.id] = summary
                return summary
            }
            
            self.persistCache()
            
            results.append(contentsOf: newSummaries)
            return results
            
        } catch {
            print("❌ Hermes Analysis Failed: \(error)")
            // Return whatever we have from cache if API fails
            if !results.isEmpty { return results }
            
            let nsError = error as NSError
            if nsError.code == 429 {
                throw HermesError.quotaExhausted
            }
            throw error
        }
    }
    
    // MARK: - Hermes V2: Quick Sentiment (Cache-Based)
    
    /// Gets quick sentiment score for a symbol using cached Hermes analysis
    /// Returns a score from 0-100 (50 = neutral)
    /// - Parameter symbol: Stock symbol (e.g. "AAPL", "THYAO.IS")
    /// - Returns: HermesQuickSentiment with score and news count
    func getQuickSentiment(for symbol: String) async -> HermesQuickSentiment {
        // Get all cached summaries for this symbol
        let symbolSummaries = cache.values.filter { 
            $0.symbol.uppercased() == symbol.uppercased() ||
            $0.symbol.uppercased() == symbol.replacingOccurrences(of: ".IS", with: "").uppercased()
        }
        
        guard !symbolSummaries.isEmpty else {
            // No cached data - return neutral
            return HermesQuickSentiment(
                symbol: symbol,
                score: 50,
                bullishPercent: 50,
                bearishPercent: 50,
                newsCount: 0,
                source: .fallback,
                lastUpdated: Date()
            )
        }
        
        // Calculate average sentiment from cached summaries
        let totalScore = symbolSummaries.reduce(0.0) { $0 + Double($1.impactScore) }
        let avgScore = totalScore / Double(symbolSummaries.count)
        
        // Calculate bullish/bearish percentages
        let positiveCount = symbolSummaries.filter { $0.impactScore >= 55 }.count
        let negativeCount = symbolSummaries.filter { $0.impactScore <= 45 }.count
        let total = symbolSummaries.count
        
        let bullishPercent = Double(positiveCount) / Double(total) * 100
        let bearishPercent = Double(negativeCount) / Double(total) * 100
        
        return HermesQuickSentiment(
            symbol: symbol,
            score: avgScore,
            bullishPercent: bullishPercent,
            bearishPercent: bearishPercent,
            newsCount: symbolSummaries.count,
            source: .llm,
            lastUpdated: symbolSummaries.first?.createdAt ?? Date()
        )
    }
    
    /// Gets recent news summaries for a symbol from cache
    func getCachedSummaries(for symbol: String, count: Int = 5) -> [HermesSummary] {
        let symbolSummaries = cache.values.filter { 
            $0.symbol.uppercased() == symbol.uppercased() ||
            $0.symbol.uppercased() == symbol.replacingOccurrences(of: ".IS", with: "").uppercased()
        }
        .sorted { ($0.publishedAt ?? $0.createdAt) > ($1.publishedAt ?? $1.createdAt) }
        
        return Array(symbolSummaries.prefix(count))
    }
    
    /// Gets recent news with sentiment for a symbol (deprecated - use getCachedSummaries)
    func getNewsWithSentiment(for symbol: String, count: Int = 5) async -> [FinnhubSentimentNews] {
        // Finnhub API is not available - return empty
        // Use getCachedSummaries instead for cached Hermes analysis
        return []
    }
    
    private func persistCache() {
        let snapshot = self.cache
        Task {
            await ArgusDataStore.shared.save(snapshot, key: "argus_hermes_cache")
        }
    }
    
    private func buildBatchPrompt(_ articles: [NewsArticle], isGeneral: Bool = false) -> String {
        var articlesText = ""
        for (index, article) in articles.enumerated() {
            articlesText += """
            [NEWS \(index + 1)]
            ID: \(article.id)
            Symbol: \(article.symbol)
            Headline: \(article.headline)
            Summary: \(article.summary ?? "")
            
            """
        }
        
        // Global feed için ek talimat
        let symbolInstruction = isGeneral ? """
        
        ÖNEMLİ - SEMBOL TESPİTİ:
        Bu haberler genel piyasa haberleri. Her haber için:
        1. Haberde bahsedilen ANA şirketi/ticker'ı tespit et (örn: "Apple" → "AAPL", "Tesla" → "TSLA")
        2. Eğer haber birden fazla şirketi ilgilendiriyorsa, en çok etkilenen şirketi seç
        3. Eğer belirli bir şirket yoksa, sektörü belirle (örn: "Tech", "Energy", "Crypto")
        4. JSON'da "detected_symbol" alanına tespit ettiğin ticker'ı yaz
        
        """ : ""
        
        return """
        Sen Argus Terminal içindeki Hermes v2.3 modülüsün.
        Görevin aşağıdaki haberleri finansal ve BAĞLAMSAL açıdan analiz etmek.
        \(symbolInstruction)
        GİRDİ:
        \(articlesText)
        
        GÖREV:
        Her bir haber için analiz yap ve JSON üret.
        
        PUANLAMA KURALLARI (KESİN UYULMALI):
        - POSITIVE: 65 - 100 arası. (65 = Hafif Olumlu, 100 = Game Changer)
        - NEGATIVE: 0 - 35 arası. (0 = İflas/Kriz, 35 = Hafif Olumsuz)
        - NEUTRAL: 45 - 55 arası. (Piyasayı etkilemez)
        * Asla Sentiment ile Puan çelişmemeli (Örn: Positive deyip 40 verme).
        
        KURALLAR:
        1. summary_tr: Türkçe 1 cümlelik net özet.
        2. impact_comment_tr: "Hisse için [olumlu/olumsuz/nötr] bir gelişme." şeklinde 1 cümlelik yorum.
        3. sentiment: "POSITIVE", "NEGATIVE" veya "NEUTRAL" (BÜYÜK HARF).
        4. impact_score: Yukarıdaki aralıklara göre bir tamsayı.
        5. related_sectors: İngilizce sektör etiketleri (Örn: "Energy", "Tech").
        6. ripple_effect_score: Piyasaya yayılma potansiyeli (0-100).
        7. detected_symbol: Haberin ilgili olduğu ticker (örn: "AAPL", "TSLA"). Belirsizse boş bırak.
        
        ÇIKTI FORMATI (JSON OBJE):
        {
          "results": [
            {
              "id": "Haber ID'si aynen kopyalanmalı",
              "detected_symbol": "AAPL",
              "summary_tr": "...",
              "impact_comment_tr": "...",
              "sentiment": "POSITIVE",
              "impact_score": 75,
              "related_sectors": ["Sector1"],
              "ripple_effect_score": 60
            }
          ]
        }
        """
    }
}



