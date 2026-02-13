# ARGUS v2.5: Reflector (Quant Forensic Module)

**Role:** Quant Forensic Scientist & ML Architect
**Objective:** Automated Post-Trade Analysis & Parameter Tuning.
**Philosophy:** "Fail Fast, Learn Faster".

---

## 1. Post-Mortem Analysis (The Autopsy)

### What
Her kapanan işlemden (Trade Closed) sonra tetiklenen bir analiz motorudur. Eğer işlem zararla kapandıysa (Loss) veya beklenen kârdan az getiri sağladıysa, "Heavy Mode" devreye girer.

### Why
Yatırımcılar genellikle sadece PnL'e bakar. "Neden kaybettim?" sorusuna "Piyasa kötüydü" deyip geçerler. Reflector ise "Stop Loss %0.5 daha aşağıda olsaydı ne olurdu?" sorusunu matematiksel olarak cevaplar.

### How
*   **Trigger:** `src/main.py` veya `AuditManager` kapanan işlemi `Reflector.analyze(trade)` fonksiyonuna gönderir.
*   **Data Slice:** İşlem anından önceki 1 saat ve sonraki 4 saatlik (Counterfactual) veriyi Polars ile RAM'e çeker.

---

## 2. Counterfactual Simulations ("What If?" Scenarios)

### What
Gerçekleşen işlem üzerinde parametreleri değiştirerek 1000'lerce simülasyon yapma tekniği.

### Scenarios
1.  **Timing Shift:** Giriş zamanını -5dk ile +15dk arasında kaydır. (Erken mi girdik, geç mi kaldık?)
2.  **Stop Loss Sensitivity:** SL seviyesini %0.1 adımlarla genişlet/daralt. (SL avına mı kurban gittik?)
3.  **Take Profit Sensitivity:** TP seviyesini değiştir. (Erken mi çıktık?)

### Optimization
Bu simülasyonlar Python döngüleriyle yapılırsa çok yavaştır. NumPy Broadcasting kullanarak vektörize edeceğiz. 1000 senaryo < 50ms sürmelidir.

---

## 3. Classification (Diagnosis)

### What
Kaybın (veya başarısızlığın) kök nedenini etiketleme.

### Categories
*   **NOISE (Gürültü):** Fiyat SL'i patlatıp hemen geri döndü. (Çözüm: SL'i genişlet).
*   **BAD_TIMING (Zamanlama):** 5 dk sonra girseydik kazanacaktık. (Çözüm: Entry Threshold'u artır).
*   **REGIME_SHIFT (Rejim Değişimi):** Trend bekliyorduk, Chop başladı. (Çözüm: SQS filtresini sıkılaştır).
*   **EXECUTION (Uygulama):** Slippage yüzünden kaybettik. (Çözüm: Limit emir kullan).

---

## 4. Adjustment Vector (Action Plan)

### What
Mevcut varlığın (Asset) Genom'una uygulanacak "ince ayar" vektörü. Darwin Engine'in aksine, bu modül genleri rastgele mutasyona uğratmaz; bilinçli olarak yönlendirir.

### How
Eğer "NOISE" hatası sıklaşıyorsa -> `AdjustmentVector(sl_atr_mult=+0.2)`.
Bu vektör, bir sonraki `DarwinEngine.evolve()` döngüsünde "Targeted Mutation" olarak kullanılır.

---

## Architecture

```mermaid
graph TD
    TradeClosed --> CheckPnL{Is Loss?}
    CheckPnL -- No --> LogSuccess
    CheckPnL -- Yes --> FetchContext[Get 1h Pre/4h Post Data]

    FetchContext --> SimLoop[Run 1000 Sims (NumPy)]
    SimLoop --> CompareResults

    CompareResults --> Classify{Reason?}
    Classify -- SL Hunt --> AdjustSL[Suggest Wider SL]
    Classify -- Early Entry --> AdjustEntry[Suggest Higher Threshold]

    AdjustEntry --> OutputVector[AdjustmentVector]
    OutputVector --> Database[Save for Next Evolution]
```
