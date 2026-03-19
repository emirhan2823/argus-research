# 🗺️ Argus Modül Bağlantı Haritası

## 📊 Genel Bakış

| Kategori | Sayı | Durum |
|----------|------|-------|
| Servis Dosyaları | 114 | 🟡 Bazıları orphan |
| Council Modülleri | 22 | 🟢 Aktif |
| ViewModels | 10 | 🟡 Legacy var |
| Alt Dizinler | 32 | 🟢 Modüler |

---

## 🔗 ANA VERİ AKIŞI

```
MarketDataStore → Orion → Council → Decision → TradeBrain → PortfolioEngine
       ↓              ↓         ↓
    Hermes ←→ HermesCoordinator → HermesCouncil
       ↓              ↓
    Chiron ←→ Weights → OrionAnalysisService
       ↓
    Aether → MacroRegimeService → AetherCouncil
       ↓
    Atlas → FundamentalScoreEngine → AtlasCouncil
       ↓
   Demeter → SectorETF Analysis → BistGrandCouncil (BIST only)
       ↓
   Athena → Factor Analysis → Advisory (Non-voting)
```

---

## 🚨 KRİTİK BAĞLANTI SORUNLARI

### 1. 🔴 BistTradingViewModel (ORPHAN LEGACY)

```
Konum: ViewModels/Bist/BistTradingViewModel.swift (278 satır)

Sorun:
├── Kendi balance/portfolio yönetimi (bist_balance_v1, bist_portfolio_v1)
├── PortfolioEngine ile ENTEGRE DEĞİL
├── Council sistemine BAĞLI DEĞİL
├── Sadece basit OrionAnalysis kullanıyor
└── BistDataService kullanıyor (ayrı servis)

Bağlantılar:
├── BistMarketView ✅ kullanıyor
├── BistPortfolioView ✅ kullanıyor
└── Ana akışla ❌ bağlantısız

Öneri: Kaldır veya PortfolioEngine'e migre et
```

### 2. 🟡 SmartPlanGenerator (AZ KULLANILIYOR)

```
Konum: Services/SmartPlanGenerator.swift (350 satır)

Kullananlar:
├── VortexEngine.swift ✅
└── ...ve başka YOK

Özellikleri (ATIL):
├── 5 plan stili (Conservative, Balanced, Aggressive, Momentum, SwingTrade)
├── ATR-bazlı stop/target hesaplama
├── RSI overbought kontrolü
├── Council action change tetikleyicileri
└── Zaman bazlı değerlendirme

Sorun: Council action değişikliklerini dinliyor AMA
        dinamik rejim (Chiron) ve Hermes entegrasyonu YOK

Öneri: PositionPlanStore ve TradeBrain ile entegre et
```

### 3. 🟡 PhoenixScenarioEngine (SINIIRLI KULLANIM)

```
Konum: Services/PhoenixScenarioEngine.swift

Kullananlar:
├── TradingViewModel+Argus.swift ✅
└── ...ve başka YOK

Sorun: Sadece Argus analiz akışında kullanılıyor
       Council'da kullanılmıyor

Öneri: PhoenixCouncil oluştur veya Orion'a entegre et
```

### 4. 🟡 VortexEngine (NİŞ KULLANIM)

```
Konum: Services/VortexEngine.swift

Kullananlar:
├── PositionPlanStore.swift ✅
├── PlanEditorSheet.swift ✅
└── Kendi içinde SmartPlanGenerator ✅

Fonksiyonu: Pozisyon planlaması
Sorun: Ana karar akışından kopuk
```

---

## ✅ DOĞRU ÇALIŞAN BAĞLANTILAR

### Hermes → Council Akışı

```swift
// HermesCoordinator.swift
func analyzeOnDemand(symbol: String) async -> Double?
    ↓
// HeimdallOrchestrator.shared.requestNews()
    ↓
// processNews() → HermesLLMService.analyzeBatch()
    ↓
// calculateWeightedScore() → hermesScore
    ↓
// ArgusGrandCouncil.convene() → HermesCouncil.convene()
    ↓
// hermesMultiplier (1.15 boost / 0.85 drag)
    ↓
// Final confidence adjustment
```

**Durum:** ✅ Doğru çalışıyor, hermesScore Council'a iletiliyor

### Chiron → Orion Ağırlıkları

```swift
// OrionAnalysisService.swift:104
if let learned = ChironRegimeEngine.shared.getLearnedOrionWeights(symbol: symbol) {
    // Öğrenilmiş ağırlıkları kullan
}
```

