import Testing
@testable import Algo_Trading

struct InstrumentResolverTests {

    @Test func verifyYahooMappings() async {
        let resolver = InstrumentResolver.shared
        
        // VIX -> ^VIX (Yahoo)
        let vix = await resolver.resolve("VIX")
        #expect(vix.yahooSymbol == "^VIX")
        #expect(vix.internalId == "macro.vix") // Known def returns constant
        
        // DXY -> DX-Y.NYB (Yahoo)
        let dxy = await resolver.resolve("DXY")
        #expect(dxy.yahooSymbol == "DX-Y.NYB")
        
        // SILVER -> SI=F (Yahoo)
        let silver = await resolver.resolve("SILVER")
        #expect(silver.yahooSymbol == "SI=F")
        
        // SPY -> SPY
        let spy = await resolver.resolve("SPY")
        #expect(spy.yahooSymbol == "SPY")
    }

    @Test func verifyFredMappings() async {
        let resolver = InstrumentResolver.shared
        
        // CPI -> CPIAUCSL (FRED)
        let cpi = await resolver.resolve("CPI")
        #expect(cpi.fredSeriesId == "CPIAUCSL")
        
        // RATES -> DGS10 (FRED)
        let rates = await resolver.resolve("RATES")
        #expect(rates.fredSeriesId == "DGS10")
        
        // BOND2Y -> DGS2
        let bond2 = await resolver.resolve("BOND2Y")
        #expect(bond2.fredSeriesId == "DGS2")
    }

    @Test func verifyFallback() async {
        let resolver = InstrumentResolver.shared
        
        // Unknown Stock -> Returns as is
        let aapl = await resolver.resolve("AAPL")
        #expect(aapl.internalId == "AAPL")
        #expect(aapl.yahooSymbol == "AAPL")
        #expect(aapl.assetType == .stock)
        
        // Forex Fallback detection
        let fx = await resolver.resolve("EURUSD=X")
        #expect(fx.assetType == .forex)
        
        // Index Fallback detection
        let idx = await resolver.resolve("^GDAXI")
        #expect(idx.assetType == .index)
    }
}
