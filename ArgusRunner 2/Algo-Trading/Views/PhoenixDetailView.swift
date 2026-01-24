import SwiftUI
import Charts

struct PhoenixDetailView: View {
    let symbol: String
    let advice: PhoenixAdvice
    let candles: [Candle] // Should be the full history available, we'll slice key part
    var onRunBacktest: (() -> Void)? = nil
    @Environment(\.presentationMode) var presentationMode
    
    // Chart State
    @State private var selectedDate: Date?
    @State private var selectedPrice: Double?
    
    // Institution Rates State
    @State private var institutionRates: [InstitutionRate] = []
    @State private var showInstitutionRates = false
    
    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: 24) {
                        
                        // 1. Header & Score
                        headerSection
                            .padding(.horizontal)
                        
                        // 2. Main Chart (Linear Regression Channel)
                        chartSection
                            .frame(height: 350)
                            .padding(.horizontal)
                        
                        // 3. Explanation
                        explanationSection
                            .padding(.horizontal)
                        
                        // 4. Statistics Grid
                        statsGrid
                            .padding(.horizontal)
                        
                        // 5. Signal Checklist
                        checklistSection
                            .padding(.horizontal)
                            .padding(.bottom, 30)
                    }
                    .padding(.top)
                }
            }
            .navigationTitle("Phoenix Analizi")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if let run = onRunBacktest {
                        Button(action: {
                            presentationMode.wrappedValue.dismiss()
                            // Small delay to allow dismiss animation to start before triggering new sheet state
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                                run()
                            }
                        }) {
                            HStack(spacing: 4) {
                                Image(systemName: "clock.arrow.circlepath")
                                Text("GEÇMİŞ TEST")
                            }
                            .font(.caption)
                            .bold()
                        }
                        .foregroundColor(Theme.tint)
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Kapat") {
                        presentationMode.wrappedValue.dismiss()
                    }
                    .foregroundColor(Theme.tint)
                }
            }
            .task {
                await loadInstitutionRates()
            }
        }
    }
    
    // MARK: - Sections
    
    private var headerSection: some View {
        VStack(spacing: 8) {
            Text(symbol)
                .font(.system(size: 32, weight: .heavy, design: .monospaced))
                .foregroundColor(.white)
            
            HStack(spacing: 12) {
                Badge(text: advice.timeframe.localizedName, color: Theme.tint)
                Badge(text: statusText, color: statusColor)
            }
            
            Text("Güven Skoru: \(Int(advice.confidence))/100")
                .font(.headline)
                .foregroundColor(statusColor)
                .padding(.top, 4)
        }
    }
    
    private var chartSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("REGRESYON KANALI")
                .font(.caption)
                .bold()
                .foregroundColor(Theme.textSecondary)
            
            ZStack {
                Theme.cardBackground.cornerRadius(12)
                
                if candles.count > 20 {
                    PhoenixChannelChart(candles: candles, advice: advice)
                        .padding()
                } else {
                    Text("Grafik oluşturmak için yetersiz veri")
                        .foregroundColor(.gray)
                }
            }
        }
    }
    
    private var explanationSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "doc.text.magnifyingglass")
                .foregroundColor(.orange)
                Text("ANALİZ DETAYI")
                    .font(.headline)
                    .bold()
                    .foregroundColor(.white)
            }
            
            Text(advice.reasonShort)
                .font(.body)
                .foregroundColor(.white.opacity(0.9))
                .padding()
                .background(Theme.secondaryBackground)
                .cornerRadius(12)
                .fixedSize(horizontal: false, vertical: true)
                
            Text("Phoenix, regresyon kanalı (R-Squared) ve volatilite (ATR) kullanarak 'aşırı satım' bölgelerini belirler. Eğer fiyat alt banda değerse ve hacim + momentum teyidi gelirse yüksek puan verir.")
                .font(.caption)
                .foregroundColor(.gray)
                .padding(.top, 4)
        }
    }
    
    private var statsGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
            StatBox(title: "Eğim (Slope)", value: String(format: "%.4f", advice.regressionSlope ?? 0.0), icon: "chart.line.uptrend.xyaxis")
            StatBox(title: "Sigma (Sapma)", value: String(format: "%.2f", advice.sigma ?? 0.0), icon: "arrow.up.and.down")
            StatBox(title: "Pivot (Orta)", value: String(format: "%.2f", advice.channelMid ?? 0.0), icon: "crosshairs")
            StatBox(title: "Kanal Genişliği", value: String(format: "%%%.1f", ((advice.sigma ?? 0.0) / (advice.channelMid ?? 1.0)) * 400), icon: "arrow.left.and.right")
            // NEW: R² Reliability Indicator
            StatBox(
                title: "R² Güvenilirlik",
                value: String(format: "%.0f%%", (advice.rSquared ?? 0.5) * 100),
                icon: "checkmark.seal.fill",
                valueColor: (advice.rSquared ?? 0.5) > 0.5 ? .green : ((advice.rSquared ?? 0.5) > 0.25 ? .yellow : .red)
            )
            StatBox(title: "Lookback", value: "\(advice.lookback) gün", icon: "calendar")
        }
    }
    
    private var checklistSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("SİNYAL KONTROL LİSTESİ")
                .font(.caption)
                .bold()
                .foregroundColor(Theme.textSecondary)
            
            VStack(spacing: 0) {
                CheckRow(title: "Kanal Dibi Teması", isActive: advice.triggers.touchLowerBand)
                Divider().background(Color.gray.opacity(0.2))
                CheckRow(title: "RSI Dönüş Sinyali", isActive: advice.triggers.rsiReversal)
                Divider().background(Color.gray.opacity(0.2))
                CheckRow(title: "Pozitif Uyumsuzluk", isActive: advice.triggers.bullishDivergence)
                Divider().background(Color.gray.opacity(0.2))
                CheckRow(title: "Trend Onayı", isActive: advice.triggers.trendOk)
            }
            .background(Theme.secondaryBackground)
            .cornerRadius(12)
        }
    }
    
    // MARK: - Helpers
    
    private var statusText: String {
        switch advice.confidence {
        case 80...100: return "FIRSAT (A+)"
        case 60..<80: return "GÜÇLÜ"
        case 40..<60: return "NÖTR"
        default: return "ZAYIF"
        }
    }
    
    private var statusColor: Color {
        switch advice.confidence {
        case 70...100: return .green
        case 40..<70: return .yellow
        default: return .red
        }
    }
    
    // MARK: - Data Loading
    
    private func loadInstitutionRates() async {
        // Map symbol to Doviz.com slug
        let slug: String?
        if symbol.contains("ALTIN") || symbol == "GRAM" || symbol == "GLD" {
            slug = "gram-altin"
        } else if symbol.contains("GUMUS") {
            slug = "gram-gumus"
        } else if symbol == "USD" || symbol == "USDTRY" {
            slug = "USD"
        } else {
            slug = nil
        }
        
        if let asset = slug {
            do {
                if ["gram-altin", "gram-gumus", "ons-altin"].contains(asset) {
                    let rates = try await DovizComService.shared.fetchMetalInstitutionRates(asset: asset)
                    await MainActor.run {
                        self.institutionRates = rates
                        self.showInstitutionRates = true
                    }
                }
            } catch {
                print("Failed to load rates: \(error)")
            }
        }
    }
}

