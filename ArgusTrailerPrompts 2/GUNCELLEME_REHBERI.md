# ARGUS GÜNCELLEME REHBERİ

## Mevcut Projeyi Güncelleme

Bu rehber, eski promptlarla başlamış ve projeyi belirli bir seviyeye getirmiş kullanıcılar içindir.

---

## 🔍 Önce Kontrol Et

Projenizde şunlar var mı kontrol edin:

| Dosya | Var mı? | Güncelleme Gerekir mi? |
|-------|---------|------------------------|
| `TradingViewModel.swift` | ✅/❌ | Konsey entegrasyonu ekle |
| `OrionAnalysisService.swift` | ✅/❌ | V2 ağırlıkları (35-25-25-15) |
| `MacroRegimeService.swift` | ✅/❌ | Kategori skorları (Leading/Coincident/Lagging) |
| `ArgusGrandCouncil.swift` | ✅/❌ | Yeni oylama matematiği |
| `Theme.swift` | ✅/❌ | Muhtemelen OK |

---

## 📦 Yeni Özellikler (v2024.12)

### 1. Orion V2 Ağırlıkları

Eski:

```swift
// Eski - eşit ağırlık
let total = (trend + momentum + volatility + structure) / 4
```

Yeni:

```swift
// Yeni - v2 ağırlıkları
structureScore: 0-35  // %35
trendScore: 0-25      // %25
momentumScore: 0-25   // %25
patternScore: 0-15    // %15
```

**Güncelleme:** `04_ORION_TEKNIK_ANALIZ.md` dosyasından `OrionAnalysisService.swift` kodunu kopyala.

---

### 2. Aether Kategori Skorları

Eski:

```swift
// Sadece toplam skor
let numericScore: Double
```

Yeni:

```swift
// Kategori skorları eklendi
let leadingScore: Double?      // Öncü (x1.5 ağırlık)
let coincidentScore: Double?   // Eşzamanlı (x1.0)
let laggingScore: Double?      // Gecikmeli (x0.8)
```

**Güncelleme:**

1. `MacroModels.swift`'e yeni alanları ekle
2. `MacroRegimeService.swift`'i güncelle (`05_AETHER_MAKRO.md`)

---

### 3. Konsey Sistemi (Yeni)

Eski promptlarda yoktu. Şimdi eklendi.

**Yeni dosyalar oluştur:**

- `CouncilModels.swift`
- `CouncilAdvisorGenerator.swift`
- `ArgusGrandCouncil.swift`

Kaynak: `08_COUNCIL_KONSEY.md`

---

### 4. Beklenti Girişi Sistemi (Yeni)

Manuel ekonomik beklenti girişi ve sürpriz hesabı.

**Yeni dosyalar:**

- `ExpectationsStore.swift`
- `ExpectationsEntryView.swift`

Bu promptlarda yok! Ayrıca eklenmeli (isterseniz ekleyebilirim).

---

## 🔄 Hızlı Güncelleme Adımları

### Sadece Konsey Eklemek İstiyorsan

1. `08_COUNCIL_KONSEY.md` aç
2. 3 dosyayı oluştur: Models, Generator, GrandCouncil
3. TradingViewModel'e `grandCouncilDecisions` ekle
4. UI'da `CouncilCard` kullan

### Sadece Orion V2 İstiyorsan

1. `OrionScoreResult` modelini güncelle (4 category score)
2. `OrionAnalysisService.calculateScore()` fonksiyonunu güncelle
3. UI'da yeni skorları göster

### Sadece Aether Kategorileri İstiyorsan

1. `MacroEnvironmentRating` modeline 3 kategori skoru ekle
2. `MacroRegimeService.analyze()` fonksiyonunu güncelle
3. UI'da `MiniPill` ile kategorileri göster

---

## ⚠️ Dikkat Edilmesi Gerekenler

1. **Model Değişiklikleri:**
   - Yeni alanlar eklediğinde Codable uyumluluğunu kontrol et
   - Optional (`?`) kullan ki eski verilerle crash olmasın

2. **ViewModel Değişiklikleri:**
   - Yeni `@Published` değişkenler eklediğinde UI güncellenecek
   - `async` fonksiyonlarda `await MainActor.run` unutma

3. **Mevcut Veriler:**
   - Cache temizlenmeli (UserDefaults'ta eski format varsa)

```swift
// Eski cache'i temizle
UserDefaults.standard.removeObject(forKey: "old_cache_key")
```

---

## 🎯 Önerilen Güncelleme Sırası

1. **Models** - Veri yapısını güncelle
2. **Services** - İş mantığını güncelle
3. **ViewModel** - Bağlantıları yap
4. **UI** - Görsel değişiklikler
5. **Test** - Build ve çalıştır

---

## 💡 İpucu

Claude/ChatGPT'ye şöyle sor:

```
Mevcut [DOSYA_ADI] dosyamı şu yeni versiyonla güncelle.
Sadece değişen kısımları göster, tüm dosyayı yeniden yazma.

Mevcut kodum:
[MEVCUT KODU YAPISTIR]

Yeni versiyon:
[YENİ PROMPTTAN KODU YAPISTIR]
```

Bu şekilde sadece farkları görebilirsin.
