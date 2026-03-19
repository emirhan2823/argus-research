import Foundation
import Combine

// MARK: - PortfolioStore
/// Tek Gerçek Kaynak (Single Source of Truth) portföy yönetim sistemi.
/// Tüm portföy işlemleri bu class üzerinden yapılır.
/// BIST ve Global piyasalar ayrı bakiyeler, tek portföy listesi.

@MainActor
final class PortfolioStore: ObservableObject {
    
    // MARK: - Singleton
    static let shared = PortfolioStore()
    
    // MARK: - Published State
    @Published private(set) var trades: [Trade] = []
    @Published private(set) var globalBalance: Double = 100_000.0  // USD
    @Published private(set) var bistBalance: Double = 1_000_000.0  // TRY
    @Published private(set) var transactions: [Transaction] = []
    
    // MARK: - Persistence Keys (Tek Kaynak)
    private let portfolioKey = "argus_portfolio_v4"
    private let globalBalanceKey = "argus_balance_usd_v2"
    private let bistBalanceKey = "argus_balance_try_v2"
    private let transactionsKey = "argus_transactions_v2"

    // MARK: - Debounced Save Mechanism
    private var saveWorkItem: DispatchWorkItem?
    private let saveDebounceInterval: TimeInterval = 1.0 // 1 saniye

    /// Debounced disk yazma - çok sık yazma işlemlerini birleştirir
    private func scheduleDebouncedSave() {
        saveWorkItem?.cancel()
        saveWorkItem = DispatchWorkItem { [weak self] in
            self?.saveToDisk()
        }
        if let workItem = saveWorkItem {
            DispatchQueue.main.asyncAfter(deadline: .now() + saveDebounceInterval, execute: workItem)
        }
    }
    
    // MARK: - Public Methods
    
    func addTransaction(_ transaction: Transaction) {
        transactions.insert(transaction, at: 0)
        saveToDisk()
        print("📝 PortfolioStore: Transaction logged: \(transaction.type.rawValue) \(transaction.symbol)")
    }
    
    // MARK: - Initialization
    private init() {
        loadFromDisk()
    }
    
    // MARK: - Computed Properties
    
    var openTrades: [Trade] {
        trades.filter { $0.isOpen }
    }
    
    var closedTrades: [Trade] {
        trades.filter { !$0.isOpen }
    }
    
    var globalOpenTrades: [Trade] {
        openTrades.filter { $0.currency == .USD }
    }
    
    var bistOpenTrades: [Trade] {
        openTrades.filter { $0.currency == .TRY }
    }
    
    // MARK: - Balance Helpers
    
    func availableBalance(for symbol: String) -> Double {
        isBistSymbol(symbol) ? bistBalance : globalBalance
    }
    
    func availableBalance(currency: Currency) -> Double {
        currency == .TRY ? bistBalance : globalBalance
    }
    
    // MARK: - Buy Operation
    
    @discardableResult
    func buy(
        symbol: String,
        quantity: Double,
        price: Double,
        source: TradeSource = .user,
        engine: AutoPilotEngine? = nil,
        stopLoss: Double? = nil,
        takeProfit: Double? = nil,
        rationale: String? = nil,
        orionSnapshot: OrionComponentSnapshot? = nil
    ) -> Bool {
        guard quantity > 0, price > 0 else { return false }
        
        let isBist = isBistSymbol(symbol)
        let currency: Currency = isBist ? .TRY : .USD
        let cost = quantity * price
        let commission = FeeModel.shared.calculate(amount: cost)
        let totalCost = cost + commission
        
        // Balance Check
        if isBist {
            guard bistBalance >= totalCost else {
                print("❌ PortfolioEngine: Yetersiz BIST bakiyesi (₺\(bistBalance) < ₺\(totalCost))")
                return false
            }
            bistBalance -= totalCost
        } else {
            guard globalBalance >= totalCost else {
                print("❌ PortfolioEngine: Yetersiz USD bakiyesi ($\(globalBalance) < $\(totalCost))")
                return false
            }
            globalBalance -= totalCost
        }
        
        // Create Trade
        var trade = Trade(
            symbol: symbol,
            entryPrice: price,
            quantity: quantity,
            entryDate: Date(),
            isOpen: true,
            source: source,
            engine: engine,
            stopLoss: stopLoss,
            takeProfit: takeProfit,
            rationale: rationale,
            currency: currency
        )
        trade.entryOrionSnapshot = orionSnapshot
        
        trades.append(trade)
        
        // Log Transaction
        let transaction = Transaction(
            id: UUID(),
            type: .buy,
            symbol: symbol,
            amount: cost,
            price: price,
            date: Date(),
            fee: commission
        )
        transactions.insert(transaction, at: 0)
        
        saveToDisk()
        
        let currencySymbol = isBist ? "₺" : "$"
        print("✅ PortfolioEngine: BUY \(symbol) x\(quantity) @ \(currencySymbol)\(price)")
        return true
    }
    
