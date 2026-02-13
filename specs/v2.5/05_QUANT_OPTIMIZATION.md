# ARGUS v2.5: Senior Quant Optimization Strategy

**Role:** Senior Lead Quant Engineer (Ex-Renaissance/Two Sigma)
**Objective:** Optimize ARGUS v2.5 for "Survival First" High-Sharpe Performance on RTX A3000M.

---

## 1. Memory-Efficient Modeling: FinBERT & XGBoost Concurrency

### 1.1. Quantized Inference (ONNX Runtime)

**What:**
FinBERT modelini `PyTorch` (default) üzerinden değil, **ONNX Runtime** (Open Neural Network Exchange) üzerinden ve **INT8 Quantization** (8-bit tamsayı) ile çalıştırmak.

**Why:**
Standart PyTorch FP32 inference, 6GB VRAM'in önemli bir kısmını (%30-40) rezerve edebilir ve GPU Context Switch maliyeti yaratır. RTX A3000M, Tensor Core'lara sahiptir ve INT8 işlemlerinde FP32'ye göre 4x daha hızlıdır.
*   **VRAM Tasarrufu:** Model boyutu ~450MB'dan ~110MB'a düşer.
*   **Latency:** CPU darboğazını (bottleneck) aşar.

**How:**
1.  **Export to ONNX:** HuggingFace `optimum` kütüphanesi ile modeli ONNX formatına dönüştürün.
    ```python
    from optimum.onnxruntime import ORTModelForSequenceClassification
    from transformers import AutoTokenizer

    # Load & Quantize
    model = ORTModelForSequenceClassification.from_pretrained("ProsusAI/finbert", export=True)
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model.save_pretrained("models/finbert_onnx_int8")
    ```
2.  **Hybrid Execution Strategy:**
    *   **FinBERT (GPU):** ONNX Runtime `CUDAExecutionProvider` ile GPU'da çalışır. (VRAM: <200MB).
    *   **XGBoost (CPU):** XGBoost modellerini `TreeLite` kütüphanesi ile C++ koduna derleyip (compiled models) CPU üzerinde çalıştırın. Bu, GPU VRAM'ini tamamen FinBERT ve Grafik işlemleri için boş bırakır ve XGBoost inference süresini mikrosaniye seviyesine indirir.

---

## 2. Market Regime Switching: Gaussian HMM Integration

### 2.1. Hidden Markov Models (HMM)

**What:**
Piyasanın görünmeyen "gizli durumlarını" (Hidden States) istatistiksel olarak tahmin eden bir gözetimsiz öğrenme (Unsupervised Learning) modelidir. 3 Durumlu (3-State) Gaussian HMM kurgulanacak.

**Why:**
"Survival First" felsefesi, piyasa rejimine (Trend vs. Mean Reverting) göre strateji değiştirmeyi gerektirir. Basit ADX/RSI filtreleri gecikmelidir (lagging). HMM, olasılıksal (probabilistic) bir yaklaşımla rejim değişikliğini daha erken tespit edebilir.

**How:**
1.  **Feature Engineering:** Log-Returns ve Volatility (GARCH(1,1) conditional volatility) kullanın.
2.  **States:**
    *   **State 0 (Low Vol / Bull):** Yüksek Sharpe, düşük varyans. -> **FULL RISK ON.**
    *   **State 1 (High Vol / Bear):** Negatif getiri, yüksek varyans. -> **SHORT ONLY or CASH.**
    *   **State 2 (High Vol / Chop):** Yön belirsiz, varyans çok yüksek. -> **SLEEP MODE.**
3.  **Sleep Mode Trigger:**
    *   Eğer `HMM_Prob(State 2) > 0.8` ise: Tüm alım-satım sinyallerini (SQS) `VETO` et. Mevcut pozisyonları `Tighten Stop Loss` moduna al.

---

## 3. Position Sizing: Fractional Kelly Criterion (Risk Engine)

### 3.1. Reflector-Driven Kelly

**What:**
Sabit lot (Fixed Fractional) yerine, sistemin o anki "kazanma olasılığına" göre sermaye tahsis eden dinamik bir algoritma.

**Why:**
Standart Kelly Kriteri ($f^* = p - q/b$) agresiftir ve "Ruin" (iflas) riski taşır. Biz **Fractional Kelly** ($c \times f^*$) kullanarak büyümeyi optimize ederken volatiliteyi düşüreceğiz. Reflector modülü, geçmiş simülasyonlardan gelen *gerçekçi* `p` (Win Probability) ve `b` (Win/Loss Ratio) değerlerini sağlar.

