import SwiftUI

struct MarketView: View {
    @EnvironmentObject var appState: AppStateCoordinator // Yeni navigation
    @EnvironmentObject var viewModel: TradingViewModel // Legacy (Geçiş döneminde korunuyor)
    @EnvironmentObject var watchlistVM: WatchlistViewModel // FAZ 2: Yeni modüler sistem
    @ObservedObject var notificationStore = NotificationStore.shared
    
    // Market Mode: Global veya BIST
    enum MarketMode { case global, bist }
    @State private var selectedMarket: MarketMode = .global
    @Namespace private var animation // For sliding tab effect
    
    // UI State
    @State private var showSearch = false // showAddSymbolSheet idi, showSearch yaptık
    @State private var showNotifications = false
    @State private var showAetherDetail = false
    @State private var showEducation = false // NEW
    
    // Filtered Watchlist - ARTIK WatchlistViewModel'DEN OKUYOR (Performans iyileştirmesi)
    var filteredWatchlist: [String] {
        switch selectedMarket {
        case .global:
            return watchlistVM.watchlist.filter { !$0.uppercased().hasSuffix(".IS") }
        case .bist:
            return watchlistVM.watchlist.filter { $0.uppercased().hasSuffix(".IS") || SymbolResolver.shared.isBistSymbol($0) }
        }
    }
    
    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                VStack(spacing: 0) {
                    // 1. CUSTOM HEADER (Premium Toggle)
                    HStack {
                        marketTabButton(title: "GLOBAL 🌍", mode: .global)
                        marketTabButton(title: "SİRKİYE 🇹🇷", mode: .bist)
                    }
                    .padding()
                    .background(Theme.secondaryBackground.opacity(0.5))
                    // Custom Header
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Piyasa")
                                .font(.largeTitle)
                                .fontWeight(.bold)
                                .foregroundColor(.white)
                            
                            // Tarih
                            Text(Date().formatted(date: .abbreviated, time: .omitted))
                                .font(.caption)
                                .foregroundColor(Theme.textSecondary)
                        }
                        
                        Spacer()
                        
                        // Action Buttons
                        HStack(spacing: 16) {
                            Button(action: { showSearch = true }) {
                                Image(systemName: "plus.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(Theme.tint)
                            }
                            
                            NavigationLink(destination: NotificationsView(viewModel: viewModel)) {
                                Image(systemName: "bell.fill")
                                    .font(.title3)
                                    .foregroundColor(Theme.textSecondary)
                            }
                        }
                    }
                    .padding()
                    
