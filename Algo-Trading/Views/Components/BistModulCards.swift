import SwiftUI

// MARK: - BIST Modül Kartları
// Faktör, Sektör, Rejim ve MoneyFlow için UI bileşenleri

// ═══════════════════════════════════════════════════════════════════
// MARK: - Faktör Kartı
// ═══════════════════════════════════════════════════════════════════

struct BistFaktorCard: View {
    let symbol: String
    @State private var result: BistFaktorResult?
    @State private var isLoading = true
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            Button(action: { withAnimation(.spring()) { isExpanded.toggle() } }) {
                HStack {
                    // Özel Türk motifi ikon
                    ZStack {
                        Circle()
                            .fill(LinearGradient(colors: [Color.blue, Color.cyan], startPoint: .topLeading, endPoint: .bottomTrailing))
                            .frame(width: 32, height: 32)
                        Text("F")
                            .font(.system(size: 16, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                    }
                    
                    Text("Faktör")
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Spacer()
                    
                    if isLoading {
                        ProgressView().scaleEffect(0.7)
                    } else if let r = result {
                        HStack(spacing: 4) {
                            Text("\(Int(r.totalScore))")
                                .font(.title3)
                                .bold()
                            Text("/100")
                                .font(.caption)
                                .foregroundColor(.gray)
                        }
                        .foregroundColor(scoreColor(r.totalScore))
                    }
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
            .buttonStyle(PlainButtonStyle())
            
            if let r = result {
                // Faktör Barları
                HStack(spacing: 8) {
                    ForEach(r.factors) { factor in
                        VStack(spacing: 4) {
                            Text(factor.name.components(separatedBy: " ").first ?? factor.name)
                                .font(.system(size: 9))
                                .foregroundColor(.gray)
                            ZStack(alignment: .bottom) {
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(Color.gray.opacity(0.2))
                                    .frame(width: 30, height: 40)
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(factorColor(factor.color))
                                    .frame(width: 30, height: CGFloat(factor.score / 100) * 40)
                            }
                            Text("\(Int(factor.score))")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(factorColor(factor.color))
                        }
                    }
                }
                .frame(maxWidth: .infinity)
                
                // Detaylar
                if isExpanded {
                    VStack(alignment: .leading, spacing: 8) {
                        Divider().background(Color.white.opacity(0.2))
                        
                        ForEach(r.factors) { factor in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(factor.name)
                                        .font(.caption)
                                        .bold()
                                        .foregroundColor(.white)
                                    Spacer()
                                    Text("\(Int(factor.score))/100")
                                        .font(.caption2)
                                        .foregroundColor(.gray)
                                }
                                
                                ForEach(factor.details, id: \.self) { detail in
                                    Text("• \(detail)")
                                        .font(.caption2)
                                        .foregroundColor(.gray)
                                }
                            }
                            .padding(8)
                            .background(Color.white.opacity(0.05))
                            .cornerRadius(8)
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(bistCardBackground)
        .cornerRadius(16)
        .onAppear { loadData() }
    }
    
    private func loadData() {
        Task {
            if let data = try? await BistFaktorEngine.shared.analyze(symbol: symbol) {
                await MainActor.run {
                    self.result = data
                    self.isLoading = false
                }
            } else {
                await MainActor.run { self.isLoading = false }
            }
        }
    }
    
    private func scoreColor(_ score: Double) -> Color {
        if score >= 70 { return .green }
        if score >= 50 { return .yellow }
        return .red
    }
    
    private func factorColor(_ name: String) -> Color {
        switch name {
        case "blue": return .blue
        case "green": return .green
        case "purple": return .purple
        case "yellow": return .yellow
        default: return .gray
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// MARK: - Sektör Kartı
// ═══════════════════════════════════════════════════════════════════

struct BistSektorCard: View {
    @State private var result: BistSektorResult?
    @State private var isLoading = true
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            Button(action: { withAnimation(.spring()) { isExpanded.toggle() } }) {
                HStack {
                    ZStack {
                        Circle()
                            .fill(LinearGradient(colors: [Color.orange, Color.red], startPoint: .topLeading, endPoint: .bottomTrailing))
                            .frame(width: 32, height: 32)
                        Text("S")
                            .font(.system(size: 16, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                    }
                    
                    Text("Sektör")
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Spacer()
                    
                    if isLoading {
                        ProgressView().scaleEffect(0.7)
                    } else if let r = result {
                        Text(r.rotation.rawValue)
                            .font(.caption)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(rotationColor(r.rotation).opacity(0.2))
                            .foregroundColor(rotationColor(r.rotation))
                            .cornerRadius(8)
                    }
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
            .buttonStyle(PlainButtonStyle())
            
            if let r = result, !r.sectors.isEmpty {
                // Sektör Listesi (Top 4)
                VStack(spacing: 6) {
                    ForEach(r.sectors.prefix(isExpanded ? 8 : 4)) { sector in
                        HStack {
                            Image(systemName: sector.icon)
                                .font(.caption)
                                .foregroundColor(momentumColor(sector.momentum))
                                .frame(width: 20)
                            
                            Text(sector.name)
                                .font(.caption)
                                .foregroundColor(.white)
                            
                            Spacer()
                            
                            Text("\(sector.dailyChange >= 0 ? "+" : "")\(String(format: "%.2f", sector.dailyChange))%")
                                .font(.caption)
                                .bold()
                                .foregroundColor(sector.dailyChange >= 0 ? .green : .red)
                        }
                        .padding(.vertical, 4)
                    }
                }
                
                if isExpanded {
                    Divider().background(Color.white.opacity(0.2))
                    
                    // Güçlü/Zayıf Özet
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("En Güçlü")
                                .font(.caption2)
                                .foregroundColor(.gray)
                            Text(r.strongestSector?.name ?? "-")
                                .font(.caption)
                                .foregroundColor(.green)
                        }
                        
                        Spacer()
                        
                        VStack(alignment: .trailing, spacing: 2) {
                            Text("En Zayıf")
                                .font(.caption2)
                                .foregroundColor(.gray)
                            Text(r.weakestSector?.name ?? "-")
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(bistCardBackground)
        .cornerRadius(16)
        .onAppear { loadData() }
    }
    
    private func loadData() {
        Task {
            if let data = try? await BistSektorEngine.shared.analyze() {
                await MainActor.run {
                    self.result = data
                    self.isLoading = false
                }
            } else {
                await MainActor.run { self.isLoading = false }
            }
        }
    }
    
    private func rotationColor(_ rotation: SektorRotasyon) -> Color {
        switch rotation {
        case .riskOn, .buyume: return .green
        case .teknoloji: return .cyan
        case .defansif: return .yellow
        case .riskOff, .belirsiz: return .red
        case .karisik: return .orange
        }
    }
    
    private func momentumColor(_ momentum: SektorMomentum) -> Color {
        switch momentum {
        case .strong, .positive: return .green
        case .neutral: return .yellow
        case .negative, .weak: return .red
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// MARK: - Rejim Kartı
// ═══════════════════════════════════════════════════════════════════

struct BistRejimCard: View {
    @State private var result: BistRejimResult?
    @State private var isLoading = true
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            Button(action: { withAnimation(.spring()) { isExpanded.toggle() } }) {
                HStack {
                    ZStack {
                        Circle()
                            .fill(LinearGradient(colors: [Color.purple, Color.pink], startPoint: .topLeading, endPoint: .bottomTrailing))
                            .frame(width: 32, height: 32)
                        Text("R")
                            .font(.system(size: 16, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                    }
                    
                    Text("Rejim")
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Spacer()
                    
                    if isLoading {
                        ProgressView().scaleEffect(0.7)
                    } else if let r = result {
                        HStack(spacing: 6) {
                            Image(systemName: r.regime.icon)
                            Text(r.regime.rawValue)
                        }
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(regimeColor(r.regime).opacity(0.2))
                        .foregroundColor(regimeColor(r.regime))
                        .cornerRadius(8)
                    }
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
            .buttonStyle(PlainButtonStyle())
            
            if let r = result {
                // Score Bar
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.gray.opacity(0.2))
                        RoundedRectangle(cornerRadius: 4)
                            .fill(regimeColor(r.regime))
                            .frame(width: geo.size.width * CGFloat(r.score / 100))
                    }
                }
                .frame(height: 8)
                
                // Öneri
                Text(r.recommendation)
                    .font(.caption)
                    .foregroundColor(.gray)
                
                if isExpanded {
                    Divider().background(Color.white.opacity(0.2))
                    
                    // Bileşenler
                    ForEach(r.components) { comp in
                        HStack {
                            Text(comp.name)
                                .font(.caption)
                                .foregroundColor(.white)
                            Spacer()
                            Text(comp.detail)
                                .font(.caption2)
                                .foregroundColor(statusColor(comp.status))
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(bistCardBackground)
        .cornerRadius(16)
        .onAppear { loadData() }
    }
    
    private func loadData() {
        Task {
            if let data = try? await BistRejimEngine.shared.analyze() {
                await MainActor.run {
                    self.result = data
                    self.isLoading = false
                }
            } else {
                await MainActor.run { self.isLoading = false }
            }
        }
    }
    
    private func regimeColor(_ regime: PiyasaRejimi) -> Color {
        switch regime {
        case .gucluBoga, .boga: return .green
        case .notr: return .yellow
        case .ayi, .gucluAyi: return .red
        }
    }
    
    private func statusColor(_ status: RejimStatus) -> Color {
        switch status {
        case .bullish, .positive: return .green
        case .neutral: return .yellow
        case .negative, .bearish: return .red
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// MARK: - MoneyFlow Kartı
// ═══════════════════════════════════════════════════════════════════

struct BistMoneyFlowCard: View {
    let symbol: String
    @State private var result: BistMoneyFlowResult?
    @State private var isLoading = true
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            Button(action: { withAnimation(.spring()) { isExpanded.toggle() } }) {
                HStack {
                    ZStack {
                        Circle()
                            .fill(LinearGradient(colors: [Color.teal, Color.blue], startPoint: .topLeading, endPoint: .bottomTrailing))
                            .frame(width: 32, height: 32)
                        Text("$")
                            .font(.system(size: 16, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                    }
                    
                    Text("MoneyFlow")
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Spacer()
                    
                    if isLoading {
                        ProgressView().scaleEffect(0.7)
                    } else if let r = result {
                        HStack(spacing: 4) {
                            Image(systemName: r.flowStatus.icon)
                            Text(r.flowStatus.rawValue)
                        }
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(flowColor(r.flowStatus).opacity(0.2))
                        .foregroundColor(flowColor(r.flowStatus))
                        .cornerRadius(8)
                    }
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
            .buttonStyle(PlainButtonStyle())
            
            if let r = result {
                // Hacim Karşılaştırma
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Bugün")
                            .font(.caption2)
                            .foregroundColor(.gray)
                        Text(formatVolume(r.todayVolume))
                            .font(.subheadline)
                            .bold()
                            .foregroundColor(.white)
                    }
                    
                    Spacer()
                    
                    VStack(spacing: 2) {
                        Text("×")
                            .font(.caption2)
                            .foregroundColor(.gray)
                        Text(String(format: "%.1f", r.volumeRatio))
                            .font(.subheadline)
                            .bold()
                            .foregroundColor(r.volumeRatio > 1.5 ? .green : (r.volumeRatio < 0.5 ? .red : .yellow))
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("Ortalama")
                            .font(.caption2)
                            .foregroundColor(.gray)
                        Text(formatVolume(r.avgVolume))
                            .font(.subheadline)
                            .foregroundColor(.gray)
                    }
                }
                
                if isExpanded && !r.signals.isEmpty {
                    Divider().background(Color.white.opacity(0.2))
                    
                    ForEach(r.signals) { signal in
                        HStack {
                            Circle()
                                .fill(signalColor(signal.type))
                                .frame(width: 6, height: 6)
                            Text(signal.description)
                                .font(.caption)
                                .foregroundColor(.white)
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(bistCardBackground)
        .cornerRadius(16)
        .onAppear { loadData() }
    }
    
    private func loadData() {
        Task {
            if let data = try? await BistMoneyFlowEngine.shared.analyze(symbol: symbol) {
                await MainActor.run {
                    self.result = data
                    self.isLoading = false
                }
            } else {
                await MainActor.run { self.isLoading = false }
            }
        }
    }
    
    private func flowColor(_ status: FlowStatus) -> Color {
        switch status {
        case .strongInflow, .inflow: return .green
        case .neutral: return .yellow
        case .outflow, .strongOutflow: return .red
        }
    }
    
    private func signalColor(_ type: MoneyFlowSignalType) -> Color {
        switch type {
        case .highVolume, .risingVolume, .accumulation, .bullishFlow: return .green
        case .lowVolume, .distribution, .bearishFlow: return .red
        }
    }
    
    private func formatVolume(_ vol: Double) -> String {
        if vol >= 1_000_000_000 { return String(format: "%.1fB", vol / 1_000_000_000) }
        if vol >= 1_000_000 { return String(format: "%.1fM", vol / 1_000_000) }
        if vol >= 1_000 { return String(format: "%.0fK", vol / 1_000) }
        return String(format: "%.0f", vol)
    }
}

// ═══════════════════════════════════════════════════════════════════
// MARK: - Ortak Stiller
// ═══════════════════════════════════════════════════════════════════

private var bistCardBackground: some View {
    RoundedRectangle(cornerRadius: 16)
        .fill(
            LinearGradient(
                colors: [Color(red: 0.12, green: 0.08, blue: 0.06), Color(red: 0.08, green: 0.05, blue: 0.03)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(
                    LinearGradient(
                        colors: [Color.orange.opacity(0.3), Color.red.opacity(0.1)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 1
                )
        )
}
