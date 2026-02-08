# ARGUS KULLANIM KILAVUZU (TR)

Bu dokuman, Argus projesini yeni devralan birinin sistemi calistirmasi, raporlamasi ve operasyonel olarak takip etmesi icin hazirlandi.

## Amac ve Kapsam
- Bu kilavuzun amaci: sistemi "calisan operasyon" seviyesinde kullanabilmeni saglamak.
- Kapsam:
  - Backtest/validation
  - Audit/raporlama
  - ML model egitimi
  - Telegram bot operasyonu
  - Run klasoru uzerinden durum takibi
- Kapsam disi:
  - Strateji matematigi derin teori
  - Prod deployment altyapisi (docker/k8s vb.)

## Hizli Baslangic (5-10 dk)

### 1) Proje kokune gec
```bash
cd "/Users/emirhan/deneme2 kopyası/argus-terminal"
```

### 2) Temel saglik kontrolu
```bash
pytest tests/unit/test_exchanges.py tests/unit/test_ml_model.py tests/unit/test_compliance.py tests/unit/test_telegram_bot.py -q
```
Beklenen: tum testlerin gecmesi (`passed`).

### 3) Hangi run klasorunu izleyecegini sec
Ornek aktif run klasoru:
- `runs/phase19_twin/STRICT`

Hizli kontrol:
```bash
ls -la runs/phase19_twin/STRICT
```

### 4) Son durumu oku
```bash
cat runs/phase19_twin/STRICT/heartbeat.json
cat runs/phase19_twin/STRICT/daemon_state.json
```

### 5) Haftalik audit cikar
```bash
python3 Scripts/weekly_audit.py runs/phase19_twin/SOFT/ --week 2026-W06
```

## Gunluk Operasyon Akisi

### A) Durum kontrolu
- `heartbeat.json`: anlik durum (equity, risk seviyesi, son bar)
- `daemon_state.json`: daemon state snapshot

Komutlar:
```bash
cat runs/phase19_twin/STRICT/heartbeat.json
cat runs/phase19_twin/STRICT/daemon_state.json
```

### B) Audit
```bash
python3 Scripts/weekly_audit.py runs/phase19_twin/SOFT/ --week 2026-W06
```

### C) Backtest / validation
```bash
python3 Scripts/sprint1_walkforward_12m.py --symbol BTCUSDT --start_date 2024-02-01 --end_date 2025-02-01 --train_months 3 --test_months 1 --step_months 1 --skip_invalid
python3 Scripts/verify_determinism.py --runs 2 --seed 42
```

### D) Raporlama / vergi raporu
```bash
python3 Scripts/generate_tax_report.py runs/20260203_215219_56c032/trades.csv --year 2024 --output runs/20260203_215219_56c032/tax_report_2024.csv --statement-json runs/20260203_215219_56c032/tax_report_2024_summary.json
```

### E) ML model egitimi
```bash
python3 Scripts/train_ml_model.py --input runs/training_data.csv --output models/signal_model.lgb
```

## Ana Moduller ve Ne Ise Yarar

### `argus_py/models/*`
- Sinyal motorlari: `orion`, `aether`, `hermes`, `phoenix`, `chiron`, `aegean`
- Gorev: piyasa/duygu/regime analizleri ve oy/score uretimi

### `argus_py/council/*`
- Farkli motor oylarini agirliklandirip tek karar uretir
- Veto ve agirlik tabanli karar yapisi burada

### `argus_py/risk/*`
- Kill-switch, sizing, mode/state/risk kurallari
- Kritik koruma katmani: zarar limitleri ve trade bloklama

### `argus_py/broker/*`
- `paper.py`: paper trading
- `live.py`: live bridge ve safety guardrails
- `realism.py`: fee/slippage/funding gercekciligi

### `argus_py/portfolio/*`
- Multi-symbol pozisyon yonetimi
- Bucket exposure, cash reserve, limit ve ranking

### `argus_py/ml/*`
- ML sinyal modeli (`signal_model.py`)
- Feature extraction (`feature_eng.py`)

### `argus_py/reporting/*`
- Audit pipeline, compliance, run report ve diagnostics
- Haftalik audit + vergi raporu burada

### `argus_py/bot/*`
- Telegram bot komutlari ve kontrol akisi
- Yetkili user kontrolu + status/report/trade komutlari

## Onemli Scriptler ve Kullanim Senaryolari

### 1) `Scripts/sprint1_walkforward_12m.py`
- Senaryo: rolling walk-forward validation

### 2) `Scripts/verify_determinism.py`
- Senaryo: ayni seed ile ayni sonuc geliyor mu kontrolu

### 3) `Scripts/weekly_audit.py`
- Senaryo: reject, conversion, gate etkisi haftalik raporu

### 4) `Scripts/train_ml_model.py`
- Senaryo: training CSV'den sinyal modelini egitme

