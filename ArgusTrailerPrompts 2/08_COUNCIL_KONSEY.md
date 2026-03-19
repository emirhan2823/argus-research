# PROMPT 8: COUNCIL - KONSEY KARAR MEKANİZMASI

## Açıklama

Tüm motorların (Atlas, Orion, Aether, Hermes) oylamayla karar verdiği konsey sistemi.

---

## PROMPT

```
Argus Terminal için Council (Konsey) karar sistemini oluştur.

## Konsept
Her motor bir "danışman" gibi davranır. Her danışman kendi analiz alanında oy verir.
Konsey başkanı (Grand Council) tüm oyları ağırlıklandırarak nihai karar verir.

## Matematik Formülü

### 1. Bireysel Motor Oyları
Her motor 3 değer üretir:
- **Stance (Duruş):** BUY / HOLD / SELL
- **Confidence (Güven):** 0-100
- **Weight (Ağırlık):** Motora özel

### 2. Oy Dönüşümü
Stance'ı sayısal değere çevir:
```

BUY  = +1
HOLD =  0
SELL = -1

```

### 3. Ağırlıklı Net Destek Formülü
```

NetSupport = Σ (VoteValue × Confidence × Weight) / Σ (Confidence × Weight)

Örnek:

- Atlas:  BUY  (+1) × 85 × 0.30 = +25.5
- Orion:  BUY  (+1) × 70 × 0.35 = +24.5
- Aether: HOLD ( 0) × 60 × 0.20 =   0.0
- Hermes: BUY  (+1) × 55 × 0.15 = +8.25

Toplam Ağırlıklı Oy = 25.5 + 24.5 + 0 + 8.25 = 58.25
Toplam Ağırlık = (85×0.30) + (70×0.35) + (60×0.20) + (55×0.15)
               = 25.5 + 24.5 + 12 + 8.25 = 70.25

NetSupport = 58.25 / 70.25 = 0.83 (yani %83 BUY yönünde)

```

### 4. Nihai Karar
```

NetSupport > +0.33  → BULLISH (Yükseliş Beklentisi)
NetSupport < -0.33  → BEARISH (Düşüş Beklentisi)
Diğer              → NEUTRAL (Nötr)

```

---

## CouncilModels.swift

```swift
import Foundation

// Danışman oyu
struct AdvisorVote: Codable, Identifiable {
    var id: String { advisor.rawValue }
    let advisor: AdvisorType
    let stance: VoteStance
    let confidence: Double       // 0-100
    let reasoning: String
    let keyMetrics: [String]     // Önemli metrikler
}

enum AdvisorType: String, Codable, CaseIterable {
    case atlas = "ATLAS"         // Temel Analiz
    case orion = "ORION"         // Teknik Analiz
    case aether = "AETHER"       // Makro Analiz
    case hermes = "HERMES"       // Haber Analizi
    
    var displayName: String {
        switch self {
        case .atlas: return "Atlas - Temel Analiz"
        case .orion: return "Orion - Teknik Analiz"
        case .aether: return "Aether - Makro Ortam"
        case .hermes: return "Hermes - Haber Duygusu"
        }
    }
    
    var weight: Double {
        switch self {
        case .atlas: return 0.30   // %30
        case .orion: return 0.35   // %35 (en yüksek)
        case .aether: return 0.20  // %20
        case .hermes: return 0.15  // %15
        }
    }
    
    var icon: String {
        switch self {
        case .atlas: return "building.columns.fill"
        case .orion: return "waveform.path.ecg"
        case .aether: return "globe.europe.africa.fill"
        case .hermes: return "newspaper.fill"
        }
    }
    
    var color: String {
        switch self {
        case .atlas: return "blue"
        case .orion: return "purple"
        case .aether: return "cyan"
        case .hermes: return "orange"
        }
    }
}

enum VoteStance: String, Codable {
    case bullish = "BULLISH"
    case neutral = "NEUTRAL"
    case bearish = "BEARISH"
    
    var numericValue: Double {
        switch self {
        case .bullish: return +1.0
        case .neutral: return  0.0
        case .bearish: return -1.0
        }
    }
    