**How:**
Algoritma Şeması:
1.  **Reflector Input:** Son 50 işlemin "Simulated Outcome" verisinden `p_hat` (tahmini kazanma oranı) ve `b_hat` (tahmini Reward/Risk) çekilir.
2.  **Kelly Calculation:**
    $$ f^* = \frac{p_{hat} \times b_{hat} - (1 - p_{hat})}{b_{hat}} $$
3.  **Survival Constraints (Critical):**
    *   **Fraction ($c$):** 0.3 (Conservative) ile 0.5 (Aggressive) arasında dinamik değişir (Regime State'e göre).
    *   **Volatility Scaling:** $f_{final} = f^* \times \frac{TargetVol}{\sigma_{current}}$.
    *   **Max Allocation:** Asla portföyün %20'sinden fazlasını tek işleme bağlama (Leverage dahil).

---

## 4. SOTA Integration: MLFinLab & VectorBT

### 4.1. Fractional Differentiation (Stationarity)

**What:**
Fiyat verisini (Time Series) durağan (stationary) hale getirirken "hafızayı" (memory) silmeyen bir dönüşüm tekniği. Standart fark alma (Differencing, d=1) hafızayı siler; Fractional (d=0.4 gibi) silmez.

**Why:**
ML modelleri (XGBoost/LSTM) durağan veri ister. Ancak trend bilgisini (hafıza) kaybederseniz modeliniz "kör" olur. Lopez de Prado'nun bu tekniği, hem istatistiksel geçerliliği hem de prediktif gücü korur.

**How:**
*   **Library:** `tsfracdiff` veya `mlfinlab`.
*   **Implementation:** OHLC verisine `FracDiff(d=FindMinD())` uygulayarak yeni bir feature seti (`close_frac`, `vol_frac`) oluşturun ve XGBoost'a bunu verin.

### 4.2. Triple Barrier Method (Labeling)

**What:**
Klasik "sabit zamanlı" (fixed-time horizon) etiketleme yerine, 3 bariyerli (Üst, Alt, Zaman) dinamik etiketleme.
1.  **Upper Barrier:** Take Profit (ör. +2x Volatilite).
2.  **Lower Barrier:** Stop Loss (ör. -1x Volatilite).
3.  **Vertical Barrier:** Max Time (ör. 48 bar).

**Why:**
Piyasa zamanla değil, fiyatla hareket eder. Sabit zamanlı etiketleme (ör. "10 bar sonra fiyat > %1 mi?") gürültülüdür. Triple Barrier, gerçekçi işlem başarısını (Path Dependency) simüle eder.

**How:**
*   **Library:** `mlfinlab` labeling module.
*   **Integration:** Darwin Engine, strateji başarısını (Fitness) ölçerken sadece PnL'e değil, "Hangi bariyere, ne kadar sürede çarptı?" verisine de bakmalı.

---

## 5. Anti-Overfitting: Purged K-Fold Cross-Validation

### 5.1. Combinatorial Purged CV

**What:**
Finansal verilerde "sızıntıyı" (leakage) önlemek için standart K-Fold yerine, eğitim ve test setleri arasına "tampon" (embargo) koyan ve test setini eğitim setinden tamamen yalıtan bir validasyon yöntemi.

**Why:**
Standart CV'de, Test setinin hemen öncesindeki eğitim verisi, Test setindeki geleceği "görebilir" (çünkü indikatörler/feature'lar örtüşür). Bu, Backtest'te %300 kazanç, Live'da %100 kayıp demektir.

**How:**
1.  **Purging:** Test setinin başlangıç zamanından `Lookback_Window` kadar önceki veriyi Eğitim setinden silin.
2.  **Embargo:** Test setinin bitiş zamanından `Hold_Period` kadar sonraki veriyi Eğitim setinden silin (işlem süresi sızıntısını önlemek için).
3.  **Implementation:** `sklearn.model_selection` yerine `mlfinlab.cross_validation.PurgedKFold` kullanın. Darwin Engine, her jenerasyonda stratejileri bu yöntemle (farklı zaman dilimlerinde) test etmeli, sadece tüm "Fold"larda başarılı olanı seçmelidir.

---

## Summary of Optimization Plan

| Module | Technique | Library/Tool | Benefit |
| :--- | :--- | :--- | :--- |
| **NLP** | INT8 Quantization + ONNX | `optimum` | Low VRAM Usage, Fast Inference |
| **Regime** | Gaussian HMM (3-State) | `hmmlearn` | Early Regime Detection |
| **Sizing** | Fractional Kelly w/ Vol Scaling | Custom | Risk-Optimal Growth |
| **Features** | Fractional Differentiation | `tsfracdiff` | Memory + Stationarity |
| **Labels** | Triple Barrier Method | `mlfinlab` | Realistic Trade Simulation |
| **Validation** | Purged K-Fold CV | `mlfinlab` | True Out-of-Sample Performance |
