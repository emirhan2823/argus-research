/*
 //
 //  ArgusWidget.swift
 //  ArgusWidgetExtension
 //
 //  Created for Argus Terminal using ArgusStorage
 //
 //  INSTRUCTIONS:
 //  1. Create a new Widget Target in Xcode (File > New > Target > Widget Extension).
 //  2. Name it "ArgusWidget".
 //  3. Ensure "App Groups" capability is enabled for BOTH the Main App and the Widget Extension.
 //  4. Use the SAME Group ID: "group.com.yourcompany.argus" (Update ArgusStorage.swift with this ID too).
 //  5. Copy the code below into your Widget's main swift file.
 //  6. Make sure ArgusStorage.swift and ArgusLabModels.swift (WidgetConfig part) are added to the Widget Target membership.
 //
 
 import WidgetKit
 import SwiftUI
 
 struct Provider: TimelineProvider {
     
     // Use Shared Storage
     let storage = ArgusStorage.shared
     
     func placeholder(in context: Context) -> ArgusEntry {
         ArgusEntry(date: Date(), items: mockItems())
     }
 
     func getSnapshot(in context: Context, completion: @escaping (ArgusEntry) -> ()) {
         let entry = ArgusEntry(date: Date(), items: loadItemsFromStorage())
         completion(entry)
     }
 
     func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> ()) {
         let currentDate = Date()
         
         // 1. Load Data from Shared Storage (Fast, No Network)
         let items = loadItemsFromStorage()
         
         // 2. Schedule Next Update (e.g. every 15 mins)
         let nextUpdateDate = Calendar.current.date(byAdding: .minute, value: 15, to: currentDate)!
         
         let entry = ArgusEntry(date: currentDate, items: items)
         
         let timeline = Timeline(entries: [entry], policy: .after(nextUpdateDate))
         completion(timeline)
     }
     
     // MARK: - Helpers
     
     func loadItemsFromStorage() -> [WidgetDisplayItem] {
         guard let config = storage.loadWidgetConfig() else {
             return [WidgetDisplayItem(symbol: "NO CONFIG", price: 0, change: 0, signal: "---")]
         }
         
         let scores = storage.loadWidgetScores()
         
         return config.symbols.map { symbol in
             if let data = scores[symbol] {
                 return WidgetDisplayItem(
                     symbol: symbol,
                     price: data.price,
                     change: data.changePercent,
                     signal: data.signal == .buy ? "AL" : (data.signal == .sell ? "SAT" : "TUT")
                 )
             } else {
                 return WidgetDisplayItem(symbol: symbol, price: 0, change: 0, signal: "---")
             }
         }
     }
     
     func mockItems() -> [WidgetDisplayItem] {
         [
             WidgetDisplayItem(symbol: "AAPL", price: 175.50, change: 1.25, signal: "AL"),
             WidgetDisplayItem(symbol: "BTC", price: 65000, change: -0.5, signal: "TUT")
         ]
     }
 }
 
 struct ArgusEntry: TimelineEntry {
     let date: Date
     let items: [WidgetDisplayItem]
 }
 
 struct WidgetDisplayItem: Identifiable {
     let id = UUID()
     let symbol: String
     let price: Double
     let change: Double
     let signal: String
 }
 
 struct ArgusWidgetEntryView : View {
     var entry: Provider.Entry
     @Environment(\.widgetFamily) var family
 
     var body: some View {
         VStack(spacing: 0) {
             // Header
             HStack {
                 Text("ARGUS")
                     .font(.caption)
                     .bold()
                     .foregroundColor(.cyan)
                 Spacer()
                 Text(entry.date, style: .time)
                     .font(.caption2)
                     .foregroundColor(.gray)
             }
             .padding(.bottom, 8)
             
             // List
             ForEach(entry.items.prefix(4)) { item in
                 HStack {
                     Text(item.symbol)
                         .font(.system(size: 12, weight: .bold))
                         .frame(width: 45, alignment: .leading)
                     
                     Spacer()
                     
                     Text("\(item.price, specifier: "%.2f")")
                         .font(.system(size: 12))
                         .foregroundColor(.white)
                     
                     Text("\(item.change > 0 ? "+" : "")\(item.change, specifier: "%.1f")%")
                         .font(.system(size: 10))
                         .foregroundColor(item.change >= 0 ? .green : .red)
                         .frame(width: 40, alignment: .trailing)
                     
                     // Signal Badge if Space Permits
                     Text(item.signal.prefix(1))
                         .font(.system(size: 8, weight: .heavy))
                         .padding(3)
                         .background(item.signal == "AL" ? Color.green : (item.signal == "SAT" ? Color.red : Color.gray))
                         .cornerRadius(4)
                 }
                 .padding(.vertical, 2)
                 Divider().opacity(0.2)
             }
             Spacer()
         }
         .padding()
         .background(Color(red: 0.05, green: 0.07, blue: 0.12)) // Argus Dark Blue
     }
 }
 
 @main
 struct ArgusWidget: Widget {
     let kind: String = "ArgusWidget"
 
     var body: some WidgetConfiguration {
         StaticConfiguration(kind: kind, provider: Provider()) { entry in
             ArgusWidgetEntryView(entry: entry)
         }
         .configurationDisplayName("Argus Terminal")
         .description("Portföy ve Sinyalleriniz.")
         .supportedFamilies([.systemSmall, .systemMedium])
     }
 }
 */