### 5) `Scripts/generate_tax_report.py`
- Senaryo: trades.csv'den 8949 uyumlu tax lot + period statement

### 6) `Scripts/run_telegram_bot.py`
- Senaryo: Telegram'dan status/report/trade kontrolu

### 7) `Scripts/telegram_local_command_test.py`
- Senaryo: Telegram API'ye cikmadan komut smoke-test

Ornek:
```bash
python3 Scripts/telegram_local_command_test.py --run-dir runs/phase19_twin/STRICT --user-id 1
```

## Run Klasoru Anatomisi

Standart dosyalar:
- `trades.csv`: islem loglari
- `decisions.csv`: karar loglari
- `rejects.csv`: reject nedenleri
- `heartbeat.json`: canli durum snapshot
- `daemon_state.json`: daemon state

Hizli kontrol:
```bash
ls -la runs/phase19_twin/STRICT
head -n 20 runs/phase19_twin/STRICT/trades.csv
head -n 20 runs/phase19_twin/STRICT/decisions.csv
head -n 20 runs/phase19_twin/STRICT/rejects.csv
```

## Telegram Bot Kullanimi

### Komutlar
- `/status`: equity, drawdown, kill-switch, open positions
- `/trades`: son 5 islem
- `/killswitch soft|hard|off`: kill-switch kontrolu
- `/report`: gunluk/haftalik net, gross, WR, symbol kirilimi
- `/balance`: balance/equity

### Calistirma
```bash
python3 Scripts/run_telegram_bot.py --token "<TOKEN>" --run-dir runs/phase19_twin/STRICT --allowed-user <TELEGRAM_USER_ID>
```

### Guvenlik modeli
- Bot sadece `--allowed-user` listesinde olan user ID'lerden komut kabul eder.
- Bu liste disindaki istekler cevaplanmaz.

### Bu ortamdaki ag/DNS notu
- Bu workspace'te bazi denemelerde `api.telegram.org` DNS/network erisimi engelliydi.
- Bu durumda local smoke-test scripti ile komut akisini dogrulayip, canli polling'i ag acik bir ortamda calistir.

## Risk Notu (Planlanan Guncelleme)

- Mevcut davranis: gunluk max zarar esigine ulasilinca yeni trade acilisi bloklanir.
- Planlanan iyilestirme (small-live oncesi):
  - Risk seviyesi `SOFT` iken sadece secici trade acilsin.
  - Sadece yuksek conviction setup'lara izin verilsin (score/esik yukseltilmis).
  - Pozisyon boyutu normalin `%25-%40` araligina cekilsin.
  - Islem aralarina cooldown uygulansin.
- Amac: koruma katmanini bozmadan "firsat kacirma" etkisini azaltmak.

## Sik Hatalar ve Cozum

### 1) `python-telegram-bot is not installed`
- Cozum: bagimliligi ortamda kur veya vendored path kullan.
- Bu repoda `.vendor/` altinda paket vendored olarak tutulabilir.

### 2) `telegram.error.NetworkError / httpx.ConnectError`
- Neden: Telegram API DNS/Network cikisi yok.
- Cozum: ag erisimi acik ortamda botu calistir.

### 3) `No data` / `training_data.csv bulunamadi`
- Neden: run veya dataset dosyasi eksik.
- Cozum: dogru input path ver ve run klasoru varligini kontrol et.

### 4) CSV parse uyumsuzlugu
- Neden: beklenen kolon adlari farkli.
- Cozum: scriptlerin bekledigi kolon setlerini (`timestamp/symbol/price/qty/...`) koru.

## Onerilen Ilk 7 Gun Plani

### Gun 1
- Repo ve test ortamini ayaga kaldir
- Temel test paketini calistir

### Gun 2
- `runs/phase19_twin/STRICT` ve `SOFT` klasorlerini oku
- heartbeat/decision/trade/reject akislarini anla

### Gun 3
- `weekly_audit.py` ile audit raporu cikar
- Ana reject sebeplerini not et

### Gun 4
- `verify_determinism.py` calistir
- Sonuc hash'lerini karsilastir

### Gun 5
- `sprint1_walkforward_12m.py` ile kisa walk-forward smoke denemesi yap

### Gun 6
- `train_ml_model.py` ile model egitimi dry-run yap
- `generate_tax_report.py` ile compliance ciktilarini uret

### Gun 7
- `telegram_local_command_test.py` ile bot komutlarini smoke-test et
- Ag acik ortamda `run_telegram_bot.py` canli baslatma denemesi yap

## Hedeflenen Operasyon Sonucu
- Her gun en az bir health-check + bir audit gorunumu alinmis olmasi
- Haftalik olarak determinism + walk-forward + compliance raporunun uretilebilmesi
- Risk/kill-switch durumunun heartbeat uzerinden surekli izlenebilmesi
