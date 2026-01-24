import Foundation

// MARK: - TCMB EVDS Data Service
/// Turkiye Cumhuriyet Merkez Bankasi Elektronik Veri Dagitim Sistemi
/// Gercek zamanli makroekonomik veriler: Enflasyon, Faiz, Doviz, Petrol, Altin

actor TCMBDataService {
    static let shared = TCMBDataService()
    
    // MARK: - Configuration
    // API Key: https://evds2.tcmb.gov.tr adresinden ucretsiz alinir
    // Header olarak gonderilmeli: key: API_KEY
    private let baseURL = "https://evds2.tcmb.gov.tr/service/evds"
    
    // API Key - Settings'ten alinacak, simdilik bos
    private var apiKey: String {
        UserDefaults.standard.string(forKey: "tcmb_evds_api_key") ?? ""
    }
    
    // MARK: - Serie Codes (TCMB Veri Kodlari)
    enum SerieCode: String {
        // Doviz Kurlari
        case usdTry = "TP.DK.USD.A.YTL"      // USD/TRY Alis
        case eurTry = "TP.DK.EUR.A.YTL"      // EUR/TRY Alis
        
        // Faiz Oranlari
        case policyRate = "TP.TRB.PFO01"      // Politika Faizi
        case depositRate = "TP.TRB.MF05"      // Mevduat Faizi
        
        // Enflasyon (TUFE)
        case cpiFull = "TP.FG.J0"             // TUFE Genel
        case cpiCore = "TP.FG.J01"            // Cekirdek Enflasyon
        
        // Emtia
        case brentOil = "TP.FTRPIT"           // Brent Petrol
        case goldOz = "TP.FGALT01"            // Altin (Ons/$)
        
        // Piyasa Gostergeleri
        case bist100 = "TP.BSTPAY.XKURY"      // BIST 100 Endeksi
    }
    
    // MARK: - Data Models
    
    struct MacroDataPoint: Codable {
        let date: String
        let value: Double
        
        enum CodingKeys: String, CodingKey {
            case date = "Tarih"
            case value
        }
    }
    
    struct TCMBMacroSnapshot {
        let usdTry: Double?
        let eurTry: Double?
        let policyRate: Double?
        let inflation: Double?
        let coreInflation: Double?
        let brentOil: Double?
        let goldPrice: Double?
        let bist100: Double?
        let timestamp: Date
        
        static let empty = TCMBMacroSnapshot(
            usdTry: nil, eurTry: nil, policyRate: nil,
            inflation: nil, coreInflation: nil,
            brentOil: nil, goldPrice: nil,
            bist100: nil, timestamp: Date()
        )
    }
    
    // MARK: - Cache
    private var cachedSnapshot: TCMBMacroSnapshot?
    private var lastFetchTime: Date?
    private let cacheValiditySeconds: TimeInterval = 3600 // 1 saat
    
    // MARK: - Public API
    
    /// Guncel makro snapshot'i dondur (cache varsa kullan)
    func getMacroSnapshot() async -> TCMBMacroSnapshot {
        // Cache gecerli mi?
        if let cached = cachedSnapshot,
           let lastTime = lastFetchTime,
           Date().timeIntervalSince(lastTime) < cacheValiditySeconds {
            return cached
        }
        
        // API Key yoksa varsayilan degerler don
        guard !apiKey.isEmpty else {
            print("⚠️ TCMB: API Key ayarlanmamis, varsayilan degerler kullaniliyor")
            return TCMBMacroSnapshot.empty
        }
        
        // Yeni veri cek
        return await fetchFreshData()
    }
    
    /// API Key'i ayarla
    func setAPIKey(_ key: String) {
        UserDefaults.standard.set(key, forKey: "tcmb_evds_api_key")
        cachedSnapshot = nil // Cache'i invalidate et
    }
    
    /// API baglantisini test et
    func testConnection() async -> Bool {
        guard !apiKey.isEmpty else { return false }
        
        do {
            let _ = try await fetchSerie(.usdTry, days: 1)
            return true
        } catch {
            print("❌ TCMB API baglanti hatasi: \(error)")
            return false
        }
    }
    
    // MARK: - Private Methods
    
    private func fetchFreshData() async -> TCMBMacroSnapshot {
        async let usd = fetchLatestValue(.usdTry)
        async let eur = fetchLatestValue(.eurTry)
        async let policy = fetchLatestValue(.policyRate)
        async let cpi = fetchLatestValue(.cpiFull)
        async let core = fetchLatestValue(.cpiCore)
        async let oil = fetchLatestValue(.brentOil)
        async let gold = fetchLatestValue(.goldOz)
        async let bist = fetchLatestValue(.bist100)
        
        let snapshot = TCMBMacroSnapshot(
            usdTry: await usd,
            eurTry: await eur,
            policyRate: await policy,
            inflation: await cpi,
            coreInflation: await core,
            brentOil: await oil,
            goldPrice: await gold,
            bist100: await bist,
            timestamp: Date()
        )
        
        cachedSnapshot = snapshot
        lastFetchTime = Date()
        
        print("✅ TCMB: Makro veriler guncellendi")
        print("   USD/TRY: \(snapshot.usdTry ?? 0), Faiz: %\(snapshot.policyRate ?? 0), Enflasyon: %\(snapshot.inflation ?? 0)")
        
        return snapshot
    }
    
    private func fetchLatestValue(_ serie: SerieCode) async -> Double? {
        do {
            let data = try await fetchSerie(serie, days: 7)
            return data.last?.value
        } catch {
            print("⚠️ TCMB \(serie.rawValue) veri alinamadi: \(error)")
            return nil
        }
    }
    
    private func fetchSerie(_ serie: SerieCode, days: Int) async throws -> [MacroDataPoint] {
        // Tarih araligi
        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -days, to: endDate)!
        
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "dd-MM-yyyy"
        
        let startStr = dateFormatter.string(from: startDate)
        let endStr = dateFormatter.string(from: endDate)
        
        // URL olustur
        let urlString = "\(baseURL)/series=\(serie.rawValue)&startDate=\(startStr)&endDate=\(endStr)&type=json"
        
        guard let url = URL(string: urlString) else {
            throw TCMBError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.setValue(apiKey, forHTTPHeaderField: "key")
        request.timeoutInterval = 10
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw TCMBError.apiError
        }
        
        // Parse JSON with JSONSerialization
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let items = json["items"] as? [[String: Any]] else {
            throw TCMBError.parseError
        }
        
        return items.compactMap { item -> MacroDataPoint? in
            guard let valueStr = item[serie.rawValue] as? String,
                  let value = Double(valueStr) else { return nil }
            return MacroDataPoint(date: item["Tarih"] as? String ?? "", value: value)
        }
    }
    
    enum TCMBError: Error {
        case invalidURL
        case apiError
        case parseError
    }
}

// MARK: - Sirkiye Engine Integration

extension TCMBDataService {
    /// SirkiyeEngine icin input olusturur. Kritik veri (USD/TRY) yoksa nil doner.
    func getSirkiyeInput() async -> SirkiyeEngine.SirkiyeInput? {
        let snapshot = await getMacroSnapshot()
        
        // Kritik veriler yoksa analiz yapma (Clean Rice Protocol)
        guard let usdTry = snapshot.usdTry, usdTry > 0 else { return nil }
        
        // Onceki gun tahmini (Veri varsa)
        let previousUsdTry = usdTry * 0.99
        
        return SirkiyeEngine.SirkiyeInput(
            usdTry: usdTry,
            usdTryPrevious: previousUsdTry,
            dxy: 104.0, // DXY icin ayri kaynak gerekli (Sabit deger - Bunu da temizlemek lazim ama TCMB disi)
            brentOil: snapshot.brentOil,
            globalVix: 15.0,
            newsSnapshot: nil,
            currentInflation: snapshot.inflation,
            policyRate: snapshot.policyRate,
            xu100Change: nil,
            goldPrice: snapshot.goldPrice
        )
    }
}