    // MARK: - Market Data Updates (Stop Loss / Take Profit)
    
    func handleQuoteUpdates(_ quotes: [String: DataValue<Quote>]) {
        // Sadece açık pozisyonlar için quote'ları güncelle ve kontrol et
        let openSymbols = Set(trades.filter { $0.isOpen }.map { $0.symbol })
        
        for symbol in openSymbols {
            if let dataValue = quotes[symbol], let quote = dataValue.value {
                let currentPrice = quote.currentPrice
                
                // Stop Loss / Take Profit / HWM kontrolü
                for index in trades.indices where trades[index].symbol == symbol && trades[index].isOpen {
                    let trade = trades[index]
                    
                    // High Water Mark Update (Trailing Stop için)
                    if currentPrice > (trade.highWaterMark ?? 0) {
                        var mutableTrade = trades[index]
                        mutableTrade.highWaterMark = currentPrice
                        trades[index] = mutableTrade
                        scheduleDebouncedSave() // Debounced - çok sık yazma önlenir
                    }

                    checkStopLoss(for: trade, at: index, currentPrice: currentPrice)
                    checkTakeProfit(for: trade, at: index, currentPrice: currentPrice)
                }
            }
        }
    }
    
    private func checkStopLoss(for trade: Trade, at index: Int, currentPrice: Double) {
        guard let stopLoss = trade.stopLoss,
              currentPrice <= stopLoss,
              !trade.isPendingSale else { return } // Duplicate trigger koruması

        // İşaretle ve sat - race condition önleme
        trades[index].isPendingSale = true
        scheduleDebouncedSave()

        // Stop Loss tetiklendi
        print("🛑 PortfolioStore: STOP LOSS tetiklendi for \(trade.symbol) @ \(currentPrice) (SL: \(stopLoss))")
        sell(tradeId: trade.id, currentPrice: currentPrice, reason: "STOP_LOSS")
    }

    private func checkTakeProfit(for trade: Trade, at index: Int, currentPrice: Double) {
        guard let takeProfit = trade.takeProfit,
              currentPrice >= takeProfit,
              !trade.isPendingSale else { return } // Duplicate trigger koruması

        // İşaretle ve sat - race condition önleme
        trades[index].isPendingSale = true
        scheduleDebouncedSave()

        // Take Profit tetiklendi
        print("💰 PortfolioStore: TAKE PROFIT tetiklendi for \(trade.symbol) @ \(currentPrice) (TP: \(takeProfit))")
        sell(tradeId: trade.id, currentPrice: currentPrice, reason: "TAKE_PROFIT")
    }
    
    // MARK: - Sell Operation
    
