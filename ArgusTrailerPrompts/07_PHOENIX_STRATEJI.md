# PROMPT 7: PHOENIX - STRATEJİ MOTORU

## Açıklama

Tüm motorları birleştirerek nihai al/sat sinyali üreten Phoenix stratejisi.

---

## PROMPT

```
Argus Terminal için Phoenix (Strateji) motorunu oluştur.

## Özellikler
- Atlas, Orion, Aether, Hermes skorlarını birleştirme
- Ağırlıklı toplam hesaplama
- Al/Sat/Tut sinyali üretme
- Güven skoru ve hedef fiyat

## PhoenixEngine.swift

```swift
import Foundation

class PhoenixEngine {
    static let shared = PhoenixEngine()
    
    // Bileşen ağırlıkları (toplam 100)
    private let weights = PhoenixWeights(
        technical: 40,      // Orion - Teknik Analiz
        fundamental: 30,    // Atlas - Temel Analiz
        macro: 20,          // Aether - Makro
        sentiment: 10       // Hermes - Haber
    )
    
    func calculateSignal(
        symbol: String,
        orion: OrionScoreResult?,
        atlas: FundamentalScoreResult?,
        aether: MacroEnvironmentRating?,
        hermes: HermesResult?,
        currentPrice: Double
    ) -> PhoenixResult {
        
        // 1. Bileşen skorlarını normalize et (0-100)
        let technicalScore = (orion?.totalScore ?? 50) // Zaten 0-100
        let fundamentalScore = (atlas?.totalScore ?? 50) // Zaten 0-100
        let macroScore = aether?.numericScore ?? 50 // Zaten 0-100
        let sentimentScore = hermes?.sentimentScore ?? 50 // Zaten 0-100
        
        // 2. Ağırlıklı toplam
        let weightedScore = (
            technicalScore * Double(weights.technical) +
            fundamentalScore * Double(weights.fundamental) +
            macroScore * Double(weights.macro) +
            sentimentScore * Double(weights.sentiment)
        ) / 100
        
        // 3. Sinyali belirle
        let signal = determineSignal(score: weightedScore)
        
        // 4. Güven skoru (bileşenlerin uyumu)
        let confidence = calculateConfidence(
            technical: technicalScore,
            fundamental: fundamentalScore,
            macro: macroScore,
            sentiment: sentimentScore
        )
        
        // 5. Hedef fiyat ve stop loss
        let (priceTarget, stopLoss) = calculateLevels(
            signal: signal,
            currentPrice: currentPrice,
            confidence: confidence
        )
        
        // 6. Açıklama oluştur
        let reasoning = generateReasoning(
            signal: signal,
            technical: technicalScore,
            fundamental: fundamentalScore,
            macro: macroScore,
            sentiment: sentimentScore
        )
        
        return PhoenixResult(
            symbol: symbol,
            signal: signal,
            confidence: confidence,
            priceTarget: priceTarget,
            stopLoss: stopLoss,
            reasoning: reasoning,
            technicalScore: technicalScore * Double(weights.technical) / 100,
            fundamentalScore: fundamentalScore * Double(weights.fundamental) / 100,
            macroScore: macroScore * Double(weights.macro) / 100,
            sentimentScore: sentimentScore * Double(weights.sentiment) / 100,
            calculatedAt: Date()
        )
    }
    
    // MARK: - Sinyal Belirleme
    
    private func determineSignal(score: Double) -> PhoenixSignal {
        switch score {
        case 75...100: return .strongBuy
        case 60..<75: return .buy
        case 40..<60: return .hold
        case 25..<40: return .sell
        default: return .strongSell
        }
    }
    
    // MARK: - Güven Skoru
    
    private func calculateConfidence(technical: Double, fundamental: Double, macro: Double, sentiment: Double) -> Double {
        let scores = [technical, fundamental, macro, sentiment]
        let avg = scores.reduce(0, +) / Double(scores.count)
        
        // Standart sapma hesapla
        let variance = scores.map { pow($0 - avg, 2) }.reduce(0, +) / Double(scores.count)
        let stdDev = sqrt(variance)
        
        // Düşük standart sapma = yüksek uyum = yüksek güven
        // stdDev 0 ise güven 100, stdDev 30+ ise güven düşük
        let confidence = max(0, min(100, 100 - stdDev * 2))
        
        return confidence
    }
    
