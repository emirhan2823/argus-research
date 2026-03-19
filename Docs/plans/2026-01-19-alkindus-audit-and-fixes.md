# Alkindus Öğrenme Modülü - Denetim ve Düzeltme Planı

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Alkindus modülündeki kritik sorunları düzeltmek ve eksik bileşenleri tamamlamak

**Architecture:** Alkindus, 14 servis dosyası ve 4 UI dosyasından oluşan öğrenme motoru. Argus'tan kararları gözlemler, T+7/T+15 horizonlarında değerlendirir ve modül ağırlıklarını kalibre eder. Pinecone RAG entegrasyonu ile vektör tabanlı arama sağlar.

**Tech Stack:** Swift 5.9, SwiftUI, Actors (async/await), JSON persistence, Pinecone Vector DB, Gemini Embeddings

---

## DENETİM BULGULARI

### Mevcut Durum
| Kategori | Durum | Puan |
|----------|-------|------|
| Kod Kalitesi | İyi | 8/10 |
| Mimari | İyi | 8/10 |
| Test Kapsamı | Yetersiz | 2/10 |
| Hata Yönetimi | Orta | 5/10 |
| Dokümantasyon | Orta | 6/10 |

### Kritik Sorunlar (Öncelik Sırasıyla)
1. **TEST YOK** - Alkindus için hiç unit test yok
2. **Horizon Trigger Belirsiz** - processMaturedDecisions() nerede çağrılıyor?
3. **RAG Sync Sessiz Hatalar** - Pinecone hataları yutulur
4. **Score Boundary Hassasiyeti** - 79.9 vs 80 ayrı bracket'lere düşer
5. **Timezone Handling** - UTC varsayımı BIST için sorun

---

## TASK 1: Horizon Maturation Trigger Düzeltmesi

**Sorun:** `processMaturedDecisions()` fonksiyonu tanımlı ama nerede/ne zaman çağrıldığı belirsiz.

**Files:**
- Modify: `/Users/erenkapak/Desktop/Algo-Trading/Algo-Trading/Services/Alkindus/AlkindusCalibrationEngine.swift`
- Modify: `/Users/erenkapak/Desktop/Algo-Trading/Algo-Trading/Algo_TradingApp.swift`

**Step 1: AlkindusCalibrationEngine'de periodicCheck fonksiyonu ekle**

```swift
// AlkindusCalibrationEngine.swift - observe() fonksiyonundan sonra ekle

/// Periyodik maturation kontrolü - App başlangıcında ve saatlik tetiklenir
func periodicMatureCheck() async {
    // Güncel fiyatları al
    let store = MarketDataStore.shared
    var currentPrices: [String: Double] = [:]

    for observation in pendingObservations {
        if let quote = store.quotes[observation.symbol]?.value {
            currentPrices[observation.symbol] = quote.currentPrice
        }
    }

    guard !currentPrices.isEmpty else {
        print("⚠️ Alkindus: Fiyat verisi yok, maturation atlanıyor")
        return
    }

    await processMaturedDecisions(currentPrices: currentPrices)
    print("✅ Alkindus: Maturation check tamamlandı (\(pendingObservations.count) pending)")
}
```

**Step 2: App başlangıcında ve Timer ile tetikle**

```swift
// Algo_TradingApp.swift - init() veya onAppear içinde

// MARK: - Alkindus Periodic Check
private func startAlkindusPeriodicCheck() {
    // Başlangıçta bir kez çalıştır
    Task {
        await AlkindusCalibrationEngine.shared.periodicMatureCheck()
    }

    // Her saat başı tekrarla
    Timer.scheduledTimer(withTimeInterval: 3600, repeats: true) { _ in
        Task {
            await AlkindusCalibrationEngine.shared.periodicMatureCheck()
        }
    }
}
```

**Step 3: Verify**

Run: Build project and check console for "Alkindus: Maturation check" logs

**Step 4: Commit**

```bash
git add Algo-Trading/Services/Alkindus/AlkindusCalibrationEngine.swift Algo-Trading/Algo_TradingApp.swift
git commit -m "fix(alkindus): add periodic maturation trigger"
```

---

