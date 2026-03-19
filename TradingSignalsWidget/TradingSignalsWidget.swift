import WidgetKit
import SwiftUI

// MARK: - Shared Models (Mirrored for Widget Target)

struct WidgetAetherData: Codable {
    let score: Double
    let regime: String
    let summary: String
    let lastUpdated: Date
    
    let spyChange: Double
    let vixValue: Double
    let gldChange: Double
    let btcChange: Double
}

struct WidgetPortfolioData: Codable {
    let totalEquity: Double
    let totalPnL: Double
    let dayPnLPercent: Double
    
    let isAutoPilotActive: Bool
    let autoPilotWinRate: Double
    
    let lastActionTitle: String?
    let topSignalTitle: String?
    
    let lastUpdated: Date
}

// MARK: - Provider

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> ArgusEntry {
        ArgusEntry(date: Date(), aether: .mock, portfolio: .mock)
    }

    func getSnapshot(in context: Context, completion: @escaping (ArgusEntry) -> ()) {
        let entry = ArgusEntry(date: Date(), aether: .mock, portfolio: .mock)
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<ArgusEntry>) -> ()) {
        // Fetch from UserDefaults (App Group)
        let suiteName = "group.com.argusterminal"
        let defaults = UserDefaults(suiteName: suiteName) ?? UserDefaults.standard
        
        var aether: WidgetAetherData?
        if let data = defaults.data(forKey: "widget_aether_data") {
            aether = try? JSONDecoder().decode(WidgetAetherData.self, from: data)
        }
        
        var portfolio: WidgetPortfolioData?
        if let data = defaults.data(forKey: "widget_portfolio_data") {
            portfolio = try? JSONDecoder().decode(WidgetPortfolioData.self, from: data)
        }
        
        // If nil, use mock/empty state
        let entry = ArgusEntry(
            date: Date(),
            aether: aether ?? .empty,
            portfolio: portfolio ?? .empty
        )

        // Reload every 15 mins
        let nextUpdateDate = Calendar.current.date(byAdding: .minute, value: 15, to: Date())!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdateDate))
        completion(timeline)
    }
}

struct ArgusEntry: TimelineEntry {
    let date: Date
    let aether: WidgetAetherData
    let portfolio: WidgetPortfolioData
}

// MARK: - Widget View

struct ArgusWidgetEntryView : View {
    var entry: ArgusEntry
    @Environment(\.widgetFamily) var family

    var body: some View {
        VStack(spacing: 0) {
            // MARK: Top - Aether
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Aether Makro")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.gray)
                    Text(entry.aether.regime.uppercased())
                        .font(.system(size: 12, weight: .black))
                        .foregroundColor(regimeColor(entry.aether.score))
                }
                
                Spacer()
                
                // Score
                Text(String(format: "%.1f", entry.aether.score / 10.0))
                    .font(.system(size: 28, weight: .heavy, design: .rounded))
                    .foregroundColor(regimeColor(entry.aether.score))
                    .shadow(color: regimeColor(entry.aether.score).opacity(0.5), radius: 8)
                
                Spacer()
                
                // Grid Metrics
                VStack(alignment: .trailing, spacing: 2) {
                    miniMetric(icon: "chart.line.uptrend.xyaxis", label: "SPY", value: entry.aether.spyChange)
                    miniMetric(icon: "bolt.fill", label: "VIX", value: entry.aether.vixValue, isVix: true)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 8)
            .frame(maxWidth: .infinity)
            .background(
                LinearGradient(
                    colors: [regimeColor(entry.aether.score).opacity(0.15), Color.clear],
                    startPoint: .top,
                    endPoint: .bottom
                )
            )
            .widgetURL(URL(string: "argusterminal://aether"))
            
            Divider()
                .background(Color.white.opacity(0.1))
            
            // MARK: Bottom - Portfolio
            VStack(alignment: .leading, spacing: 8) {
                // Header
                HStack {
                    Image(systemName: "cpu")
                        .font(.system(size: 10))
                        .foregroundColor(entry.portfolio.isAutoPilotActive ? .green : .gray)
                    Text("Auto-Pilot")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.white)
                    
                    Spacer()
                    
                    Text(entry.portfolio.isAutoPilotActive ? "AKTİF" : "PASİF")
                        .font(.system(size: 9, weight: .bold))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(entry.portfolio.isAutoPilotActive ? Color.green.opacity(0.2) : Color.gray.opacity(0.2))
                        .foregroundColor(entry.portfolio.isAutoPilotActive ? .green : .gray)
                        .cornerRadius(4)
                }
                
                // Main Stats
                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text("PORTFÖY PnL")
                            .font(.system(size: 8, weight: .semibold))
                            .foregroundColor(.gray)
                        Text(formatCurrency(entry.portfolio.totalPnL))
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(entry.portfolio.totalPnL >= 0 ? .green : .red)
                    }
                    