                    // Main Content
                    ScrollView {
                        LazyVStack(spacing: 24) {
                            
                            // Market Tab'a göre ilgili Cockpit'i göster
                            switch selectedMarket {
                            case .global:
                                // 1. Global Markets
                                GlobalCockpitView(
                                    viewModel: viewModel,
                                    watchlist: filteredWatchlist, // Zaten global filtrelenmiş
                                    showAetherDetail: $showAetherDetail,
                                    showEducation: $showEducation,
                                    deleteAction: { symbol in
                                        deleteSymbol(symbol)
                                    }
                                )
                                
                            case .bist:
                                // 2. Borsa Istanbul (Sirkiye en üstte)
                                BistCockpitView(
                                    viewModel: viewModel,
                                    watchlist: filteredWatchlist, // Zaten BIST filtrelenmiş
                                    deleteAction: { symbol in
                                       deleteSymbol(symbol)
                                    }
                                )
                            }
                            
                            Spacer(minLength: 100)
                        }
                    }
                }
                
                // Navigation Link for Programmatic Navigation (State'i AppState'e taşıdık)
                NavigationLink(
                    destination: StockDetailView(
                        symbol: appState.selectedSymbol ?? "", 
                        viewModel: viewModel
                    ),
                    isActive: Binding(
                        get: { appState.selectedSymbol != nil },
                        set: { if !$0 { appState.selectedSymbol = nil } }
                    )
                ) { EmptyView() }
            }
            .navigationBarHidden(true)
            .sheet(isPresented: $showSearch) {
                AddSymbolSheet() // Environment'tan alıyor
            }
            .sheet(isPresented: $showAetherDetail) {
                if let macro = viewModel.macroRating { ArgusAetherDetailView(rating: macro) }
            }
            .sheet(isPresented: $showEducation) {
                ChironEducationCard(result: ChironRegimeEngine.shared.lastResult, isPresented: $showEducation)
            }
            .frame(maxWidth: .infinity)
        }
    }
    
    private func deleteSymbol(_ symbol: String) {
        // HER İKİ SİSTEMDEN DE SİL (Geçiş dönemi senkronizasyonu)
        watchlistVM.removeSymbol(symbol)
        if let index = viewModel.watchlist.firstIndex(of: symbol) {
            viewModel.deleteFromWatchlist(at: IndexSet(integer: index))
        }
    }
    
    // Custom Tab Button
    @ViewBuilder
    func marketTabButton(title: String, mode: MarketMode) -> some View {
        Button(action: { withAnimation { selectedMarket = mode } }) {
            VStack(spacing: 4) {
                Text(title)
                    .font(.headline)
                    .fontWeight(selectedMarket == mode ? .bold : .regular)
                    .foregroundColor(selectedMarket == mode ? .white : .gray)
                
                if selectedMarket == mode {
                    Rectangle()
                        .fill(mode == .global ? Theme.primary : Color.cyan)
                        .frame(height: 2)
                        .matchedGeometryEffect(id: "TabUnderline", in: animation)
                } else {
                    Rectangle().fill(Color.clear).frame(height: 2)
                }
            }
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - GLOBAL COCKPIT
struct GlobalCockpitView: View {
    @ObservedObject var viewModel: TradingViewModel // Legacy (Aether, SmartTicker için)
    @EnvironmentObject var watchlistVM: WatchlistViewModel // Quotes için yeni sistem
    let watchlist: [String]
    @Binding var showAetherDetail: Bool
    @Binding var showEducation: Bool // NEW
    let deleteAction: (String) -> Void
    
    var body: some View {
        VStack(spacing: 0) {
            // Aether HUD (New Futuristic Design)
            AetherDashboardHUD(
                rating: viewModel.macroRating,
                onTap: { showAetherDetail = true }
            )
            // PERFORMANS: Macro load artık background'da, Bootstrap'ta zaten çağrılıyor
            // Sadece cache boşsa lazy load yap
            .onAppear { 
                if viewModel.macroRating == nil { 
                    Task.detached(priority: .background) {
                        await MainActor.run { viewModel.loadMacroEnvironment() }
                    }
                } 
            }
            
            // CHIRON NEURAL LINK (PULSE) - NEW!
            ChironNeuralLink(showEducation: $showEducation)
                .padding(.horizontal, 16)
                .padding(.top, 4)
            
            // ScoutStoriesBar REMOVED from here (Moved to Terminal)
            
            SmartTickerStrip(viewModel: viewModel)
                .padding(.top, 16)
            
            // Watchlist Header
            HStack {
                Text("GLOBAL İZLEME")
                    .font(.caption).bold().foregroundColor(Theme.textSecondary)
                Spacer()
                Text(viewModel.isLiveMode ? "LIVE" : "DELAY")
                    .font(.caption2).bold()
                    .foregroundColor(viewModel.isLiveMode ? .green : .gray)
            }
            .padding(.horizontal)
            .padding(.top, 20)
            .padding(.bottom, 8)
            
            // Watchlist - QUOTES ARTIK WatchlistViewModel'DEN OKUNUYOR
            if watchlist.isEmpty {
                MarketEmptyStateView().padding(.top, 40)
            } else {
                LazyVStack(spacing: 0) {
                    ForEach(watchlist, id: \.self) { symbol in
                        NavigationLink(destination: StockDetailView(symbol: symbol, viewModel: viewModel)) {
                            CrystalWatchlistRow(
                                symbol: symbol,
                                quote: watchlistVM.quotes[symbol], // Yeni sistem
                                candles: viewModel.candles[symbol], // Candles hala TradingVM'den
                                forecast: viewModel.prometheusForecastBySymbol[symbol] // Prometheus
                            )
                            .padding(.horizontal, 16).padding(.vertical, 4)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .contextMenu {
                            Button(role: .destructive) { deleteAction(symbol) } label: { Label("Sil", systemImage: "trash") }
                        }
                    }
                }
            }
        }
    }
}

// MARK: - BIST COCKPIT (SİRKİYE)
struct BistCockpitView: View {
    @ObservedObject var viewModel: TradingViewModel // Legacy (Orion, SirkiyeDashboard için)
    @EnvironmentObject var watchlistVM: WatchlistViewModel // Quotes için yeni sistem
    let watchlist: [String]
    let deleteAction: (String) -> Void
    
    var body: some View {
        VStack(spacing: 0) {
            // Sirkiye Dashboard Header
            HStack {
                Text("SİRKİYE KOKPİTİ")
                    .font(.title3).bold()
                    .tracking(1)
                    .foregroundColor(.white)
                Spacer()
                Image(systemName: "eye.fill")
                    .foregroundColor(.cyan)
            }
            .padding(.horizontal)
            
            SirkiyeDashboardView(viewModel: viewModel)
                .padding(.bottom, 8)
            
            // Watchlist Header
            HStack {
                Text("BIST TAKİP (TL)")
                    .font(.caption).bold().foregroundColor(Theme.textSecondary)
                Spacer()
            }
            .padding(.horizontal)
            .padding(.top, 20)
            .padding(.bottom, 8)
            
            if watchlist.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "chart.bar.doc.horizontal")
                        .font(.system(size: 48)).foregroundColor(Theme.textSecondary.opacity(0.3))
                    Text("BIST hissesi ekle")
                        .foregroundColor(Theme.textSecondary)
                }.padding(.top, 40)
            } else {
                LazyVStack(spacing: 10) {
                    ForEach(watchlist, id: \.self) { symbol in
                        NavigationLink(destination: StockDetailView(symbol: symbol, viewModel: viewModel)) {
                            // Enhanced Bist Watchlist Row
                            BistCockpitRow(
                                symbol: symbol,
                                quote: watchlistVM.quotes[symbol], // Yeni sistem
                                orionResult: viewModel.orionScores[symbol], // Orion hala TradingVM'den
                                onAppear: {
                                    // Trigger Orion Analysis if missing
                                    if viewModel.orionScores[symbol] == nil {
                                        Task { await viewModel.loadOrionScore(for: symbol) }
                                    }
                                }
                            )
                        }
                        .buttonStyle(PlainButtonStyle())
                        .contextMenu {
                            Button(role: .destructive) { deleteAction(symbol) } label: { Label("Sil", systemImage: "trash") }
                        }
                    }
                }
                .padding(.horizontal)
            }
        }
    }
}

