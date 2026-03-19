import SwiftUI

struct HermesFeedView: View {
    @ObservedObject var viewModel: TradingViewModel
    @State private var selectedScope = 0 // 0: Takip Listem, 1: Genel Piyasa
    
    var currentInsights: [NewsInsight] {
        return selectedScope == 0 ? viewModel.watchlistNewsInsights : viewModel.generalNewsInsights
    }
    
    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                VStack(spacing: 0) {
                    // 1. Sleek Scope Selector
                    ScopeSelectorBar(selectedScope: $selectedScope)
                        .padding(.vertical, 12)
                        .background(Theme.background)
                        .onChange(of: selectedScope) { _, newValue in
                            if newValue == 0 && viewModel.watchlistNewsInsights.isEmpty {
                                viewModel.loadWatchlistFeed()
                            } else if newValue == 1 && viewModel.generalNewsInsights.isEmpty {
                                viewModel.loadGeneralFeed()
                            }
                        }
                    
                    if currentInsights.isEmpty {
                        EmptyStateView(
                            scope: selectedScope,
                            isLoading: viewModel.isLoadingNews,
                            errorMessage: viewModel.newsErrorMessage,
                            onRetry: {
                                if selectedScope == 0 { viewModel.loadWatchlistFeed() }
                                else { viewModel.loadGeneralFeed() }
                            }
                        )
                    } else {
                        ScrollView {
                            LazyVStack(spacing: 0) { // Single Column, No spacing (handled by dividers or card padding)
                                ForEach(currentInsights) { insight in
                                    if insight.symbol != "MARKET" && insight.symbol != "GENERAL" {
                                        NavigationLink(destination: StockDetailView(symbol: insight.symbol, viewModel: viewModel)) {
                                            DiscoveryProCard(insight: insight)
                                        }
                                        .buttonStyle(PlainButtonStyle())
                                    } else {
                                        DiscoveryProCard(insight: insight)
                                    }
                                    
                                    Divider()
                                        .background(Theme.border.opacity(0.3))
                                        .padding(.horizontal)
                                }
                            }
                            .padding(.bottom, 80)
                        }
                        .refreshable {
                            if selectedScope == 0 { viewModel.loadWatchlistFeed() }
                            else { viewModel.loadGeneralFeed() }
                        }
                    }
                }
            }
            .navigationTitle("HERMES FEED")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if viewModel.isLoadingNews {
                        ProgressView().scaleEffect(0.8)
                    } else {
                        Button(action: {
                            if selectedScope == 0 { viewModel.loadWatchlistFeed() }
                            else { viewModel.loadGeneralFeed() }
                        }) {
                            Image(systemName: "arrow.clockwise")
                                .font(.system(size: 14))
                                .foregroundColor(Theme.tint)
                        }
                    }
                }
            }
        }
    }
}

// MARK: - Components

struct ScopeSelectorBar: View {
    @Binding var selectedScope: Int
    
    var body: some View {
        HStack(spacing: 0) {
            ScopeButton(title: "PORTFÖY & TAKİP", isSelected: selectedScope == 0) {
                withAnimation { selectedScope = 0 }
            }
            
            // Vertical Divider
            Rectangle()
                .fill(Color.gray.opacity(0.3))
                .frame(width: 1, height: 20)
            
            ScopeButton(title: "GENEL PİYASA", isSelected: selectedScope == 1) {
                withAnimation { selectedScope = 1 }
            }
        }
        .padding(4)
        .background(Theme.secondaryBackground.opacity(0.5))
        .cornerRadius(10)
        .padding(.horizontal)
    }
}

struct ScopeButton: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 11, weight: isSelected ? .bold : .medium, design: .monospaced))
                .foregroundColor(isSelected ? .white : .gray)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(isSelected ? Theme.tint.opacity(0.2) : Color.clear)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(isSelected ? Theme.tint.opacity(0.5) : Color.clear, lineWidth: 1)
                )
        }
    }
}

struct DiscoveryProCard: View {
    let insight: NewsInsight
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header: Symbol, Time
            HStack(alignment: .center) {
                Text(insight.symbol)
                    .font(.system(size: 14, weight: .bold, design: .monospaced))
                    .foregroundColor(Theme.tint)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Theme.tint.opacity(0.1))
                    .cornerRadius(4)
                
                Spacer()
                
                Text(timeAgo(insight.createdAt).uppercased())
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundColor(.gray)
            }
            
            // Content
            VStack(alignment: .leading, spacing: 6) {
                Text(insight.headline)
                    .font(.system(size: 15, weight: .medium)) // Clean readable font
                    .foregroundColor(.white)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                
                if !insight.impactSentenceTR.isEmpty {
                    Text("Analiz: \(insight.impactSentenceTR)")
                        .font(.system(size: 13))
                        .foregroundColor(.gray.opacity(0.9))
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            
            // Footer: Sentiment & Viral
            HStack {
                // Sentiment Pill
                HStack(spacing: 6) {
                    Circle()
                        .fill(colorForSentiment(insight.sentiment))
                        .frame(width: 8, height: 8)
                    
                    Text(insight.sentiment.displayTitle.uppercased())
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(colorForSentiment(insight.sentiment))
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(colorForSentiment(insight.sentiment).opacity(0.1))
                .cornerRadius(6)
                
                Spacer()
                
                if HermesHypeEngine.shared.isViral(symbol: insight.symbol) {
                    HStack(spacing: 4) {
                        Image(systemName: "flame.fill")
                            .font(.caption2)
                        Text("YÜKSEK ETKİLEŞİM")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                    }
                    .foregroundColor(.orange)
                }
            }
        }
        .padding(16)
        .background(Color.clear) // Clean list look
    }
    
    private func colorForSentiment(_ s: NewsSentiment) -> Color {
        switch s {
        case .strongPositive: return Theme.positive
        case .weakPositive: return Theme.positive.opacity(0.7)
        case .neutral: return .gray
        case .weakNegative: return Theme.negative.opacity(0.7)
        case .strongNegative: return Theme.negative
        }
    }
    
    private func timeAgo(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .full
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

struct EmptyStateView: View {
    let scope: Int
    let isLoading: Bool
    let errorMessage: String?
    let onRetry: () -> Void
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            ZStack {
                Circle()
                    .fill(Theme.secondaryBackground)
                    .frame(width: 100, height: 100)
                    .blur(radius: 5)
                
                Image(systemName: "antenna.radiowaves.left.and.right")
                    .font(.system(size: 40))
                    .foregroundColor(Theme.tint.opacity(0.5))
            }
            
            VStack(spacing: 12) {
                Text(scope == 0 ? "PORTFÖY TARANIYOR" : "PİYASA TARANIYOR")
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                    .foregroundColor(Theme.textPrimary)
                
                if isLoading {
                    Text("Hermes yapay zekası haber akışını analiz ediyor...")
                        .font(.caption)
                        .foregroundColor(Theme.textSecondary)
                } else {
                    Text("Henüz kritik bir haber tespit edilmedi.")
                        .font(.caption)
                        .foregroundColor(Theme.textSecondary)
                }
            }
            .multilineTextAlignment(.center)
            .padding(.horizontal)
            
            if let error = errorMessage {
                 Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding()
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
            }
            
            if !isLoading {
                Button(action: onRetry) {
                    HStack {
                        Image(systemName: "magnifyingglass")
                        Text("YENİDEN TARA")
                    }
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(Color.black)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(Theme.tint)
                    .cornerRadius(8)
                }
            } else {
                ProgressView()
                    .scaleEffect(1.0)
            }
            
            Spacer()
        }
    }
}

