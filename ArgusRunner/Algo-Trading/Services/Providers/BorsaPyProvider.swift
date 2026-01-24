import Foundation

// MARK: - BorsaPy Swift Provider
// Türk finansal piyasaları için veri sağlayıcı
// borsapy Python kütüphanesinin Swift portu
// https://github.com/saidsurucu/borsapy

actor BorsaPyProvider {
    static let shared = BorsaPyProvider()
    
    // MARK: - API URLs
    private let isyatirimBaseURL = "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common"
    private let dovizBaseURL = "https://api.doviz.com/api/v12"
    
    // Doviz.com token (fallback)
    private var dovizToken: String = "3e75d7fabf1c50c8b962626dd0e5ea22d8000815e1b0920d0a26afd77fcd6609"
    
    // Cache
    private var quoteCache: [String: (quote: BistQuote, timestamp: Date)] = [:]
    private var fxCache: [String: (rate: FXRate, timestamp: Date)] = [:]
    private let cacheTTL: TimeInterval = 60 // 1 dakika
    
    private init() {}
    
    // MARK: - BIST Hisse Verileri (İş Yatırım)
    
    /// BIST hissesi için anlık fiyat çeker
    /// - Parameter symbol: Hisse kodu (örn: "THYAO", ".IS" suffix'e ihtiyaç yok)
    func getBistQuote(symbol: String) async throws -> BistQuote {
        let cleanSymbol = symbol.uppercased()
            .replacingOccurrences(of: ".IS", with: "")
            .replacingOccurrences(of: ".E", with: "")
        
        // Cache kontrolü
        if let cached = quoteCache[cleanSymbol],
           Date().timeIntervalSince(cached.timestamp) < cacheTTL {
            return cached.quote
        }
        
        let url = URL(string: "\(isyatirimBaseURL)/ChartData.aspx/OneEndeks?endeks=\(cleanSymbol)")!
        
        var request = URLRequest(url: url)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", forHTTPHeaderField: "User-Agent")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw BorsaPyError.requestFailed
        }
        
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        
        guard let json = json else {
            throw BorsaPyError.invalidResponse
        }
        
        let quote = BistQuote(
            symbol: cleanSymbol,
            last: json["son"] as? Double ?? json["close"] as? Double ?? 0,
            open: json["acilis"] as? Double ?? json["open"] as? Double ?? 0,
            high: json["yuksek"] as? Double ?? json["high"] as? Double ?? 0,
            low: json["dusuk"] as? Double ?? json["low"] as? Double ?? 0,
            previousClose: json["oncekiKapanis"] as? Double ?? json["prevClose"] as? Double ?? 0,
            volume: json["hacim"] as? Double ?? json["volume"] as? Double ?? 0,
            change: json["yuzdeDegisim"] as? Double ?? json["change"] as? Double ?? 0,
            bid: json["alis"] as? Double ?? 0,
            ask: json["satis"] as? Double ?? 0,
            timestamp: Date()
        )
        
        quoteCache[cleanSymbol] = (quote, Date())
        return quote
    }
    
    /// BIST endeks verisi çeker (XU100, XU030, vb.)
    func getBistIndex(code: String) async throws -> BistQuote {
        return try await getBistQuote(symbol: code)
    }
    
    /// BIST hisse geçmiş verisi çeker
    func getBistHistory(symbol: String, days: Int = 30) async throws -> [BorsaPyCandle] {
        let cleanSymbol = symbol.uppercased()
            .replacingOccurrences(of: ".IS", with: "")
            .replacingOccurrences(of: ".E", with: "")
        
        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -days, to: endDate)!
        
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "dd-MM-yyyy"
        
        let startStr = dateFormatter.string(from: startDate)
        let endStr = dateFormatter.string(from: endDate)
        
        // 2024-2025 Güncel Endpoint: Data.aspx/HisseTekil
        // Eski: ChartData.aspx/IndexHistoricalAll (artık çalışmıyor)
        let urlString = "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseTekil?hisse=\(cleanSymbol)&startdate=\(startStr)&enddate=\(endStr)"
        
        guard let url = URL(string: urlString) else {
            throw BorsaPyError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", forHTTPHeaderField: "User-Agent")
        request.setValue("https://www.isyatirim.com.tr", forHTTPHeaderField: "Referer")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // response kontrolü
        guard let httpResponse = response as? HTTPURLResponse else {
            throw BorsaPyError.requestFailed
        }
        
        // 200 dışında bir kod gelirse hata fırlat
        guard httpResponse.statusCode == 200 else {
            print("⚠️ BorsaPy: HTTP \(httpResponse.statusCode) for \(cleanSymbol)")
            throw BorsaPyError.requestFailed
        }
        
        // Boş veri kontrolü
        guard !data.isEmpty else {
            print("⚠️ BorsaPy: Empty data for \(cleanSymbol)")
            throw BorsaPyError.invalidResponse
        }
        
        // JSON parsing - yeni format: { "d": [ {...}, {...} ] } veya direkt array
        let jsonObject = try JSONSerialization.jsonObject(with: data)
        
        var jsonArray: [[String: Any]]?
        
        if let wrapper = jsonObject as? [String: Any],
           let d = wrapper["d"] as? [[String: Any]] {
            // Yeni format: { "d": [...] }
            jsonArray = d
        } else if let directArray = jsonObject as? [[String: Any]] {
            // Eski format: [...]
            jsonArray = directArray
        }
        
        guard let items = jsonArray else {
            print("⚠️ BorsaPy: Could not parse JSON for \(cleanSymbol)")
            throw BorsaPyError.invalidResponse
        }
        
        print("✅ BorsaPy: \(items.count) candles for \(cleanSymbol)")
        
        return items.compactMap { item -> BorsaPyCandle? in
            // Yeni format field'ları: HGDG_TARIH, HGDG_KAPANIS, HGDG_ACILIS, HGDG_DUSUK, HGDG_YUKSEK, HGDG_HACIM
            // Eski format: date, open, high, low, close, volume
            
            let dateStr = item["HGDG_TARIH"] as? String ?? item["date"] as? String
            let open = item["HGDG_ACILIS"] as? Double ?? item["open"] as? Double ?? 0
            let high = item["HGDG_YUKSEK"] as? Double ?? item["high"] as? Double ?? 0
            let low = item["HGDG_DUSUK"] as? Double ?? item["low"] as? Double ?? 0
            let close = item["HGDG_KAPANIS"] as? Double ?? item["close"] as? Double ?? 0
            let volume = item["HGDG_HACIM"] as? Double ?? item["volume"] as? Double ?? 0
            
            guard let dateString = dateStr else { return nil }
            
            // Tarih parse - birden fazla format dene
            let dateFormatters = [
                "yyyy-MM-dd'T'HH:mm:ss",
                "yyyy-MM-dd",
                "dd.MM.yyyy"
            ]
            
            var parsedDate: Date?
            for format in dateFormatters {
                let formatter = DateFormatter()
                formatter.dateFormat = format
                formatter.locale = Locale(identifier: "tr_TR")
                if let d = formatter.date(from: String(dateString.prefix(format.count == 10 ? 10 : 19))) {
                    parsedDate = d
                    break
                }
            }
            
            guard let date = parsedDate else { return nil }
            
            return BorsaPyCandle(
                date: date,
                open: open,
                high: high,
                low: low,
                close: close,
                volume: volume
            )
        }
    }
    
    // MARK: - Döviz Kurları (Doviz.com)
    
    /// Döviz kuru çeker (USD, EUR, GBP, vb.)
    func getFXRate(asset: String) async throws -> FXRate {
        let cleanAsset = asset.uppercased()
        
        // Cache kontrolü
        if let cached = fxCache[cleanAsset],
           Date().timeIntervalSince(cached.timestamp) < cacheTTL {
            return cached.rate
        }
        
        let url = URL(string: "\(dovizBaseURL)/assets/\(cleanAsset)/daily?limit=1")!
        
        var request = URLRequest(url: url)
        request.setValue("Bearer \(dovizToken)", forHTTPHeaderField: "Authorization")
        request.setValue("https://www.doviz.com", forHTTPHeaderField: "Origin")
        request.setValue("https://www.doviz.com/", forHTTPHeaderField: "Referer")
        request.setValue("*/*", forHTTPHeaderField: "Accept")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw BorsaPyError.requestFailed
        }
        
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dataObj = json["data"] as? [String: Any],
              let archive = dataObj["archive"] as? [[String: Any]],
              let latest = archive.first else {
            throw BorsaPyError.invalidResponse
        }
        
        let rate = FXRate(
            symbol: cleanAsset,
            last: latest["close"] as? Double ?? 0,
            open: latest["open"] as? Double ?? 0,
            high: latest["highest"] as? Double ?? 0,
            low: latest["lowest"] as? Double ?? 0,
            timestamp: Date()
        )
        
        fxCache[cleanAsset] = (rate, Date())
        return rate
    }
    
    /// Altın fiyatı çeker (gram-altin, ons)
    func getGoldPrice(type: GoldType = .gramAltin) async throws -> FXRate {
        let asset = type.rawValue
        
        let url = URL(string: "\(dovizBaseURL)/assets/\(asset)/daily?limit=1")!
        
        var request = URLRequest(url: url)
        request.setValue("Bearer \(dovizToken)", forHTTPHeaderField: "Authorization")
        request.setValue("https://altin.doviz.com", forHTTPHeaderField: "Origin")
        request.setValue("https://altin.doviz.com/", forHTTPHeaderField: "Referer")
        request.setValue("*/*", forHTTPHeaderField: "Accept")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw BorsaPyError.requestFailed
        }
        
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dataObj = json["data"] as? [String: Any],
              let archive = dataObj["archive"] as? [[String: Any]],
              let latest = archive.first else {
            throw BorsaPyError.invalidResponse
        }
        
        return FXRate(
            symbol: asset,
            last: latest["close"] as? Double ?? 0,
            open: latest["open"] as? Double ?? 0,
            high: latest["highest"] as? Double ?? 0,
            low: latest["lowest"] as? Double ?? 0,
            timestamp: Date()
        )
    }
    
    /// Brent petrol fiyatı çeker
    func getBrentPrice() async throws -> FXRate {
        return try await getFXRate(asset: "BRENT")
    }
    
    /// FX geçmiş verisi çeker
    func getFXHistory(asset: String, days: Int = 30) async throws -> [FXCandle] {
        let endTime = Int(Date().timeIntervalSince1970)
        let startTime = endTime - (days * 86400)
        
        let url = URL(string: "\(dovizBaseURL)/assets/\(asset)/archive?start=\(startTime)&end=\(endTime)")!
        
        var request = URLRequest(url: url)
        request.setValue("Bearer \(dovizToken)", forHTTPHeaderField: "Authorization")
        request.setValue("https://www.doviz.com", forHTTPHeaderField: "Origin")
        request.setValue("*/*", forHTTPHeaderField: "Accept")
        
        let (data, _) = try await URLSession.shared.data(for: request)
        
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dataObj = json["data"] as? [String: Any],
              let archive = dataObj["archive"] as? [[String: Any]] else {
            throw BorsaPyError.invalidResponse
        }
        
        return archive.compactMap { item -> FXCandle? in
            guard let timestamp = item["update_date"] as? Double else {
                return nil
            }
            
            return FXCandle(
                date: Date(timeIntervalSince1970: timestamp),
                open: item["open"] as? Double ?? 0,
                high: item["highest"] as? Double ?? 0,
                low: item["lowest"] as? Double ?? 0,
                close: item["close"] as? Double ?? 0
            )
        }
    }
    
    // MARK: - BIST Finansal Veriler (İş Yatırım)
    
    private let stockInfoURL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx"
    
    /// Temettü geçmişi çeker
    func getDividends(symbol: String) async throws -> [BistDividend] {
        let cleanSymbol = symbol.uppercased()
            .replacingOccurrences(of: ".IS", with: "")
            .replacingOccurrences(of: ".E", with: "")
        
        let data = try await fetchSermayeData(symbol: cleanSymbol)
        return parseDividends(from: data)
    }
    
    /// Sermaye artırımları (split) geçmişi çeker
    func getCapitalIncreases(symbol: String) async throws -> [BistCapitalIncrease] {
        let cleanSymbol = symbol.uppercased()
            .replacingOccurrences(of: ".IS", with: "")
            .replacingOccurrences(of: ".E", with: "")
        
        let data = try await fetchSermayeData(symbol: cleanSymbol)
        return parseCapitalIncreases(from: data)
    }
    
    /// İş Yatırım sermaye artırımları API'sini çağırır
    private func fetchSermayeData(symbol: String) async throws -> [[String: Any]] {
        guard let url = URL(string: "\(stockInfoURL)/GetSermayeArttirimlari") else {
            throw BorsaPyError.invalidURL
        }
        
        let payload: [String: Any] = [
            "hisseKodu": symbol,
            "hisseTanimKodu": "",
            "yil": 0,
            "zaman": "HEPSI",
            "endeksKodu": "09",
            "sektorKodu": ""
        ]
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json; charset=UTF-8", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json, text/javascript, */*; q=0.01", forHTTPHeaderField: "Accept")
        request.setValue("XMLHttpRequest", forHTTPHeaderField: "X-Requested-With")
        request.setValue("https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse=\(symbol)", forHTTPHeaderField: "Referer")
        request.setValue("https://www.isyatirim.com.tr", forHTTPHeaderField: "Origin")
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw BorsaPyError.requestFailed
        }
        
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dValue = json["d"] else {
            throw BorsaPyError.invalidResponse
        }
        
        // Response: {"d": "[{...}, {...}]"} - JSON string içinde JSON
        if let jsonString = dValue as? String,
           let jsonData = jsonString.data(using: .utf8),
           let array = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]] {
            return array
        }
        
        if let array = dValue as? [[String: Any]] {
            return array
        }
        
        return []
    }
    
    private func parseDividends(from items: [[String: Any]]) -> [BistDividend] {
        var dividends: [BistDividend] = []
        
        for item in items {
            // Tip 04 = Nakit Temettü
            guard let tip = item["SHT_KODU"] as? String, tip == "04" else { continue }
            
            guard let timestamp = item["SHHE_TARIH"] as? Double else { continue }
            let date = Date(timeIntervalSince1970: timestamp / 1000)
            
            let grossRate = (item["SHHE_NAKIT_TM_ORAN"] as? Double) ?? 0
            let netRate = (item["SHHE_NAKIT_TM_ORAN_NET"] as? Double) ?? 0
            let totalDividend = (item["SHHE_NAKIT_TM_TUTAR"] as? Double) ?? 0
            
            dividends.append(BistDividend(
                date: date,
                grossRate: grossRate,
                netRate: netRate,
                totalAmount: totalDividend,
                perShare: grossRate / 100
            ))
        }
        
        return dividends.sorted { $0.date > $1.date }
    }
    
    private func parseCapitalIncreases(from items: [[String: Any]]) -> [BistCapitalIncrease] {
        var increases: [BistCapitalIncrease] = []
        
        for item in items {
            // Tip 03 = Bedelli/Bedelsiz, Tip 09 = Bedelsiz Temettü
            guard let tip = item["SHT_KODU"] as? String, ["03", "09"].contains(tip) else { continue }
            
            guard let timestamp = item["SHHE_TARIH"] as? Double else { continue }
            let date = Date(timeIntervalSince1970: timestamp / 1000)
            
            let capital = (item["HSP_BOLUNME_SONRASI_SERMAYE"] as? Double) ?? 0
            let rightsIssue = (item["SHHE_BDLI_ORAN"] as? Double) ?? 0
            let bonusCapital = (item["SHHE_BDSZ_IK_ORAN"] as? Double) ?? 0
            let bonusDividend = (item["SHHE_BDSZ_TM_ORAN"] as? Double) ?? 0
            
            increases.append(BistCapitalIncrease(
                date: date,
                capitalAfter: capital,
                rightsIssueRate: rightsIssue,
                bonusFromCapitalRate: bonusCapital,
                bonusFromDividendRate: bonusDividend
            ))
        }
        
        return increases.sorted { $0.date > $1.date }
    }
    
    /// XU100 (BIST 100) endeks verisi çeker
    func getXU100() async throws -> BistQuote {
        return try await getBistQuote(symbol: "XU100")
    }
    
    /// XU030 (BIST 30) endeks verisi çeker  
    func getXU030() async throws -> BistQuote {
        return try await getBistQuote(symbol: "XU030")
    }
    
    /// Sektör endeksi verisi çeker (XBANK, XUSIN, XGMYO, XULAS, XTEKS)
    func getSectorIndex(code: String) async throws -> BistQuote {
        return try await getBistQuote(symbol: code)
    }
    
    /// Tüm ana sektör endekslerini çeker
    func getAllSectorIndices() async throws -> [String: BistQuote] {
        let sectors = ["XBANK", "XUSIN", "XGMYO", "XULAS", "XTEKS", "XELKT", "XUHIZ"]
        var results: [String: BistQuote] = [:]
        
        for sector in sectors {
            if let quote = try? await getSectorIndex(code: sector) {
                results[sector] = quote
            }
        }
        
        return results
    }
    
    // MARK: - Mali Tablolar (İş Yatırım)
    
    /// Şirketin mali tablolarını çeker (HTML Scraping + Veri Türetme)
    /// Not: Detaylı bilanço endpointi kapalı olduğu için veriler rasyolar üzerinden geri hesaplanır.
    func getFinancialStatements(symbol: String) async throws -> BistFinancials {
        let cleanSymbol = symbol.uppercased()
            .replacingOccurrences(of: ".IS", with: "")
            .replacingOccurrences(of: ".E", with: "")
        
        // 1. HTML Scraping (Rasyolar)
        let pageURL = URL(string: "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse=\(cleanSymbol)")!
        var request = URLRequest(url: pageURL)
        request.setValue("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", forHTTPHeaderField: "Accept")
        request.setValue("Mozilla/5.0", forHTTPHeaderField: "User-Agent")
        
        var pe: Double?
        var pb: Double?
        var Period: String = ""
        
        if let (data, response) = try? await URLSession.shared.data(for: request),
           let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200,
           let html = String(data: data, encoding: .utf8) {
            
            // Tabloyu Bul: data-csvname="finansaloranlargerceklesen"
            let tablePattern = #"data-csvname="finansaloranlargerceklesen"[^>]*>.*?<tbody>(.*?)</tbody>"#
            let tdPattern = #"<td>(.*?)</td>"#
            
            if let regex = try? NSRegularExpression(pattern: tablePattern, options: [.dotMatchesLineSeparators]),
               let match = regex.firstMatch(in: html, range: NSRange(location: 0, length: html.utf16.count)),
               let range = Range(match.range(at: 1), in: html) {
                
                let tbody = String(html[range])
                
                if let cellRegex = try? NSRegularExpression(pattern: tdPattern, options: [.dotMatchesLineSeparators]) {
                    let matches = cellRegex.matches(in: tbody, range: NSRange(location: 0, length: tbody.utf16.count))
                    let cells = matches.compactMap { m -> String? in
                        guard let r = Range(m.range(at: 1), in: tbody) else { return nil }
                        return String(tbody[r])
                    }
                    
                    if cells.count >= 7 {
                        func parseDouble(_ s: String) -> Double? {
                            let cleaned = s.replacingOccurrences(of: ".", with: "").replacingOccurrences(of: ",", with: ".")
                            return Double(cleaned)
                        }
                        
                        pe = parseDouble(cells[2])
                        pb = parseDouble(cells[5])
                        Period = cells[6]
                    }
                }
            }
        }
        
        // 2. Veri Zenginleştirme (Reverse Calculation)
        // Sermaye ve Fiyat -> Market Cap -> Net Kar & Özkaynak
        
        var calculatedMarketCap: Double?
        var derivedNetProfit: Double?
        var derivedEquity: Double?
        
        // Sermaye Verisi
        let capitalData = try? await fetchSermayeData(symbol: cleanSymbol)
        // En güncel sermayeyi bul (Tarihe göre sırala veya sonuncuyu al)
        let latestCapital = capitalData?.compactMap { $0["HSP_BOLUNME_SONRASI_SERMAYE"] as? Double }.first
        
        // Anlık Fiyat
        let quote = try? await getBistQuote(symbol: cleanSymbol)
        
        if let cap = latestCapital, let price = quote?.last, price > 0 {
            let mCap = cap * price
            calculatedMarketCap = mCap
            
            // Net Kar = Market Cap / FK
            if let p = pe, p > 0 {
                derivedNetProfit = mCap / p
            }
            
            // Özkaynak = Market Cap / PD/DD
            if let b = pb, b > 0 {
                derivedEquity = mCap / b
            }
            
            print("✅ BorsaPy Zenginleştirme: \(cleanSymbol) -> MCup: \(mCap.formatted()), NetKar: \(derivedNetProfit?.formatted() ?? "-"), Özkaynak: \(derivedEquity?.formatted() ?? "-")")
        }
        
        // ROE Hesaplama (Türetilmiş)
        var derivedROE: Double?
        if let profit = derivedNetProfit, let equity = derivedEquity, equity > 0 {
            derivedROE = (profit / equity) * 100
        }
        
        // EPS (Hisse Başına Kar) Hesaplama
        // Net Kar / Ödenmiş Sermaye (kabaca lot sayısı olarak kabul edilir)
        var derivedEPS: Double?
        if let profit = derivedNetProfit, let capital = latestCapital, capital > 0 {
            derivedEPS = profit / capital
        }
        
        return BistFinancials(
            symbol: cleanSymbol,
            period: Period.isEmpty ? "N/A" : Period,
            // Türetilmiş Veriler
            netProfit: derivedNetProfit,
            ebitda: nil, // Türetilemedi
            revenue: nil, // Türetilemedi
            grossProfit: nil,
            operatingProfit: nil,
            totalAssets: nil,
            totalEquity: derivedEquity,
            totalDebt: nil,
            shortTermDebt: nil,
            longTermDebt: nil,
            currentAssets: nil,
            cash: nil,
            // Oranlar
            roe: derivedROE,
            roa: nil,
            currentRatio: nil,
            debtToEquity: nil,
            netMargin: nil,
            // Değerleme
            pe: pe,
            pb: pb,
            marketCap: calculatedMarketCap,
            eps: derivedEPS,
            timestamp: Date()
        )
    }
    
    /// Analist önerilerini çeker (HTML Scraping - Fallback Yöntemi)
    func getAnalystRecommendations(symbol: String) async throws -> BistAnalystConsensus {
        let cleanSymbol = symbol.uppercased()
            .replacingOccurrences(of: ".IS", with: "")
            .replacingOccurrences(of: ".E", with: "")
        
        // Şirket Kartı Sayfası
        let pageURL = URL(string: "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse=\(cleanSymbol)")!
        
        var request = URLRequest(url: pageURL)
        request.setValue("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", forHTTPHeaderField: "Accept")
        request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15", forHTTPHeaderField: "User-Agent")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw BorsaPyError.requestFailed
        }
        
        guard let html = String(data: data, encoding: .utf8) else {
            throw BorsaPyError.invalidResponse
        }
        
        // Regex Patterns
        // 1. Öneri: <span class="al" title="" id="Oneri_Aciklama">AL</span>
        // Not: Class "al", "sat", "tut" olabilir, id sabit.
        let recommendationPattern = #"id="Oneri_Aciklama">([^<]+)</span>"#
        
        // 2. Hedef Fiyat: <li>Hedef Fiyat <span>580,00</span></li>
        let targetPattern = #"<li>Hedef Fiyat <span>([\d,]+)</span></li>"#
        
        // Helper function for regex
        func extract(pattern: String, from text: String) -> String? {
            guard let regex = try? NSRegularExpression(pattern: pattern, options: []) else { return nil }
            let nsString = text as NSString
            let results = regex.matches(in: text, options: [], range: NSRange(location: 0, length: nsString.length))
            if let match = results.first {
                return nsString.substring(with: match.range(at: 1))
            }
            return nil
        }
        
        let rawRec = extract(pattern: recommendationPattern, from: html)?.uppercased() ?? "NÖTR"
        let rawTarget = extract(pattern: targetPattern, from: html)
        
        // Parse Values
        var buyCount = 0
        var holdCount = 0
        var sellCount = 0
        
        if rawRec.contains("AL") || rawRec.contains("BUY") {
            buyCount = 1
        } else if rawRec.contains("SAT") || rawRec.contains("SELL") {
            sellCount = 1
        } else {
            holdCount = 1
        }
        
        // Turkish locale number parsing (coma -> dot)
        let targetPrice: Double? = {
            guard let val = rawTarget else { return nil }
            let cleaned = val.replacingOccurrences(of: ".", with: "").replacingOccurrences(of: ",", with: ".") // 1.000,50 -> 1000.50
            return Double(cleaned)
        }()
        
        // Tek kaynak olduğu için total=1. İleride başka kaynaklar eklenirse burası artar.
        print("✅ BorsaPy Scraping: \(cleanSymbol) -> \(rawRec) / Hedef: \(targetPrice ?? 0)")
        
        return BistAnalystConsensus(
            symbol: cleanSymbol,
            buyCount: buyCount,
            holdCount: holdCount,
            sellCount: sellCount,
            totalAnalysts: (buyCount + holdCount + sellCount > 0) ? 1 : 0, // Eğer veri yoksa 0 olur
            averageTargetPrice: targetPrice,
            highTargetPrice: targetPrice,
            lowTargetPrice: targetPrice,
            timestamp: Date()
        )
    }

    private let tcmbCalcURL = "https://appg.tcmb.gov.tr/KIMENFH/enflasyon/hesapla"
    
    /// Enflasyon hesaplar (TCMB resmi API)
    /// - Parameters:
    ///   - amount: Başlangıç tutarı (TL)
    ///   - startYear: Başlangıç yılı
    ///   - startMonth: Başlangıç ayı (1-12)
    ///   - endYear: Bitiş yılı
    ///   - endMonth: Bitiş ayı (1-12)
    func calculateInflation(
        amount: Double,
        startYear: Int,
        startMonth: Int,
        endYear: Int,
        endMonth: Int
    ) async throws -> InflationResult {
        
        let payload: [String: Any] = [
            "baslangicYil": String(startYear),
            "baslangicAy": String(startMonth),
            "bitisYil": String(endYear),
            "bitisAy": String(endMonth),
            "malSepeti": String(amount)
        ]
        
        guard let url = URL(string: tcmbCalcURL) else {
            throw BorsaPyError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("https://herkesicin.tcmb.gov.tr", forHTTPHeaderField: "Origin")
        request.setValue("https://herkesicin.tcmb.gov.tr/", forHTTPHeaderField: "Referer")
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw BorsaPyError.requestFailed
        }
        
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw BorsaPyError.invalidResponse
        }
        
        return InflationResult(
            startDate: "\(startYear)-\(String(format: "%02d", startMonth))",
            endDate: "\(endYear)-\(String(format: "%02d", endMonth))",
            initialValue: amount,
            finalValue: parseDouble(json["yeniSepetDeger"]),
            totalYears: json["toplamYil"] as? Int ?? 0,
            totalMonths: json["toplamAy"] as? Int ?? 0,
            totalChange: parseDouble(json["toplamDegisim"]),
            avgYearlyInflation: parseDouble(json["ortalamaYillikEnflasyon"]),
            startCPI: parseDouble(json["ilkYilTufe"]),
            endCPI: parseDouble(json["sonYilTufe"])
        )
    }
    
    /// Son enflasyon oranını çeker (basitleştirilmiş)
    func getLatestInflation() async throws -> Double {
        // Son 12 aylık enflasyonu hesapla
        let now = Date()
        let calendar = Calendar.current
        let currentYear = calendar.component(.year, from: now)
        let currentMonth = calendar.component(.month, from: now)
        
        // 1 yıl öncesi
        let startYear = currentMonth == 1 ? currentYear - 2 : currentYear - 1
        let startMonth = currentMonth == 1 ? 12 : currentMonth - 1
        let endYear = currentMonth == 1 ? currentYear - 1 : currentYear
        let endMonth = currentMonth == 1 ? 12 : currentMonth - 1
        
        let result = try await calculateInflation(
            amount: 100,
            startYear: startYear,
            startMonth: startMonth,
            endYear: endYear,
            endMonth: endMonth
        )
        
        return result.totalChange
    }
    
    private func parseDouble(_ value: Any?) -> Double {
        if let d = value as? Double { return d }
        if let s = value as? String {
            // Türkçe format: "47,09" -> 47.09
            let cleaned = s.replacingOccurrences(of: ",", with: ".")
                .replacingOccurrences(of: "%", with: "")
                .trimmingCharacters(in: .whitespaces)
            return Double(cleaned) ?? 0
        }
        if let i = value as? Int { return Double(i) }
        return 0
    }
}

