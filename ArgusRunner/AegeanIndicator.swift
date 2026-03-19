import Foundation

enum AegeanSignal: String {
    case buy
    case sell
    case none
}

enum AegeanZone: String {
    case dip     // near lower band
    case neutral
    case top     // near upper band
}

struct AegeanOutput {
    let expRsi: Double
    let upper: Double
    let lower: Double
    let signal: AegeanSignal

    // Pre-signal extras
    let pos: Double        // 0..1 position in band
    let zone: AegeanZone   // DIP / NEUTRAL / TOP
    let slope: Double      // expRsi delta over N bars
    let slopeDir: String   // UP / DOWN / FLAT
}

enum AegeanIndicator {

    // Defaults match your Pine inputs
    struct Config {
        let rsiLength: Int
        let expSmoothFactor: Double
        let emaPeriod: Int
        let linearRegSmoothing: Int
        let channelMultiplier: Double

        let posDipThreshold: Double
        let posTopThreshold: Double
        let slopeLookback: Int
        let slopeEps: Double

        init(
            rsiLength: Int = 5,
            expSmoothFactor: Double = 0.1,
            emaPeriod: Int = 200,
            linearRegSmoothing: Int = 5,
            channelMultiplier: Double = 2,

            posDipThreshold: Double = 0.20,
            posTopThreshold: Double = 0.80,
            slopeLookback: Int = 3,
            slopeEps: Double = 0.15
        ) {
            self.rsiLength = rsiLength
            self.expSmoothFactor = expSmoothFactor
            self.emaPeriod = emaPeriod
            self.linearRegSmoothing = linearRegSmoothing
            self.channelMultiplier = channelMultiplier
            self.posDipThreshold = posDipThreshold
            self.posTopThreshold = posTopThreshold
            self.slopeLookback = slopeLookback
            self.slopeEps = slopeEps
        }
    }

    static func compute(candles: [RunnerCandle], cfg: Config = Config()) -> AegeanOutput? {
        // Need enough bars for EMA and percentChange window
        let minBars = max(cfg.emaPeriod + cfg.rsiLength + cfg.linearRegSmoothing + 5, 260)
        guard candles.count >= minBars else { return nil }

        // Build HLC3 series
        let hlc3: [Double] = candles.map { ( $0.high + $0.low + $0.close ) / 3.0 }

        // 1) RSI on hlc3
        guard let rsiSeries = rsi(series: hlc3, length: cfg.rsiLength) else { return nil }

        // 2) Exponential smoothing on RSI (expRsi)
        let expRsiSeries = expSmooth(series: rsiSeries, alpha: cfg.expSmoothFactor)

        // 3) percentChangeFromMean(expRsi, emaPeriod) -> series
        guard let changeFromMean = percentChangeFromMeanSeries(series: expRsiSeries, length: cfg.emaPeriod) else { return nil }

        // 4) linearRegValue = linreg(changeFromMean, linearRegSmoothing)
        guard let linregSeries = linreg(series: changeFromMean, length: cfg.linearRegSmoothing) else { return nil }
        guard let linearRegValue = linregSeries.last else { return nil }

        // 5) previousValue = ema(expRsi, emaPeriod)[1]
        guard let emaExpRsi = ema(series: expRsiSeries, period: cfg.emaPeriod) else { return nil }
        guard emaExpRsi.count >= 3 else { return nil }
        let previousValue = emaExpRsi[emaExpRsi.count - 2] // [1] previous bar

        // 6) upper/lower channel
        let bandFactor = (linearRegValue * cfg.channelMultiplier / 100.0)
        let upper = previousValue * (bandFactor + 1.0)
        let lower = previousValue * (1.0 - bandFactor)

        // Current & previous expRsi for crossover tests
        let currExp = expRsiSeries.last!
        let prevExp = expRsiSeries[expRsiSeries.count - 2]

        // Approx prevUpper/prevLower using one-step-back stats
        let prevLinearRegValue = linregSeries[linregSeries.count - 2]
        let prevPrevValue = emaExpRsi[emaExpRsi.count - 3]
        let prevBandFactor = (prevLinearRegValue * cfg.channelMultiplier / 100.0)
        let prevUpper = prevPrevValue * (prevBandFactor + 1.0)
        let prevLower = prevPrevValue * (1.0 - prevBandFactor)

        // Pine signals
        let sellCross = (prevExp <= prevUpper) && (currExp > upper)
        let buyCross  = (prevExp >= prevLower) && (currExp < lower)

        let sellOver  = currExp > upper * 1.05
        let buyUnder  = currExp < lower * 0.95

        let signal: AegeanSignal
        if sellCross || sellOver {
            signal = .sell
        } else if buyCross || buyUnder {
            signal = .buy
        } else {
            signal = .none
        }

        // Pre-signal metrics
        let denom = max(upper - lower, 1e-9)
        var pos = (currExp - lower) / denom
        pos = max(0.0, min(1.0, pos))

        let zone: AegeanZone
        if pos <= cfg.posDipThreshold { zone = .dip }
        else if pos >= cfg.posTopThreshold { zone = .top }
        else { zone = .neutral }

        // slope: last - N bars back
        let n = max(1, cfg.slopeLookback)
        let idxBack = max(0, expRsiSeries.count - 1 - n)
        let slope = currExp - expRsiSeries[idxBack]

        let slopeDir: String
        if slope > cfg.slopeEps { slopeDir = "UP" }
        else if slope < -cfg.slopeEps { slopeDir = "DOWN" }
        else { slopeDir = "FLAT" }

        return AegeanOutput(
            expRsi: currExp,
            upper: upper,
            lower: lower,
            signal: signal,
            pos: pos,
            zone: zone,
            slope: slope,
            slopeDir: slopeDir
        )
    }

