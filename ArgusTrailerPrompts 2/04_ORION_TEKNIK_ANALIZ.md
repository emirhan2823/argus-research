# PROMPT 4: ORION - TEKNİK ANALİZ MOTORU

## Açıklama

Teknik indikatörler ve yapısal analiz yapan Orion motoru.

---

## PROMPT

```
Argus Terminal için Orion (Teknik Analiz) motorunu oluştur.

## Özellikler
- Mum verileri ile çalışma
- 4 kategori: Yapı, Trend, Momentum, Pattern
- 15+ teknik indikatör
- Al/Sat/Tut önerisi

## IndicatorService.swift

```swift
import Foundation

class IndicatorService {
    static let shared = IndicatorService()
    
    // MARK: - Trend İndikatörleri
    
    func calculateSMA(prices: [Double], period: Int) -> [Double] {
        guard prices.count >= period else { return [] }
        var sma: [Double] = []
        for i in (period - 1)..<prices.count {
            let slice = prices[(i - period + 1)...i]
            sma.append(slice.reduce(0, +) / Double(period))
        }
        return sma
    }
    
    func calculateEMA(prices: [Double], period: Int) -> [Double] {
        guard prices.count >= period else { return [] }
        let multiplier = 2.0 / Double(period + 1)
        var ema: [Double] = [prices[0..<period].reduce(0, +) / Double(period)]
        
        for i in period..<prices.count {
            let value = (prices[i] - ema.last!) * multiplier + ema.last!
            ema.append(value)
        }
        return ema
    }
    
    // MARK: - Momentum İndikatörleri
    
    func calculateRSI(prices: [Double], period: Int = 14) -> Double? {
        guard prices.count > period else { return nil }
        
        var gains: [Double] = []
        var losses: [Double] = []
        
        for i in 1..<prices.count {
            let change = prices[i] - prices[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        }
        
        let avgGain = gains.suffix(period).reduce(0, +) / Double(period)
        let avgLoss = losses.suffix(period).reduce(0, +) / Double(period)
        
        if avgLoss == 0 { return 100 }
        let rs = avgGain / avgLoss
        return 100 - (100 / (1 + rs))
    }
    
    func calculateMACD(prices: [Double]) -> (macd: Double, signal: Double, histogram: Double)? {
        let ema12 = calculateEMA(prices: prices, period: 12)
        let ema26 = calculateEMA(prices: prices, period: 26)
        
        guard let last12 = ema12.last, let last26 = ema26.last else { return nil }
        
        let macdLine = last12 - last26
        let macdValues = zip(ema12.suffix(ema26.count), ema26).map { $0 - $1 }
        let signalLine = calculateEMA(prices: macdValues, period: 9).last ?? 0
        let histogram = macdLine - signalLine
        
        return (macdLine, signalLine, histogram)
    }
    
    func calculateStochastic(candles: [Candle], period: Int = 14) -> (k: Double, d: Double)? {
        guard candles.count >= period else { return nil }
        
        let recent = Array(candles.suffix(period))
        let highestHigh = recent.map { $0.high }.max() ?? 0
        let lowestLow = recent.map { $0.low }.min() ?? 0
        let currentClose = candles.last?.close ?? 0
        
        if highestHigh == lowestLow { return (50, 50) }
        
        let k = ((currentClose - lowestLow) / (highestHigh - lowestLow)) * 100
        let d = k // Basitleştirilmiş
        
        return (k, d)
    }
    
    // MARK: - Volatilite
    
    func calculateBollingerBands(prices: [Double], period: Int = 20, stdDev: Double = 2) -> (upper: Double, middle: Double, lower: Double)? {
        guard prices.count >= period else { return nil }
        
        let recent = Array(prices.suffix(period))
        let sma = recent.reduce(0, +) / Double(period)
        
        let variance = recent.map { pow($0 - sma, 2) }.reduce(0, +) / Double(period)
        let standardDeviation = sqrt(variance)
        
        return (
            sma + (stdDev * standardDeviation),
            sma,
            sma - (stdDev * standardDeviation)
        )
    }
    
    func calculateATR(candles: [Candle], period: Int = 14) -> Double? {
        guard candles.count >= period + 1 else { return nil }
        
        var trueRanges: [Double] = []
        for i in 1..<candles.count {
            let high = candles[i].high
            let low = candles[i].low
            let prevClose = candles[i-1].close
            
            let tr = max(high - low, abs(high - prevClose), abs(low - prevClose))
            trueRanges.append(tr)
        }
        
        return trueRanges.suffix(period).reduce(0, +) / Double(period)
    }
}
```

## OrionAnalysisService.swift

```swift
import Foundation

class OrionAnalysisService {
    static let shared = OrionAnalysisService()
    private let indicators = IndicatorService.shared
    
    func analyze(symbol: String, candles: [Candle]) -> OrionScoreResult {
        let closes = candles.map { $0.close }
        
        // 1. Yapı Skoru (0-35)
        let structureScore = calculateStructure(candles: candles, closes: closes)
        
        // 2. Trend Skoru (0-25)
        let trendScore = calculateTrend(closes: closes)
        
        // 3. Momentum Skoru (0-25)
        let momentumScore = calculateMomentum(candles: candles, closes: closes)
        
        // 4. Pattern Skoru (0-15)
        let patternScore = calculatePatterns(candles: candles)
        
        let total = structureScore + trendScore + momentumScore + patternScore
        
        let recommendation = getRecommendation(score: total)
        let reasoning = generateReasoning(
            structure: structureScore,
            trend: trendScore,
            momentum: momentumScore,
            pattern: patternScore
        )
        
        return OrionScoreResult(
            symbol: symbol,
            totalScore: total,
            structureScore: structureScore,
            trendScore: trendScore,
            momentumScore: momentumScore,
            patternScore: patternScore,
            recommendation: recommendation,
            reasoning: reasoning,
            calculatedAt: Date()
        )
    }
    
