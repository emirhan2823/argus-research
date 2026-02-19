# ARGUS Hedge Fund Bot — Full System Plan

**Tarih:** 2026-02-14 (v3 güncelleme)  
**Hedef:** $1 → $100 (temsili — $100 → $10K, $1K → $100K aynı oran)  
**Exchange:** BingX (crypto long/short/spot) + gelecekte IBKR (ABD hisse), BIST broker  
**Format:** 8B yerel model anlayacak açıklıkta  
**Kodlama:** AI Agent tarafından yapılacak

---

## 1) SİSTEM ÖZETİ

### Ne yapıyor?
Bot 7/24 çalışır. Piyasayı izler. Fırsat bulursa alır veya açığa satar. Kârı bileşik büyütür. Kayıp sınırlıdır. İnsan müdahalesi minimum.

### Temel kural
```
KORUMA > KAZANÇ

Önce kaybetme. Sonra kazan. Kazanınca bileşik büyüt.
```

### Varlık evreni

| Sınıf | Varlıklar | Exchange / Broker | Long/Short |
|-------|-----------|:------------------:|:----------:|
| Crypto | BTC, ETH, SOL, AVAX, DOGE, XRP | BingX Perpetual | ✅ / ✅ |
| Emtia | XAU (Altın), XAG (Gümüş) | BingX CFD | ✅ / ✅ |
| ABD Hisse | SPY, QQQ, AAPL, NVDA, TSLA | BingX Copy / gelecek: IBKR | ✅ / ✅ |
| TR Hisse | BIST30 endeks / seçili hisse | Gelecek: TR broker API | ✅ / kısıtlı |

> **BingX öncelikli.** Bot başlangıçta sadece BingX ile çalışır. Diğer broker'lar Phase 6'da eklenir.

---

## 2) $1 → $100 MATEMATİĞİ

### Bileşik büyüme formülü
```
final_equity = start × (1 + monthly_return) ^ months

$100 hedef ($1'den):
  - Aylık %20 compound → 24 ayda: 1 × 1.20^24 = $79.5  (~80×)
  - Aylık %25 compound → 20 ayda: 1 × 1.25^20 = $86.7  (~87×)
  - Aylık %22 compound → 24 ayda: 1 × 1.22^24 = $109   (~109×) ✅
```

### Aylık %22 nasıl elde edilir?

```
Ayda ~15 trade (ortalama)
Win rate: %55
Ortalama kazanç: +1.5R
Ortalama kayıp: -1.0R

Beklenen R/trade = (0.55 × 1.5) - (0.45 × 1.0) = +0.375R
15 trade × 0.375R = +5.6R / ay
Risk per trade: %1.5 equity
Aylık getiri: 5.6 × 1.5% = ~%8.4 (sadece core engine)

Accel engine (trend dönemleri):
- Ayda 3-4 trend trade × 2× risk = ekstra +%6-8

Pyramiding (güçlü trend):
- Ayda 1-2 pyramid × 1.8× size = ekstra +%5-7

TOPLAM: %8 + %7 + %6 = ~%21-22/ay
```

> [!CAUTION]
> Bu rakamlar **her ayın trend içermesini** varsayar. Pure chop aylarında getiri %3-5'e düşer. Ortalama hedef: **%15-22/ay over 24 months**.

---

## 3) SİSTEM MİMARİSİ

