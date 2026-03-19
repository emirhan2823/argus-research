# Argus Terminal

iOS için gelişmiş hisse senedi analiz ve karar destek sistemi.

![Swift](https://img.shields.io/badge/Swift-5.9-orange)
![iOS](https://img.shields.io/badge/iOS-17.0+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 🎯 Özellikler

### Analiz Modülleri

- **Orion** - Teknik Analiz (RSI, MACD, SMA, Yapı, Pattern)
- **Atlas** - Temel Analiz (PE, ROE, Margin, Değerleme)
- **Aether** - Makroekonomik Analiz (FRED verileri, VIX, DXY)
- **Hermes** - Haber & Sentiment Analizi
- **Athena** - Smart Beta & Faktör Analizi
- **Demeter** - Sektör Rotasyonu
- **Chiron** - Öğrenme & Risk Yönetimi

### Sistemler

- **Argus Grand Council** - Tüm modüllerin oylama ile karar vermesi
- **Phoenix** - Destek/Direnç bazlı strateji
- **AutoPilot** - Otomatik pozisyon yönetimi (simülasyon)
- **Backtest** - Geçmiş performans testi

## 🚀 Kurulum

### 1. Projeyi Clone Et

```bash
git clone https://github.com/KULLANICI_ADI/argus-terminal.git
cd argus-terminal
```

### 2. API Key'leri Ayarla

```bash
# Örnek dosyayı kopyala
cp Algo-Trading/Services/Secrets.swift.example Algo-Trading/Services/Secrets.swift

# Secrets.swift dosyasını aç ve API key'lerini gir
```

### 3. API Key'leri Al (Ücretsiz)

| Servis | Link | Zorunlu |
|--------|------|---------|
| FRED | <https://fred.stlouisfed.org/docs/api/api_key.html> | ✅ Evet |
| FMP | <https://financialmodelingprep.com/developer> | ✅ Evet |
| Groq | <https://console.groq.com> | ❌ Opsiyonel |
| Gemini | <https://aistudio.google.com/apikey> | ❌ Opsiyonel |

### 4. Xcode'da Aç ve Çalıştır

```bash
open Algo-Trading.xcodeproj
# Cmd+R ile çalıştır
```

## Paper Soak Operations

Bu bölüm Year-2 paper soak çalıştırması için core infra scriptlerini açıklar.

### Start

```bash
Scripts/soak_start.sh council
```

Farklı strateji örneği:

```bash
Scripts/soak_start.sh tophunter_short_v1 --interval 1h
```

### Monitor

```bash
Scripts/soak_status.sh
```

Bu komut:
- PID durumunu gösterir
- `heartbeat.json` zaman damgasını ve yaşını gösterir
- `daemon.log` son satırlarını tail eder

### Stop

```bash
Scripts/soak_stop.sh
```

Bu komut:
- daemon PID'yi graceful şekilde durdurur
- gerekirse force kill uygular
- `daemon.pid` dosyasını temizler

### Quick Smoke

```bash
Scripts/soak_smoke.sh council
```

Bu komut hızlıca `start -> wait -> status -> stop` akışını çalıştırır.

### JSON Status Reader

```bash
venv/bin/python Scripts/status_reader.py --run-dir runs/year2/paper_main
```

### launchd Service (macOS)

```bash
Scripts/soak_service.sh install council
Scripts/soak_service.sh status
Scripts/soak_service.sh stop
```

### Windows 7/24 Node (PowerShell)

Kurulum:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_prepare.ps1
```

Paper soak start:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_start.ps1 -Strategy council
```

Durum:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_status.ps1
```

Stop:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_stop.ps1
```

Smoke:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_smoke.ps1 -Strategy council
```

Dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_dashboard_start.ps1 -RunDir runs/year2/paper_main -Host 127.0.0.1 -Port 18081
powershell -ExecutionPolicy Bypass -File Scripts\win_dashboard_status.ps1
powershell -ExecutionPolicy Bypass -File Scripts\win_dashboard_stop.ps1
```

Boot'ta otomatik baslatma (Task Scheduler):

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_task.ps1 -Action install -Strategy council -RunDir runs/year2/paper_main
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_task.ps1 -Action status
```

### Log ve Runtime Konumu

- Run dizini: `runs/year2/paper_main`
- PID dosyası: `runs/year2/paper_main/daemon.pid`
- Daemon log: `runs/year2/paper_main/daemon.log`
- Daemon err log (Windows): `runs/year2/paper_main/daemon.err.log`
- Service log: `runs/year2/paper_main/service.log`
- Heartbeat: `runs/year2/paper_main/heartbeat.json`
- Metrics: `runs/year2/paper_main/metrics.json`

### Koruma Notu

`Scripts/soak_start.sh`, `Scripts/soak_status.sh`, `Scripts/soak_stop.sh`, `Scripts/soak_smoke.sh`, `Scripts/soak_service.sh`, `Scripts/win_soak_start.ps1`, `Scripts/win_soak_status.ps1`, `Scripts/win_soak_stop.ps1`, `Scripts/win_soak_smoke.ps1` dosyalari **ARGUS CORE INFRA** kapsamindadir ve gelecekteki cleanup/refactor calismalarinda korunmalidir.

## 📱 Ekran Görüntüleri

*Yakında eklenecek*

## ⚠️ Yasal Uyarı

**Bu uygulama YATIRIM TAVSİYESİ DEĞİLDİR.**

- Eğitim ve araştırma amaçlıdır
- Alım-satım kararlarınızdan siz sorumlusunuz
- Kayıplarınızdan siz sorumlusunuz
- Profesyonel danışmanlık almanız önerilir
- Kaybetmeyi göze alamayacağınız parayla işlem yapmayın

## 📄 Lisans

MIT License - Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## 🤝 Katkıda Bulunma

Pull request'ler kabul edilir. Büyük değişiklikler için önce issue açın.

---

**Not:** Bu proje aktif geliştirme aşamasındadır. API değişiklikleri olabilir.
