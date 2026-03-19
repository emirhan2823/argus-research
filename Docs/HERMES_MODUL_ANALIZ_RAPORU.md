# HERMES MODÜLÜ - KAPSAMLI ANALİZ RAPORU

**Tarih:** 2025  
**İnceleme Kapsamı:** LLM Entegrasyonu, Puanlama Mekanizması, Global Feed, Mimari Yeterlilik

---

## 1. GENEL DURUM

### 1.1 Mevcut Mimari

Hermes modülü **iki farklı LLM servisi** kullanıyor:
- **HermesLLMService** (Groq/Llama 3.1 8B) - Batch analiz için
- **GeminiNewsService** (Groq/Llama 3.3 70B) - Tekil analiz için (ESKİ)

**Sorun:** İki servis paralel çalışıyor, tutarsızlık yaratıyor.

### 1.2 Veri Akışı

```
HermesFeedView (UI)
    ↓
TradingViewModel.loadGeneralFeed()
    ↓
loadNewsAndInsights(for: "GENERAL", isGeneral: true)
    ↓
AggregatedNewsService.fetchNews() → [NewsArticle]
    ↓
GeminiNewsService.analyzeNews() → [NewsInsight] (ESKİ YOL)
    ↓
generalNewsInsights (UI'da gösteriliyor)
```

**Sorun:** Global feed için `HermesCoordinator` kullanılmıyor, direkt `GeminiNewsService` çağrılıyor.

---

## 2. TESPİT EDİLEN SORUNLAR

### 2.1 LLM Servisi Karmaşası ⚠️ KRİTİK

**Sorun:**
- Global feed: `GeminiNewsService` kullanıyor (eski, tek tek analiz)
- Watchlist/Detail: `HermesCoordinator` → `HermesLLMService` kullanıyor (yeni, batch)
- İki farklı prompt, iki farklı model, iki farklı puanlama

**Kod Kanıtı:**
```swift
// TradingViewModel+Hermes.swift:137
let insight = try await GeminiNewsService.shared.analyzeNews(symbol: analysisSymbol, article: article)
```

**Etki:**
- Global feed'deki haberler farklı kalitede analiz ediliyor
- Puanlama tutarsız
- Rate limit sorunları (tek tek çağrı)

### 2.2 Prompt Sorunları ⚠️ ORTA

**Sorun:** `HermesLLMService.buildBatchPrompt()` içinde prompt **iki kez tekrar ediyor**:

```swift
// Satır 89-107: Aynı içerik iki kez yazılmış
return """
Sen Argus Terminal içindeki Hermes v2.1 modülüsün.
...
KURALLAR:
Sen Argus Terminal içindeki Hermes v2.2 modülüsün.  // TEKRAR!
...
```

**Etki:**
- LLM'e karışık mesaj gidiyor
- Token israfı
- Daha yavaş yanıt

### 2.3 Global Feed Context Sorunu ⚠️ KRİTİK

**Sorun:** Global feed için "GENERAL" veya "MARKET" sembolü kullanılıyor:

```swift
// TradingViewModel+Hermes.swift:135
let analysisSymbol = isGeneral ? "MARKET" : symbol
```

LLM'e şöyle bir prompt gidiyor:
```
"Analyze this news. First, IDENTIFY the main company/asset mentioned. 
Then analyze the impact for THAT asset."
```

**Sorunlar:**
1. LLM hangi şirketi analiz ettiğini belirtmiyor
2. `NewsInsight.symbol` alanı "MARKET" veya "GENERAL" oluyor
3. UI'da hangi hisse için haber olduğu belirsiz
4. Cache'de sembol bazlı saklanamıyor

**Etki:**
- Global feed'deki haberler hangi hisseye ait olduğu belirsiz
- Filtreleme yapılamıyor
- Cache çalışmıyor

### 2.4 Puanlama Mekanizması Sorunları ⚠️ YÜKSEK

#### A. Sentiment-Score Alignment (Hallucination Fix)

**Mevcut Kod:**
```swift
// HermesLLMService.swift:37-51
if sentiment == "POSITIVE" && correctedScore < 55 {
    correctedScore = max(70.0, correctedScore + 30.0) // +30 boost
} else if sentiment == "NEGATIVE" && correctedScore > 45 {
    correctedScore = min(30.0, correctedScore - 30.0) // -30 crush
}
```

**Sorunlar:**
1. **Aşırı Düzeltme:** +30/-30 çok agresif, orijinal skoru tamamen değiştiriyor
2. **Mantık Hatası:** LLM "POSITIVE" deyip 50 vermişse, bu "hafif pozitif" olabilir, 70'e çıkarmak yanlış
3. **Threshold Sorunları:** 55 ve 45 threshold'ları keyfi

