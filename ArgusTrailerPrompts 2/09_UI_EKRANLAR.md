# PROMPT 9: UI EKRANLAR

## Açıklama

Ana ekranlar ve detay görünümleri.

---

## PROMPT

```
Argus Terminal için UI ekranlarını oluştur.

## Ana Ekranlar

1. **WatchlistView** - Takip listesi
2. **StockDetailView** - Hisse detay
3. **CouncilCard** - Konsey kararı kartı

## WatchlistView.swift

```swift
import SwiftUI

struct WatchlistView: View {
    @StateObject private var viewModel = TradingViewModel.shared
    @State private var selectedSymbol: String?
    
    var body: some View {
        NavigationStack {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: 16) {
                        // Aether HUD (Makro göstergesi)
                        if let macro = viewModel.macroRating {
                            AetherHUDCard(rating: macro)
                        }
                        
                        // Watchlist
                        ForEach(viewModel.watchlist, id: \.self) { symbol in
                            WatchlistRow(
                                symbol: symbol,
                                quote: viewModel.quotes[symbol],
                                council: viewModel.grandCouncilDecisions[symbol]
                            )
                            .onTapGesture {
                                selectedSymbol = symbol
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Argus Terminal")
            .navigationDestination(item: $selectedSymbol) { symbol in
                StockDetailView(symbol: symbol, viewModel: viewModel)
            }
            .task {
                await viewModel.loadMacroAnalysis()
                for symbol in viewModel.watchlist {
                    await viewModel.loadFullAnalysis(for: symbol)
                    await viewModel.conveneCouncil(for: symbol)
                }
            }
        }
    }
}

// MARK: - Watchlist Row

struct WatchlistRow: View {
    let symbol: String
    let quote: Quote?
    let council: GrandCouncilDecision?
    
    var body: some View {
        HStack(spacing: 12) {
            // Logo placeholder
            Circle()
                .fill(Theme.cardBackground)
                .frame(width: 44, height: 44)
                .overlay(
                    Text(String(symbol.prefix(1)))
                        .font(.headline)
                        .foregroundColor(.white)
                )
            
            // Symbol & Price
            VStack(alignment: .leading, spacing: 2) {
                Text(symbol)
                    .font(.headline)
                    .foregroundColor(.white)
                
                if let q = quote {
                    Text(String(format: "$%.2f", q.currentPrice))
                        .font(.subheadline)
                        .foregroundColor(Theme.textSecondary)
                }
            }
            
            Spacer()
            
            // Change
            if let q = quote, let dp = q.dp {
                Text(String(format: "%+.2f%%", dp))
                    .font(.subheadline)
                    .bold()
                    .foregroundColor(dp >= 0 ? Theme.positive : Theme.negative)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background((dp >= 0 ? Theme.positive : Theme.negative).opacity(0.2))
                    .cornerRadius(6)
            }
            
            // Council verdict
            if let c = council {
                Image(systemName: councilIcon(c.finalStance))
                    .foregroundColor(councilColor(c.finalStance))
                    .font(.title3)
            }
        }
        .padding()
        .background(Theme.secondaryBackground)
        .cornerRadius(12)
    }
    
    private func councilIcon(_ stance: VoteStance) -> String {
        switch stance {
        case .bullish: return "arrow.up.circle.fill"
        case .bearish: return "arrow.down.circle.fill"
        case .neutral: return "minus.circle.fill"
        }
    }
    
    private func councilColor(_ stance: VoteStance) -> Color {
        switch stance {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .yellow
        }
    }
}
```

## StockDetailView.swift

```swift
import SwiftUI

struct StockDetailView: View {
    let symbol: String
    @ObservedObject var viewModel: TradingViewModel
    
    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            
            ScrollView {
                VStack(spacing: 20) {
                    // Header
                    headerSection
                    
                    // Council Card
                    if let decision = viewModel.grandCouncilDecisions[symbol] {
                        CouncilCard(decision: decision)
                    }
                    
                    // Phoenix Card
                    if let phoenix = viewModel.phoenixResults[symbol] {
                        PhoenixCard(result: phoenix)
                    }
                    
                    // Analysis Cards
                    analysisCardsSection
                    
                    Spacer(minLength: 40)
                }
                .padding()
            }
        }
        .navigationTitle(symbol)
        .navigationBarTitleDisplayMode(.inline)
    }
    
