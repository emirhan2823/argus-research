# PROMPT 2: TEMA VE VERİ MODELLERİ (v2 - Birebir)

## ⚠️ ÖNEMLİ

Bu prompt, Argus Terminal'in **gerçek** renk paletini ve veri yapılarını içerir. AI'a verdiğinizde **hiçbir değeri değiştirmeyin**.

---

## PROMPT (Kopyalayın ve AI'a Verin)

```
Argus Terminal için aşağıdaki TEMA ve MODELLERİ birebir uygula.

## 1. THEME.swift (Renk Paleti)

MUTLAK HEX KODLARI - DEĞİŞTİRME:

```swift
import SwiftUI

struct Theme {
    // ═══════════════════════════════════════
    // BACKGROUNDS (Deep Space)
    // ═══════════════════════════════════════
    static let background = Color(hex: "050505")            // #050505 Void Black
    static let secondaryBackground = Color(hex: "0A0A0E")   // #0A0A0E Deep Nebula  
    static let cardBackground = Color(hex: "12121A")        // #12121A Glass Base
    static let border = Color(hex: "2D3748").opacity(0.3)   // #2D3748 @ 30%
    static let groupedBackground = background
    
    // ═══════════════════════════════════════
    // BRAND IDENTITY
    // ═══════════════════════════════════════
    static let primary = Color(hex: "FFD700")   // #FFD700 Argus Gold (Wisdom)
    static let accent = Color(hex: "00A8FF")    // #00A8FF Cyber Blue (Tech)
    static let tint = primary
    
    // ═══════════════════════════════════════
    // TYPOGRAPHY
    // ═══════════════════════════════════════
    static let textPrimary = Color.white
    static let textSecondary = Color(hex: "8A8F98") // #8A8F98 Stardust Gray
    
    // ═══════════════════════════════════════
    // SIGNAL COLORS (Neon)
    // ═══════════════════════════════════════
    static let positive = Color(hex: "00FFA3")  // #00FFA3 Cyber Green
    static let negative = Color(hex: "FF2E55")  // #FF2E55 Crimson Red
    static let warning = Color(hex: "FFD740")   // #FFD740 Amber
    static let neutral = Color(hex: "565E6D")   // #565E6D Steel Gray
    
    static let chartUp = positive
    static let chartDown = negative
    
    // ═══════════════════════════════════════
    // LAYOUT CONSTANTS
    // ═══════════════════════════════════════
    struct Spacing {
        static let small: CGFloat = 8
        static let medium: CGFloat = 16
        static let large: CGFloat = 24
        static let xLarge: CGFloat = 32
    }
    
    struct Radius {
        static let small: CGFloat = 8
        static let medium: CGFloat = 12
        static let large: CGFloat = 16
        static let pill: CGFloat = 999
    }
    
    // HELPERS
    static func colorForScore(_ score: Double) -> Color {
        if score >= 50 { return positive }
        else if score <= -50 { return negative }
        else { return neutral }
    }
}

// ═══════════════════════════════════════
// COLOR HEX EXTENSION (ZORUNLU)
// ═══════════════════════════════════════
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 6: (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default: (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(.sRGB, red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255, opacity: Double(a) / 255)
    }
}
```

## 2. 7 MODÜL RENKLERİ (SanctumTheme)

```swift
struct SanctumTheme {
    // Background Gradient (Radial)
    static let bg = RadialGradient(
        colors: [Color(hex: "080b14"), Color(hex: "020205")], 
        center: .center, 
        startRadius: 50, 
        endRadius: 500
    )
    
    // ═══════════════════════════════════════
    // 7 ANALİZ MODÜLÜ RENKLERİ
    // ═══════════════════════════════════════
    static let orionColor = Color(hex: "00ff9d")   // #00FF9D Cyber Green - TEKNİK ANALİZ
    static let atlasColor = Color(hex: "ffd700")   // #FFD700 Gold - TEMEL ANALİZ
    static let aetherColor = Color(hex: "bd00ff")  // #BD00FF Purple - MAKRO EKONOMİ
    static let hermesColor = Color(hex: "00d0ff")  // #00D0FF Cyan - HABER ANALİZİ
    static let athenaColor = Color(hex: "ff0055")  // #FF0055 Neon Red - SMART BETA
    static let demeterColor = Color(hex: "8b5a2b") // #8B5A2B Bronze - SEKTÖR ANALİZİ
    static let chironColor = Color(hex: "ffffff")  // #FFFFFF White - ÖĞRENME/RİSK
    
    // Glass Material
    static let glassMaterial = Material.ultraThinMaterial
}
```

## 3. VERİ MODELLERİ

### Quote (Fiyat Verisi)

```swift
struct Quote: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    var currentPrice: Double
    var previousClose: Double?
    var d: Double?               // Günlük değişim $
    var dp: Double?              // Günlük değişim %
    var h: Double?               // Günün en yüksek
    var l: Double?               // Günün en düşük
    var o: Double?               // Açılış
    var t: TimeInterval?         // Unix timestamp
    var timestamp: Date { Date(timeIntervalSince1970: t ?? Date().timeIntervalSince1970) }
}
```

### Candle (OHLC Mum Verisi)

```swift
struct Candle: Codable, Identifiable {
    var id: String { "\(date.timeIntervalSince1970)" }
    let date: Date
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double?
    
