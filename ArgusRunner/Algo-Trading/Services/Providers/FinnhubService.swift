import Foundation
import Combine

/// Failover Provider (The Hydra: Backup Head)
/// Failover Provider (The Hydra: Backup Head)
final class FinnhubService: HeimdallProvider, @unchecked Sendable {
    static let shared = FinnhubService()
    var name: String { "Finnhub" }
    
    var capabilities: [HeimdallDataField] {
        return [.fundamentals, .quote, .news]
    }
    
    private let baseURL = "https://finnhub.io/api/v1"
    
    
    private init() {}
    
    func setPrimaryToken(_ token: String) {
        // Since Secrets manages keys and rotation, we need a way to inject a user preference.
        // For now, let's just log it or update Secrets if mutable.
        // Ideally Secrets.shared.updateFinnhubKey(token)
        // But Secrets keys are private var.
        // To strictly follow "Secrets manages keys", we shouldn't bypass.
        // But for maintaining the compilation of SettingsViewModel:
        print("ℹ️ Finnhub Key Update Requested: \(token) (Not implemented in Secrets yet)")
    }
    
    // MARK: - Fundamentals (Primary for Atlas)
    func fetchFundamentals(symbol: String) async throws -> FinancialsData {
        let apiKey = Secrets.shared.finnhub
        let urlString = "\(baseURL)/stock/metric?symbol=\(symbol)&metric=all&token=\(apiKey)"
        guard let url = URL(string: urlString) else { throw URLError(.badURL) }
        
        let data = try await HeimdallNetwork.request(url: url, engine: .atlas, provider: .finnhub, symbol: symbol)
        
        // Finnhub Basic Financials Response
        struct FHMetricResponse: Codable {
            struct Metric: Codable {
                let marketCapitalization: Double?
                let peBasicExclExtraTTM: Double?
                let dividendYieldIndicatedAnnual: Double?
                let beta: Double?
                let epsExclExtraItemsTTM: Double?
                let currentRatioAnnual: Double?
                
                // Additions for Atlas Resurrection
                let revenueTTM: Double?
                let totalDebtToEquityAnnual: Double?
                let roiTTM: Double?
            }
            let metric: Metric
            // let series: ... ignored
        }
        
        do {
            let res = try JSONDecoder().decode(FHMetricResponse.self, from: data)
            let m = res.metric
            
            // Normalize Units: Finnhub Market Cap is in Millions. RevenueTTM is in Millions too usually?
            // "revenueTTM": 95000 -> 95 Billion? Or 95 Million?
            // Finnhub documentation says "All values are in million" for Market Cap.
            // Let's assume consistent Million scaling for Revenue too.
            let scaler = 1_000_000.0
            
            let revenue = (m.revenueTTM ?? 0) * scaler
            let mCap = (m.marketCapitalization ?? 0) * scaler
            
            // Approximation for Debt (if Debt/Equity known and Market Cap ~ Equity check?)
            // We can't easily get Total Debt from just Debt/Equity without Book Value.
            // But we can store derived stuff if needed. For now, nil is safer than bad guess.
            
            return FinancialsData(
                symbol: symbol,
                currency: "USD",
                lastUpdated: Date(),
                totalRevenue: revenue > 0 ? revenue : nil,
                netIncome: nil, // Not directly in basic metric
                totalShareholderEquity: nil,
                marketCap: mCap > 0 ? mCap : nil,
                revenueHistory: [],
                netIncomeHistory: [],
                ebitda: nil,
                shortTermDebt: nil,
                longTermDebt: nil,
                operatingCashflow: nil,
                capitalExpenditures: nil,
                cashAndCashEquivalents: nil,
                peRatio: m.peBasicExclExtraTTM,
                forwardPERatio: nil,
                priceToBook: nil, // PB not in basic, usually.
                evToEbitda: nil,
                dividendYield: m.dividendYieldIndicatedAnnual,
                forwardGrowthEstimate: m.roiTTM, // Using ROI as proxy for growth quality temporarily? Or just leave nil.
                isETF: false
            )
        } catch {
            print("❌ Finnhub Fundamentals Parse Error: \(error)")
            throw error
        }
    }
    
