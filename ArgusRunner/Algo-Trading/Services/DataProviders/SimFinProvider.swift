import Foundation

/// SimFin Fundamental Data Provider
/// US hisseleri için Income Statement, Balance Sheet ve Cash Flow verileri sağlar.
/// Free tier: 2000 istek/gün, 5 yıl geçmiş veri
final class SimFinProvider: HeimdallProvider, Sendable {
    static let shared = SimFinProvider()
    nonisolated var name: String { "SimFin" }
    
    nonisolated var capabilities: [HeimdallDataField] {
        return [.fundamentals]
    }
    
    private let baseURL = "https://backend.simfin.com/api/v3"
    private let cacheKeyPrefix = "SimFinCache"
    private let cacheTTL: TimeInterval = 7 * 86400 // 7 gün (fundamental data nadir güncellenir)
    
    private init() {}
    
    // MARK: - Main Fetch
    
    /// Fetches fundamental data for a US stock
    func fetchFundamentals(symbol: String) async throws -> FinancialsData {
        // 1. Check Cache
        if let cached = checkCache(symbol: symbol) {
            print("💾 SimFin: Using cached fundamentals for \(symbol)")
            return cached
        }
        
        // 2. Check API Key
        guard let apiKey = getApiKey(), !apiKey.isEmpty else {
            print("❌ SimFin: No API Key configured")
            throw HeimdallCoreError(category: .authInvalid, code: 401, message: "SimFin API Key missing", bodyPrefix: "")
        }
        
        // 3. Fetch statements
        print("📊 SimFin: Fetching fundamentals for \(symbol)...")
        
        do {
            // Fetch all statements in parallel
            async let incomeData = fetchStatement(symbol: symbol, statement: "pl", apiKey: apiKey)
            async let balanceData = fetchStatement(symbol: symbol, statement: "bs", apiKey: apiKey)
            async let cashFlowData = fetchStatement(symbol: symbol, statement: "cf", apiKey: apiKey)
            
            let (income, balance, cashFlow) = try await (incomeData, balanceData, cashFlowData)
            
            // 4. Parse and combine into FinancialsData
            let financials = parseStatements(symbol: symbol, income: income, balance: balance, cashFlow: cashFlow)
            
            // 5. Cache result
            saveCache(symbol: symbol, data: financials)
            print("✅ SimFin: Fundamentals fetched for \(symbol)")
            
            return financials
        } catch {
            print("❌ SimFin: Error fetching \(symbol): \(error.localizedDescription)")
            
            // Try stale cache
            if let stale = checkCache(symbol: symbol, ignoreExpiry: true) {
                print("⚠️ SimFin: Serving stale data for \(symbol)")
                return stale
            }
            throw error
        }
    }
    
    // MARK: - Statement Fetch
    