    // Hesaplanmış değerler
    var isBullish: Bool { close > open }
    var bodySize: Double { abs(close - open) }
    var range: Double { high - low }
}
```

### OrionScoreResult (Teknik Analiz)

```swift
struct OrionScoreResult: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    
    // Ana skor ve alt bileşenler
    let score: Double              // 0-100 toplam
    let structureScore: Double     // 0-35 (Yapı: Destek/Direnç)
    let trendScore: Double         // 0-25 (Trend: SMA/EMA)
    let momentumScore: Double      // 0-25 (Momentum: RSI/MACD)
    let patternScore: Double       // 0-15 (Pattern: Formasyonlar)
    
    // Sonuç
    let recommendation: String     // "GÜÇLÜ AL", "AL", "TUT", "SAT", "GÜÇLÜ SAT"
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
    
    var totalScore: Double { score } // Alias for compatibility
}
```

### FundamentalScore (Temel Analiz)

```swift
struct FundamentalScore: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let totalScore: Double         // 0-100
    let profitabilityScore: Double // 0-30
    let growthScore: Double        // 0-25
    let debtScore: Double          // 0-25
    let valuationScore: Double     // 0-20
    let letterGrade: String
    let summary: String
    let isETF: Bool
    let financials: FinancialsData?
    let calculatedAt: Date
}

struct FinancialsData: Codable {
    let symbol: String
    let marketCap: Double?
    let peRatio: Double?
    let pbRatio: Double?
    let roe: Double?
    let revenueGrowth: Double?
    let debtToEquity: Double?
    let grossMargin: Double?
    let operatingMargin: Double?
    let profitMargin: Double?
    let currentRatio: Double?
    let dividendYield: Double?
}
```

### MacroEnvironmentRating (Makro Analiz)

```swift
enum MacroRegime: String, Codable {
    case riskOn = "Risk İştahı Yüksek"
    case neutral = "Nötr / Kararsız"
    case riskOff = "Risk Kaçınma"
    
    var displayName: String { rawValue }
}

struct MacroEnvironmentRating: Codable {
    // Kategori skorları (0-100)
    let leadingScore: Double?      // Öncü göstergeler
    let coincidentScore: Double?   // Eşzamanlı göstergeler
    let laggingScore: Double?      // Gecikmeli göstergeler
    
    // Bireysel skorlar
    let equityRiskScore: Double    // SPY momentum
    let volatilityScore: Double    // VIX (ters)
    let interestRateScore: Double  // Faiz ortamı
    let inflationScore: Double     // CPI durumu
    let laborScore: Double         // İstihdam
    
    // Sonuç
    let numericScore: Double       // 0-100 toplam
    let letterGrade: String        // A, B, C, D, F
    let regime: MacroRegime
    let summary: String
    let details: String
}
```

### SignalAction (Sinyal Enum)

```swift
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
```

### NewsSentiment (Haber Duygu Analizi)

```swift
enum NewsSentiment: String, Codable {
    case strongPositive = "Çok Olumlu"
    case weakPositive = "Olumlu"
    case neutral = "Nötr"
    case weakNegative = "Olumsuz"
    case strongNegative = "Çok Olumsuz"
    
    var emoji: String {
        switch self {
        case .strongPositive: return "🚀"
        case .weakPositive: return "📈"
        case .neutral: return "➖"
        case .weakNegative: return "📉"
        case .strongNegative: return "💥"
        }
    }
}

struct NewsInsight: Codable, Identifiable {
    let id: UUID
    let symbol: String
    let headline: String
    let sentiment: NewsSentiment
    let confidence: Double         // 0-1
    let impactScore: Double        // 0-100
    let createdAt: Date
}
```

Bu dosyaları oluştur ve build'in çalıştığını doğrula.

```

---

## Renk Haritası Özeti

| Renk Adı | Hex Kodu | Kullanım |
|----------|----------|----------|
| Void Black | #050505 | Ana arka plan |
| Deep Nebula | #0A0A0E | İkincil arka plan |
| Glass Base | #12121A | Kart arka planı |
| Argus Gold | #FFD700 | Marka rengi |
| Cyber Blue | #00A8FF | Accent |
| Cyber Green | #00FFA3 | Pozitif/Yükseliş |
| Crimson Red | #FF2E55 | Negatif/Düşüş |
| Amber | #FFD740 | Uyarı |
| Steel Gray | #565E6D | Nötr |
| Stardust Gray | #8A8F98 | İkincil metin |

## Modül Renkleri

| Modül | Hex Kodu | Görev |
|-------|----------|-------|
| Orion | #00FF9D | Teknik Analiz |
| Atlas | #FFD700 | Temel Analiz |
| Aether | #BD00FF | Makro Ekonomi |
| Hermes | #00D0FF | Haber Analizi |
| Athena | #FF0055 | Smart Beta |
| Demeter | #8B5A2B | Sektör Rotasyonu |
| Chiron | #FFFFFF | Öğrenme/Risk |