    @discardableResult
    func sell(tradeId: UUID, currentPrice: Double, reason: String? = nil) -> Double? {
        guard let index = trades.firstIndex(where: { $0.id == tradeId && $0.isOpen }) else {
            print("❌ PortfolioEngine: Trade bulunamadı: \(tradeId)")
            return nil
        }
        
        var trade = trades[index]
        let isBist = trade.currency == .TRY
        let revenue = trade.quantity * currentPrice
        let commission = FeeModel.shared.calculate(amount: revenue)
        let netRevenue = revenue - commission
        let pnl = (currentPrice - trade.entryPrice) * trade.quantity - commission
        
        // Add to balance
        if isBist {
            bistBalance += netRevenue
        } else {
            globalBalance += netRevenue
        }
        
        // Close trade
        trade.isOpen = false
        trade.exitPrice = currentPrice
        trade.exitDate = Date()
        trades[index] = trade
        
        // Log for Chiron Learning
        let tradeLog = TradeLog(
            date: Date(),
            symbol: trade.symbol,
            entryPrice: trade.entryPrice,
            exitPrice: currentPrice,
            pnlPercent: trade.profitPercentage,
            pnlAbsolute: pnl,
            entryRegime: ChironRegimeEngine.shared.globalResult.regime,
            entryOrionScore: trade.entryOrionSnapshot?.momentumScore ?? 0,
            entryAtlasScore: 0,
            entryAetherScore: 0,
            engine: trade.engine?.rawValue ?? "MANUAL",
            entryOrionSnapshot: trade.entryOrionSnapshot,
            exitOrionSnapshot: nil
        )
        TradeLogStore.shared.append(tradeLog)
        
        // Log Transaction
        var transaction = Transaction(
            id: UUID(),
            type: .sell,
            symbol: trade.symbol,
            amount: revenue,
            price: currentPrice,
            date: Date(),
            fee: commission,
            pnl: pnl,
            pnlPercent: trade.profitPercentage
        )
        transaction.reasonCode = reason
        transactions.insert(transaction, at: 0)
        
        saveToDisk()
        
        let currencySymbol = isBist ? "₺" : "$"
        print("✅ PortfolioEngine: SELL \(trade.symbol) @ \(currencySymbol)\(currentPrice), PnL: \(currencySymbol)\(String(format: "%.2f", pnl))")
        return pnl
    }
    
    // MARK: - Partial Sell (Trim)
    
    @discardableResult
    func trim(tradeId: UUID, percentage: Double, currentPrice: Double, reason: String? = nil) -> Double? {
        guard percentage > 0, percentage < 100 else { return nil }
        guard let index = trades.firstIndex(where: { $0.id == tradeId && $0.isOpen }) else { return nil }
        
        var trade = trades[index]
        let sellQuantity = trade.quantity * (percentage / 100.0)
        let remainingQuantity = trade.quantity - sellQuantity
        
        let isBist = trade.currency == .TRY
        let revenue = sellQuantity * currentPrice
        let commission = FeeModel.shared.calculate(amount: revenue)
        let netRevenue = revenue - commission
        let pnl = (currentPrice - trade.entryPrice) * sellQuantity - commission
        
        // Add to balance
        if isBist {
            bistBalance += netRevenue
        } else {
            globalBalance += netRevenue
        }
        
        // Update trade quantity
        trade.quantity = remainingQuantity
        trades[index] = trade
        
        // Log Transaction
        var transaction = Transaction(
            id: UUID(),
            type: .sell,
            symbol: trade.symbol,
            amount: revenue,
            price: currentPrice,
            date: Date(),
            fee: commission,
            pnl: pnl,
            pnlPercent: ((currentPrice - trade.entryPrice) / trade.entryPrice) * 100
        )
        transaction.reasonCode = "TRIM_\(Int(percentage))%"
        transactions.insert(transaction, at: 0)
        
        saveToDisk()
        
        print("✅ PortfolioEngine: TRIM \(trade.symbol) \(Int(percentage))% @ \(currentPrice)")
        return pnl
    }
    
    // MARK: - Portfolio Value Calculations
    
    func getGlobalEquity(quotes: [String: Quote]) -> Double {
        let positionValue = globalOpenTrades.reduce(0.0) { sum, trade in
            let currentPrice = quotes[trade.symbol]?.currentPrice ?? trade.entryPrice
            return sum + (trade.quantity * currentPrice)
        }
        return globalBalance + positionValue
    }
    
