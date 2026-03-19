# PROMPT 9: UI TASARIM SİSTEMİ (v2 - Detaylı)

## ⚠️ ÖNEMLİ

Bu prompt, Argus Terminal'in **birebir** kopyasını oluşturur. Renk kodları, spacing değerleri ve efektler tam olarak belirtilmiştir. AI'a bu promptu verdiğinizde **değiştirmeden** kullanın.

---

## PROMPT (Kopyalayın ve AI'a Verin)

```
Argus Terminal için aşağıdaki TASARIM SİSTEMİNİ birebir uygula. HİÇBİR değeri değiştirme.

## 1. TEMA (Theme.swift)

```swift
import SwiftUI

struct Theme {
    // ─────────────────────────────────────
    // BACKGROUNDS (Deep Space)
    // ─────────────────────────────────────
    static let background = Color(hex: "050505")        // Void Black
    static let secondaryBackground = Color(hex: "0A0A0E") // Deep Nebula  
    static let cardBackground = Color(hex: "12121A")    // Glass Base
    static let border = Color(hex: "2D3748").opacity(0.3)
    
    // ─────────────────────────────────────
    // BRAND IDENTITY
    // ─────────────────────────────────────
    static let primary = Color(hex: "FFD700")   // Argus Gold
    static let accent = Color(hex: "00A8FF")    // Cyber Blue
    
    // ─────────────────────────────────────
    // TYPOGRAPHY
    // ─────────────────────────────────────
    static let textPrimary = Color.white
    static let textSecondary = Color(hex: "8A8F98") // Stardust Gray
    
    // ─────────────────────────────────────
    // SIGNAL COLORS (Neon)
    // ─────────────────────────────────────
    static let positive = Color(hex: "00FFA3")  // Cyber Green
    static let negative = Color(hex: "FF2E55")  // Crimson Red
    static let warning = Color(hex: "FFD740")   // Amber
    static let neutral = Color(hex: "565E6D")   // Steel Gray
    
    // ─────────────────────────────────────
    // LAYOUT CONSTANTS
    // ─────────────────────────────────────
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

// HEX Color Extension (ZORUNLU)
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
```

## 2. SANCTUM THEME (Modül Renkleri)

```swift
struct SanctumTheme {
    // Background Gradient
    static let bg = RadialGradient(
        colors: [Color(hex: "080b14"), Color(hex: "020205")], 
        center: .center, 
        startRadius: 50, 
        endRadius: 500
    )
    
    // 7 MODÜL RENKLERİ (Holografik/Neon)
    static let orionColor = Color(hex: "00ff9d")   // Cyber Green - Teknik
    static let atlasColor = Color(hex: "ffd700")   // Gold - Temel
    static let aetherColor = Color(hex: "bd00ff")  // Deep Purple - Makro
    static let hermesColor = Color(hex: "00d0ff")  // Cyan - Haber
    static let athenaColor = Color(hex: "ff0055")  // Neon Red - Smart Beta
    static let demeterColor = Color(hex: "8b5a2b") // Bronze - Sektör
    static let chironColor = Color(hex: "ffffff")  // White - Öğrenme
    
    // Glass Material
    static let glassMaterial = Material.ultraThinMaterial
}
```

## 3. GLASS CARD (Buzlu Cam Efekti)

```swift
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
            // 1. Frosted Glass Base
            RoundedRectangle(cornerRadius: cornerRadius)
                .fill(.ultraThinMaterial)
                .opacity(0.9)
            
            // 2. Dark Tint Overlay
            RoundedRectangle(cornerRadius: cornerRadius)
                .fill(Theme.cardBackground.opacity(0.4 + brightness))
            
            // 3. Gradient Border (Tech Edge)
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
            
            // 4. Content
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
```

## 4. MODÜL TİPLERİ

```swift
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
```

## 5. ORBİTAL SANCTUM VIEW (Ana Karar Ekranı)

```swift
struct ArgusSanctumView: View {
    let symbol: String
    @State private var selectedModule: ModuleType? = nil
    @State private var rotateOrbit = false
    
    private let orbitRadius: CGFloat = 130
    