// Keep Helper Views
// PILOT MIGRATION: AddSymbolSheet artık WatchlistViewModel kullanıyor
struct AddSymbolSheet: View {
    @EnvironmentObject var watchlistVM: WatchlistViewModel // Yeni sistem
    @EnvironmentObject var viewModel: TradingViewModel // Backward compatibility (search için)
    @Environment(\.presentationMode) var presentationMode
    @State private var symbol: String = ""
    @FocusState private var isFocused: Bool
    let popularSymbols = ["NVDA", "AMD", "TSLA", "AAPL", "MSFT", "META", "AMZN", "GOOGL", "NFLX", "COIN"]
    let popularBist = ["THYAO.IS", "ASELS.IS", "AKBNK.IS", "KCHOL.IS", "EREGL.IS"]
    @State private var searchBist = false
    
    var body: some View {
        NavigationView {
             ZStack {
                Theme.background.ignoresSafeArea()
                VStack(spacing: 20) {
                    // Search Bar
                     HStack {
                        Image(systemName: "magnifyingglass").foregroundColor(Theme.textSecondary)
                        TextField("Sembol Ara (Örn: \(searchBist ? "THYAO.IS" : "PLTR"))", text: $symbol)
                            .foregroundColor(Theme.textPrimary)
                            .disableAutocorrection(true)
                            .focused($isFocused)
                            .onChange(of: symbol) { _, newValue in 
                                // Search: Her iki VM'de de çağır (geçiş dönemi)
                                watchlistVM.search(query: newValue)
                            }
                            .onSubmit { addAndDismiss(symbol) }
                        
                        if !symbol.isEmpty {
                            Button(action: { symbol = ""; watchlistVM.searchResults = [] }) {
                                Image(systemName: "xmark.circle.fill").foregroundColor(Theme.textSecondary)
                            }
                        }
                    }
                    .padding()
                    .background(Theme.secondaryBackground)
                    .cornerRadius(12)
                    .padding(.horizontal)
                    .padding(.top)
                    
                    // Toggle for Suggestions
                    Picker("Piyasa", selection: $searchBist) {
                        Text("Global").tag(false)
                        Text("BIST").tag(true)
                    }
                    .pickerStyle(SegmentedPickerStyle())
                    .padding(.horizontal)
                    
                    // WatchlistViewModel'den search results
                    if !symbol.isEmpty && !watchlistVM.searchResults.isEmpty {
                        List(watchlistVM.searchResults) { result in
                            Button(action: { addAndDismiss(result.symbol) }) {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(result.symbol).bold().foregroundColor(Theme.textPrimary)
                                        Text(result.description).font(.caption).foregroundColor(Theme.textSecondary)
                                    }
                                    Spacer()
                                    Image(systemName: "plus.circle").foregroundColor(Theme.primary)
                                }
                            }
                            .listRowBackground(Theme.secondaryBackground)
                        }
                        .listStyle(.plain)
                        .background(Theme.background)
                    } else {
                        VStack(alignment: .leading) {
                            Text("Popüler (\(searchBist ? "BIST" : "Global"))").font(.caption).foregroundColor(Theme.textSecondary).padding(.horizontal)
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack {
                                    ForEach(searchBist ? popularBist : popularSymbols, id: \.self) { item in
                                        Button(action: { addAndDismiss(item) }) {
                                            Text(item).padding(.horizontal, 12).padding(.vertical, 8)
                                                .background(Theme.secondaryBackground).foregroundColor(Theme.textPrimary).cornerRadius(20)
                                        }
                                    }
                                }.padding(.horizontal)
                            }
                        }
                        Spacer()
                    }
                }
            }
            .navigationTitle("Hisse Ekle")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarLeading) { Button("Kapat") { presentationMode.wrappedValue.dismiss() } } }
            .onAppear { DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { isFocused = true } }
        }
    }
    private func addAndDismiss(_ symbolToAdd: String) {
        if !symbolToAdd.isEmpty {
            // HER İKİ SİSTEME DE EKLE (Geçiş dönemi senkronizasyonu)
            watchlistVM.addSymbol(symbolToAdd)
            viewModel.addSymbol(symbolToAdd)
            presentationMode.wrappedValue.dismiss()
        }
    }
}

