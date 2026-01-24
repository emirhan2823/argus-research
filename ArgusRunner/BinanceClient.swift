import Foundation

enum BinanceError: Error {
    case badURL
    case http(Int)
    case decode(String)
}

final class BinanceClient {
    private let base = "https://api.binance.com"

    func fetchKlines(symbol: String, interval: String, limit: Int = 200) async throws -> [Candle] {
        var comps = URLComponents(string: base + "/api/v3/klines")
        comps?.queryItems = [
            .init(name: "symbol", value: symbol.uppercased()),
            .init(name: "interval", value: interval),
            .init(name: "limit", value: String(limit))
        ]
        guard let url = comps?.url else { throw BinanceError.badURL }

        let (data, resp) = try await URLSession.shared.data(from: url)
        guard let http = resp as? HTTPURLResponse else { throw BinanceError.http(-1) }
        guard (200..<300).contains(http.statusCode) else { throw BinanceError.http(http.statusCode) }

        // Binance klines: [[openTime, open, high, low, close, volume, closeTime, ...], ...]
        guard let raw = try JSONSerialization.jsonObject(with: data) as? [[Any]] else {
            throw BinanceError.decode("Not array-of-arrays")
        }

        var out: [Candle] = []
        out.reserveCapacity(raw.count)

        for row in raw where row.count >= 7 {
            guard
                let openTime = row[0] as? Int64,
                let openStr = row[1] as? String,
                let highStr = row[2] as? String,
                let lowStr  = row[3] as? String,
                let closeStr = row[4] as? String,
                let volStr = row[5] as? String,
                let closeTime = row[6] as? Int64,
                let open = Double(openStr),
                let high = Double(highStr),
                let low  = Double(lowStr),
                let close = Double(closeStr),
                let volume = Double(volStr)
            else { continue }

            out.append(Candle(
                openTime: openTime,
                closeTime: closeTime,
                open: open,
                high: high,
                low: low,
                close: close,
                volume: volume
            ))
        }
        return out
    }
}

func msToISO(_ ms: Int64) -> String {
    let sec = TimeInterval(ms) / 1000.0
    let d = Date(timeIntervalSince1970: sec)
    return ISO8601DateFormatter().string(from: d)
}
