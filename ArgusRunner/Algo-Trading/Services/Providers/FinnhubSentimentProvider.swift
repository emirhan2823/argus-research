import Foundation

// MARK: - Finnhub Sentiment Provider
// Provides news and sentiment data from Finnhub API
// Free tier: 60 requests/minute

actor FinnhubSentimentProvider {
    static let shared = FinnhubSentimentProvider()
    
    private let baseURL = "https://finnhub.io/api/v1"
    private var apiKey: String { Secrets.finnhubKey }
    
    // Cache to reduce API calls
    private var sentimentCache: [String: (score: FinnhubSentiment, timestamp: Date)] = [:]
    private let cacheExpiry: TimeInterval = 300 // 5 minutes
    
    // MARK: - Public API
    
    /// Fetches sentiment analysis for a given symbol
    /// Returns a normalized 0-100 score (50 = neutral)
    func getSentiment(for symbol: String) async throws -> FinnhubSentiment {
        // Check cache first
        if let cached = sentimentCache[symbol],
           Date().timeIntervalSince(cached.timestamp) < cacheExpiry {
            return cached.score
        }
        
        // Fetch fresh data
        let sentiment = try await fetchSentiment(symbol: symbol)
        sentimentCache[symbol] = (sentiment, Date())
        return sentiment
    }
    
    /// Fetches recent news for a symbol with sentiment scores
    func getNews(for symbol: String, count: Int = 10) async throws -> [FinnhubSentimentNews] {
        let encodedSymbol = symbol.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? symbol
        
        // Calculate date range (last 7 days)
        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -7, to: endDate) ?? endDate
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        
        let urlString = "\(baseURL)/company-news?symbol=\(encodedSymbol)&from=\(formatter.string(from: startDate))&to=\(formatter.string(from: endDate))&token=\(apiKey)"
        
        guard let url = URL(string: urlString) else {
            throw FinnhubError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw FinnhubError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw FinnhubError.httpError(httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        let news = try decoder.decode([FinnhubSentimentNews].self, from: data)
        
        return Array(news.prefix(count))
    }
    
    // MARK: - Private Methods
    
    private func fetchSentiment(symbol: String) async throws -> FinnhubSentiment {
        let encodedSymbol = symbol.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? symbol
        let urlString = "\(baseURL)/news-sentiment?symbol=\(encodedSymbol)&token=\(apiKey)"
        
        guard let url = URL(string: urlString) else {
            throw FinnhubError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw FinnhubError.invalidResponse
        }
        
        // Handle rate limiting
        if httpResponse.statusCode == 429 {
            throw FinnhubError.rateLimited
        }
        
        guard httpResponse.statusCode == 200 else {
            throw FinnhubError.httpError(httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        let rawSentiment = try decoder.decode(FinnhubSentimentResponse.self, from: data)
        
        return FinnhubSentiment(from: rawSentiment)
    }
}

// MARK: - Models

struct FinnhubSentiment {
    let bullishPercent: Double  // 0-100
    let bearishPercent: Double  // 0-100
    let neutralPercent: Double  // 0-100
    let overallScore: Double    // 0-100 (50 = neutral)
    let newsCount: Int
    let companyNewsScore: Double // -1 to 1
    let sectorAverageScore: Double // -1 to 1
    
    /// Normalized score for Hermes integration (0-100)
    var hermesScore: Double {
        // Convert -1 to 1 range to 0-100
        // -1 = 0 (very bearish), 0 = 50 (neutral), 1 = 100 (very bullish)
        return (companyNewsScore + 1) * 50
    }
    
    init(from response: FinnhubSentimentResponse) {
        self.bullishPercent = response.sentiment?.bullishPercent ?? 50
        self.bearishPercent = response.sentiment?.bearishPercent ?? 50
        self.neutralPercent = 100 - bullishPercent - bearishPercent
        self.companyNewsScore = response.companyNewsScore ?? 0
        self.sectorAverageScore = response.sectorAverageNewsScore ?? 0
        self.newsCount = response.buzz?.articlesInLastWeek ?? 0
        
        // Calculate overall score from bullish/bearish ratio
        let ratio = bullishPercent - bearishPercent // -100 to 100
        self.overallScore = (ratio + 100) / 2 // Normalize to 0-100
    }
    
    /// Empty/neutral sentiment
    static let neutral = FinnhubSentiment(
        bullishPercent: 50,
        bearishPercent: 50,
        overallScore: 50,
        newsCount: 0,
        companyNewsScore: 0
    )
    
    private init(bullishPercent: Double, bearishPercent: Double, overallScore: Double, newsCount: Int, companyNewsScore: Double) {
        self.bullishPercent = bullishPercent
        self.bearishPercent = bearishPercent
        self.neutralPercent = 0
        self.overallScore = overallScore
        self.newsCount = newsCount
        self.companyNewsScore = companyNewsScore
        self.sectorAverageScore = 0
    }
}

struct FinnhubSentimentResponse: Codable {
    let buzz: Buzz?
    let companyNewsScore: Double?
    let sectorAverageNewsScore: Double?
    let sentiment: SentimentData?
    let symbol: String?
    
    struct Buzz: Codable {
        let articlesInLastWeek: Int?
        let buzz: Double?
        let weeklyAverage: Double?
    }
    
    struct SentimentData: Codable {
        let bearishPercent: Double?
        let bullishPercent: Double?
    }
}

struct FinnhubSentimentNews: Codable, Identifiable {
    let id: Int
    let category: String?
    let datetime: Int // Unix timestamp
    let headline: String
    let image: String?
    let related: String?
    let source: String?
    let summary: String?
    let url: String?
    
    var date: Date {
        Date(timeIntervalSince1970: TimeInterval(datetime))
    }
    
    var formattedDate: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

// MARK: - Errors

enum FinnhubError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case httpError(Int)
    case rateLimited
    case decodingError
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid Finnhub URL"
        case .invalidResponse: return "Invalid response from Finnhub"
        case .httpError(let code): return "Finnhub HTTP error: \(code)"
        case .rateLimited: return "Finnhub rate limit exceeded"
        case .decodingError: return "Failed to decode Finnhub response"
        }
    }
}
