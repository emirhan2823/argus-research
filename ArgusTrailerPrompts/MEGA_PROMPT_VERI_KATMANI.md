# 🔬 ARGUS İLERİ SEVİYE PROMPT - Veri Modelleri & Servisler

## Bu Prompt Ne Yapar?

MEGA_PROMPT_BIREBIR.md'yi tamamladıktan sonra, bu prompt ile:

- Veri modelleri (Quote, Candle, Score)
- API servisleri (Yahoo Finance, FRED)
- TradingViewModel
- Gerçek veri akışı

---

# PROMPT (MEGA PROMPT'TAN SONRA KULLAN)

```
Argus Terminal için şimdi VERİ KATMANINI ekle. Birebir bu kodları kullan.

═══════════════════════════════════════════════════════════════════
DOSYA: Models/Quote.swift
═══════════════════════════════════════════════════════════════════

import Foundation

struct Quote: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    var currentPrice: Double
    var previousClose: Double?
    var d: Double?
    var dp: Double?
    var h: Double?
    var l: Double?
    var o: Double?
    var t: TimeInterval?
    
    var timestamp: Date { Date(timeIntervalSince1970: t ?? Date().timeIntervalSince1970) }
    
    var changePercent: Double { dp ?? 0 }
    var isPositive: Bool { (dp ?? 0) >= 0 }
}

═══════════════════════════════════════════════════════════════════
DOSYA: Models/Candle.swift
═══════════════════════════════════════════════════════════════════

import Foundation

struct Candle: Codable, Identifiable {
    var id: String { "\(date.timeIntervalSince1970)" }
    let date: Date
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double?
    
    var isBullish: Bool { close > open }
    var bodySize: Double { abs(close - open) }
    var range: Double { high - low }
}

═══════════════════════════════════════════════════════════════════
DOSYA: Models/SignalAction.swift
═══════════════════════════════════════════════════════════════════

import Foundation

enum SignalAction: String, Codable {
    case buy = "AL"
    case sell = "SAT"
    case hold = "TUT"
    case wait = "BEKLE"
    case skip = "ATLA"
    
    var emoji: String {
        switch self {
        case .buy: return "🟢"
        case .sell: return "🔴"
        case .hold: return "🟡"
        case .wait: return "⏳"
        case .skip: return "⏭️"
        }
    }
}

═══════════════════════════════════════════════════════════════════
DOSYA: Models/OrionScoreResult.swift
═══════════════════════════════════════════════════════════════════

import Foundation

struct OrionScoreResult: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let score: Double
    let structureScore: Double
    let trendScore: Double
    let momentumScore: Double
    let patternScore: Double
    let recommendation: String
    let reasoning: String
    let calculatedAt: Date
    
    var letterGrade: String {
        switch score {
        case 80...100: return "A"
        case 60..<80: return "B"
        case 40..<60: return "C"
        case 20..<40: return "D"
        default: return "F"
        }
    }
    
    var totalScore: Double { score }
}

═══════════════════════════════════════════════════════════════════
DOSYA: Models/FundamentalScore.swift
═══════════════════════════════════════════════════════════════════

import Foundation

struct FundamentalScore: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let totalScore: Double
    let profitabilityScore: Double
    let growthScore: Double
    let debtScore: Double
    let valuationScore: Double
    let letterGrade: String
    let summary: String
    let isETF: Bool
    let calculatedAt: Date
}

═══════════════════════════════════════════════════════════════════
DOSYA: Models/MacroEnvironmentRating.swift
═══════════════════════════════════════════════════════════════════

import Foundation

enum MacroRegime: String, Codable {
    case riskOn = "Risk İştahı Yüksek"
    case neutral = "Nötr"
    case riskOff = "Risk Kaçınma"
    
    var displayName: String { rawValue }
}

struct MacroEnvironmentRating: Codable, Identifiable {
    var id: String { UUID().uuidString }
    let leadingScore: Double?
    let coincidentScore: Double?
    let laggingScore: Double?
    let numericScore: Double
    let letterGrade: String
    let regime: MacroRegime
    let summary: String
    let details: String
}

═══════════════════════════════════════════════════════════════════
DOSYA: Services/Secrets.swift
═══════════════════════════════════════════════════════════════════

import Foundation

struct Secrets {
    // BU DEĞERLERİ KENDİ API KEY'LERİNLE DEĞİŞTİR
    static let fmpAPIKey = "BURAYA_FMP_KEY"
    static let fredAPIKey = "BURAYA_FRED_KEY"
    static let groqAPIKey = "BURAYA_GROQ_KEY"
}

═══════════════════════════════════════════════════════════════════
DOSYA: Services/YahooFinanceProvider.swift
═══════════════════════════════════════════════════════════════════

import Foundation

class YahooFinanceProvider {
    static let shared = YahooFinanceProvider()
    
    func fetchQuote(symbol: String) async throws -> Quote {
        let url = URL(string: "https://query1.finance.yahoo.com/v8/finance/chart/\(symbol)?interval=1d&range=1d")!
        let (data, _) = try await URLSession.shared.data(from: url)
        
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let chart = json?["chart"] as? [String: Any]
        let result = (chart?["result"] as? [[String: Any]])?.first
        let meta = result?["meta"] as? [String: Any]
        
        let price = meta?["regularMarketPrice"] as? Double ?? 0
        let prevClose = meta?["chartPreviousClose"] as? Double
        
        let change = prevClose.map { price - $0 }
        let changePercent = prevClose.map { ((price - $0) / $0) * 100 }
        
        return Quote(
            symbol: symbol,
            currentPrice: price,
            previousClose: prevClose,
            d: change,
            dp: changePercent,
            h: nil,
            l: nil,
            o: nil,
            t: Date().timeIntervalSince1970
        )
    }
    
    func fetchCandles(symbol: String, range: String = "3mo") async throws -> [Candle] {
        let url = URL(string: "https://query1.finance.yahoo.com/v8/finance/chart/\(symbol)?interval=1d&range=\(range)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let chart = json?["chart"] as? [String: Any]
        let result = (chart?["result"] as? [[String: Any]])?.first
        let timestamps = result?["timestamp"] as? [TimeInterval] ?? []
        let indicators = result?["indicators"] as? [String: Any]
        let quote = (indicators?["quote"] as? [[String: Any]])?.first
        
        let opens = quote?["open"] as? [Double?] ?? []
        let highs = quote?["high"] as? [Double?] ?? []
        let lows = quote?["low"] as? [Double?] ?? []
        let closes = quote?["close"] as? [Double?] ?? []
        let volumes = quote?["volume"] as? [Double?] ?? []
        
        var candles: [Candle] = []
        for i in 0..<timestamps.count {
            guard let o = opens[safe: i] ?? nil,
                  let h = highs[safe: i] ?? nil,
                  let l = lows[safe: i] ?? nil,
                  let c = closes[safe: i] ?? nil else { continue }
            
            candles.append(Candle(
                date: Date(timeIntervalSince1970: timestamps[i]),
                open: o,
                high: h,
                low: l,
                close: c,
                volume: volumes[safe: i] ?? nil
            ))
        }
        
        return candles
    }
}

extension Array {
    subscript(safe index: Int) -> Element? {
        return indices.contains(index) ? self[index] : nil
    }
}

═══════════════════════════════════════════════════════════════════
DOSYA: ViewModels/TradingViewModel.swift
═══════════════════════════════════════════════════════════════════

import Foundation
import Combine

@MainActor
class TradingViewModel: ObservableObject {
    static let shared = TradingViewModel()
    
    @Published var watchlist: [String] = ["AAPL", "GOOGL", "MSFT", "NVDA", "TSLA", "AMZN"]
    @Published var quotes: [String: Quote] = [:]
    @Published var candles: [String: [Candle]] = [:]
    @Published var orionScores: [String: OrionScoreResult] = [:]
    @Published var fundamentalScores: [String: FundamentalScore] = [:]
    @Published var macroRating: MacroEnvironmentRating?
    
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let yahooProvider = YahooFinanceProvider.shared
    
    func loadQuote(for symbol: String) async {
        do {
            let quote = try await yahooProvider.fetchQuote(symbol: symbol)
            quotes[symbol] = quote
        } catch {
            print("Quote fetch failed: \(error)")
        }
    }
    
    func loadCandles(for symbol: String) async {
        do {
            let fetched = try await yahooProvider.fetchCandles(symbol: symbol)
            candles[symbol] = fetched
        } catch {
            print("Candles fetch failed: \(error)")
        }
    }
    
    func loadAllQuotes() async {
        isLoading = true
        for symbol in watchlist {
            await loadQuote(for: symbol)
        }
        isLoading = false
    }
}

═══════════════════════════════════════════════════════════════════
GÜNCELLE: ContentView.swift - ViewModel Entegrasyonu
═══════════════════════════════════════════════════════════════════

ContentView'da şunu değiştir:

struct WatchlistView: View {
    @StateObject private var viewModel = TradingViewModel.shared
    
    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ForEach(viewModel.watchlist, id: \.self) { symbol in
                    WatchlistRowLive(symbol: symbol, quote: viewModel.quotes[symbol])
                }
            }
            .padding()
        }
        .task {
            await viewModel.loadAllQuotes()
        }
    }
}

struct WatchlistRowLive: View {
    let symbol: String
    let quote: Quote?
    
    var body: some View {
        HStack {
            Circle()
                .fill(Theme.cardBackground)
                .frame(width: 44, height: 44)
                .overlay(
                    Text(String(symbol.prefix(1)))
                        .font(.headline)
                        .foregroundColor(.white)
                )
            
            VStack(alignment: .leading, spacing: 2) {
                Text(symbol)
                    .font(.headline)
                    .foregroundColor(.white)
                if let q = quote {
                    Text(String(format: "$%.2f", q.currentPrice))
                        .font(.subheadline)
                        .foregroundColor(Theme.textSecondary)
                }
            }
            
            Spacer()
            
            if let q = quote, let dp = q.dp {
                Text(String(format: "%+.2f%%", dp))
                    .font(.subheadline)
                    .bold()
                    .foregroundColor(dp >= 0 ? Theme.positive : Theme.negative)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background((dp >= 0 ? Theme.positive : Theme.negative).opacity(0.2))
                    .cornerRadius(6)
            }
        }
        .padding()
        .glassCard()
    }
}

═══════════════════════════════════════════════════════════════════
BUILD ET VE TEST ET
═══════════════════════════════════════════════════════════════════

Artık uygulama:
1. Yahoo Finance'den gerçek fiyat çekiyor
2. Watchlist'te canlı veriler gösteriyor
3. Yeşil/kırmızı değişim oranları çalışıyor

```

---

## Sonraki Adımlar

Bu prompt'tan sonra şunları ekleyebilirsin:

- 03_ATLAS_TEMEL_ANALIZ.md → Temel analiz motoru
- 04_ORION_TEKNIK_ANALIZ.md → RSI, MACD hesaplamaları
- 05_AETHER_MAKRO.md → FRED makro verileri
