import XCTest
@testable import Algo_Trading

/// Unit tests for AlkindusMemoryStore
final class AlkindusMemoryStoreTests: XCTestCase {

    var sut: AlkindusMemoryStore!

    override func setUp() async throws {
        // Use shared instance for testing
        sut = AlkindusMemoryStore.shared
    }

    override func tearDown() async throws {
        // Clean up test data if needed
        sut = nil
    }

    // MARK: - Persistence Tests

    func test_saveAndLoad_preservesCalibrationData() async {
        // Get initial data
        let initialCalibration = await sut.loadCalibration()
        let initialModuleCount = initialCalibration.modules.count

        // Modify calibration
        await sut.recordOutcomeWeighted(
            module: "test_module",
            scoreBracket: "80-100",
            wasCorrect: true,
            weight: 1.0,
            regime: "risk_on"
        )

        // Force save and reload
        await sut.saveToDisk()
        await sut.loadFromDisk()

        // Verify persisted
        let loadedCalibration = await sut.loadCalibration()
        XCTAssertNotNil(loadedCalibration.modules["test_module"], "Test module should be persisted")

        // Verify stats
        let moduleStats = loadedCalibration.modules["test_module"]
        XCTAssertNotNil(moduleStats, "Module stats should exist")
        XCTAssertGreaterThanOrEqual(moduleStats!.brackets["80-100"]?.attempts ?? 0, 1, "Should have at least 1 attempt")
    }

    func test_recordOutcomeWeighted_increasesAttempts() async {
        // Reset test data
        await sut.recordOutcomeWeighted(
            module: "test_module_2",
            scoreBracket: "60-80",
            wasCorrect: true,
            weight: 1.0,
            regime: "risk_on"
        )

        let calibration = await sut.loadCalibration()
        let moduleStats = calibration.modules["test_module_2"]

        XCTAssertNotNil(moduleStats, "Module stats should exist")
        XCTAssertEqual(moduleStats!.brackets["60-80"]?.attempts ?? 0, 1.0, "Attempts should be 1.0")
    }

    func test_recordOutcomeWeighted_increasesCorrect() async {
        // Record correct outcome
        await sut.recordOutcomeWeighted(
            module: "test_module_3",
            scoreBracket: "80-100",
            wasCorrect: true,
            weight: 1.0,
            regime: "risk_on"
        )

        let calibration = await sut.loadCalibration()
        let moduleStats = calibration.modules["test_module_3"]

        XCTAssertNotNil(moduleStats, "Module stats should exist")
        XCTAssertEqual(moduleStats!.brackets["80-100"]?.correct ?? 0, 1.0, "Correct count should be 1.0")
    }

    func test_recordOutcomeWeighted_calculatesHitRate() async {
        // Record 2 outcomes: 1 correct, 1 incorrect
        await sut.recordOutcomeWeighted(
            module: "test_module_4",
            scoreBracket: "80-100",
            wasCorrect: true,
            weight: 1.0,
            regime: "risk_on"
        )

        await sut.recordOutcomeWeighted(
            module: "test_module_4",
            scoreBracket: "80-100",
            wasCorrect: false,
            weight: 1.0,
            regime: "risk_on"
        )

        let calibration = await sut.loadCalibration()
        let moduleStats = calibration.modules["test_module_4"]

        XCTAssertNotNil(moduleStats, "Module stats should exist")

        let attempts = moduleStats!.brackets["80-100"]?.attempts ?? 0
        let correct = moduleStats!.brackets["80-100"]?.correct ?? 0
        let hitRate = moduleStats!.brackets["80-100"]?.hitRate ?? 0

        XCTAssertEqual(attempts, 2.0, "Attempts should be 2.0")
        XCTAssertEqual(correct, 1.0, "Correct should be 1.0")
        XCTAssertEqual(hitRate, 0.5, accuracy: 0.01, "Hit rate should be 0.5")
    }

    // MARK: - Pending Observations Tests

    func test_appendPendingObservation_increasesCount() async {
        // Get initial count
        let initialPending = await sut.loadPendingObservations()

        // Create test observation
        let testObservation = PendingObservation(
            symbol: "TEST_SYMBOL",
            decisionDate: Date(),
            action: "BUY",
            moduleScores: ["orion": 75.0],
            regime: "risk_on",
            priceAtDecision: 100.0,
            horizons: [7, 15],
            evaluatedHorizons: []
        )

        await sut.appendPendingObservation(testObservation)

        // Verify count increased
        let finalPending = await sut.loadPendingObservations()
        XCTAssertEqual(finalPending.count, initialPending.count + 1, "Pending observations should increase by 1")
    }

