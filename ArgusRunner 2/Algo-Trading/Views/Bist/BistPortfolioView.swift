import SwiftUI

// MARK: - BIST Portfolio View (Refactored to use main PortfolioEngine)
// MARK: - BIST Portfolio View (Refactored to use main PortfolioStore)
// Artık TradingViewModel ve PortfolioStore kullanıyor

struct BistPortfolioView: View {
    @EnvironmentObject var viewModel: TradingViewModel
    @State private var showSearch = false
    
    // BIST trades from PortfolioStore
    var bistTrades: [Trade] {
        PortfolioStore.shared.bistOpenTrades
    }
    
    var bistBalance: Double {
        PortfolioStore.shared.bistBalance
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // MARK: - Balance Card (TL)
                VStack(alignment: .leading, spacing: 16) {
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Toplam Varlık (TL)")
                                .font(.subheadline)
                                .foregroundColor(.white.opacity(0.7))
                            
                            HStack(alignment: .lastTextBaseline) {
                                Text("₺")
                                    .font(.title2)
                                    .foregroundColor(.white.opacity(0.8))
                                Text(String(format: "%.2f", bistBalance + portfolioValue))
                                    .font(.system(size: 32, weight: .bold))
                                    .foregroundColor(.white)
                            }
                        }
                        Spacer()
                        Image(systemName: "turkishlirasign.circle.fill")
                            .font(.system(size: 40))
                            .foregroundColor(.white)
                    }
                    
                    Divider().background(Color.white.opacity(0.2))
                    
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Nakit")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.7))
                            Text("₺\(String(format: "%.2f", bistBalance))")
                                .font(.headline)
                                .foregroundColor(.white)
                        }
                        
                        Spacer()
                        
                        VStack(alignment: .trailing) {
                            Text("Hisse Değeri")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.7))
                            Text("₺\(String(format: "%.2f", portfolioValue))")
                                .font(.headline)
                                .foregroundColor(.white)
                        }
                    }
                    
                    Divider().background(Color.white.opacity(0.2))
                    
                    // Argus Auto-Pilot (BIST Mode)
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Argus BIST Yöneticisi")
                                .font(.caption).bold()
                                .foregroundColor(.white)
                            Text(viewModel.isAutoPilotEnabled ? "Aktif: Piyasa taranıyor..." : "Pasif: Manuel Mod")
                                .font(.caption2)
                                .foregroundColor(.white.opacity(0.7))
                        }
                        
                        Spacer()
                        
                        Toggle("", isOn: $viewModel.isAutoPilotEnabled)
                            .labelsHidden()
                            .toggleStyle(SwitchToggleStyle(tint: .green))
                    }
                }
                .padding()
                .background(
                    LinearGradient(gradient: Gradient(colors: [Theme.bistAccent.opacity(0.9), Theme.bistSecondary.opacity(0.8)]), startPoint: .topLeading, endPoint: .bottomTrailing)
                )
                .cornerRadius(20)
                .shadow(color: Theme.bistAccent.opacity(0.3), radius: 10, x: 0, y: 5)
                .padding(.horizontal)
                
                // MARK: - Portfolio List
                if bistTrades.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "case.fill")
                            .font(.system(size: 48))
                            .foregroundColor(.gray.opacity(0.5))
                        Text("Portföyün Boş")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        Text("BIST hisseleri ekleyerek başla.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        Button(action: { showSearch = true }) {
                            Text("Hisse Ekle")
                                .bold()
                                .padding()
                                .background(Theme.tint)
                                .foregroundColor(.white)
                                .cornerRadius(12)
                        }
                    }
                    .padding(.top, 40)
                } else {
                    LazyVStack(spacing: 12) {
                        ForEach(bistTrades) { trade in
                            BistPositionRowV2(trade: trade, quote: viewModel.quotes[trade.symbol])
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.top)
        }
        .background(Theme.background.ignoresSafeArea())
        .sheet(isPresented: $showSearch) {
            BistMarketView()
                .environmentObject(viewModel)
        }
    }
    
    // Computed
    var portfolioValue: Double {
        bistTrades.reduce(0) { total, trade in
            let price = viewModel.quotes[trade.symbol]?.currentPrice ?? trade.entryPrice
            return total + (trade.quantity * price)
        }
    }
}

// MARK: - Subviews
struct BistPositionRowV2: View {
    let trade: Trade
    let quote: Quote?
    
    // Plan desteği
    var plan: PositionPlan? {
        PositionPlanStore.shared.getPlan(for: trade.id)
    }
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                VStack(alignment: .leading) {
                    Text(trade.symbol.replacingOccurrences(of: ".IS", with: ""))
                        .font(.headline)
                        .bold()
                    Text("\(Int(trade.quantity)) Adet")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    let currentPrice = quote?.currentPrice ?? trade.entryPrice
                    Text("₺\(String(format: "%.2f", currentPrice))")
                        .bold()
                    
                    let pnl = (currentPrice - trade.entryPrice) * trade.quantity
                    let pnlPercent = ((currentPrice - trade.entryPrice) / trade.entryPrice) * 100.0
                    
                    HStack(spacing: 4) {
                        Image(systemName: pnl >= 0 ? "arrow.up" : "arrow.down")
                        Text("\(String(format: "%.1f", pnlPercent))%")
                        Text("(₺\(Int(pnl)))")
                    }
                    .font(.caption)
                    .foregroundColor(pnl >= 0 ? Theme.bistPositive : Theme.bistNegative)
                }
            }
            
            // Plan durumu gösterimi
            if let plan = plan {
                Divider().background(Color.white.opacity(0.1))
                
                HStack(spacing: 8) {
                    // Intent ikonu
                    Image(systemName: plan.intent.icon)
                        .font(.caption)
                        .foregroundColor(Theme.bistAccent)
                    
                    Text(plan.intent.rawValue)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    
                    Spacer()
                    
                    // Aktif senaryo
                    if plan.bullishScenario.isActive {
                        Label("BOĞA", systemImage: "arrow.up.right")
                            .font(.caption2)
                            .foregroundColor(.green)
                    } else if plan.bearishScenario.isActive {
                        Label("AYI", systemImage: "arrow.down.right")
                            .font(.caption2)
                            .foregroundColor(.red)
                    }
                    
                    // Sonraki adım
                    if let nextStep = plan.bullishScenario.steps.first(where: { !plan.executedSteps.contains($0.id) }) {
                        Text(nextStep.trigger.displayText)
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Theme.bistAccent.opacity(0.2))
                            .cornerRadius(4)
                    }
                }
            } else {
                // Plan yoksa oluştur butonu
                HStack {
                    Image(systemName: "doc.badge.plus")
                        .font(.caption)
                        .foregroundColor(.orange)
                    Text("Plan oluştur")
                        .font(.caption2)
                        .foregroundColor(.orange)
                    Spacer()
                }
            }
        }
        .padding()
        .background(Theme.secondaryBackground)
        .cornerRadius(12)
    }
}

