# PROMPT 1: PROJE KURULUM

## Açıklama

Bu prompt ile Xcode projesi oluşturulur, API anahtarları yapılandırılır ve temel dosya yapısı kurulur.

---

## PROMPT

```
Bana iOS SwiftUI uygulaması oluştur. Uygulama adı "Argus Terminal" olsun.

## Proje Yapısı

/Argus-Terminal
├── /Models
│   └── (veri modelleri)
├── /Views
│   ├── /Components
│   └── (ekranlar)
├── /ViewModels
│   └── TradingViewModel.swift
├── /Services
│   ├── Secrets.swift
│   └── (API servisleri)
└── /Resources
    └── Assets.xcassets

## Secrets.swift Dosyası

API anahtarlarını güvenli saklamak için bu dosyayı oluştur:

```swift
import Foundation

struct Secrets {
    // FRED API - Makroekonomik veriler için
    // https://fred.stlouisfed.org/docs/api/api_key.html adresinden ücretsiz al
    static let fredAPIKey = "BURAYA_FRED_API_KEY_YAPISTIR"
    
    // FMP API - Finansal veriler için  
    // https://site.financialmodelingprep.com/ adresinden ücretsiz al
    static let fmpAPIKey = "BURAYA_FMP_API_KEY_YAPISTIR"
    
    // Groq API - AI analizi için (opsiyonel)
    // https://console.groq.com/ adresinden ücretsiz al
    static let groqAPIKey = "BURAYA_GROQ_API_KEY_YAPISTIR"
}
```

## Info.plist Ayarları

App Transport Security için HTTP izni ekle:

- NSAppTransportSecurity > NSAllowsArbitraryLoads = YES

## Minimum Gereksinimler

- iOS Deployment Target: 17.0
- Swift: 5.9+
- Xcode: 15.0+

## İlk ViewModel

TradingViewModel.swift oluştur:

```swift
import SwiftUI
import Combine

@MainActor
class TradingViewModel: ObservableObject {
    static let shared = TradingViewModel()
    
    // Watchlist
    @Published var watchlist: [String] = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
    
    // Fiyat verileri
    @Published var quotes: [String: Quote] = [:]
    @Published var candles: [String: [Candle]] = [:]
    
    // Yükleme durumları
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private init() {}
}

// Temel modeller
struct Quote: Codable {
    let symbol: String
    let currentPrice: Double
    let change: Double?
    let changePercent: Double?
    var dp: Double? { changePercent }
}

struct Candle: Codable, Identifiable {
    var id: Date { date }
    let date: Date
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double?
}
```

Bu temel yapıyı oluştur ve build'in çalıştığını doğrula.

```

---

## Beklenen Çıktı
- Boş Xcode projesi
- Secrets.swift (API key placeholder'ları ile)
- TradingViewModel.swift
- Temel Quote ve Candle modelleri