    func getBistEquity(quotes: [String: Quote]) -> Double {
        let positionValue = bistOpenTrades.reduce(0.0) { sum, trade in
            let currentPrice = quotes[trade.symbol]?.currentPrice ?? trade.entryPrice
            return sum + (trade.quantity * currentPrice)
        }
        return bistBalance + positionValue
    }
    
    func getGlobalUnrealizedPnL(quotes: [String: Quote]) -> Double {
        globalOpenTrades.reduce(0.0) { sum, trade in
            let currentPrice = quotes[trade.symbol]?.currentPrice ?? trade.entryPrice
            return sum + ((currentPrice - trade.entryPrice) * trade.quantity)
        }
    }
    
    func getBistUnrealizedPnL(quotes: [String: Quote]) -> Double {
        bistOpenTrades.reduce(0.0) { sum, trade in
            let currentPrice = quotes[trade.symbol]?.currentPrice ?? trade.entryPrice
            return sum + ((currentPrice - trade.entryPrice) * trade.quantity)
        }
    }
    
    func getRealizedPnL(currency: Currency? = nil) -> Double {
        let relevantTransactions: [Transaction]
        if let currency = currency {
            relevantTransactions = transactions.filter { tx in
                guard tx.type == .sell, let pnl = tx.pnl else { return false }
                let isBist = isBistSymbol(tx.symbol)
                return currency == .TRY ? isBist : !isBist
            }
        } else {
            relevantTransactions = transactions.filter { $0.type == .sell }
        }
        return relevantTransactions.compactMap { $0.pnl }.reduce(0.0, +)
    }
    
    // MARK: - Position Helpers
    
    func getPosition(for symbol: String) -> [Trade] {
        openTrades.filter { $0.symbol == symbol }
    }
    
    func getTotalQuantity(for symbol: String) -> Double {
        getPosition(for: symbol).reduce(0) { $0 + $1.quantity }
    }
    
    func hasPosition(for symbol: String) -> Bool {
        openTrades.contains { $0.symbol == symbol }
    }
    
    // MARK: - Helpers
    
    private func isBistSymbol(_ symbol: String) -> Bool {
        symbol.uppercased().hasSuffix(".IS")
    }
    
    // MARK: - Persistence
    
    private func saveToDisk() {
        let encoder = JSONEncoder()
        
        if let portfolioData = try? encoder.encode(trades) {
            UserDefaults.standard.set(portfolioData, forKey: portfolioKey)
        }
        
        if let txData = try? encoder.encode(transactions) {
            UserDefaults.standard.set(txData, forKey: transactionsKey)
        }
        
        UserDefaults.standard.set(globalBalance, forKey: globalBalanceKey)
        UserDefaults.standard.set(bistBalance, forKey: bistBalanceKey)
        
        // Sync with ArgusStorage (for Widget/AppGroup)
        ArgusStorage.shared.savePortfolio(trades)
    }
    
    private func loadFromDisk() {
        let decoder = JSONDecoder()
        
        // Try new keys first
        if let data = UserDefaults.standard.data(forKey: portfolioKey),
           let saved = try? decoder.decode([Trade].self, from: data) {
            trades = saved
        } else {
            // Migration: Try old keys
            migrateFromOldSources()
        }
        
        if let txData = UserDefaults.standard.data(forKey: transactionsKey),
           let savedTx = try? decoder.decode([Transaction].self, from: txData) {
            transactions = savedTx
        }
        
        if UserDefaults.standard.object(forKey: globalBalanceKey) != nil {
            globalBalance = UserDefaults.standard.double(forKey: globalBalanceKey)
        }
        
        if UserDefaults.standard.object(forKey: bistBalanceKey) != nil {
            bistBalance = UserDefaults.standard.double(forKey: bistBalanceKey)
        }
        
        print("📂 PortfolioEngine: Loaded \(trades.count) trades, USD: $\(globalBalance), TRY: ₺\(bistBalance)")
    }
    
    // MARK: - Migration from Old Sources
    