                    Spacer()
                    
                    if entry.portfolio.isAutoPilotActive {
                        VStack(alignment: .trailing, spacing: 1) {
                            Text("WIN RATE")
                            .font(.system(size: 8, weight: .semibold))
                            .foregroundColor(.gray)
                            Text("\(Int(entry.portfolio.autoPilotWinRate))%")
                                .font(.system(size: 14, weight: .bold))
                                .foregroundColor(.white)
                        }
                    }
                }
                
                // LastAction / Info
                if let action = entry.portfolio.lastActionTitle {
                    HStack(spacing: 4) {
                        Circle().fill(Color.blue).frame(width: 4, height: 4)
                        Text(action)
                            .font(.system(size: 9, weight: .medium))
                            .foregroundColor(.white.opacity(0.8))
                            .lineLimit(1)
                    }
                } else {
                    Text("Henüz işlem yok")
                        .font(.system(size: 9))
                        .foregroundColor(.gray)
                }
            }
            .padding(12)
            .background(Color(hex: "#1A202C")) // Card Background
            .cornerRadius(12)
            .padding(10)
            .padding(.bottom, 4)
        }
        .widgetBackgroundCompat(Color(hex: "#10121A")) // Theme Background
        .widgetURL(URL(string: "argusterminal://portfolio"))
    }
    
    // MARK: - Helpers
    func regimeColor(_ score: Double) -> Color {
        if score >= 65 { return Color.green }
        if score <= 40 { return Color.red }
        return Color.orange
    }
    
    func miniMetric(icon: String, label: String, value: Double, isVix: Bool = false) -> some View {
        HStack(spacing: 2) {
            Image(systemName: icon)
                .font(.system(size: 8))
                .foregroundColor(.gray)
            
            Text(isVix ? String(format: "%.1f", value) : String(format: "%.1f%%", value))
                .font(.system(size: 9, weight: .bold))
                .foregroundColor(isVix ? (value > 20 ? .red : .green) : (value >= 0 ? .green : .red))
        }
    }
    
    func formatCurrency(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencySymbol = "$"
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? "$0"
    }
}

// MARK: - Configuration

struct ArgusWidget: Widget {
    let kind: String = "ArgusWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { entry in
            ArgusWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Argus Terminal")
        .description("Makro rejim ve Auto-Pilot portföy durumu.")
        .supportedFamilies([.systemMedium])
    }
}

// MARK: - Mock Data Extensions

extension WidgetAetherData {
    static let mock = WidgetAetherData(
        score: 75.0,
        regime: "Risk-On",
        summary: "Piyasalar pozitif.",
        lastUpdated: Date(),
        spyChange: 0.5,
        vixValue: 14.2,
        gldChange: -0.2,
        btcChange: 1.5
    )
    
    static let empty = WidgetAetherData(
        score: 50.0,
        regime: "Veri Bekleniyor",
        summary: "Analiz yapılıyor...",
        lastUpdated: Date(),
        spyChange: 0,
        vixValue: 0,
        gldChange: 0,
        btcChange: 0
    )
}

extension WidgetPortfolioData {
    static let mock = WidgetPortfolioData(
        totalEquity: 10450.0,
        totalPnL: 450.0,
        dayPnLPercent: 1.2,
        isAutoPilotActive: true,
        autoPilotWinRate: 68.0,
        lastActionTitle: "TSLA • AL • 3 ad @ 241$",
        topSignalTitle: "GÜÇLÜ AL: NVDA",
        lastUpdated: Date()
    )
    
    static let empty = WidgetPortfolioData(
        totalEquity: 10000.0,
        totalPnL: 0.0,
        dayPnLPercent: 0.0,
        isAutoPilotActive: false,
        autoPilotWinRate: 0.0,
        lastActionTitle: nil,
        topSignalTitle: nil,
        lastUpdated: Date()
    )
}

// MARK: - View Extension
extension View {
    @ViewBuilder
    func widgetBackgroundCompat(_ color: Color) -> some View {
        if #available(iOS 17.0, *) {
            containerBackground(for: .widget) {
                color
            }
        } else {
            background(color)
        }
    }
}

// MARK: - Color Extension
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue:  Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
