# ARGUS HIZLI BAŞLANGIÇ

## 🚀 5 Dakikada Çalışan Uygulama

Bu dosya, tüm promptları tek seferde kullanmak isteyenler için özet rehberdir.

---

## Adım 1: Xcode Projesi

1. Xcode aç → Create New Project → iOS App
2. Product Name: `Argus-Terminal`
3. Interface: SwiftUI
4. Language: Swift

---

## Adım 2: API Anahtarları (ÜCRETSİZ)

| API | Kayıt Linki | Ne İçin |
|-----|-------------|---------|
| FRED | <https://fred.stlouisfed.org/docs/api/api_key.html> | Makro veriler |
| FMP | <https://financialmodelingprep.com/developer> | Hisse verileri |
| Groq | <https://console.groq.com> (opsiyonel) | AI sentiment |

Her site için:

1. Ücretsiz kayıt ol
2. API key al
3. Kopyala

---

## Adım 3: Secrets.swift Oluştur

```swift
// Argus-Terminal/Services/Secrets.swift
import Foundation

struct Secrets {
    static let fredAPIKey = "BURAYA_YAPISTIR"
    static let fmpAPIKey = "BURAYA_YAPISTIR"
    static let groqAPIKey = "BURAYA_YAPISTIR"  // Opsiyonel
}
```

---

## Adım 4: Promptları Sırayla Uygula

```
1. 01_PROJE_KURULUM.md    → Temel yapı
2. 02_TEMA_VE_MODELS.md   → Dark theme + modeller
3. 11_VERI_CEKME.md       → Yahoo/FMP veri servisleri
4. 03_ATLAS_TEMEL_ANALIZ.md → Fundamental motor
5. 04_ORION_TEKNIK_ANALIZ.md → Teknik motor
6. 05_AETHER_MAKRO.md     → Makro motor (FRED kullanır)
7. 06_HERMES_HABER.md     → Haber motoru
8. 07_PHOENIX_STRATEJI.md → Strateji birleştirici
9. 08_COUNCIL_KONSEY.md   → Konsey oylama
10. 09_UI_EKRANLAR.md     → Ekranlar
```

Her prompt sonrası: **Build et → Hataları düzelt → Sonraki prompt**

---

## Adım 5: İlk Çalıştırma

1. Simulator seç (iPhone 15 Pro)
2. Cmd+R → Çalıştır
3. Watchlist yüklenmeli
4. Herhangi bir hisseye dokun

---

## Minimum Çalışan Versiyon (MVP)

Eğer hızlı sonuç istiyorsan, sadece şu 3 dosyayı oluştur:

### A) TradingViewModel.swift

- Watchlist, quotes, candles
- Yahoo'dan veri çekme

### B) MarketDataProvider.swift  

- fetchQuote ve fetchCandles
- Yahoo API entegrasyonu

### C) WatchlistView.swift

- Hisse listesi
- Fiyat ve değişim gösterimi

Bu 3 dosya ile temel bir watchlist uygulaması çalışır.

---

## Kontrol Listesi

- [ ] Xcode 15+ kurulu
- [ ] iOS 17 SDK
- [ ] FRED API key alındı
- [ ] FMP API key alındı
- [ ] Secrets.swift oluşturuldu
- [ ] İlk build başarılı
- [ ] Watchlist görünüyor
- [ ] Fiyatlar yükleniyor

---

## Sorun mu Yaşıyorsun?

1. **Veri gelmiyor:** API key kontrolü yap
2. **Build hatası:** 12_HATA_AYIKLAMA.md'ye bak
3. **UI bozuk:** Theme.swift ve dark mode kontrolü