// MARK: - Models

struct BistQuote: Codable, Sendable {
    let symbol: String
    let last: Double
    let open: Double
    let high: Double
    let low: Double
    let previousClose: Double
    let volume: Double
    let change: Double // Yüzde değişim
    let bid: Double
    let ask: Double
    let timestamp: Date
    
    var changePercent: Double {
        guard previousClose > 0 else { return 0 }
        return ((last - previousClose) / previousClose) * 100
    }
    
    var isPositive: Bool {
        return last >= previousClose
    }
}

struct BorsaPyCandle: Codable, Sendable {
    let date: Date
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double
}

struct FXRate: Codable, Sendable {
    let symbol: String
    let last: Double
    let open: Double
    let high: Double
    let low: Double
    let timestamp: Date
    
    var changePercent: Double {
        guard open > 0 else { return 0 }
        return ((last - open) / open) * 100
    }
}

struct FXCandle: Codable, Sendable {
    let date: Date
    let open: Double
    let high: Double
    let low: Double
    let close: Double
}

struct InflationResult: Codable, Sendable {
    let startDate: String
    let endDate: String
    let initialValue: Double
    let finalValue: Double
    let totalYears: Int
    let totalMonths: Int
    let totalChange: Double // Toplam yüzde değişim
    let avgYearlyInflation: Double
    let startCPI: Double
    let endCPI: Double
}