    // MARK: - Header
    
    private var headerSection: some View {
        VStack(spacing: 8) {
            if let quote = viewModel.quotes[symbol] {
                Text(String(format: "$%.2f", quote.currentPrice))
                    .font(.system(size: 42, weight: .bold))
                    .foregroundColor(.white)
                
                if let dp = quote.dp {
                    HStack {
                        Text(String(format: "%+.2f%%", dp))
                            .font(.headline)
                            .foregroundColor(dp >= 0 ? .green : .red)
                        Text("bugün")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                }
            }
        }
        .padding()
    }
    
    // MARK: - Analysis Cards
    
    private var analysisCardsSection: some View {
        VStack(spacing: 12) {
            // Orion (Teknik)
            if let orion = viewModel.orionScores[symbol] {
                AnalysisCard(
                    title: "ORION",
                    subtitle: "Teknik Analiz",
                    score: orion.totalScore,
                    grade: orion.letterGrade,
                    icon: "waveform.path.ecg",
                    color: .purple
                )
            }
            
            // Atlas (Temel)
            if let atlas = viewModel.fundamentalScores[symbol] {
                AnalysisCard(
                    title: "ATLAS",
                    subtitle: "Temel Analiz",
                    score: atlas.totalScore,
                    grade: atlas.letterGrade,
                    icon: "building.columns.fill",
                    color: .blue
                )
            }
            
            // Hermes (Haber)
            if let hermes = viewModel.hermesResults[symbol] {
                AnalysisCard(
                    title: "HERMES",
                    subtitle: "Haber Analizi",
                    score: hermes.sentimentScore,
                    grade: nil,
                    icon: "newspaper.fill",
                    color: .orange
                )
            }
        }
    }
}

// MARK: - Analysis Card

struct AnalysisCard: View {
    let title: String
    let subtitle: String
    let score: Double
    let grade: String?
    let icon: String
    let color: Color
    
    var body: some View {
        HStack {
            // Icon
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
                .frame(width: 44)
            
            // Info
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(.white)
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.gray)
            }
            
            Spacer()
            
            // Score
            VStack(alignment: .trailing) {
                Text("\(Int(score))")
                    .font(.title2)
                    .bold()
                    .foregroundColor(scoreColor)
                
                if let g = grade {
                    Text(g)
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
        }
        .padding()
        .background(Theme.secondaryBackground)
        .cornerRadius(12)
    }
    
    private var scoreColor: Color {
        if score >= 70 { return .green }
        if score >= 50 { return .yellow }
        return .red
    }
}
```

## CouncilCard.swift

```swift
import SwiftUI

struct CouncilCard: View {
    let decision: GrandCouncilDecision
    @State private var isExpanded = false
    
    var body: some View {
        VStack(spacing: 16) {
            // Header
            HStack {
                Image(systemName: "person.3.fill")
                    .foregroundColor(.purple)
                Text("KONSEY KARARI")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                
                // Final verdict badge
                Text(decision.finalStance.rawValue)
                    .font(.caption)
                    .bold()
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(stanceColor.opacity(0.2))
                    .foregroundColor(stanceColor)
                    .cornerRadius(8)
            }
            
            // Net Support Gauge
            VStack(spacing: 4) {
                HStack {
                    Text("Net Destek")
                        .font(.caption)
                        .foregroundColor(.gray)
                    Spacer()
                    Text("\(Int(abs(decision.netSupport) * 100))%")
                        .font(.caption)
                        .bold()
                        .foregroundColor(.white)
                }
                
                // Gauge
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        // Background
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.gray.opacity(0.3))
                        
                        // Fill
                        RoundedRectangle(cornerRadius: 4)
                            .fill(stanceColor)
                            .frame(width: geo.size.width * abs(decision.netSupport))
                    }
                }
                .frame(height: 8)
            }
            
            // Consensus badge
            Text(decision.consensusLevel)
                .font(.caption)
                .foregroundColor(.gray)
            
            // Votes mini display
            HStack(spacing: 8) {
                ForEach(decision.votes) { vote in
                    VoteChip(vote: vote)
                }
            }
            
            // Expand button
            Button(action: { isExpanded.toggle() }) {
                HStack {
                    Text(isExpanded ? "Detayları Gizle" : "Detayları Göster")
                        .font(.caption)
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                }
                .foregroundColor(.cyan)
            }
            