    // MARK: - Fiyat Seviyeleri
    
    private func calculateLevels(signal: PhoenixSignal, currentPrice: Double, confidence: Double) -> (target: Double?, stopLoss: Double?) {
        let riskReward: Double = 2.0 // 1:2 risk/reward
        
        switch signal {
        case .strongBuy:
            let target = currentPrice * (1 + 0.15 * (confidence / 100)) // Max %15
            let stop = currentPrice * 0.95 // %5 stop
            return (target, stop)
            
        case .buy:
            let target = currentPrice * (1 + 0.10 * (confidence / 100)) // Max %10
            let stop = currentPrice * 0.93 // %7 stop
            return (target, stop)
            
        case .hold:
            return (nil, nil)
            
        case .sell:
            let target = currentPrice * (1 - 0.10 * (confidence / 100)) // Short hedef
            let stop = currentPrice * 1.07 // Short stop
            return (target, stop)
            
        case .strongSell:
            let target = currentPrice * (1 - 0.15 * (confidence / 100)) // Short hedef
            let stop = currentPrice * 1.05 // Short stop
            return (target, stop)
        }
    }
    
    // MARK: - Açıklama Üretme
    
    private func generateReasoning(signal: PhoenixSignal, technical: Double, fundamental: Double, macro: Double, sentiment: Double) -> String {
        var parts: [String] = []
        
        // En güçlü faktör
        let factors: [(String, Double)] = [
            ("Teknik", technical),
            ("Temel", fundamental),
            ("Makro", macro),
            ("Duygu", sentiment)
        ]
        
        let sorted = factors.sorted { $0.1 > $1.1 }
        
        if let strongest = sorted.first, strongest.1 >= 65 {
            parts.append("\(strongest.0) analiz güçlü destek veriyor")
        }
        
        if let weakest = sorted.last, weakest.1 <= 35 {
            parts.append("\(weakest.0) analiz zayıf")
        }
        
        // Genel değerlendirme
        switch signal {
        case .strongBuy:
            parts.append("Tüm göstergeler uyumlu, güçlü alım fırsatı")
        case .buy:
            parts.append("Olumlu koşullar, alım düşünülebilir")
        case .hold:
            parts.append("Karışık sinyaller, beklemek mantıklı")
        case .sell:
            parts.append("Olumsuz koşullar, satış düşünülebilir")
        case .strongSell:
            parts.append("Ciddi uyarı sinyalleri, pozisyondan çık")
        }
        
        return parts.joined(separator: ". ")
    }
}

struct PhoenixWeights {
    let technical: Int
    let fundamental: Int
    let macro: Int
    let sentiment: Int
}
```

## TradingViewModel Entegrasyonu

```swift
@Published var phoenixResults: [String: PhoenixResult] = [:]

func calculatePhoenixSignal(for symbol: String) async {
    let orion = orionScores[symbol]
    let atlas = fundamentalScores[symbol]
    let aether = macroRating
    let hermes = hermesResults[symbol]
    let price = quotes[symbol]?.currentPrice ?? 0
    
    let result = PhoenixEngine.shared.calculateSignal(
        symbol: symbol,
        orion: orion,
        atlas: atlas,
        aether: aether,
        hermes: hermes,
        currentPrice: price
    )
    
    await MainActor.run {
        self.phoenixResults[symbol] = result
    }
}

// Tüm analizleri sırayla çalıştır
func loadFullAnalysis(for symbol: String) async {
    isLoading = true
    
    // 1. Fiyat verilerini çek
    await loadQuote(for: symbol)
    await loadCandles(for: symbol)
    
    // 2. Paralel analizler
    async let _ = loadFundamentals(for: symbol)      // Atlas
    async let _ = loadOrionAnalysis(for: symbol)     // Orion
    async let _ = loadMacroAnalysis()                // Aether
    async let _ = loadNewsAnalysis(for: symbol)      // Hermes
    
    // Bekle
    try? await Task.sleep(nanoseconds: 2_000_000_000)
    
    // 3. Phoenix sinyali
    await calculatePhoenixSignal(for: symbol)
    
    isLoading = false
}
```

---

## Phoenix UI Bileşeni (PhoenixCard.swift)

```swift
import SwiftUI