## TASK 2: RAG Sync Hata Yönetimi

**Sorun:** Pinecone sync hataları sessizce yutulur, veri tutarsızlığı oluşabilir.

**Files:**
- Modify: `/Users/erenkapak/Desktop/Algo-Trading/Algo-Trading/Services/Alkindus/AlkindusRAGEngine.swift`
- Create: `/Users/erenkapak/Desktop/Algo-Trading/Algo-Trading/Services/Alkindus/AlkindusSyncRetryQueue.swift`

**Step 1: Retry queue struct tanımla**

```swift
// AlkindusSyncRetryQueue.swift - YENİ DOSYA

import Foundation

/// Başarısız RAG sync işlemlerini retry için saklar
actor AlkindusSyncRetryQueue {
    static let shared = AlkindusSyncRetryQueue()

    struct FailedSync: Codable, Identifiable {
        let id: UUID
        let namespace: String
        let documentId: String
        let text: String
        let metadata: [String: String]
        let failedAt: Date
        var retryCount: Int
    }

    private var queue: [FailedSync] = []
    private let maxRetries = 3
    private let persistencePath: URL = {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
            .appendingPathComponent("alkindus_sync_retry_queue.json")
    }()

    init() {
        Task { await loadFromDisk() }
    }

    func enqueue(_ sync: FailedSync) {
        queue.append(sync)
        Task { await saveToDisk() }
        print("⚠️ Alkindus RAG: Sync kuyruğa eklendi (\(queue.count) bekleyen)")
    }

    func processRetryQueue() async {
        guard !queue.isEmpty else { return }

        var remaining: [FailedSync] = []

        for var sync in queue {
            do {
                try await AlkindusRAGEngine.shared.upsertDocument(
                    namespace: sync.namespace,
                    id: sync.documentId,
                    text: sync.text,
                    metadata: sync.metadata
                )
                print("✅ Alkindus RAG: Retry başarılı - \(sync.documentId)")
            } catch {
                sync.retryCount += 1
                if sync.retryCount < maxRetries {
                    remaining.append(sync)
                    print("⚠️ Alkindus RAG: Retry \(sync.retryCount)/\(maxRetries) - \(sync.documentId)")
                } else {
                    print("❌ Alkindus RAG: Max retry aşıldı, siliniyor - \(sync.documentId)")
                }
            }
        }

        queue = remaining
        await saveToDisk()
    }

    private func saveToDisk() async {
        guard let data = try? JSONEncoder().encode(queue) else { return }
        try? data.write(to: persistencePath)
    }

    private func loadFromDisk() async {
        guard let data = try? Data(contentsOf: persistencePath),
              let loaded = try? JSONDecoder().decode([FailedSync].self, from: data) else { return }
        queue = loaded
    }
}
```

**Step 2: RAGEngine'de retry entegrasyonu**

```swift
// AlkindusRAGEngine.swift - syncDocument fonksiyonunu güncelle

// MEVCUT (hata yutulur):
// } catch {
//     print("❌ RAG sync error: \(error)")
// }

// YENİ (retry queue'ya ekle):
} catch {
    print("❌ RAG sync error: \(error)")

    let failedSync = AlkindusSyncRetryQueue.FailedSync(
        id: UUID(),
        namespace: namespace,
        documentId: id,
        text: text,
        metadata: metadata,
        failedAt: Date(),
        retryCount: 0
    )
    await AlkindusSyncRetryQueue.shared.enqueue(failedSync)
}
```

**Step 3: Periodic retry işlemi**

```swift
// Algo_TradingApp.swift - startAlkindusPeriodicCheck() içine ekle

// Retry queue'yu işle (her 15 dakikada)
Timer.scheduledTimer(withTimeInterval: 900, repeats: true) { _ in
    Task {
        await AlkindusSyncRetryQueue.shared.processRetryQueue()
    }
}
```

**Step 4: Commit**

```bash
git add Algo-Trading/Services/Alkindus/AlkindusSyncRetryQueue.swift
git add Algo-Trading/Services/Alkindus/AlkindusRAGEngine.swift
git add Algo-Trading/Algo_TradingApp.swift
git commit -m "feat(alkindus): add RAG sync retry queue for resilience"
```

