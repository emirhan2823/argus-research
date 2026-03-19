# 🚀 ARGUS MEGA PROMPT - BİREBİR AYNI SONUÇ

## ⚠️ KRİTİK TALİMAT

Bu prompt, Argus Terminal'in **BİREBİR AYNISINI** oluşturur.

**KURALLARI:**

1. Bu promptu **HİÇBİR DEĞİŞİKLİK YAPMADAN** kopyala-yapıştır yap
2. AI'a başka bir şey söyleme - sadece bu promptu ver
3. Her dosyayı sırasıyla oluşturmasını bekle
4. Build et, hata varsa hatayı AI'a geri ver

---

## BAŞLANGIÇ: Xcode Projesi

```
1. Xcode aç → Create New Project → iOS App
2. Product Name: Argus-Terminal
3. Interface: SwiftUI
4. Language: Swift
5. Minimum Deployments: iOS 17.0
6. "Create" tıkla
```

---

# PROMPT (AYNEN KOPYALA VE AI'A VER)

```
Argus Terminal iOS uygulaması için aşağıdaki dosyaları AYNEN oluştur. HİÇBİR değeri değiştirme, HİÇBİR yorum ekleme, HİÇBİR iyileştirme yapma. Sadece bu kodu kopyala.

═══════════════════════════════════════════════════════════════════
DOSYA 1: Theme.swift
═══════════════════════════════════════════════════════════════════

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
    
    static func colorForScore(_ score: Double) -> Color {
        if score >= 50 { return positive }
        else if score <= -50 { return negative }
        else { return neutral }
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

═══════════════════════════════════════════════════════════════════
DOSYA 2: SanctumTheme.swift
═══════════════════════════════════════════════════════════════════

import SwiftUI

struct SanctumTheme {
    static let bg = RadialGradient(
        colors: [Color(hex: "080b14"), Color(hex: "020205")], 
        center: .center, 
        startRadius: 50, 
        endRadius: 500
    )
    
    // 7 MODÜL RENKLERİ
    static let orionColor = Color(hex: "00ff9d")
    static let atlasColor = Color(hex: "ffd700")
    static let aetherColor = Color(hex: "bd00ff")
    static let hermesColor = Color(hex: "00d0ff")
    static let athenaColor = Color(hex: "ff0055")
    static let demeterColor = Color(hex: "8b5a2b")
    static let chironColor = Color(hex: "ffffff")
    
    static let glassMaterial = Material.ultraThinMaterial
}

═══════════════════════════════════════════════════════════════════
DOSYA 3: GlassCard.swift
═══════════════════════════════════════════════════════════════════

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

═══════════════════════════════════════════════════════════════════
DOSYA 4: ArgusGlobalBackground.swift
═══════════════════════════════════════════════════════════════════

import SwiftUI

struct ArgusGlobalBackground: View {
    @State private var startAnimation = false
    
    var body: some View {
        ZStack {
            Theme.background
                .ignoresSafeArea()
            
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
        .onAppear {
            startAnimation = true
        }
    }
}

═══════════════════════════════════════════════════════════════════
DOSYA 5: ModuleType.swift
═══════════════════════════════════════════════════════════════════

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
        case .athena: return "Akıllı Varyans (Smart Beta)"
        case .demeter: return "Sektör & Endüstri Analizi"
        case .chiron: return "Öğrenme & Risk Yönetimi"
        }
    }
}

═══════════════════════════════════════════════════════════════════
DOSYA 6: OrbView.swift (Modül Balonları)
═══════════════════════════════════════════════════════════════════

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

═══════════════════════════════════════════════════════════════════
DOSYA 7: ArgusFloatingTabBar.swift
═══════════════════════════════════════════════════════════════════

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
                            .scaleEffect(
                                index == 2 ? 1.3 : (selectedTab == index ? 1.15 : 1.0)
                            )
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
            GlassCard(cornerRadius: 32) {
                Color.clear
            }
        )
        .padding(.horizontal, 16)
        .padding(.bottom, 8)
    }
}

═══════════════════════════════════════════════════════════════════
DOSYA 8: SanctumView.swift (Ana Karar Ekranı - Basitleştirilmiş)
═══════════════════════════════════════════════════════════════════

import SwiftUI

struct SanctumView: View {
    let symbol: String
    @State private var selectedModule: ModuleType? = nil
    
    private let orbitRadius: CGFloat = 130
    
    // Demo skorlar (gerçek uygulamada ViewModel'den gelir)
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
                            .font(.title)
                            .fontWeight(.black)
                            .foregroundColor(.white)
                        Text("$185.42")
                            .font(.headline)
                            .foregroundColor(.gray)
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
                    // Orbit Ring
                    Circle()
                        .stroke(Color.white.opacity(0.1), lineWidth: 1)
                        .frame(width: orbitRadius * 2, height: orbitRadius * 2)
                    
                    // Center Core
                    ZStack {
                        Circle()
                            .fill(
                                RadialGradient(
                                    colors: [Theme.primary.opacity(0.8), Theme.primary.opacity(0.2)],
                                    center: .center,
                                    startRadius: 0,
                                    endRadius: 50
                                )
                            )
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
                                withAnimation(.spring()) {
                                    selectedModule = module
                                }
                            }
                    }
                }
                .frame(height: 350)
                
                Spacer()
                
                // Bottom Info
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
                        .font(.caption)
                        .foregroundColor(Theme.accent)
                    }
                    .padding()
                    .glassCard()
                    .padding()
                } else {
                    Text("Modül seçin")
                        .font(.caption)
                        .foregroundColor(.gray)
                        .padding(.bottom, 40)
                }
            }
        }
    }
}

═══════════════════════════════════════════════════════════════════
DOSYA 9: ContentView.swift (App Entry)
═══════════════════════════════════════════════════════════════════

import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0
    @State private var showVoiceSheet = false
    
    var body: some View {
        ZStack {
            ArgusGlobalBackground()
            
            TabView(selection: $selectedTab) {
                WatchlistView()
                    .tag(0)
                
                SanctumView(symbol: "AAPL")
                    .tag(1)
                
                Color.clear
                    .tag(2)
                
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
        .preferredColorScheme(.dark)
    }
}

struct WatchlistView: View {
    let symbols = ["AAPL", "GOOGL", "MSFT", "NVDA", "TSLA"]
    
    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ForEach(symbols, id: \.self) { symbol in
                    WatchlistRow(symbol: symbol)
                }
            }
            .padding()
        }
    }
}

struct WatchlistRow: View {
    let symbol: String
    
    var body: some View {
        HStack {
            Circle()
                .fill(Theme.cardBackground)
                .frame(width: 44, height: 44)
                .overlay(
                    Text(String(symbol.prefix(1)))
                        .font(.headline)
                        .foregroundColor(.white)
                )
            
            VStack(alignment: .leading, spacing: 2) {
                Text(symbol)
                    .font(.headline)
                    .foregroundColor(.white)
                Text("$185.42")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
            }
            
            Spacer()
            
            Text("+2.45%")
                .font(.subheadline)
                .bold()
                .foregroundColor(Theme.positive)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Theme.positive.opacity(0.2))
                .cornerRadius(6)
        }
        .padding()
        .glassCard()
    }
}

struct PortfolioPlaceholder: View {
    var body: some View {
        VStack {
            Image(systemName: "briefcase.fill")
                .font(.system(size: 60))
                .foregroundColor(Theme.primary)
            Text("Portföy")
                .font(.title2)
                .foregroundColor(.white)
        }
    }
}

struct SettingsPlaceholder: View {
    var body: some View {
        VStack {
            Image(systemName: "gearshape.fill")
                .font(.system(size: 60))
                .foregroundColor(Theme.accent)
            Text("Ayarlar")
                .font(.title2)
                .foregroundColor(.white)
        }
    }
}

#Preview {
    ContentView()
}

═══════════════════════════════════════════════════════════════════
DOSYA 10: Argus_TerminalApp.swift
═══════════════════════════════════════════════════════════════════

import SwiftUI

@main
struct Argus_TerminalApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

═══════════════════════════════════════════════════════════════════
BİTTİ - BUILD ET VE ÇALIŞTIR
═══════════════════════════════════════════════════════════════════

Bu 10 dosyayı oluşturduktan sonra:
1. Cmd+B ile build et
2. iPhone 15 Pro simulator seç
3. Cmd+R ile çalıştır

Göreceğin:
- Siyah (#050505) arka plan üzerinde mavi/altın nebula animasyonu
- Alt kısımda buzlu cam tab bar (ortada altın voice butonu)
- Watchlist: GlassCard içinde hisseler
- Sanctum: Ortada altın ARGUS, etrafında 7 renkli modül orbiti

```

---

## RENK REHBERİ

| Kullanım | Hex Kodu |
|----------|----------|
| Ana arka plan | #050505 |
| İkincil arka plan | #0A0A0E |
| Kart tabanı | #12121A |
| Altın (Brand) | #FFD700 |
| Mavi (Accent) | #00A8FF |
| Yeşil (Pozitif) | #00FFA3 |
| Kırmızı (Negatif) | #FF2E55 |
| Orion | #00FF9D |
| Atlas | #FFD700 |
| Aether | #BD00FF |
| Hermes | #00D0FF |
| Athena | #FF0055 |
| Demeter | #8B5A2B |
| Chiron | #FFFFFF |