    var emoji: String {
        switch self {
        case .bullish: return "🟢"
        case .neutral: return "🟡"
        case .bearish: return "🔴"
        }
    }
}

// Konsey kararı
struct GrandCouncilDecision: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let votes: [AdvisorVote]
    let finalStance: VoteStance
    let netSupport: Double           // -1 ile +1 arası
    let consensusLevel: String       // "Tam Uzlaşı", "Çoğunluk", "Bölünmüş"
    let summary: String
    let calculatedAt: Date
    
    // Yardımcı hesaplamalar
    var bullishCount: Int { votes.filter { $0.stance == .bullish }.count }
    var bearishCount: Int { votes.filter { $0.stance == .bearish }.count }
    var neutralCount: Int { votes.filter { $0.stance == .neutral }.count }
}
```

## CouncilAdvisorGenerator.swift

```swift
import Foundation

class CouncilAdvisorGenerator {
    static let shared = CouncilAdvisorGenerator()
    
    // MARK: - Atlas Oyu (Temel Analiz)
    
    func generateAtlasVote(score: FundamentalScoreResult?) -> AdvisorVote {
        guard let s = score else {
            return AdvisorVote(
                advisor: .atlas,
                stance: .neutral,
                confidence: 30,
                reasoning: "Temel analiz verisi mevcut değil",
                keyMetrics: []
            )
        }
        
        // Skor -> Stance dönüşümü
        let stance: VoteStance
        if s.totalScore >= 65 { stance = .bullish }
        else if s.totalScore <= 35 { stance = .bearish }
        else { stance = .neutral }
        
        // Güven = skorun kesinliği
        let confidence = min(100, max(30, s.totalScore))
        
        var metrics: [String] = []
        if s.profitabilityScore >= 22 { metrics.append("Güçlü karlılık") }
        if s.debtScore <= 10 { metrics.append("Yüksek borç riski") }
        if s.growthScore >= 18 { metrics.append("İyi büyüme") }
        
        return AdvisorVote(
            advisor: .atlas,
            stance: stance,
            confidence: confidence,
            reasoning: generateAtlasReasoning(score: s, stance: stance),
            keyMetrics: metrics
        )
    }
    
    // MARK: - Orion Oyu (Teknik Analiz)
    
    func generateOrionVote(score: OrionScoreResult?) -> AdvisorVote {
        guard let s = score else {
            return AdvisorVote(
                advisor: .orion,
                stance: .neutral,
                confidence: 30,
                reasoning: "Teknik analiz verisi mevcut değil",
                keyMetrics: []
            )
        }
        
        let stance: VoteStance
        if s.totalScore >= 65 { stance = .bullish }
        else if s.totalScore <= 35 { stance = .bearish }
        else { stance = .neutral }
        
        let confidence = min(100, max(30, s.totalScore))
        
        var metrics: [String] = []
        if s.structureScore >= 25 { metrics.append("Güçlü yapı") }
        if s.trendScore >= 18 { metrics.append("Yükseliş trendi") }
        if s.momentumScore >= 18 { metrics.append("Güçlü momentum") }
        if s.patternScore >= 10 { metrics.append("Olumlu pattern") }
        
        return AdvisorVote(
            advisor: .orion,
            stance: stance,
            confidence: confidence,
            reasoning: s.reasoning,
            keyMetrics: metrics
        )
    }
    
    // MARK: - Aether Oyu (Makro)
    
    func generateAetherVote(rating: MacroEnvironmentRating?) -> AdvisorVote {
        guard let r = rating else {
            return AdvisorVote(
                advisor: .aether,
                stance: .neutral,
                confidence: 40,
                reasoning: "Makro veri mevcut değil",
                keyMetrics: []
            )
        }
        
        let stance: VoteStance
        switch r.regime {
        case .riskOn: stance = .bullish
        case .riskOff: stance = .bearish
        case .neutral: stance = .neutral
        }
        
        let confidence = min(100, max(30, r.numericScore))
        
        var metrics: [String] = []
        if r.volatilityScore >= 70 { metrics.append("Düşük VIX") }
        if r.laborScore >= 70 { metrics.append("Güçlü istihdam") }
        if r.inflationScore <= 40 { metrics.append("Enflasyon riski") }
        
        return AdvisorVote(
            advisor: .aether,
            stance: stance,
            confidence: confidence,
            reasoning: r.summary,
            keyMetrics: metrics
        )
    }
    