            // Expanded details
            if isExpanded {
                VStack(spacing: 8) {
                    ForEach(decision.votes) { vote in
                        AdvisorVoteRow(vote: vote)
                    }
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
            
            // Summary
            Text(decision.summary)
                .font(.caption)
                .foregroundColor(.gray)
                .multilineTextAlignment(.leading)
        }
        .padding()
        .background(Theme.secondaryBackground)
        .cornerRadius(16)
        .animation(.spring(), value: isExpanded)
    }
    
    private var stanceColor: Color {
        switch decision.finalStance {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .yellow
        }
    }
}

// MARK: - Vote Chip

struct VoteChip: View {
    let vote: AdvisorVote
    
    var body: some View {
        VStack(spacing: 2) {
            Text(vote.stance.emoji)
                .font(.system(size: 16))
            Text(String(vote.advisor.rawValue.prefix(1)))
                .font(.caption2)
                .foregroundColor(.gray)
        }
        .frame(width: 36, height: 36)
        .background(Theme.cardBackground)
        .cornerRadius(8)
    }
}

// MARK: - Advisor Vote Row

struct AdvisorVoteRow: View {
    let vote: AdvisorVote
    
    var body: some View {
        HStack {
            // Icon + Name
            Image(systemName: vote.advisor.icon)
                .foregroundColor(advisorColor)
            Text(vote.advisor.displayName)
                .font(.caption)
                .foregroundColor(.white)
            
            Spacer()
            
            // Stance + Confidence
            Text("\(vote.stance.emoji) \(Int(vote.confidence))%")
                .font(.caption)
                .foregroundColor(.gray)
        }
        .padding(.vertical, 4)
    }
    
    private var advisorColor: Color {
        switch vote.advisor {
        case .atlas: return .blue
        case .orion: return .purple
        case .aether: return .cyan
        case .hermes: return .orange
        }
    }
}
```

## AetherHUDCard.swift

```swift
import SwiftUI

struct AetherHUDCard: View {
    let rating: MacroEnvironmentRating
    
    var body: some View {
        HStack(spacing: 12) {
            // Score Circle
            ZStack {
                Circle()
                    .stroke(regimeColor.opacity(0.3), lineWidth: 4)
                    .frame(width: 50, height: 50)
                
                Circle()
                    .trim(from: 0, to: rating.numericScore / 100)
                    .stroke(regimeColor, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                    .frame(width: 50, height: 50)
                    .rotationEffect(.degrees(-90))
                
                Text("\(Int(rating.numericScore))")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(.white)
            }
            
            // Info
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Image(systemName: "globe.europe.africa.fill")
                        .foregroundColor(.cyan)
                    Text("AETHER")
                        .font(.caption)
                        .bold()
                        .foregroundColor(.cyan)
                }
                
                Text(rating.regime.displayName)
                    .font(.headline)
                    .foregroundColor(regimeColor)
            }
            
            Spacer()
            
            // Category mini pills
            HStack(spacing: 4) {
                MiniPill(emoji: "🟢", score: rating.leadingScore)
                MiniPill(emoji: "🟡", score: rating.coincidentScore)
                MiniPill(emoji: "🔴", score: rating.laggingScore)
            }
        }
        .padding()
        .background(Theme.secondaryBackground)
        .cornerRadius(12)
    }
    
    private var regimeColor: Color {
        switch rating.regime {
        case .riskOn: return .green
        case .neutral: return .yellow
        case .riskOff: return .red
        }
    }
}

struct MiniPill: View {
    let emoji: String
    let score: Double?
    
    var body: some View {
        HStack(spacing: 2) {
            Text(emoji)
                .font(.system(size: 8))
            Text("\(Int(score ?? 50))")
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(pillColor)
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 3)
        .background(pillColor.opacity(0.15))
        .cornerRadius(10)
    }
    
    private var pillColor: Color {
        guard let s = score else { return .gray }
        if s >= 60 { return .green }
        if s >= 40 { return .yellow }
        return .red
    }
}
```

---

## App Entry Point (Algo_TradingApp.swift)

```swift
import SwiftUI

@main
struct ArgusTerminalApp: App {
    var body: some Scene {
        WindowGroup {
            WatchlistView()
                .preferredColorScheme(.dark)
        }
    }
}
```