    // MARK: - Helpers

    private static func expSmooth(series: [Double], alpha: Double) -> [Double] {
        guard !series.isEmpty else { return [] }
        var out = Array(repeating: 0.0, count: series.count)
        out[0] = series[0]
        let a = max(0.0001, min(1.0, alpha))
        for i in 1..<series.count {
            out[i] = a * series[i] + (1.0 - a) * out[i-1]
        }
        return out
    }

    private static func sma(_ arr: ArraySlice<Double>) -> Double {
        let c = Double(arr.count)
        if c == 0 { return 0 }
        return arr.reduce(0.0, +) / c
    }

    private static func ema(series: [Double], period: Int) -> [Double]? {
        guard period > 0, series.count >= period else { return nil }
        let k = 2.0 / (Double(period) + 1.0)
        var out = Array(repeating: 0.0, count: series.count)

        // seed with SMA of first period
        let seed = sma(series[0..<period])
        out[period - 1] = seed

        if period < series.count {
            for i in period..<series.count {
                out[i] = series[i] * k + out[i - 1] * (1.0 - k)
            }
        }

        return out
    }

    // RSI on a series (Wilder)
    private static func rsi(series: [Double], length: Int) -> [Double]? {
        guard length > 0, series.count > length else { return nil }

        var gains = Array(repeating: 0.0, count: series.count)
        var losses = Array(repeating: 0.0, count: series.count)

        for i in 1..<series.count {
            let diff = series[i] - series[i-1]
            gains[i] = max(0.0, diff)
            losses[i] = max(0.0, -diff)
        }

        var avgGain = sma(gains[1...length])
        var avgLoss = sma(losses[1...length])

        var out = Array(repeating: 0.0, count: series.count)

        out[length] = rsiValue(avgGain: avgGain, avgLoss: avgLoss)

        if length + 1 < series.count {
            for i in (length + 1)..<series.count {
                avgGain = (avgGain * Double(length - 1) + gains[i]) / Double(length)
                avgLoss = (avgLoss * Double(length - 1) + losses[i]) / Double(length)
                out[i] = rsiValue(avgGain: avgGain, avgLoss: avgLoss)
            }
        }

        // fill leading indices
        for i in 0..<length {
            out[i] = out[length]
        }

        return out
    }

    private static func rsiValue(avgGain: Double, avgLoss: Double) -> Double {
        if avgLoss == 0 { return 100.0 }
        let rs = avgGain / avgLoss
        return 100.0 - (100.0 / (1.0 + rs))
    }

    // percentChangeFromMean(source, length) series
    private static func percentChangeFromMeanSeries(series: [Double], length: Int) -> [Double]? {
        guard length > 1, series.count >= length else { return nil }
        var out = Array(repeating: 0.0, count: series.count)

        for i in 0..<series.count {
            let start = max(0, i - (length - 1))
            let slice = series[start...i]
            let mean = sma(slice)
            let denom = abs(mean) < 1e-9 ? 1e-9 : mean

            var sumAbsPct = 0.0
            for v in slice {
                sumAbsPct += abs(((v - mean) / denom) * 100.0)
            }
            out[i] = sumAbsPct / Double(slice.count)
        }

        return out
    }

    // Linear regression value of series over `length` at each bar
    private static func linreg(series: [Double], length: Int) -> [Double]? {
        guard length > 1, series.count >= length else { return nil }
        var out = Array(repeating: 0.0, count: series.count)

        for i in 0..<series.count {
            let start = max(0, i - (length - 1))
            let slice = Array(series[start...i])
            let m = Double(slice.count)

            let xs = (0..<slice.count).map { Double($0) }
            let xMean = xs.reduce(0.0, +) / m
            let yMean = slice.reduce(0.0, +) / m

            let xVar = xs.map { ($0 - xMean) * ($0 - xMean) }.reduce(0.0, +)
            let denom = xVar < 1e-9 ? 1e-9 : xVar

            var cov = 0.0
            for j in 0..<slice.count {
                cov += (xs[j] - xMean) * (slice[j] - yMean)
            }

            let slope = cov / denom
            let intercept = yMean - slope * xMean

            let xPred = Double(slice.count - 1)
            out[i] = intercept + slope * xPred
        }

        return out
    }
}