    // MARK: - Hermes Oyu (Haber)
    
    func generateHermesVote(result: HermesResult?) -> AdvisorVote {
        guard let h = result else {
            return AdvisorVote(
                advisor: .hermes,
                stance: .neutral,
                confidence: 30,
                reasoning: "Haber verisi mevcut değil",
                keyMetrics: []
            )
        }
        
        let stance: VoteStance
        switch h.overallSentiment {
        case .positive: stance = .bullish
        case .negative: stance = .bearish
        case .neutral: stance = .neutral
        }
        
        let confidence = min(100, max(20, h.sentimentScore))
        
        var metrics: [String] = []
        if h.newsCount > 5 { metrics.append("\(h.newsCount) haber analiz edildi") }
        
        return AdvisorVote(
            advisor: .hermes,
            stance: stance,
            confidence: confidence,
            reasoning: h.summary,
            keyMetrics: metrics
        )
    }
    
    // MARK: - Yardımcılar
    
    private func generateAtlasReasoning(score: FundamentalScoreResult, stance: VoteStance) -> String {
        switch stance {
        case .bullish:
            return "Şirket güçlü finansal sağlık gösteriyor. \(score.summary)"
        case .bearish:
            return "Finansal göstergeler zayıf. \(score.summary)"
        case .neutral:
            return "Karışık finansal sinyaller. \(score.summary)"
        }
    }
}
```

## ArgusGrandCouncil.swift

```swift
import Foundation

class ArgusGrandCouncil {
    static let shared = ArgusGrandCouncil()
    private let generator = CouncilAdvisorGenerator.shared
    
    /// Ana karar fonksiyonu
    func convene(
        symbol: String,
        atlas: FundamentalScoreResult?,
        orion: OrionScoreResult?,
        aether: MacroEnvironmentRating?,
        hermes: HermesResult?
    ) -> GrandCouncilDecision {
        
        // 1. Her danışmandan oy al
        let atlasVote = generator.generateAtlasVote(score: atlas)
        let orionVote = generator.generateOrionVote(score: orion)
        let aetherVote = generator.generateAetherVote(rating: aether)
        let hermesVote = generator.generateHermesVote(result: hermes)
        
        let votes = [atlasVote, orionVote, aetherVote, hermesVote]
        
        // 2. Ağırlıklı net destek hesapla
        let netSupport = calculateNetSupport(votes: votes)
        
        // 3. Nihai karar
        let finalStance = determineFinalStance(netSupport: netSupport)
        
        // 4. Uzlaşı seviyesi
        let consensus = determineConsensus(votes: votes)
        
        // 5. Özet oluştur
        let summary = generateSummary(
            stance: finalStance,
            netSupport: netSupport,
            votes: votes
        )
        
        return GrandCouncilDecision(
            symbol: symbol,
            votes: votes,
            finalStance: finalStance,
            netSupport: netSupport,
            consensusLevel: consensus,
            summary: summary,
            calculatedAt: Date()
        )
    }
    
    // MARK: - Net Destek Hesaplama
    
    /// Formül: Σ(Vote × Confidence × Weight) / Σ(Confidence × Weight)
    private func calculateNetSupport(votes: [AdvisorVote]) -> Double {
        var weightedSum = 0.0
        var totalWeight = 0.0
        
        for vote in votes {
            let voteValue = vote.stance.numericValue  // -1, 0, +1
            let confidence = vote.confidence / 100.0  // 0-1 arası
            let weight = vote.advisor.weight          // 0.15-0.35 arası
            
            weightedSum += voteValue * confidence * weight
            totalWeight += confidence * weight
        }
        
        guard totalWeight > 0 else { return 0 }
        
        return weightedSum / totalWeight  // -1 ile +1 arası
    }
    
