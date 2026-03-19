# ARGUS TRAİLER PROMPTLARI - İNDEKS

## Genel Bilgi

Bu klasör, Argus Terminal uygulamasını sıfırdan oluşturmak için gereken tüm promptları içerir.

**Son Güncelleme:** 27 Aralık 2024

**Önemli:** Her prompt bağımsız çalışabilir ancak sırasıyla uygulanması önerilir.

---

## 📖 ÖNCE BU DOSYALARI OKU

| Dosya | İçerik |
|-------|--------|
| `00_KULLANICI_REHBERI.md` | **BAŞLAMADAN ÖNCE OKU!** Yasal uyarılar + Windows/Mac kurulum |
| `HIZLI_BASLANGIC.md` | 5 dakikada çalışan MVP |
| `GUNCELLEME_REHBERI.md` | Mevcut projeyi güncelleyenler için |

---

## 📋 Prompt Listesi

| # | Dosya | İçerik | Önem |
|---|-------|--------|------|
| 1 | `01_PROJE_KURULUM.md` | Xcode projesi + API anahtarları | ⭐⭐⭐ |
| 2 | `02_TEMA_VE_MODELS.md` | Dark theme + veri modelleri | ⭐⭐⭐ |
| 3 | `03_ATLAS_TEMEL_ANALIZ.md` | Fundamental analiz (FMP API) | ⭐⭐ |
| 4 | `04_ORION_TEKNIK_ANALIZ.md` | Teknik indikatörler (RSI, MACD, SMA) | ⭐⭐⭐ |
| 5 | `05_AETHER_MAKRO.md` | Makroekonomik analiz (FRED API) | ⭐⭐ |
| 6 | `06_HERMES_HABER.md` | Haber analizi + AI sentiment | ⭐ |
| 7 | `07_PHOENIX_STRATEJI.md` | Al/Sat sinyalleri birleştirme | ⭐⭐⭐ |
| 8 | `08_COUNCIL_KONSEY.md` | **Konsey oylama + matematik formüller** | ⭐⭐⭐ |
| 9 | `09_UI_EKRANLAR.md` | Ana ekranlar ve kartlar | ⭐⭐⭐ |
| 10 | `10_CHIRON_OGRENME.md` | Makine öğrenmesi + ağırlık optimizasyonu | ⭐⭐ |
| 11 | `11_VERI_CEKME.md` | Yahoo/FMP fallback sistemi | ⭐⭐⭐ |
| 12 | `12_HATA_AYIKLAMA.md` | Yaygın hatalar ve çözümleri | ⭐⭐ |
| **13** | `13_YASAL_UYARI.md` | **Zorunlu! Onaysız uygulama açılmaz** | ⭐⭐⭐ |

---

## 🔑 Gerekli API Anahtarları (Tamamı ÜCRETSİZ)

| API | Link | Kullanım | Zorunlu |
|-----|------|----------|---------|
| **FRED** | <https://fred.stlouisfed.org/docs/api/api_key.html> | Makro veriler (CPI, İşsizlik) | ✅ Evet |
| **FMP** | <https://site.financialmodelingprep.com/developer> | Finansal oranlar, profil | ✅ Evet |
| **Groq** | <https://console.groq.com> | AI sentiment (Llama 3) | ❌ Opsiyonel |

**Not:** Yahoo Finance API key gerektirmez.

---

## 🧮 Önemli Formüller

### Konsey Net Destek Hesabı

```
NetSupport = Σ(Vote × Confidence × Weight) / Σ(Confidence × Weight)

Örnek:
Atlas:  BUY (+1) × 0.75 × 0.30 = +0.225
Orion:  BUY (+1) × 0.80 × 0.35 = +0.280
Aether: HOLD (0) × 0.60 × 0.20 =  0.000
Hermes: BUY (+1) × 0.55 × 0.15 = +0.0825

Net = 0.5875 / 0.7075 = 0.83 → BULLISH (%83)
```

### Aether Makro Skor

```
Score = (Leading×1.5 + Coincident×1.0 + Lagging×0.8) / 3.3

Kategoriler:
- Öncü (x1.5): VIX, İşsizlik Başvuruları, SPY Momentum, BTC
- Eşzamanlı (x1.0): İstihdam, DXY
- Gecikmeli (x0.8): CPI, Faiz, Altın
```

### Chiron Ağırlık Optimizasyonu

```
Yeni Ağırlık = Eski × (1 + α × (Doğruluk - 50) / 100)

α = 0.1 (öğrenme oranı)
```

---

## 📁 Klasör Yapısı

Uygulama tamamlandığında şu yapıda olmalı:

```
Argus-Terminal/
├── Models/
│   ├── OrionModels.swift
│   ├── FundamentalModels.swift
│   ├── MacroModels.swift
│   ├── PhoenixModels.swift
│   └── CouncilModels.swift
│
├── Views/
│   ├── WatchlistView.swift
│   ├── StockDetailView.swift
│   ├── CouncilCard.swift
│   ├── PhoenixCard.swift
│   ├── AetherHUDCard.swift
│   └── Theme.swift
│
├── ViewModels/
│   └── TradingViewModel.swift
│
├── Services/
│   ├── Secrets.swift
│   ├── MarketDataProvider.swift
│   ├── FMPProvider.swift
│   ├── FREDProvider.swift
│   ├── YahooFinanceProvider.swift
│   │
│   ├── FundamentalScoreEngine.swift   (Atlas)
│   ├── OrionAnalysisService.swift     (Orion)
│   ├── IndicatorService.swift
│   ├── MacroRegimeService.swift       (Aether)
│   ├── HermesService.swift            (Hermes)
│   ├── GroqSentimentService.swift
│   ├── RSSNewsProvider.swift
│   │
│   ├── PhoenixEngine.swift
│   ├── ArgusGrandCouncil.swift
│   ├── CouncilAdvisorGenerator.swift
│   └── ChironLearningService.swift
│
└── Resources/
    └── Assets.xcassets
```

---

## 🏃 Önerilen Uygulama Sırası

1. **Gün 1:** Promptlar 1-2-11 (Proje + Tema + Veri)
2. **Gün 2:** Promptlar 4-3 (Orion + Atlas)
3. **Gün 3:** Promptlar 5-6 (Aether + Hermes)
4. **Gün 4:** Promptlar 7-8-9 (Phoenix + Council + UI)
5. **Gün 5:** Prompt 10 (Chiron) + Test

**Toplam Tahmini Süre:** 5-8 saat (deneyime göre)

---

## ❓ Sık Sorulan Sorular

**S: Hangi prompt en önemli?**
C: 04 (Orion), 08 (Council), 11 (Veri çekme)

**S: API key almadan deneyebilir miyim?**
C: Hayır, FRED ve FMP kesinlikle gerekli. Groq opsiyonel.

**S: Build hatası alıyorum?**
C: 12_HATA_AYIKLAMA.md dosyasına bak.

**S: UI düzgün görünmüyor?**
C: `.preferredColorScheme(.dark)` eklediğinden emin ol.
