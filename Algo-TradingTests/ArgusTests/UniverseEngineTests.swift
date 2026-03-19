import XCTest
@testable import Algo_Trading

final class UniverseEngineTests: XCTestCase {
    
    override func setUp() async throws {
        // Clear Universe before each test
        // Since UniverseEngine is a singleton, this might be tricky.
        // Ideally we'd inject a store, but for now we test public API behavior.
    }
    
    func testRegistration() async {
        let engine = UniverseEngine.shared
        
        await engine.register(symbol: "AAPL", source: .watchlist, tags: ["Tech"])
        
        let universe = await engine.universe
        XCTAssertNotNil(universe["AAPL"])
        XCTAssertTrue(universe["AAPL"]!.sources.contains(.watchlist))
        XCTAssertTrue(universe["AAPL"]!.tags.contains("Tech"))
    }
    
    func testDeregistration() async {
        let engine = UniverseEngine.shared
        await engine.register(symbol: "TSLA", source: .manual)
        
        // Deregister Manual
        await engine.deregister(symbol: "TSLA", source: .manual)
        
        let item = await engine.universe["TSLA"]
        XCTAssertNotNil(item) // Should still exist
        XCTAssertFalse(item!.isActive) // But handle inactive
        XCTAssertFalse(item!.sources.contains(.manual))
    }
    
    func testMultipleSources() async {
        let engine = UniverseEngine.shared
        
        await engine.register(symbol: "NVDA", source: .watchlist)
        await engine.register(symbol: "NVDA", source: .scout) // Same symbol, different source
        
        let item = await engine.universe["NVDA"]!
        XCTAssertEqual(item.sources.count, 2)
        XCTAssertTrue(item.sources.contains(.watchlist))
        XCTAssertTrue(item.sources.contains(.scout))
        
        // Deregister one
        await engine.deregister(symbol: "NVDA", source: .watchlist)
        let itemUpdated = await engine.universe["NVDA"]!
        XCTAssertTrue(itemUpdated.isActive) // Still active via Scout
        XCTAssertEqual(itemUpdated.sources.count, 1)
        XCTAssertTrue(itemUpdated.sources.contains(.scout))
    }
    
    func testReasonString() async {
         let engine = UniverseEngine.shared
         await engine.register(symbol: "XRP-USD", source: .manual)
         await engine.register(symbol: "XRP-USD", source: .watchlist)
         
         let reason = await engine.getReason(for: "XRP-USD")
         // Order in Set is not guaranteed, but it should contain both
         XCTAssertTrue(reason.contains("Manual"))
         XCTAssertTrue(reason.contains("Watchlist"))
    }
}
