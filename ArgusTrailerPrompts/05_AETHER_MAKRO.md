# PROMPT 5: AETHER - MAKROEKONOMİK ANALİZ

## Açıklama

FRED API kullanarak makroekonomik ortamı analiz eden Aether motoru.

---

## PROMPT

```
Argus Terminal için Aether (Makroekonomik Analiz) motorunu oluştur.

## Özellikler
- FRED API'den makro veri çekme (CPI, İşsizlik, GDP, Faiz)
- Yahoo Finance'den piyasa verileri (VIX, SPY, GLD, BTC, DXY)
- 3 kategori: Öncü, Eşzamanlı, Gecikmeli göstergeler
- Risk On / Risk Off / Nötr rejim tespiti

## FREDProvider.swift

```swift
import Foundation

class FREDProvider {
    static let shared = FREDProvider()
    private let baseURL = "https://api.stlouisfed.org/fred/series/observations"
    
    private var apiKey: String { Secrets.fredAPIKey }
    
    func fetchSeries(seriesId: String, limit: Int = 12) async throws -> [FREDObservation] {
        var components = URLComponents(string: baseURL)!
        components.queryItems = [
            URLQueryItem(name: "series_id", value: seriesId),
            URLQueryItem(name: "api_key", value: apiKey),
            URLQueryItem(name: "file_type", value: "json"),
            URLQueryItem(name: "sort_order", value: "desc"),
            URLQueryItem(name: "limit", value: String(limit))
        ]
        
        let (data, _) = try await URLSession.shared.data(from: components.url!)
        let response = try JSONDecoder().decode(FREDResponse.self, from: data)
        return response.observations
    }
    
    // Önemli seriler
    func fetchCPI() async throws -> Double? {
        let obs = try await fetchSeries(seriesId: "CPIAUCSL", limit: 2)
        return calculateYoYChange(obs)
    }
    
    func fetchUnemployment() async throws -> Double? {
        let obs = try await fetchSeries(seriesId: "UNRATE", limit: 1)
        return Double(obs.first?.value ?? "0")
    }
    
    func fetchFedFundsRate() async throws -> Double? {
        let obs = try await fetchSeries(seriesId: "FEDFUNDS", limit: 1)
        return Double(obs.first?.value ?? "0")
    }
    
    func fetchInitialClaims() async throws -> Double? {
        let obs = try await fetchSeries(seriesId: "ICSA", limit: 1)
        return Double(obs.first?.value ?? "0")
    }
    
    private func calculateYoYChange(_ obs: [FREDObservation]) -> Double? {
        guard obs.count >= 2,
              let current = Double(obs[0].value),
              let previous = Double(obs[1].value),
              previous != 0 else { return nil }
        return ((current - previous) / previous) * 100
    }
}

struct FREDResponse: Codable {
    let observations: [FREDObservation]
}

struct FREDObservation: Codable {
    let date: String
    let value: String
}
```

## YahooFinanceProvider.swift

```swift
import Foundation

class YahooFinanceProvider {
    static let shared = YahooFinanceProvider()
    private let baseURL = "https://query1.finance.yahoo.com/v8/finance/chart"
    
    func fetchQuote(symbol: String) async throws -> YahooQuote? {
        let url = URL(string: "\(baseURL)/\(symbol)?interval=1d&range=1mo")!
        var request = URLRequest(url: url)
        request.setValue("Mozilla/5.0", forHTTPHeaderField: "User-Agent")
        
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(YahooChartResponse.self, from: data)
        
        guard let result = response.chart.result?.first,
              let meta = result.meta else { return nil }
        
        return YahooQuote(
            symbol: symbol,
            price: meta.regularMarketPrice ?? 0,
            change: (meta.regularMarketPrice ?? 0) - (meta.previousClose ?? 0),
            changePercent: meta.regularMarketPrice != nil && meta.previousClose != nil ?
                ((meta.regularMarketPrice! - meta.previousClose!) / meta.previousClose!) * 100 : 0
        )
    }
    
