# ARGUS v2.5: Multi-Asset Evolutionary Optimization

**Role:** Senior ML Engineer & Quant Strategist
**Objective:** Autonomous Asset-Specific Tuning using Genetic Algorithms.
**Philosophy:** "One Size Fits None" -> Asset-Specific Adaptation.

---

## 1. Multi-Asset Population Management

### What
Tek bir genel popülasyon yerine, her varlık (Asset) için ayrı bir "Ada" (Island Model) popülasyonu yöneten yapı.

### Why
Bitcoin'in (BTC) volatilite karakteristiği ile Koç Holding'in (KCHOL) karakteristiği tamamen farklıdır. BTC için evrimleşmiş agresif bir RSI stratejisi, KCHOL'de felaket olabilir. Her varlığın kendi "mikro-evrimine" ihtiyacı vardır.

### How
`DarwinEngine` sınıfı artık `Dict[Symbol, List[Genome]]` yapısını tutacak.
*   **Isolation:** BTC genomları sadece BTC genomlarıyla çiftleşir.
*   **Scalability:** Yeni bir varlık eklendiğinde, `register_asset` fonksiyonu ile ona özel boş bir popülasyon yaratılır.

---

## 2. Dynamic Indicator Search Space

### What
Genom yapısını genişleterek, sadece parametreleri (ör. 14 vs 21) değil, hangi indikatörlerin kullanılacağını (ör. RSI vs MACD) da seçebilen esnek bir yapı.

### Why
Bazı varlıklar trend takibine (Moving Average) iyi tepki verirken, bazıları ortalamaya dönüşe (Bollinger Bands) iyi tepki verir. GA'nın bunu keşfetmesine izin vermeliyiz.

### How
Genom'a yeni genler ekleyeceğiz:
*   `use_rsi` (0 or 1)
*   `use_macd` (0 or 1)
*   `use_bollinger` (0 or 1)
*   `indicator_weight_rsi`: Sinyal birleştirme ağırlığı.

---

## 3. Hardware-Accelerated Evolution (Multi-Island)

### What
16 Thread'i verimli kullanmak için, varlıkları gruplayıp paralel işleme sokma.

### Why
Eğer 10 varlığımız varsa ve her biri için 64 bireyden oluşan bir popülasyon varsa, toplam 640 backtest yapmamız gerekir. Bunu sıralı yapmak çok yavaştır.

### How
`ProcessPoolExecutor`'a iş gönderirken, iş birimini (Task) "Tek bir Genom Backtesti" olarak tanımlayacağız.
`evaluate_all_assets()` fonksiyonu:
1.  Tüm varlıkların popülasyonlarını tek bir büyük listede topla (Flatten).
2.  `Executor.map` ile hepsini havuza at.
3.  Sonuçları alıp tekrar ilgili varlıkların popülasyonlarına dağıt.

---

## 4. Results Persistence (Champion Memory)

### What
Evrim sonucu ortaya çıkan "Şampiyon" (En yüksek Fitness puanlı) genomları diske JSON formatında kaydetme ve sistem yeniden başladığında geri yükleme.

### Why
Evrim pahalı bir işlemdir (CPU/Zaman). Eğer bot kapanıp açıldığında sıfırdan başlarsa, tüm öğrenilen bilgi kaybolur.

### How
`data/champions.json`:
```json
{
  "BTC/USDT": {
    "id": "gen_50_best",
    "genes": {"rsi_period": 14, "ema_short": 20, ...},
    "fitness": 4.5
  },
  "XAU/USDT": { ... }
}
```

---

## Architecture Diagram

```mermaid
graph TD
    Start[Startup] --> LoadChampions{Exists champions.json?}
    LoadChampions -- Yes --> LoadPop[Populate from File]
    LoadChampions -- No --> RandomPop[Init Random Genomes]

    Trigger[Evolution Trigger (Weekly)] --> Flatten[Flatten All Populations]

    Flatten --> Parallel[Executor Pool (16 Threads)]

    Parallel --> Backtest_BTC_Gen1
    Parallel --> Backtest_XAU_Gen5

    Backtest_BTC_Gen1 --> Score

    Score --> Selection[Select per Asset]
    Selection --> Crossover[Crossover per Asset]
    Selection --> Mutation[Mutate per Asset]

    Mutation --> Save[Save Best to JSON]
```
