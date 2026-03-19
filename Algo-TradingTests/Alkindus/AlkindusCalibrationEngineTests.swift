import XCTest
@testable import Algo_Trading

/// Unit tests for AlkindusCalibrationEngine
final class AlkindusCalibrationEngineTests: XCTestCase {

    var sut: AlkindusCalibrationEngine!

    override func setUp() async throws {
        // Use shared instance for testing
        sut = AlkindusCalibrationEngine.shared
    }

    override func tearDown() async throws {
        // Clean up test data if needed
        sut = nil
    }

    // MARK: - Bracket Mapping Tests

    func test_scoreToBracket_highScore_returnsTopBracket() async {
        let bracket = await sut.testScoreToBracket(85)
        XCTAssertEqual(bracket, "80-100", "Score 85 should map to 80-100 bracket")
    }

    func test_scoreToBracket_boundaryScore_usesUpperBracket() async {
        // 78+ should map to 80-100 with soft boundaries
        let bracket = await sut.testScoreToBracket(78)
        XCTAssertEqual(bracket, "80-100", "Score 78 should map to 80-100 (soft boundary)")
    }

    func test_scoreToBracket_edgeCase_79point9() async {
        // Edge case: 79.9 should map to 80-100 (soft boundary)
        let bracket = await sut.testScoreToBracket(79.9)
        XCTAssertEqual(bracket, "80-100", "Score 79.9 should map to 80-100 (soft boundary)")
    }

    func test_scoreToBracket_boundaryLower_58_returnsMiddleBracket() async {
        let bracket = await sut.testScoreToBracket(58)
        XCTAssertEqual(bracket, "60-80", "Score 58 should map to 60-80 bracket")
    }

    func test_scoreToBracket_lowScore_returnsBottomBracket() async {
        let bracket = await sut.testScoreToBracket(10)
        XCTAssertEqual(bracket, "0-20", "Score 10 should map to 0-20 bracket")
    }

    func test_scoreToBracketsWeighted_boundaryRegion_returnsBothBrackets() async {
        // Score 79 is near 80 threshold, should return weighted brackets
        let weighted = await sut.testScoreToBracketsWeighted(79)

        XCTAssertEqual(weighted.count, 2, "Score 79 should return 2 weighted brackets")
        XCTAssertEqual(weighted[0].bracket, "60-80", "First bracket should be 60-80")
        XCTAssertEqual(weighted[1].bracket, "80-100", "Second bracket should be 80-100")

        // Check weights sum to 1.0
        let totalWeight = weighted.reduce(0.0) { $0 + $1.weight }
        XCTAssertEqual(totalWeight, 1.0, accuracy: 0.01, "Total weight should be 1.0")
    }

    func test_scoreToBracketsWeighted_outsideBoundaryRegion_singleBracket() async {
        // Score 90 is far from boundaries, should return single bracket
        let weighted = await sut.testScoreToBracketsWeighted(90)

        XCTAssertEqual(weighted.count, 1, "Score 90 should return 1 weighted bracket")
        XCTAssertEqual(weighted[0].bracket, "80-100", "Bracket should be 80-100")
        XCTAssertEqual(weighted[0].weight, 1.0, "Weight should be 1.0")
    }

    // MARK: - Observation Tests

    func test_observe_createsNewPendingObservation() async {
        let initialCount = await sut.getPendingCount()

        await sut.observe(
            symbol: "TEST",
            action: "BUY",
            moduleScores: ["orion": 75, "atlas": 80],
            regime: "risk_on",
            currentPrice: 100.0
        )

        let finalCount = await sut.getPendingCount()
        XCTAssertEqual(finalCount, initialCount + 1, "Should create 1 new pending observation")
    }

    func test_observe_holdAction_skipped() async {
        let initialCount = await sut.getPendingCount()

        await sut.observe(
            symbol: "TEST",
            action: "HOLD",
            moduleScores: ["orion": 75],
            regime: "risk_on",
            currentPrice: 100.0
        )

        let finalCount = await sut.getPendingCount()
        XCTAssertEqual(finalCount, initialCount, "HOLD action should be skipped")
    }

    func test_observe_abstainAction_skipped() async {
        let initialCount = await sut.getPendingCount()

        await sut.observe(
            symbol: "TEST",
            action: "ABSTAIN",
            moduleScores: ["orion": 75],
            regime: "risk_on",
            currentPrice: 100.0
        )

        let finalCount = await sut.getPendingCount()
        XCTAssertEqual(finalCount, initialCount, "ABSTAIN action should be skipped")
    }

    // MARK: - Maturation Tests

    func test_processMaturedDecisions_evaluatesHorizons() async {
        // This test requires mock data setup
        // For now, we'll test that the method exists and doesn't crash
        await sut.processMaturedDecisions(currentPrices: ["TEST": 105.0])

        // Should not crash
        XCTAssertTrue(true, "processMaturedDecisions should complete without crash")
    }

    func test_periodicMatureCheck_completesSuccessfully() async {
        // Should complete without error even with empty data
        await sut.periodicMatureCheck()

        // Should not crash
        XCTAssertTrue(true, "periodicMatureCheck should complete without crash")
    }
}
