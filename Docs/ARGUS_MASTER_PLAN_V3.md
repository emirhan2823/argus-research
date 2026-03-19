# ARGUS v3.0 — AUTONOMOUS HEDGE FUND MASTER PLAN

**Tarih:** 2026-02-14  
**Durum:** DRAFT — Review Bekliyor  
**Hedef:** Full-otonom, kendi kendini geliştiren, 7/24 çalışan multi-asset trading sistemi  
**Başlangıç:** $100 + aylık $100 ekleme  
**Aylık Hedef:** %15-22 bileşik büyüme  

---

## İÇİNDEKİLER

1. [Faz 0: Backtest Motoru (QuantConnect Seviyesi)](#faz-0)
2. [Faz 1: Gerçek Zamanlı İstihbarat Sistemi](#faz-1)
3. [Faz 2: BingX Multi-Asset Genişleme](#faz-2)
4. [Faz 3: Şirket Radar Sistemi](#faz-3)
5. [Faz 4: Otonom Strateji Fabrikası](#faz-4)
6. [Faz 5: Kendini Geliştiren Sistem](#faz-5)
7. [Faz 6: 7/24 Otonom Operasyon](#faz-6)

---

## MEVCUT DURUM (Baseline)

```
Mevcut Motorlar: Titan (trend), Nautilus (range), Phoenix (volatility),
                 Hermes (haber), Atlas (risk overlay), Hydra (scalp) [YENİ]
Mevcut Varlık:   Crypto (8 sembol, BingX)
Mevcut Backtest: Walk-forward 12 aylık, ama basit — gerçek fee/slippage yok
Mevcut Sinyal:   Signal Quality Filter 6 faktörlü [YENİ]
Eksikler:        Profesyonel backtest, haber/whale feed, hisse, radar, otonomi
```

---

<a id="faz-0"></a>
## FAZ 0: PROFESYONEl BACKTEST MOTORU

**Süre:** 2 hafta  
**Öncelik:** 🔴 KRİTİK — Diğer her şey buna bağlı  
**Neden:** Strateji test edemezsen geliştiremezsin. QuantConnect/Lean seviyesi gerek.

### 0.1 Mimari

```
┌─────────────────────────────────────────────────────────┐
│                  ARGUS BACKTEST ENGINE                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Data Feed│───▶│ Event Engine │───▶│ Strategy     │   │
│  │ (OHLCV+  │    │ (tick-by-    │    │ Executor     │   │
│  │  OB+Fund)│    │  tick veya   │    │ (gerçekçi    │   │
│  └──────────┘    │  bar-by-bar) │    │  fill sim)   │   │
│                  └──────┬───────┘    └──────┬───────┘   │
│                         │                   │            │
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

### 0.2 Teknik Detaylar

#### Dosya Yapısı
```
src/backtest/
├── __init__.py
├── engine.py           # Ana backtest motoru
├── data_feed.py        # Bar/tick veri sağlayıcı
├── fill_simulator.py   # Gerçekçi emir doldurma
├── portfolio.py        # Portföy takibi + equity curve
├── metrics.py          # Performans metrikleri hesaplama
├── report.py           # HTML + JSON rapor üretici
├── walk_forward.py     # Rolling window optimizasyon
└── optimizer.py        # Parametre grid/random search
```

#### `engine.py` — Ana Motor Sınıfı
```python
class BacktestEngine:
    """QuantConnect seviyesi event-driven backtest motoru."""
    
    def __init__(self, config: BacktestConfig):
        self.config = config              # Başlangıç sermaye, fee, slippage
        self.portfolio = Portfolio(config) # Equity + pozisyon takibi
        self.fill_sim = FillSimulator(    # Gerçekçi fill
            taker_fee=0.0005,             # BingX taker: %0.05
            maker_fee=0.0002,             # BingX maker: %0.02
            slippage_model="volume_based", # Hacme göre kayma
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
            if signal: self._execute(signal, bar)
            # 4. Equity curve güncelle
            self.portfolio.mark_to_market(bar)
            self.metrics.record(bar, self.portfolio)
        return self.metrics.generate_report()
```

#### `fill_simulator.py` — Gerçekçi Emir Doldurma
```python
class FillSimulator:
    """Gerçek dünya koşullarını simüle et."""
    
    def simulate_fill(self, order, bar) -> FillResult:
        # 1. Limit order: fiyat bar'ın low/high'ına ulaştı mı?
        if order.type == "limit":
            if order.side == "buy" and bar.low <= order.price:
                fill_price = order.price  # Limit fiyattan dolduruldu
            elif order.side == "sell" and bar.high >= order.price:
                fill_price = order.price
            else:
                return FillResult(filled=False)  # Doldurulamadı
        
        # 2. Market order: slippage ekle
        elif order.type == "market":
            slippage = self._calc_slippage(order.size, bar.volume)
            fill_price = bar.close * (1 + slippage * (1 if order.side == "buy" else -1))
        
        # 3. Fee hesapla
        fee = fill_price * order.size * self.fee_rate(order.type)
        
        return FillResult(
            filled=True,
            fill_price=fill_price,
            fee=fee,
            slippage=abs(fill_price - bar.close) / bar.close,
        )
    
    def _calc_slippage(self, size, volume) -> float:
        """Hacme göre kayma: büyük emir + düşük hacim = çok kayma."""
        impact = (size / max(volume, 1)) * 0.1  # %10 impact factor
        return min(impact, 0.005)  # Max %0.5 kayma
```

#### `metrics.py` — Performans Metrikleri
```python
class MetricsCollector:
    """Tüm performans metriklerini hesapla."""
    
    def generate_report(self) -> BacktestReport:
        return BacktestReport(
            # Temel Metrikler
            total_return_pct=self._total_return(),
            annualized_return_pct=self._annualized_return(),
            max_drawdown_pct=self._max_drawdown(),
            
            # Risk Metrikleri
            sharpe_ratio=self._sharpe(),          # Hedef: > 1.5
            sortino_ratio=self._sortino(),        # Hedef: > 2.0
            calmar_ratio=self._calmar(),          # Return / MaxDD
            
            # Trade Metrikleri
            total_trades=len(self.trades),
            win_rate=self._win_rate(),             # Hedef: > 55%
            profit_factor=self._profit_factor(),   # Hedef: > 1.5
            avg_win_loss_ratio=self._avg_rr(),     # Hedef: > 1.3
            avg_trade_duration_hours=self._avg_duration(),
            
            # Maliyet Metrikleri
            total_fees=sum(t.fee for t in self.trades),
            total_slippage=sum(t.slippage for t in self.trades),
            fee_drag_pct=self._fee_drag(),        # Fee'lerin getiriye etkisi
            
            # Aylık Dağılım
            monthly_returns=self._monthly_returns(),  # Dict[str, float]
            
            # Equity Curve (grafik için)
            equity_curve=self.equity_history,
        )
```

#### `walk_forward.py` — Rolling Window Validasyon
```python
class WalkForwardAnalyzer:
    """12 aylık rolling window backtest."""
    
    def __init__(self, train_months=6, test_months=1, step_months=1):
        self.train_months = train_months   # 6 ay eğitim
        self.test_months = test_months     # 1 ay test (görülmemiş)
        self.step_months = step_months     # 1 ay kaydır
    
    def analyze(self, strategy_factory, data) -> WalkForwardReport:
        """Her pencerede: eğit → test → sonuçları kaydet."""
        results = []
        for window in self._generate_windows(data):
            # 1. Eğitim periyodunda parametreleri optimize et
            best_params = self._optimize(strategy_factory, window.train_data)
            # 2. Test periyodunda görülmemiş veriyle test et
            strategy = strategy_factory(best_params)
            result = BacktestEngine(self.config).run(strategy, window.test_data)
            results.append(result)
        
        return WalkForwardReport(
            windows=results,
            avg_return=mean([r.total_return_pct for r in results]),
            avg_sharpe=mean([r.sharpe_ratio for r in results]),
            stability=self._stability_score(results),  # Tutarlılık
            overfitting_score=self._detect_overfit(results),
        )
```

### 0.3 Kabul Kriterleri
- [ ] Fee + slippage dahil gerçekçi backtest
- [ ] 12 aylık walk-forward tek komutla çalışır
- [ ] HTML rapor: equity curve grafik + aylık tablo + trade loglari
- [ ] Sharpe, Sortino, Calmar, Profit Factor hesaplanır
- [ ] Overfit tespiti (train vs test farkı)

---

<a id="faz-1"></a>
## FAZ 1: GERÇEK ZAMANLI İSTİHBARAT SİSTEMİ

**Süre:** 3 hafta  
**Öncelik:** 🔴 KRİTİK  
**Neden:** Dış dünya bilgisi olmadan sinyal kalitesi eksik kalır.

### 1.1 Mimari

```
┌─────────────────────────────────────────────────────────────┐
│              ARGUS INTELLIGENCE LAYER                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Whale Alert  │  │ Insider/     │  │ Macro News       │  │
│  │ Tracker      │  │ Institutional│  │ Aggregator       │  │
│  │              │  │ Flow Tracker │  │                  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │             │
│         └─────────────────┼────────────────────┘             │
│                           │                                  │
│                  ┌────────▼─────────┐                        │
│                  │  Intelligence    │                        │
│                  │  Fusion Engine   │                        │
│                  │  (skorlama +     │                        │
│                  │   önceliklendirme│                        │
│                  └────────┬─────────┘                        │
│                           │                                  │
│                  ┌────────▼─────────┐                        │
│                  │  Signal Quality  │  mevcut SQF'ye        │
│                  │  Filter'a feed   │  ek faktör olarak     │
│                  └──────────────────┘  enjekte edilir        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Modüller

#### 1.2.1 Whale Alert Tracker
```
Dosya: src/intel/whale_tracker.py

Veri Kaynakları:
  - whale-alert.io API (ücretsiz tier: 10 req/dk)
  - Blockchain.com büyük transfer API'si
  - Etherscan/BSCScan whale wallet takibi

Takip Edilecekler:
  - Exchange'e gelen büyük transferler (>$1M) → SATIŞ baskısı
  - Exchange'den çıkan büyük transferler → ALIM baskısı
  - Stablecoin mint/burn olayları → Piyasa likidite değişimi
  - Bilinen whale cüzdanlarının hareketleri

Sinyal Üretimi:
  whale_signal = {
      "direction": "bearish" | "bullish" | "neutral",
      "magnitude": 0.0-1.0,      # Transfer büyüklüğüne göre
      "urgency": "LOW"|"HIGH",    # Zamana göre (son 1 saat = HIGH)
      "asset": "BTC"|"ETH"|...,
      "detail": "500 BTC moved to Binance from unknown wallet",
  }

Entegrasyon:
  - Signal Quality Filter'a whale_signal eklenir
  - magnitude > 0.7 ve direction == sinyal yönünün tersi → confidence -0.15
  - magnitude > 0.7 ve direction == sinyal yönü → confidence +0.10
```

#### 1.2.2 Insider / Institutional Flow Tracker
```
Dosya: src/intel/insider_tracker.py

Veri Kaynakları:
  - SEC EDGAR API (ücretsiz) — Form 4 insider işlemleri
  - Finviz insider trading sayfası (scraping)
  - OpenInsider.com (scraping)
  - CoinGecko developer activity metrics

Takip Edilecekler:
  HISSE İÇİN:
    - CEO/CFO alım/satım işlemleri
    - 10%+ hissedar değişiklikleri
    - Cluster buying (birden fazla insider aynı anda alıyor)
    - Unusual options activity (büyük call/put alımları)
  
  KRİPTO İÇİN:
    - Büyük OTC masası hareketleri
    - Grayscale/BlackRock ETF fund flow
    - Exchange reserve değişimleri
    - Smart money wallet tracking (Nansen benzeri)

Sinyal Üretimi:
  insider_signal = {
      "asset": "AAPL" | "BTCUSDT",
      "signal_type": "insider_buy"|"insider_sell"|"institutional_flow",
      "actors": ["CEO John Smith"],
      "total_value_usd": 500000,
      "confidence": 0.0-1.0,
      "time_horizon": "short"|"medium"|"long",
  }
```

#### 1.2.3 Macro News Aggregator
```
Dosya: src/intel/news_aggregator.py

Veri Kaynakları:
  - NewsAPI.org (ücretsiz: 100 req/gün)
  - CryptoPanic API (ücretsiz tier)
  - Twitter/X API (anahtar hesaplar)
  - Reddit API (r/cryptocurrency, r/wallstreetbets)
  - FED/ECB/TCMB takvimi (statik JSON)

İşleme Pipeline:
  1. Ham haber çek (her 5 dakika)
  2. LLM ile özetle ve skorla (local Ollama veya API)
     Prompt: "Bu haberin [varlık] üzerindeki etkisi: -10..+10 ve güven: 0-1"
  3. Duplicate/spam filtrele
  4. Sonuçları önbelleğe al (SQLite)
  5. Hermes engine'e feed et

Önemli Olaylar (Otomatik Tetikleyiciler):
  - FED faiz kararı → TÜM pozisyon boyutunu %50 küçült
  - CPI/NFP verisi → 30 dk öncesinden trade durdur
  - Exchange hack haberi → Anında tüm pozisyonları kapat
  - Regulatory haber (yasaklama vs) → İlgili varlıkta trade durdur
```

#### 1.2.4 Intelligence Fusion Engine
```
Dosya: src/intel/fusion.py

Tüm istihbarat kaynaklarını birleştirir:

class IntelligenceFusion:
    def compute_intel_score(self, symbol) -> IntelScore:
        whale = self.whale_tracker.get_signal(symbol)
        insider = self.insider_tracker.get_signal(symbol)
        news = self.news_aggregator.get_sentiment(symbol)
        
        # Ağırlıklı birleştirme
        score = (
            whale.magnitude * 0.30 * whale.direction_mult +
            insider.confidence * 0.25 * insider.direction_mult +
            news.sentiment * 0.25 +
            macro_calendar.impact * 0.20
        )
        
        return IntelScore(
            composite=clamp(score, -1.0, 1.0),
            should_trade=abs(score) < 0.7,  # Çok güçlü sinyal → dikkat
            risk_adjustment=1.0 + score * 0.2,  # -0.2 .. +0.2 adj
        )
```

### 1.3 Kabul Kriterleri
- [ ] Whale alert takibi çalışıyor (en az 1 kaynak)
- [ ] Haber sentiment skoru üretiliyor
- [ ] Signal Quality Filter'a entegre
- [ ] FED/makro takvim tetikleyicileri aktif
- [ ] Tüm veriler SQLite'a loglanıyor

---

<a id="faz-2"></a>
## FAZ 2: BingX MULTİ-ASSET GENİŞLEME

**Süre:** 2 hafta  
**Öncelik:** 🟡 YÜKSEK  
**Neden:** BingX'te hisse + kripto + emtia → daha fazla fırsat, daha az korelasyon.

### 2.1 BingX Desteklenen Varlıklar

```
KRİPTO (mevcut):
  Perpetual Futures: BTC, ETH, SOL, DOGE, AVAX, LINK, ARB, MATIC
  Kaldıraç: 1x-150x (biz max 3x kullanacağız)
  Fee: Maker %0.02, Taker %0.05

HİSSE (YENİ — Copy Trading / CFD):
  US Hisseleri: AAPL, TSLA, NVDA, MSFT, AMZN, GOOGL, META, AMD
  Kaldıraç: 1x-20x (biz max 2x)
  Fee: %0.05 + spread
  
  NOT: BingX'te gerçek hisse değil CFD (Contract for Difference)
  Avantaj: 7/24 trade edilebilir bazıları, düşük minimum
  Dezavantaj: Spread geniş olabilir, overnight fee var

EMTİA (YENİ):
  XAU/USD (Altın), XAG/USD (Gümüş), CRUDE OIL
  Kaldıraç: 1x-100x (biz max 2x)

İNDEKS (YENİ):
  NAS100, SPX500, US30
```

### 2.2 Multi-Asset Adapter Yapısı

```
src/adapters/
├── __init__.py
├── base.py              # AbstractExchangeAdapter
├── bingx/
│   ├── __init__.py
│   ├── client.py        # REST + WebSocket client
│   ├── crypto_adapter.py    # Kripto futures
│   ├── stock_adapter.py     # Hisse CFD
│   └── commodity_adapter.py # Emtia CFD
├── data_normalizer.py   # Tüm adapter'lardan gelen veriyi MarketSnapshot'a çevir
└── fee_models.py        # Varlık bazlı fee modeli

class AbstractExchangeAdapter(Protocol):
    async def fetch_ohlcv(symbol, timeframe, limit) -> list[Candle]
    async def fetch_orderbook(symbol, depth) -> OrderBook
    async def place_order(order: Order) -> OrderResult
    async def cancel_order(order_id: str) -> bool
    async def get_positions() -> list[Position]
    async def get_balance() -> Balance
    async def subscribe_ticker(symbol, callback) -> None
```

### 2.3 Varlık Korelasyon Matrisi

```
Hedef: Korelasyonu düşük varlıklar aynı anda trade et.

          BTC    ETH    AAPL   NVDA   XAU    NAS100
BTC       1.00   0.85   0.30   0.25   0.05   0.35
ETH       0.85   1.00   0.25   0.20   0.03   0.30
AAPL      0.30   0.25   1.00   0.70   0.10   0.85
NVDA      0.25   0.20   0.70   1.00   0.05   0.80
XAU       0.05   0.03   0.10   0.05   1.00   -0.20
NAS100    0.35   0.30   0.85   0.80   -0.20  1.00

Kural: Korelasyonu > 0.6 olan varlıklarda aynı yönde aynı anda
       MAX 1 pozisyon. İkincisi yarı boyutta.
```

### 2.4 Kabul Kriterleri
- [ ] BingX REST + WS client çalışıyor
- [ ] En az 3 varlık sınıfında veri çekiliyor
- [ ] Korelasyon kontrol aktif
- [ ] Her varlık sınıfı için fee modeli doğru

---

<a id="faz-3"></a>
## FAZ 3: ŞİRKET RADAR SİSTEMİ

**Süre:** 3 hafta  
**Öncelik:** 🟡 YÜKSEK  
**Neden:** Düşük değerli ama potansiyeli yüksek şirketleri bul → kısa vadede pozisyon al.

### 3.1 Mimari

```
┌─────────────────────────────────────────────────────────┐
│              ARGUS RADAR SYSTEM                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐    │
│  │ Fundamental│  │ Technical  │  │ Sentiment      │    │
│  │ Scanner    │  │ Scanner    │  │ Scanner        │    │
│  └─────┬──────┘  └─────┬──────┘  └───────┬────────┘    │
│        └───────────────┼──────────────────┘              │
│                        │                                 │
│               ┌────────▼────────┐                        │
│               │ Composite       │                        │
│               │ Opportunity     │                        │
│               │ Scorer          │                        │
│               └────────┬────────┘                        │
│                        │                                 │
│               ┌────────▼────────┐                        │
│               │ Watchlist       │  Top 10-20 fırsat      │
│               │ Generator      │  günlük güncellenir     │
│               └─────────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Fundamental Scanner
```
Dosya: src/radar/fundamental.py

Veri Kaynakları:
  - Financial Modeling Prep API (ücretsiz: 250 req/gün)
  - Yahoo Finance API (yfinance kütüphanesi)
  - EDGAR (SEC filings)

Tarama Kriterleri:
  class FundamentalFilter:
      pe_ratio_max: float = 15.0       # Ucuz P/E
      pe_ratio_min: float = 3.0        # Çok düşük = tehlike
      ps_ratio_max: float = 3.0        # Ucuz P/S
      revenue_growth_min: float = 0.10  # >%10 gelir büyümesi
      debt_equity_max: float = 1.5     # Düşük borç
      market_cap_min: float = 500e6    # >$500M (küçük ama tehlikeli değil)
      market_cap_max: float = 50e9     # <$50B (büyük olanlar yavaş hareket eder)
      insider_buying_last_90d: bool = True  # İçeriden alım pozitif sinyal
      
  Skor (0-100):
      pe_score    = 25 * (1 - pe/pe_max)        # Düşük PE = yüksek skor
      growth_score = 25 * min(revenue_growth/0.5, 1.0)
      insider_score = 25 * insider_buy_ratio
      value_score  = 25 * (1 - ps/ps_max)
```

### 3.3 Technical Scanner
```
Dosya: src/radar/technical.py

Tarama (günlük çerçeve):
  - 52-hafta düşük yakınında (%10 içinde) → geri dönüş potansiyeli
  - RSI(14) < 30 → aşırı satım
  - Volume spike > 3x ortalama → ilgi çekiyor
  - Golden cross yaklaşıyor (EMA50 yaklaşıyor EMA200'e)
  - MACD histogram pozitife dönüyor
  
Skor (0-100):
  distance_from_52wk_low * 30 +
  rsi_oversold_score * 25 +
  volume_confirmation * 25 +
  trend_reversal_signals * 20
```

### 3.4 Sentiment Scanner
```
Dosya: src/radar/sentiment.py

Kaynaklar:
  - Reddit r/wallstreetbets, r/stocks trending
  - Twitter/X finans hesapları mention sayısı
  - Analyst upgrade/downgrade (Finviz)
  - Insider buying clusters

Skor (0-100):
  social_buzz * 20 +
  analyst_consensus * 30 +
  insider_cluster * 30 +
  momentum_shift * 20
```

### 3.5 Çıktı: Günlük Radar Raporu
```
Her gün 06:00 UTC'de güncellenir:

ARGUS RADAR — 2026-02-14
═══════════════════════════════════════════
Rank | Sembol | Skor | Fundamental | Technical | Sentiment | Aksiyon
  1  | PLTR   |  87  |     82      |    90     |    88     | STRONG BUY
  2  | SOFI   |  81  |     78      |    85     |    80     | BUY
  3  | RKLB   |  76  |     70      |    82     |    75     | WATCH
  ...
  
Toplam taranan: 2,500+ hisse
Filtre sonrası: 15-20 aday
Top 5 otomatik watchlist'e eklenir
```

### 3.6 Kabul Kriterleri
- [ ] 2500+ hisse taranıyor (S&P500 + NASDAQ + small-cap)
- [ ] 3 faktörlü composite skor üretiliyor
- [ ] Günlük watchlist otomatik üretiliyor
- [ ] Top adaylar BingX'te varsa otomatik trade'e açılıyor
- [ ] Tüm tarama sonuçları loglanıyor

---

<a id="faz-4"></a>
## FAZ 4: OTONOM STRATEJİ FABRİKASI

**Süre:** 4 hafta  
**Öncelik:** 🔴 KRİTİK — Sistemin kendi kendini geliştirmesi için temel  
**Neden:** İnsan müdahalesi olmadan yeni stratejiler üretmeli ve test etmeli.

### 4.1 Mimari

```
┌──────────────────────────────────────────────────────────────┐
│             OTONOM STRATEJİ FABRİKASI                         │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────┐    ┌────────────┐    ┌──────────────────┐    │
│  │ Factor     │───▶│ Strategy   │───▶│ Auto Backtest    │    │
│  │ Discovery  │    │ Generator  │    │ & Validation     │    │
│  │ (alpha     │    │ (kombine   │    │ (walk-forward    │    │
│  │  arama)    │    │  et)       │    │  + out-of-sample)│    │
│  └────────────┘    └────────────┘    └────────┬─────────┘    │
│                                               │               │
│                                      ┌────────▼─────────┐    │
│                                      │ Promotion Gate   │    │
│                                      │ (canlıya terfi   │    │
│                                      │  kriterleri)     │    │
│                                      └────────┬─────────┘    │
│                                               │               │
│                              ┌────────────────▼──────┐       │
│                              │ LIVE / PAPER           │       │
│                              │ (canlı veya kağıt     │       │
│                              │  üzerinde çalıştır)   │       │
│                              └───────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Factor Discovery Engine
```
Dosya: src/factory/factor_discovery.py

Amaç: Yüzlerce teknik/fundamental faktörü tarayarak
       "alpha" üreten kombinasyonları otomatik bul.

class FactorDiscovery:
    """Otomatik alpha keşfi."""
    
    # Test edilecek faktör havuzu (100+)
    FACTOR_POOL = [
        # Teknik
        "rsi_14", "rsi_7", "rsi_21",
        "bb_pct_b_20_2", "bb_pct_b_20_3",
        "adx_14", "adx_7",
        "ema_cross_5_21", "ema_cross_21_55",
        "volume_ratio_5", "volume_ratio_20",
        "macd_signal", "macd_histogram",
        "obv_slope", "cmf_20",
        "atr_ratio_5_20",
        "vwap_deviation",
        "orderbook_imbalance",
        "funding_rate_zscore",
        "open_interest_change",
        # ... 80+ daha
        
        # Fundamental (hisse için)
        "pe_ratio_zscore", "ps_ratio_zscore",
        "revenue_growth_qoq", "earnings_surprise",
        "insider_buy_ratio",
        
        # Sentiment
        "news_sentiment_score",
        "social_buzz_zscore",
        "whale_flow_direction",
    ]
    
    def discover(self, data, target="next_1h_return"):
        """Her faktörün Information Coefficient'ini hesapla."""
        results = []
        for factor in self.FACTOR_POOL:
            ic = self._compute_ic(data[factor], data[target])
            turnover = self._compute_turnover(data[factor])
            results.append(FactorResult(
                name=factor,
                ic=ic,                    # Korelasyon gücü
                ic_ir=ic / ic_std,        # IC Information Ratio
                turnover=turnover,        # Ne sıklıkla sinyal değişiyor
                profitable=(ic > 0.03),   # IC > 0.03 = alpha var
            ))
        
        # En iyi faktörleri seç
        return sorted(results, key=lambda x: x.ic_ir, reverse=True)[:20]
```

### 4.3 Strategy Generator
```
Dosya: src/factory/strategy_generator.py

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
        
        # 2. 2'li kombinasyonlar (top 10'dan)
        for f1, f2 in combinations(top_factors[:10], 2):
            # Korelasyonu düşük olanları kombine et
            if abs(correlation(f1, f2)) < 0.5:
                strategies.append(DualFactorStrategy(f1, f2))
        
        # 3. ML-tabanlı (ensemble)
        if len(top_factors) >= 5:
            strategies.append(MLEnsembleStrategy(
                factors=top_factors[:15],
                model_type="lightgbm",  # Hızlı + GPU desteği
            ))
        
        return strategies
```

### 4.4 Auto Backtest & Validation
```
Dosya: src/factory/auto_validator.py

class AutoValidator:
    """Üretilen stratejileri otomatik test et ve rapor üret."""
    
    PROMOTION_CRITERIA = {
        "min_sharpe": 1.5,
        "min_profit_factor": 1.3,
        "max_drawdown": 0.10,     # Max %10 DD
        "min_trades": 50,          # Yeterli trade sayısı
        "min_win_rate": 0.45,      # En az %45
        "walk_forward_stable": True,  # Tüm pencerelerde kârlı
        "overfit_score_max": 0.3,    # Düşük overfit
    }
    
    def validate(self, strategy) -> ValidationResult:
        # 1. Tam veri backtest
        full_result = self.backtest_engine.run(strategy, full_data)
        
        # 2. Walk-forward (6 ay eğitim, 1 ay test, 12 pencere)
        wf_result = self.walk_forward.analyze(strategy, full_data)
        
        # 3. Monte Carlo simülasyon (trade sırasını karıştır)
        mc_result = self._monte_carlo(strategy, n_simulations=1000)
        
        # 4. Overfit tespiti
        overfit = self._detect_overfit(full_result, wf_result)
        
        # 5. Terfi kararı
        promoted = all([
            full_result.sharpe >= self.PROMOTION_CRITERIA["min_sharpe"],
            full_result.max_drawdown <= self.PROMOTION_CRITERIA["max_drawdown"],
            full_result.profit_factor >= self.PROMOTION_CRITERIA["min_profit_factor"],
            wf_result.stability >= 0.6,
            overfit.score <= self.PROMOTION_CRITERIA["overfit_score_max"],
        ])
        
        return ValidationResult(
            strategy=strategy,
            promoted=promoted,
            deploy_to="paper" if promoted else "archive",
            report=self._generate_report(full_result, wf_result, mc_result),
        )
```

### 4.5 Promotion Pipeline
```
Keşif → Backtest → Walk-Forward → Monte Carlo → Paper (2 hafta) → Live

Her aşamada geçemeyen strateji → "archive" klasörüne
Paper'da 2 hafta başarılı → otomatik live'a terfi
Live'da 1 hafta başarısız → otomatik deaktive

Strateji Yaşam Döngüsü:
  DISCOVERED → BACKTESTED → VALIDATED → PAPER → LIVE → [RETIRED]
```

### 4.6 Kabul Kriterleri
- [ ] 100+ faktör taranıyor
- [ ] IC hesaplaması çalışıyor
- [ ] Strateji kombinasyonları otomatik üretiliyor
- [ ] Walk-forward + Monte Carlo validasyon
- [ ] Paper → Live terfi pipeline'ı aktif
- [ ] Tüm süreç insan müdahalesi olmadan çalışıyor

---

<a id="faz-5"></a>
## FAZ 5: KENDİNİ GELİŞTİREN SİSTEM (SELF-IMPROVING)

**Süre:** 4 hafta  
**Öncelik:** 🔴 KRİTİK — Asıl fark buradan gelir  
**Neden:** Sistem boşa çalışmasın, her döngüde daha iyi olsun.

### 5.1 Mimari

```
┌──────────────────────────────────────────────────────────────────┐
│           ARGUS SELF-IMPROVEMENT LOOP                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────────┐  │
│  │ Performance │────▶│ Diagnostic   │────▶│ Optimizer        │  │
│  │ Monitor     │     │ Engine       │     │ (parametre       │  │
│  │ (KPI takip) │     │ (neden       │     │  ayarlama)       │  │
│  └─────────────┘     │  kötü/iyi?)  │     └────────┬─────────┘  │
│                      └──────────────┘              │             │
│                                           ┌────────▼─────────┐  │
│                                           │ A/B Tester       │  │
│                                           │ (eski vs yeni    │  │
│                                           │  paper'da karş.) │  │
│                                           └────────┬─────────┘  │
│                                                    │             │
│                                           ┌────────▼─────────┐  │
│                                           │ Auto Deploy      │  │
│                                           │ (kazanan versiyon │  │
│                                           │  live'a geçer)   │  │
│                                           └──────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ HAFTALIK EVOLUTION CYCLE (Her Pazar 00:00 UTC)             │  │
│  │                                                            │  │
│  │ 1. Son 7 günün trade'lerini analiz et                      │  │
│  │ 2. Kaybeden stratejileri teşhis et (neden kaybetti?)       │  │
│  │ 3. Parametreleri micro-adjust et (bounded: max ±10%)       │  │
│  │ 4. Yeni faktörler tara → yeni strateji adayları üret       │  │
│  │ 5. Walk-forward ile doğrula                                 │  │
│  │ 6. A/B test başlat (eski vs yeni, paper'da)                │  │
│  │ 7. 1 hafta sonra kazananı seç → live'a terfi               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Performance Monitor
```
Dosya: src/evolution/performance_monitor.py

class PerformanceMonitor:
    """7/24 KPI takibi ve alert sistemi."""
    
    # Anlık Takip
    kpi_dashboard = {
        "equity": float,          # Anlık equity
        "daily_pnl": float,       # Günlük kar/zarar
        "weekly_pnl": float,      # Haftalık kar/zarar
        "monthly_pnl": float,     # Aylık kar/zarar
        "current_drawdown": float, # Anlık drawdown
        "sharpe_rolling_30d": float,
        "win_rate_7d": float,
        "trades_today": int,
        "active_positions": int,
    }
    
    # Alarm Durumları
    ALERTS = {
        "EQUITY_NEW_HIGH": "🎉 Yeni ATH!",
        "DRAWDOWN_WARNING": "⚠️ DD > %5",
        "DRAWDOWN_CRITICAL": "🚨 DD > %8 — trade duraklatıldı",
        "STRATEGY_DEGRADED": "📉 Strateji X son 20 trade'de negatif",
        "EDGE_LOST": "❌ Strateji X'in edge'i kayboldu (Sharpe < 0.5)",
    }
```

### 5.3 Diagnostic Engine
```
Dosya: src/evolution/diagnostics.py

class DiagnosticEngine:
    """Neden kaybettik? Neden kazandık? Analiz et."""
    
    def diagnose(self, trades: list[TradeRecord]) -> Diagnosis:
        return Diagnosis(
            # Ne zaman kaybediyoruz?
            losing_regimes=self._losing_by_regime(trades),
            losing_hours=self._losing_by_hour(trades),
            losing_symbols=self._losing_by_symbol(trades),
            
            # Hangi parametreler sorunlu?
            sl_too_tight=self._check_sl_hit_rate(trades),  # SL çok sık mı vuruluyor?
            tp_too_far=self._check_tp_hit_rate(trades),    # TP'ye hiç ulaşılmıyor mu?
            entry_timing=self._check_entry_timing(trades),  # Erken mi giriyoruz?
            
            # Piyasa değişti mi?
            regime_shift=self._detect_regime_shift(),
            volatility_change=self._detect_vol_change(),
            
            # Öneriler
            recommendations=[
                "SL mesafesini %15 artır (son 50 trade'de %68'i SL'ye takıldı)",
                "RANGING rejimde Nautilus'u deaktive et (son 30 günde -$45)",
                "Gece 02:00-06:00 UTC arası trade'i durdur (en kötü saatler)",
            ],
        )
```

### 5.4 Bounded Auto-Optimizer
```
Dosya: src/evolution/optimizer.py

class BoundedOptimizer:
    """Parametreleri güvenli sınırlar içinde otomatik ayarla.
    
    KURAL: Hiçbir parametre tek seferde %10'dan fazla değişemez.
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
    
    def optimize_step(self, diagnosis: Diagnosis) -> list[ParamChange]:
        """Teşhise göre parametreleri micro-ayarla."""
        changes = []
        
        for rec in diagnosis.recommendations:
            if "SL mesafesi" in rec:
                current = self.get_param("risk.sl_atr_mult")
                new_val = min(current * 1.10, 3.0)  # Max %10 artış
                changes.append(ParamChange("risk.sl_atr_mult", current, new_val))
        
        return changes
```

### 5.5 A/B Testing Framework
```
Dosya: src/evolution/ab_tester.py

class ABTester:
    """Eski parametre seti vs yeni parametre seti karşılaştır."""
    
    def start_test(self, variant_a_config, variant_b_config, duration_days=7):
        """İki config'i aynı anda paper trade olarak çalıştır."""
        # A: Mevcut (kontrol grubu)
        # B: Optimize edilmiş (deney grubu)
        
        # 7 gün sonra:
        # - Hangisinin Sharpe'ı daha yüksek?
        # - Hangisinin DD'si daha düşük?
        # - Hangisinin profit factor'u daha iyi?
        # → Kazanan config live'a terfi eder
```

### 5.6 Kabul Kriterleri
- [ ] Haftalık evolution cycle otomatik çalışıyor
- [ ] Teşhis raporu üretiliyor (neden kaybettik)
- [ ] Parametreler bounded olarak otomatik ayarlanıyor
- [ ] A/B test framework'ü çalışıyor
- [ ] Kazanan config otomatik deploy ediliyor

---

<a id="faz-6"></a>
## FAZ 6: 7/24 OTONOM OPERASYON

**Süre:** 3 hafta  
**Öncelik:** 🔴 KRİTİK  
**Neden:** Sistem uyurken de para kazanmalı.

### 6.1 Sistem Mimarisi

```
┌──────────────────────────────────────────────────────────────┐
│                  ARGUS 7/24 DAEMON                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐     │
│  │ Scheduler  │  │ Watchdog   │  │ Health Monitor     │     │
│  │ (cron +    │  │ (crash     │  │ (heartbeat +       │     │
│  │  interval) │  │  recovery) │  │  metrics endpoint) │     │
│  └─────┬──────┘  └─────┬──────┘  └────────┬───────────┘     │
│        └───────────────┼──────────────────┘                   │
│                        │                                      │
│               ┌────────▼────────┐                             │
│               │ Main Loop       │                             │
│               │                 │                             │
│               │ her 1 dk:       │                             │
│               │  1. Veri çek    │                             │
│               │  2. Sinyal üret │                             │
│               │  3. Pozisyon    │                             │
│               │     kontrol     │                             │
│               │  4. Risk kontrol│                             │
│               │  5. Telemetri   │                             │
│               └─────────────────┘                             │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ZAMANLANMIŞ GÖREVLER                                   │  │
│  │                                                        │  │
│  │ Her 1 dakika:  Sinyal tarama + pozisyon güncelleme     │  │
│  │ Her 5 dakika:  Orderbook snapshot + whale kontrol      │  │
│  │ Her 15 dakika: Scalp sinyal tarama (Hydra)             │  │
│  │ Her 1 saat:    Ana sinyal döngüsü (tüm motorlar)      │  │
│  │ Her 4 saat:    Rejim yeniden sınıflandırma             │  │
│  │ Her gün 06:00: Radar tarama + günlük rapor             │  │
│  │ Her Pazar:     Evolution cycle (parametre optimizasyon) │  │
│  │ Her ay 1.:     Aylık performans raporu + deposit        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ CRASH RECOVERY                                         │  │
│  │                                                        │  │
│  │ 1. Watchdog süreci ana süreç'i izler                   │  │
│  │ 2. Çökme tespit → 10 sn bekle → yeniden başlat         │  │
│  │ 3. Yeniden başlatılınca:                                │  │
│  │    a. Mevcut pozisyonları exchange'den oku              │  │
│  │    b. SL emirlerinin hala aktif olduğunu kontrol et     │  │
│  │    c. Eksik SL varsa hemen koy                          │  │
│  │    d. Normal döngüye devam et                           │  │
│  │ 4. 3 art arda çökme → HALT + Telegram bildirimi        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ BİLDİRİM SİSTEMİ (Telegram Bot)                       │  │
│  │                                                        │  │
│  │ Mesajlar:                                               │  │
│  │ 📈 "LONG BTC @ $45,230 | Conf: 0.82 | Engine: Titan"  │  │
│  │ 📉 "CLOSED ETH | +2.3% | Duration: 4.5h"              │  │
│  │ 🎉 "Günlük rapor: +$12.50 (+1.8%) | 5W/2L"            │  │
│  │ ⚠️ "DD %6.2 — pozisyon boyutu azaltıldı"              │  │
│  │ 🚨 "HALT — 3 art arda çökme — müdahale gerekli"       │  │
│  │                                                        │  │
│  │ Komutlar (Telegram'dan kontrol):                        │  │
│  │ /status    — anlık durum                                │  │
│  │ /positions — açık pozisyonlar                           │  │
│  │ /pnl       — günlük/haftalık/aylık PnL                 │  │
│  │ /halt      — trade'i durdur                             │  │
│  │ /resume    — trade'e devam et                           │  │
│  │ /close_all — tüm pozisyonları kapat                    │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Dosya Yapısı
```
src/daemon/
├── __init__.py
├── main_loop.py        # Ana 7/24 döngü
├── scheduler.py        # Zamanlanmış görevler
├── watchdog.py         # Crash recovery + otomatik yeniden başlatma
├── health.py           # HTTP health endpoint (/health)
├── telegram_bot.py     # Bildirim + komut sistemi
└── state_manager.py    # Pozisyon + durum kalıcılığı (SQLite)
```

### 6.3 Kabul Kriterleri
- [ ] Sistem 7 gün kesintisiz çalışıyor
- [ ] Crash sonrası otomatik recovery
- [ ] Telegram bildirimleri çalışıyor
- [ ] Tüm zamanlanmış görevler doğru zamanda çalışıyor
- [ ] Pozisyon durumu kalıcı (yeniden başlatmada kaybolmaz)

---

## ZAMAN ÇİZELGESİ

```
Şubat 2026 (Kalan):
  Hafta 3: Faz 0 — Backtest motoru temel
  Hafta 4: Faz 0 tamamla + Faz 1 başla

Mart 2026:
  Hafta 1-2: Faz 1 — İstihbarat (whale + haber)
  Hafta 3: Faz 1 tamamla + Faz 2 başla (BingX multi-asset)
  Hafta 4: Faz 2 tamamla

Nisan 2026:
  Hafta 1-2: Faz 3 — Radar sistemi
  Hafta 3-4: Faz 4 — Strateji fabrikası (başla)

Mayıs 2026:
  Hafta 1-2: Faz 4 tamamla
  Hafta 3-4: Faz 5 — Self-improvement loop

Haziran 2026:
  Hafta 1-2: Faz 5 tamamla
  Hafta 3-4: Faz 6 — 7/24 daemon + Telegram
  
Temmuz 2026:
  Full otonom çalışma başlar
  $100 başlangıç + 5 ay deposit = $600 başlangıç sermayesi
```

---

## RİSK VE GÜVENLİK KURALLARI (TÜM FAZLAR İÇİN)

```
1. ASLA %1.5'ten fazla tek trade riski alma
2. ASLA günlük %3'ten fazla kaybet
3. ASLA %10'dan fazla drawdown'a izin ver
4. Her pozisyonda EXCHANGE-SIDE STOP LOSS zorunlu
5. Her parametre değişikliği max ±%10
6. Her yeni strateji 2 hafta paper → sonra live
7. 3 art arda çökme → TÜM trade DURDUR
8. FED/CPI gibi olaylarda 30 dk önceden trade durdur
9. Tüm trade'ler, kararlar, metrikler loglanır — silme YOK
10. Günde 1 kez otomatik SQLite yedekleme
```