struct MarketEmptyStateView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "magnifyingglass.circle").font(.system(size: 64)).foregroundColor(Theme.textSecondary.opacity(0.5))
            Text("Takip listen boş").font(.headline).foregroundColor(Theme.textPrimary)
            Text("İzlemek istediğin hisseleri eklemek için\n+ butonuna bas.").font(.subheadline).foregroundColor(Theme.textSecondary).multilineTextAlignment(.center)
        }
    }
}

// ENHANCED BIST ROW (Previously used OrionBistResult, now V2 OrionScoreResult for compatibility)
struct BistCockpitRow: View { // Renamed from BistWatchlistRow
    let symbol: String
    let quote: Quote? // Changed from BistTicker? to Quote?
    let orionResult: OrionScoreResult? // V2 Result
    let onAppear: () -> Void
    
    var body: some View {
        HStack {
            // Left: Symbol
            VStack(alignment: .leading, spacing: 4) {
                Text(symbol.replacingOccurrences(of: ".IS", with: ""))
                    .font(.headline).bold().foregroundColor(.white)
                
                Text("BIST")
                    .font(.caption2).bold()
                    .padding(.horizontal, 4).padding(.vertical, 2)
                    .background(Color.red.opacity(0.3)).cornerRadius(4)
                    .foregroundColor(.white)
            }
            
            Spacer()
            
            // Middle: TAHTA (Signal)
            if let result = orionResult {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("TAHTA")
                        .font(.caption2).foregroundColor(.gray)
                    
                    HStack(spacing: 4) {
                        Text(result.verdict)
                            .font(.caption).bold()
                            .foregroundColor(color(for: result.verdict))
                        
                        Circle()
                            .fill(color(for: result.verdict))
                            .frame(width: 6, height: 6)
                    }
                }
            } else {
                 Text("Tahta: ...")
                    .font(.caption2).foregroundColor(.gray)
            }
            
            Spacer().frame(width: 20)
            
            // Right: Price
            if let q = quote {
                VStack(alignment: .trailing, spacing: 4) {
                    Text("₺\(String(format: "%.2f", q.currentPrice))")
                        .font(.body).bold().foregroundColor(.white)
                    
                    HStack(spacing: 2) {
                        Image(systemName: q.isPositive ? "arrow.up" : "arrow.down")
                        Text("\(String(format: "%.2f", q.percentChange))%")
                    }
                    .font(.caption)
                    .foregroundColor(q.isPositive ? .green : .red)
                }
            } else {
                ProgressView().scaleEffect(0.7)
            }
        }
        .padding()
        .background(Color(hex: "1A1D26"))
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.1), lineWidth: 1))
        .onAppear { onAppear() }
    }
    
    func color(for verdict: String) -> Color {
        if verdict.contains("Buy") || verdict.contains("Al") { return .green }
        if verdict.contains("Sell") || verdict.contains("Sat") { return .red }
        return .yellow
    }
}
