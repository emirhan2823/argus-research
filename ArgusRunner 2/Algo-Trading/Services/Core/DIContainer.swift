import Foundation
import SwiftUI
import Combine

// MARK: - Dependency Injection Container
// Singleton'ları merkezi bir noktadan yönetir ve test edilebilirlik sağlar.

@MainActor
final class DIContainer: ObservableObject {
    
    // MARK: - Singleton Instance
    static let shared = DIContainer()
    
    // MARK: - Configuration
    
    /// Trading configuration
    let config: TradingConfig
    
    // MARK: - Service References (Lazy Access to Singletons)
    // Not: Şimdilik mevcut singleton'lara erişim sağlıyoruz
    // İleriki fazlarda bu protokol-based injection'a dönüşecek
    
    var marketDataStore: MarketDataStore { MarketDataStore.shared }
    var orionService: OrionAnalysisService { OrionAnalysisService.shared }
    var macroService: MacroRegimeService { MacroRegimeService.shared }
    var notificationManager: NotificationManager { NotificationManager.shared }
    
    // MARK: - Initialization
    
    private init() {
        self.config = TradingConfig.default
    }
    
    /// Test initialization with custom config
    init(config: TradingConfig) {
        self.config = config
    }
    
    // MARK: - Factory Methods
    
    /// Production container
    static func createProduction() -> DIContainer {
        return DIContainer.shared
    }
    
    /// Mock container for testing
    static func createMock() -> DIContainer {
        // Mock config ile
        var mockConfig = TradingConfig.default
        mockConfig.maxPositionRisk = 0.02 // Test için daha yüksek limit
        return DIContainer(config: mockConfig)
    }
}

// MARK: - Service Error

enum ServiceError: Error, LocalizedError {
    case dataUnavailable(String)
    case networkError(String)
    case invalidInput(String)
    
    var errorDescription: String? {
        switch self {
        case .dataUnavailable(let resource):
            return "\(resource) verisi mevcut değil"
        case .networkError(let message):
            return "Ağ hatası: \(message)"
        case .invalidInput(let message):
            return "Geçersiz giriş: \(message)"
        }
    }
}
