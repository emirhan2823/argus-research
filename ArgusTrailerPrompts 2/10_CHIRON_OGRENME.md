# PROMPT 10: CHIRON - MAKİNE ÖĞRENMESİ

## Açıklama

Backtest sonuçlarından öğrenen ve ağırlıkları optimize eden Chiron sistemi.

---

## PROMPT

```
Argus Terminal için Chiron (Öğrenme) sistemini oluştur.

## Konsept
Chiron, geçmiş işlem sonuçlarını analiz ederek:
1. Motor ağırlıklarını optimize eder
2. Hangi koşullarda hangi motorun daha başarılı olduğunu öğrenir
3. Rejime göre (Risk On/Off) farklı stratejiler önerir

## Matematik: Ağırlık Optimizasyonu

### Performans Skoru Hesaplama
Her işlem için:
```

İşlem Skoru = (Gerçekleşen Getiri / Beklenen Getiri) × 100

Örnek:

- Beklenen (Phoenix hedef): %5
- Gerçekleşen: %3
- İşlem Skoru = 3/5 × 100 = 60

```

### Motor Katkı Analizi
Her motor için:
```

Motor Doğruluk = Doğru Tahmin Sayısı / Toplam Tahmin

Doğru Tahmin:

- BUY dedi ve fiyat yükseldi
- SELL dedi ve fiyat düştü
- HOLD dedi ve fiyat ±%2 içinde kaldı

```

### Ağırlık Güncelleme
```

Yeni Ağırlık = Eski Ağırlık × (1 + Öğrenme Oranı × (Performans - 50) / 100)

Örnek:

- Atlas eski ağırlık: 0.30
- Atlas doğruluk: 70%
- Öğrenme oranı: 0.1
- Yeni Ağırlık = 0.30 × (1 + 0.1 × (70-50)/100) = 0.30 × 1.02 = 0.306

```

---

## ChironModels.swift

```swift
import Foundation

// Öğrenme kaydı
struct LearningRecord: Codable, Identifiable {
    let id: UUID
    let symbol: String
    let entryDate: Date
    let exitDate: Date
    let entryPrice: Double
    let exitPrice: Double
    let signal: PhoenixSignal
    let actualReturn: Double
    let expectedReturn: Double
    let councilDecision: VoteStance
    
    // Motor tahminleri
    let atlasStance: VoteStance
    let orionStance: VoteStance
    let aetherStance: VoteStance
    let hermesStance: VoteStance
    
    // Başarı metrikleri
    var isSuccessful: Bool {
        switch signal {
        case .strongBuy, .buy:
            return actualReturn > 0
        case .sell, .strongSell:
            return actualReturn < 0
        case .hold:
            return abs(actualReturn) < 2 // ±%2 içinde
        }
    }
    
    var performanceScore: Double {
        guard expectedReturn != 0 else { return 50 }
        return min(100, max(0, (actualReturn / expectedReturn) * 100))
    }
}

// Motor performans özeti
struct EnginePerformance: Codable {
    let engine: AdvisorType
    var totalPredictions: Int
    var correctPredictions: Int
    var accuracy: Double { Double(correctPredictions) / Double(max(1, totalPredictions)) * 100 }
    
    // Rejime göre performans
    var riskOnAccuracy: Double
    var riskOffAccuracy: Double
    var neutralAccuracy: Double
}

// Optimize edilmiş ağırlıklar
struct OptimizedWeights: Codable {
    var atlasWeight: Double
    var orionWeight: Double
    var aetherWeight: Double
    var hermesWeight: Double
    let lastUpdated: Date
    let basedOnRecords: Int
    
    static var `default`: OptimizedWeights {
        OptimizedWeights(
            atlasWeight: 0.30,
            orionWeight: 0.35,
            aetherWeight: 0.20,
            hermesWeight: 0.15,
            lastUpdated: Date(),
            basedOnRecords: 0
        )
    }
    
    // Normalize et (toplam 1.0 olmalı)
    mutating func normalize() {
        let total = atlasWeight + orionWeight + aetherWeight + hermesWeight
        guard total > 0 else { return }
        atlasWeight /= total
        orionWeight /= total
        aetherWeight /= total
        hermesWeight /= total
    }
}
```

## ChironLearningService.swift

```swift
import Foundation

class ChironLearningService {
    static let shared = ChironLearningService()
    
