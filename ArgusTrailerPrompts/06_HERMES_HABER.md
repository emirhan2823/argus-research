# PROMPT 6: HERMES - HABER ANALİZİ

## Açıklama

RSS ve AI kullanarak haber analizi ve duygu skoru hesaplayan Hermes motoru.

---

## PROMPT

```
Argus Terminal için Hermes (Haber Analizi) motorunu oluştur.

## Özellikler
- RSS feed'lerden haber çekme (ücretsiz)
- AI ile duygu analizi (Groq - ücretsiz)
- Pozitif/Negatif/Nötr sınıflandırma
- Etki skoru hesaplama

## RSSNewsProvider.swift

```swift
import Foundation

class RSSNewsProvider {
    static let shared = RSSNewsProvider()
    
    // Ücretsiz RSS kaynakları
    private let feeds: [String: String] = [
        "yahoo": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=",
        "seeking": "https://seekingalpha.com/api/sa/combined/"
    ]
    
    func fetchNews(for symbol: String) async throws -> [NewsItem] {
        // Yahoo Finance RSS
        let url = URL(string: "https://feeds.finance.yahoo.com/rss/2.0/headline?s=\(symbol)&region=US&lang=en-US")!
        
        var request = URLRequest(url: url)
        request.setValue("Mozilla/5.0", forHTTPHeaderField: "User-Agent")
        
        let (data, _) = try await URLSession.shared.data(for: request)
        return parseRSS(data: data, symbol: symbol)
    }
    
    private func parseRSS(data: Data, symbol: String) -> [NewsItem] {
        guard let xmlString = String(data: data, encoding: .utf8) else { return [] }
        
        var items: [NewsItem] = []
        
        // Basit XML parsing
        let itemPattern = "<item>(.*?)</item>"
        let titlePattern = "<title>(.*?)</title>"
        let linkPattern = "<link>(.*?)</link>"
        let pubDatePattern = "<pubDate>(.*?)</pubDate>"
        
        let itemMatches = xmlString.matches(for: itemPattern)
        
        for itemContent in itemMatches.prefix(10) {
            let title = itemContent.firstMatch(for: titlePattern) ?? ""
            let link = itemContent.firstMatch(for: linkPattern) ?? ""
            let pubDate = itemContent.firstMatch(for: pubDatePattern) ?? ""
            
            if !title.isEmpty {
                items.append(NewsItem(
                    id: UUID().uuidString,
                    symbol: symbol,
                    title: title.removingHTMLTags(),
                    url: link,
                    publishedAt: parseDate(pubDate),
                    source: "Yahoo Finance"
                ))
            }
        }
        
        return items
    }
    
    private func parseDate(_ dateString: String) -> Date {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss Z"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter.date(from: dateString) ?? Date()
    }
}

struct NewsItem: Identifiable, Codable {
    let id: String
    let symbol: String
    let title: String
    let url: String
    let publishedAt: Date
    let source: String
    
    var sentiment: NewsSentiment?
    var sentimentScore: Double?
}

enum NewsSentiment: String, Codable {
    case positive = "Pozitif"
    case negative = "Negatif"
    case neutral = "Nötr"
    
    var emoji: String {
        switch self {
        case .positive: return "🟢"
        case .negative: return "🔴"
        case .neutral: return "🟡"
        }
    }
}

