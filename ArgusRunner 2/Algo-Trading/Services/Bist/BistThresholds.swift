import Foundation

// MARK: - BIST Thresholds Configuration
/// Tüm BIST engine'lerinde kullanılan eşik değerleri
/// Magic number'lar yerine merkezi yapılandırma

struct BistThresholds {
    
    // MARK: - Sektör Momentum Eşikleri
    struct Momentum {
        static let strong: Double = 2.0        // Günlük değişim > 2% = Güçlü
        static let positive: Double = 0.5      // Günlük değişim > 0.5% = Pozitif
        static let negativeUpper: Double = -0.5 // Günlük değişim > -0.5% = Nötr
        static let negative: Double = -2.0      // Günlük değişim > -2% = Negatif
    }
    
    // MARK: - Hacim Eşikleri
    struct Volume {
        static let highRatio: Double = 2.0      // Ortalama hacmin 2x üzeri = Yüksek hacim
        static let moderateRatio: Double = 1.5  // Ortalama hacmin 1.5x üzeri = Orta hacim
        static let lowRatio: Double = 0.5       // Ortalama hacmin 0.5x altı = Düşük hacim
    }
    
    // MARK: - Puanlama Değerleri
    struct Scoring {
        // Volume Puanları
        static let highVolumeScore: Double = 25
        static let moderateVolumeScore: Double = 15
        static let lowVolumeDeduction: Double = -10
        
        // Birikim/Dağıtım Puanları
        static let accumulationScore: Double = 20
        static let distributionDeduction: Double = -20
        
        // A/D Göstergesi Puanları
        static let bullishFlowScore: Double = 15
        static let bearishFlowDeduction: Double = -15
        
        // Akış Durumu Eşikleri
        static let strongInflowThreshold: Double = 75
        static let inflowThreshold: Double = 60
        static let neutralThreshold: Double = 40
        static let outflowThreshold: Double = 25
    }
    
    // MARK: - Değerleme Eşikleri (Value)
    struct Valuation {
        // P/E (F/K)
        static let deepValuePE: Double = 5.0    // F/K < 5 = Derin Değer
        static let valuePE: Double = 10.0       // F/K < 10 = Ucuz
        static let normalPE: Double = 20.0      // F/K < 20 = Normal
        
        static let deepValuePEScore: Double = 25
        static let valuePEScore: Double = 15
        static let expensivePEDeduction: Double = -15
        
        // P/B (PD/DD)
        static let bookValuePB: Double = 1.0    // PD/DD < 1 = Defter altı
        static let fairValuePB: Double = 1.5    // PD/DD < 1.5 = Uygun
        
        static let bookValuePBScore: Double = 25
        static let fairValuePBScore: Double = 10
    }
    
    // MARK: - Momentum Eşikleri (Return)
    struct Returns {
        static let strong20Day: Double = 15.0   // 20G getiri > %15 = Güçlü
        static let positive20Day: Double = 5.0  // 20G getiri > %5 = Pozitif
        static let neutral20Day: Double = 0.0   // 20G getiri > %0 = Nötr
        static let weak20Day: Double = -10.0    // 20G getiri > -%10 = Zayıf
        
        static let strong5Day: Double = 5.0     // 5G getiri > %5
        static let weak5Day: Double = -5.0      // 5G getiri < -%5
    }
    
    // MARK: - Kalite Eşikleri
    struct Quality {
        // ROE
        static let excellentROE: Double = 20.0
        static let goodROE: Double = 15.0
        static let normalROE: Double = 10.0
        
        // Net Kar Marjı
        static let highMargin: Double = 15.0
        static let goodMargin: Double = 10.0
        
        // Borç/Özkaynak
        static let lowDebt: Double = 0.5
        static let highDebt: Double = 1.5
    }
    
    // MARK: - Temettü Eşikleri
    struct Dividend {
        static let highYield: Double = 8.0      // Verim > %8 = Yüksek
        static let goodYield: Double = 5.0      // Verim > %5 = İyi
        static let normalYield: Double = 3.0    // Verim > %3 = Normal
        
        static let continuityYears: Int = 4     // 4+ yıl sürekli temettü = bonus
    }
    
    // MARK: - A/D Gösterge Eşikleri
    struct ADIndicator {
        static let bullishThreshold: Double = 0.6
        static let bearishThreshold: Double = -0.6
    }
    
    // MARK: - Rotasyon Eşikleri
    struct Rotation {
        static let riskOnThreshold: Double = 1.0     // Ortalama değişim > %1 = Risk On
        static let riskOffThreshold: Double = -1.0   // Ortalama değişim < -%1 = Risk Off
        static let sectorLeadThreshold: Double = 0.5 // Sektör liderliği için minimum değişim
    }
}
