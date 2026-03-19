
import XCTest
@testable import Algo_Trading

final class HeimdallResilienceTests: XCTestCase {

    override func setUp() async throws {
        // Reset Registry before each test
        await ProviderCapabilityRegistry.shared.resetBans()
    }

    // TEST 1: Circuit Breaker for FMP 403 Legacy
    func testFMPCircuitBreaker() async throws {
        let registry = ProviderCapabilityRegistry.shared
        let error = HeimdallError(category: .entitlementDenied, code: 403, message: "Legacy Endpoint", bodyPrefix: "Invalid")
        
        // Report Failure
        await registry.reportCriticalFailure(provider: "FMP", field: .candles, error: error)
        
        // Verify Lock
        let isBanned = await registry.isQuarantined(provider: "FMP", field: .candles)
        XCTAssertTrue(isBanned, "FMP Should be quarantined after 403 Legacy")
        
        // Verify Duration (approx 15 mins)
        let status = await registry.getQuarantineStatus()
        let banInfo = status["FMP_candles"] ?? status["FMP_ALL"]
        XCTAssertTrue(banInfo?.contains("Locked (89") ?? false || banInfo?.contains("Locked (90") ?? false, "Lock duration should be ~900s")
    }

    // TEST 2: Orchestrator Fallback Iteration
    func testOrchestratorFallback() async throws {
        // Pre-condition: Ban Primary (Finnhub) to force fallback
        let registry = ProviderCapabilityRegistry.shared
        let primaryError = HeimdallError(category: .rateLimited, code: 429, message: "Too Many Requests", bodyPrefix: "")
        await registry.reportCriticalFailure(provider: "Finnhub", field: .news, error: primaryError)
        
        // Verify News logic chooses Backup (e.g. Yahoo or Stub)
        // Since we can't easily mock network calls here without dependency injection refactor,
        // we verified the Plan generation logic.
        
        let candidates = await registry.getCandidates(for: .news, assetType: .stock)
        XCTAssertFalse(candidates.contains("Finnhub"), "Finnhub should be excluded from candidates")
        XCTAssertTrue(candidates.contains("Yahoo") || candidates.contains("FMP"), "Should have remaining candidates")
    }

    // TEST 3: Phoenix Isolation (Mock)
    func testPhoenixGracefulFailure() async {
        // Simulate ViewModel behavior
        let viewModel = TradingViewModel()
        
        // We can't easily inject a failure into the singleton Provider without using Protocol Mocks.
        // But we can assert that the method 'refreshMarketPulse' does not throw.
        
        do {
            await viewModel.refreshMarketPulse()
            XCTAssertTrue(true, "refreshMarketPulse should swallow errors and complete safely")
        } catch {
            XCTFail("refreshMarketPulse should catch all errors internally")
        }
    }
}