    private func fetchStatement(symbol: String, statement: String, apiKey: String) async throws -> SimFinStatementResponse? {
        // pl = Income Statement (Profit & Loss)
        // bs = Balance Sheet
        // cf = Cash Flow
        
        // V3 API: /companies/statements/compact with Authorization header
        let urlString = "\(baseURL)/companies/statements/compact?ticker=\(symbol)&statements=\(statement)"
        
        guard let url = URL(string: urlString) else { return nil }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(apiKey, forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        if let httpResponse = response as? HTTPURLResponse {
            guard httpResponse.statusCode == 200 else {
                print("⚠️ SimFin \(statement): HTTP \(httpResponse.statusCode)")
                return nil
            }
        }
        
        // Parse response - V3 returns array directly
        do {
            let decoded = try JSONDecoder().decode([SimFinStatementResponse].self, from: data)
            return decoded.first
        } catch {
            print("⚠️ SimFin: Decode error for \(statement): \(error)")
            return nil
        }
    }
    
    // MARK: - Parse Statements
    
    private func parseStatements(symbol: String, income: SimFinStatementResponse?, balance: SimFinStatementResponse?, cashFlow: SimFinStatementResponse?) -> FinancialsData {
        
        // Helper to get value from column data
        func getValue(_ response: SimFinStatementResponse?, column: String) -> Double? {
            guard let resp = response,
                  let columns = resp.columns,
                  let data = resp.data?.first,
                  let index = columns.firstIndex(of: column),
                  index < data.count else { return nil }
            
            if let value = data[index] as? Double { return value }
            if let value = data[index] as? Int { return Double(value) }
            if let str = data[index] as? String, let value = Double(str) { return value }
            return nil
        }
        
        // Income Statement
        let totalRevenue = getValue(income, column: "Revenue")
        let netIncome = getValue(income, column: "Net Income")
        let operatingIncome = getValue(income, column: "Operating Income (Loss)")
        
        // Balance Sheet
        let totalEquity = getValue(balance, column: "Total Equity")
        let totalAssets = getValue(balance, column: "Total Assets")
        let totalDebt = getValue(balance, column: "Total Debt")
        let cash = getValue(balance, column: "Cash, Cash Equivalents & Short Term Investments")
        let currentAssets = getValue(balance, column: "Total Current Assets")
        let currentLiabilities = getValue(balance, column: "Total Current Liabilities")
        
        // Cash Flow
        let operatingCashFlow = getValue(cashFlow, column: "Net Cash from Operating Activities")
        let capex = getValue(cashFlow, column: "Capital Expenditures") ?? getValue(cashFlow, column: "Acquisition of Fixed Assets & Intangibles")
        
        // Derived metrics
        var debtToEquity: Double? = nil
        if let debt = totalDebt, let equity = totalEquity, equity > 0 {
            debtToEquity = debt / equity
        }
        
        var currentRatio: Double? = nil
        if let ca = currentAssets, let cl = currentLiabilities, cl > 0 {
            currentRatio = ca / cl
        }
        
        var freeCashFlow: Double? = nil
        if let ocf = operatingCashFlow {
            freeCashFlow = ocf - abs(capex ?? 0)
        }
        
        return FinancialsData(
            symbol: symbol,
            currency: "USD",
            lastUpdated: Date(),
            totalRevenue: totalRevenue,
            netIncome: netIncome,
            totalShareholderEquity: totalEquity,
            marketCap: nil,
            revenueHistory: [],
            netIncomeHistory: [],
            ebitda: nil,
            shortTermDebt: nil,
            longTermDebt: totalDebt,
            operatingCashflow: operatingCashFlow,
            capitalExpenditures: capex,
            cashAndCashEquivalents: cash,
            peRatio: nil,
            forwardPERatio: nil,
            priceToBook: nil,
            evToEbitda: nil,
            dividendYield: nil,
            forwardGrowthEstimate: nil,
            debtToEquity: debtToEquity,
            currentRatio: currentRatio,
            freeCashFlow: freeCashFlow,
            enterpriseValue: nil,
            pegRatio: nil,
            priceToSales: nil,
            revenueGrowth: nil,
            earningsGrowth: nil
        )
    }
    
    // MARK: - Cache Helpers
    
    private func checkCache(symbol: String, ignoreExpiry: Bool = false) -> FinancialsData? {
        let key = "\(cacheKeyPrefix)_\(symbol)"
        guard let data = UserDefaults.standard.data(forKey: key) else { return nil }
        
        do {
            let wrapper = try JSONDecoder().decode(CacheWrapper.self, from: data)
            
            if !ignoreExpiry && -wrapper.timestamp.timeIntervalSinceNow > cacheTTL {
                return nil // Expired
            }
            
            return wrapper.data
        } catch {
            return nil
        }
    }
    
    private func saveCache(symbol: String, data: FinancialsData) {
        let key = "\(cacheKeyPrefix)_\(symbol)"
        let wrapper = CacheWrapper(timestamp: Date(), data: data)
        
        if let encoded = try? JSONEncoder().encode(wrapper) {
            UserDefaults.standard.set(encoded, forKey: key)
        }
    }
    
    private func getApiKey() -> String? {
        return APIKeyStore.getDirectKey(for: .simfin)
    }
    
    // MARK: - Cache Model
    
    private struct CacheWrapper: Codable {
        let timestamp: Date
        let data: FinancialsData
    }
    
    // MARK: - Heimdall Protocol Stubs
    
    func fetchQuote(symbol: String) async throws -> Quote { throw URLError(.unsupportedURL) }
    func fetchCandles(symbol: String, timeframe: String, limit: Int) async throws -> [Candle] { throw URLError(.unsupportedURL) }
    func fetchCandles(symbol: String, interval: String, outputSize: Int) async throws -> [Candle] { throw URLError(.unsupportedURL) }
    func fetchProfile(symbol: String) async throws -> AssetProfile { throw URLError(.unsupportedURL) }
    func fetchNews(symbol: String) async throws -> [NewsArticle] { throw URLError(.unsupportedURL) }
    func fetchMacro(symbol: String) async throws -> HeimdallMacroIndicator { throw URLError(.unsupportedURL) }
    func fetchScreener(type: ScreenerType, limit: Int) async throws -> [Quote] { throw URLError(.unsupportedURL) }
    func fetchHoldings(symbol: String) async throws -> [EtfHolding] { return [] }
}

// MARK: - SimFin API Response Models

struct SimFinStatementResponse: Codable {
    let found: Bool?
    let columns: [String]?
    let data: [[AnyCodable]]?
    
    enum CodingKeys: String, CodingKey {
        case found, columns, data
    }
}

/// Helper for decoding mixed-type arrays
struct AnyCodable: Codable {
    let value: Any
    
    init(_ value: Any) {
        self.value = value
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let intValue = try? container.decode(Int.self) {
            value = intValue
        } else if let doubleValue = try? container.decode(Double.self) {
            value = doubleValue
        } else if let stringValue = try? container.decode(String.self) {
            value = stringValue
        } else if let boolValue = try? container.decode(Bool.self) {
            value = boolValue
        } else if container.decodeNil() {
            value = NSNull()
        } else {
            throw DecodingError.typeMismatch(Any.self, DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Unsupported type"))
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        
        if let intValue = value as? Int {
            try container.encode(intValue)
        } else if let doubleValue = value as? Double {
            try container.encode(doubleValue)
        } else if let stringValue = value as? String {
            try container.encode(stringValue)
        } else if let boolValue = value as? Bool {
            try container.encode(boolValue)
        } else if value is NSNull {
            try container.encodeNil()
        }
    }
}