    private func migrateFromOldSources() {
        let decoder = JSONDecoder()
        var migratedTrades: [Trade] = []
        
        // 1. portfolio_v2 (TradingViewModel)
        if let data = UserDefaults.standard.data(forKey: "portfolio_v2"),
           let oldTrades = try? decoder.decode([Trade].self, from: data) {
            migratedTrades.append(contentsOf: oldTrades)
            print("📦 Migration: \(oldTrades.count) trades from portfolio_v2")
        }
        
        // 2. argus_portfolio_v2 (PortfolioStore)
        if let data = UserDefaults.standard.data(forKey: "argus_portfolio_v2"),
           let oldTrades = try? decoder.decode([Trade].self, from: data) {
            // Avoid duplicates by ID
            let existingIds = Set(migratedTrades.map { $0.id })
            let newTrades = oldTrades.filter { !existingIds.contains($0.id) }
            migratedTrades.append(contentsOf: newTrades)
            print("📦 Migration: \(newTrades.count) trades from argus_portfolio_v2")
        }
        
        // 3. bist_portfolio_v1 (BistTradingViewModel) - Different model, manual conversion
        if let data = UserDefaults.standard.data(forKey: "bist_portfolio_v1") {
            // BistTrade has different structure, decode manually
            if let bistTrades = try? decoder.decode([BistTradeLegacy].self, from: data) {
                for bt in bistTrades {
                    let converted = Trade(
                        id: bt.id,
                        symbol: bt.symbol,
                        entryPrice: bt.entryPrice,
                        quantity: bt.quantity,
                        entryDate: bt.entryDate,
                        isOpen: bt.isOpen,
                        source: .user,
                        currency: .TRY
                    )
                    // Avoid duplicates
                    if !migratedTrades.contains(where: { $0.id == converted.id }) {
                        migratedTrades.append(converted)
                    }
                }
                print("📦 Migration: \(bistTrades.count) trades from bist_portfolio_v1")
            }
        }
        
        // Migrate Balances
        if UserDefaults.standard.object(forKey: "userBalance") != nil {
            globalBalance = UserDefaults.standard.double(forKey: "userBalance")
            print("📦 Migration: USD balance from userBalance: $\(globalBalance)")
        }
        
        if UserDefaults.standard.object(forKey: "bistBalance") != nil {
            bistBalance = UserDefaults.standard.double(forKey: "bistBalance")
            print("📦 Migration: TRY balance from bistBalance: ₺\(bistBalance)")
        } else if UserDefaults.standard.object(forKey: "bist_balance_v1") != nil {
            bistBalance = UserDefaults.standard.double(forKey: "bist_balance_v1")
            print("📦 Migration: TRY balance from bist_balance_v1: ₺\(bistBalance)")
        }
        
        trades = migratedTrades
        
        if !migratedTrades.isEmpty {
            saveToDisk()
            print("✅ Migration Complete: \(migratedTrades.count) trades consolidated")
        }
    }
    
    // MARK: - Reset (Dev Only)
    
    func resetPortfolio() {
        trades = []
        transactions = []
        globalBalance = 100_000.0
        bistBalance = 1_000_000.0
        saveToDisk()
        print("🔄 PortfolioEngine: Reset complete")
    }
    
    func resetBistPortfolio() {
        print("🚨 PortfolioStore: BIST PORTFÖYÜ SIFIRLANIYOR...")
        
        // 1. Remove BIST Trades
        trades.removeAll { $0.currency == .TRY }
        
        // 2. Remove BIST Transactions
        // Transaction model might not have currency, check symbol
        transactions.removeAll { isBistSymbol($0.symbol) }
        
        // 3. Reset Balance
        bistBalance = 1_000_000.0
        
        saveToDisk()
        print("✅ PortfolioStore: BIST Reset Complete")
    }
}

// MARK: - Legacy BistTrade for Migration

private struct BistTradeLegacy: Codable {
    let id: UUID
    let symbol: String
    let quantity: Double
    let entryPrice: Double
    let entryDate: Date
    let isOpen: Bool
}
