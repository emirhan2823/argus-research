import Foundation

// MARK: - BIST Faktör Engine
// Value, Momentum, Quality, Dividend faktörlerini hesaplar
// BorsaPy verilerini kullanır

actor BistFaktorEngine {
    static let shared = BistFaktorEngine()
    
    private init() {}
    
    // MARK: - Ana Analiz
    
    func analyze(symbol: String) async throws -> BistFaktorResult {
        let cleanSymbol = symbol.uppercased()
            .replacingOccurrences(of: ".IS", with: "")
        
        // Verileri Çek
        let financials = try await BorsaPyProvider.shared.getFinancialStatements(symbol: cleanSymbol)
        let quote = try? await BorsaPyProvider.shared.getBistQuote(symbol: cleanSymbol)
        let history = try? await BorsaPyProvider.shared.getBistHistory(symbol: cleanSymbol, days: 60)
        let dividends = try? await BorsaPyProvider.shared.getDividends(symbol: cleanSymbol)
        
        // Faktörleri Hesapla
        let valueScore = calculateValueFactor(financials, quote: quote)
        let momentumScore = calculateMomentumFactor(history)
        let qualityScore = calculateQualityFactor(financials)
        let dividendScore = calculateDividendFactor(dividends, quote: quote)
        
        // Toplam Skor (Eşit ağırlık)
        let totalScore = (valueScore.score + momentumScore.score + qualityScore.score + dividendScore.score) / 4
        
        return BistFaktorResult(
            symbol: cleanSymbol,
            totalScore: totalScore,
            factors: [valueScore, momentumScore, qualityScore, dividendScore],
            timestamp: Date()
        )
    }
    
    // MARK: - Value Faktör (Ucuzluk)
    
    private func calculateValueFactor(_ f: BistFinancials, quote: BistQuote?) -> BistFaktor {
        var score: Double = 50
        var details: [String] = []
        
        // F/K
        if let pe = f.pe, pe > 0 {
            if pe < 5 { score += 25; details.append("F/K: \(String(format: "%.1f", pe)) (Derin Değer)") }
            else if pe < 10 { score += 15; details.append("F/K: \(String(format: "%.1f", pe)) (Ucuz)") }
            else if pe < 20 { details.append("F/K: \(String(format: "%.1f", pe)) (Normal)") }
            else { score -= 15; details.append("F/K: \(String(format: "%.1f", pe)) (Pahalı)") }
        }
        
        // PD/DD
        if let pb = f.pb, pb > 0 {
            if pb < 1.0 { score += 25; details.append("PD/DD: \(String(format: "%.2f", pb)) (Defter altı)") }
            else if pb < 1.5 { score += 10; details.append("PD/DD: \(String(format: "%.2f", pb)) (Uygun)") }
            else { details.append("PD/DD: \(String(format: "%.2f", pb))") }
        }
        
        return BistFaktor(
            name: "Değer (Value)",
            score: min(100, max(0, score)),
            icon: "tag.fill",
            color: "blue",
            details: details
        )
    }
    
    // MARK: - Momentum Faktör
    
    private func calculateMomentumFactor(_ history: [BorsaPyCandle]?) -> BistFaktor {
        var score: Double = 50
        var details: [String] = []

        guard let candles = history, candles.count >= 20,
              let lastCandle = candles.last else {
            return BistFaktor(name: "Momentum", score: 50, icon: "arrow.up.right", color: "green", details: ["Veri yetersiz"])
        }

        // 20 Günlük Getiri (güvenli index erişimi)
        let current = lastCandle.close
        let past20Index = max(0, candles.count - 20)
        let past20 = candles[past20Index].close
        guard past20 > 0 else {
            return BistFaktor(name: "Momentum", score: 50, icon: "arrow.up.right", color: "green", details: ["Hesaplama hatası"])
        }
        let return20 = ((current - past20) / past20) * 100
        
        if return20 > 15 { score += 30; details.append("20G: +\(String(format: "%.1f", return20))% (Güçlü)") }
        else if return20 > 5 { score += 15; details.append("20G: +\(String(format: "%.1f", return20))%") }
        else if return20 > 0 { score += 5; details.append("20G: +\(String(format: "%.1f", return20))%") }
        else if return20 > -10 { score -= 10; details.append("20G: \(String(format: "%.1f", return20))%") }
        else { score -= 25; details.append("20G: \(String(format: "%.1f", return20))% (Zayıf)") }
        
        // 5 Günlük Kısa Vadeli
        if candles.count >= 5 {
            let past5 = candles[candles.count - 5].close
            let return5 = ((current - past5) / past5) * 100
            if return5 > 5 { score += 10 }
            else if return5 < -5 { score -= 10 }
            details.append("5G: \(return5 >= 0 ? "+" : "")\(String(format: "%.1f", return5))%")
        }
        
        return BistFaktor(
            name: "Momentum",
            score: min(100, max(0, score)),
            icon: "arrow.up.right",
            color: "green",
            details: details
        )
    }
    
    // MARK: - Quality Faktör (Kalite)
    
    private func calculateQualityFactor(_ f: BistFinancials) -> BistFaktor {
        var score: Double = 50
        var details: [String] = []
        
        // ROE
        if let roe = f.roe {
            if roe > 20 { score += 25; details.append("ROE: \(String(format: "%.1f", roe))% (Mükemmel)") }
            else if roe > 15 { score += 15; details.append("ROE: \(String(format: "%.1f", roe))% (İyi)") }
            else if roe > 10 { score += 5; details.append("ROE: \(String(format: "%.1f", roe))%") }
            else if roe > 0 { details.append("ROE: \(String(format: "%.1f", roe))%") }
            else { score -= 20; details.append("ROE: \(String(format: "%.1f", roe))% (Negatif)") }
        }
        
        // Net Kar Marjı
        if let margin = f.netMargin {
            if margin > 15 { score += 15; details.append("Marj: \(String(format: "%.1f", margin))%") }
            else if margin > 10 { score += 5 }
            else if margin < 0 { score -= 15 }
        }
        
        // Borç/Özkaynak
        if let de = f.debtToEquity {
            if de < 0.5 { score += 10; details.append("Borç/Öz: \(String(format: "%.2f", de)) (Düşük)") }
            else if de > 1.5 { score -= 15; details.append("Borç/Öz: \(String(format: "%.2f", de)) (Yüksek)") }
        }
        
        return BistFaktor(
            name: "Kalite (Quality)",
            score: min(100, max(0, score)),
            icon: "checkmark.seal.fill",
            color: "purple",
            details: details
        )
    }
    
    // MARK: - Dividend Faktör (Temettü)
    
    private func calculateDividendFactor(_ dividends: [BistDividend]?, quote: BistQuote?) -> BistFaktor {
        var score: Double = 30 // Temettü yoksa düşük başla
        var details: [String] = []
        
        guard let divs = dividends, !divs.isEmpty,
              let lastDiv = divs.first,
              let price = quote?.last, price > 0 else {
            return BistFaktor(name: "Temettü", score: 30, icon: "banknote.fill", color: "yellow", details: ["Temettü yok"])
        }

        // Son Temettü Verimi (güvenli erişim)
        let yield = (lastDiv.perShare / price) * 100
        
        if yield > 8 { score = 90; details.append("Verim: \(String(format: "%.1f", yield))% (Yüksek)") }
        else if yield > 5 { score = 75; details.append("Verim: \(String(format: "%.1f", yield))%") }
        else if yield > 3 { score = 60; details.append("Verim: \(String(format: "%.1f", yield))%") }
        else { score = 45; details.append("Verim: \(String(format: "%.1f", yield))% (Düşük)") }
        
        // Süreklilik
        let years = Set(divs.prefix(5).map { Calendar.current.component(.year, from: $0.date) }).count
        if years >= 4 { score += 10; details.append("\(years) yıl sürekli") }
        
        return BistFaktor(
            name: "Temettü",
            score: min(100, max(0, score)),
            icon: "banknote.fill",
            color: "yellow",
            details: details
        )
    }
}

// MARK: - Modeller

struct BistFaktorResult: Sendable {
    let symbol: String
    let totalScore: Double
    let factors: [BistFaktor]
    let timestamp: Date
    
    var verdict: String {
        switch totalScore {
        case 75...: return "Çok Güçlü"
        case 60..<75: return "Güçlü"
        case 45..<60: return "Nötr"
        case 30..<45: return "Zayıf"
        default: return "Çok Zayıf"
        }
    }
}

struct BistFaktor: Sendable, Identifiable {
    var id: String { name }
    let name: String
    let score: Double
    let icon: String
    let color: String
    let details: [String]
}
