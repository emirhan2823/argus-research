import Foundation

// MARK: - 2.1 NewsProvider Protocol
protocol NewsProvider {
    func fetchNews(symbol: String, limit: Int) async throws -> [NewsArticle]
}

// MARK: - 2.2 FinnhubNewsProvider
final class FinnhubNewsProvider: NewsProvider {
    // Valid Finnhub Key from APIKeyStore (via Secrets)
    private var apiKey: String { Secrets.finnhubKey }
    private let baseURL = "https://finnhub.io/api/v1/company-news"
    
    func fetchNews(symbol: String, limit: Int) async throws -> [NewsArticle] {
        // Calculate date range (Last 30 days to ensure volume)
        let now = Date()
        let fromDate = Calendar.current.date(byAdding: .day, value: -30, to: now)!
        
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        
        let fromStr = dateFormatter.string(from: fromDate)
        let toStr = dateFormatter.string(from: now)
        
        // Construct URL
        let urlString: String
        if symbol == "GENERAL" {
            urlString = "https://finnhub.io/api/v1/news?category=general&token=\(apiKey)"
        } else {
            urlString = "\(baseURL)?symbol=\(symbol)&from=\(fromStr)&to=\(toStr)&token=\(apiKey)"
        }
        
        guard let url = URL(string: urlString) else {
            throw URLError(.badURL)
        }
        
        let (data, _) = try await URLSession.shared.data(from: url)
        
        // Finnhub uses a specific JSON structure for news
        let finnhubNews = try JSONDecoder().decode([FinnhubNewsItem].self, from: data)
        
        // Map to domain model
        let articles = finnhubNews.map { item -> NewsArticle in
            let date = Date(timeIntervalSince1970: TimeInterval(item.datetime))
            return NewsArticle(
                id: "\(item.id)", // API ID
                symbol: symbol,
                source: "Finnhub",
                headline: item.headline,
                summary: item.summary,
                url: item.url,
                publishedAt: date
            )
        }
        
        // Sort and limit
        return Array(articles.sorted { $0.publishedAt > $1.publishedAt }.prefix(limit))
    }
}

// Helper struct for Finnhub response
private struct FinnhubNewsItem: Codable {
    let id: Int
    let headline: String
    let datetime: Int
    let summary: String
    let url: String
    let source: String
}

// MARK: - 2.3 SecondaryNewsProvider (Skeleton)
final class SecondaryNewsProvider: NewsProvider {
    // Bu provider’ın JSON mapping kısmı ilgili API’ye göre kullanıcı tarafından doldurulmalıdır.
    private let apiKey = "SECONDARY_NEWS_API_KEYI_BURAYA_BEN_YAZACAĞIM"
    private let baseURL = "https://SECOND_NEWS_API_BASE_URL"
    
    func fetchNews(symbol: String, limit: Int) async throws -> [NewsArticle] {
        // Placeholder implementation
        // Example logic:
        // 1. URL definition
        // 2. Fetch data
        // 3. Decode JSON
        // 4. Map to NewsArticle with source = "Secondary"
        
        // For now, return empty to not break anything
        return []
    }
}

// MARK: - 2.4 AggregatedNewsService
final class AggregatedNewsService {
    static let shared = AggregatedNewsService()
    
    private let primary: NewsProvider
    private let secondary: NewsProvider
    private let rssProvider: NewsProvider
    
    init(primary: NewsProvider = FinnhubNewsProvider(),
         secondary: NewsProvider = YahooFinanceNewsProvider(),
         rssProvider: NewsProvider = RSSNewsProvider()) {
        self.primary = primary
        self.secondary = secondary
        self.rssProvider = rssProvider
    }
    
    func fetchNews(symbol: String, limit: Int) async throws -> [NewsArticle] {
        // 0. Priority: Investing.com RSS for General/Market news
        if symbol == "GENERAL" || symbol == "MARKET" {
            do {
                let rssArticles = try await rssProvider.fetchNews(symbol: "GENERAL", limit: limit)
                if !rssArticles.isEmpty {
                    return rssArticles
                }
            } catch {
                print("RSS Provider failed for GENERAL: \(error)")
            }
        }
        
        // ArgusDataService kullan (Heimdall yerine)
        do {
            let articles = try await ArgusDataService.shared.fetchNews(symbol: symbol, limit: limit)
            return articles
        } catch {
            print("⚠️ AggregatedNewsService: ArgusDataService failed for \(symbol): \(error)")
            
            // Fallback: Try Legacy Finnhub Directly
            do {
                return try await primary.fetchNews(symbol: symbol, limit: limit)
            } catch {
                print("⚠️ Fallback to Primary failed: \(error)")
                return []
            }
        }
    }
}
