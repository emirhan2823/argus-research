import Foundation

class AlphaVantageService {
    static let shared = AlphaVantageService()
    
    private let apiKey = Secrets.alphaVantageKey
    
    func fetchTreasury() async throws -> Double {
        // Stub implementation
        return 4.5
    }
}
