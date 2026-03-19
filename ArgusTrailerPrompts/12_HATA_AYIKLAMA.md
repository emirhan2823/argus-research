# PROMPT 12: HATA AYIKLAMA REHBERİ

## Açıklama

Sık karşılaşılan hatalar ve çözümleri.

---

## PROMPT

```
Argus Terminal geliştirirken karşılaşılan yaygın hataları ve çözümlerini öğren.

## 1. API Key Hataları

### Problem: "API key not found" veya boş veri
### Çözüm:

```swift
// Secrets.swift kontrolü
struct Secrets {
    static let fredAPIKey = "YOUR_ACTUAL_KEY"  // "BURAYA..." değil!
    static let fmpAPIKey = "YOUR_ACTUAL_KEY"
    static let groqAPIKey = "YOUR_ACTUAL_KEY"  // Opsiyonel
}

// API key doğrulama
func validateAPIKeys() {
    if Secrets.fredAPIKey.contains("BURAYA") || Secrets.fredAPIKey.isEmpty {
        print("⚠️ FRED API key eksik! https://fred.stlouisfed.org/docs/api/api_key.html")
    }
    if Secrets.fmpAPIKey.contains("BURAYA") || Secrets.fmpAPIKey.isEmpty {
        print("⚠️ FMP API key eksik! https://financialmodelingprep.com/developer")
    }
}
```

## 2. JSON Decode Hataları

### Problem: "The data couldn't be read because it is missing"

### Çözüm

```swift
// YANLIŞ - Tüm alanlar zorunlu
struct Quote: Codable {
    let symbol: String
    let price: Double
    let change: Double      // Crash!
}

// DOĞRU - Optional kullan
struct Quote: Codable {
    let symbol: String
    let price: Double
    let change: Double?     // Güvenli
    let changePercent: Double?
}

// Debugging için raw response yazdır
func fetchData() async {
    let (data, _) = try await URLSession.shared.data(from: url)
    
    // Debug: Raw JSON'ı gör
    if let json = String(data: data, encoding: .utf8) {
        print("📦 Raw Response:\n\(json)")
    }
    
    let decoded = try JSONDecoder().decode(MyType.self, from: data)
}
```

## 3. MainActor Hataları

### Problem: "Publishing changes from background threads is not allowed"

### Çözüm

```swift
// YANLIŞ
func loadData() async {
    let result = await someAsyncCall()
    self.data = result  // ❌ Background thread!
}

// DOĞRU
func loadData() async {
    let result = await someAsyncCall()
    await MainActor.run {
        self.data = result  // ✅ Main thread
    }
}

// VEYA class seviyesinde
@MainActor
class TradingViewModel: ObservableObject {
    // Tüm updates otomatik main thread'de
}
```

## 4. Network Hataları

### Problem: "The request timed out" veya "Could not connect"

### Çözüm

```swift
// Timeout ayarla
func fetchWithTimeout(url: URL) async throws -> Data {
    var request = URLRequest(url: url)
    request.timeoutInterval = 15  // 15 saniye
    
    let (data, response) = try await URLSession.shared.data(for: request)
    
    guard let httpResponse = response as? HTTPURLResponse else {
        throw NetworkError.invalidResponse
    }
    
    switch httpResponse.statusCode {
    case 200...299:
        return data
    case 429:
        throw NetworkError.rateLimited
    case 401, 403:
        throw NetworkError.unauthorized
    default:
        throw NetworkError.serverError(httpResponse.statusCode)
    }
}

enum NetworkError: Error {
    case invalidResponse
    case rateLimited
    case unauthorized
    case serverError(Int)
}
```

## 5. SwiftUI Preview Hataları

### Problem: Preview çalışmıyor

### Çözüm

```swift
// Preview için mock data oluştur
#Preview {
    StockDetailView(
        symbol: "AAPL",
        viewModel: MockViewModel()
    )
}

class MockViewModel: TradingViewModel {
    override init() {
        super.init()
        // Mock data
        self.quotes["AAPL"] = Quote(
            symbol: "AAPL",
            currentPrice: 185.50,
            change: 2.30,
            changePercent: 1.25
        )
    }
}
```

## 6. Build Hataları

### Problem: "Cannot find type 'X' in scope"

### Çözüm

```swift
// 1. Import eksik olabilir
import Foundation
import SwiftUI
import Combine  // @Published için gerekli

// 2. Dosya Xcode projesine ekli olmayabilir
// Project Navigator'da dosyayı kontrol et
// Target Membership işaretli olmalı

// 3. Circular dependency olabilir
// A imports B, B imports A → Hata
// Çözüm: Ortak modeli ayrı dosyaya taşı
```

## 7. Görsel Sorunları

### Problem: UI düzgün görünmüyor

### Çözüm

```swift
// Dark mode zorunlu
.preferredColorScheme(.dark)

// Safe area dikkat
ZStack {
    Theme.background.ignoresSafeArea()  // Arka plan
    
    ScrollView {
        VStack {
            // Content - ignoresSafeArea OLMADAN
        }
        .padding()  // Padding ekle
    }
}

// Text truncation
Text(longText)
    .lineLimit(2)
    .truncationMode(.tail)

// Responsive layout
GeometryReader { geo in
    if geo.size.width < 400 {
        // Compact layout
    } else {
        // Regular layout
    }
}
```

## 8. Performans Sorunları

### Problem: Uygulama yavaş

### Çözüm

```swift
// 1. Paralel veri çekme
func loadAllData() async {
    await withTaskGroup(of: Void.self) { group in
        for symbol in watchlist {
            group.addTask {
                await self.loadQuote(for: symbol)
            }
        }
    }
}

// 2. Cache kullan
private var cache: [String: (data: Quote, timestamp: Date)] = [:]
private let cacheLifetime: TimeInterval = 60  // 1 dakika

func getCached(symbol: String) -> Quote? {
    guard let cached = cache[symbol],
          Date().timeIntervalSince(cached.timestamp) < cacheLifetime else {
        return nil
    }
    return cached.data
}

// 3. Debounce kullan
import Combine
private var searchCancellable: AnyCancellable?

func debounceSearch(_ text: String) {
    searchCancellable?.cancel()
    searchCancellable = Just(text)
        .delay(for: .milliseconds(300), scheduler: RunLoop.main)
        .sink { [weak self] query in
            self?.performSearch(query)
        }
}
```

## 9. Test ve Debug

```swift
// Debug mode check
#if DEBUG
print("🔍 Debug: \(someValue)")
#endif

// Conditional compilation
#if targetEnvironment(simulator)
// Simulator-specific code
#else
// Device-specific code
#endif

// Preview detect
extension ProcessInfo {
    static var isPreview: Bool {
        processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1"
    }
}
```
