# PROMPT 11: VERİ ÇEKME SERVİSLERİ

## Açıklama

Fiyat verileri çekmek için temel servisler (Yahoo Finance fallback ile).

---

## PROMPT

```
Argus Terminal için veri çekme servislerini oluştur.

## Problem
- FMP API ücretsiz planı sınırlı
- FRED bazı verileri güncellemede geç kalabilir
- Yahoo Finance bazen bloklanabilir

## Çözüm: Fallback Sistemi

### MarketDataProvider.swift

```swift
import Foundation

class MarketDataProvider {
    static let shared = MarketDataProvider()
    
    // Primary: FMP, Fallback: Yahoo
    func fetchQuote(symbol: String) async -> Quote? {
        // 1. Önce FMP dene
        if let quote = try? await fetchFromFMP(symbol: symbol) {
            return quote
        }
        
        // 2. FMP başarısızsa Yahoo dene
        if let quote = try? await fetchFromYahoo(symbol: symbol) {
            return quote
        }
        
        return nil
    }
    
    func fetchCandles(symbol: String, days: Int = 365) async -> [Candle] {
        // 1. Önce Yahoo dene (daha iyi historik veri)
        if let candles = try? await fetchCandlesFromYahoo(symbol: symbol, days: days) {
            return candles
        }
        
        // 2. Yahoo başarısızsa FMP dene
        if let candles = try? await fetchCandlesFromFMP(symbol: symbol, days: days) {
            return candles
        }
        
        return []
    }
    
    // MARK: - FMP Implementation
    
    private func fetchFromFMP(symbol: String) async throws -> Quote {
        let url = URL(string: "https://financialmodelingprep.com/api/v3/quote/\(symbol)?apikey=\(Secrets.fmpAPIKey)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        
        let decoded = try JSONDecoder().decode([FMPQuote].self, from: data)
        guard let fmp = decoded.first else { throw DataError.noData }
        
        return Quote(
            symbol: fmp.symbol,
            currentPrice: fmp.price,
            change: fmp.change,
            changePercent: fmp.changesPercentage
        )
    }
    
    private func fetchCandlesFromFMP(symbol: String, days: Int) async throws -> [Candle] {
        let url = URL(string: "https://financialmodelingprep.com/api/v3/historical-price-full/\(symbol)?apikey=\(Secrets.fmpAPIKey)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        
        let decoded = try JSONDecoder().decode(FMPHistorical.self, from: data)
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        
        return decoded.historical.prefix(days).compactMap { h in
            guard let date = formatter.date(from: h.date) else { return nil }
            return Candle(
                date: date,
                open: h.open,
                high: h.high,
                low: h.low,
                close: h.close,
                volume: h.volume
            )
        }.reversed()
    }
    
    // MARK: - Yahoo Implementation
    
    private func fetchFromYahoo(symbol: String) async throws -> Quote {
        let url = URL(string: "https://query1.finance.yahoo.com/v8/finance/chart/\(symbol)?interval=1d&range=1d")!
        
        var request = URLRequest(url: url)
        request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", forHTTPHeaderField: "User-Agent")
        
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(YahooChartResponse.self, from: data)
        
        guard let result = response.chart.result?.first,
              let meta = result.meta,
              let price = meta.regularMarketPrice else {
            throw DataError.noData
        }
        
        let prevClose = meta.previousClose ?? price
        
        return Quote(
            symbol: symbol,
            currentPrice: price,
            change: price - prevClose,
            changePercent: ((price - prevClose) / prevClose) * 100
        )
    }
    
    private func fetchCandlesFromYahoo(symbol: String, days: Int) async throws -> [Candle] {
        let period1 = Int(Date().addingTimeInterval(-Double(days) * 86400).timeIntervalSince1970)
        let period2 = Int(Date().timeIntervalSince1970)
        
        let url = URL(string: "https://query1.finance.yahoo.com/v8/finance/chart/\(symbol)?period1=\(period1)&period2=\(period2)&interval=1d")!
        
        var request = URLRequest(url: url)
        request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", forHTTPHeaderField: "User-Agent")
        
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(YahooChartResponse.self, from: data)
        
        guard let result = response.chart.result?.first,
              let timestamps = result.timestamp,
              let indicators = result.indicators,
              let quote = indicators.quote?.first else {
            throw DataError.noData
        }
        
        var candles: [Candle] = []
        
        for i in 0..<timestamps.count {
            guard let open = quote.open?[i],
                  let high = quote.high?[i],
                  let low = quote.low?[i],
                  let close = quote.close?[i] else { continue }
            
            candles.append(Candle(
                date: Date(timeIntervalSince1970: TimeInterval(timestamps[i])),
                open: open,
                high: high,
                low: low,
                close: close,
                volume: quote.volume?[i]
            ))
        }
        
        return candles
    }
}

// MARK: - Error Types

enum DataError: Error {
    case noData
    case apiLimit
    case networkError
}

// MARK: - FMP Models

struct FMPQuote: Codable {
    let symbol: String
    let price: Double
    let change: Double?
    let changesPercentage: Double?
}

struct FMPHistorical: Codable {
    let historical: [FMPCandle]
}

struct FMPCandle: Codable {
    let date: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double?
}

// MARK: - Yahoo Models (Extended)

struct YahooChartResponse: Codable {
    let chart: YahooChart
}

struct YahooChart: Codable {
    let result: [YahooResult]?
    let error: YahooError?
}

struct YahooResult: Codable {
    let meta: YahooMeta?
    let timestamp: [Int]?
    let indicators: YahooIndicators?
}

struct YahooMeta: Codable {
    let currency: String?
    let symbol: String?
    let regularMarketPrice: Double?
    let previousClose: Double?
}

struct YahooIndicators: Codable {
    let quote: [YahooQuoteData]?
}

struct YahooQuoteData: Codable {
    let open: [Double?]?
    let high: [Double?]?
    let low: [Double?]?
    let close: [Double?]?
    let volume: [Double?]?
}

struct YahooError: Codable {
    let code: String?
    let description: String?
}
```

## TradingViewModel Entegrasyonu

```swift
func loadQuote(for symbol: String) async {
    if let quote = await MarketDataProvider.shared.fetchQuote(symbol: symbol) {
        await MainActor.run {
            self.quotes[symbol] = quote
        }
    }
}

func loadCandles(for symbol: String, days: Int = 365) async {
    let candles = await MarketDataProvider.shared.fetchCandles(symbol: symbol, days: days)
    await MainActor.run {
        self.candles[symbol] = candles
    }
}
```

---

## Sık Karşılaşılan Hatalar ve Çözümler

### 1. "Too Many Requests" (FMP)

```swift
// Rate limiting ekle
private var lastRequestTime: Date?
private let minInterval: TimeInterval = 0.5 // 500ms

private func waitIfNeeded() async {
    if let last = lastRequestTime {
        let elapsed = Date().timeIntervalSince(last)
        if elapsed < minInterval {
            try? await Task.sleep(nanoseconds: UInt64((minInterval - elapsed) * 1_000_000_000))
        }
    }
    lastRequestTime = Date()
}
```

### 2. "Could not decode" Hatası

```swift
// Optional fields kullan
struct Quote: Codable {
    let symbol: String
    let currentPrice: Double
    let change: Double?  // Optional!
    let changePercent: Double?  // Optional!
}
```

### 3. Yahoo Bloklandığında

```swift
// Farklı User-Agent dene
let userAgents = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
]
request.setValue(userAgents.randomElement()!, forHTTPHeaderField: "User-Agent")
```