// String extension for regex
extension String {
    func matches(for pattern: String) -> [String] {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: .dotMatchesLineSeparators) else { return [] }
        let range = NSRange(self.startIndex..., in: self)
        return regex.matches(in: self, range: range).compactMap {
            guard let range = Range($0.range(at: 1), in: self) else { return nil }
            return String(self[range])
        }
    }
    
    func firstMatch(for pattern: String) -> String? {
        matches(for: pattern).first
    }
    
    func removingHTMLTags() -> String {
        replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            .replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&lt;", with: "<")
            .replacingOccurrences(of: "&gt;", with: ">")
            .replacingOccurrences(of: "&#39;", with: "'")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
```

## GroqSentimentService.swift

```swift
import Foundation

class GroqSentimentService {
    static let shared = GroqSentimentService()
    private let baseURL = "https://api.groq.com/openai/v1/chat/completions"
    
    private var apiKey: String { Secrets.groqAPIKey }
    
    func analyzeSentiment(headlines: [String]) async throws -> [SentimentResult] {
        guard !apiKey.isEmpty, apiKey != "BURAYA_GROQ_API_KEY_YAPISTIR" else {
            // API key yoksa basit analiz yap
            return headlines.map { simpleSentiment(headline: $0) }
        }
        
        let prompt = """
        Aşağıdaki finans haberlerini analiz et. Her haber için sentiment (positive/negative/neutral) ve 0-100 arası etki skoru ver.
        
        Format: Her satırda "sentiment,skor" şeklinde yanıt ver.
        
        Haberler:
        \(headlines.enumerated().map { "\($0 + 1). \($1)" }.joined(separator: "\n"))
        """
        
        var request = URLRequest(url: URL(string: baseURL)!)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "model": "llama-3.3-70b-versatile",
            "messages": [["role": "user", "content": prompt]],
            "temperature": 0.3,
            "max_tokens": 500
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(GroqResponse.self, from: data)
        
        guard let content = response.choices.first?.message.content else {
            return headlines.map { simpleSentiment(headline: $0) }
        }
        
        return parseGroqResponse(content, count: headlines.count)
    }
    
    private func simpleSentiment(headline: String) -> SentimentResult {
        let lower = headline.lowercased()
        
        let positiveWords = ["rise", "gain", "surge", "rally", "beat", "growth", "up", "high", "profit", "success"]
        let negativeWords = ["fall", "drop", "crash", "plunge", "miss", "loss", "down", "low", "fail", "risk"]
        
        let positiveCount = positiveWords.filter { lower.contains($0) }.count
        let negativeCount = negativeWords.filter { lower.contains($0) }.count
        
        if positiveCount > negativeCount {
            return SentimentResult(sentiment: .positive, score: 60 + Double(positiveCount) * 10)
        } else if negativeCount > positiveCount {
            return SentimentResult(sentiment: .negative, score: 40 - Double(negativeCount) * 10)
        }
        return SentimentResult(sentiment: .neutral, score: 50)
    }
    
    private func parseGroqResponse(_ content: String, count: Int) -> [SentimentResult] {
        let lines = content.components(separatedBy: "\n").filter { !$0.isEmpty }
        var results: [SentimentResult] = []
        
        for line in lines.prefix(count) {
            let parts = line.components(separatedBy: ",")
            if parts.count >= 2 {
                let sentimentStr = parts[0].lowercased().trimmingCharacters(in: .whitespaces)
                let score = Double(parts[1].trimmingCharacters(in: .whitespaces)) ?? 50
                
                let sentiment: NewsSentiment
                if sentimentStr.contains("positive") { sentiment = .positive }
                else if sentimentStr.contains("negative") { sentiment = .negative }
                else { sentiment = .neutral }
                
                results.append(SentimentResult(sentiment: sentiment, score: score))
            }
        }
        
        // Eksik olanları tamamla
        while results.count < count {
            results.append(SentimentResult(sentiment: .neutral, score: 50))
        }
        
        return results
    }
}

struct SentimentResult {
    let sentiment: NewsSentiment
    let score: Double
}

struct GroqResponse: Codable {
    let choices: [GroqChoice]
}

struct GroqChoice: Codable {
    let message: GroqMessage
}

struct GroqMessage: Codable {
    let content: String
}
```

## HermesService.swift

```swift
import Foundation

class HermesService {
    static let shared = HermesService()
    
    func analyzeNews(for symbol: String) async -> HermesResult {
        do {
            // 1. Haberleri çek
            let news = try await RSSNewsProvider.shared.fetchNews(for: symbol)
            
            guard !news.isEmpty else {
                return HermesResult(
                    symbol: symbol,
                    overallSentiment: .neutral,
                    sentimentScore: 50,
                    newsCount: 0,
                    topNews: [],
                    summary: "Haber bulunamadı"
                )
            }
            
            // 2. AI ile analiz et
            let headlines = news.map { $0.title }
            let sentiments = try await GroqSentimentService.shared.analyzeSentiment(headlines: headlines)
            
            // 3. Haberlere sentiment ekle
            var analyzedNews = news
            for i in 0..<min(news.count, sentiments.count) {
                analyzedNews[i].sentiment = sentiments[i].sentiment
                analyzedNews[i].sentimentScore = sentiments[i].score
            }
            
            // 4. Genel skor hesapla
            let avgScore = sentiments.map { $0.score }.reduce(0, +) / Double(sentiments.count)
            
            let overall: NewsSentiment
            if avgScore >= 60 { overall = .positive }
            else if avgScore <= 40 { overall = .negative }
            else { overall = .neutral }
            
            return HermesResult(
                symbol: symbol,
                overallSentiment: overall,
                sentimentScore: avgScore,
                newsCount: news.count,
                topNews: Array(analyzedNews.prefix(5)),
                summary: generateSummary(sentiment: overall, score: avgScore, count: news.count)
            )
            
        } catch {
            print("❌ Hermes error: \(error)")
            return HermesResult(
                symbol: symbol,
                overallSentiment: .neutral,
                sentimentScore: 50,
                newsCount: 0,
                topNews: [],
                summary: "Haber analizi başarısız"
            )
        }
    }
    
    private func generateSummary(sentiment: NewsSentiment, score: Double, count: Int) -> String {
        let sentimentText: String
        switch sentiment {
        case .positive: sentimentText = "Haberler genel olarak olumlu."
        case .negative: sentimentText = "Haberler genel olarak olumsuz."
        case .neutral: sentimentText = "Haberler karışık veya nötr."
        }
        return "\(count) haber analiz edildi. \(sentimentText) Duygu skoru: \(Int(score))/100"
    }
}

struct HermesResult: Identifiable {
    var id: String { symbol }
    let symbol: String
    let overallSentiment: NewsSentiment
    let sentimentScore: Double
    let newsCount: Int
    let topNews: [NewsItem]
    let summary: String
}
```

## TradingViewModel Entegrasyonu

```swift
@Published var hermesResults: [String: HermesResult] = [:]

func loadNewsAnalysis(for symbol: String) async {
    let result = await HermesService.shared.analyzeNews(for: symbol)
    await MainActor.run {
        self.hermesResults[symbol] = result
    }
}
```

---

## API Key Alma (Groq - Opsiyonel)

1. <https://console.groq.com/> adresine git
2. Ücretsiz hesap oluştur
3. API key al
4. Secrets.swift'e yapıştır

**Not:** Groq API key olmadan da çalışır (basit kelime tabanlı analiz yapar).

```
