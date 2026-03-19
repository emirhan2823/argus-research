# PROMPT 2: TEMA VE VERİ MODELLERİ

## Açıklama

Dark theme tasarımı ve tüm veri modelleri oluşturulur.

---

## PROMPT

```
Argus Terminal için premium dark theme ve veri modellerini oluştur.

## Theme.swift

```swift
import SwiftUI

struct Theme {
    // Ana renkler
    static let background = Color(red: 0.06, green: 0.07, blue: 0.10)
    static let secondaryBackground = Color(red: 0.10, green: 0.11, blue: 0.15)
    static let cardBackground = Color(red: 0.12, green: 0.13, blue: 0.18)
    
    // Metin renkleri
    static let textPrimary = Color.white
    static let textSecondary = Color(white: 0.6)
    
    // Accent renkler
    static let tint = Color.cyan
    static let border = Color(white: 0.2)
    
    // Pozitif/Negatif
    static let positive = Color.green
    static let negative = Color.red
    static let neutral = Color.yellow
}

// Color extension for hex
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
```

## OrionModels.swift (Teknik Analiz)

```swift
import Foundation

// Teknik analiz sonucu
struct OrionScoreResult: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let totalScore: Double           // 0-100
    let structureScore: Double       // Yapı: 0-35
    let trendScore: Double           // Trend: 0-25
    let momentumScore: Double        // Momentum: 0-25
    let patternScore: Double         // Pattern: 0-15
    let recommendation: String       // "GÜÇLÜ AL", "AL", "TUT", "SAT", "GÜÇLÜ SAT"
    let reasoning: String            // Açıklama
    let calculatedAt: Date
    
    var letterGrade: String {
        switch totalScore {
        case 80...100: return "A"
        case 60..<80: return "B"
        case 40..<60: return "C"
        case 20..<40: return "D"
        default: return "F"
        }
    }
}
```

## FundamentalModels.swift (Temel Analiz)

```swift
import Foundation

// Finansal veriler
struct FinancialsData: Codable {
    // Karlılık
    let revenueGrowth: Double?
    let netIncomeGrowth: Double?
    let grossMargin: Double?
    let operatingMargin: Double?
    let netMargin: Double?
    let roe: Double?
    let roa: Double?
    
    // Değerleme
    let peRatio: Double?
    let pbRatio: Double?
    let psRatio: Double?
    let evToEbitda: Double?
    
    // Borç
    let debtToEquity: Double?
    let currentRatio: Double?
    let quickRatio: Double?
    let interestCoverage: Double?
    
    // Büyüme
    let epsGrowth: Double?
    let fcfGrowth: Double?
}

// Temel analiz sonucu
struct FundamentalScoreResult: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let totalScore: Double           // 0-100
    let profitabilityScore: Double   // Karlılık: 0-30
    let growthScore: Double          // Büyüme: 0-25
    let debtScore: Double            // Borç: 0-25
    let valuationScore: Double       // Değerleme: 0-20
    let letterGrade: String          // A, B, C, D, F
    let summary: String
    let financials: FinancialsData?
    let calculatedAt: Date
}
```

## MacroModels.swift (Makro Analiz)

```swift
import Foundation

enum MacroRegime: String, Codable {
    case riskOn = "Risk İştahı Yüksek"
    case neutral = "Nötr / Kararsız"
    case riskOff = "Risk Kaçınma"
    
    var displayName: String { rawValue }
}

struct MacroEnvironmentRating: Codable, Identifiable {
    var id: String { UUID().uuidString }
    
    // Bireysel skorlar (0-100)
    let equityRiskScore: Double      // SPY momentum
    let volatilityScore: Double      // VIX (ters)
    let safeHavenScore: Double       // GLD (ters)
    let cryptoRiskScore: Double      // BTC momentum
    let interestRateScore: Double    // Faiz ortamı
    let currencyScore: Double        // DXY durumu
    let inflationScore: Double       // CPI durumu
    let laborScore: Double           // İstihdam
    let growthScore: Double          // GDP büyümesi
    let creditSpreadScore: Double    // Kredi spreadi
    let claimsScore: Double          // İşsizlik başvuruları
    
    // Kategori skorları
    let leadingScore: Double?        // Öncü göstergeler
    let coincidentScore: Double?     // Eşzamanlı göstergeler
    let laggingScore: Double?        // Gecikmeli göstergeler
    
    // Toplam
    let numericScore: Double         // 0-100
    let letterGrade: String          // A, B, C, D, F
    let regime: MacroRegime
    let summary: String
    let details: String
}
```

## PhoenixModels.swift (Strateji)

```swift
import Foundation

enum PhoenixSignal: String, Codable {
    case strongBuy = "GÜÇLÜ AL"
    case buy = "AL"
    case hold = "TUT"
    case sell = "SAT"
    case strongSell = "GÜÇLÜ SAT"
    
    var color: String {
        switch self {
        case .strongBuy, .buy: return "green"
        case .hold: return "yellow"
        case .sell, .strongSell: return "red"
        }
    }
}

struct PhoenixResult: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let signal: PhoenixSignal
    let confidence: Double           // 0-100
    let priceTarget: Double?
    let stopLoss: Double?
    let reasoning: String
    
    // Bileşen skorları
    let technicalScore: Double       // Teknik: 0-40
    let fundamentalScore: Double     // Temel: 0-30
    let macroScore: Double           // Makro: 0-20
    let sentimentScore: Double       // Duygu: 0-10
    
    let calculatedAt: Date
}
```

Bu modelleri oluştur ve build'in çalıştığını doğrula.

```

---

## Beklenen Çıktı
- Theme.swift (dark mode renkleri)
- OrionModels.swift (teknik analiz)
- FundamentalModels.swift (temel analiz)
- MacroModels.swift (makro analiz)
- PhoenixModels.swift (strateji)
