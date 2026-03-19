# ARGUS - Sonraki Adimlar ve Iyilestirme Plani

**Tarih:** 2026-02-18  
**Durum:** Phases A-K tamamlandi, production hardening bitti, paper daemon hazir.

---

## 1) MEVCUT SISTEM DURUMU

### Neler Calisiyor
- 6 engine (Titan, Nautilus, Phoenix, Hermes, Hydra, Gemini) tamamen kodlandi
- 11 adimli pipeline: veri -> rejim -> sinyal -> kalite -> whale boost -> precision -> gates -> sizing -> execution
- Dynamic exit FSM (3 asamali partial TP + trailing SL)
- Validated sizing (leverage derived, breakeven-R gate)
- Hyper-precision execution (OBI-based limit entry, snipe partial exit)
- 21 tablo SQLite telemetri veritabani
- 800+ test (hepsi geciyor)

### Kritik Eksikler (Henuz Production-Ready Degil)
1. **Gercek exchange client yok** - `DemoBroker` mock dolduruyor, BingX API entegrasyonu gerekli
2. **Gercek veri akisi yok** - Evolve modunda parquet, normal modda mock random walk
3. **Learning pipeline baglantisiz** - Darwin ve Reflector var ama otomatik trigger edilmiyor
4. **Hermes LLM baglanmamis** - v2 engine sadece rule-based, Ollama kullanilmiyor

---

## 2) DOGRULUGU ARTTIRMAK ICIN YAPILACAKLAR

### 2.1 - Gercek Veri Entegrasyonu (EN KRITIK)

**Problem:** Sistem su an sentetik random walk verisi uzerinde calisiyor. Hicbir sinyal gercek piyasa kosuluyla test edilmemis.

**Cozum:**
```
Oncelik: YUKSEK
Efor: 2-3 gun

a) BingX REST API client yaz (public klines endpoint - API key gerektirmez)
   - GET /openApi/swap/v2/quote/klines
   - 1m, 5m, 15m, 1h barlar
   - DataFactory.exchange_client olarak wire et

b) Websocket baglantisi (ileri asama)
   - Orderbook imbalance (OBI) icin realtime gerekiyor
   - Funding rate icin 8 saatlik endpoint yeterli

c) Alternatif: Binance public API (zaten legacy daemon'da kullaniliyor)
   - api.binance.com/api/v3/klines (API key gereksiz)
   - Daha hizli, daha guvenilir
```

### 2.2 - Walk-Forward Backtesting ile Parametre Validasyonu

**Problem:** Engine parametreleri (ADX threshold, RSI overbought/oversold, BB period) hardcoded. Optimize edilmemis.

**Cozum:**
```
Oncelik: YUKSEK
Efor: 1-2 gun

a) 6 aylik BTC/ETH 1m veri indir (Binance'den ucretsiz)
b) Walk-forward backtest calistir:
   - Train window: 30 gun, test window: 7 gun, roll: 7 gun
   - Her engine icin Sharpe, max DD, win rate olc
c) Mevcut parametreleri sonuclara gore ayarla
d) src/backtest/lab/walk_forward.py zaten var - kullanilabilir durumda
```

### 2.3 - Rejim Siniflandirma Iyilestirmesi

**Problem:** RuleBasedRegimeClassifier tek classifier. ADX + Hurst + EMA kullaniyor. Gercek piyasada regime gecisleri daha karisik.

**Cozum:**
```
Oncelik: ORTA
Efor: 2-3 gun

a) ML regime classifier ekle (LightGBM zaten import edilmis)
   - Feature: ADX, Hurst, ATR ratio, volume, EMA spread, BTC dominance
   - Label: retrospektif rejim (trend/range/volatile/crisis)
   - 3 ay veri ile train et

b) Consensus votingda agirlik ayarla:
   - rule_based: 0.4, ml: 0.4, hermes: 0.2
   - Su an hepsi esit (4 ayni vote)
```

### 2.4 - Hermes Sentiment (8B Model Entegrasyonu)

**Problem:** v2 Hermes engine sadece `hermes_sentiment_score` threshold kontrolu yapiyor. Gercek haber analizi yok.