    // MARK: - Nihai Karar
    
    private func determineFinalStance(netSupport: Double) -> VoteStance {
        if netSupport > 0.33 { return .bullish }
        if netSupport < -0.33 { return .bearish }
        return .neutral
    }
    
    // MARK: - Uzlaşı Seviyesi
    
    private func determineConsensus(votes: [AdvisorVote]) -> String {
        let bullish = votes.filter { $0.stance == .bullish }.count
        let bearish = votes.filter { $0.stance == .bearish }.count
        
        // Tam uzlaşı: 4/4 aynı yön
        if bullish == 4 || bearish == 4 {
            return "Tam Uzlaşı ✓"
        }
        
        // Güçlü çoğunluk: 3/4 aynı yön
        if bullish >= 3 || bearish >= 3 {
            return "Güçlü Çoğunluk"
        }
        
        // Çoğunluk: 2/4 + 2 nötr veya 2 bullish + 2 bearish
        if bullish == 2 && bearish == 0 || bearish == 2 && bullish == 0 {
            return "Çoğunluk"
        }
        
        return "Bölünmüş Konsey"
    }
    
    // MARK: - Özet Oluşturma
    
    private func generateSummary(stance: VoteStance, netSupport: Double, votes: [AdvisorVote]) -> String {
        let supportPercent = Int(abs(netSupport) * 100)
        
        // En güçlü destekçi
        let strongest = votes.max { $0.confidence < $1.confidence }
        let strongestName = strongest?.advisor.displayName ?? ""
        
        switch stance {
        case .bullish:
            return "Konsey %\(supportPercent) güvenle YÜKSELŞ bekliyor. \(strongestName) en güçlü desteği veriyor."
        case .bearish:
            return "Konsey %\(supportPercent) güvenle DÜŞÜŞ uyarısı veriyor. \(strongestName) en yüksek güvene sahip."
        case .neutral:
            return "Konsey kararsız. Danışmanlar arasında görüş ayrılığı var. Beklemek mantıklı."
        }
    }
}
```

## TradingViewModel Entegrasyonu

```swift
@Published var grandCouncilDecisions: [String: GrandCouncilDecision] = [:]

func conveneCouncil(for symbol: String) async {
    let atlas = fundamentalScores[symbol]
    let orion = orionScores[symbol]
    let aether = macroRating
    let hermes = hermesResults[symbol]
    
    let decision = ArgusGrandCouncil.shared.convene(
        symbol: symbol,
        atlas: atlas,
        orion: orion,
        aether: aether,
        hermes: hermes
    )
    
    await MainActor.run {
        self.grandCouncilDecisions[symbol] = decision
    }
}
```

---

## Örnek Hesaplama

```
Senaryo: AAPL hissesi

Atlas:  BULLISH, Güven: 75%, Ağırlık: 0.30
Orion:  BULLISH, Güven: 80%, Ağırlık: 0.35
Aether: NEUTRAL, Güven: 60%, Ağırlık: 0.20
Hermes: BULLISH, Güven: 55%, Ağırlık: 0.15

Hesaplama:
1. Atlas:  (+1) × 0.75 × 0.30 = +0.225
2. Orion:  (+1) × 0.80 × 0.35 = +0.280
3. Aether: ( 0) × 0.60 × 0.20 =  0.000
4. Hermes: (+1) × 0.55 × 0.15 = +0.0825

Toplam Ağırlıklı = 0.225 + 0.280 + 0.000 + 0.0825 = 0.5875
Toplam Ağırlık   = (0.75×0.30) + (0.80×0.35) + (0.60×0.20) + (0.55×0.15)
                 = 0.225 + 0.28 + 0.12 + 0.0825 = 0.7075

Net Destek = 0.5875 / 0.7075 = 0.83

Karar: 0.83 > 0.33 → BULLISH (%83 güvenle)
Uzlaşı: 3/4 BULLISH → "Güçlü Çoğunluk"
```
