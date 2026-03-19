import Foundation
import Combine
import SwiftUI

// MARK: - Execution State ViewModel
/// Extracted from TradingViewModel (God Object Decomposition - Phase 2)
/// Responsibilities: AutoPilot state, execution monitoring, trade cooldowns

@MainActor
final class ExecutionStateViewModel: ObservableObject {
    static let shared = ExecutionStateViewModel()
    
    // MARK: - Published Properties
    
    /// AutoPilot enabled state
    @Published var isAutoPilotEnabled: Bool = false {
        didSet {
            UserDefaults.standard.set(isAutoPilotEnabled, forKey: "autopilot_enabled_v2")
            if isAutoPilotEnabled {
                startAutoPilot()
            } else {
                stopAutoPilot()
            }
        }
    }
    
    /// Selected AutoPilot engine
    @Published var selectedEngine: AutoPilotEngine = .corse {
        didSet {
            UserDefaults.standard.set(selectedEngine.rawValue, forKey: "autopilot_engine_v2")
        }
    }
    
    /// Is currently scanning
    @Published var isScanning: Bool = false
    
    /// Last scan time
    @Published var lastScanTime: Date?
    
    /// Active scan symbols
    @Published var activeScanSymbols: [String] = []
    
    /// AutoPilot Execution Logs
    @Published var autoPilotLogs: [String] = []

    /// Last Trade Times (Shared for Agora Checks)
    @Published var lastTradeTimes: [String: Date] = [:]


    
    /// Trade Brain alerts
    @Published var planAlerts: [TradeBrainAlert] = []
    
    /// AGORA decision snapshots
    @Published var agoraSnapshots: [DecisionSnapshot] = []
    
    /// Cooldown tracking - Symbol → Next allowed trade time
    @Published var tradeCooldowns: [String: Date] = [:]
    
    // MARK: - Internal State
    private var autoPilotTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()
    
    private init() {
        loadPersistedState()
        setupTradeBrainObservers()
    }
    
    // MARK: - Persistence
    private func loadPersistedState() {
        isAutoPilotEnabled = UserDefaults.standard.bool(forKey: "autopilot_enabled_v2")
        if let engineRaw = UserDefaults.standard.string(forKey: "autopilot_engine_v2"),
           let engine = AutoPilotEngine(rawValue: engineRaw) {
            selectedEngine = engine
        }
    }
    
    // MARK: - AutoPilot Control
    
    private func startAutoPilot() {
        print("🚀 AutoPilot Started: \(selectedEngine.rawValue)")
        NotificationCenter.default.post(name: .autoPilotStateChanged, object: nil, userInfo: ["enabled": true])
    }
    
    private func stopAutoPilot() {
        print("⏹️ AutoPilot Stopped")
        autoPilotTask?.cancel()
        autoPilotTask = nil
        isScanning = false
        NotificationCenter.default.post(name: .autoPilotStateChanged, object: nil, userInfo: ["enabled": false])
    }
    
    /// Toggle AutoPilot
    func toggleAutoPilot() {
        isAutoPilotEnabled.toggle()
    }
    
    /// Set scanning state
    func setScanning(_ scanning: Bool, symbols: [String] = []) {
        isScanning = scanning
        activeScanSymbols = symbols
        if scanning {
            lastScanTime = Date()
        }
    }
    
    // MARK: - Cooldown Management
    
    /// Check if symbol is in cooldown
    func isInCooldown(symbol: String) -> Bool {
        guard let cooldownEnd = tradeCooldowns[symbol] else { return false }
        return Date() < cooldownEnd
    }
    
    /// Set cooldown for a symbol
    func setCooldown(symbol: String, duration: TimeInterval) {
        tradeCooldowns[symbol] = Date().addingTimeInterval(duration)
    }
    
    /// Clear cooldown for a symbol
    func clearCooldown(symbol: String) {
        tradeCooldowns.removeValue(forKey: symbol)
    }
    
    /// Get remaining cooldown time
    func remainingCooldown(symbol: String) -> TimeInterval? {
        guard let cooldownEnd = tradeCooldowns[symbol] else { return nil }
        let remaining = cooldownEnd.timeIntervalSinceNow
        return remaining > 0 ? remaining : nil
    }
    
    // MARK: - Trade Brain Observers
    private func setupTradeBrainObservers() {
        NotificationCenter.default.publisher(for: .tradeBrainAlert)
            .receive(on: DispatchQueue.main)
            .compactMap { $0.userInfo?["alert"] as? TradeBrainAlert }
            .sink { [weak self] alert in
                self?.planAlerts.append(alert)
                // Keep last 50 alerts
                if self?.planAlerts.count ?? 0 > 50 {
                    self?.planAlerts.removeFirst()
                }
            }
            .store(in: &cancellables)
    }
    
    // MARK: - AGORA Snapshots
    
    /// Add decision snapshot
    func addAgoraSnapshot(_ snapshot: DecisionSnapshot) {
        agoraSnapshots.insert(snapshot, at: 0)
        // Keep last 100
        if agoraSnapshots.count > 100 {
            agoraSnapshots.removeLast()
        }
    }
    
    /// Get recent snapshots for a symbol
    func getRecentSnapshots(for symbol: String, limit: Int = 10) -> [DecisionSnapshot] {
        return agoraSnapshots
            .filter { $0.symbol == symbol }
            .prefix(limit)
            .map { $0 }
    }
}

// MARK: - Notification Names
extension Notification.Name {
    static let autoPilotStateChanged = Notification.Name("autoPilotStateChanged")
    static let tradeBrainAlert = Notification.Name("tradeBrainAlert")
}