**Cozum (Ollama ile):**
```
Oncelik: ORTA
Efor: 1-2 gun

a) Ollama zaten config'de tanimli:
   ollama_url: "http://127.0.0.1:11434/api/generate"
   ollama_model: "llama3.1:8b"

b) HermesEngine.generate_signal() icine RSS fetch + LLM analiz ekle:
   - CoinDesk, CoinTelegraph, TheBlock RSS feed'lerini cek
   - Her headline'i Ollama'ya gonder:
     "Rate this crypto headline sentiment -100 to +100: {headline}"
   - Ortalama sentiment'i pipeline'a besle

c) Ollama baslatmak icin:
   ollama pull llama3.1:8b
   ollama serve
```

### 2.5 - Darwin Otomatik Evolution

**Problem:** Darwin (GA) ve Reflector tamamen yazilmis ama hic cagirilmiyor.

**Cozum:**
```
Oncelik: ORTA-YUKSEK
Efor: 1 gun

a) Paper daemon'a entegre et:
   - Her cycle'da: eger trade kapandiysa -> Reflector.reflect() cagir
   - Her 1000 cycle'da: Darwin.full_evolve() cagir
   - Reflector 5+ ayni failure mode tespit ederse: Darwin.micro_evolve()

b) Genome ciktisini engine parametrelerine map et:
   - adx_threshold -> Titan/Nautilus max_adx
   - rsi_oversold -> Nautilus bb_reversion rsi_oversold
   - sl_mult -> validated_sizer parametreleri
```

---

## 3) 8B MODEL (llama3.1:8b) RAPORLARI ANLAR MI?

### Kisa Cevap: EVET, ama sinirli.

### Detayli Analiz:

**Ne anlar:**
- Basit JSON/CSV rapor ozetlerini (win rate, Sharpe, max DD)
- "Bu trade neden kaybetti?" gibi yapilandirilmis sorulari
- Rejim siniflama ("bu piyasa trending mi ranging mi?")
- Sentiment analizi (haber basliklarindan duygu cikarma)
- Basit pattern recognition ("RSI 30 altinda + OBI pozitif = long sinyal")

**Ne ANLAMAZ / Zayif oldugu yerler:**
- Karmasik zaman serisi analizi (cointegration, OU process, half-life)
- Coklu degiskenli korelasyon matrisi yorumlama
- Neden-sonuc iliskisi (correlation != causation)
- Kendi kendine strateji olusturma (hallucination riski)
- Buyuk sayilarla matematik (Decimal precision gereken hesaplar)

### Onerilen Kullanim Modeli:

```
8B modeli SU amaclarla kullan:
1. Haber sentiment analizi (CoinDesk/CoinTelegraph basliklari)
2. Trade post-mortem ozeti ("Bu trade neden kaybetti?")
3. Gunluk rapor ozeti (dogal dil)
4. Alert mesaj formatlama (Telegram icin)

8B modeli SU amaclarla KULLANMA:
1. Strateji karari (long/short/skip)
2. Parametre optimizasyonu
3. Risk hesaplama
4. Execution kararlari
```

### Rapor Formati (8B Modelin Anlamasi Icin):

```json
{
  "report_type": "daily_summary",
  "date": "2026-02-18",
  "metrics": {
    "total_trades": 12,
    "wins": 8,
    "losses": 4,
    "win_rate": 0.667,
    "total_pnl_pct": 1.23,
    "max_drawdown_pct": 0.45,
    "sharpe_ratio": 2.1
  },
  "regime_distribution": {
    "TRENDING": 6,
    "RANGING": 4,
    "VOLATILE": 2
  },
  "top_failure_mode": "sl_too_tight",
  "question": "Summarize today's trading performance and suggest one improvement."
}
```

Bu format 8B model tarafindan rahatca anlasilir ve anlamli bir ozet uretebilir.

---

## 4) SISTEM PERFORMANSINI OLCMEK ICIN METRIKLER

### Temel KPI'lar
| Metrik | Hedef | Olcum Yeri |
|--------|-------|------------|
| Win Rate | > 55% | trades tablosu |
| Profit Factor | > 1.5 | PnL / Loss |
| Max Drawdown | < 5% | equity curve |
| Sharpe Ratio | > 1.5 | returns serisi |
| Avg R-Multiple | > 0.5R | dynamic_exit_log |
| Fee Drag / Gross PnL | < 20% | validated_sizing_log |
| Signal Quality (SQS) | > 0.65 avg | sqs_log |
| Precision Filter Pass Rate | > 60% | pipeline logs |
| Regime Accuracy | > 70% | retrospektif analiz |