```
┌─────────────────────────────────────────────────┐
│                   ARGUS BOT                      │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Data Feed│→│  Regime   │→│ Signal Engine │  │
│  │ (BingX)  │  │ Detector │  │ (SQS/CHOP)   │  │
│  └──────────┘  └──────────┘  └──────┬───────┘  │
│                                      │          │
│                              ┌───────▼───────┐  │
│                              │  Entry/Exit   │  │
│                              │  Templates    │  │
│                              └───────┬───────┘  │
│                                      │          │
│  ┌──────────┐  ┌──────────┐  ┌───────▼───────┐  │
│  │ Compound │←│   Risk    │←│   Execution   │  │
│  │ Growth   │  │  Manager │  │   (BingX API) │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │         SQLite Database (Ledger)          │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Modül listesi (dosya bazında)

```
src/v25/
├── bot/
│   ├── main_loop.py          # Ana döngü: fetch → analyze → decide → execute
│   ├── scheduler.py          # Cycle zamanlama (5m, 15m)
│   └── health_check.py       # Bot canlı mı? Heartbeat
│
├── data/
│   ├── feed_bingx.py         # BingX OHLCV + orderbook + funding rate
│   ├── feed_generic.py       # Genel exchange adapter (gelecek)
│   ├── normalizer.py         # Ham veriyi standart DataFrame'e çevir
│   └── indicators.py         # ADX, BB, EMA, ATR, RSI hesaplama
│
├── signal/
│   ├── regime_classifier.py  # TREND / CHOP / VOLATILE / CRISIS tespit
│   ├── sqs_engine.py         # Sinyal kalite skoru (5 komponent)
│   ├── chop/
│   │   ├── detector.py       # CHOP tespiti + range builder
│   │   ├── edge_score.py     # ChopEdgeScore (5 komponent)
│   │   └── templates.py      # CHOP_EXTREME + CHOP_FAILED_BREAKOUT
│   ├── trend/
│   │   ├── templates.py      # TREND_PULLBACK + TREND_BREAKOUT
│   │   └── momentum.py       # ADX/EMA slope momentum scorer
│   └── multi_tf.py           # Multi-timeframe fusion (5m+15m+1h+4h)
│
├── risk/
│   ├── position_sizer.py     # Kelly + regime-aware sizing
│   ├── exposure_manager.py   # Toplam exposure limitleri
│   ├── circuit_breaker.py    # Drawdown kademeli savunma
│   ├── cash_governor.py      # Min nakit tutma
│   ├── correlation_guard.py  # Korelasyon kontrolü
│   └── black_swan.py         # Flash crash dedektörü
│
├── growth/
│   ├── compounder.py         # Bileşik büyüme motoru
│   ├── pyramiding.py         # Trend'de katmanlı pozisyon ekleme
│   ├── accel_engine.py       # Dual pool: core + accel
│   ├── equity_momentum.py    # Equity curve trend okuma
│   └── alpha_rotation.py     # Multi-asset rotasyon
│
├── execution/
│   ├── bingx_client.py       # BingX API wrapper
│   ├── order_manager.py      # Limit/market order + cancel + status
│   ├── slippage_tracker.py   # Fill kalitesi izleme
│   └── hedging.py            # Pairs trade execution
│
├── exit/
│   ├── stop_manager.py       # SL yerleştirme + BE move + trailing
│   ├── tp_manager.py         # TP hesaplama + partial close
│   ├── time_stop.py          # Zaman bazlı çıkış
│   └── hard_exits.py         # Volatilite / regime flip / spread anomali
│
├── db/
│   ├── migrations.py         # ✅ Mevcut (13 tablo)
│   ├── ledger.py             # Equity tracking + PnL kayıt
│   └── trade_log.py          # Trade CRUD + features_json
│
├── postmortem/
│   ├── tagger.py             # Trade etiketleme (avoidable? overtraded?)
│   ├── edge_health.py        # Strateji performans bozulma tespiti
│   ├── counterfactual.py     # "Yapmasaydık ne olurdu?" analizi
│   └── weekly_report.py      # Haftalık performans raporu
│
├── contracts/                # ✅ Mevcut (16 pydantic model)
├── config/                   # ✅ Mevcut (YAML loader)
├── bootstrap.py              # ✅ Mevcut (public seam)
└── telemetry/                # ✅ Mevcut (log writer)
```

---

## 4) ANA DÖNGÜ (HER 5 DAKİKA)

```
WHILE bot_running:

  1. FETCH
     - BingX'ten son 100 bar OHLCV al (5m)
     - BingX'ten son 40 bar OHLCV al (15m, 1h, 4h)
     - Funding rate, spread, volume al
     - Eventler varsa (CPI, FOMC) takvimden kontrol et

  2. INDICATORS
     - ADX(14), BB(20,2), EMA(21), ATR(14), RSI(14) hesapla
     - Her timeframe için ayrı ayrı hesapla

  3. REGIME
     - classify_regime() → TREND_STRONG / TREND_WEAK / CHOP / VOLATILE / CRISIS
     - Multi-TF fusion: 4 TF'den birleşik karar

  4. RISK CHECK (ÖNCELİKLİ)
     - circuit_breaker: DD seviyesi kontrol → trade açılabilir mi?
     - black_swan: flash crash var mı?
     - exposure: max exposure aşıldı mı?
     - cash_governor: yeterli nakit var mı?
     - Herhangi biri FAIL → bu cycle SKIP, sadece exit kontrol

  5. SIGNAL (regime'e göre rota)
     IF regime == TREND:
       → SQS compute → trend templates evaluate
     IF regime == CHOP:
       → ChopEdgeScore compute → chop templates evaluate
     IF regime == VOLATILE:
       → Yalnızca çok yüksek SQS (>0.88) + küçük size
     IF regime == CRISIS:
       → Sıfır yeni pozisyon. Tüm açıkları kapat.

  6. SIZE
     - position_sizer: regime + kelly + equity curve → lot size
     - compounder: current equity × risk_pct (compound mode)
     - accel check: 9 gate pass → accel pool'dan büyük size

  7. EXECUTE
     - Sinyal PASS → order_manager.place_order()
     - Limit-first: limit order at edge, X bar timeout
     - Fill sonrası → slippage_tracker.record()

  8. EXIT CHECK (her cycle, pozisyon varsa)
     - stop_manager: SL hit mi? BE move zamanı mı?
     - tp_manager: TP'ye ulaştı mı? Partial close?
     - time_stop: Max bar aşıldı mı?
     - hard_exits: vol spike? regime flip? spread anomalisi?

  9. LOG
     - Trade açıldı/kapandı → trade_log + ledger güncelle
     - SQS/CHOP score → sqs_log tablosuna yaz
     - Reject → counterfactual tablosuna yaz
     - Equity → equity_snapshots tablosuna yaz

  10. SLEEP
      - Sonraki 5m bar'a kadar bekle

END WHILE
```

---

## 5) STRATEJİ DETAYLARI

### 5.1 — TREND Stratejisi (Ana kâr kaynağı)

**Amaç:** Güçlü trend'leri erkenden yakala ve sonuna kadar sür.

| Template | Koşul | Hedef |
|----------|-------|-------|
| TREND_PULLBACK | Trend yönünde geri çekilme + EMA destek + RSI 40-60 | 2-4R |
| TREND_BREAKOUT | Key level kırılması + hacim doğrulaması + ADX > 25 | 3-6R |

**Trend'de özel kurallar:**
- Trailing stop aktif: ATR(14) × 2.0
- Pyramiding aktif: +1R'da ekle, +2R'da tekrar ekle
- Accel engine: tüm gate'ler geçerse 2× risk
- Target: Büyük R, sınırsız yukarı. Trend bitene kadar tut.

### 5.2 — CHOP Stratejisi (Sermaye koruma + küçük kâr)

**Amaç:** Range piyasada sınıf kenarlarından küçük ama tutarlı kâr.

| Template | Koşul | Hedef |
|----------|-------|-------|
| CHOP_EXTREME | Range kenarında wick rejection + bounce | 1.2-1.8R |
| CHOP_FAILED_BREAKOUT | Range kırılıp geri dönme | 1.5-2.5R |

**CHOP'ta özel kurallar:**
- Trailing stop YOK (noise çok fazla)
- Pyramiding YOK
- Max 4 trade/gün
- Günlük %2 kayıp limiti
- Midpoint'e ulaşınca hemen kapat

### 5.3 — VOLATILE Stratejisi (Fırsat + tehlike)

**Amaç:** Yüksek volatilitede çok seçici trade.

- SQS > 0.88 gerekli (çok yüksek kalite)
- Size: normal'in %40'ı
- Stop: geniş (1.5× ATR)
- Max 2 trade/gün
- 15m timeframe tercih (5m çok gürültülü)

### 5.4 — CRISIS Modu (Sadece kapat)

**Amaç:** Sermayeyi sıfır riskle koru.

- Yeni pozisyon YOK
- Tüm açık pozisyonları market order ile kapat
- Bot nakit'te oturur
- Manuel onay gelene kadar veya CRISIS bitene kadar bekle

---

## 6) RİSK YÖNETİMİ (SERMAYE KORUMA)

### 6.1 — Pozisyon boyutu

```
base_risk = equity × risk_pct

risk_pct tablosu:
  TREND_STRONG:  %1.50
  TREND_WEAK:    %1.00
  CHOP:          %0.75
  VOLATILE:      %0.60
  CRISIS:        %0.00

lot_size = base_risk / stop_distance

Örnek:
  equity = $500
  risk_pct = %1.50 (TREND_STRONG)
  base_risk = $500 × 0.015 = $7.50
  stop_distance = $200 (BTC 0.3%)
  lot_size = $7.50 / $200 = 0.0375 BTC
```

### 6.2 — Drawdown circuit breaker

```
DD = (peak_equity - current_equity) / peak_equity × 100

Kademeler:
  DD ≥  3% → size %50'ye düş
  DD ≥  5% → sadece TREND_STRONG, CHOP kapalı
  DD ≥  8% → yeni trade yok, sadece çıkış
  DD ≥ 12% → tüm pozisyonları kapat, manuel onay bekle

Geri dönüş:
  DD < önceki_seviye - 2% VE min 24h bekleme → bir kademe geri
```

### 6.3 — Günlük kayıp limitleri

| Regime | Günlük Max Kayıp | Aşılırsa |
|--------|:----------------:|----------|
| TREND | %3.0 | O gün trade durur |
| CHOP | %2.0 | O gün CHOP durur |
| VOLATILE | %2.0 | O gün trade durur |
| Toplam | %4.0 | Tüm trade durur, ertesi gün reset |

### 6.4 — Cooldown kuralları

```
2 ardışık kayıp → 60 dakika bekleme
3 ardışık kayıp → gün sonu kadar trade yok
Aynı asset'te 2 kayıp → o asset 24h karantina
```

### 6.5 — Max exposure (açık pozisyon toplamı)

| Regime | Max Gross Exposure | Max Leverage |
|--------|:-----------------:|:------------:|
| TREND_STRONG | %100 equity | 2× |
| TREND_WEAK | %60 equity | 1.5× |
| CHOP | %30 equity | 1× |
| VOLATILE | %40 equity | 1× |
| CRISIS | %0 | 0× |

### 6.6 — Nakit rezervi

```
TREND_STRONG: min %20 nakit
TREND_WEAK:   min %40 nakit
CHOP:         min %60 nakit
VOLATILE:     min %50 nakit
CRISIS:       min %90 nakit

Yeni trade açılmadan: available = equity × (1 - min_cash_pct)
```

### 6.7 — Black swan koruması

```
Anında tüm pozisyonları kapat EĞER:
  - Herhangi bir varlık 15 dakikada %8+ düşerse
  - Spread normal'in 10× üstündeyse
  - Funding rate > %0.5 (tek periyot)
  - Hacim 1h ortalamasının 10× üstündeyse
  - Exchange API 3 kez üst üste hata verirse

Sonra 4 saat bekleme. Manuel onay ile tekrar aç.
```

---

## 7) BİLEŞİK BÜYÜME MOTORU

### 7.1 — Compound reinvestment

```
HER TRADE İÇİN:
  risk_amount = CURRENT_EQUITY × risk_pct
  (başlangıç sermayesi değil, GÜNCEL equity)

Örnek büyüme ($100 başlangıç):
  Ay 1:  equity $100 → risk $1.50/trade → ay sonu $115
  Ay 3:  equity $152 → risk $2.28/trade → ay sonu $175
  Ay 6:  equity $265 → risk $3.97/trade → ay sonu $305
  Ay 12: equity $630 → risk $9.45/trade → ay sonu $725
  Ay 18: equity $1,500 → risk $22.50/trade → ay sonu $1,725
  Ay 24: equity $3,570 → risk $53.55/trade → ay sonu $4,100

  Accel + pyramid ile → $10,000+ (100×)
```

### 7.2 — Profit lock (kâr kilitleme)

```
Her %25 equity büyümede:
  büyümenin %20'sini "untouchable reserve"a aktar

Örnek:
  $100 → $125 olduğunda: $5 kilitlenir (25 × 0.20)
  Bu $5 hiçbir trade'e kullanılmaz
  Amaç: worst case'de bile sıfıra düşmemek
```

### 7.3 — Pyramiding (katmanlı pozisyon)

```
SADECE TREND_STRONG REJIMDE:

Katman 1 (base):  Normal entry → 1.0× size
Katman 2 (+1R):   Pozisyon +1R kârdayken → +0.5× ekle
Katman 3 (+2R):   Pozisyon +2R kârdayken → +0.3× ekle

Toplam: 1.8× normal size (max)

Her katmanda:
  - Önceki katmanların SL → breakeven'a taşı
  - Toplam risk < %3 equity
  - ADX hâlâ > 30 olmalı (trend hâlâ güçlü)
```

### 7.4 — Accel engine (hızlanma motoru)

```
İKİ HAVUZ:
  core_pool  = equity × %80 (korumalı, normal trading)
  accel_pool = equity × %20 (agresif, trend trading)

ACCEL AKTİF OLMA ŞARTI (9 gate ALL PASS):
  S1: sub_regime == STRONG_TREND
  S2: alignment_score >= 0.70 (tüm TF'ler uyumlu)
  S3: sqs_score >= 0.85
  R1: kill_switch == 0
  A:  rolling_vol_24h IN [0.005, 0.04] (normal volatilite)
  B:  current_drawdown < %5
  C:  recent_slippage < %2 (veya veri yok → neutral)
  D:  filled_orders >= 20 (yeterli tecrübe)

ACCEL AKTİFKEN:
  - Risk per trade: 2× normal (accel pool'dan)
  - 3 ardışık kayıpta → accel kapatılır, core'a dön
  - Max accel exposure: accel pool'un %50'si
```

### 7.5 — Alpha rotation (varlık rotasyonu)

```
HER HAFTA:
  Her varlık için:
    alpha_score = rolling_sharpe_30 × edge_health × regime_fit

  Top 3 varlığa: exposure artır
  Bottom 3 varlıktan: exposure çek

Kural:
  - Minimum 20 trade verisi gerekli (yoksa rotate etme)
  - En az 2 farklı varlık sınıfı (örn: crypto + emtia)
  - Tek varlığa max %40 toplam exposure
```

### 7.6 — Equity curve momentum

```
equity_ema_20 = EMA(günlük equity, 20)
equity_ema_50 = EMA(günlük equity, 50)

Hot streak:  equity > equity_ema_20 VE son 10 trade > %60 win
  → size multiplier: 1.2×

Normal:      equity ≈ equity_ema_20
  → size multiplier: 1.0×

Cold streak: equity < equity_ema_20 VEYA son 10 trade < %40 win
  → size multiplier: 0.6×

Deep cold:   equity < equity_ema_50
  → size multiplier: 0.3×

KURAL: Hot streak multiplier sadece TREND_STRONG'da geçerli.
       Anti-martingale: kazanırken büyüt, kaybederken küçült.
```

---

## 8) BİNGX EXCHANGE ENTEGRASYONU

### 8.1 — Gerekli API'ler

| Endpoint | Kullanım | Rate Limit |
|----------|----------|:----------:|
| `GET /api/v1/market/getLatestKlines` | OHLCV verisi | 20/s |
| `GET /api/v1/market/getLatestFunding` | Funding rate | 10/s |
| `POST /api/v1/trade/order` | Order yerleştirme | 10/s |
| `GET /api/v1/trade/openOrders` | Açık order'lar | 10/s |
| `GET /api/v1/trade/allPositions` | Açık pozisyonlar | 10/s |
| `GET /api/v1/account/balance` | Bakiye | 5/s |

### 8.2 — Rate limit koruması

```
- enableRateLimit: True
- Her API çağrısı arası: min 100ms
- Rate limit hatası → exponential backoff: 1s, 2s, 4s, 8s
- 3 üst üste hata → cycle SKIP, 60s bekleme
- Günde max 5000 API call (BingX daily limit)
```

### 8.3 — Order tipleri

```
CHOP entry:  LIMIT order (kenardan gir, spread'den kaçın)
  - Timeout: 3 bar (15 dakika on 5m)
  - Dolmazsa: cancel, fırsat kaçtı

TREND entry: LIMIT veya MARKET (duruma göre)
  - Pullback: LIMIT (sakin giriş)
  - Breakout: MARKET (momentum kaçırmama)

CHOP exit:   LIMIT (midpoint'e order koy)
TREND exit:  Trailing stop (exchange-side veya local)
Hard exit:   MARKET (acil)
```

### 8.4 — Desteklenen varlıklar (BingX)

```
Perpetual Swap: BTC-USDT, ETH-USDT, SOL-USDT, XRP-USDT, DOGE-USDT
Standard CFD:   XAUUSD (altın), XAGUSD (gümüş)
Leveraged:      1×-125× (biz max 2× kullanacağız)
```

---

## 9) VERİTABANI ŞEMASI (ÖNEMLİ TABLOLAR)

### Mevcut tablolar (Package 0'dan) ✅
- `trades` — tüm trade kayıtları
- `sqs_log` — sinyal kalite skoru geçmişi
- `regime_history` — regime değişim geçmişi
- `counterfactuals` — reject edilen sinyallerin sonuçları
- `edge_health` — strateji performans takibi
- `ledger` — genel hesap hareketleri
- `decisions` — her karar ve nedeni
- `equity_snapshots` — equity zaman serisi
- `kill_switch` — acil durdurma durumu
- `walk_forward_results` — backtest sonuçları

### Yeni tablolar (eklenmesi gereken)

```sql
CREATE TABLE IF NOT EXISTS pyramid_layers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_trade_id TEXT NOT NULL,
  layer_number INTEGER NOT NULL,
  entry_price REAL NOT NULL,
  size REAL NOT NULL,
  sl_price REAL NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exposure_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  gross_exposure_pct REAL NOT NULL,
  net_exposure_pct REAL NOT NULL,
  cash_pct REAL NOT NULL,
  regime TEXT NOT NULL,
  dd_pct REAL NOT NULL,
  circuit_breaker_level INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alpha_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  symbol TEXT NOT NULL,
  rolling_sharpe REAL,
  edge_health_score REAL,
  regime_fit REAL,
  alpha_score REAL NOT NULL,
  rank INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS profit_locks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  equity_at_lock REAL NOT NULL,
  amount_locked REAL NOT NULL,
  cumulative_locked REAL NOT NULL
);
```

---

## 10) CONFIG YAPISI

```yaml
# config/hedge_fund.yaml

bot:
  cycle_interval_seconds: 300      # 5 dakikada bir çalış
  primary_timeframe: "5m"
  htf_timeframes: ["15m", "1h", "4h"]
  assets: ["BTC-USDT", "ETH-USDT", "XAU-USD"]

exchange:
  name: "bingx"
  api_key_env: "BINGX_API_KEY"
  api_secret_env: "BINGX_API_SECRET"
  testnet: false
  rate_limit_ms: 100
  max_retries: 3

risk:
  per_trade_risk:
    trend_strong: 0.015
    trend_weak: 0.010
    chop: 0.0075
    volatile: 0.006
    crisis: 0.0
  max_leverage: 2.0
  daily_loss_cap: 0.04
  drawdown_levels: [0.03, 0.05, 0.08, 0.12]
  min_cash:
    trend_strong: 0.20
    trend_weak: 0.40
    chop: 0.60
    volatile: 0.50
    crisis: 0.90

growth:
  compound_mode: true
  profit_lock_threshold: 0.25
  profit_lock_fraction: 0.20
  pyramid_max_layers: 3
  pyramid_add_r: [1.0, 2.0]
  pyramid_add_size: [0.5, 0.3]
  accel_pool_fraction: 0.20

chop:
  max_trades_per_day: 4
  daily_loss_cap: 0.02
  cooldown_after_2_loss_min: 60
  edge_score_go: 0.80
  edge_score_caution: 0.65

trend:
  sqs_go: 0.85
  sqs_caution: 0.70
  trailing_stop_atr_mult: 2.0
  min_adx_for_pyramid: 30

black_swan:
  price_drop_15m_pct: 0.08
  spread_mult: 10
  funding_rate_max: 0.005
  volume_spike_mult: 10
  cooldown_hours: 4
```

---

## 11) LOGLAR VE İZLEME

### Her cycle loglanır

```json
{
  "ts": "2026-02-14T00:30:00Z",
  "cycle": 12847,
  "regime": "TREND_STRONG",
  "regime_confidence": 0.85,
  "sqs_score": 0.82,
  "signal": "TREND_PULLBACK_LONG",
  "signal_passed": true,
  "equity": 847.32,
  "dd_pct": 1.2,
  "circuit_breaker_level": 0,
  "open_positions": 1,
  "gross_exposure_pct": 0.35,
  "cash_pct": 0.65,
  "accel_active": false,
  "action": "OPEN_LONG",
  "asset": "BTC-USDT",
  "size": 0.012,
  "entry_price": 68450,
  "sl_price": 68050,
  "risk_pct": 0.015
}
```

### Haftalık rapor çıktısı

```
═══════════════════════════════════════
  ARGUS WEEKLY REPORT — Week 7, 2026
═══════════════════════════════════════
  Trades:        12
  Win Rate:      58.3%
  Avg R:         +1.42
  Total Return:  +8.7%
  Max DD:        2.1%
  Equity:        $847 → $921
  
  By Regime:
    TREND:  6 trades, 66% win, +6.2%
    CHOP:   4 trades, 50% win, +1.8%
    VOL:    2 trades, 50% win, +0.7%
    
  Edge Health:
    TREND_PULLBACK: Sharpe 1.8 (healthy)
    CHOP_EXTREME:   Sharpe 0.9 (watch)
    
  Counterfactuals:
    Rejected: 18 signals
    Would have been profitable: 5 (27%)
    → Thresholds OK (< 30%)
═══════════════════════════════════════
```

---

## 12) UYGULAMA SIRASI (AI AGENT İÇİN)

### Aşama 1: Temel altyapı
```
1. src/v25/data/feed_bingx.py       — BingX OHLCV fetch
2. src/v25/data/indicators.py       — ADX, BB, EMA, ATR, RSI
3. src/v25/data/normalizer.py       — Standart DataFrame format
4. src/v25/bot/main_loop.py         — Ana döngü iskelet
5. src/v25/execution/bingx_client.py — BingX API wrapper
```

### Aşama 2: Sinyal motoru
```
6.  regime_classifier.py
7.  sqs_engine.py
8.  chop/detector.py
9.  chop/edge_score.py
10. chop/templates.py
11. trend/templates.py
12. multi_tf.py
```

### Aşama 3: Risk + çıkış
```
13. position_sizer.py
14. exit/stop_manager.py + tp_manager.py + time_stop.py + hard_exits.py
15. circuit_breaker.py
16. exposure_manager.py
17. cash_governor.py
```

### Aşama 4: Büyüme motoru
```
18. compounder.py
19. pyramiding.py
20. accel_engine.py
21. equity_momentum.py
```

### Aşama 5: Analitik + izleme
```
22. postmortem/tagger.py + edge_health.py
23. counterfactual.py
24. weekly_report.py
25. bot/health_check.py
```

### Aşama 6: Genişleme (gelecek)
```
26. alpha_rotation.py
27. hedging.py (pairs trade)
28. correlation_guard.py
29. black_swan.py
30. Ek exchange adapter'lar (IBKR, TR broker)
```

---

## 13) TEST PLANI (ÖNEMLİ TESTLER)

| # | Test | GIVEN | WHEN | THEN |
|---|------|-------|------|------|
| 1 | DD circuit breaker Level 1 | Equity $500, peak $520 (DD=%3.8) | Yeni trade sinyali gelir | Size %50'ye düşer |
| 2 | DD circuit breaker Level 3 | DD=%9 | Yeni trade sinyali gelir | Trade reddedilir, sadece exit |
| 3 | CHOP daily cap | 4 CHOP trade yapılmış | 5. sinyal gelir | Reddedilir: MAX_TRADES_DAY |
| 4 | Compound sizing | Equity $200 (başlangıç $100) | Trade açılır | Risk = $200 × %1.5 = $3 ($100'den değil) |
| 5 | Profit lock | Equity $100 → $125 | %25 büyüme aşılır | $5 kilitlenir, tradeable = $120 |
| 6 | Pyramid add | TREND_STRONG, pozisyon +1.2R | Pyramid check | Katman 2 eklenir: +0.5× size |
| 7 | Pyramid reject | TREND_WEAK, pozisyon +1.5R | Pyramid check | Reddedilir: regime uygun değil |
| 8 | Accel activation | 9 gate ALL PASS | Accel check | Accel pool aktif, 2× risk |
| 9 | Accel deactivation | Accel'de 3 ardışık kayıp | Accel check | Accel kapatılır, core'a dönülür |
| 10 | Black swan | BTC %10 düşüş 15 dakikada | Her cycle check | Tüm pozisyonlar kapatılır |
| 11 | Cash governor | CHOP regime, %65 pozisyonda | Yeni trade | Reddedilir: nakit < %60 minimum |
| 12 | Equity momentum hot | Equity > EMA20, son 10 trade %65 win | Size hesapla | 1.2× multiplier uygulanır |
| 13 | Equity momentum cold | Equity < EMA20, DD > %3 | Size hesapla | 0.6× multiplier uygulanır |
| 14 | Regime CRISIS | regime = CRISIS | Cycle çalışır | Tüm açık pozisyonlar kapatılır |
| 15 | Cooldown | 2 ardışık CHOP kaybı | Yeni CHOP sinyali (30 dk sonra) | Reddedilir: cooldown aktif |
| 16 | Rate limit | BingX 429 hatası | API çağrısı | Backoff: 1s → 2s → 4s |
| 17 | Limit order timeout | CHOP_EXTREME limit order, 3 bar dolmadı | Timeout check | Order cancel edilir |
| 18 | Trailing stop TREND | Pozisyon +3R, ATR stop 1.5R'da | Fiyat geri çekilir | Stop tetiklenir, +1.5R kâr |
| 19 | Alpha rotation | BTC Sharpe 2.1, ETH Sharpe 0.3 | Haftalık rotation | BTC exposure artırılır, ETH azaltılır |
| 20 | Multi-TF veto | 5m CHOP, 1h TREND_STRONG UP | Short CHOP_EXTREME upper | Reddedilir: HTF veto |

---

## 14) GÜVENLİK

```
KESİNLİKLE:
- API key'ler .env dosyasında (repo'da DEĞİL)
- .gitignore: .env, *.db, runs/, logs/
- Withdrawal API yetkisi KAPALI (sadece trade)
- IP whitelist BingX'te ayarlanmalı
- Log'larda API key/secret yazdırılmamalı
```

---

## 15) BAŞLATMA KOMUTU

```bash
# Geliştirme (paper trading / dry-run)
python -m src.v25.bot.main_loop --mode paper --config config/hedge_fund.yaml

# Canlı (gerçek para)
python -m src.v25.bot.main_loop --mode live --config config/hedge_fund.yaml

# Backtest (geçmiş veri)
python -m src.v25.bot.main_loop --mode backtest --start 2025-01-01 --end 2025-12-31
```

---

## 16) ÇOK KAYNAKLI VERİ İSTİHBARATI

### Felsefe
```
İŞLEM = BingX (tek exchange)
VERİ  = Her yerden (doğrulama + zenginleştirme)
```

BingX sadece işlem yapar. Ama veri doğrulaması, fiyat karşılaştırması ve sinyal zenginleştirmesi için birden fazla kaynak kullanılır. Böylece BingX verisi manipüle edilse bile bot fark eder.

### 16.1 — Veri Kaynakları

| Kaynak | Ne alınır | Kullanım | Maliyet |
|--------|----------|----------|:-------:|
| **BingX** | OHLCV, orderbook, funding, pozisyon | İŞLEM + birincil veri | Ücretsiz |
| **Binance** | OHLCV, 24h ticker, volume | Fiyat doğrulaması (cross-check) | Ücretsiz |
| **CoinGecko API** | Global market cap, fear/greed, dominance | Makro sentiment | Ücretsiz (50 call/min) |
| **Yahoo Finance** | XAU, XAG, SPY, QQQ, AAPL günlük fiyat | Emtia/hisse veri | Ücretsiz (yfinance) |
| **Alternative.me** | Crypto Fear & Greed Index | Sentiment filtresi | Ücretsiz |
| **CoinMarketCap** | Hacim doğrulaması | Volume cross-check | Ücretsiz (tier 1) |

### 16.2 — Cross-Check (Fiyat Doğrulama)

```
HER CYCLE:
  bingx_price = BingX'ten BTC fiyatı
  binance_price = Binance'ten BTC fiyatı
  deviation = abs(bingx_price - binance_price) / binance_price

  IF deviation > 0.005 (%0.5):
    → WARNING log
    → Spread anormalliği: trade'lerde slippage bütçesini artır

  IF deviation > 0.02 (%2):
    → CRITICAL: BingX fiyatı güvenilir değil
    → Bu cycle'da trade YAPMA
    → "PRICE_DEVIATION_HALT" log

Amaç: BingX'te fiyat manipülasyonu veya liquidity boşluğu varsa trade yapma.
```

### 16.3 — Sentiment Entegrasyonu

```
fear_greed = CoinGecko'dan Fear & Greed Index (0-100)

  0-20  (Extreme Fear):   → CHOP/VOLATILE'da short bias güçlendir
  20-40 (Fear):            → Normal
  40-60 (Neutral):         → Normal
  60-80 (Greed):           → Stop'ları sıkılaştır, pyramid'de dikkatli
  80-100 (Extreme Greed):  → Yeni long açma, mevcut uzunları koru

Bu filtre VETO değil, SIZE MODIFIER:
  Extreme Fear + Short sinyal → size 1.2×
  Extreme Greed + Long sinyal → size 0.6×
```

### 16.4 — Modül yapısı

```
src/v25/data/
├── feed_bingx.py         # ✅ Mevcut — İŞLEM + birincil veri
├── feed_binance.py       # [YENİ] Cross-check fiyat verisi
├── feed_coingecko.py     # [YENİ] Sentiment + global metrics
├── feed_yahoo.py         # [YENİ] Emtia/hisse verisi
├── cross_checker.py      # [YENİ] Fiyat doğrulama mantığı
├── sentiment.py          # [YENİ] Fear/Greed → size modifier
├── normalizer.py         # ✅ Mevcut
└── indicators.py         # ✅ Mevcut
```

---

## 17) SELF-LEARNING OTONOM SİSTEM (HATASINDAN ÖĞRENME)

### Felsefe
```
Bot kendi hatalarını analiz eder.
Threshold'ları SADECE SIKILAŞTIRIR (asla gevşetmez).
İnsan onayı olmadan ASLA leverage/risk ARTIRMAZ.
Ama kendi kendine "daha az hata yapmayı" ÖĞRENIR.
```

### 17.1 — 5 Öğrenme Döngüsü

```
┌──────────────────────────────────────────────────┐
│              SELF-LEARNING LOOPS                  │
│                                                   │
│  Loop 1: Trade Tagger (her trade sonrası)        │
│  Loop 2: Pattern Detector (günlük)               │
│  Loop 3: Threshold Tuner (haftalık)              │
│  Loop 4: Edge Health Monitor (haftalık)          │
│  Loop 5: Counterfactual Resolver (günlük)        │
│                                                   │
│  KURAL: Sadece sıkılaştır. Gevşetme = insan.    │
└──────────────────────────────────────────────────┘
```

### 17.2 — Loop 1: Trade Tagger (her trade kapandığında)

```
Her kapanan trade otomatik etiketlenir:

Etiketler:
  CLEAN_WIN        → Plan çalıştı, temiz kazanç
  CLEAN_LOSS       → Plan çalıştı ama piyasa tersine gitti (normal)
  AVOIDABLE_LOSS   → Daha sıkı filtre ile kaçınılabilirdi
  OVERTRADED       → Cooldown'da olmalıydı ama trade açıldı
  EARLY_EXIT       → TP'den önce çıkıldı (time stop veya hard exit)
  LATE_EXIT        → Kâr vardı ama geri verildi
  FAKEOUT          → Range kırılması gerçek trend oldu, short zarar gördü
  WRONG_REGIME     → Regime yanlış tespit edildi (chop sanıldı trend'de)

Etiketleme kuralları (deterministik):
  IF trade.r_realized < -0.5 AND trade.entry_edge_score < 0.70:
    → AVOIDABLE_LOSS
  IF trade.exit_reason == TIME_STOP AND trade.max_unrealized_r > 0.8:
    → LATE_EXIT
  IF trade.template == CHOP_FAILED_BREAKOUT AND trade.r_realized < -1.0:
    → FAKEOUT
```

### 17.3 — Loop 2: Pattern Detector (günlük gece yarısı UTC)

```
Son 24 saatin trade'lerini tara. Tekrarlayan hata kalıpları bul:

Kalıp 1: "Saatlik Tuzak"
  → Belirli saatlerde (örn: 14:00-15:00 UTC) CHOP trade'leri sürekli kaybediyorsa
  → O saat dilimini "dangerous_hours" listesine ekle
  → dangerous_hours'da ChopEdgeScore threshold +0.10

Kalıp 2: "Asset Zayıflığı"
  → Bir asset'te son 10 trade'den 7+ kayıpsa
  → O asset'e "quarantine" uygula (48h trade yok)

Kalıp 3: "Regime Yanılgısı"
  → WRONG_REGIME etiketi son 5 trade'de 2+ kez varsa
  → Regime classifier güvenlik marjını artır (3/5 → 4/5 kriter)

Kalıp 4: "Volume Tuzağı"
  → Düşük hacimli saatlerde kayıp oranı > %60 ise
  → Min volume threshold ekle (volume < 20-bar SMA × 0.5 → skip)
```

### 17.4 — Loop 3: Threshold Tuner (her Pazar gecesi UTC)

```
Haftalık postmortem veriden threshold ayarları:

KURAL: SADECE SIKILAŞTIR. ASLA GEVŞETMİR.
KURAL: Min 30 trade verisi olmadan adjustment yok.
KURAL: Adjustment max %10 step (büyük değişiklik yok).

Otomatik sıkılaştırma:
  IF avoidable_loss_rate > 0.30:
    → SQS GO threshold += 0.02
    → CHOP edge score GO threshold += 0.02
    → Log: "AUTO_TIGHTEN_SQS: 0.85 -> 0.87"

  IF fakeout_rate > 0.20:
    → CHOP_FAILED_BREAKOUT threshold += 0.03
    → Failed breakout max_bars_outside -= 1
    → Log: "AUTO_TIGHTEN_FAKEOUT"

  IF daily_loss_cap_hit_count >= 2 (son 7 günde):
    → per_trade_risk -= 0.001 (ör: 0.015 -> 0.014)
    → Log: "AUTO_REDUCE_RISK"

Gevşetme istiyorsa (threshold düşürme, risk artırma):
  → Sadece öneri üretir: "SUGGESTION: Consider lowering SQS GO to 0.83"
  → İnsan onayı bekler
  → Onay gelene kadar mevcut threshold kalır
```

### 17.5 — Loop 4: Edge Health Monitor (her Pazar)

```
Her strateji/template için rolling performance:

Metrikler (son 30 trade penceresi):
  - Win rate
  - Average R
  - Sharpe ratio
  - Profit factor
  - Max consecutive losses

Status geçişleri:
  ACTIVE     → Sharpe ≥ 0.8,  win rate ≥ 45%
  WATCHING   → Sharpe 0.5-0.8 VEYA win rate 35-45%
  DECAYING   → Sharpe < 0.5   VEYA win rate < 35%
  SUSPENDED  → Sharpe < 0.3   VEYA win rate < 25% (3 hafta üst üste DECAYING)

SUSPENDED olan template:
  - Yeni trade açmaz
  - Mevcut açık pozisyonları normal yönetir
  - 30 gün sonra otomatik "WATCHING"a döner (ikinci şans)
  - 2. kez SUSPENDED → RETIRED (kalıcı kapatma, insan onayıyla geri açılır)
```

### 17.6 — Loop 5: Counterfactual Resolver (günlük)

```
Dün reject edilen sinyallerin "ne olurdu" analizi:

HER REJECT İÇİN:
  1. Reject anındaki fiyatı kaydet
  2. 24 saat sonra: fiyat hedef TP'ye ulaştı mı?
  3. Sonuç:
     good_reject     → Reject doğru karar (fiyat ters gitti veya TP'ye ulaşmadı)
     missed_opp      → Reject yanlış (fiyat TP'ye ulaştı)

Haftalık değerlendirme:
  IF missed_opp_rate > 0.35 (%35+):
    → "SUGGESTION: Threshold too tight, consider loosening"
    → İnsan onayı bekle

  IF missed_opp_rate < 0.15 (%15-):
    → "Threshold'lar doğru, reject kalitesi yüksek"
    → No action
```

### 17.7 — Öğrenme DB tabloları

```sql
CREATE TABLE IF NOT EXISTS learning_adjustments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  loop_name TEXT NOT NULL,
  parameter TEXT NOT NULL,
  old_value REAL NOT NULL,
  new_value REAL NOT NULL,
  direction TEXT NOT NULL CHECK(direction IN ('tighten', 'suggest_loosen')),
  reason TEXT NOT NULL,
  applied INTEGER DEFAULT 1,
  human_approved INTEGER DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS pattern_detections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  pattern_type TEXT NOT NULL,
  details_json TEXT NOT NULL,
  action_taken TEXT NOT NULL,
  still_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dangerous_hours (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hour_utc INTEGER NOT NULL,
  regime TEXT NOT NULL,
  loss_rate REAL NOT NULL,
  added_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
```

### 17.8 — Modül yapısı

```
src/v25/learning/
├── trade_tagger.py       # Loop 1: Her trade otomatik etiketleme
├── pattern_detector.py   # Loop 2: Günlük kalıp tespiti
├── threshold_tuner.py    # Loop 3: Haftalık threshold sıkılaştırma
├── edge_monitor.py       # Loop 4: Strateji sağlık takibi
├── counterfactual.py     # Loop 5: "Ne olurdu?" analizi
└── learning_config.py    # Hangi loop'lar aktif, min_trades, max_step
```

---

## 18) GITHUB OPEN-SOURCE İSTİHBARATI

### Felsefe
```
Tekerleği yeniden icat etme. Açık kaynak kütüphaneleri kullan.
Ama sadece DOĞRULANMIŞ ve ANLAŞILMIŞ kodu entegre et.
Kara kutu yok. Her fonksiyon audit edilebilir olmalı.
```

### 18.1 — Entegre Edilebilecek Repolar

| Repo | Ne için | Nasıl kullanılır |
|------|--------|-----------------|
| **freqtrade/freqtrade** | Backtesting framework | `FreqtradeBacktester` wrapper ile WF backtest altyapısı |
| **jesse-ai/jesse** | Strateji DSL | İndikatör hesaplama fonksiyonları fork edilebilir |
| **ta-lib / pandas-ta** | Teknik indikatörler | ADX, BB, EMA, ATR, RSI hesaplamaları direkt kullan |
| **ccxt/ccxt** | Exchange abstraction | BingX + Binance + gelecekte IBKR adapter |
| **pydantic/pydantic** | Data validation | ✅ Zaten kullanılıyor |
| **bukosabino/ta** | Alternatif TA | pandas-ta yoksa fallback |
| **stefan-jansen/zipline-reloaded** | Event-driven backtest | Walk-forward harness |
| **ranaroussi/yfinance** | Yahoo Finance veri | XAU, SPY, AAPL fiyat çekme |

### 18.2 — Fork/Entegrasyon Kuralları

```
KURAL 1: Tüm kodu yeniden yazmak zorunda değilsin.
         Ama import edilen her fonksiyonu ANLA.

KURAL 2: Üçüncü parti kodu src/v25/vendor/ altına koy.
         Doğrudan pip install tercihen.
         
KURAL 3: Her üçüncü parti dependency'yi requirements.txt'e pin'le.
         Versiyon kilitle: ccxt==4.2.1 (değişmesin)

KURAL 4: Üçüncü parti kodun ÇIKTISI her zaman kendi Pydantic
         contract'ımızdan geçsin (trust nothing).
         
KURAL 5: Hiçbir üçüncü parti kod doğrudan order vermesin.
         Sadece BİZİM execution/bingx_client.py order verir.
```

### 18.3 — Dependency listesi (güncel + yeni)

```
# requirements.txt güncellemesi

# Mevcut ✅
pydantic>=2.0.0
pyyaml>=6.0
numpy>=1.24

# Yeni (Hedge Fund Bot)
ccxt>=4.0.0                  # Exchange abstraction (BingX + Binance)
pandas>=2.0.0                # DataFrame işlemleri
yfinance>=0.2.30            # Yahoo Finance (XAU, SPY, hisse)
requests>=2.31.0             # CoinGecko, Alternative.me API
ta>=0.11.0                   # Teknik indikatörler (pandas-ta alternatif)
schedule>=1.2.0              # Cron-like scheduler
python-dotenv>=1.0.0         # .env yükleme
rich>=13.0.0                 # Renkli terminal log (opsiyonel)
```

---

## 19) IBKR GEÇİŞ MİLESTONE'U (30K TL)

### Felsefe
```
Şu an: BingX ile crypto + emtia CFD.
Hedef: 30K TL (~$900) biriktiğinde Interactive Brokers hesabı aç.
       Tüm dünya borsaları: NYSE, NASDAQ, LSE, BIST, HKEX...
       Gerçek hisse senedi, ETF, options, futures.
```

### 19.1 — Graduation koşulları

```
IBKR'ye GEÇ EĞER:
  1. Equity ≥ 30,000 TL (~$900 veya daha fazla)
  2. Bot en az 3 ay kârlı çalışmış
  3. Max DD hiçbir zaman %15'i geçmemiş
  4. Win rate >= %50 (son 100 trade)
  5. Profit factor >= 1.5 (son 100 trade)

3 ve 4 ve 5 AYNI ANDA sağlanmalı.
```

### 19.2 — IBKR'de ne değişir?

| Özellik | BingX (şimdi) | IBKR (30K TL sonrası) |
|---------|:------------:|:--------------------:|
| Varlıklar | Crypto + CFD | + Hisse + ETF + Options + Futures |
| Borsalar | Sadece BingX | NYSE, NASDAQ, BIST, LSE, TSE... |
| Saat | 7/24 | Borsa saatleri (09:30-16:00 ET vb.) |
| Short | Perpetual swap | Gerçek short selling + put options |
| Fees | %0.04-0.06 | %0.01-0.03 (daha ucuz!) |
| Leverage | 1-125× | 1-4× (RegT margin) |
| Settlement | Anında | T+1 (hisse), T+0 (futures) |
| Minimum | $1 | $0 (IBKR Lite) veya $100K (Pro) |

### 19.3 — Eklenmesi gereken modüller (IBKR aşaması)

```
src/v25/execution/
├── bingx_client.py        # ✅ Mevcut
├── ibkr_client.py         # [YENİ] IBKR TWS API wrapper
├── broker_router.py       # [YENİ] Asset'e göre doğru broker'a yönlendir
└── market_hours.py        # [YENİ] Borsa saatleri + pre/after market

config/brokers/
├── bingx.yaml             # BingX config
├── ibkr.yaml              # IBKR config
└── routing.yaml           # asset → broker mapping

Routing örneği:
  BTC-USDT  → BingX (crypto her zaman BingX)
  ETH-USDT  → BingX
  XAUUSD    → BingX CFD (veya IBKR futures)
  AAPL      → IBKR
  SPY       → IBKR
  QQQ       → IBKR
  THYAO     → IBKR (BIST erişimi)
```

### 19.4 — Zaman çizelgesi

```
Ay 0:   Bot başlar (BingX only, $100 equity)
Ay 1-6: Sinyal motoru + risk katmanı olgunlaşır
Ay 6-12: Accel + compound growth aktif
Ay 12:  Equity ~$900 (30K TL) → IBKR için yeterli
Ay 12+: IBKR eklenir → çoklu borsa, çoklu asset class
Ay 24:  $10K+ hedef
```

> [!NOTE]
> IBKR entegrasyonu, bot mimarisinde **tek satır bile değiştirmez**. Sadece yeni bir `execution/ibkr_client.py` eklenir ve `broker_router.py` bunu yönlendirir. Tüm signal/risk/growth modülleri aynı kalır.

---

## 20) TÜM MODÜL LİSTESİ (GÜNCEL)

```
src/v25/                                 # 60+ modül
├── bot/
│   ├── main_loop.py
│   ├── scheduler.py
│   └── health_check.py
│
├── data/
│   ├── feed_bingx.py
│   ├── feed_binance.py                  # [YENİ] Cross-check
│   ├── feed_coingecko.py                # [YENİ] Sentiment
│   ├── feed_yahoo.py                    # [YENİ] Emtia/hisse
│   ├── cross_checker.py                 # [YENİ] Fiyat doğrulama
│   ├── sentiment.py                     # [YENİ] Fear/Greed modifier
│   ├── normalizer.py
│   └── indicators.py
│
├── signal/
│   ├── regime_classifier.py
│   ├── sqs_engine.py
│   ├── chop/detector.py, edge_score.py, templates.py
│   ├── trend/templates.py, momentum.py
│   └── multi_tf.py
│
├── risk/
│   ├── position_sizer.py
│   ├── exposure_manager.py
│   ├── circuit_breaker.py
│   ├── cash_governor.py
│   ├── correlation_guard.py
│   └── black_swan.py
│
├── growth/
│   ├── compounder.py
│   ├── pyramiding.py
│   ├── accel_engine.py
│   ├── equity_momentum.py
│   └── alpha_rotation.py
│
├── learning/                             # [YENİ] Self-learning
│   ├── trade_tagger.py
│   ├── pattern_detector.py
│   ├── threshold_tuner.py
│   ├── edge_monitor.py
│   ├── counterfactual.py
│   └── learning_config.py
│
├── intelligence/                         # [YENİ] Dış Dünya İstihbaratı (HERMES)
│   ├── hermes_core.py                   # Tüm istihbarat kaynakları orchestrator
│   ├── news_nlp.py                      # 8B model ile haber yorumlama
│   ├── macro_calendar.py                # CPI/FOMC/NFP takvim + koruma
│   ├── whale_alert.py                   # Büyük cüzdan hareketleri
│   ├── onchain.py                       # Exchange flow, miner reserve, stablecoin
│   ├── social_sentiment.py              # Twitter/Reddit/Telegram sentiment
│   ├── event_shield.py                  # Event-driven pozisyon koruma
│   ├── intel_fusion.py                  # Tüm istihbaratı tek skora birleştir
│   ├── prompts/                         # 8B model prompt template'leri
│   │   ├── news_analysis.txt
│   │   ├── tweet_sentiment.txt
│   │   └── event_impact.txt
│   └── intel_config.py                  # Kaynak ağırlıkları, eşikler
│
├── execution/
│   ├── bingx_client.py
│   ├── ibkr_client.py                   # [GELECEK] IBKR
│   ├── broker_router.py                 # [GELECEK] routing
│   ├── order_manager.py
│   ├── slippage_tracker.py
│   └── hedging.py
│
├── exit/
│   ├── stop_manager.py
│   ├── tp_manager.py
│   ├── time_stop.py
│   └── hard_exits.py
│
├── db/migrations.py, ledger.py, trade_log.py
├── postmortem/tagger.py, edge_health.py, counterfactual.py, weekly_report.py
├── contracts/                            # ✅ Mevcut
├── config/                               # ✅ Mevcut
├── bootstrap.py                          # ✅ Mevcut
└── telemetry/                            # ✅ Mevcut
```

---

## 21) DIŞ DÜNYA İSTİHBARATI — HERMES SİSTEMİ 🌐

### Felsefe
```
Piyasa fiyattan ibaret değil.
Fiyat SONUÇTUR. Nedenler dışarıda:
  - Haberler (SEC davası, exchange hack, partnership)
  - Makro (CPI, FOMC, faiz kararı)
  - Whale hareketleri (10K BTC exchange'e girdi)
  - On-chain (miner satışı, stablecoin basımı)
  - Sosyal medya (Elon tweet'i, influencer pump)

Bot bu bilgileri ANLAR ve pozisyonunu AYARLAR.
8B local model = beyin. API'ler = gözler ve kulaklar.
```

### Genel akış

```
┌────────────────────────────────────────────────────────────┐
│                    HERMES INTELLIGENCE                      │
│                                                             │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│   │ News API │ │ Macro    │ │ Whale    │ │ On-Chain │    │
│   │ (RSS +   │ │ Calendar │ │ Alert    │ │ Data     │    │
│   │ scrape)  │ │ (ekonomi)│ │ (cüzdan) │ │ (blokzin)│    │
│   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘    │
│        │             │            │             │           │
│   ┌────▼─────┐       │            │             │           │
│   │ 8B LOCAL │       │            │             │           │
│   │ MODEL    │       │            │             │           │
│   │ (NLP)    │       │            │             │           │
│   └────┬─────┘       │            │             │           │
│        │             │            │             │           │
│   ┌────▼─────────────▼────────────▼─────────────▼────┐     │
│   │              INTEL FUSION                         │     │
│   │         (hermes_score: -1.0 → +1.0)              │     │
│   └──────────────────────┬────────────────────────────┘     │
│                          │                                   │
│                    ┌─────▼─────┐                            │
│                    │ SQS C5    │ → Sinyal kalitesine etki   │
│                    │ hermes_   │ → Size modifier            │
│                    │ news_risk │ → Event shield             │
│                    └───────────┘                            │
└────────────────────────────────────────────────────────────┘
```

---

### 21.1 — Haber Yorumlama (8B Local Model ile NLP)

#### Veri kaynakları

| Kaynak | Tür | Ne çekilir | Sıklık |
|--------|-----|-----------|:------:|
| CryptoPanic API | Haber aggregator | Crypto haberleri (başlık + özet) | 5 dk |
| RSS Feeds | Haber | CoinDesk, The Block, Bloomberg Crypto | 15 dk |
| NewsAPI.org | Genel haber | "bitcoin", "ethereum", "fed rate" arama | 15 dk |
| Google News RSS | Genel haber | Finansal haberler | 30 dk |

#### 8B Model Pipeline

```
ADIM 1: Ham haberi çek
  → CryptoPanic API veya RSS'ten son 10 haber

ADIM 2: Her haber için 8B modele gönder
  → Prompt template (aşağıda)
  → Model JSON döner

ADIM 3: JSON'ı parse et
  → Pydantic contract'tan geçir (trust nothing)

ADIM 4: Sonucu intel_fusion'a gönder
  → SQS C5 (hermes_news_risk) hesapla
```

#### Prompt template (news_analysis.txt)

```
Sen bir finans analisti botsun. Aşağıdaki haberi analiz et.

HABER:
"{headline}"

KAYNAK: {source}
TARİH: {published_at}

Aşağıdaki JSON formatında yanıt ver. Başka hiçbir şey yazma.

{
  "sentiment": "BULLISH | BEARISH | NEUTRAL",
  "impact_score": 0.0 ile 1.0 arası (0 = önemsiz, 1 = çok önemli),
  "affected_assets": ["BTC", "ETH", ...],
  "category": "REGULATORY | HACK | PARTNERSHIP | MACRO | TECHNICAL | ADOPTION | SCAM",
  "urgency": "IMMEDIATE | HOURS | DAYS | IRRELEVANT",
  "confidence": 0.0 ile 1.0 arası (kendi emin olma derecen),
  "reasoning": "1-2 cümle neden"
}
```

#### Örnek model çıktısı

```json
{
  "sentiment": "BEARISH",
  "impact_score": 0.85,
  "affected_assets": ["BTC", "ETH", "SOL"],
  "category": "REGULATORY",
  "urgency": "IMMEDIATE",
  "confidence": 0.90,
  "reasoning": "SEC Bitcoin ETF başvurusunu reddetti. Kısa vadede satış baskısı beklenir."
}
```

#### Haber skoru → trading etkisi

```
news_score hesaplama (her haber için):
  raw = sentiment_to_num(sentiment) × impact_score × confidence
    sentiment_to_num: BULLISH=+1, NEUTRAL=0, BEARISH=-1
  
  weighted = raw × urgency_weight
    urgency_weight: IMMEDIATE=1.0, HOURS=0.7, DAYS=0.3, IRRELEVANT=0.0

  Birden fazla haber varsa:
    combined_news_score = weighted average (son 6h haberleri)

Trading etkileri:
  combined_news_score > +0.50  → Long bias güçlenir, short sinyal size ×0.5
  combined_news_score > +0.80  → "NEWS_CATALYST_LONG" extra sinyal template aktif
  combined_news_score < -0.50  → Short bias güçlenir, long sinyal size ×0.5
  combined_news_score < -0.80  → "NEWS_CATALYST_SHORT" extra sinyal + stop'ları sıkılaştır
  abs(combined_news_score) > 0.90 → URGENT: mevcut ters pozisyonları kapat
```

#### 8B Model entegrasyonu (teknik)

```python
# news_nlp.py — basitleştirilmiş akış

import json
import subprocess

def analyze_news(headline: str, source: str, model_path: str) -> dict:
    """8B local model ile haber analizi."""
    
    prompt = PROMPT_TEMPLATE.format(
        headline=headline,
        source=source,
        published_at=datetime.utcnow().isoformat()
    )
    
    # Ollama veya llama.cpp ile local model çağır
    result = subprocess.run(
        ["ollama", "run", model_path, prompt],
        capture_output=True, text=True, timeout=30
    )
    
    # JSON parse + Pydantic validation
    raw_json = extract_json(result.stdout)
    validated = NewsAnalysis.model_validate_json(raw_json)
    
    return validated

# Alternatif: HTTP API (Ollama server mode)
def analyze_news_http(headline: str) -> dict:
    """Ollama HTTP API ile (daha stabil)."""
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "llama3.1:8b",
        "prompt": prompt,
        "format": "json",
        "stream": False
    })
    return NewsAnalysis.model_validate_json(response.json()["response"])
```

#### Pydantic contract

```python
class NewsAnalysis(ArgusModel):
    """8B model haber analizi çıktısı."""
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    impact_score: float = Field(ge=0.0, le=1.0)
    affected_assets: list[str]
    category: Literal[
        "REGULATORY", "HACK", "PARTNERSHIP", 
        "MACRO", "TECHNICAL", "ADOPTION", "SCAM"
    ]
    urgency: Literal["IMMEDIATE", "HOURS", "DAYS", "IRRELEVANT"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
```

---

### 21.2 — Makro Ekonomik Takvim

#### Takip edilen olaylar

| Olay | Etki | Kaynak | Sıklık |
|------|------|--------|:------:|
| FOMC Faiz Kararı | 🔴 Çok Yüksek | ForexFactory RSS / Investing.com | 6-8 hafta |
| CPI (Enflasyon) | 🔴 Çok Yüksek | BLS.gov takvimi | Aylık |
| NFP (İstihdam) | 🟡 Yüksek | BLS.gov takvimi | Aylık |
| PPI (Üretici Enflasyonu) | 🟡 Orta | BLS.gov | Aylık |
| Unemployment Claims | 🟢 Düşük | DOL.gov | Haftalık |
| GDP | 🟡 Yüksek | BEA.gov | 3 Aylık |
| TCMB Faiz Kararı | 🟡 Yüksek (TL varlıklar) | TCMB.gov.tr | Aylık |
| ECB Faiz Kararı | 🟡 Orta | ECB takvimi | 6 hafta |
| Bitcoin Halving | 🔴 Çok Yüksek | Blok sayısı takibi | ~4 yıl |

#### Event-driven koruma protokolü

```
HER CYCLE:
  upcoming_events = macro_calendar.get_upcoming(hours=4)
  
  FOR each event in upcoming_events:
    IF event.impact == "HIGH" AND hours_until < 2:
      → EVENT_SHIELD aktif:
        1. Yeni pozisyon AÇMA (tüm regime'ler)
        2. Mevcut pozisyonlarda stop'ları sıkılaştır (ATR×1.5 → ATR×1.0)
        3. Pyramid pozisyonlarının son hatmanını kapat
        4. Accel engine → core'a geri dön
        
    IF event.impact == "HIGH" AND hours_until < 0.5 (30 dk):
      → FULL_SHIELD aktif:
        1. Pozisyon boyutunu %50'ye düşür
        2. Veya: tüm pozisyonları kapat (config'e göre)

    EVENT SONRASI (ilk 30 dk):
      → VOLATILITY_WATCH:
        1. İlk 30 dk trade yapma (whipsaw riski)
        2. Regime re-classify et
        3. Spread normal'e dönünce normal moda geç
```

#### Takvim veri kaynağı

```
Birincil:  ForexFactory RSS (ücretsiz, düzenli)
           URL: https://www.forexfactory.com/calendar.php?do=getCalendar

Yedek:     Investing.com Economic Calendar API
           URL: https://www.investing.com/economic-calendar/

Parse:     HTML/RSS parse → event_name, date, time, impact, forecast, previous
           Günde 2 kez güncelle (00:00 ve 12:00 UTC)

Depolama:  SQLite macro_events tablosu
```

---

### 21.3 — Whale / Smart Money Alertları

#### Ne takip edilir?

```
"Whale" = Büyük cüzdan. 100+ BTC veya 1000+ ETH hareket eden adresler.
"Smart Money" = Historically kârlı adresler (on-chain analiz).

Takip edilen hareketler:
  1. BTC/ETH büyük transferler (>$1M)
  2. Exchange'e giriş (satış sinyali olabilir)
  3. Exchange'ten çıkış (hodl sinyali olabilir)
  4. Miner cüzdan hareketleri
  5. Stablecoin büyük basım/yakma (USDT, USDC)
```

#### Veri kaynakları

| Kaynak | API | Ne verir | Maliyet |
|--------|-----|----------|:-------:|
| Whale Alert | `api.whale-alert.io` | Büyük transfer bildirimleri | Ücretsiz (10 req/min) |
| Etherscan | `api.etherscan.io` | ETH büyük transfer log | Ücretsiz (5 req/s) |
| Blockchain.com | `blockchain.info/rawaddr` | BTC adres bakiye | Ücretsiz |
| Glassnode (gelecek) | `api.glassnode.com` | On-chain metrics premium | $39/ay |

#### Whale sinyalleri → trading etkisi

```
WHALE SİNYAL TABLOSU:

Signal: WHALE_EXCHANGE_DEPOSIT
  Anlam: Büyük miktar exchange'e gönderildi (satış hazırlığı)
  Etki:  BEARISH modifier: long sinyal size ×0.7
  Eşik:  > $5M tek transfer, son 1h içinde

Signal: WHALE_EXCHANGE_WITHDRAW  
  Anlam: Büyük miktar exchange'ten çıktı (hodl)
  Etki:  BULLISH modifier: short sinyal size ×0.7
  Eşik:  > $5M tek transfer

Signal: STABLECOIN_MINT
  Anlam: Yeni USDT/USDC basıldı (alım hazırlığı olabilir)
  Etki:  BULLISH modifier: +0.1 news_score
  Eşik:  > $100M basım

Signal: STABLECOIN_BURN
  Anlam: USDT/USDC yakıldı (likidite çekilmesi)
  Etki:  BEARISH modifier: +0.1 news_score (negatif yönde)
  Eşik:  > $100M yakım

Signal: MINER_SELL
  Anlam: Miner cüzdanından exchange'e BTC transferi
  Etki:  BEARISH: supply pressure
  Eşik:  > 500 BTC / gün (normal'in 3×'ü)
```

---

### 21.4 — On-Chain İstihbarat

#### Takip edilen metrikler

| Metrik | Ne anlama gelir | Kaynak | Sıklık |
|--------|----------------|--------|:------:|
| Exchange Netflow | + = exchange'e giriş (satış), - = çıkış (hodl) | CryptoQuant / Glassnode | 1h |
| Miner Reserve | Miner'ların BTC stoğu | Blockchain.com | 1 gün |
| Stablecoin Supply | USDT+USDC toplam supply değişimi | CoinGecko | 1 gün |
| MVRV Ratio | Market Value / Realized Value | CoinGecko / Lookintobitcoin | 1 gün |
| NUPL | Net Unrealized Profit/Loss | Glassnode | 1 gün |
| NVT Signal | Network Value to Transactions | Blockchain.com | 1 gün |
| Active Addresses | Günlük aktif adres sayısı | Blockchain.com | 1 gün |

#### On-chain → trading etkisi

```
onchain_score hesaplama (-1.0 → +1.0):

  exchange_netflow_score:
    netflow > +5000 BTC/gün → -0.3 (satış baskısı)
    netflow < -5000 BTC/gün → +0.3 (hodl modu)
    arasında → 0

  miner_reserve_score:
    reserve artıyor → +0.1 (miner'lar satmıyor)
    reserve azalıyor → -0.1 (miner'lar satıyor)

  stablecoin_score:
    supply artıyor → +0.2 (alım gücü artıyor)
    supply azalıyor → -0.2 (likidite çekilmesi)

  mvrv_score:
    MVRV > 3.5 → -0.4 (aşırı kârdalar, satış riski)
    MVRV < 1.0 → +0.3 (undervalued olabilir)
    arasında → 0

  onchain_score = sum(tüm component'ler)
  clamp(-1.0, +1.0)
```

---

### 21.5 — Sosyal Medya Sentiment

#### Veri kaynakları

| Platform | API / Yöntem | Ne çekilir | Sıklık |
|----------|-------------|-----------|:------:|
| Twitter/X | `api.twitter.com` (v2) veya scraper | #BTC, #ETH, $BTC hashtagler, influencer tweet'ler | 15 dk |
| Reddit | `reddit.com/r/cryptocurrency.json` | Hot/new post'lar, yorum sayısı, upvote | 30 dk |
| Telegram | Bot API + kanal scraper | Crypto kanal mesajları (signal grupları) | 30 dk |
| LunarCrush | `lunarcrush.com/api` | Social volume, galaxy score | 1h |

#### Influencer listesi (ağırlıklı)

```
TIER 1 (yüksek etki, ağırlık: 3×):
  - @elonmusk (market mover, geçmişte DOGE +300%)
  - Vitalik Buterin (@VitalikButerin)
  - CZ Binance (@caborofficial)
  - Michael Saylor (@saylor)

TIER 2 (orta etki, ağırlık: 2×):
  - Arthur Hayes (@CryptoHayes)
  - Raoul Pal (@RaoulGMI)
  - PlanB (@100trillionUSD)
  - Willy Woo (@woonomic)

TIER 3 (düşük etki, ağırlık: 1×):
  - Genel #BTC #ETH hashtag volume
  - Reddit r/cryptocurrency hot post sentiment
  - Telegram signal kanal consensus

Ağırlıklı ortalama ile social_score hesaplanır.
```

#### 8B Model ile tweet analizi

```
Prompt template (tweet_sentiment.txt):

Sen bir crypto piyasa analisti botsun. 
Aşağıdaki tweet'i analiz et.

TWEET: "{tweet_text}"
YAZAR: {author} (Takipçi: {followers})
TARİH: {created_at}

JSON formatında yanıt ver:

{
  "sentiment": "BULLISH | BEARISH | NEUTRAL | SARCASTIC",
  "market_impact": 0.0 ile 1.0 arası,
  "affected_assets": ["BTC", "DOGE", ...],
  "is_pump_signal": true | false,
  "confidence": 0.0 ile 1.0 arası
}

UYARI: "SARCASTIC" = ironi/şaka. Pump signal = manipülatif.
```

#### Social sentiment → trading etkisi

```
social_score hesaplama (-1.0 → +1.0):

1. Tier-weighted influencer tweets (son 6h)
2. Reddit sentiment (hot 25 post)
3. Social volume change (24h vs 7d avg)
4. LunarCrush galaxy score (varsa)

social_score > +0.60  → Sosyal bullish. Long bias güçlenir.
social_score < -0.60  → Sosyal bearish. Short bias güçlenir.

UYARI VETO:
  IF is_pump_signal == true:
    → O asset 4h karantina (pump-dump riski)
    → Log: "PUMP_SIGNAL_QUARANTINE"
  
  IF social_volume > 5× ortalama VE fiyat flat:
    → Dikkat: hype var ama fiyata yansımamış
    → size modifier ×0.5 (temkinli)
```

---

### 21.6 — Event-Driven Pozisyon Koruma (Event Shield)

#### Tam event shield protokolü

```
EVENT TIPLERI VE AKSIYONLAR:

┌──────────────────────────────────────────────────────────────┐
│ Event Tipi         │ Önce (T-2h)     │ Sırasında    │ Sonra │
├──────────────────────────────────────────────────────────────┤
│ FOMC/CPI/NFP       │ Stop sıkılaştır │ Trade yok    │ 30dk  │
│ (yüksek etki)      │ Pyramid kapat   │ Full shield  │ bekle │
│                     │ Accel → core    │              │       │
├──────────────────────────────────────────────────────────────┤
│ Haber BEARISH >0.8 │ Long size ×0.5  │ Ters pozis.  │ —     │
│ (acil)              │ Short bias act. │ kontrol      │       │
├──────────────────────────────────────────────────────────────┤
│ Whale deposit >$10M│ Long size ×0.7  │ —            │ 2h    │
│                     │ Stop sıkılaştır │              │ bekle │
├──────────────────────────────────────────────────────────────┤
│ Exchange hack/halt │ TÜM KAPAT       │ Trade yok    │ İnsan │
│                     │ (full exit)     │              │ onay  │
├──────────────────────────────────────────────────────────────┤
│ Elon tweet DOGE    │ DOGE karantina │ —             │ 4h    │
│ (pump risk)         │ (pump guard)   │              │ bekle │
├──────────────────────────────────────────────────────────────┤
│ Stablecoin depeg   │ TÜM KAPAT       │ CRISIS mode  │ İnsan │
│ (USDT <$0.99)      │ (sistemik risk) │              │ onay  │
└──────────────────────────────────────────────────────────────┘
```

---

### 21.7 — İstihbarat Füzyonu (Intel Fusion)

#### Tüm kaynakları tek skora birleştir

```
hermes_score hesaplama (-1.0 → +1.0):

  hermes_score = (
    news_score      × 0.30 +    # 8B model haber analizi
    macro_score     × 0.20 +    # Makro takvim proximity
    whale_score     × 0.15 +    # Whale hareketleri
    onchain_score   × 0.20 +    # On-chain metrikler
    social_score    × 0.15      # Sosyal medya sentiment
  )

  clamp(-1.0, +1.0)
```

#### Hermes score → SQS C5 dönüşümü

```
SQS C5 (hermes_news_risk) hesaplama:

  IF hermes_score >= 0:
    c5 = 0.5 + (hermes_score × 0.5)
    # +1.0 → c5 = 1.0 (çok olumlu, sqs artırır)
    # 0.0  → c5 = 0.5 (nötr)
  
  IF hermes_score < 0:
    c5 = 0.5 + (hermes_score × 0.5)
    # -0.5 → c5 = 0.25
    # -1.0 → c5 = 0.0 (çok olumsuz, sqs düşürür)

  SQS total'de C5 ağırlığı: %15

SONUÇ:
  Çok olumsuz haber akışı → SQS düşer → daha az trade açılır
  Çok olumlu haber akışı → SQS artar → trade kalitesi yükselir
```

#### Hermes score → size modifier

```
Ek olarak, hermes_score doğrudan size'ı etkiler:

  hermes > +0.5:  size ×1.1 (biraz daha agresif)
  hermes > +0.8:  size ×1.2 (güçlü pozitif sinyal)
  hermes < -0.5:  size ×0.7 (dikkatli ol)
  hermes < -0.8:  size ×0.5 (çok temkinli)
  hermes < -0.9:  TRADE YAPMA (event shield aktif)
```

---

### 21.8 — Intelligence DB Tabloları

```sql
CREATE TABLE IF NOT EXISTS news_analyses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  headline TEXT NOT NULL,
  source TEXT NOT NULL,
  sentiment TEXT NOT NULL CHECK(sentiment IN ('BULLISH','BEARISH','NEUTRAL')),
  impact_score REAL NOT NULL,
  affected_assets TEXT NOT NULL,
  category TEXT NOT NULL,
  urgency TEXT NOT NULL,
  model_confidence REAL NOT NULL,
  reasoning TEXT,
  news_score REAL NOT NULL,
  model_used TEXT DEFAULT 'llama3.1:8b'
);

CREATE TABLE IF NOT EXISTS macro_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_name TEXT NOT NULL,
  event_date TEXT NOT NULL,
  event_time TEXT,
  impact TEXT NOT NULL CHECK(impact IN ('HIGH','MEDIUM','LOW')),
  forecast TEXT,
  previous TEXT,
  actual TEXT,
  shield_activated INTEGER DEFAULT 0,
  shield_level TEXT
);

CREATE TABLE IF NOT EXISTS whale_alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  tx_hash TEXT,
  asset TEXT NOT NULL,
  amount_usd REAL NOT NULL,
  direction TEXT NOT NULL CHECK(direction IN ('EXCHANGE_IN','EXCHANGE_OUT','WALLET_TO_WALLET')),
  from_label TEXT,
  to_label TEXT,
  whale_score REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS social_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  platform TEXT NOT NULL,
  asset TEXT NOT NULL,
  sentiment_score REAL NOT NULL,
  social_volume INTEGER,
  influencer_mentions INTEGER DEFAULT 0,
  pump_signals INTEGER DEFAULT 0,
  social_score REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS hermes_fusion_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  news_score REAL,
  macro_score REAL,
  whale_score REAL,
  onchain_score REAL,
  social_score REAL,
  hermes_score REAL NOT NULL,
  c5_value REAL NOT NULL,
  size_modifier REAL NOT NULL,
  event_shield_active INTEGER DEFAULT 0,
  event_shield_reason TEXT
);
```

---

### 21.9 — Intelligence Config

```yaml
# config/hedge_fund.yaml (intelligence bölümü eklenir)

intelligence:
  enabled: true
  
  local_model:
    provider: "ollama"                # ollama veya llama-cpp
    model: "llama3.1:8b"
    endpoint: "http://localhost:11434"
    timeout_seconds: 30
    max_concurrent: 2
    fallback_on_timeout: "NEUTRAL"    # Model yanıt vermezse nötr al
  
  news:
    enabled: true
    sources:
      - name: "cryptopanic"
        url: "https://cryptopanic.com/api/v1/posts/"
        api_key_env: "CRYPTOPANIC_API_KEY"
        interval_minutes: 5
      - name: "newsapi"
        url: "https://newsapi.org/v2/everything"
        api_key_env: "NEWSAPI_KEY"
        interval_minutes: 15
        queries: ["bitcoin", "ethereum", "crypto regulation", "fed rate"]
    max_headlines_per_cycle: 10
    min_impact_to_log: 0.3
  
  macro:
    enabled: true
    calendar_source: "forexfactory"
    update_interval_hours: 12
    shield_hours_before_high: 2
    shield_hours_before_medium: 1
    post_event_cooldown_minutes: 30
  
  whale:
    enabled: true
    whale_alert_api_key_env: "WHALE_ALERT_KEY"
    min_usd_threshold: 5000000          # $5M minimum
    etherscan_api_key_env: "ETHERSCAN_KEY"
  
  onchain:
    enabled: true
    update_interval_hours: 1
    sources: ["blockchain.com", "coingecko"]
  
  social:
    enabled: true
    twitter_bearer_env: "TWITTER_BEARER"
    reddit_enabled: true
    influencer_tiers:
      tier1: ["elonmusk", "VitalikButerin", "caborofficial", "saylor"]
      tier2: ["CryptoHayes", "RaoulGMI", "100trillionUSD"]
    pump_quarantine_hours: 4
  
  fusion:
    weights:
      news: 0.30
      macro: 0.20
      whale: 0.15
      onchain: 0.20
      social: 0.15
    veto_threshold: -0.90              # Bu değerin altında trade YAPMA
    shield_threshold: -0.70            # Bu değerin altında size ×0.5
```

---

### 21.10 — Ana Döngüye Entegrasyon (Güncellenmiş)

```
WHILE bot_running:

  1. FETCH (mevcut)
  
  1.5 INTELLIGENCE (YENİ ADIM)
     - hermes_core.update_all():
       a. news_nlp: Son haberleri çek → 8B model analiz → news_score
       b. macro_calendar: Yaklaşan event var mı? → macro_score
       c. whale_alert: Son 1h büyük transfer → whale_score
       d. onchain: Exchange netflow, miner reserve → onchain_score
       e. social_sentiment: Twitter/Reddit → social_score
       f. intel_fusion: Tümünü birleştir → hermes_score
     
     - event_shield: Shield aktif mi? Seviyesi ne?
     
  2. INDICATORS (mevcut)
  
  3. REGIME (mevcut)
  
  4. RISK CHECK (mevcut + hermes_score eklenir)
     - YENİ: hermes_score < veto_threshold → bu cycle SKIP
     - YENİ: event_shield aktifse → sadece exit
  
  5. SIGNAL (mevcut + C5 güncellenir)
     - SQS C5 = intel_fusion → hermes_score'dan hesaplanır
     
  6. SIZE (mevcut + hermes modifier eklenir)
     - size × hermes_size_modifier
  
  7-10. (mevcut, değişiklik yok)

END WHILE
```

---

## 22) PROFESYONEL BACKTEST MOTORU (QuantConnect Seviyesi)

### Neden gerekli?
Strateji test edemezsen geliştiremezsin. Mevcut basit backtest yetersiz — gerçek fee, slippage ve fill simülasyonu lazım.

### 22.1 — Mimari

```
┌─────────────────────────────────────────────────────────┐
│                  ARGUS BACKTEST ENGINE                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Data Feed│───▶│ Event Engine │───▶│ Strategy     │   │
│  │ (OHLCV+  │    │ (bar-by-bar  │    │ Executor     │   │
│  │  OB+Fund)│    │  tick simül) │    │ (gerçekçi    │   │
│  └──────────┘    └──────┬───────┘    │  fill sim)   │   │
│                         │            └──────┬───────┘   │
│                  ┌──────▼───────────────────▼───────┐   │
│                  │       Portfolio Tracker           │   │
│                  │  equity, pozisyon, PnL, DD        │   │
│                  └──────────────┬────────────────────┘   │
│                                │                         │
│                  ┌─────────────▼────────────────┐       │
│                  │    Report Generator           │       │
│                  │  Sharpe, Sortino, MaxDD,      │       │
│                  │  Win Rate, Profit Factor,     │       │
│                  │  Monthly Returns, Trade Log   │       │
│                  └──────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### 22.2 — Dosya Yapısı

```
src/backtest/
├── __init__.py
├── engine.py           # Ana backtest motoru (BacktestEngine sınıfı)
├── data_feed.py        # Bar/tick veri sağlayıcı
├── fill_simulator.py   # Gerçekçi emir doldurma (fee + slippage)
├── portfolio.py        # Portföy takibi + equity curve
├── metrics.py          # Performans metrikleri hesaplama
├── report.py           # HTML + JSON rapor üretici
├── walk_forward.py     # Rolling window optimizasyon
└── optimizer.py        # Parametre grid/random search
```

### 22.3 — BacktestEngine Sınıfı

```python
class BacktestEngine:
    """QuantConnect seviyesi event-driven backtest motoru."""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.portfolio = Portfolio(config)
        self.fill_sim = FillSimulator(
            taker_fee=0.0005,             # BingX taker: %0.05
            maker_fee=0.0002,             # BingX maker: %0.02
            slippage_model="volume_based",
            max_slippage_pct=0.001,
        )
        self.metrics = MetricsCollector()
    
    def run(self, strategy, data_feed) -> BacktestResult:
        """Bar-by-bar strateji çalıştır."""
        for bar in data_feed:
            # 1. Mevcut pozisyonları güncelle (SL/TP kontrol)
            self._check_exits(bar)
            # 2. Strateji sinyali al
            signal = strategy.on_bar(bar, self.portfolio)
            # 3. Emir varsa fill simülasyonu
            if signal:
                self._execute(signal, bar)
            # 4. Equity curve güncelle
            self.portfolio.mark_to_market(bar)
            self.metrics.record(bar, self.portfolio)
        return self.metrics.generate_report()
```

### 22.4 — FillSimulator (Gerçekçi Emir Doldurma)

```python
class FillSimulator:
    """Gerçek dünya koşullarını simüle et."""
    
    def simulate_fill(self, order, bar) -> FillResult:
        # 1. Limit order: fiyat bar'ın low/high'ına ulaştı mı?
        if order.type == "limit":
            if order.side == "buy" and bar.low <= order.price:
                fill_price = order.price
            elif order.side == "sell" and bar.high >= order.price:
                fill_price = order.price
            else:
                return FillResult(filled=False)
        
        # 2. Market order: slippage ekle
        elif order.type == "market":
            slippage = self._calc_slippage(order.size, bar.volume)
            fill_price = bar.close * (1 + slippage * (1 if order.side == "buy" else -1))
        
        # 3. Fee hesapla
        fee = fill_price * order.size * self.fee_rate(order.type)
        
        return FillResult(filled=True, fill_price=fill_price, fee=fee,
                          slippage=abs(fill_price - bar.close) / bar.close)
    
    def _calc_slippage(self, size, volume) -> float:
        """Hacme göre kayma: büyük emir + düşük hacim = çok kayma."""
        impact = (size / max(volume, 1)) * 0.1
        return min(impact, 0.005)  # Max %0.5 kayma
```

### 22.5 — Performans Metrikleri

```python
class MetricsCollector:
    def generate_report(self) -> BacktestReport:
        return BacktestReport(
            total_return_pct=self._total_return(),
            annualized_return_pct=self._annualized_return(),
            max_drawdown_pct=self._max_drawdown(),
            sharpe_ratio=self._sharpe(),            # Hedef: > 1.5
            sortino_ratio=self._sortino(),          # Hedef: > 2.0
            calmar_ratio=self._calmar(),            # Return / MaxDD
            total_trades=len(self.trades),
            win_rate=self._win_rate(),               # Hedef: > 55%
            profit_factor=self._profit_factor(),     # Hedef: > 1.5
            avg_win_loss_ratio=self._avg_rr(),       # Hedef: > 1.3
            total_fees=sum(t.fee for t in self.trades),
            total_slippage=sum(t.slippage for t in self.trades),
            fee_drag_pct=self._fee_drag(),
            monthly_returns=self._monthly_returns(),
            equity_curve=self.equity_history,
        )
```

### 22.6 — Walk-Forward Analiz

```python
class WalkForwardAnalyzer:
    """12 aylık rolling window backtest."""
    
    def __init__(self, train_months=6, test_months=1, step_months=1):
        self.train_months = train_months
        self.test_months = test_months
        self.step_months = step_months
    
    def analyze(self, strategy_factory, data) -> WalkForwardReport:
        results = []
        for window in self._generate_windows(data):
            best_params = self._optimize(strategy_factory, window.train_data)
            strategy = strategy_factory(best_params)
            result = BacktestEngine(self.config).run(strategy, window.test_data)
            results.append(result)
        
        return WalkForwardReport(
            windows=results,
            avg_return=mean([r.total_return_pct for r in results]),
            avg_sharpe=mean([r.sharpe_ratio for r in results]),
            stability=self._stability_score(results),
            overfitting_score=self._detect_overfit(results),
        )
```

### 22.7 — Kabul Kriterleri

```
[ ] Fee + slippage dahil gerçekçi backtest
[ ] 12 aylık walk-forward tek komutla çalışır
[ ] HTML rapor: equity curve grafik + aylık tablo + trade logları
[ ] Sharpe, Sortino, Calmar, Profit Factor hesaplanır
[ ] Overfit tespiti (train vs test farkı)
```

---

## 23) BingX MULTİ-ASSET GENİŞLEME (Hisse + Emtia + İndeks)

### Neden gerekli?
BingX'te hisse CFD + emtia + indeks var. Daha fazla varlık = daha fazla fırsat + korelasyon düşer.

### 23.1 — BingX Desteklenen Varlıklar

```
KRİPTO (mevcut):
  Perpetual Futures: BTC, ETH, SOL, DOGE, AVAX, LINK, ARB, MATIC
  Kaldıraç: 1x-150x (biz max 3x kullanacağız)
  Fee: Maker %0.02, Taker %0.05

HİSSE CFD (YENİ):
  US Hisseleri: AAPL, TSLA, NVDA, MSFT, AMZN, GOOGL, META, AMD
  Kaldıraç: 1x-20x (biz max 2x)
  Fee: %0.05 + spread
  NOT: Gerçek hisse değil CFD. Avantaj: 7/24 bazıları, düşük minimum.
       Dezavantaj: Spread geniş olabilir, overnight fee var.

EMTİA CFD (YENİ):
  XAU/USD (Altın), XAG/USD (Gümüş), CRUDE OIL
  Kaldıraç: 1x-100x (biz max 2x)

İNDEKS (YENİ):
  NAS100, SPX500, US30
```

### 23.2 — Multi-Asset Adapter Yapısı

```
src/adapters/
├── __init__.py
├── base.py              # AbstractExchangeAdapter (Protocol)
├── bingx/
│   ├── __init__.py
│   ├── client.py        # REST + WebSocket client
│   ├── crypto_adapter.py    # Kripto futures
│   ├── stock_adapter.py     # Hisse CFD
│   └── commodity_adapter.py # Emtia CFD
├── data_normalizer.py   # Tüm adapter'lardan → MarketSnapshot
└── fee_models.py        # Varlık bazlı fee modeli

# Adapter interface:
class AbstractExchangeAdapter(Protocol):
    async def fetch_ohlcv(symbol, timeframe, limit) -> list[Candle]
    async def fetch_orderbook(symbol, depth) -> OrderBook
    async def place_order(order: Order) -> OrderResult
    async def cancel_order(order_id: str) -> bool
    async def get_positions() -> list[Position]
    async def get_balance() -> Balance
    async def subscribe_ticker(symbol, callback) -> None
```

### 23.3 — Varlık Korelasyon Kontrolü

```
Hedef: Korelasyonu düşük varlıklar aynı anda trade et.

          BTC    ETH    AAPL   NVDA   XAU    NAS100
BTC       1.00   0.85   0.30   0.25   0.05   0.35
ETH       0.85   1.00   0.25   0.20   0.03   0.30
AAPL      0.30   0.25   1.00   0.70   0.10   0.85
NVDA      0.25   0.20   0.70   1.00   0.05   0.80
XAU       0.05   0.03   0.10   0.05   1.00   -0.20
NAS100    0.35   0.30   0.85   0.80   -0.20  1.00

KURAL: Korelasyonu > 0.6 olan varlıklarda aynı yönde aynı anda
       MAX 1 pozisyon. İkincisi yarı boyutta.
```

---

## 24) ŞİRKET RADAR SİSTEMİ (Fırsat Bulucu)

### Neden gerekli?
Düşük değerli ama potansiyeli yüksek şirketleri bul → kısa vadede pozisyon al.

### 24.1 — Mimari

```
┌─────────────────────────────────────────────────────────┐
│              ARGUS RADAR SYSTEM                          │
├─────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐    │
│  │ Fundamental│  │ Technical  │  │ Sentiment      │    │
│  │ Scanner    │  │ Scanner    │  │ Scanner        │    │
│  └─────┬──────┘  └─────┬──────┘  └───────┬────────┘    │
│        └───────────────┼──────────────────┘              │
│               ┌────────▼────────┐                        │
│               │ Composite       │                        │
│               │ Opportunity     │                        │
│               │ Scorer          │                        │
│               └────────┬────────┘                        │
│               ┌────────▼────────┐                        │
│               │ Watchlist       │  Top 10-20 fırsat      │
│               │ Generator      │  günlük güncellenir     │
│               └─────────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

### 24.2 — Dosya Yapısı

```
src/radar/
├── __init__.py
├── fundamental.py      # P/E, P/S, gelir büyümesi, borç/özkaynak
├── technical.py        # 52w low, RSI, volume spike, golden cross
├── sentiment.py        # Reddit, Twitter, analyst upgrades, insider buys
├── composite_scorer.py # 3 faktör birleştirme
├── watchlist.py        # Günlük watchlist üretici
└── radar_config.py     # Tarama parametreleri
```

### 24.3 — Fundamental Scanner

```python
class FundamentalFilter:
    """Ucuz ama büyüyen şirketleri bul."""
    pe_ratio_max: float = 15.0       # Ucuz P/E
    pe_ratio_min: float = 3.0        # Çok düşük = tehlike
    ps_ratio_max: float = 3.0        # Ucuz P/S
    revenue_growth_min: float = 0.10  # >%10 gelir büyümesi
    debt_equity_max: float = 1.5     # Düşük borç
    market_cap_min: float = 500e6    # >$500M
    market_cap_max: float = 50e9     # <$50B (büyükler yavaş hareket eder)
    insider_buying_last_90d: bool = True

Veri Kaynakları:
  - Financial Modeling Prep API (ücretsiz: 250 req/gün)
  - Yahoo Finance (yfinance kütüphanesi)
  - SEC EDGAR (insider filings)

Skor (0-100):
  pe_score    = 25 × (1 - pe/pe_max)
  growth_score = 25 × min(revenue_growth/0.5, 1.0)
  insider_score = 25 × insider_buy_ratio
  value_score  = 25 × (1 - ps/ps_max)
```

### 24.4 — Technical Scanner

```
Tarama (günlük çerçeve):
  - 52-hafta düşük yakınında (%10 içinde) → geri dönüş potansiyeli
  - RSI(14) < 30 → aşırı satım
  - Volume spike > 3× ortalama → ilgi çekiyor
  - Golden cross yaklaşıyor (EMA50 ≈ EMA200)
  - MACD histogram pozitife dönüyor

Skor (0-100):
  distance_from_52wk_low × 30 +
  rsi_oversold_score × 25 +
  volume_confirmation × 25 +
  trend_reversal_signals × 20
```

### 24.5 — Sentiment Scanner

```
Kaynaklar:
  - Reddit r/wallstreetbets, r/stocks trending
  - Twitter/X finans hesapları mention sayısı
  - Analyst upgrade/downgrade (Finviz)
  - Insider buying clusters (OpenInsider)

Skor (0-100):
  social_buzz × 20 +
  analyst_consensus × 30 +
  insider_cluster × 30 +
  momentum_shift × 20
```

### 24.6 — Günlük Radar Raporu Çıktısı

```
ARGUS RADAR — 2026-02-14
═══════════════════════════════════════════
Rank | Sembol | Skor | Fund. | Tech. | Sent. | Aksiyon
  1  | PLTR   |  87  |  82   |  90   |  88   | STRONG BUY
  2  | SOFI   |  81  |  78   |  85   |  80   | BUY
  3  | RKLB   |  76  |  70   |  82   |  75   | WATCH
  ...

Toplam taranan: 2,500+ hisse
Filtre sonrası: 15-20 aday
Top 5 otomatik watchlist'e eklenir
BingX'te varsa otomatik trade'e açılır
```

### 24.7 — Radar DB tabloları

```sql
CREATE TABLE IF NOT EXISTS radar_scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  fundamental_score REAL,
  technical_score REAL,
  sentiment_score REAL,
  composite_score REAL NOT NULL,
  rank INTEGER,
  action TEXT CHECK(action IN ('STRONG_BUY','BUY','WATCH','SKIP')),
  in_watchlist INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS radar_watchlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  added_date TEXT NOT NULL,
  composite_score REAL NOT NULL,
  current_price REAL,
  entry_price REAL,
  status TEXT DEFAULT 'WATCHING' CHECK(status IN ('WATCHING','ENTERED','EXITED','EXPIRED'))
);
```

---

## 25) OTONOM STRATEJİ FABRİKASI (Self-Generating)

### Neden gerekli?
İnsan müdahalesi olmadan yeni stratejiler üretmeli, test etmeli, onaylamalı.

### 25.1 — Mimari

```
┌──────────────────────────────────────────────────────────────┐
│             OTONOM STRATEJİ FABRİKASI                         │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────┐    ┌────────────┐    ┌──────────────────┐    │
│  │ Factor     │───▶│ Strategy   │───▶│ Auto Backtest    │    │
│  │ Discovery  │    │ Generator  │    │ & Validation     │    │
│  │ (alpha     │    │ (kombine   │    │ (walk-forward    │    │
│  │  arama)    │    │  et)       │    │  + Monte Carlo)  │    │
│  └────────────┘    └────────────┘    └────────┬─────────┘    │
│                                               │               │
│                                      ┌────────▼─────────┐    │
│                                      │ Promotion Gate   │    │
│                                      │ (canlıya terfi)  │    │
│                                      └────────┬─────────┘    │
│                              ┌────────────────▼──────┐       │
│                              │ PAPER → LIVE pipeline │       │
│                              └───────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

### 25.2 — Dosya Yapısı

```
src/factory/
├── __init__.py
├── factor_discovery.py   # 100+ faktör tarama, IC hesaplama
├── strategy_generator.py # Faktörlerden strateji üretme
├── auto_validator.py     # Backtest + walk-forward + Monte Carlo
├── promotion_gate.py     # Paper → live terfi yönetimi
├── strategy_registry.py  # Aktif/arşiv strateji kayıtları
└── factory_config.py     # Parametreler
```

### 25.3 — Factor Discovery Engine

```python
class FactorDiscovery:
    """Otomatik alpha keşfi — 100+ faktör arasından en iyi olanları bul."""
    
    FACTOR_POOL = [
        # Teknik (60+)
        "rsi_14", "rsi_7", "rsi_21",
        "bb_pct_b_20_2", "bb_pct_b_20_3",
        "adx_14", "adx_7",
        "ema_cross_5_21", "ema_cross_21_55",
        "volume_ratio_5", "volume_ratio_20",
        "macd_signal", "macd_histogram",
        "obv_slope", "cmf_20",
        "atr_ratio_5_20", "vwap_deviation",
        "orderbook_imbalance", "funding_rate_zscore",
        "open_interest_change",
        # ... 40+ daha
        
        # Fundamental (hisse için)
        "pe_ratio_zscore", "ps_ratio_zscore",
        "revenue_growth_qoq", "earnings_surprise",
        "insider_buy_ratio",
        
        # Sentiment
        "news_sentiment_score", "social_buzz_zscore", "whale_flow_direction",
    ]
    
    def discover(self, data, target="next_1h_return"):
        """Her faktörün Information Coefficient'ini hesapla."""
        results = []
        for factor in self.FACTOR_POOL:
            ic = self._compute_ic(data[factor], data[target])  # Korelasyon
            ic_std = self._compute_ic_std(data[factor], data[target])
            turnover = self._compute_turnover(data[factor])
            results.append(FactorResult(
                name=factor,
                ic=ic,
                ic_ir=ic / max(ic_std, 0.001),  # IC Information Ratio
                turnover=turnover,
                profitable=(ic > 0.03),  # IC > 0.03 = alpha var
            ))
        return sorted(results, key=lambda x: x.ic_ir, reverse=True)[:20]
```

### 25.4 — Strategy Generator

```python
class StrategyGenerator:
    """Keşfedilen faktörlerden strateji üret."""
    
    def generate(self, top_factors: list[FactorResult]) -> list[Strategy]:
        strategies = []
        
        # 1. Tekli faktör stratejileri
        for f in top_factors[:10]:
            strategies.append(SingleFactorStrategy(
                factor=f.name,
                long_threshold=f.optimal_long,
                short_threshold=f.optimal_short,
            ))
        
        # 2. 2'li kombinasyonlar (korelasyonu düşük olanları kombine et)
        for f1, f2 in combinations(top_factors[:10], 2):
            if abs(correlation(f1, f2)) < 0.5:
                strategies.append(DualFactorStrategy(f1, f2))
        
        # 3. ML-tabanlı ensemble (top 15 faktör → LightGBM)
        if len(top_factors) >= 5:
            strategies.append(MLEnsembleStrategy(
                factors=top_factors[:15],
                model_type="lightgbm",
            ))
        
        return strategies
```

### 25.5 — Auto Validation + Promotion

```python
class AutoValidator:
    """Üretilen stratejileri test et, başarılıları terfi ettir."""
    
    PROMOTION_CRITERIA = {
        "min_sharpe": 1.5,
        "min_profit_factor": 1.3,
        "max_drawdown": 0.10,
        "min_trades": 50,
        "min_win_rate": 0.45,
        "walk_forward_stable": True,
        "overfit_score_max": 0.3,
    }
    
    def validate(self, strategy) -> ValidationResult:
        # 1. Tam veri backtest
        full_result = self.backtest_engine.run(strategy, full_data)
        # 2. Walk-forward (6 ay eğitim, 1 ay test, 12 pencere)
        wf_result = self.walk_forward.analyze(strategy, full_data)
        # 3. Monte Carlo simülasyon (trade sırasını karıştır, 1000 iterasyon)
        mc_result = self._monte_carlo(strategy, n_simulations=1000)
        # 4. Overfit tespiti
        overfit = self._detect_overfit(full_result, wf_result)
        # 5. Terfi kararı
        promoted = all(criteria_checks...)
        return ValidationResult(
            promoted=promoted,
            deploy_to="paper" if promoted else "archive",
        )

Strateji Yaşam Döngüsü:
  DISCOVERED → BACKTESTED → VALIDATED → PAPER (2 hafta) → LIVE → [RETIRED]
  
  Paper'da 2 hafta başarılı → otomatik LIVE'a terfi
  Live'da 1 hafta başarısız → otomatik deaktive
```

### 25.6 — Factory DB tabloları

```sql
CREATE TABLE IF NOT EXISTS discovered_factors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  discovery_date TEXT NOT NULL,
  factor_name TEXT NOT NULL,
  ic REAL NOT NULL,
  ic_ir REAL NOT NULL,
  turnover REAL,
  profitable INTEGER
);

CREATE TABLE IF NOT EXISTS generated_strategies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy_name TEXT NOT NULL,
  factors_used TEXT NOT NULL,         -- JSON list
  strategy_type TEXT NOT NULL,        -- "single"|"dual"|"ml_ensemble"
  status TEXT DEFAULT 'DISCOVERED',
  sharpe REAL, profit_factor REAL, max_dd REAL, win_rate REAL,
  overfit_score REAL,
  promoted_to_paper_at TEXT,
  promoted_to_live_at TEXT,
  retired_at TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
```

---

## 26) KENDİNİ GELİŞTİREN SİSTEM (Auto-Optimization)

### Neden gerekli?
Sistem boşa çalışmasın. Her döngüde daha iyi olsun. 7/24 açıkken kendi kendini optimize etsin.

### 26.1 — Haftalık Evolution Cycle (Her Pazar 00:00 UTC)

```
┌────────────────────────────────────────────────────────────┐
│ HAFTALIK EVOLUTION CYCLE                                    │
│                                                             │
│ 1. Son 7 günün trade'lerini analiz et                       │
│ 2. Kaybeden stratejileri teşhis et (neden kaybetti?)        │
│ 3. Parametreleri micro-adjust et (bounded: max ±%10)        │
│ 4. Yeni faktörler tara → yeni strateji adayları üret        │
│ 5. Walk-forward ile doğrula                                  │
│ 6. A/B test başlat (eski vs yeni, paper'da)                 │
│ 7. 1 hafta sonra kazananı seç → live'a terfi                │
└────────────────────────────────────────────────────────────┘
```

### 26.2 — Dosya Yapısı

```
src/evolution/
├── __init__.py
├── performance_monitor.py  # 7/24 KPI takibi + alert
├── diagnostics.py          # Neden kaybettik? analizi
├── optimizer.py            # Bounded auto-parametre ayarlama
├── ab_tester.py            # Eski vs yeni config karşılaştırma
├── auto_deploy.py          # Kazanan config'i live'a geçir
└── evolution_config.py     # Sınırlar + parametreler
```

### 26.3 — Performance Monitor

```python
class PerformanceMonitor:
    """7/24 KPI takibi."""
    kpi_dashboard = {
        "equity": float,
        "daily_pnl": float,
        "weekly_pnl": float,
        "monthly_pnl": float,
        "current_drawdown": float,
        "sharpe_rolling_30d": float,
        "win_rate_7d": float,
        "trades_today": int,
        "active_positions": int,
    }
    
    ALERTS = {
        "EQUITY_NEW_HIGH": "🎉 Yeni ATH!",
        "DRAWDOWN_WARNING": "⚠️ DD > %5",
        "DRAWDOWN_CRITICAL": "🚨 DD > %8 — trade duraklatıldı",
        "STRATEGY_DEGRADED": "📉 Strateji X son 20 trade'de negatif",
        "EDGE_LOST": "❌ Strateji X edge'i kayboldu (Sharpe < 0.5)",
    }
```

### 26.4 — Diagnostic Engine

```python
class DiagnosticEngine:
    """Neden kaybettik? Neden kazandık?"""
    
    def diagnose(self, trades) -> Diagnosis:
        return Diagnosis(
            losing_regimes=self._losing_by_regime(trades),
            losing_hours=self._losing_by_hour(trades),
            losing_symbols=self._losing_by_symbol(trades),
            sl_too_tight=self._check_sl_hit_rate(trades),
            tp_too_far=self._check_tp_hit_rate(trades),
            entry_timing=self._check_entry_timing(trades),
            regime_shift=self._detect_regime_shift(),
            recommendations=[
                "SL mesafesini %15 artır (son 50 trade %68 SL'ye takıldı)",
                "RANGING'de Nautilus'u deaktive et (son 30d -$45)",
                "Gece 02:00-06:00 UTC trade durdur (en kötü saatler)",
            ],
        )
```

### 26.5 — Bounded Auto-Optimizer

```python
class BoundedOptimizer:
    """Parametreleri güvenli sınırlar içinde ayarla.
    
    KURAL: Tek seferde max ±%10 değişiklik.
    KURAL: Her değişiklik walk-forward ile doğrulanmalı.
    KURAL: Değişiklik paper'da 1 hafta test edilmeli.
    """
    
    TUNABLE_PARAMS = {
        # Parametre adı → (min, max, step)
        "titan.min_confidence":    (0.55, 0.80, 0.01),
        "nautilus.min_confidence": (0.55, 0.80, 0.01),
        "hydra.rsi_oversold":     (20, 35, 1),
        "hydra.rsi_overbought":   (65, 80, 1),
        "risk.sl_atr_mult":       (1.0, 3.0, 0.1),
        "risk.tp_atr_mult":       (1.5, 5.0, 0.25),
        "risk.max_risk_pct":      (0.01, 0.03, 0.001),
        "risk.dd_halt_pct":       (0.03, 0.08, 0.005),
    }
```

### 26.6 — A/B Testing Framework

```python
class ABTester:
    """Eski config vs yeni config — paper'da 7 gün yarıştır."""
    
    def start_test(self, variant_a, variant_b, duration_days=7):
        # A: Mevcut (kontrol grubu)
        # B: Optimize edilmiş (deney grubu)
        # 7 gün sonra: Sharpe, DD, Profit Factor karşılaştır
        # Kazanan → live'a terfi

    def evaluate(self, test_id) -> ABResult:
        # B variant, A'dan Sharpe'da >%10 ve DD'de <%5 iyiyse → B kazanır
        # Aksi halde A kalır (status quo bias — güvenlik)
```

---

## 27) 7/24 OTONOM OPERASYON (Daemon + Telegram)

### Neden gerekli?
Sistem uyurken de para kazanmalı. Çökse bile kendini toparlamalı.

### 27.1 — Sistem Mimarisi

```
┌──────────────────────────────────────────────────────────────┐
│                  ARGUS 7/24 DAEMON                            │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐     │
│  │ Scheduler  │  │ Watchdog   │  │ Health Monitor     │     │
│  │ (cron +    │  │ (crash     │  │ (heartbeat +       │     │
│  │  interval) │  │  recovery) │  │  /health endpoint) │     │
│  └─────┬──────┘  └─────┬──────┘  └────────┬───────────┘     │
│        └───────────────┼──────────────────┘                   │
│               ┌────────▼────────┐                             │
│               │ Main Loop       │                             │
│               │ her 1 dk:       │                             │
│               │  sinyal + risk  │                             │
│               │  + pozisyon     │                             │
│               │  + telemetri    │                             │
│               └─────────────────┘                             │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ZAMANLANMIŞ GÖREVLER                                   │  │
│  │                                                        │  │
│  │ Her 1 dk:    Sinyal tarama + pozisyon güncelleme        │  │
│  │ Her 5 dk:    Orderbook snapshot + whale kontrol         │  │
│  │ Her 15 dk:   Scalp sinyal tarama (Hydra)                │  │
│  │ Her 1 saat:  Ana sinyal döngüsü (tüm motorlar)         │  │
│  │ Her 4 saat:  Rejim yeniden sınıflandırma                │  │
│  │ Her gün 06:00: Radar tarama + günlük rapor              │  │
│  │ Her Pazar:   Evolution cycle (parametre optimizasyon)    │  │
│  │ Her ay 1.:   Aylık performans raporu                    │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 27.2 — Dosya Yapısı

```
src/daemon/
├── __init__.py
├── main_loop.py        # Ana 7/24 döngü
├── scheduler.py        # Zamanlanmış görevler (cron + interval)
├── watchdog.py         # Crash recovery + otomatik yeniden başlatma
├── health.py           # HTTP health endpoint (/health)
├── telegram_bot.py     # Bildirim + komut sistemi
└── state_manager.py    # Pozisyon + durum kalıcılığı (SQLite)
```

### 27.3 — Crash Recovery Protokolü

```
1. Watchdog süreci ana süreci izler
2. Çökme tespit → 10 sn bekle → yeniden başlat
3. Yeniden başlatılınca:
   a. Mevcut pozisyonları exchange'den oku
   b. SL emirlerinin hala aktif olduğunu kontrol et
   c. Eksik SL varsa hemen koy
   d. Normal döngüye devam et
4. 3 art arda çökme → HALT + Telegram bildirimi
```

### 27.4 — Telegram Bot (Bildirim + Kontrol)

```
BİLDİRİM MESAJLARI:
  📈 "LONG BTC @ $45,230 | Conf: 0.82 | Engine: Titan"
  📉 "CLOSED ETH | +2.3% | Duration: 4.5h"
  🎉 "Günlük rapor: +$12.50 (+1.8%) | 5W/2L"
  ⚠️ "DD %6.2 — pozisyon boyutu azaltıldı"
  🚨 "HALT — 3 art arda çökme — müdahale gerekli"

KOMUTLAR (Telegram'dan kontrol):
  /status       — anlık durum (equity, DD, pozisyon sayısı)
  /positions    — açık pozisyonlar listesi
  /pnl          — günlük/haftalık/aylık PnL
  /halt         — trade'i durdur
  /resume       — trade'e devam et
  /close_all    — tüm pozisyonları kapat
  /radar        — son radar tarama sonuçları
  /evolution    — son evolution cycle raporu
```

### 27.5 — Health Endpoint

```python
# GET http://localhost:8080/health
{
    "status": "healthy",
    "uptime_hours": 168.5,
    "last_cycle": "2026-02-14T15:30:00Z",
    "open_positions": 2,
    "equity": 847.32,
    "dd_pct": 1.2,
    "regime": "TREND_STRONG",
    "last_trade": "2h ago",
    "watchdog_restarts": 0,
    "errors_24h": 0
}
```

---

## 28) RİSK VE GÜVENLİK KURALLARI (TÜM FAZLAR İÇİN)

```
1.  ASLA %1.5'ten fazla tek trade riski alma
2.  ASLA günlük %3'ten fazla kaybet
3.  ASLA %10'dan fazla drawdown'a izin ver
4.  Her pozisyonda EXCHANGE-SIDE STOP LOSS zorunlu
5.  Her parametre değişikliği max ±%10
6.  Her yeni strateji 2 hafta paper → sonra live
7.  3 art arda çökme → TÜM trade DURDUR
8.  FED/CPI gibi olaylarda 30 dk önceden trade durdur
9.  Tüm trade'ler, kararlar, metrikler loglanır — silme YOK
10. Günde 1 kez otomatik SQLite yedekleme
```

---

## 29) GÜNCEL MODÜL LİSTESİ (TÜM SİSTEM)

```
src/v25/                                 # 80+ modül
├── bot/
│   ├── main_loop.py, scheduler.py, health_check.py
│
├── data/
│   ├── feed_bingx.py, feed_binance.py, feed_coingecko.py
│   ├── feed_yahoo.py, cross_checker.py, sentiment.py
│   ├── normalizer.py, indicators.py
│
├── signal/
│   ├── regime_classifier.py, sqs_engine.py
│   ├── chop/ (detector.py, edge_score.py, templates.py)
│   ├── trend/ (templates.py, momentum.py)
│   └── multi_tf.py
│
├── risk/
│   ├── position_sizer.py, exposure_manager.py
│   ├── circuit_breaker.py, cash_governor.py
│   ├── correlation_guard.py, black_swan.py
│
├── growth/
│   ├── compounder.py, pyramiding.py, accel_engine.py
│   ├── equity_momentum.py, alpha_rotation.py
│
├── learning/                             # Self-learning (Section 17)
│   ├── trade_tagger.py, pattern_detector.py
│   ├── threshold_tuner.py, edge_monitor.py
│   ├── counterfactual.py, learning_config.py
│
├── intelligence/                         # Hermes (Section 21)
│   ├── hermes_core.py, news_nlp.py, macro_calendar.py
│   ├── whale_alert.py, onchain.py, social_sentiment.py
│   ├── event_shield.py, intel_fusion.py, intel_config.py
│   └── prompts/ (news_analysis.txt, tweet_sentiment.txt, event_impact.txt)
│
├── backtest/                             # [YENİ] Section 22
│   ├── engine.py, data_feed.py, fill_simulator.py
│   ├── portfolio.py, metrics.py, report.py
│   ├── walk_forward.py, optimizer.py
│
├── adapters/                             # [YENİ] Section 23
│   ├── base.py
│   ├── bingx/ (client.py, crypto_adapter.py, stock_adapter.py, commodity_adapter.py)
│   ├── data_normalizer.py, fee_models.py
│
├── radar/                                # [YENİ] Section 24
│   ├── fundamental.py, technical.py, sentiment.py
│   ├── composite_scorer.py, watchlist.py, radar_config.py
│
├── factory/                              # [YENİ] Section 25
│   ├── factor_discovery.py, strategy_generator.py
│   ├── auto_validator.py, promotion_gate.py
│   ├── strategy_registry.py, factory_config.py
│
├── evolution/                            # [YENİ] Section 26
│   ├── performance_monitor.py, diagnostics.py
│   ├── optimizer.py, ab_tester.py
│   ├── auto_deploy.py, evolution_config.py
│
├── daemon/                               # [YENİ] Section 27
│   ├── main_loop.py, scheduler.py, watchdog.py
│   ├── health.py, telegram_bot.py, state_manager.py
│
├── execution/
│   ├── bingx_client.py, ibkr_client.py [GELECEK]
│   ├── broker_router.py [GELECEK], order_manager.py
│   ├── slippage_tracker.py, hedging.py
│
├── exit/
│   ├── stop_manager.py, tp_manager.py
│   ├── time_stop.py, hard_exits.py
│
├── db/ (migrations.py, ledger.py, trade_log.py)
├── postmortem/ (tagger.py, edge_health.py, counterfactual.py, weekly_report.py)
├── contracts/, config/, bootstrap.py, telemetry/
```

---

**Son güncelleme:** 2026-02-14 v3
**Toplam section:** 29
**Toplam modül:** 80+
**Format:** AI Agent + 8B model dostu