    // Makro için önemli semboller
    func fetchMacroIndicators() async -> MacroMarketData {
        async let spy = fetchQuote(symbol: "SPY")
        async let vix = fetchQuote(symbol: "^VIX")
        async let gld = fetchQuote(symbol: "GLD")
        async let btc = fetchQuote(symbol: "BTC-USD")
        async let dxy = fetchQuote(symbol: "DX-Y.NYB")
        
        return MacroMarketData(
            spy: try? await spy,
            vix: try? await vix,
            gld: try? await gld,
            btc: try? await btc,
            dxy: try? await dxy
        )
    }
}

struct YahooChartResponse: Codable {
    let chart: YahooChart
}

struct YahooChart: Codable {
    let result: [YahooResult]?
}

struct YahooResult: Codable {
    let meta: YahooMeta?
}

struct YahooMeta: Codable {
    let regularMarketPrice: Double?
    let previousClose: Double?
}

struct YahooQuote {
    let symbol: String
    let price: Double
    let change: Double
    let changePercent: Double
}

struct MacroMarketData {
    let spy: YahooQuote?
    let vix: YahooQuote?
    let gld: YahooQuote?
    let btc: YahooQuote?
    let dxy: YahooQuote?
}
```

## MacroRegimeService.swift

```swift
import Foundation

class MacroRegimeService {
    static let shared = MacroRegimeService()
    
    func analyze() async -> MacroEnvironmentRating {
        // Veri çek
        let marketData = await YahooFinanceProvider.shared.fetchMacroIndicators()
        
        let cpi = try? await FREDProvider.shared.fetchCPI()
        let unemployment = try? await FREDProvider.shared.fetchUnemployment()
        let fedRate = try? await FREDProvider.shared.fetchFedFundsRate()
        let claims = try? await FREDProvider.shared.fetchInitialClaims()
        
        // Skorları hesapla (her biri 0-100)
        
        // 1. Öncü Göstergeler (Ağırlık: x1.5)
        let vixScore = calculateVIXScore(marketData.vix)           // VIX düşük = iyi
        let claimsScore = calculateClaimsScore(claims)              // İşsizlik başvurusu düşük = iyi
        let spyMomentum = calculateMomentumScore(marketData.spy)    // SPY yükseliyor = iyi
        let btcScore = calculateMomentumScore(marketData.btc)       // BTC yükseliyor = risk on
        
        // 2. Eşzamanlı Göstergeler (Ağırlık: x1.0)
        let laborScore = calculateLaborScore(unemployment)          // İşsizlik düşük = iyi
        let dxyScore = calculateDXYScore(marketData.dxy)            // DXY stabil = iyi
        
        // 3. Gecikmeli Göstergeler (Ağırlık: x0.8)
        let inflationScore = calculateInflationScore(cpi)           // Enflasyon düşük = iyi
        let rateScore = calculateRateScore(fedRate)                 // Faiz yükselmiyorsa = iyi
        let goldScore = calculateGoldScore(marketData.gld)          // Altın düşüyor = risk on
        
        // Kategori ortalamaları
        let leadingAvg = (vixScore + claimsScore + spyMomentum + btcScore) / 4
        let coincidentAvg = (laborScore + dxyScore) / 2
        let laggingAvg = (inflationScore + rateScore + goldScore) / 3
        
        // Ağırlıklı toplam
        let totalScore = (leadingAvg * 1.5 + coincidentAvg * 1.0 + laggingAvg * 0.8) / 3.3
        
        // Rejim belirle
        let regime: MacroRegime
        if totalScore >= 60 { regime = .riskOn }
        else if totalScore >= 40 { regime = .neutral }
        else { regime = .riskOff }
        
        return MacroEnvironmentRating(
            equityRiskScore: spyMomentum,
            volatilityScore: vixScore,
            safeHavenScore: goldScore,
            cryptoRiskScore: btcScore,
            interestRateScore: rateScore,
            currencyScore: dxyScore,
            inflationScore: inflationScore,
            laborScore: laborScore,
            growthScore: 50, // GDP için ayrı servis gerekir
            creditSpreadScore: 50,
            claimsScore: claimsScore,
            leadingScore: leadingAvg,
            coincidentScore: coincidentAvg,
            laggingScore: laggingAvg,
            numericScore: totalScore,
            letterGrade: letterGrade(for: totalScore),
            regime: regime,
            summary: generateSummary(regime: regime, score: totalScore),
            details: ""
        )
    }
    
