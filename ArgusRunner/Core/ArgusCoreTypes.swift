import Foundation

// Minimal MVP Models to replace dependencies on huge Models.swift

public struct Candle: Codable, Identifiable, Equatable {
    public let id: UUID
    public let date: Date
    public let open: Double
    public let high: Double
    public let low: Double
    public let close: Double
    public let volume: Double
    
    public init(date: Date, open: Double, high: Double, low: Double, close: Double, volume: Double) {
        self.id = UUID()
        self.date = date
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
    }
}

// Support for legacy code if needed
public enum SignalAction: String, Codable {
    case buy = "BUY"
    case sell = "SELL"
    case hold = "HOLD"
}

public enum AutoPilotEngine: String, Codable {
    case pulse = "PULSE"
    case corse = "CORSE"
    case manual = "MANUAL"
}

public enum SetupQuality: String, Codable, Comparable {
    case skip = "SKIP"
    case ok = "OK"
    case good = "GOOD"
    case great = "GREAT"
    
    public static func < (lhs: SetupQuality, rhs: SetupQuality) -> Bool {
        let rank: (SetupQuality) -> Int = {
            switch $0 {
            case .skip: return 0
            case .ok: return 1
            case .good: return 2
            case .great: return 3
            }
        }
        return rank(lhs) < rank(rhs)
    }
}