    func test_removePendingObservation_decreasesCount() async {
        // Create test observation
        let testObservation = PendingObservation(
            symbol: "TEST_SYMBOL_REMOVE",
            decisionDate: Date(),
            action: "BUY",
            moduleScores: ["orion": 75.0],
            regime: "risk_on",
            priceAtDecision: 100.0,
            horizons: [7, 15],
            evaluatedHorizons: []
        )

        await sut.appendPendingObservation(testObservation)

        let pendingBefore = await sut.loadPendingObservations()

        // Remove it
        if let index = pendingBefore.firstIndex(where: { $0.symbol == "TEST_SYMBOL_REMOVE" }) {
            await sut.removePendingObservation(at: index)
        }

        // Verify count decreased
        let pendingAfter = await sut.loadPendingObservations()
        XCTAssertEqual(pendingAfter.count, pendingBefore.count - 1, "Pending observations should decrease by 1")
    }

    // MARK: - Bootstrap Tests

    func test_importBootstrap_loadsInitialCalibration() async {
        await sut.importBootstrapCalibration()

        let calibration = await sut.loadCalibration()

        // Bootstrap should have modules
        XCTAssertGreaterThanOrEqual(calibration.modules.count, 5, "Bootstrap should have at least 5 modules")

        // Orion should exist
        XCTAssertNotNil(calibration.modules["orion"], "Orion module should exist")
        XCTAssertNotNil(calibration.modules["atlas"], "Atlas module should exist")
        XCTAssertNotNil(calibration.modules["aether"], "Aether module should exist")
        XCTAssertNotNil(calibration.modules["hermes"], "Hermes module should exist")
        XCTAssertNotNil(calibration.modules["athena"], "Athena module should exist")
    }

    func test_importBootstrap_setsDefaultWeights() async {
        await sut.importBootstrapCalibration()

        let calibration = await sut.loadCalibration()

        // Each module should have bracket stats
        for (moduleName, moduleCal) in calibration.modules {
            XCTAssertFalse(moduleCal.brackets.isEmpty, "Module \(moduleName) should have bracket stats")

            // Verify each bracket has hitRate
            for (bracketName, bracketStats) in moduleCal.brackets {
                XCTAssertNotNil(bracketStats.hitRate, "Bracket \(bracketName) should have hitRate")
                XCTAssertGreaterThanOrEqual(bracketStats.hitRate, 0.0, "Hit rate should be >= 0.0")
                XCTAssertLessThanOrEqual(bracketStats.hitRate, 1.0, "Hit rate should be <= 1.0")
            }
        }
    }

    // MARK: - Data Integrity Tests

    func test_updateModuleCalibration_createsModuleIfNotExists() async {
        // Record outcome for non-existent module
        await sut.recordOutcomeWeighted(
            module: "new_test_module",
            scoreBracket: "60-80",
            wasCorrect: true,
            weight: 1.0,
            regime: "risk_on"
        )

        let calibration = await sut.loadCalibration()

        XCTAssertNotNil(calibration.modules["new_test_module"], "New module should be created")
    }

    func test_updateModuleCalibration_updatesExistingModule() async {
        // Record first outcome
        await sut.recordOutcomeWeighted(
            module: "existing_test_module",
            scoreBracket: "80-100",
            wasCorrect: true,
            weight: 1.0,
            regime: "risk_on"
        )

        let calibration1 = await sut.loadCalibration()
        let attempts1 = calibration1.modules["existing_test_module"]?.brackets["80-100"]?.attempts ?? 0

        // Record second outcome
        await sut.recordOutcomeWeighted(
            module: "existing_test_module",
            scoreBracket: "80-100",
            wasCorrect: true,
            weight: 1.0,
            regime: "risk_on"
        )

        let calibration2 = await sut.loadCalibration()
        let attempts2 = calibration2.modules["existing_test_module"]?.brackets["80-100"]?.attempts ?? 0

        XCTAssertEqual(attempts2, attempts1 + 1.0, "Attempts should increase")
    }
}
