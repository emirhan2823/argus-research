import SwiftUI
import Combine

// MARK: - API Key Store (Secure & Dynamic)
// Bu sınıf kullanıcı tarafından girilen veya Secrets dosyasından gelen key'leri yönetir.
// Git'e gönderildiğinde temizdir, hardcoded key içermez.

@MainActor
class APIKeyStore: ObservableObject {
    static let shared = APIKeyStore()
    
    // Published Keys (For UI binding)
    @Published var keys: [APIProvider: String] = [:]
    
    // UserDefaults Storage
    private let defaults = UserDefaults.standard
    
    private init() {
        loadKeys()
    }
    
    private func loadKeys() {
        // 1. Load from UserDefaults (User Input overrides everything)
        for provider in APIProvider.allCases {
            if let savedKey = defaults.string(forKey: "API_KEY_\(provider.rawValue)") {
                keys[provider] = savedKey
            } else {
                // 2. Fallback to Secrets.swift (Static Keys)
                switch provider {
                case .twelveData: keys[.twelveData] = Secrets.twelveDataKey
                case .fmp: keys[.fmp] = Secrets.fmpKey
                case .finnhub: keys[.finnhub] = Secrets.finnhubKey
                case .tiingo: keys[.tiingo] = Secrets.tiingoKey
                case .marketstack: keys[.marketstack] = Secrets.marketStackKey
                case .alphaVantage: keys[.alphaVantage] = Secrets.alphaVantageKey
                case .eodhd: keys[.eodhd] = Secrets.eodhdKey
                case .gemini: keys[.gemini] = Secrets.geminiKey
                case .fred: keys[.fred] = Secrets.fredKey
                case .simfin: keys[.simfin] = Secrets.simfinKey
                case .pinecone: keys[.pinecone] = Secrets.pineconeKey
                }
            }
        }
    }
    
    func getKey(for provider: APIProvider) -> String? {
        // Return key if valid (not placeholder)
        let key = keys[provider]
        if key == nil || key == "placeholder" || key?.starts(with: "YOUR_") == true {
            return nil
        }
        return key
    }
    
    nonisolated static func getDirectKey(for provider: APIProvider) -> String? {
        // Static access helper
        // Since we are MainActor, this is tricky. Ideally use shared instance generally.
        // For compatibility with legacy code calling from background:
        // We'll peek at UserDefaults directly.
        let udKey = UserDefaults.standard.string(forKey: "API_KEY_\(provider.rawValue)")
        if let udKey = udKey, !udKey.isEmpty { return udKey }
        
        // Fallback to Secrets
        let secret: String?
        switch provider {
        case .twelveData: secret = Secrets.twelveDataKey
        case .fmp: secret = Secrets.fmpKey
        case .finnhub: secret = Secrets.finnhubKey
        case .tiingo: secret = Secrets.tiingoKey
        case .marketstack: secret = Secrets.marketStackKey
        case .alphaVantage: secret = Secrets.alphaVantageKey
        case .eodhd: secret = Secrets.eodhdKey
        case .gemini: secret = Secrets.geminiKey
        case .fred: secret = Secrets.fredKey
        case .simfin: secret = Secrets.simfinKey
        case .pinecone: secret = Secrets.pineconeKey
        }
        
        if let secret = secret, !secret.isEmpty, !secret.starts(with: "YOUR_") {
            return secret
        }
        return nil
    }
    
    func setKey(provider: APIProvider, key: String) {
        keys[provider] = key
        defaults.set(key, forKey: "API_KEY_\(provider.rawValue)")
        NotificationCenter.default.post(name: .argusKeyStoreDidUpdate, object: nil)
    }
    
    func deleteKey(provider: APIProvider) {
        keys.removeValue(forKey: provider)
        defaults.removeObject(forKey: "API_KEY_\(provider.rawValue)")
        NotificationCenter.default.post(name: .argusKeyStoreDidUpdate, object: nil)
    }
}

extension NSNotification.Name {
    static let argusKeyStoreDidUpdate = NSNotification.Name("argusKeyStoreDidUpdate")
}