**Durum:** ✅ Chiron öğrenilmiş ağırlıklar Orion'a aktarılıyor

### Council → TradeBrain Akışı

```swift
// SmartPlanGenerator.swift:147-159
// Council action değişikliği tetikleyicileri

.councilActionChanged(from: decision.action, to: .trim)
    → .reduceAndHold(30)

.councilActionChanged(from: decision.action, to: .liquidate)
    → .sellAll
```

**Durum:** 🟡 Mekanizma var AMA aktif olarak kullanılmıyor

---

## 📋 MODÜL KULLANIM MATRİKSİ

| Modül | Council | AutoPilot | UI | TradeBrain |
|-------|---------|-----------|-----|------------|
| Orion | ✅ | ✅ | ✅ | ✅ |
| Atlas | ✅ | ✅ | ✅ | ❌ |
| Aether | ✅ | ✅ | ✅ | ❌ |
| Hermes | ✅ | 🟡 | ✅ | ❌ |
| Chiron | ✅ | ✅ | ✅ | ❌ |
| Phoenix | 🟡 (advisor) | ❌ | ✅ | ❌ |
| Demeter | ✅ (BIST) | ❌ | ✅ | ❌ |
| Athena | 🟡 (advisor) | ❌ | ✅ | ❌ |

---

## 🗑️ ÖLÇEK KOD / ORPHAN ADAYLARI

| Dosya/Modül | Durum | Öneri |
|-------------|-------|-------|
| BistTradingViewModel | 🔴 Orphan | Kaldır |
| BistDataService | 🔴 Legacy | MarketDataStore'a migre |
| PhoenixScenarioEngine | 🟡 Underused | Council'a entegre |
| SmartPlanGenerator | 🟡 Underused | TradeBrain'e entegre |
| ChronosLabViewModel | ❓ Kontrol et | Aktif mi? |
| VortexEngine | 🟡 Niş | Dokümante et |

---

## 🔄 EKSİK BAĞLANTILAR (OLMASI GEREKEN)

### 1. Hermes → TradeBrain

```
Mevcut: Hermes → Council → Decision
Eksik:  Hermes → SmartPlanGenerator (haber bazlı plan ayarı)

Örnek: Olumsuz haber → Stop'u sıkılaştır
```

### 2. Chiron Rejim → Plan Stili

```
Mevcut: Chiron → Orion Weights
Eksik:  Chiron Regime → SmartPlanGenerator.style

Örnek: 
  - Trend rejimi → Momentum plan stili
  - Chop rejimi → Conservative plan stili
```

### 3. Demeter → Global Council

```
Mevcut: Demeter → BistGrandCouncil (BIST only)
Eksik:  Demeter → ArgusGrandCouncil (Global)

Sektör rotasyonu global için de geçerli
```

### 4. Phoenix → Council Veto

```
Mevcut: Phoenix → Advisor (non-voting)
Eksik:  Phoenix low confidence → Veto mekanizması

R² < 0.25 → Entry veto olmalı?
```

---

## 📊 ViewModel Bağımlılık Haritası

```
TradingViewModel (2015 satır - GOD OBJECT)
├── MarketDataProvider
├── FundamentalScoreStore
├── AISignalService
├── OrionStore
├── PortfolioEngine ✅
├── ChironRegimeEngine ✅
├── ChimeraSynergyEngine
├── DemeterEngine ✅
├── UniverseEngine
├── EconomicCalendarService
├── TradeBrain
├── ArgusLedger
├── ChironJournalService
└── ProviderCapabilityRegistry

BistTradingViewModel (278 satır - ORPHAN)
├── BistDataService ❌ (ayrı)
├── OrionAnalysis (basit) ❌
└── KENDİ balance/portfolio ❌ (PortfolioEngine dışı)
```

---

## ⚡ AKSIYON ÖNCELİKLERİ

1. **🔴 KRİTİK:** BistTradingViewModel → PortfolioEngine migrasyon
2. **🟡 ÖNEMLİ:** SmartPlanGenerator ← Chiron rejim entegrasyonu
3. **🟡 ÖNEMLİ:** Demeter → Global Council entegrasyonu
4. **🟢 İYİLEŞTİRME:** Phoenix → Council veto mekanizması
5. **🟢 İYİLEŞTİRME:** Hermes → TradeBrain plan ayarı