**Örnek Senaryo:**
- LLM: "POSITIVE, 52" → Sistem: "70" yapıyor (18 puan boost)
- LLM: "NEGATIVE, 48" → Sistem: "30" yapıyor (18 puan düşürme)

Bu, LLM'in ince ayarlarını yok ediyor.

#### B. Puanlama Aralıkları

**Prompt'ta Belirtilen:**
```
- POSITIVE: 65 - 100 arası
- NEGATIVE: 0 - 35 arası  
- NEUTRAL: 45 - 55 arası
```

**Sorun:** 35-45 ve 55-65 arası "gri bölge" tanımsız. LLM bu aralıklarda skor verirse ne olacak?

#### C. Ortalama Skor Hesaplama

**Mevcut:**
```swift
// HermesCoordinator.swift:33-34
let total = summaries.map { Double($0.impactScore) }.reduce(0.0, +)
let avg = total / Double(summaries.count)
```

**Sorun:** Basit aritmetik ortalama. Ağırlıklı ortalama yok:
- Yeni haberler daha önemli olabilir
- Yüksek impact score'lu haberler daha ağırlıklı olmalı
- Ripple effect score dikkate alınmıyor

### 2.5 Cache Mekanizması Sorunları ⚠️ ORTA

**Sorun:** Global feed için cache kontrolü yok:

```swift
// TradingViewModel+Hermes.swift:118-125
for article in topArticles {
    // Check if we already analyzed this article
    let targetList = isGeneral ? self.generalNewsInsights : self.watchlistNewsInsights
    
    if let existing = targetList.first(where: { $0.articleId == article.id }) {
        insights.append(existing)
        continue
    }
    // ...
}
```

**Sorunlar:**
1. Sadece memory'deki `generalNewsInsights` kontrol ediliyor
2. `HermesCacheStore` kullanılmıyor
3. Uygulama yeniden başlatıldığında cache kayboluyor

### 2.6 Fallback Mekanizması Devre Dışı ⚠️ YÜKSEK

**Mevcut Kod:**
```swift
// HermesCoordinator.swift:76-84
} catch {
    print("Hermes AI Error: \(error)")
    // Fallback DISABLED per user request (If Groq fails, return 0/Empty)
    // We return empty results so Argus treats Hermes as unavailable (nil score)
}
```

**Sorun:**
- LLM başarısız olursa **hiçbir şey dönmüyor**
- Kullanıcı boş ekran görüyor
- Lite mode devre dışı (satır 66-69)

**Etki:**
- Rate limit durumunda tüm Hermes modülü çalışmıyor
- Kullanıcı deneyimi kötü

### 2.7 Rate Limiting Sorunları ⚠️ ORTA

**Sorun:** Global feed için rate limiting yok:

```swift
// TradingViewModel+Hermes.swift:130-131
let sleepTime: UInt64 = isGeneral ? 500_000_000 : 1_500_000_000 // 0.5s vs 1.5s
```

**Sorunlar:**
1. 0.5 saniye çok kısa, rate limit'e takılabilir
2. Batch analiz kullanılmıyor (tek tek çağrı)
3. `GroqClient` rate limiter'ı var ama `GeminiNewsService` kendi rate limiter'ını kullanıyor

---

## 3. PUANLAMA MEKANİZMASI DETAYLI ANALİZ

### 3.1 Mevcut Puanlama Akışı

```
1. LLM Analizi (Groq/Llama 3.1 8B)
   ↓
2. Sentiment + Impact Score Döner
   ↓
3. Sentiment-Score Alignment Check (Hallucination Fix)
   - POSITIVE + Score < 55 → +30 boost, min 70
   - NEGATIVE + Score > 45 → -30 crush, max 30
   - NEUTRAL → 50'e çek
   ↓
4. Final Impact Score (0-100)
   ↓
5. Ortalama Hesaplama (Basit Aritmetik)
```

### 3.2 Sorunlu Senaryolar

#### Senaryo 1: Hafif Pozitif Haber
- **LLM Çıktısı:** "POSITIVE", 58
- **Sistem Düzeltmesi:** 58 < 55 değil, değişiklik yok
- **Sonuç:** 58 (Doğru)