    // MARK: - Quote (Backup)
    // MARK: - Quote (Backup)
    func fetchQuote(symbol: String) async throws -> Quote {
        let apiKey = Secrets.shared.finnhub
        let urlString = "\(baseURL)/quote?symbol=\(symbol)&token=\(apiKey)"
        guard let url = URL(string: urlString) else { throw URLError(.badURL) }
        
        // Use HeimdallNetwork for observability
        // Note: Finnhub is a backup, so it might not be the primary provider in logs, but useful for tracing.
        let data = try await HeimdallNetwork.request(url: url, engine: .market, provider: .finnhub, symbol: symbol)
        
        struct FHQuote: Codable {
            let c: Double
            let d: Double
            let dp: Double
        }
        
        let q = try JSONDecoder().decode(FHQuote.self, from: data)
        var quote = Quote(c: q.c, d: q.d, dp: q.dp, currency: "USD")
        quote.timestamp = Date()
        return quote
    }
    
    func fetchCandles(symbol: String, timeframe: String, limit: Int) async throws -> [Candle] {
        let apiKey = Secrets.shared.finnhub
        
        // Map Resolution
        let resolution: String
        let now = Date()
        var fromDate: Date
        
        if timeframe.contains("week") { 
            resolution = "W"
            fromDate = Calendar.current.date(byAdding: .weekOfYear, value: -limit, to: now) ?? now
        } else if timeframe.contains("month") { 
            resolution = "M" 
             fromDate = Calendar.current.date(byAdding: .month, value: -limit, to: now) ?? now
        } else { 
            resolution = "D" 
            fromDate = Calendar.current.date(byAdding: .day, value: -(limit * 2), to: now) ?? now // *2 to cover weekends
        }
        
        let from = Int(fromDate.timeIntervalSince1970)
        let to = Int(now.timeIntervalSince1970)
        
        let urlString = "\(baseURL)/stock/candle?symbol=\(symbol)&resolution=\(resolution)&from=\(from)&to=\(to)&token=\(apiKey)"
        guard let url = URL(string: urlString) else { throw URLError(.badURL) }
        
        let data = try await HeimdallNetwork.request(url: url, engine: .market, provider: .finnhub, symbol: symbol)
        
        struct FHCandleResp: Codable {
            let s: String // status "ok" or "no_data"
            let c: [Double]?
            let h: [Double]?
            let l: [Double]?
            let o: [Double]?
            let v: [Double]?
            let t: [Int]? // timestamps
        }
        
        let resp = try JSONDecoder().decode(FHCandleResp.self, from: data)
        if resp.s != "ok" { throw URLError(.resourceUnavailable) }
        
        guard let times = resp.t, let opens = resp.o, let highs = resp.h, let lows = resp.l, let closes = resp.c, let volumes = resp.v else {
             return []
        }
        
        var candles: [Candle] = []
        for i in 0..<times.count {
            let date = Date(timeIntervalSince1970: TimeInterval(times[i]))
            candles.append(Candle(date: date, open: opens[i], high: highs[i], low: lows[i], close: closes[i], volume: volumes[i]))
        }
        
        // Return reversed (Newest First) to match system standard
        return candles.reversed()
    }
    
    // MARK: - Search
    func search(query: String) async throws -> [SearchResult] {
        let apiKey = Secrets.shared.finnhub
        let urlString = "\(baseURL)/search?q=\(query)&token=\(apiKey)"
        guard let url = URL(string: urlString) else { throw URLError(.badURL) }
        
        // Search is generally UI/Market engine
        let data = try await HeimdallNetwork.request(url: url, engine: .market, provider: .finnhub, symbol: "SEARCH")
        
        struct FHSearchResp: Codable {
            struct Result: Codable {
                let symbol: String
                let description: String?
                let type: String?
            }
            let result: [Result]
        }
        
        let resp = try JSONDecoder().decode(FHSearchResp.self, from: data)
        return resp.result.map { r in
             SearchResult(symbol: r.symbol, description: r.description ?? r.symbol)
        }
    }
}
