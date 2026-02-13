# ARGUS v2.5: Data Integrity & Validation Architecture

**Role:** Senior Data Integrity Specialist (Ex-HFT Infrastructure Architect)
**Objective:** Engineer a Zero-Trust Data Pipeline.
**Philosophy:** "Trust, but Verify" -> "Verify, then Trust".

---

## 1. Cross-Exchange Validation (BingX vs. Binance)

### What
Birincil veri kaynağımız (BingX) ile piyasanın en likit kaynağını (Binance) saniyelik bazda karşılaştıran ve fiyat sapmalarını (Price Deviation) raporlayan mekanizma.

### Why
Borsalar bazen "Flash Crash" veya "API Glitch" yaşayabilir. Eğer BingX fiyatı %5 düşmüş ama Binance sabitse, bu gerçek bir piyasa hareketi değil, borsaya özel bir anomalidir. Bu veriye güvenerek işlem açmak (özellikle kaldıraçlı) intihardır.

### How
`ccxt` kütüphanesini kullanarak asenkron olarak Binance verisini çekeceğiz. Polars `join_asof` veya `join` kullanarak iki zaman serisini eşleştireceğiz.
*   **Threshold:** %0.3 (30 bps).
*   **Action:** Eğer sapma > %0.3 ise, o veri bloğunu "UNTRUSTED" olarak işaretle ve `RiskManager`'ı uyar (Halt Trading).

---

## 2. Outlier Guard (Z-Score Anomaly Detection)

### What
Fiyat ve Hacim serilerindeki istatistiksel sapmaları (Outliers) tespit eden filtre.
*   **Z-Score:** $(Value - Mean) / StdDev$.

### Why
HFT verilerinde bazen "Bad Tick" (hatalı fiyat) gelir. Fiyat 100 -> 200 -> 100 olur (milisaniyelik). Eğer bu veriyi GARCH modeline sokarsan, volatilite tahminin tavan yapar ve sistem gereksiz yere pozisyon kapatır.

### How
Polars `rolling_mean` ve `rolling_std` kullanarak hareketli Z-Score hesaplayacağız.
*   **Window:** 100 bar.
*   **Threshold:** Z > 4.0 (Standart sapmanın 4 katı).
*   **Action:** Hatalı veriyi `null` yap veya önceki değerle doldur (Forward Fill), ve logla.

---

## 3. Gap-Report (Discontinuity Analysis)

### What
Veri setindeki zaman damgaları (Timestamp) arasındaki farkları analiz eden raporlama sistemi.

### Why
Backtest yaparken "DataFactory" boşlukları doldurduğunu iddia etse de, bazen borsada hiç işlem olmayan dakikalar olabilir (Illiquid Assets). Bu "doğal boşluklar" ile "veri kaybı" arasındaki farkı anlamalıyız.

### How
Polars `diff()` fonksiyonu ile `delta_t = ts[i] - ts[i-1]` hesaplanır.
*   **Expected:** 60,000 ms (1 dakika).
*   **Anomaly:** `delta_t > 60,000`.
*   **Report:** Boşlukların başladığı ve bittiği zamanları listele.

---

## 4. Lock-Verification (Future Leakage Test)

### What
Backtest motorunun kalbi olan `DataLock` sınıfının, gelecekteki veriyi (Future Data) sızdırıp sızdırmadığını matematiksel olarak kanıtlayan test prosedürü.

### Why
En yaygın backtest hatası "Look-ahead Bias"tır. Kodun bir yerinde `df['close'].shift(-1)` unutulursa, strateji geleceği görür ve %100 kazanır. Bu testi geçemeyen hiçbir backtest motoru canlıya alınamaz.

### How
Bir Unit Test yazacağız:
1.  Yapay bir veri seti oluştur (0'dan 100'e artan fiyatlar).
2.  `DataLock.get_features_at(t=50)` çağır.
3.  Dönen verinin içinde `t=51` veya sonrası var mı kontrol et.
4.  Eğer tek bir satır bile sızmışsa -> **FAIL**.

---

## Implementation Plan

```mermaid
graph TD
    RawData[BingX Data] --> OutlierGuard{Z-Score > 4?}
    OutlierGuard -- Yes --> Flag[Mark as BAD_TICK]
    OutlierGuard -- No --> CrossCheck{Diff(Binance) > 0.3%?}

    CrossCheck -- Yes --> Flag
    CrossCheck -- No --> GapCheck{Delta_T > 1m?}

    GapCheck -- Yes --> LogGap[Log Gap Interval]
    GapCheck -- No --> CleanData[Clean Data Store]
```
