import Foundation

// MARK: - Aegean Indicator (Pine v5 port, simplified but faithful)

struct AegeanConfig {
    var rsiLength: Int = 5
    var expSmoothFactor: Double = 0.1
    var emaPeriod: Int = 200
    var linearRegSmoothing: Int = 5
    var channelMultiplier: Double = 2.0

    // Pine conditions:
    // sell_signal = crossover(expRsi, upper) OR (expRsi > upper*1.05)
    // buy_signal  = crossunder(expRsi, lower) OR (expRsi < lower*0.95)
    var sellOvershoot: Double = 1.05
    var buyOvershoot: Double = 0.95
}

enum AegeanSignal: String { case buy, sell, none }

struct AegeanOutput {
    let signal: AegeanSignal
    let expRsi: Double
    let upper: Double
    let lower: Double
}

enum AegeanIndicator {

    static func compute(candles: [Candle], config: AegeanConfig = .init()) -> AegeanOutput? {
        // Needs enough bars for emaPeriod and smoothing
        let minBars = max(config.emaPeriod + 5, config.rsiLength + 5)
        guard candles.count >= minBars else { return nil }

        // 1) hlc3 series
        let hlc3: [Double] = candles.map { ($0.high + $0.low + $0.close) / 3.0 }

        // 2) RSI on hlc3
        guard let rsiSeries = rsi(values: hlc3, length: config.rsiLength) else { return nil }

        // 3) Exponential smoothing of RSI (expRsi in Pine)
        let expRsiSeries = expSmooth(values: rsiSeries, alpha: config.expSmoothFactor)

        // 4) changeFromMean = percentChangeFromMean(expRsi, emaPeriod)
        guard let changeFromMean = percentChangeFromMean(values: expRsiSeries, length: config.emaPeriod) else { return nil }

        // 5) linearRegValue = linreg(changeFromMean, linearRegSmoothing)
        guard let linReg = linreg(values: changeFromMean, length: config.linearRegSmoothing) else { return nil }

        // 6) previousValue = ema(expRsi, emaPeriod)[1]
        guard let emaExp = ema(values: expRsiSeries, length: config.emaPeriod) else { return nil }
        // We want "previous bar" values for band reference like Pine's [1]
        let i = candles.count - 1
        guard i - 1 >= 0 else { return nil }

        let prevEma = emaExp[i - 1]
        let lr = linReg[i] // linreg at current bar
        let mult = config.channelMultiplier

        // upper = prevEma * ((lr*mult/100)+1)
        // lower = prevEma * (1 - (lr*mult/100))
        let upper = prevEma * ((lr * mult / 100.0) + 1.0)
        let lower = prevEma * (1.0 - (lr * mult / 100.0))

        let expRsiNow = expRsiSeries[i]
        let expRsiPrev = expRsiSeries[i - 1]

        // bands (we approximate bands as computed per bar; Pine uses linebr but logic uses values)
        // For crossover/crossunder we compare prev vs now.
        // Need prev bands too:
        let prevPrevEma = (i - 2 >= 0) ? emaExp[i - 2] : prevEma
        let lrPrev = linReg[i - 1]
        let upperPrev = prevPrevEma * ((lrPrev * mult / 100.0) + 1.0)
        let lowerPrev = prevPrevEma * (1.0 - (lrPrev * mult / 100.0))

        let sellCrossover = (expRsiPrev <= upperPrev) && (expRsiNow > upper)
        let buyCrossunder = (expRsiPrev >= lowerPrev) && (expRsiNow < lower)

        let sellOvershoot = expRsiNow > (upper * config.sellOvershoot)
        let buyOvershoot  = expRsiNow < (lower * config.buyOvershoot)

        let sell = sellCrossover || sellOvershoot
        let buy  = buyCrossunder || buyOvershoot

        let signal: AegeanSignal
        if sell && !buy { signal = .sell }
        else if buy && !sell { signal = .buy }
        else { signal = .none }

        return AegeanOutput(signal: signal, expRsi: expRsiNow, upper: upper, lower: lower)
    }

    // MARK: - Helpers

    private static func expSmooth(values: [Double], alpha: Double) -> [Double] {
        guard !values.isEmpty else { return [] }
        var out = Array(repeating: 0.0, count: values.count)
        out[0] = values[0]
        if values.count == 1 { return out }
        for i in 1..<values.count {
            out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
        }
        return out
    }

