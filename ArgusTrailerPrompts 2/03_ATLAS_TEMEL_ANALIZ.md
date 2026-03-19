# PROMPT 3: ATLAS - TEMEL ANALİZ MOTORU

## Açıklama

FMP API kullanarak fundamental (temel) analiz yapan Atlas motoru.

---

## PROMPT

```
Argus Terminal için Atlas (Temel Analiz) motorunu oluştur.

## Özellikler
- FMP API'den finansal veri çekme
- 4 kategori skorlama: Karlılık, Büyüme, Borç, Değerleme
- A-F not sistemi
- Özet ve detaylı analiz

## FMPProvider.swift

```swift
import Foundation

class FMPProvider {
    static let shared = FMPProvider()
    private let baseURL = "https://financialmodelingprep.com/api/v3"
    
    private var apiKey: String { Secrets.fmpAPIKey }
    
    // Şirket profili
    func fetchProfile(symbol: String) async throws -> CompanyProfile? {
        let url = URL(string: "\(baseURL)/profile/\(symbol)?apikey=\(apiKey)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let profiles = try JSONDecoder().decode([CompanyProfile].self, from: data)
        return profiles.first
    }
    
    // Finansal oranlar
    func fetchRatios(symbol: String) async throws -> FinancialRatios? {
        let url = URL(string: "\(baseURL)/ratios/\(symbol)?limit=1&apikey=\(apiKey)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let ratios = try JSONDecoder().decode([FinancialRatios].self, from: data)
        return ratios.first
    }
    
    // Gelir tablosu büyümesi
    func fetchIncomeGrowth(symbol: String) async throws -> IncomeGrowth? {
        let url = URL(string: "\(baseURL)/income-statement-growth/\(symbol)?limit=1&apikey=\(apiKey)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let growth = try JSONDecoder().decode([IncomeGrowth].self, from: data)
        return growth.first
    }
}

// FMP modelleri
struct CompanyProfile: Codable {
    let symbol: String?
    let companyName: String?
    let sector: String?
    let industry: String?
    let mktCap: Double?
    let price: Double?
    let beta: Double?
    let volAvg: Double?
    let description: String?
    let ceo: String?
    let website: String?
    let image: String?
}

struct FinancialRatios: Codable {
    let peRatio: Double?
    let priceToBookRatio: Double?
    let priceToSalesRatio: Double?
    let returnOnEquity: Double?
    let returnOnAssets: Double?
    let grossProfitMargin: Double?
    let operatingProfitMargin: Double?
    let netProfitMargin: Double?
    let debtEquityRatio: Double?
    let currentRatio: Double?
    let quickRatio: Double?
    let interestCoverage: Double?
    
    enum CodingKeys: String, CodingKey {
        case peRatio = "peRatioTTM"
        case priceToBookRatio = "priceToBookRatioTTM"
        case priceToSalesRatio = "priceToSalesRatioTTM"
        case returnOnEquity = "returnOnEquityTTM"
        case returnOnAssets = "returnOnAssetsTTM"
        case grossProfitMargin = "grossProfitMarginTTM"
        case operatingProfitMargin = "operatingProfitMarginTTM"
        case netProfitMargin = "netProfitMarginTTM"
        case debtEquityRatio = "debtEquityRatioTTM"
        case currentRatio = "currentRatioTTM"
        case quickRatio = "quickRatioTTM"
        case interestCoverage = "interestCoverageTTM"
    }
}

struct IncomeGrowth: Codable {
    let revenueGrowth: Double?
    let grossProfitGrowth: Double?
    let netIncomeGrowth: Double?
    let epsgrowth: Double?
    
    enum CodingKeys: String, CodingKey {
        case revenueGrowth = "growthRevenue"
        case grossProfitGrowth = "growthGrossProfit"
        case netIncomeGrowth = "growthNetIncome"
        case epsgrowth = "growthEPS"
    }
}
```

## FundamentalScoreEngine.swift

```swift
import Foundation

class FundamentalScoreEngine {
    static let shared = FundamentalScoreEngine()
    
    func calculateScore(
        ratios: FinancialRatios,
        growth: IncomeGrowth?,
        symbol: String
    ) -> FundamentalScoreResult {
        
        // 1. Karlılık Skoru (0-30)
        let profitabilityScore = calculateProfitability(ratios)
        
        // 2. Büyüme Skoru (0-25)
        let growthScore = calculateGrowth(growth)
        
        // 3. Borç Skoru (0-25)
        let debtScore = calculateDebt(ratios)
        
        // 4. Değerleme Skoru (0-20)
        let valuationScore = calculateValuation(ratios)
        
        let total = profitabilityScore + growthScore + debtScore + valuationScore
        
        let grade = letterGrade(for: total)
        let summary = generateSummary(total: total, grade: grade)
        
        return FundamentalScoreResult(
            symbol: symbol,
            totalScore: total,
            profitabilityScore: profitabilityScore,
            growthScore: growthScore,
            debtScore: debtScore,
            valuationScore: valuationScore,
            letterGrade: grade,
            summary: summary,
            financials: nil,
            calculatedAt: Date()
        )
    }
    
    // MARK: - Kategori Hesaplamaları
    
    private func calculateProfitability(_ r: FinancialRatios) -> Double {
        var score = 0.0
        
        // ROE (0-10) - %15+ iyi
        if let roe = r.returnOnEquity {
            score += min(10, max(0, roe * 100 / 1.5))
        }
        
        // Net Margin (0-10) - %10+ iyi
        if let nm = r.netProfitMargin {
            score += min(10, max(0, nm * 100))
        }
        
        // Gross Margin (0-10) - %30+ iyi
        if let gm = r.grossProfitMargin {
            score += min(10, max(0, gm * 100 / 3))
        }
        
        return min(30, score)
    }
    
    private func calculateGrowth(_ g: IncomeGrowth?) -> Double {
        guard let g = g else { return 12.5 } // Ortalama
        var score = 0.0
        
        // Gelir Büyümesi (0-12.5) - %20+ iyi
        if let rev = g.revenueGrowth {
            score += min(12.5, max(0, (rev + 0.1) * 50))
        }
        
        // Net Gelir Büyümesi (0-12.5) - %25+ iyi
        if let ni = g.netIncomeGrowth {
            score += min(12.5, max(0, (ni + 0.1) * 40))
        }
        
        return min(25, score)
    }
    
    private func calculateDebt(_ r: FinancialRatios) -> Double {
        var score = 25.0 // Başlangıç tam puan
        
        // D/E Ratio - 1.0+ ceza
        if let de = r.debtEquityRatio, de > 1.0 {
            score -= min(10, (de - 1.0) * 5)
        }
        
        // Current Ratio - 1.5 altı ceza
        if let cr = r.currentRatio, cr < 1.5 {
            score -= min(8, (1.5 - cr) * 5)
        }
        
        // Interest Coverage - 3 altı ceza
        if let ic = r.interestCoverage, ic < 3 {
            score -= min(7, (3 - ic) * 2)
        }
        
        return max(0, score)
    }
    
    private func calculateValuation(_ r: FinancialRatios) -> Double {
        var score = 10.0 // Başlangıç ortalama
        
        // P/E Oranı - 15-25 arası ideal
        if let pe = r.peRatio {
            if pe < 0 { score -= 5 }
            else if pe < 15 { score += 5 }
            else if pe > 30 { score -= 5 }
        }
        
        // P/B Oranı - 3 altı iyi
        if let pb = r.priceToBookRatio {
            if pb < 3 { score += 5 }
            else if pb > 5 { score -= 5 }
        }
        
        return min(20, max(0, score))
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
    
    private func generateSummary(total: Double, grade: String) -> String {
        switch grade {
        case "A": return "Mükemmel finansal sağlık. Güçlü bilanço ve karlılık."
        case "B": return "İyi finansal durum. Sağlam temeller."
        case "C": return "Ortalama finansal performans. İzlenmeli."
        case "D": return "Zayıf finansal göstergeler. Dikkatli olunmalı."
        default: return "Ciddi finansal sorunlar. Riskli."
        }
    }
}
```

## TradingViewModel Entegrasyonu

TradingViewModel'e ekle:

```swift
// Atlas skorları
@Published var fundamentalScores: [String: FundamentalScoreResult] = [:]

func loadFundamentals(for symbol: String) async {
    do {
        let ratios = try await FMPProvider.shared.fetchRatios(symbol: symbol)
        let growth = try await FMPProvider.shared.fetchIncomeGrowth(symbol: symbol)
        
        if let ratios = ratios {
            let score = FundamentalScoreEngine.shared.calculateScore(
                ratios: ratios,
                growth: growth,
                symbol: symbol
            )
            await MainActor.run {
                self.fundamentalScores[symbol] = score
            }
        }
    } catch {
        print("❌ Atlas error: \(error)")
    }
}
```

Build'i çalıştır ve FMP API key'i Secrets.swift'e ekleyerek test et.

```

---

## API Key Alma
1. https://site.financialmodelingprep.com/ adresine git
2. Ücretsiz hesap oluştur
3. Dashboard'dan API key'i kopyala
4. Secrets.swift'e yapıştır