### Rapor Toplanma Noktalari
1. **SQLite v2.5 DB** (`runs/v25/argus_v25.db`) - 21 tablo
2. **Daemon metrics** (`runs/paper_v2/metrics.json`) - cycle-level
3. **Decisions JSONL** (`runs/paper_v2/decisions.jsonl`) - her karar
4. **Reflector DB** (`runs/argus_reflections.db`) - failure analizi
5. **Darwin state** (`runs/darwin/darwin_state.json`) - genome evolution

---

## 5) ONCELIK SIRALI EYLEM PLANI

### Hafta 1: Veri + Paper Trading
```
1. [x] Paper daemon scripti olustur (DONE)
2. [x] start_paper.bat / start_paper.sh (DONE)
3. [ ] Binance public API client yaz (klines endpoint)
4. [ ] DataFactory'ye wire et
5. [ ] Paper daemon'u calistir, 24 saat veri topla
6. [ ] Ilk gunluk raporu incele
```

### Hafta 2: Backtest + Parametre Tuning
```
7. [ ] 3 ay BTC/ETH/SOL 1m kline veri indir
8. [ ] Walk-forward backtest calistir (her engine icin)
9. [ ] Parametreleri optimize et (ADX, RSI, BB thresholds)
10. [ ] Optimize edilmis parametrelerle paper trading tekrar baslat
```

### Hafta 3: Learning Pipeline
```
11. [ ] Reflector'u paper daemon'a entegre et
12. [ ] Darwin micro-evolution'i failure mode trigger'a bagla
13. [ ] Haftalik full evolution schedule kur
14. [ ] Ollama + Hermes sentiment entegrasyonu
```

### Hafta 4: Gercek Exchange Entegrasyonu
```
15. [ ] BingX API client (authenticated - trade icin)
16. [ ] Paper trading -> BingX testnet
17. [ ] Position reconciliation (lokal vs exchange)
18. [ ] SL placement verification (GR-8 enforcement)
```

---

## 6) RISK UYARILARI

### Gercek Para ile Baslamadan ONCE Yapilmasi GEREKEN Seyler
1. **En az 1000 paper trade** tamamlanmali (istatistiksel anlamlilik)
2. **Walk-forward backtest** her engine icin pozitif Sharpe gostermeli
3. **Max drawdown < 8%** paper'da kanitlanmali
4. **Fee drag hesabi** gercek BingX fee'leriyle dogrulanmali
5. **Kill switch** test edilmeli (DD 3% -> 4% -> 8% escalation)
6. **Reconciliation** calisir durumda olmali (lokal state = exchange state)
7. **SL placement** her pozisyonda exchange-side dogrulanmali

### Asla Yapilmamasi Gerekenler
- Optimize edilmis parametrelerle hemen live'a gecme (overfitting riski)
- 8B modele strateji karari birakmak (hallucination)
- Leverage'i artirmak (derived, never input - GR-11)
- Test etmeden fee modelini degistirmek
- Kill switch seviyelerini gevsetmek

---

## 7) MEVCUT DURUMDA START ETMEK ICIN

```bash
# Windows:
start_paper.bat

# Linux/macOS:
chmod +x start_paper.sh
./start_paper.sh
```

### Ne Olacak:
1. Pipeline her 60 saniyede calisacak
2. **GERCEK Binance Futures verisi** ile sinyal uretecek (otomatik bagli!)
3. `DemoBroker` mock fill verecek (paper mode)
4. Her karar `runs/paper_v2/decisions.jsonl`'ye yazilacak
5. Heartbeat `runs/paper_v2/heartbeat.json`'da gorunecek
6. v2.5 telemetri `runs/v25/argus_v25.db`'ye yazilacak

### Veri Kaynagi Secimi (.env):
```bash
# Binance (default - API key gerektirmez):
ARGUS_DATA_SOURCE=binance

# BingX (API key gerekli):
ARGUS_DATA_SOURCE=bingx
BINGX_API_KEY=your_key_here
BINGX_API_SECRET=your_secret_here
```