    private static func sma(values: [Double], length: Int) -> [Double]? {
        guard length > 0, values.count >= length else { return nil }
        var out = Array(repeating: Double.nan, count: values.count)
        var sum = 0.0
        for i in 0..<values.count {
            sum += values[i]
            if i >= length { sum -= values[i - length] }
            if i >= length - 1 { out[i] = sum / Double(length) }
        }
        return out
    }

    private static func ema(values: [Double], length: Int) -> [Double]? {
        guard length > 0, values.count >= length else { return nil }
        let alpha = 2.0 / (Double(length) + 1.0)
        var out = Array(repeating: Double.nan, count: values.count)

        // seed with SMA at first valid point
        var seed = 0.0
        for i in 0..<length { seed += values[i] }
        seed /= Double(length)
        out[length - 1] = seed

        if values.count == length { return out }

        for i in length..<values.count {
            let prev = out[i - 1].isNaN ? seed : out[i - 1]
            out[i] = alpha * values[i] + (1.0 - alpha) * prev
        }
        return out
    }

    private static func rsi(values: [Double], length: Int) -> [Double]? {
        guard length > 0, values.count >= length + 1 else { return nil }

        var gains = Array(repeating: 0.0, count: values.count)
        var losses = Array(repeating: 0.0, count: values.count)

        for i in 1..<values.count {
            let ch = values[i] - values[i - 1]
            if ch >= 0 { gains[i] = ch }
            else { losses[i] = -ch }
        }

        // Wilder's smoothing
        var avgGain = 0.0
        var avgLoss = 0.0
        for i in 1...length {
            avgGain += gains[i]
            avgLoss += losses[i]
        }
        avgGain /= Double(length)
        avgLoss /= Double(length)

        var out = Array(repeating: Double.nan, count: values.count)
        out[length] = rsiValue(avgGain: avgGain, avgLoss: avgLoss)

        if values.count == length + 1 { return out }

        for i in (length + 1)..<values.count {
            avgGain = (avgGain * Double(length - 1) + gains[i]) / Double(length)
            avgLoss = (avgLoss * Double(length - 1) + losses[i]) / Double(length)
            out[i] = rsiValue(avgGain: avgGain, avgLoss: avgLoss)
        }

        // fill earlier NaNs with first computed for stability
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

    private static func percentChangeFromMean(values: [Double], length: Int) -> [Double]? {
        guard let mean = sma(values: values, length: length) else { return nil }
        var out = Array(repeating: Double.nan, count: values.count)

        for i in 0..<values.count {
            if i < length - 1 || mean[i].isNaN { continue }
            let m = mean[i]
            if m == 0 { out[i] = 0; continue }

            var sumAbs = 0.0
            for k in 0..<length {
                let v = values[i - k]
                sumAbs += abs(((v - m) / m) * 100.0)
            }
            out[i] = sumAbs / Double(length)
        }

        // forward-fill NaNs to keep arrays usable
        var last = 0.0
        for i in 0..<out.count {
            if out[i].isNaN { out[i] = last }
            else { last = out[i] }
        }
        return out
    }

    private static func linreg(values: [Double], length: Int) -> [Double]? {
        // Linear regression value at each point over last `length` samples
        guard length > 1, values.count >= length else { return nil }
        var out = Array(repeating: Double.nan, count: values.count)

        // x = 0...(length-1)
        let n = Double(length)
        let sumX = (n - 1.0) * n / 2.0
        let sumX2 = (n - 1.0) * n * (2.0 * n - 1.0) / 6.0
        let denom = n * sumX2 - sumX * sumX

        for i in (length - 1)..<values.count {
            var sumY = 0.0
            var sumXY = 0.0
            for k in 0..<length {
                let x = Double(k)
                let y = values[i - (length - 1) + k]
                sumY += y
                sumXY += x * y
            }
            let slope = (n * sumXY - sumX * sumY) / denom
            let intercept = (sumY - slope * sumX) / n

            // Pine linreg(..., offset=0) returns value at last x (length-1)
            let xLast = n - 1.0
            out[i] = intercept + slope * xLast
        }

        // fill leading NaNs
        var last = out.first(where: { !$0.isNaN }) ?? 0.0
        for i in 0..<out.count {
            if out[i].isNaN { out[i] = last }
            else { last = out[i] }
        }
        return out
    }
}
