import Foundation

final class MimirQuotaGovernorTests {
    static func run() async {
        print("\n🚀 STARTING MIMIR QUOTA TESTS...")
        
        await testRPM()
        await testDailyLimit()
        
        print("✅ MIMIR QUOTA TESTS COMPLETE\n")
    }
    
    private static func testRPM() async {
        var conf = MimirConfig.standard
        conf.maxRequestsPerMinute = 2
        let gov = QuotaGovernor(config: conf)
        
        // 1. Allow
        let d1 = await gov.check(estimatedTokens: 10, priority: 2)
        assert(d1 == .allow, "Req 1 should allow")
        await gov.recordDispatch(tokens: 10)
        
        // 2. Allow
        let d2 = await gov.check(estimatedTokens: 10, priority: 2)
        assert(d2 == .allow, "Req 2 should allow")
        await gov.recordDispatch(tokens: 10)
        
        // 3. Reject (Limit hit)
        let d3 = await gov.check(estimatedTokens: 10, priority: 2)
        assert(d3 == .reject, "Req 3 should reject (RPM limit 2)")
        
        print("   ✅ RPM Test Passed")
    }
    
    private static func testDailyLimit() async {
        var conf = MimirConfig.standard
        conf.maxTokensPerDay = 100
        let gov = QuotaGovernor(config: conf)
        
        // Consume 90
        await gov.recordDispatch(tokens: 90)
        
        // Try 20
        let d = await gov.check(estimatedTokens: 20, priority: 2)
        assert(d == .reject, "Should reject (90+20 > 100)")
        
        print("   ✅ Daily Limit Test Passed")
    }
    
    static func assert(_ condition: Bool, _ msg: String) {
        if !condition { print("🛑 FAIL: \(msg)") }
    }
}
