import SwiftUI

// MARK: - Atlas V2 Detail View
// Şirketi A'dan Z'ye öğreten eğitici arayüz

struct AtlasV2DetailView: View {
    let symbol: String
    @State private var result: AtlasV2Result?
    @State private var isLoading = true
    @State private var error: String?
    @State private var expandedSections: Set<String> = []
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                if isLoading {
                    loadingView
                } else if let error = error {
                    errorView(error)
                } else if let result = result {
                    // Başlık ve Genel Skor
                    headerCard(result)
                    
                    // Öne Çıkanlar & Uyarılar
                    if !result.highlights.isEmpty || !result.warnings.isEmpty {
                        highlightsCard(result)
                    }
                    
                    // Bölüm Kartları
                    sectionCard(
                        title: "Değerleme",
                        icon: "dollarsign.circle.fill",
                        iconColor: .green,
                        score: result.valuationScore,
                        metrics: result.valuation.allMetrics,
                        sectionId: "valuation"
                    )
                    
                    sectionCard(
                        title: "Karlılık",
                        icon: "chart.line.uptrend.xyaxis",
                        iconColor: .blue,
                        score: result.profitabilityScore,
                        metrics: result.profitability.allMetrics,
                        sectionId: "profitability"
                    )
                    
                    sectionCard(
                        title: "Büyüme",
                        icon: "arrow.up.right.circle.fill",
                        iconColor: .purple,
                        score: result.growthScore,
                        metrics: result.growth.allMetrics,
                        sectionId: "growth"
                    )
                    
                    sectionCard(
                        title: "Finansal Sağlık",
                        icon: "shield.checkered",
                        iconColor: .cyan,
                        score: result.healthScore,
                        metrics: result.health.allMetrics,
                        sectionId: "health"
                    )
                    
                    sectionCard(
                        title: "Nakit Kalitesi",
                        icon: "banknote.fill",
                        iconColor: .green,
                        score: result.cashScore,
                        metrics: result.cash.allMetrics,
                        sectionId: "cash"
                    )
                    
                    sectionCard(
                        title: "Temetü",
                        icon: "gift.fill",
                        iconColor: .pink,
                        score: result.dividendScore,
                        metrics: result.dividend.allMetrics,
                        sectionId: "dividend"
                    )
                    
                    // YENİ: Risk Kartı
                    sectionCard(
                        title: "Risk Analizi",
                        icon: "exclamationmark.triangle.fill",
                        iconColor: .orange,
                        score: 100 - (result.risk.beta.value ?? 1.0) * 20,
                        metrics: result.risk.allMetrics,
                        sectionId: "risk"
                    )
                    
                    // Özet
                    summaryCard(result)
                }
            }
            .padding()
        }
        .navigationTitle("Atlas Analizi")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await loadData()
        }
    }
    
    // MARK: - Header Card
    
    private func headerCard(_ result: AtlasV2Result) -> some View {
        VStack(spacing: 16) {
            // Şirket İsmi ve Sembol
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(result.profile.name)
                        .font(.title2.bold())
                        .foregroundColor(.primary)
                    HStack(spacing: 8) {
                        Text(result.symbol)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        // Sektör Badge
                        if let sector = result.profile.sector {
                            Text(sector)
                                .font(.caption2)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.blue.opacity(0.2))
                                .foregroundColor(.blue)
                                .cornerRadius(4)
                        }
                    }
                }
                Spacer()
                
                // Piyasa Değeri
                VStack(alignment: .trailing, spacing: 4) {
                    Text(result.profile.formattedMarketCap)
                        .font(.headline)
                    Text(result.profile.marketCapTier)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            // Endüstri Bilgisi (varsa)
            if let industry = result.profile.industry {
                HStack {
                    Image(systemName: "building.2.fill")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(industry)
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                }
            }
            
            Divider()
            
            // Genel Skor Ring
            HStack(spacing: 24) {
                // Circular Progress
                ZStack {
                    Circle()
                        .stroke(Color.gray.opacity(0.2), lineWidth: 8)
                        .frame(width: 80, height: 80)
                    
                    Circle()
                        .trim(from: 0, to: result.totalScore / 100)
                        .stroke(
                            LinearGradient(
                                colors: [scoreColor(result.totalScore), scoreColor(result.totalScore).opacity(0.6)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            style: StrokeStyle(lineWidth: 8, lineCap: .round)
                        )
                        .frame(width: 80, height: 80)
                        .rotationEffect(.degrees(-90))
                    
                    VStack(spacing: 0) {
                        Text("\(Int(result.totalScore))")
                            .font(.title.bold())
                        Text("/100")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                // Kalite Bandı
                VStack(alignment: .leading, spacing: 8) {
                    Text("Kalite Bandı")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    HStack {
                        Text(result.qualityBand.rawValue)
                            .font(.title.bold())
                            .foregroundColor(scoreColor(result.totalScore))
                        Text("(\(result.qualityBand.description))")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    
                    Text(result.summary)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }
                
                Spacer()
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .shadow(color: scoreColor(result.totalScore).opacity(0.2), radius: 10, x: 0, y: 5)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(scoreColor(result.totalScore).opacity(0.3), lineWidth: 1)
        )
    }
    
    // MARK: - Highlights Card
    
    private func highlightsCard(_ result: AtlasV2Result) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // Öne Çıkanlar
            ForEach(result.highlights, id: \.self) { highlight in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "star.fill")
                        .foregroundColor(.yellow)
                    Text(highlight)
                        .font(.subheadline)
                }
            }
            
            // Uyarılar
            ForEach(result.warnings, id: \.self) { warning in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    Text(warning)
                        .font(.subheadline)
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(cardBackground)
    }
    
    // MARK: - Section Card
    
    private func sectionCard(title: String, icon: String = "", iconColor: Color = .white, score: Double, metrics: [AtlasMetric], sectionId: String) -> some View {
        VStack(spacing: 0) {
            // Header
            Button {
                // FIX: withAnimation kaldırıldı - main thread blocking önleniyor
                if expandedSections.contains(sectionId) {
                    expandedSections.remove(sectionId)
                } else {
                    expandedSections.insert(sectionId)
                }
            } label: {
                HStack {
                    if !icon.isEmpty {
                        Image(systemName: icon)
                            .foregroundColor(iconColor)
                    }
                    Text(title)
                        .font(.headline)
                    
                    Spacer()
                    
                    // Mini Progress Bar
                    miniProgressBar(score: score)
                    
                    // Score
                    Text("\(Int(score))")
                        .font(.headline)
                        .foregroundColor(scoreColor(score))
                    
                    // Chevron
                    Image(systemName: expandedSections.contains(sectionId) ? "chevron.up" : "chevron.down")
                        .foregroundColor(.secondary)
                }
                .padding()
            }
            .buttonStyle(.plain)
            
            // Expanded Content
            if expandedSections.contains(sectionId) {
                VStack(spacing: 16) {
                    ForEach(metrics) { metric in
                        metricRow(metric)
                    }
                }
                .padding(.horizontal)
                .padding(.bottom)
                // transition kaldırıldı - performans optimizasyonu
            }
        }
        .background(cardBackground)
    }
    
    // MARK: - Metric Row
    
    private func metricRow(_ metric: AtlasMetric) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            // Üst satır: İsim, Değer, Durum
            HStack {
                Text(metric.name)
                    .font(.subheadline.weight(.medium))
                
                Spacer()
                
                Text(metric.formattedValue)
                    .font(.subheadline.bold())
                
                Text(metric.status.emoji)
            }
            
            // Sektör karşılaştırması
            if let sectorAvg = metric.sectorAverage {
                HStack {
                    Text("Sektör Ort:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(AtlasMetric.format(sectorAvg))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            // Açıklama
            Text(metric.explanation)
                .font(.caption)
                .foregroundColor(explanationColor(metric.status))
            
            // Eğitici not (varsa)
            if !metric.educationalNote.isEmpty {
                HStack(alignment: .top, spacing: 4) {
                    Image(systemName: "book.fill")
                        .font(.caption)
                        .foregroundColor(.blue)
                    Text(metric.educationalNote)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .italic()
                }
                .padding(.top, 4)
            }
            
            Divider()
        }
    }
    
    // MARK: - Summary Card
    
    private func summaryCard(_ result: AtlasV2Result) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 4) {
                Image(systemName: "graduationcap.fill")
                    .foregroundColor(.orange)
                Text("Yatırımcı İçin Özet")
                    .font(.headline)
            }
            
            Text(result.summary)
                .font(.subheadline)
            
            // Alt bölüm skorları grid
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 12) {
                miniScoreCard("Karlılık", result.profitabilityScore)
                miniScoreCard("Değerleme", result.valuationScore)
                miniScoreCard("Sağlık", result.healthScore)
                miniScoreCard("Büyüme", result.growthScore)
                miniScoreCard("Nakit", result.cashScore)
                miniScoreCard("Temettü", result.dividendScore)
            }
        }
        .padding()
        .background(cardBackground)
    }
    
    private func miniScoreCard(_ title: String, _ score: Double) -> some View {
        VStack(spacing: 4) {
            Text(title)
                .font(.caption2)
                .foregroundColor(.secondary)
            Text("\(Int(score))")
                .font(.headline)
                .foregroundColor(scoreColor(score))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(8)
    }
    
    // MARK: - Helper Views
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)
            Text("Atlas analiz ediliyor...")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }
    
    private func errorView(_ message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundColor(.red)
            Text("Analiz Hatası")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
        .padding()
    }
    
    private func miniProgressBar(score: Double) -> some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Color.gray.opacity(0.2))
                    .frame(height: 6)
                
                Capsule()
                    .fill(scoreColor(score))
                    .frame(width: geo.size.width * (score / 100), height: 6)
            }
        }
        .frame(width: 60, height: 6)
    }
    
    private var cardBackground: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(.ultraThinMaterial)
            .shadow(color: Color.black.opacity(0.05), radius: 8, x: 0, y: 4)
    }
    
    private func scoreColor(_ score: Double) -> Color {
        switch score {
        case 70...: return .green
        case 50..<70: return .yellow
        case 30..<50: return .orange
        default: return .red
        }
    }
    
    private func explanationColor(_ status: AtlasMetricStatus) -> Color {
        switch status {
        case .excellent, .good: return .green
        case .neutral: return .primary
        case .warning: return .orange
        case .bad, .critical: return .red
        case .noData: return .secondary
        }
    }
    
    // MARK: - Data Loading
    
    private func loadData() async {
        // FIX: Timeout ekleyerek sonsuz beklemeyi önle
        let symbolToAnalyze = symbol
        
        // 30 saniye timeout ile analiz yap
        let loadTask = Task { () -> Result<AtlasV2Result, Error> in
            do {
                // Timeout protection
                let result = try await withTimeout(seconds: 30) {
                    try await AtlasV2Engine.shared.analyze(symbol: symbolToAnalyze)
                }
                return .success(result)
            } catch {
                // Timeout veya diğer hatalar
                if error is TimeoutError {
                    return .failure(NSError(domain: "AtlasV2", code: -1, userInfo: [NSLocalizedDescriptionKey: "Analiz zaman aşımına uğradı. Lütfen tekrar deneyin."]))
                }
                return .failure(error)
            }
        }
        
        let taskResult = await loadTask.value
        
        await MainActor.run {
            switch taskResult {
            case .success(let analysisResult):
                self.result = analysisResult
                self.isLoading = false
            case .failure(let err):
                self.error = err.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    // MARK: - Timeout Helper
    
    private enum TimeoutError: Error {
        case timeout
    }
    
    private func withTimeout<T>(seconds: TimeInterval, operation: @escaping () async throws -> T) async throws -> T {
        return try await withThrowingTaskGroup(of: T.self) { group in
            // Ana işlem
            group.addTask {
                try await operation()
            }
            
            // Timeout task
            group.addTask {
                try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
                throw TimeoutError.timeout
            }
            
            // İlk tamamlanan task'ı al
            guard let result = try await group.next() else {
                throw TimeoutError.timeout
            }
            
            // Diğer task'ı iptal et
            group.cancelAll()
            
            return result
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        AtlasV2DetailView(symbol: "AAPL")
    }
}
