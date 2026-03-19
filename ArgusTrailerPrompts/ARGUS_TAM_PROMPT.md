# 🚀 ARGUS TERMİNAL - TAM UYGULAMA PROMPTU

## ⚠️ KULLANIM TALİMATI

1. Bu dosyadaki `# PROMPT BAŞLANGIÇ` ile `# PROMPT BİTİŞ` arasındaki HER ŞEYİ kopyala
2. Claude, ChatGPT veya Gemini'ye yapıştır
3. Başka hiçbir şey söyleme, sadece "Bunu yap" de
4. AI tüm dosyaları sırayla oluşturacak
5. Xcode'da Cmd+B → Build et
6. iPhone Simulator'da çalıştır

---

# PROMPT BAŞLANGIÇ

```
Argus Terminal iOS uygulaması için aşağıdaki TÜM dosyaları AYNEN oluştur. 
HİÇBİR değeri değiştirme, HİÇBİR yorum ekleme, HİÇBİR iyileştirme yapma.
Sadece bu kodları kopyala.

Önce Xcode'da yeni bir iOS App projesi oluştur:
- Product Name: Argus-Terminal
- Interface: SwiftUI
- Language: Swift
- Minimum iOS: 17.0

Sonra aşağıdaki dosyaları sırayla oluştur:

════════════════════════════════════════════════════════════════════════════════
DOSYA 1/15: Theme.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct Theme {
    // BACKGROUNDS (Deep Space)
    static let background = Color(hex: "050505")
    static let secondaryBackground = Color(hex: "0A0A0E")
    static let cardBackground = Color(hex: "12121A")
    static let border = Color(hex: "2D3748").opacity(0.3)
    static let groupedBackground = background
    
    // BRAND IDENTITY
    static let primary = Color(hex: "FFD700")
    static let accent = Color(hex: "00A8FF")
    static let tint = primary
    
    // TYPOGRAPHY
    static let textPrimary = Color.white
    static let textSecondary = Color(hex: "8A8F98")
    
    // SIGNAL COLORS (Neon)
    static let positive = Color(hex: "00FFA3")
    static let negative = Color(hex: "FF2E55")
    static let warning = Color(hex: "FFD740")
    static let neutral = Color(hex: "565E6D")
    
    static let chartUp = positive
    static let chartDown = negative
    
    struct Spacing {
        static let small: CGFloat = 8
        static let medium: CGFloat = 16
        static let large: CGFloat = 24
        static let xLarge: CGFloat = 32
    }
    
    struct Radius {
        static let small: CGFloat = 8
        static let medium: CGFloat = 12
        static let large: CGFloat = 16
        static let pill: CGFloat = 999
    }
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 6: (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default: (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(.sRGB, red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255, opacity: Double(a) / 255)
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 2/15: SanctumTheme.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct SanctumTheme {
    static let bg = RadialGradient(
        colors: [Color(hex: "080b14"), Color(hex: "020205")], 
        center: .center, 
        startRadius: 50, 
        endRadius: 500
    )
    
    // 7 MODÜL RENKLERİ (Neon/Holografik)
    static let orionColor = Color(hex: "00ff9d")   // Teknik
    static let atlasColor = Color(hex: "ffd700")   // Temel
    static let aetherColor = Color(hex: "bd00ff")  // Makro
    static let hermesColor = Color(hex: "00d0ff")  // Haber
    static let athenaColor = Color(hex: "ff0055")  // Smart Beta
    static let demeterColor = Color(hex: "8b5a2b") // Sektör
    static let chironColor = Color(hex: "ffffff")  // Öğrenme
    
    static let glassMaterial = Material.ultraThinMaterial
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 3/15: GlassCard.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct GlassCard<Content: View>: View {
    let content: Content
    var cornerRadius: CGFloat
    var brightness: Double
    
    init(cornerRadius: CGFloat = 16, brightness: Double = 0.0, @ViewBuilder content: () -> Content) {
        self.content = content()
        self.cornerRadius = cornerRadius
        self.brightness = brightness
    }
    
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: cornerRadius)
                .fill(.ultraThinMaterial)
                .opacity(0.9)
            
            RoundedRectangle(cornerRadius: cornerRadius)
                .fill(Theme.cardBackground.opacity(0.4 + brightness))
            
            RoundedRectangle(cornerRadius: cornerRadius)
                .stroke(
                    LinearGradient(
                        colors: [
                            .white.opacity(0.2),
                            .white.opacity(0.05),
                            .white.opacity(0.05),
                            .white.opacity(0.0)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 0.5
                )
            
            content
        }
        .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
        .shadow(color: Color.black.opacity(0.3), radius: 10, x: 0, y: 5)
    }
}

extension View {
    func glassCard(cornerRadius: CGFloat = 16) -> some View {
        GlassCard(cornerRadius: cornerRadius) { self }
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 4/15: ArgusGlobalBackground.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct ArgusGlobalBackground: View {
    @State private var startAnimation = false
    
    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            
            GeometryReader { proxy in
                let size = proxy.size
                
                ZStack {
                    Circle()
                        .fill(Theme.accent.opacity(0.1))
                        .frame(width: size.width * 1.5, height: size.width * 1.5)
                        .blur(radius: 80)
                        .offset(x: -size.width * 0.4, y: -size.height * 0.3)
                        .scaleEffect(startAnimation ? 1.1 : 1.0)
                    
                    Circle()
                        .fill(Theme.primary.opacity(0.05))
                        .frame(width: size.width * 1.2, height: size.width * 1.2)
                        .blur(radius: 60)
                        .offset(x: size.width * 0.4, y: size.height * 0.4)
                        .rotationEffect(.degrees(startAnimation ? 360 : 0))
                }
                .animation(.easeInOut(duration: 10).repeatForever(autoreverses: true), value: startAnimation)
            }
            
            RadialGradient(
                gradient: Gradient(colors: [.clear, .black.opacity(0.8)]),
                center: .center,
                startRadius: 200,
                endRadius: 800
            )
            .ignoresSafeArea()
        }
        .onAppear { startAnimation = true }
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 5/15: ModuleType.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

enum ModuleType: String, CaseIterable {
    case atlas = "ATLAS"
    case orion = "ORION"
    case aether = "AETHER"
    case hermes = "HERMES"
    case athena = "ATHENA"
    case demeter = "DEMETER"
    case chiron = "CHIRON"
    
    var icon: String {
        switch self {
        case .atlas: return "building.columns.fill"
        case .orion: return "chart.xyaxis.line"
        case .aether: return "globe.europe.africa.fill"
        case .hermes: return "newspaper.fill"
        case .athena: return "brain.head.profile"
        case .demeter: return "leaf.fill"
        case .chiron: return "graduationcap.fill"
        }
    }
    
    var color: Color {
        switch self {
        case .atlas: return SanctumTheme.atlasColor
        case .orion: return SanctumTheme.orionColor
        case .aether: return SanctumTheme.aetherColor
        case .hermes: return SanctumTheme.hermesColor
        case .athena: return SanctumTheme.athenaColor
        case .demeter: return SanctumTheme.demeterColor
        case .chiron: return SanctumTheme.chironColor
        }
    }
    
    var description: String {
        switch self {
        case .atlas: return "Temel Analiz & Değerleme"
        case .orion: return "Teknik İndikatörler"
        case .aether: return "Makroekonomik Rejim"
        case .hermes: return "Haber & Duygu Analizi"
        case .athena: return "Akıllı Varyans"
        case .demeter: return "Sektör Analizi"
        case .chiron: return "Risk Yönetimi"
        }
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 6/15: OrbView.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct OrbView: View {
    let module: ModuleType
    let score: Double
    @State private var isPulsing = false
    
    var body: some View {
        ZStack {
            Circle()
                .fill(module.color.opacity(0.3))
                .frame(width: 60, height: 60)
                .blur(radius: 10)
                .scaleEffect(isPulsing ? 1.2 : 1.0)
            
            Circle()
                .fill(
                    LinearGradient(
                        colors: [module.color, module.color.opacity(0.6)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 50, height: 50)
                .overlay(
                    VStack(spacing: 2) {
                        Image(systemName: module.icon)
                            .font(.system(size: 16))
                            .foregroundColor(.white)
                        Text("\(Int(score))")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(.white)
                    }
                )
            
            Circle()
                .stroke(module.color.opacity(0.5), lineWidth: 2)
                .frame(width: 50, height: 50)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 2).repeatForever(autoreverses: true)) {
                isPulsing = true
            }
        }
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 7/15: ArgusFloatingTabBar.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct ArgusFloatingTabBar: View {
    @Binding var selectedTab: Int
    @Binding var showVoiceSheet: Bool
    @Namespace private var animationNamespace
    
    private let tabs = [
        "chart.bar.xaxis",
        "eye.trianglebadge.exclamationmark.fill",
        "cube.transparent",
        "briefcase.fill",
        "gearshape.fill"
    ]
    
    var body: some View {
        HStack(spacing: 0) {
            ForEach(0..<tabs.count, id: \.self) { index in
                Spacer()
                
                Button(action: {
                    if index == 2 {
                        showVoiceSheet = true
                    } else {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                            selectedTab = index
                        }
                    }
                }) {
                    VStack(spacing: 6) {
                        Image(systemName: tabs[index])
                            .font(.system(size: 22, weight: (selectedTab == index || (index == 2 && showVoiceSheet)) ? .semibold : .regular))
                            .foregroundColor(
                                index == 2 ? Theme.primary : (selectedTab == index ? Theme.accent : Theme.textSecondary.opacity(0.5))
                            )
                            .scaleEffect(index == 2 ? 1.3 : (selectedTab == index ? 1.15 : 1.0))
                            .shadow(
                                color: index == 2 ? Theme.primary.opacity(0.6) : (selectedTab == index ? Theme.accent.opacity(0.6) : .clear),
                                radius: index == 2 ? 12 : 8
                            )
                        
                        if selectedTab == index && index != 2 {
                            Circle()
                                .fill(Theme.accent)
                                .frame(width: 4, height: 4)
                                .shadow(color: Theme.accent, radius: 5)
                                .matchedGeometryEffect(id: "tab_dot", in: animationNamespace)
                        } else if index != 2 {
                            Circle().fill(.clear).frame(width: 4, height: 4)
                        }
                    }
                }
                .buttonStyle(PlainButtonStyle())
                
                Spacer()
            }
        }
        .padding(.vertical, 16)
        .padding(.horizontal, 4)
        .background(
            GlassCard(cornerRadius: 32) { Color.clear }
        )
        .padding(.horizontal, 16)
        .padding(.bottom, 8)
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 8/15: Quote.swift (Model)
════════════════════════════════════════════════════════════════════════════════

import Foundation

struct Quote: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    var currentPrice: Double
    var previousClose: Double?
    var d: Double?
    var dp: Double?
    var h: Double?
    var l: Double?
    var o: Double?
    var t: TimeInterval?
    
    var timestamp: Date { Date(timeIntervalSince1970: t ?? Date().timeIntervalSince1970) }
    var changePercent: Double { dp ?? 0 }
    var isPositive: Bool { (dp ?? 0) >= 0 }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 9/15: YahooFinanceProvider.swift (Veri Servisi)
════════════════════════════════════════════════════════════════════════════════

import Foundation

class YahooFinanceProvider {
    static let shared = YahooFinanceProvider()
    
    func fetchQuote(symbol: String) async throws -> Quote {
        let url = URL(string: "https://query1.finance.yahoo.com/v8/finance/chart/\(symbol)?interval=1d&range=1d")!
        let (data, _) = try await URLSession.shared.data(from: url)
        
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let chart = json?["chart"] as? [String: Any]
        let result = (chart?["result"] as? [[String: Any]])?.first
        let meta = result?["meta"] as? [String: Any]
        
        let price = meta?["regularMarketPrice"] as? Double ?? 0
        let prevClose = meta?["chartPreviousClose"] as? Double
        
        let change = prevClose.map { price - $0 }
        let changePercent = prevClose.map { ((price - $0) / $0) * 100 }
        
        return Quote(
            symbol: symbol,
            currentPrice: price,
            previousClose: prevClose,
            d: change,
            dp: changePercent,
            h: nil, l: nil, o: nil,
            t: Date().timeIntervalSince1970
        )
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 10/15: TradingViewModel.swift
════════════════════════════════════════════════════════════════════════════════

import Foundation
import Combine

@MainActor
class TradingViewModel: ObservableObject {
    static let shared = TradingViewModel()
    
    @Published var watchlist: [String] = ["AAPL", "GOOGL", "MSFT", "NVDA", "TSLA", "AMZN"]
    @Published var quotes: [String: Quote] = [:]
    @Published var isLoading = false
    
    private let yahooProvider = YahooFinanceProvider.shared
    
    func loadQuote(for symbol: String) async {
        do {
            let quote = try await yahooProvider.fetchQuote(symbol: symbol)
            quotes[symbol] = quote
        } catch {
            print("Quote fetch failed: \(error)")
        }
    }
    
    func loadAllQuotes() async {
        isLoading = true
        for symbol in watchlist {
            await loadQuote(for: symbol)
        }
        isLoading = false
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 11/15: DisclaimerView.swift (Yasal Uyarı - Zorunlu)
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct DisclaimerView: View {
    @Binding var hasAccepted: Bool
    @State private var hasScrolledToBottom = false
    @State private var checkboxChecked = false
    
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color.black, Color(hex: "0A0510")],
                startPoint: .top,
                endPoint: .bottom
            ).ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.shield.fill")
                        .font(.system(size: 50))
                        .foregroundColor(.orange)
                    Text("YASAL UYARI")
                        .font(.title).bold()
                        .foregroundColor(.white)
                    Text("Devam etmeden önce okuyun")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                }
                .padding(.vertical, 30)
                
                // Content
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        disclaimerSection(
                            icon: "xmark.circle.fill",
                            color: .red,
                            title: "Bu Uygulama DEĞİLDİR",
                            items: [
                                "Yatırım tavsiyesi değildir",
                                "Finansal danışmanlık değildir",
                                "Kar garantisi vermez"
                            ]
                        )
                        
                        disclaimerSection(
                            icon: "info.circle.fill",
                            color: .blue,
                            title: "Bu Uygulama",
                            items: [
                                "Eğitim aracıdır",
                                "Analiz gösterir",
                                "Karar SİZİNDİR"
                            ]
                        )
                        
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.yellow)
                                Text("RİSK UYARISI")
                                    .font(.headline)
                                    .foregroundColor(.yellow)
                            }
                            Text("Finansal piyasalarda işlem yapmak yüksek risk içerir. Yatırılan sermayenin tamamını kaybetme riski vardır.")
                                .font(.subheadline)
                                .foregroundColor(.white.opacity(0.9))
                                .padding()
                                .background(Color.yellow.opacity(0.15))
                                .cornerRadius(12)
                        }
                        
                        Color.clear.frame(height: 1).id("bottom")
                            .onAppear { hasScrolledToBottom = true }
                    }
                    .padding()
                }
                
                // Footer
                VStack(spacing: 16) {
                    Divider().background(Color.gray)
                    
                    Button(action: { checkboxChecked.toggle() }) {
                        HStack(spacing: 12) {
                            Image(systemName: checkboxChecked ? "checkmark.square.fill" : "square")
                                .font(.title2)
                                .foregroundColor(checkboxChecked ? .green : .gray)
                            Text("Okudum, anladım, riskleri kabul ediyorum")
                                .font(.caption)
                                .foregroundColor(.white)
                        }
                    }
                    .padding(.horizontal)
                    
                    Button(action: acceptDisclaimer) {
                        HStack {
                            Image(systemName: "shield.checkered")
                            Text("KABUL ET VE DEVAM ET").bold()
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(canAccept ? Color.green : Color.gray)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                    .disabled(!canAccept)
                    .padding(.horizontal)
                    
                    Button("Kabul Etmiyorum") { exit(0) }
                        .font(.caption)
                        .foregroundColor(.gray)
                        .padding(.bottom, 20)
                }
                .padding(.top, 10)
                .background(Color.black.opacity(0.8))
            }
        }
    }
    
    private var canAccept: Bool {
        hasScrolledToBottom && checkboxChecked
    }
    
    private func acceptDisclaimer() {
        UserDefaults.standard.set(true, forKey: "disclaimer_accepted")
        withAnimation { hasAccepted = true }
    }
    
    private func disclaimerSection(icon: String, color: Color, title: String, items: [String]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon).foregroundColor(color)
                Text(title).font(.headline).foregroundColor(color)
            }
            ForEach(items, id: \.self) { item in
                HStack(alignment: .top, spacing: 8) {
                    Text("•").foregroundColor(color.opacity(0.7))
                    Text(item).font(.subheadline).foregroundColor(.white.opacity(0.9))
                }
            }
        }
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 12/15: SanctumView.swift (Orbital Karar Ekranı)
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct SanctumView: View {
    let symbol: String
    @ObservedObject var viewModel: TradingViewModel
    @State private var selectedModule: ModuleType? = nil
    
    private let orbitRadius: CGFloat = 130
    private let demoScores: [ModuleType: Double] = [
        .orion: 72, .atlas: 65, .aether: 58, .hermes: 80,
        .athena: 55, .demeter: 70, .chiron: 62
    ]
    
    var body: some View {
        ZStack {
            SanctumTheme.bg.ignoresSafeArea()
            
            VStack {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(symbol)
                            .font(.title).fontWeight(.black)
                            .foregroundColor(.white)
                        if let q = viewModel.quotes[symbol] {
                            HStack(spacing: 6) {
                                Text(String(format: "$%.2f", q.currentPrice))
                                    .font(.headline).foregroundColor(.white)
                                if let dp = q.dp {
                                    Text(String(format: "%+.2f%%", dp))
                                        .font(.caption).bold()
                                        .foregroundColor(dp >= 0 ? .green : .red)
                                        .padding(.horizontal, 6).padding(.vertical, 2)
                                        .background((dp >= 0 ? Color.green : Color.red).opacity(0.2))
                                        .cornerRadius(4)
                                }
                            }
                        }
                    }
                    Spacer()
                    Image(systemName: "eye.fill")
                        .font(.title2)
                        .foregroundColor(Theme.primary)
                        .shadow(color: Theme.primary, radius: 10)
                }
                .padding()
                
                Spacer()
                
                // Orbital System
                ZStack {
                    Circle()
                        .stroke(Color.white.opacity(0.1), lineWidth: 1)
                        .frame(width: orbitRadius * 2, height: orbitRadius * 2)
                    
                    // Center Core
                    ZStack {
                        Circle()
                            .fill(RadialGradient(
                                colors: [Theme.primary.opacity(0.8), Theme.primary.opacity(0.2)],
                                center: .center, startRadius: 0, endRadius: 50
                            ))
                            .frame(width: 100, height: 100)
                            .shadow(color: Theme.primary.opacity(0.5), radius: 20)
                        
                        VStack(spacing: 4) {
                            Text("ARGUS")
                                .font(.system(size: 14, weight: .black))
                                .foregroundColor(.black)
                            Text("72")
                                .font(.system(size: 24, weight: .bold))
                                .foregroundColor(.black)
                        }
                    }
                    
                    // Orbiting Modules
                    ForEach(Array(ModuleType.allCases.enumerated()), id: \.element) { index, module in
                        let angle = (2.0 * .pi / Double(ModuleType.allCases.count)) * Double(index) - .pi / 2.0
                        let xOffset = orbitRadius * CGFloat(cos(angle))
                        let yOffset = orbitRadius * CGFloat(sin(angle))
                        
                        OrbView(module: module, score: demoScores[module] ?? 50)
                            .offset(x: xOffset, y: yOffset)
                            .onTapGesture {
                                withAnimation(.spring()) { selectedModule = module }
                            }
                    }
                }
                .frame(height: 350)
                
                Spacer()
                
                // Module Detail
                if let module = selectedModule {
                    VStack(spacing: 8) {
                        Text(module.rawValue)
                            .font(.headline)
                            .foregroundColor(module.color)
                        Text(module.description)
                            .font(.caption)
                            .foregroundColor(.gray)
                        Button("Kapat") {
                            withAnimation { selectedModule = nil }
                        }
                        .font(.caption).foregroundColor(Theme.accent)
                    }
                    .padding().glassCard().padding()
                } else {
                    Text("Modül seçin")
                        .font(.caption).foregroundColor(.gray)
                        .padding(.bottom, 40)
                }
            }
        }
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 13/15: WatchlistView.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct WatchlistView: View {
    @ObservedObject var viewModel: TradingViewModel
    @Binding var selectedSymbol: String?
    
    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ForEach(viewModel.watchlist, id: \.self) { symbol in
                    WatchlistRow(symbol: symbol, quote: viewModel.quotes[symbol])
                        .onTapGesture { selectedSymbol = symbol }
                }
            }
            .padding()
        }
        .task { await viewModel.loadAllQuotes() }
    }
}

struct WatchlistRow: View {
    let symbol: String
    let quote: Quote?
    
    var body: some View {
        HStack {
            Circle()
                .fill(Theme.cardBackground)
                .frame(width: 44, height: 44)
                .overlay(
                    Text(String(symbol.prefix(1)))
                        .font(.headline).foregroundColor(.white)
                )
            
            VStack(alignment: .leading, spacing: 2) {
                Text(symbol).font(.headline).foregroundColor(.white)
                if let q = quote {
                    Text(String(format: "$%.2f", q.currentPrice))
                        .font(.subheadline).foregroundColor(Theme.textSecondary)
                }
            }
            
            Spacer()
            
            if let q = quote, let dp = q.dp {
                Text(String(format: "%+.2f%%", dp))
                    .font(.subheadline).bold()
                    .foregroundColor(dp >= 0 ? Theme.positive : Theme.negative)
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background((dp >= 0 ? Theme.positive : Theme.negative).opacity(0.2))
                    .cornerRadius(6)
            }
        }
        .padding()
        .glassCard()
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 14/15: ContentView.swift
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = TradingViewModel.shared
    @State private var selectedTab = 0
    @State private var showVoiceSheet = false
    @State private var selectedSymbol: String? = nil
    
    var body: some View {
        ZStack {
            ArgusGlobalBackground()
            
            if let symbol = selectedSymbol {
                SanctumView(symbol: symbol, viewModel: viewModel)
                    .overlay(alignment: .topLeading) {
                        Button(action: { selectedSymbol = nil }) {
                            Image(systemName: "chevron.left")
                                .font(.title2)
                                .foregroundColor(.white)
                                .padding()
                        }
                    }
            } else {
                TabView(selection: $selectedTab) {
                    WatchlistView(viewModel: viewModel, selectedSymbol: $selectedSymbol)
                        .tag(0)
                    
                    PortfolioPlaceholder()
                        .tag(1)
                    
                    Color.clear.tag(2)
                    
                    PortfolioPlaceholder()
                        .tag(3)
                    
                    SettingsPlaceholder()
                        .tag(4)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                
                VStack {
                    Spacer()
                    ArgusFloatingTabBar(selectedTab: $selectedTab, showVoiceSheet: $showVoiceSheet)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

struct PortfolioPlaceholder: View {
    var body: some View {
        VStack {
            Image(systemName: "briefcase.fill")
                .font(.system(size: 60))
                .foregroundColor(Theme.primary)
            Text("Portföy").font(.title2).foregroundColor(.white)
        }
    }
}

struct SettingsPlaceholder: View {
    var body: some View {
        VStack {
            Image(systemName: "gearshape.fill")
                .font(.system(size: 60))
                .foregroundColor(Theme.accent)
            Text("Ayarlar").font(.title2).foregroundColor(.white)
        }
    }
}

════════════════════════════════════════════════════════════════════════════════
DOSYA 15/15: Argus_TerminalApp.swift (App Entry)
════════════════════════════════════════════════════════════════════════════════

import SwiftUI

@main
struct Argus_TerminalApp: App {
    @State private var hasAcceptedDisclaimer = UserDefaults.standard.bool(forKey: "disclaimer_accepted")
    
    var body: some Scene {
        WindowGroup {
            if hasAcceptedDisclaimer {
                ContentView()
            } else {
                DisclaimerView(hasAccepted: $hasAcceptedDisclaimer)
            }
        }
    }
}

════════════════════════════════════════════════════════════════════════════════
TAMAMLANDI - BUILD ET VE ÇALIŞTIR
════════════════════════════════════════════════════════════════════════════════

Tüm 15 dosyayı oluşturduktan sonra:
1. Cmd+B ile build et
2. iPhone 15 Pro simulator seç  
3. Cmd+R ile çalıştır

İlk açılışta:
- Yasal uyarı ekranı (scroll + checkbox + kabul butonu)
- Kabul edilince ana uygulama

Ana uygulama:
- Siyah (#050505) nebula arka planı
- Alt kısımda buzlu cam floating tab bar
- Ortada altın voice butonu
- Watchlist: Yahoo Finance'den gerçek fiyatlar
- Sanctum: 7 modüllü orbital karar ekranı
```

# PROMPT BİTİŞ

---

## RENK KODLARI (Referans)

| Kullanım | Hex |
|----------|-----|
| Arka plan | #050505 |
| Kart | #12121A |
| Altın | #FFD700 |
| Mavi | #00A8FF |
| Yeşil | #00FFA3 |
| Kırmızı | #FF2E55 |
| Orion | #00FF9D |
| Atlas | #FFD700 |
| Aether | #BD00FF |
| Hermes | #00D0FF |
| Athena | #FF0055 |
| Demeter | #8B5A2B |
| Chiron | #FFFFFF |

---

## ÖNEMLİ NOTLAR

✅ API Key gerekmez (Yahoo Finance ücretsiz)
✅ Yasal uyarı mekanizması dahil
✅ 15 dosya tek seferde oluşturulur
✅ Copy-paste, değişiklik yok
