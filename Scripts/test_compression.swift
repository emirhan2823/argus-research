
import Foundation

let str = "Hello World"
let data = str.data(using: .utf8)!
do {
    if #available(macOS 10.15, *) {
        let compressed = try data.compressed(using: .zlib)
        print("Compression success: \(compressed.count) bytes")
    } else {
        print("macOS 10.15 required")
    }
} catch {
    print("Error: \(error)")
}
