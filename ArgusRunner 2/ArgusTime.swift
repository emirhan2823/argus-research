import Foundation

enum ArgusTime {

    static func msToISO(_ ms: Int64) -> String {
        let d = Date(timeIntervalSince1970: TimeInterval(ms) / 1000.0)
        return ISO8601DateFormatter().string(from: d)
    }

}