struct BistDividend: Codable, Sendable, Identifiable {
    var id: Date { date }
    let date: Date
    let grossRate: Double      // Brüt temettü oranı (%)
    let netRate: Double        // Net temettü oranı (%)
    let totalAmount: Double    // Toplam temettü tutarı
    let perShare: Double       // Hisse başına temettü
    
    var year: Int {
        Calendar.current.component(.year, from: date)
    }
}

struct BistCapitalIncrease: Codable, Sendable, Identifiable {
    var id: Date { date }
    let date: Date
    let capitalAfter: Double       // Artırım sonrası sermaye
    let rightsIssueRate: Double    // Bedelli oran (%)
    let bonusFromCapitalRate: Double   // Bedelsiz iç kaynak (%)
    let bonusFromDividendRate: Double  // Bedelsiz temettüden (%)
    
    var totalBonusRate: Double {
        bonusFromCapitalRate + bonusFromDividendRate
    }
}

/// BIST Mali Tablolar (Bilanço + Gelir Tablosu)
struct BistFinancials: Codable, Sendable {
    let symbol: String
    let period: String // "2024/03" gibi dönem
    
    // Karlılık
    let netProfit: Double?
    let ebitda: Double?
    let revenue: Double?
    let grossProfit: Double?
    let operatingProfit: Double?
    