---

## TASK 3: Score Bracket Boundary Düzeltmesi

**Sorun:** 79.9 ve 80.0 skorları farklı bucket'lere düşer, bu sınır etkisi yaratır.

**Files:**
- Modify: `/Users/erenkapak/Desktop/Algo-Trading/Algo-Trading/Services/Alkindus/AlkindusCalibrationEngine.swift`

**Step 1: Bucket mapping fonksiyonunu soft boundary ile güncelle**

```swift
// AlkindusCalibrationEngine.swift - scoreToBracket fonksiyonunu bul ve değiştir

// MEVCUT (sert sınırlar):
// private func scoreToBracket(_ score: Double) -> String {
//     if score >= 80 { return "80-100" }
//     if score >= 60 { return "60-80" }
//     ...
// }

// YENİ (yumuşak sınırlar + interpolasyon):
private func scoreToBracket(_ score: Double) -> String {
    // Yumuşak sınırlar: ±2 puan tolerans
    switch score {
    case 78...: return "80-100"  // 78+ üst bracket'e
    case 58..<78: return "60-80"
    case 38..<58: return "40-60"
    case 18..<38: return "20-40"
    default: return "0-20"
    }
}

// Ek: İki bracket'e de katkı (weight-based)
private func scoreToBracketsWeighted(_ score: Double) -> [(bracket: String, weight: Double)] {
    // Sınır bölgelerinde iki bracket'e de katkı
    let boundaries: [(threshold: Double, brackets: (String, String))] = [
        (80, ("60-80", "80-100")),
        (60, ("40-60", "60-80")),
        (40, ("20-40", "40-60")),
        (20, ("0-20", "20-40"))
    ]

    for (threshold, (lower, upper)) in boundaries {
        if score >= threshold - 2 && score <= threshold + 2 {
            // Interpolate: 78 -> 0.5 lower, 0.5 upper
            let ratio = (score - (threshold - 2)) / 4.0
            return [(lower, 1 - ratio), (upper, ratio)]
        }
    }

    // Normal tek bracket
    return [(scoreToBracket(score), 1.0)]
}
```

**Step 2: updateCalibration'da weighted bucket kullan**

```swift
// updateCalibration fonksiyonunda değişiklik

// MEVCUT:
// let bracket = scoreToBracket(score)
// data.modules[module]?.updateBracket(bracket, correct: isCorrect)

// YENİ:
let weightedBrackets = scoreToBracketsWeighted(score)
for (bracket, weight) in weightedBrackets {
    data.modules[module]?.updateBracketWeighted(bracket, correct: isCorrect, weight: weight)
}
```

**Step 3: BracketStats'a weighted update ekle**

```swift
// AlkindusMemoryStore.swift veya inline struct

extension BracketStats {
    mutating func updateWeighted(correct: Bool, weight: Double) {
        attempts += weight
        if correct {
            self.correct += weight
        }
        hitRate = attempts > 0 ? self.correct / attempts : 0
    }
}
```

**Step 4: Commit**

```bash
git add Algo-Trading/Services/Alkindus/AlkindusCalibrationEngine.swift
git add Algo-Trading/Services/Alkindus/AlkindusMemoryStore.swift
git commit -m "fix(alkindus): add soft bracket boundaries to reduce edge effects"
```

---

## TASK 4: Unit Test Altyapısı

**Sorun:** Alkindus modülü için hiç test yok.

**Files:**
- Create: `/Users/erenkapak/Desktop/Algo-TradingTests/Alkindus/AlkindusCalibrationEngineTests.swift`
- Create: `/Users/erenkapak/Desktop/Algo-TradingTests/Alkindus/AlkindusMemoryStoreTests.swift`

**Step 1: Test dosyası oluştur - CalibrationEngine**

