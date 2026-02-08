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

### Log ve Runtime Konumu

- Run dizini: `runs/year2/paper_main`
- PID dosyası: `runs/year2/paper_main/daemon.pid`
- Daemon log: `runs/year2/paper_main/daemon.log`
- Heartbeat: `runs/year2/paper_main/heartbeat.json`

### Koruma Notu

`Scripts/soak_start.sh`, `Scripts/soak_status.sh`, `Scripts/soak_stop.sh` dosyaları **ARGUS CORE INFRA** kapsamındadır ve gelecekteki cleanup/refactor çalışmalarında korunmalıdır.

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