    private let learningRate: Double = 0.1  // Öğrenme oranı
    private let minRecords: Int = 10        // Minimum kayıt sayısı
    
    private var records: [LearningRecord] = []
    private var currentWeights = OptimizedWeights.default
    
    // MARK: - Kayıt Ekleme
    
    func recordTrade(_ record: LearningRecord) {
        records.append(record)
        saveRecords()
        
        // Yeterli kayıt varsa optimize et
        if records.count >= minRecords && records.count % 5 == 0 {
            optimizeWeights()
        }
    }
    
    // MARK: - Performans Analizi
    
    func analyzeEnginePerformance() -> [EnginePerformance] {
        var performances: [EnginePerformance] = []
        
        for engine in AdvisorType.allCases {
            let engineRecords = getEngineRecords(for: engine)
            
            let total = engineRecords.count
            let correct = engineRecords.filter { isCorrectPrediction($0, for: engine) }.count
            
            // Rejime göre ayrıştır
            let riskOnRecords = engineRecords.filter { isRiskOnPeriod($0) }
            let riskOffRecords = engineRecords.filter { isRiskOffPeriod($0) }
            let neutralRecords = engineRecords.filter { isNeutralPeriod($0) }
            
            performances.append(EnginePerformance(
                engine: engine,
                totalPredictions: total,
                correctPredictions: correct,
                riskOnAccuracy: calculateAccuracy(riskOnRecords, for: engine),
                riskOffAccuracy: calculateAccuracy(riskOffRecords, for: engine),
                neutralAccuracy: calculateAccuracy(neutralRecords, for: engine)
            ))
        }
        
        return performances
    }
    
    // MARK: - Ağırlık Optimizasyonu
    
    func optimizeWeights() {
        let performances = analyzeEnginePerformance()
        
        for perf in performances {
            let currentWeight = getWeight(for: perf.engine)
            let accuracyDiff = perf.accuracy - 50 // 50% baseline
            
            // Yeni ağırlık hesapla
            let newWeight = currentWeight * (1 + learningRate * accuracyDiff / 100)
            setWeight(for: perf.engine, value: newWeight)
        }
        
        // Normalize et
        currentWeights.normalize()
        currentWeights = OptimizedWeights(
            atlasWeight: currentWeights.atlasWeight,
            orionWeight: currentWeights.orionWeight,
            aetherWeight: currentWeights.aetherWeight,
            hermesWeight: currentWeights.hermesWeight,
            lastUpdated: Date(),
            basedOnRecords: records.count
        )
        
        saveWeights()
        print("🧠 Chiron: Ağırlıklar güncellendi - Atlas: \(String(format: "%.2f", currentWeights.atlasWeight)), Orion: \(String(format: "%.2f", currentWeights.orionWeight)), Aether: \(String(format: "%.2f", currentWeights.aetherWeight)), Hermes: \(String(format: "%.2f", currentWeights.hermesWeight))")
    }
    
    // MARK: - Rejime Göre Ağırlık Önerisi
    
    func getWeightsForRegime(_ regime: MacroRegime) -> OptimizedWeights {
        var weights = currentWeights
        
        switch regime {
        case .riskOn:
            // Risk On: Teknik ve momentum daha önemli
            weights.orionWeight *= 1.1
            weights.aetherWeight *= 0.9
            
        case .riskOff:
            // Risk Off: Temel analiz ve makro daha önemli
            weights.atlasWeight *= 1.1
            weights.aetherWeight *= 1.1
            weights.orionWeight *= 0.8
            
        case .neutral:
            // Nötr: Dengeli tut
            break
        }
        
        weights.normalize()
        return weights
    }
    
    // MARK: - Yardımcı Fonksiyonlar
    
    private func getEngineRecords(for engine: AdvisorType) -> [LearningRecord] {
        return records // Tüm kayıtlar tüm motorları içerir
    }
    
    private func isCorrectPrediction(_ record: LearningRecord, for engine: AdvisorType) -> Bool {
        let stance: VoteStance
        switch engine {
        case .atlas: stance = record.atlasStance
        case .orion: stance = record.orionStance
        case .aether: stance = record.aetherStance
        case .hermes: stance = record.hermesStance
        }
        
        switch stance {
        case .bullish: return record.actualReturn > 0
        case .bearish: return record.actualReturn < 0
        case .neutral: return abs(record.actualReturn) < 2
        }
    }
    