    // Bilanço
    let totalAssets: Double?
    let totalEquity: Double?
    let totalDebt: Double?
    let shortTermDebt: Double?
    let longTermDebt: Double?
    let currentAssets: Double?
    let cash: Double?
    
    // Oranlar
    let roe: Double? // Özkaynak Karlılığı
    let roa: Double? // Aktif Karlılığı
    let currentRatio: Double? // Cari Oran
    let debtToEquity: Double? // Borç/Özkaynak
    let netMargin: Double? // Net Kar Marjı
    
    // Değerleme
    let pe: Double? // F/K
    let pb: Double? // PD/DD
    let marketCap: Double? // Piyasa Değeri
    let eps: Double? // Hisse Başına Kar (EPS)
    
    let timestamp: Date
    
    // Hesaplanmış Oranlar
    var grossMargin: Double? {
        guard let gross = grossProfit, let rev = revenue, rev > 0 else { return nil }
        return (gross / rev) * 100
    }
    
    var operatingMargin: Double? {
        guard let op = operatingProfit, let rev = revenue, rev > 0 else { return nil }
        return (op / rev) * 100
    }
    
    var cashRatio: Double? {
        guard let c = cash, let std = shortTermDebt, std > 0 else { return nil }
        return c / std
    }
}

/// BIST Analist Konsensüsü
struct BistAnalystConsensus: Codable, Sendable {
    let symbol: String
    let buyCount: Int
    let holdCount: Int
    let sellCount: Int
    let totalAnalysts: Int
    let averageTargetPrice: Double?
    let highTargetPrice: Double?
    let lowTargetPrice: Double?
    let timestamp: Date
    