struct PhoenixCard: View {
    let result: PhoenixResult
    
    var body: some View {
        VStack(spacing: 16) {
            // Header
            HStack {
                Image(systemName: "flame.fill")
                    .foregroundColor(.orange)
                Text("PHOENIX")
                    .font(.headline)
                    .foregroundColor(.orange)
                Spacer()
                Text(result.signal.rawValue)
                    .font(.caption)
                    .bold()
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(signalColor.opacity(0.2))
                    .foregroundColor(signalColor)
                    .cornerRadius(8)
            }
            
            // Güven Göstergesi
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("Güven")
                        .font(.caption)
                        .foregroundColor(.gray)
                    Spacer()
                    Text("\(Int(result.confidence))%")
                        .font(.caption)
                        .bold()
                        .foregroundColor(.white)
                }
                
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.gray.opacity(0.3))
                            .frame(height: 6)
                        
                        RoundedRectangle(cornerRadius: 4)
                            .fill(signalColor)
                            .frame(width: geo.size.width * result.confidence / 100, height: 6)
                    }
                }
                .frame(height: 6)
            }
            
            // Bileşen Skorları
            HStack(spacing: 16) {
                ScoreIndicator(label: "Teknik", score: result.technicalScore, maxScore: 40)
                ScoreIndicator(label: "Temel", score: result.fundamentalScore, maxScore: 30)
                ScoreIndicator(label: "Makro", score: result.macroScore, maxScore: 20)
                ScoreIndicator(label: "Duygu", score: result.sentimentScore, maxScore: 10)
            }
            
            // Hedefler
            if result.priceTarget != nil || result.stopLoss != nil {
                HStack {
                    if let target = result.priceTarget {
                        VStack {
                            Text("Hedef")
                                .font(.caption2)
                                .foregroundColor(.gray)
                            Text(String(format: "$%.2f", target))
                                .font(.caption)
                                .bold()
                                .foregroundColor(.green)
                        }
                    }
                    
                    Spacer()
                    
                    if let stop = result.stopLoss {
                        VStack {
                            Text("Stop")
                                .font(.caption2)
                                .foregroundColor(.gray)
                            Text(String(format: "$%.2f", stop))
                                .font(.caption)
                                .bold()
                                .foregroundColor(.red)
                        }
                    }
                }
                .padding(.top, 8)
            }
            
            // Açıklama
            Text(result.reasoning)
                .font(.caption2)
                .foregroundColor(.gray)
                .multilineTextAlignment(.leading)
        }
        .padding()
        .background(Theme.secondaryBackground)
        .cornerRadius(16)
    }
    
    private var signalColor: Color {
        switch result.signal {
        case .strongBuy, .buy: return .green
        case .hold: return .yellow
        case .sell, .strongSell: return .red
        }
    }
}

struct ScoreIndicator: View {
    let label: String
    let score: Double
    let maxScore: Double
    
    var body: some View {
        VStack(spacing: 4) {
            Text(label)
                .font(.caption2)
                .foregroundColor(.gray)
            
            ZStack {
                Circle()
                    .stroke(Color.gray.opacity(0.3), lineWidth: 3)
                    .frame(width: 36, height: 36)
                
                Circle()
                    .trim(from: 0, to: score / maxScore)
                    .stroke(scoreColor, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                    .frame(width: 36, height: 36)
                    .rotationEffect(.degrees(-90))
                
                Text("\(Int(score))")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(.white)
            }
        }
    }
    
    private var scoreColor: Color {
        let ratio = score / maxScore
        if ratio >= 0.7 { return .green }
        if ratio >= 0.4 { return .yellow }
        return .red
    }
}
```