    // MARK: - Skor Hesaplamaları
    
    private func calculateVIXScore(_ quote: YahooQuote?) -> Double {
        guard let vix = quote?.price else { return 50 }
        // VIX 12-15 ideal, 30+ panik
        if vix <= 15 { return 90 }
        if vix <= 20 { return 70 }
        if vix <= 25 { return 50 }
        if vix <= 30 { return 30 }
        return 10
    }
    
    private func calculateClaimsScore(_ claims: Double?) -> Double {
        guard let c = claims else { return 50 }
        // 200K altı iyi, 300K+ kötü
        if c <= 200000 { return 90 }
        if c <= 250000 { return 70 }
        if c <= 300000 { return 50 }
        return 30
    }
    
    private func calculateMomentumScore(_ quote: YahooQuote?) -> Double {
        guard let pct = quote?.changePercent else { return 50 }
        // +2%+ çok iyi, -2%+ çok kötü
        return min(100, max(0, 50 + pct * 10))
    }
    
    private func calculateLaborScore(_ unemployment: Double?) -> Double {
        guard let u = unemployment else { return 50 }
        // %4 altı iyi, %6+ kötü
        if u <= 4 { return 85 }
        if u <= 5 { return 65 }
        if u <= 6 { return 45 }
        return 25
    }
    
    private func calculateDXYScore(_ quote: YahooQuote?) -> Double {
        // DXY stabil olması iyi
        guard let pct = quote?.changePercent else { return 50 }
        return 50 - abs(pct) * 5 // Büyük hareketler kötü
    }
    
    private func calculateInflationScore(_ cpi: Double?) -> Double {
        guard let c = cpi else { return 50 }
        // %2 ideal, %4+ kötü
        if c <= 2 { return 90 }
        if c <= 3 { return 70 }
        if c <= 4 { return 50 }
        return 30
    }
    
    private func calculateRateScore(_ rate: Double?) -> Double {
        guard let r = rate else { return 50 }
        // %3 altı iyi, %5+ kötü
        if r <= 3 { return 80 }
        if r <= 4 { return 60 }
        if r <= 5 { return 40 }
        return 25
    }
    
    private func calculateGoldScore(_ quote: YahooQuote?) -> Double {
        guard let pct = quote?.changePercent else { return 50 }
        // Altın düşüyorsa risk iştahı var (ters ilişki)
        return min(100, max(0, 50 - pct * 8))
    }
    
    private func letterGrade(for score: Double) -> String {
        switch score {
        case 80...100: return "A"
        case 60..<80: return "B"
        case 40..<60: return "C"
        case 20..<40: return "D"
        default: return "F"
        }
    }
    
    private func generateSummary(regime: MacroRegime, score: Double) -> String {
        switch regime {
        case .riskOn: return "Makro ortam olumlu. Risk iştahı yüksek, büyüme beklentileri güçlü."
        case .neutral: return "Karışık sinyaller. Dikkatli pozisyonlanma önerilir."
        case .riskOff: return "Savunmacı ol. Volatilite yüksek, güvenli limanlara yönelim var."
        }
    }
}
```

## TradingViewModel Entegrasyonu

```swift
@Published var macroRating: MacroEnvironmentRating?

func loadMacroAnalysis() async {
    let rating = await MacroRegimeService.shared.analyze()
    await MainActor.run {
        self.macroRating = rating
    }
}
```

---

## API Key Alma (FRED)

1. <https://fred.stlouisfed.org/docs/api/api_key.html> adresine git
2. Hesap oluştur veya giriş yap
3. API key al (ücretsiz)
4. Secrets.swift'e yapıştır

Yahoo Finance API key gerektirmez.

```