    private func calculateAccuracy(_ records: [LearningRecord], for engine: AdvisorType) -> Double {
        guard !records.isEmpty else { return 50 }
        let correct = records.filter { isCorrectPrediction($0, for: engine) }.count
        return Double(correct) / Double(records.count) * 100
    }
    
    private func isRiskOnPeriod(_ record: LearningRecord) -> Bool {
        return record.aetherStance == .bullish
    }
    
    private func isRiskOffPeriod(_ record: LearningRecord) -> Bool {
        return record.aetherStance == .bearish
    }
    
    private func isNeutralPeriod(_ record: LearningRecord) -> Bool {
        return record.aetherStance == .neutral
    }
    
    private func getWeight(for engine: AdvisorType) -> Double {
        switch engine {
        case .atlas: return currentWeights.atlasWeight
        case .orion: return currentWeights.orionWeight
        case .aether: return currentWeights.aetherWeight
        case .hermes: return currentWeights.hermesWeight
        }
    }
    
    private func setWeight(for engine: AdvisorType, value: Double) {
        let clampedValue = max(0.05, min(0.50, value)) // Min %5, Max %50
        switch engine {
        case .atlas: currentWeights.atlasWeight = clampedValue
        case .orion: currentWeights.orionWeight = clampedValue
        case .aether: currentWeights.aetherWeight = clampedValue
        case .hermes: currentWeights.hermesWeight = clampedValue
        }
    }
    
    // MARK: - Persistance
    
    private func saveRecords() {
        if let data = try? JSONEncoder().encode(records) {
            UserDefaults.standard.set(data, forKey: "chiron_records")
        }
    }
    
    private func loadRecords() {
        if let data = UserDefaults.standard.data(forKey: "chiron_records"),
           let decoded = try? JSONDecoder().decode([LearningRecord].self, from: data) {
            records = decoded
        }
    }
    
    private func saveWeights() {
        if let data = try? JSONEncoder().encode(currentWeights) {
            UserDefaults.standard.set(data, forKey: "chiron_weights")
        }
    }
    
    private func loadWeights() {
        if let data = UserDefaults.standard.data(forKey: "chiron_weights"),
           let decoded = try? JSONDecoder().decode(OptimizedWeights.self, from: data) {
            currentWeights = decoded
        }
    }
    
    // MARK: - Init
    
    init() {
        loadRecords()
        loadWeights()
    }
}
```

## Council Entegrasyonu

ArgusGrandCouncil'ı Chiron ağırlıklarını kullanacak şekilde güncelle:

```swift
// ArgusGrandCouncil.swift'e ekle:

func convene(symbol: String, ..., useAdaptiveWeights: Bool = true) -> GrandCouncilDecision {
    // Adaptive ağırlıklar kullan
    let weights: OptimizedWeights
    if useAdaptiveWeights, let aether = aether {
        weights = ChironLearningService.shared.getWeightsForRegime(aether.regime)
    } else {
        weights = OptimizedWeights.default
    }
    
    // Ağırlıkları uygula
    // ... (mevcut kod, AdvisorType.weight yerine weights kullan)
}
```

---

## Örnek Öğrenme Senaryosu

```
Başlangıç Ağırlıkları:
- Atlas:  0.30
- Orion:  0.35
- Aether: 0.20
- Hermes: 0.15

20 işlem sonrası performans:
- Atlas:  %72 doğruluk (22% > 50%)
- Orion:  %65 doğruluk (15% > 50%)
- Aether: %48 doğruluk (2% < 50%)
- Hermes: %55 doğruluk (5% > 50%)

Güncelleme (öğrenme oranı: 0.1):
- Atlas:  0.30 × (1 + 0.1 × 0.22) = 0.3066
- Orion:  0.35 × (1 + 0.1 × 0.15) = 0.3553
- Aether: 0.20 × (1 - 0.1 × 0.02) = 0.1996
- Hermes: 0.15 × (1 + 0.1 × 0.05) = 0.1508

Normalize:
Toplam = 0.3066 + 0.3553 + 0.1996 + 0.1508 = 1.0123

Yeni Ağırlıklar:
- Atlas:  0.303 (%30.3)
- Orion:  0.351 (%35.1)
- Aether: 0.197 (%19.7)
- Hermes: 0.149 (%14.9)
```

Chiron zamanla en başarılı motorlara daha fazla ağırlık verir.