    /// Konsensüs Skoru: -1 (Güçlü SAT) ile +1 (Güçlü AL) arası
    var consensusScore: Double {
        guard totalAnalysts > 0 else { return 0 }
        return Double(buyCount - sellCount) / Double(totalAnalysts)
    }
    
    /// Konsensüs Metni
    var consensusText: String {
        if consensusScore > 0.5 { return "Güçlü AL" }
        else if consensusScore > 0.2 { return "AL" }
        else if consensusScore > -0.2 { return "TUT" }
        else if consensusScore > -0.5 { return "SAT" }
        else { return "Güçlü SAT" }
    }
    
    /// Yükseliş Potansiyeli hesapla
    func upsidePotential(currentPrice: Double) -> Double? {
        guard let target = averageTargetPrice, currentPrice > 0 else { return nil }
        return ((target - currentPrice) / currentPrice) * 100
    }
}

enum GoldType: String {
    case gramAltin = "gram-altin"
    case gumus = "gumus"
    case ons = "ons"
}

enum BorsaPyError: Error, LocalizedError {
    case invalidURL
    case requestFailed
    case invalidResponse
    case symbolNotFound
    case rateLimited
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Geçersiz URL"
        case .requestFailed: return "İstek başarısız"
        case .invalidResponse: return "Geçersiz yanıt"
        case .symbolNotFound: return "Sembol bulunamadı"
        case .rateLimited: return "Rate limit aşıldı"
        }
    }
}