#### Senaryo 2: Çok Hafif Pozitif Haber
- **LLM Çıktısı:** "POSITIVE", 52
- **Sistem Düzeltmesi:** 52 < 55 → +30 boost → 82, min 70 → **70**
- **Sonuç:** 70 (Yanlış! LLM 52 demişti, 70'e çıktı)

#### Senaryo 3: Nötr Ama Pozitif Eğilimli
- **LLM Çıktısı:** "NEUTRAL", 60
- **Sistem Düzeltmesi:** NEUTRAL → 50'e çek
- **Sonuç:** 50 (Yanlış! LLM 60 demişti, 50'ye düştü)

### 3.3 Önerilen Puanlama Sistemi

```swift
// Daha yumuşak düzeltme
if sentiment == "POSITIVE" && correctedScore < 55 {
    // LLM "pozitif" demiş ama skor düşük → Hafif boost
    correctedScore = min(65.0, correctedScore + 10.0) // +10, max 65
} else if sentiment == "NEGATIVE" && correctedScore > 45 {
    // LLM "negatif" demiş ama skor yüksek → Hafif düşürme
    correctedScore = max(35.0, correctedScore - 10.0) // -10, min 35
} else if sentiment == "NEUTRAL" {
    // Nötr → 45-55 arasına çek (daha geniş aralık)
    if correctedScore > 55 {
        correctedScore = 55.0
    } else if correctedScore < 45 {
        correctedScore = 45.0
    }
    // 45-55 arasındaysa olduğu gibi bırak
}
```

---

## 4. GLOBAL FEED SORUNLARI DETAYLI

### 4.1 Mevcut Akış

```
loadGeneralFeed()
    ↓
loadNewsAndInsights(for: "GENERAL", isGeneral: true)
    ↓
AggregatedNewsService.fetchNews(symbol: "GENERAL", limit: 20)
    ↓
GeminiNewsService.analyzeNews(symbol: "MARKET", article: article)
    ↓
NewsInsight(symbol: "MARKET" veya "GENERAL")
    ↓
generalNewsInsights.append(insight)
```

### 4.2 Sorunlar

1. **Sembol Belirsizliği:** `NewsInsight.symbol` = "MARKET" veya "GENERAL"
2. **LLM Context Eksik:** LLM'e hangi şirket analiz edileceği söylenmiyor
3. **Cache Çalışmıyor:** Sembol bazlı cache yok
4. **Filtreleme Yapılamıyor:** UI'da "AAPL haberleri" gösterilemiyor

### 4.3 Önerilen Çözüm

**Yaklaşım 1: LLM'den Sembol Çıkarma**
```swift
// LLM'e prompt:
"Analyze this news and identify:
1. Main company/ticker mentioned (e.g., AAPL, TSLA)
2. Impact score for that company
3. Related tickers if any"

// LLM Response:
{
  "symbol": "AAPL",  // LLM tespit etti
  "impact_score": 75,
  "related_tickers": ["MSFT", "GOOGL"]
}
```

**Yaklaşım 2: NER (Named Entity Recognition)**
- Haber başlığından ticker çıkarma
- Alias mapping kullanma (Apple → AAPL)

---

## 5. MİMARİ YETERLİLİK DEĞERLENDİRMESİ

### 5.1 Güçlü Yönler ✅

1. **Cache Sistemi:** `HermesCacheStore` mevcut
2. **Batch Analiz:** `HermesLLMService.analyzeBatch()` var
3. **Error Handling:** Try-catch blokları var
4. **Rate Limiting:** `GroqClient` içinde rate limiter var

### 5.2 Zayıf Yönler ❌

1. **İki Farklı Servis:** `GeminiNewsService` ve `HermesLLMService` paralel
2. **Tutarsız Prompt:** İki farklı prompt formatı
3. **Global Feed Eksik:** Global feed için özel mantık yok
4. **Fallback Yok:** LLM başarısız olursa hiçbir şey dönmüyor
5. **Puanlama Karmaşık:** Çok fazla düzeltme, orijinal skor kayboluyor

### 5.3 Yeterlilik Skoru: **5/10** ⚠️

**Neden Düşük:**
- Global feed çalışmıyor (sembol belirsizliği)
- LLM servisi karmaşası
- Puanlama tutarsız
- Fallback yok

---

## 6. ÖNERİLEN ÇÖZÜMLER

### 6.1 Acil Düzeltmeler (P0)

#### 1. LLM Servisi Birleştirme
- `GeminiNewsService`'i kaldır
- Tüm analizler `HermesLLMService` üzerinden yapılsın
- Global feed için de `HermesCoordinator` kullan

#### 2. Prompt Düzeltme
- Tekrarlanan prompt'u temizle
- Global feed için özel prompt ekle (sembol tespiti)

#### 3. Fallback Ekleme
- Lite mode'u geri getir (basit keyword matching)
- LLM başarısız olursa lite mode kullan

### 6.2 Orta Vadeli İyileştirmeler (P1)

#### 1. Puanlama İyileştirme
- Sentiment-score alignment'ı yumuşat (+10/-10)
- Ağırlıklı ortalama ekle (yeni haberler + ripple effect)

#### 2. Global Feed İyileştirme
- LLM'den sembol çıkarma
- NER (Named Entity Recognition) ekle
- Cache'i sembol bazlı yap

#### 3. Rate Limiting İyileştirme
- Global feed için batch analiz kullan
- Daha akıllı rate limiting (exponential backoff)

### 6.3 Uzun Vadeli İyileştirmeler (P2)

#### 1. Çoklu LLM Desteği
- Groq başarısız olursa OpenAI'ye geç
- Model seçimi (8B vs 70B) akıllı yapılsın

#### 2. Real-time Feed
- WebSocket ile canlı haber akışı
- Push notification desteği

---

## 7. KOD ÖRNEKLERİ

### 7.1 Önerilen Global Feed Çözümü

```swift
// TradingViewModel+Hermes.swift - loadGeneralFeed() güncellemesi
func loadGeneralFeed() {
    isLoadingNews = true
    
    Task {
        do {
            // 1. Fetch General News
            let articles = try await AggregatedNewsService.shared.fetchNews(symbol: "GENERAL", limit: 20)
            
            // 2. Use HermesCoordinator (not GeminiNewsService)
            let summaries = await HermesCoordinator.shared.processNews(articles: articles, allowAI: true)
            
            // 3. Map to NewsInsight (extract symbol from LLM response)
            let insights = summaries.map { summary in
                NewsInsight(
                    symbol: summary.symbol, // LLM'den gelen sembol
                    articleId: summary.id,
                    headline: summary.summaryTR,
                    impactScore: Double(summary.impactScore),
                    // ...
                )
            }
            
            await MainActor.run {
                self.generalNewsInsights = insights
                self.isLoadingNews = false
            }
        } catch {
            // Fallback to Lite Mode
            await MainActor.run {
                self.isLoadingNews = false
                // Show cached or lite mode results
            }
        }
    }
}
```

### 7.2 Önerilen Prompt İyileştirmesi

```swift
// HermesLLMService.swift - buildBatchPrompt() güncellemesi
private func buildBatchPrompt(_ articles: [NewsArticle], isGeneral: Bool = false) -> String {
    let contextInstruction = isGeneral 
        ? """
        ÖNEMLİ: Bu haberler genel piyasa haberleri. Her haber için:
        1. Ana şirket/ticker'ı tespit et (örn: "Apple" → "AAPL")
        2. O şirket için impact score hesapla
        3. İlgili sektörleri belirle
        """
        : """
        Bu haberler belirli bir sembol için. Analiz o sembol için yapılmalı.
        """
    
    return """
    Sen Argus Terminal içindeki Hermes v2.3 modülüsün.
    \(contextInstruction)
    
    GİRDİ:
    \(articlesText)
    
    PUANLAMA KURALLARI:
    - POSITIVE: 65-100 (65 = Hafif, 100 = Game Changer)
    - NEGATIVE: 0-35 (0 = Kriz, 35 = Hafif)
    - NEUTRAL: 45-55
    
    ÇIKTI FORMATI:
    {
      "results": [
        {
          "id": "...",
          "symbol": "AAPL",  // Global feed için LLM tespit etsin
          "summary_tr": "...",
          "impact_comment_tr": "...",
          "sentiment": "POSITIVE",
          "impact_score": 75,
          "related_sectors": ["Tech"],
          "ripple_effect_score": 60
        }
      ]
    }
    """
}
```

---

## 8. SONUÇ VE ÖNERİLER

### 8.1 Genel Değerlendirme

**Hermes modülü şu anda YETERSİZ durumda:**

1. ❌ Global feed çalışmıyor (sembol belirsizliği)
2. ❌ LLM servisi karmaşası (iki farklı servis)
3. ⚠️ Puanlama tutarsız (aşırı düzeltme)
4. ❌ Fallback yok (LLM başarısız olursa hiçbir şey dönmüyor)
5. ⚠️ Prompt sorunları (tekrar, karışık mesaj)

### 8.2 Öncelik Sırası

1. **P0 (Acil):** LLM servisi birleştirme, prompt düzeltme
2. **P1 (Yüksek):** Global feed sembol tespiti, fallback ekleme
3. **P2 (Orta):** Puanlama iyileştirme, rate limiting

### 8.3 Tahmini İyileştirme Süresi

- **P0 Düzeltmeler:** 4-6 saat
- **P1 İyileştirmeler:** 8-12 saat
- **P2 İyileştirmeler:** 16-24 saat

**Toplam:** ~30-40 saat çalışma ile Hermes modülü production-ready hale getirilebilir.

---

**Rapor Hazırlayan:** AI Assistant  
**Tarih:** 2025  
**Versiyon:** 1.0