// MARK: - Phoenix Chart Component
struct PhoenixChannelChart: View {
    let candles: [Candle]
    let advice: PhoenixAdvice
    
    var body: some View {
        let displayCandles = candles.suffix(advice.lookback + 20) // Show a bit more context if available
        let sorted = Array(displayCandles).sorted { $0.date < $1.date }
        
        return Chart {
            // 1. Candles
            ForEach(sorted) { candle in
                RectangleMark(
                    x: .value("Tarih", candle.date),
                    yStart: .value("Open", candle.open),
                    yEnd: .value("Close", candle.close),
                    width: .fixed(4)
                )
                .foregroundStyle(candle.close >= candle.open ? Theme.positive : Theme.negative)
                
                RuleMark(
                    x: .value("Tarih", candle.date),
                    yStart: .value("Low", candle.low),
                    yEnd: .value("High", candle.high)
                )
                .lineStyle(StrokeStyle(lineWidth: 1))
                .foregroundStyle(Theme.neutral)
            }
            
            // 2. Channel Lines
            if !sorted.isEmpty {
                 // We calculate back in time
                
                ForEach(Array(sorted.enumerated()), id: \.offset) { index, candle in
                    // Index relative to end
                    // i=0 is oldest. i=count-1 is newest.
                    
                    if index >= (sorted.count - advice.lookback) {
                        // Calculate relative position 0..N-1
                        let relativeX = Double(index - (sorted.count - advice.lookback))
                        
                        // Line calculation
                        let distFromEnd = Double(advice.lookback - 1) - relativeX
                        let midY = (advice.channelMid ?? 0.0) - ((advice.regressionSlope ?? 0.0) * distFromEnd)
                        let upperY = midY + (2.0 * (advice.sigma ?? 0.0))
                        let lowerY = midY - (2.0 * (advice.sigma ?? 0.0))
                        
                        LineMark(x: .value("Tarih", candle.date), y: .value("Mid", midY))
                            .foregroundStyle(.purple)
                            .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))
                        
                        LineMark(x: .value("Tarih", candle.date), y: .value("Upper", upperY))
                            .foregroundStyle(.blue.opacity(0.5))
                        
                        LineMark(x: .value("Tarih", candle.date), y: .value("Lower", lowerY))
                            .foregroundStyle(.blue.opacity(0.5))
                    }
                }
            }
        }
        .chartYScale(domain: .automatic(includesZero: false))
    }
}

// MARK: - Components

struct Badge: View {
    let text: String
    let color: Color
    
    var body: some View {
        Text(text)
            .font(.caption2)
            .bold()
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.2))
            .foregroundColor(color)
            .cornerRadius(8)
    }
}

struct StatBox: View {
    let title: String
    let value: String
    let icon: String
    var valueColor: Color = .white  // NEW: Optional custom color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(Theme.tint)
                Text(title)
                    .font(.caption)
                    .foregroundColor(Theme.textSecondary)
            }
            Text(value)
                .font(.headline)
                .bold()
                .foregroundColor(valueColor)  // Use custom color
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.secondaryBackground)
        .cornerRadius(12)
    }
}

struct CheckRow: View {
    let title: String
    let isActive: Bool
    
    var body: some View {
        HStack {
            Text(title)
                .font(.subheadline)
                .foregroundColor(.white)
            Spacer()
            Image(systemName: isActive ? "checkmark.circle.fill" : "circle")
                .foregroundColor(isActive ? .green : .gray)
        }
        .padding()
    }
}