    // MARK: - Kategori Hesaplamaları
    
    private func calculateStructure(candles: [Candle], closes: [Double]) -> Double {
        var score = 17.5 // Başlangıç ortalama
        
        // SMA 50/200 ilişkisi
        let sma50 = indicators.calculateSMA(prices: closes, period: 50)
        let sma200 = indicators.calculateSMA(prices: closes, period: 200)
        
        if let last50 = sma50.last, let last200 = sma200.last {
            if last50 > last200 { score += 8 } // Golden cross
            else { score -= 8 } // Death cross
        }
        
        // Fiyat SMA'ların üstünde mi
        if let price = closes.last, let sma = sma50.last, price > sma {
            score += 5
        }
        
        return min(35, max(0, score))
    }
    
    private func calculateTrend(closes: [Double]) -> Double {
        var score = 12.5
        
        // EMA 12/26 (MACD benzeri)
        let ema12 = indicators.calculateEMA(prices: closes, period: 12)
        let ema26 = indicators.calculateEMA(prices: closes, period: 26)
        
        if let last12 = ema12.last, let last26 = ema26.last {
            if last12 > last26 { score += 6 } // Yükseliş trendi
            else { score -= 6 }
        }
        
        // Son 20 günlük eğim
        if closes.count >= 20 {
            let recent = Array(closes.suffix(20))
            if recent.last! > recent.first! { score += 6 }
            else { score -= 6 }
        }
        
        return min(25, max(0, score))
    }
    
    private func calculateMomentum(candles: [Candle], closes: [Double]) -> Double {
        var score = 12.5
        
        // RSI
        if let rsi = indicators.calculateRSI(prices: closes) {
            if rsi > 70 { score -= 5 } // Aşırı alım
            else if rsi < 30 { score += 5 } // Aşırı satım (alım fırsatı)
            else if rsi > 50 { score += 3 }
        }
        
        // Stokastik
        if let stoch = indicators.calculateStochastic(candles: candles) {
            if stoch.k > 80 { score -= 4 }
            else if stoch.k < 20 { score += 4 }
        }
        
        // MACD
        if let macd = indicators.calculateMACD(prices: closes) {
            if macd.histogram > 0 { score += 3 }
            else { score -= 3 }
        }
        
        return min(25, max(0, score))
    }
    
    private func calculatePatterns(candles: [Candle]) -> Double {
        var score = 7.5
        
        guard candles.count >= 3 else { return score }
        
        let last3 = Array(candles.suffix(3))
        
        // Engulfing pattern
        let c1 = last3[1], c2 = last3[2]
        let bullishEngulfing = c1.close < c1.open && c2.close > c2.open && c2.open < c1.close && c2.close > c1.open
        let bearishEngulfing = c1.close > c1.open && c2.close < c2.open && c2.open > c1.close && c2.close < c1.open
        
        if bullishEngulfing { score += 5 }
        if bearishEngulfing { score -= 5 }
        
        // Doji
        let lastCandle = candles.last!
        let bodySize = abs(lastCandle.close - lastCandle.open)
        let range = lastCandle.high - lastCandle.low
        if range > 0 && bodySize / range < 0.1 {
            score += 2 // Kararsızlık, dikkat
        }
        
        return min(15, max(0, score))
    }
    
    private func getRecommendation(score: Double) -> String {
        switch score {
        case 80...100: return "GÜÇLÜ AL"
        case 60..<80: return "AL"
        case 40..<60: return "TUT"
        case 20..<40: return "SAT"
        default: return "GÜÇLÜ SAT"
        }
    }
    
    private func generateReasoning(structure: Double, trend: Double, momentum: Double, pattern: Double) -> String {
        var parts: [String] = []
        
        if structure >= 25 { parts.append("Güçlü yapısal destek") }
        else if structure < 15 { parts.append("Zayıf yapı") }
        
        if trend >= 18 { parts.append("Yükseliş trendinde") }
        else if trend < 10 { parts.append("Düşüş trendinde") }
        
        if momentum >= 18 { parts.append("Güçlü momentum") }
        else if momentum < 10 { parts.append("Zayıf momentum") }
        
        return parts.isEmpty ? "Karışık sinyaller" : parts.joined(separator: ". ")
    }
}
```

## TradingViewModel Entegrasyonu

```swift
// Orion skorları
@Published var orionScores: [String: OrionScoreResult] = [:]

func loadOrionAnalysis(for symbol: String) async {
    guard let candles = candles[symbol], candles.count >= 50 else { return }
    
    let result = OrionAnalysisService.shared.analyze(symbol: symbol, candles: candles)
    
    await MainActor.run {
        self.orionScores[symbol] = result
    }
}
```

Build'i çalıştır ve test et.

```

---

## Beklenen Çıktı
- IndicatorService.swift (RSI, MACD, SMA, EMA, Bollinger, ATR, Stochastic)
- OrionAnalysisService.swift (4 kategori skorlama)
- TradingViewModel entegrasyonu