    var body: some View {
        ZStack {
            // Background Gradient
            SanctumTheme.bg.ignoresSafeArea()
            
            // Orbit Ring (Görsel)
            Circle()
                .stroke(Color.white.opacity(0.1), lineWidth: 1)
                .frame(width: orbitRadius * 2, height: orbitRadius * 2)
            
            // Orbiting Modules
            ForEach(Array(ModuleType.allCases.enumerated()), id: \.element) { index, module in
                let angle = (2.0 * .pi / Double(ModuleType.allCases.count)) * Double(index) - .pi / 2.0
                let xOffset = orbitRadius * CGFloat(cos(angle))
                let yOffset = orbitRadius * CGFloat(sin(angle))
                
                OrbView(module: module)
                    .offset(x: xOffset, y: yOffset)
                    .onTapGesture {
                        withAnimation(.spring(response: 0.5, dampingFraction: 0.7)) {
                            selectedModule = module
                        }
                    }
            }
            
            // Center Eye
            Circle()
                .fill(
                    RadialGradient(
                        colors: [Theme.primary, Theme.primary.opacity(0.3)],
                        center: .center,
                        startRadius: 0,
                        endRadius: 40
                    )
                )
                .frame(width: 80, height: 80)
                .overlay(
                    Text("ARGUS")
                        .font(.system(size: 12, weight: .black))
                        .foregroundColor(.black)
                )
        }
    }
}

// ORB VIEW (Her modül için yuvarlak buton)
struct OrbView: View {
    let module: ModuleType
    @State private var isPulsing = false
    
    var body: some View {
        ZStack {
            // Glow Effect
            Circle()
                .fill(module.color.opacity(0.3))
                .frame(width: 60, height: 60)
                .blur(radius: 10)
                .scaleEffect(isPulsing ? 1.2 : 1.0)
            
            // Main Circle
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
                    Image(systemName: module.icon)
                        .foregroundColor(.white)
                        .font(.system(size: 20))
                )
            
            // Border
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
```

## 6. HOLO PANEL (Modül Detay Kartı)

```swift
struct HoloPanelView: View {
    let module: ModuleType
    let score: Double // 0-100
    
    var body: some View {
        VStack(spacing: 12) {
            // Header
            HStack {
                Image(systemName: module.icon)
                    .foregroundColor(module.color)
                    .font(.title2)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(module.rawValue)
                        .font(.headline)
                        .foregroundColor(.white)
                    Text(module.description)
                        .font(.caption)
                        .foregroundColor(Theme.textSecondary)
                }
                
                Spacer()
                
                // Score Badge
                Text("\(Int(score))")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundColor(scoreColor)
            }
            
            // Progress Bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.white.opacity(0.1))
                    
                    RoundedRectangle(cornerRadius: 4)
                        .fill(
                            LinearGradient(
                                colors: [module.color, module.color.opacity(0.5)],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geo.size.width * (score / 100))
                }
            }
            .frame(height: 6)
        }
        .padding()
        .glassCard()
    }
    
    private var scoreColor: Color {
        if score >= 70 { return Theme.positive }
        if score >= 40 { return Theme.warning }
        return Theme.negative
    }
}
```

## 7. OUTPUT ÖRNEĞİ

Bu sistem uygulandığında şu görünümü elde edeceksin:

1. **Arka plan**: Siyah-mor radyal gradient (#080b14 → #020205)
2. **Kartlar**: Buzlu cam efekti (ultraThinMaterial + gradient border)
3. **7 modül**: Dairesel orbit üzerinde, her biri kendi neon renginde
4. **Merkez**: Altın renkli "ARGUS" yazılı göz
5. **Animasyonlar**: Modül glow pulse efekti (2 saniye döngü)

---

## API Provider Uyarısı

Veri çekme kodları 11_VERI_CEKME.md promptunda. Bu prompt SADECE UI içindir.

```

---

## Notlar

- Tüm hex renk kodları (`#XXXXXX`) tam olarak belirtilmiştir
- Spacing ve radius değerleri sabit tutulmuştur
- GlassCard efekti 4 katmandan oluşur (base + tint + border + content)
- Orbit radius 130pt olarak sabitlenmiştir
- 7 modül rengi: Orion #00ff9d, Atlas #ffd700, Aether #bd00ff, Hermes #00d0ff, Athena #ff0055, Demeter #8b5a2b, Chiron #ffffff
