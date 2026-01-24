//
//  Algo_TradingApp.swift
//  Algo-Trading
//
//  Created by Argus Team on 2.12.2025.
//

import SwiftUI
import SwiftData

@main
struct Algo_TradingApp: App {
    // Create container manually to access context easily for Singleton injection
    let container: ModelContainer

    // Static timer holder to prevent memory leaks from multiple timer instances
    private static var maturationTimer: Timer?
    private static var cleanupTimer: Timer?
    
    // Unified Singleton ViewModel (Legacy - Geçiş döneminde korunuyor)
    @StateObject private var tradingViewModel = TradingViewModel()
    
    // FAZ 2: Yeni modüler koordinatör (Paralel çalışıyor)
    @StateObject private var coordinator = AppStateCoordinator.shared

    init() {
        do {
            let modelContainer = try ModelContainer(for: ShadowTradeSession.self, MissedOpportunityLog.self)
            self.container = modelContainer
            
            // SETUP NOTIFICATION DELEGATE
            UNUserNotificationCenter.current().delegate = NotificationDelegate.shared
            
            // Inject into Singleton immediately
            Task { @MainActor in
                LearningPersistenceManager.shared.setContext(modelContainer.mainContext)
                
                // ONE-TIME PORTFOLIO RESET (v5 Migration - Zorla Temiz Başlangıç)
                let resetKey = "portfolio_v5_reset_done"
                if !UserDefaults.standard.bool(forKey: resetKey) {
                    print("🔄 ONE-TIME RESET: Portföy sıfırlanıyor (v5 migration)...")
                    PortfolioStore.shared.resetPortfolio()
                    UserDefaults.standard.set(true, forKey: resetKey)
                    print("✅ ONE-TIME RESET: Tamamlandı. USD: $100K, TRY: ₺1M")
                }
                
                // AUTO CLEANUP: Storage temizliği (günde 1 kez)
                await ArgusLedger.shared.autoCleanupIfNeeded()
                DiskCacheService.shared.cleanup()
                
                // CHIRON CLEANUP: RAG sync edilmiş 7 günden eski kayıtları sil
                let _ = await ChironDataLakeService.shared.cleanupSyncedRecords(olderThanDays: 7)
            }
        } catch {
            print("🚨 CRITICAL: Failed to create ModelContainer: \(error)")
            // FALLBACK: Create in-memory container to prevent crash
            do {
                let schema = Schema([ShadowTradeSession.self, MissedOpportunityLog.self])
                let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: true)
                self.container = try ModelContainer(for: schema, configurations: [config])
                print("⚠️ Using In-Memory Safe Container")
            } catch let fallbackError {
                // GRACEFUL DEGRADATION: Use absolute minimal container
                // Instead of crashing, log and use empty schema
                print("🚨 FATAL FALLBACK FAILED: \(fallbackError)")
                print("🛡️ Using minimal empty container - some features may be unavailable")

                // Minimal fallback - sadece app açılsın
                do {
                    self.container = try ModelContainer(for: Schema([]))
                } catch {
                    // Son çare: fatalError (bu noktaya hiç gelmemeli)
                    fatalError("🛑 ModelContainer oluşturulamadı: \(error)")
                }
            }
        }
    }

    @AppStorage("hasAcceptedDisclaimer") private var hasAcceptedDisclaimer: Bool = false

    var body: some Scene {
        WindowGroup {
            Group {
                if hasAcceptedDisclaimer {
                    ContentView()
                        .environmentObject(tradingViewModel)
                        .environmentObject(coordinator) // Yeni koordinatör
                        .environmentObject(coordinator.watchlist) // Yeni WatchlistVM
                        .environmentObject(coordinator.portfolio) // Yeni PortfolioVM
                        .task {
                            // One-time startup logic
                            tradingViewModel.bootstrap()

                            // 🧠 Chiron: Start background learning analysis
                            Task.detached(priority: .background) {
                                // Delay to let app settle
                                try? await Task.sleep(nanoseconds: 10_000_000_000) // 10 seconds
                                await ChironLearningJob.shared.runFullAnalysis()
                                print("🧠 Chiron: Startup learning cycle completed")
                            }

                            // 👁️ Alkindus: Start periodic maturation checks
                            startAlkindusPeriodicCheck()
                            
                            // 🧹 Argus Cleanup: Start periodic aggressive cleanup
                            startAutomaticCleanup()
                            
                            // 📅 ReportScheduler: Otomatik rapor oluşturmayı başlat (sistem rahatladıktan sonra)
                            Task.detached(priority: .background) {
                                try? await Task.sleep(nanoseconds: 5_000_000_000) // 5 saniye bekle
                                await ReportScheduler.shared.start()
                                print("📅 ReportScheduler: Başlatıldı (5 saniye gecikme)")
                            }
                        }
                } else {
                    DisclaimerView()
                }
            }
        }
        .modelContainer(container)
    }

    // MARK: - Alkindus Periodic Check

    private func startAlkindusPeriodicCheck() {
        // Cancel existing timer if any (prevents memory leaks from multiple timers)
        Self.maturationTimer?.invalidate()

        // Başlangıçta bir kez çalıştır (delay ile app settle olsun)
        Task.detached(priority: .background) {
            do {
                // Delay to let app and market data settle
                try await Task.sleep(nanoseconds: 15_000_000_000) // 15 seconds
                await AlkindusCalibrationEngine.shared.periodicMatureCheck()
                print("Alkindus: Startup maturation check completed")
            } catch {
                print("Alkindus maturation check failed: \(error)")
            }
        }

        // Her saat başı tekrarla - single timer instance
        Self.maturationTimer = Timer.scheduledTimer(withTimeInterval: 3600, repeats: true) { _ in
            Task {
                do {
                    await AlkindusCalibrationEngine.shared.periodicMatureCheck()
                } catch {
                    print("Alkindus hourly maturation check failed: \(error)")
                }
            }
        }
    }
    
    // MARK: - Automatic Storage Cleanup
    
    private func startAutomaticCleanup() {
        // Cancel existing timer if any
        Self.cleanupTimer?.invalidate()
        
        // Başlangıçta bir kez çalıştır
        Task.detached(priority: .background) {
            do {
                try await Task.sleep(nanoseconds: 30_000_000_000) // 30 saniye bekle
                await ArgusLedger.shared.aggressiveCleanup()
                print("🧹 Argus: Startup cleanup completed")
            } catch {
                print("Argus cleanup failed: \(error)")
            }
        }
        
        // Her 6 saatte bir tekrarla
        Self.cleanupTimer = Timer.scheduledTimer(withTimeInterval: 21600, repeats: true) { _ in
            Task {
                await ArgusLedger.shared.aggressiveCleanup()
                print("🧹 Argus: Periodic cleanup completed")
            }
        }
    }
}
