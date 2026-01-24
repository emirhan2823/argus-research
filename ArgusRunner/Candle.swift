import Foundation

// Core Candle model used by Runner + CLI + CSV persistence.
// Keep this independent from UI (Algo-Trading/Models/Models.swift).
public struct Candle: Identifiable, Codable, Sendable, Equatable {
    public let id: Int64              // closeTimeMs (unique per candle)
    public let openTime: Int64
    public let closeTime: Int64

    public let open: Double
    public let high: Double
    public let low: Double
    public let close: Double
    public let volume: Double

    public init(
        openTime: Int64,
        closeTime: Int64,
        open: Double,
        high: Double,
        low: Double,
        close: Double,
        volume: Double
    ) {
        self.openTime = openTime
        self.closeTime = closeTime
        self.id = closeTime
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
    }
}
