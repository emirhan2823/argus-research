import SwiftUI

// MARK: - SANCTUM THEME CONSTANTS
/// Argus Sanctum görsel tema sabitleri.
/// Bloomberg V2 tasarım dili.
struct SanctumTheme {
    // Background: Deep Navy Slate (OLED Friendly)
    static let bg = Color(hex: "0F172A") // Was Void Black
    
    // Core Palette (Bloomberg V2)
    static let hologramBlue = Color(hex: "38BDF8") // Active/Focus
    static let auroraGreen = Color(hex: "34D399") // Positive
    static let titanGold = Color(hex: "FBBF24") // Mythic/Accent
    static let ghostGrey = Color(hex: "94A3B8") // Passive Text
    static let crimsonRed = Color(hex: "F43F5E") // Negative/Alert
    
    // Module Colors (Mapped to V2)
    static let orionColor = hologramBlue     // Technical -> Hologram Blue
    static let atlasColor = titanGold        // Fundamental -> Titan Gold
    static let aetherColor = ghostGrey       // Macro -> Ghost Grey (Neutral base)
    static let athenaColor = titanGold       // Smart Beta -> Titan Gold (Wisdom)
    static let hermesColor = Color(hex: "FB923C") // News -> Orange (distinct from gold)
    static let demeterColor = auroraGreen    // Sectors -> Aurora Green (Growth)
    static let chironColor = Color.white     // System -> White (Ultimate contrast)
    
    // Glass Effect
    static let glassMaterial = Material.thickMaterial
}

// MARK: - MODULE TYPE (Global Markets)
/// Global piyasalar icin Argus modulleri.
enum SanctumModuleType: String, CaseIterable {
    case atlas = "ATLAS"
    case orion = "ORION"
    case aether = "AETHER"
    case hermes = "HERMES"
    case athena = "ATHENA"
    case demeter = "DEMETER"
    case chiron = "CHIRON"
    case prometheus = "PROMETHEUS"
    
    var icon: String {
        switch self {
        case .atlas: return "building.columns.fill"
        case .orion: return "chart.xyaxis.line"
        case .aether: return "globe.europe.africa.fill"
        case .hermes: return "newspaper.fill"
        case .athena: return "brain.head.profile"
        case .demeter: return "leaf.fill"
        case .chiron: return "graduationcap.fill"
        case .prometheus: return "crystal.ball"
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
        case .prometheus: return SanctumTheme.hologramBlue
        }
    }
    
    var description: String {
        switch self {
        case .atlas: return "Temel Analiz & Degerleme"
        case .orion: return "Teknik Indikatorler"
        case .aether: return "Makroekonomik Rejim"
        case .hermes: return "Haber & Duygu Analizi"
        case .athena: return "Akilli Varyans (Smart Beta)"
        case .demeter: return "Sektor & Endustri Analizi"
        case .chiron: return "Ogrenme & Risk Yonetimi"
        case .prometheus: return "5 Gunluk Fiyat Tahmini"
        }
    }
}

// MARK: - BIST MODULE TYPE (Turkiye Markets)
/// BIST piyasasi icin ozel Argus modulleri.
enum SanctumBistModuleType: String, CaseIterable {
    case bilanco = "BILANCO"    // Atlas karsiligi
    case grafik = "GRAFIK"      // Orion karsiligi
    case sirkiye = "SIRKIYE"    // Aether karsiligi
    case kulis = "KULIS"        // Hermes karsiligi
    case faktor = "FAKTOR"      // Athena karsiligi
    case vektor = "VEKTOR"      // Prometheus karsiligi
    case sektor = "SEKTOR"      // Demeter karsiligi
    case rejim = "REJIM"        // Chiron karsiligi
    case moneyflow = "PARA-AKIL" // Para Girisi/Takas
    
    var icon: String {
        switch self {
        case .bilanco: return "building.columns.fill"
        case .grafik: return "chart.xyaxis.line"
        case .sirkiye: return "globe.europe.africa.fill"
        case .kulis: return "newspaper.fill"
        case .faktor: return "brain.head.profile"
        case .vektor: return "crystal.ball"
        case .sektor: return "leaf.fill"
        case .rejim: return "traffic.light"
        case .moneyflow: return "arrow.up.right.circle.fill"
        }
    }
    
    var color: Color {
        switch self {
        case .bilanco: return SanctumTheme.atlasColor
        case .grafik: return SanctumTheme.orionColor
        case .sirkiye: return SanctumTheme.aetherColor
        case .kulis: return SanctumTheme.hermesColor
        case .faktor: return SanctumTheme.athenaColor
        case .vektor: return SanctumTheme.hologramBlue
        case .sektor: return SanctumTheme.demeterColor
        case .rejim: return SanctumTheme.crimsonRed
        case .moneyflow: return Color.green
        }
    }
    
    var description: String {
        switch self {
        case .bilanco: return "Bilanco ve Temel Veriler"
        case .grafik: return "Teknik Analiz ve Indikatorler"
        case .sirkiye: return "Makroekonomik Gostergeler (Sirkiye)"
        case .kulis: return "KAP Haberleri ve Duygu Analizi"
        case .faktor: return "Faktor Yatirimi (Smart Beta)"
        case .vektor: return "Yapay Zeka Fiyat Tahmini"
        case .sektor: return "Sektorel Performans Analizi"
        case .rejim: return "Piyasa Risk Rejimi"
        case .moneyflow: return "Para Giris/Cikis ve Takas Analizi"
        }
    }
}

// MARK: - Type Aliases (Backward Compatibility)
/// ArgusSanctumView icindeki eski referanslar icin
typealias ModuleType = SanctumModuleType
typealias BistModuleType = SanctumBistModuleType