```swift
// AlkindusCalibrationEngineTests.swift

import XCTest
@testable import Algo_Trading

final class AlkindusCalibrationEngineTests: XCTestCase {

    var sut: AlkindusCalibrationEngine!

    override func setUp() async throws {
        // Test için temiz instance (singleton bypass gerekebilir)
        sut = AlkindusCalibrationEngine.shared
    }

    // MARK: - Bracket Mapping Tests

    func test_scoreToBracket_highScore_returnsTopBracket() async {
        let bracket = await sut.testScoreToBracket(85)
        XCTAssertEqual(bracket, "80-100")
    }

    func test_scoreToBracket_boundaryScore_usesUpperBracket() async {
        // 78+ should map to 80-100 with soft boundaries
        let bracket = await sut.testScoreToBracket(78)
        XCTAssertEqual(bracket, "80-100")
    }

    func test_scoreToBracket_edgeCase_79point9() async {
        let bracket = await sut.testScoreToBracket(79.9)
        XCTAssertEqual(bracket, "80-100") // Soft boundary
    }

    // MARK: - Observation Tests

    func test_observe_createsNewPendingObservation() async {
        let initialCount = await sut.getPendingCount()

        await sut.observe(
            symbol: "TEST",
            action: "BUY",
            moduleScores: ["orion": 75, "atlas": 80],
            regime: "risk_on",
            currentPrice: 100.0
        )

        let finalCount = await sut.getPendingCount()
        XCTAssertEqual(finalCount, initialCount + 1)
    }

    // MARK: - Maturation Tests

    func test_processMaturedDecisions_evaluates7DayHorizon() async {
        // Setup: 8 gün önce oluşturulmuş observation
        // Assert: horizon 7 evaluated olmuş
        // Bu test mock data gerektirir
    }
}
```

**Step 2: Test dosyası oluştur - MemoryStore**

```swift
// AlkindusMemoryStoreTests.swift

import XCTest
@testable import Algo_Trading

final class AlkindusMemoryStoreTests: XCTestCase {

    var sut: AlkindusMemoryStore!

    override func setUp() async throws {
        sut = AlkindusMemoryStore.shared
    }

    // MARK: - Persistence Tests

    func test_saveAndLoad_preservesCalibrationData() async {
        // Get initial data
        let initial = await sut.getCalibration()

        // Modify
        await sut.updateModuleCalibration(
            module: "test_module",
            bracket: "80-100",
            correct: true
        )

        // Force save and reload
        await sut.saveToDisk()
        await sut.loadFromDisk()

        // Verify persisted
        let loaded = await sut.getCalibration()
        XCTAssertNotNil(loaded.modules["test_module"])
    }

    // MARK: - Bootstrap Tests

    func test_importBootstrap_loadsInitialCalibration() async {
        await sut.importBootstrapCalibration()

        let data = await sut.getCalibration()

        // Bootstrap has 5 modules
        XCTAssertGreaterThanOrEqual(data.modules.count, 5)

        // Orion should exist
        XCTAssertNotNil(data.modules["orion"])
    }
}
```

**Step 3: Test helper metodları ekle (gerekirse)**

```swift
// AlkindusCalibrationEngine.swift - #if DEBUG block

#if DEBUG
extension AlkindusCalibrationEngine {
    func testScoreToBracket(_ score: Double) -> String {
        return scoreToBracket(score)
    }

    func getPendingCount() -> Int {
        return pendingObservations.count
    }
}
#endif
```

**Step 4: Run tests**

```bash
xcodebuild test -scheme Algo-Trading -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:Algo-TradingTests/AlkindusCalibrationEngineTests
```

**Step 5: Commit**

```bash
git add Algo-TradingTests/Alkindus/
git commit -m "test(alkindus): add unit tests for CalibrationEngine and MemoryStore"
```

---

## TASK 5: Timezone Handling Düzeltmesi

**Sorun:** Date() UTC kullanır, BIST market saatleri için sorun.

**Files:**
- Modify: `/Users/erenkapak/Desktop/Algo-Trading/Algo-Trading/Services/Alkindus/AlkindusTemporalAnalyzer.swift`

**Step 1: Market-aware date utilities**

