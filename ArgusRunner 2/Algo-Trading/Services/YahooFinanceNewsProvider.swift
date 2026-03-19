import Foundation

/// Fetches real news from Yahoo Finance RSS feeds.
/// Provides specific news for any symbol (e.g., TSLA, AAPL, BTC-USD).
final class YahooFinanceNewsProvider: NewsProvider {
    static let shared = YahooFinanceNewsProvider()
    

    private let session: URLSession
    
    init(session: URLSession = .shared) {
        self.session = session
    }
    
    func fetchNews(symbol: String, limit: Int) async throws -> [NewsArticle] {
        // Construct Yahoo RSS URL
        // Example: https://feeds.finance.yahoo.com/rss/2.0/headline?s=TSLA
        guard let url = URL(string: "https://feeds.finance.yahoo.com/rss/2.0/headline?s=\(symbol)") else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.setValue("Mozilla/5.0 (compatible; ArgusBot/1.0)", forHTTPHeaderField: "User-Agent")
        request.timeoutInterval = 10
        
        let (data, response) = try await session.data(for: request)
        
        if let httpResponse = response as? HTTPURLResponse, !(200...299).contains(httpResponse.statusCode) {
             throw URLError(.badServerResponse)
        }
        
        // Use existing RSSParser (internal in module) or a robust local one
        // Since RSSParser in RSSNewsProvider.swift is internal, we can try to use it.
        // If it fails due to access control (if in different file), we might need to duplicate simple logic.
        // Assuming same module:
        let parser = RSSParser(limit: limit, sourceName: "Yahoo Finance") 
        let articles = parser.parse(data: data)
        
        // Post-process to ensure correct Symbol attribution
        // Yahoo feed doesn't explicitly state the symbol in the item, so we overwrite it.
        return articles.map { article in
            NewsArticle(
                id: article.id,
                symbol: symbol,
                source: "Yahoo Finance",
                headline: article.headline,
                summary: article.summary,
                url: article.url,
                publishedAt: article.publishedAt
            )
        }
    }
}