### Backtest Verisi Indirmek:
```bash
# 90 gun BTC,ETH,SOL 1h veri:
python Scripts/download_data.py --days 90 --timeframe 1h

# 180 gun tum semboller + haberler:
python Scripts/download_data.py --days 180 --news

# Ozel semboller:
python Scripts/download_data.py --symbols BTCUSDT,ETHUSDT --days 30 --timeframe 1m
```

---

## 8) AI-HEDGE-FUND REPOSU ANALIZI (virattt/ai-hedge-fund)

**Repo:** https://github.com/virattt/ai-hedge-fund (45.8k star)

### Mimari Karsilastirma

| Ozellik | ai-hedge-fund | ARGUS |
|---------|---------------|-------|
| Yaklasim | Multi-agent LLM (GPT-4o) | Rule-based + ML + GA evolution |
| Karar verici | 12+ AI agent voting | 6 engine + regime router |
| Risk yonetimi | LLM-based risk agent | Matematik-tabanli (validated sizer, breakeven-R) |
| Veri kaynagi | Financial Datasets API (equity) | Binance/BingX API (crypto futures) |
| Execution | Simulated only | DemoBroker (paper) + BingX (future live) |
| Backtesting | Var (basit) | Walk-forward + stress test + fee drag validation |
| Self-learning | Yok | Darwin GA + Reflector (post-trade analysis) |
| Sentiment | LLM-based sentiment agent | Hermes (rule-based + optional Ollama) |
| Ollama support | Evet (--ollama flag) | Config'de tanimli, henuz aktif degil |

### ARGUS'a Uyarlanabilecek Ozellikler

**1. Multi-Agent Voting Sistemi (YUKSEK ONCELIK)**
ai-hedge-fund'un en guclu ozelligi: 12 farkli yatirim "kisiligine" sahip agent
her biri bagimsiz analiz yapiyor, sonra Portfolio Manager birlestiriyor.

ARGUS'a uyarlama:
- Bizim engine'ler (Titan, Nautilus, Gemini, etc.) zaten "agent" gibi calisiyor
- Eksik olan: her engine'in REASONING (gerekce) vermesi
- Eklenmesi gereken: her engine ciktisina `reasoning: str` alani ekle
- RegimeRouter'da voting mekanizmasi zaten var (best confidence wins)
- Gelistirme: confidence yerine weighted vote + reasoning log

**2. Sentiment Agent (ORTA ONCELIK)**
ai-hedge-fund Sentiment Agent'i news + social media analizi yapiyor.

ARGUS'a uyarlama:
- Hermes zaten sentiment engine ama sadece rule-based
- Ollama (llama3.1:8b) ile haber analizi eklenebilir
- ai-hedge-fund'un prompt template'i referans olarak kullanilabilir
- Crypto-specific RSS feed'ler zaten config'de tanimli

**3. Valuation Agent - Intrinsic Value (DUSUK ONCELIK - Equity icin)**
ai-hedge-fund DCF, owner earnings, residual income hesapliyor.

ARGUS'a uyarlama:
- Crypto icin "intrinsic value" kavram olarak zayif
- Ama on-chain metriklere (NVT ratio, MVRV, active addresses) uyarlanabilir
- Ileri asama, su an oncelik degil

**4. Web UI (ORTA ONCELIK)**
ai-hedge-fund Next.js web arayuzu var (React + TypeScript).

ARGUS'a uyarlama:
- Flask zaten dependency'de var
- Dashboard icin basit bir web UI yazilabilir
- heartbeat.json + metrics.json + decisions.jsonl goruntuleme
- Ama su an terminal monitoring yeterli, ileri asama

**5. Fundamentals Agent (DUSUK ONCELIK)**
Financial statements, ratios, insider trading analizi.

ARGUS'a uyarlama:
- Crypto icin "financials" yok
- Ama token economics (circulating supply, unlock schedule, treasury) eklenebilir
- CoinGecko API veya DeFiLlama kullanilabilir
- Ileri asama

### Sonuc: Oncelikli Uyarlamalar
1. **Engine reasoning logging** - Her engine kararinin gerekceini kaydet (hemen yapilabilir)
2. **Ollama sentiment integration** - Hermes'e LLM-tabanli haber analizi ekle
3. **Weighted voting** - RegimeRouter'da confidence + reasoning bazli agirlikli oylama
4. **Web dashboard** - Monitoring icin basit Flask UI (ileri asama)