```swift
// AlkindusTemporalAnalyzer.swift başına ekle

private extension Date {
    /// BIST için İstanbul timezone'unda saat
    var istanbulHour: Int {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "Europe/Istanbul")
        formatter.dateFormat = "HH"
        return Int(formatter.string(from: self)) ?? 0
    }

    /// NYSE için New York timezone'unda saat
    var newYorkHour: Int {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "HH"
        return Int(formatter.string(from: self)) ?? 0
    }

    /// Sembolün market'ına göre local saat
    func marketHour(for symbol: String) -> Int {
        let isBist = symbol.hasSuffix(".IS") || symbol.uppercased().contains("BIST")
        return isBist ? istanbulHour : newYorkHour
    }
}
```

**Step 2: Temporal analysis'da market-aware kullan**

```swift
// analyzeTemporalPatterns fonksiyonunda

// MEVCUT:
// let hour = Calendar.current.component(.hour, from: date)

// YENİ:
let hour = date.marketHour(for: symbol)
```

**Step 3: Commit**

```bash
git add Algo-Trading/Services/Alkindus/AlkindusTemporalAnalyzer.swift
git commit -m "fix(alkindus): add market-aware timezone handling for BIST/NYSE"
```

---

## TASK 6: Dashboard'da Eksik Bilgileri Göster

**Sorun:** Temporal insights ve correlation precision UI'da eksik.

**Files:**
- Modify: `/Users/erenkapak/Desktop/Algo-Trading/Algo-Trading/Views/AlkindusDashboardView.swift`

**Step 1: Pending observations kartı ekle**

```swift
// AlkindusDashboardView.swift - body içine ekle

// MARK: - Pending Observations Section
Section {
    HStack {
        Image(systemName: "clock.badge.questionmark")
            .foregroundColor(.orange)
        Text("Bekleyen Gözlemler")
        Spacer()
        Text("\(pendingCount)")
            .font(.title2)
            .foregroundColor(.orange)
    }

    if pendingCount > 0 {
        Text("T+7 ve T+15 horizonları değerlendirilmeyi bekliyor")
            .font(.caption)
            .foregroundColor(.secondary)
    }
} header: {
    Text("Maturation Queue")
}
```

**Step 2: Temporal insights kartı**

```swift
// AlkindusDashboardView.swift - Temporal Section

Section {
    ForEach(temporalInsights, id: \.dayOfWeek) { insight in
        HStack {
            Text(insight.dayOfWeek)
            Spacer()
            Text("\(insight.trades) trade")
                .foregroundColor(.secondary)
            Text(String(format: "%.0f%%", insight.hitRate * 100))
                .foregroundColor(insight.hitRate > 0.5 ? .green : .red)
        }
    }
} header: {
    Text("Günlere Göre Performans")
}
```

**Step 3: Commit**

```bash
git add Algo-Trading/Views/AlkindusDashboardView.swift
git commit -m "feat(alkindus): add pending observations and temporal insights to dashboard"
```

---

## ÖZET VE ÖNCELİK SIRASI

| Task | Öncelik | Effort | Risk |
|------|---------|--------|------|
| Task 1: Horizon Trigger | KRITIK | 30 dk | Yüksek |
| Task 2: RAG Retry Queue | YÜKSEK | 45 dk | Orta |
| Task 3: Soft Boundaries | ORTA | 30 dk | Düşük |
| Task 4: Unit Tests | YÜKSEK | 60 dk | - |
| Task 5: Timezone | ORTA | 20 dk | Düşük |
| Task 6: Dashboard UI | DÜŞÜK | 30 dk | - |

**Toplam Tahmini Süre:** ~3.5 saat

---

## NOTLAR

### Bootstrap Kontrolü Gerekli
App başlangıcında `AlkindusMemoryStore.shared.importBootstrapCalibration()` çağrılıyor mu kontrol et. Eğer hayırsa AppDelegate/SceneDelegate'e ekle.

### Pattern Learner Entegrasyonu
OrionPatternEngine tespit ettiği formasyonları Alkindus'a bildirmeli. Bu entegrasyon mevcut mu kontrol et.

### Chiron Sync
ChironDataLakeService'te `syncChironTrade()` çağrısı aktif mi? Trade kapanışlarında bu sync tetiklenmeli.

---

**Plan Tarihi:** 19 Ocak 2026
**Hazırlayan:** Claude (superpowers:writing-plans skill)
