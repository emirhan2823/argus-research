import SwiftUI

struct ContentView: View {
    @EnvironmentObject var viewModel: TradingViewModel // Singleton
    // @StateObject private var viewModel = TradingViewModel() // Removed local creation
    @State private var isAppReady = false
    @State private var selectedTab = 0
    @StateObject private var settingsViewModel = SettingsViewModel()
    @State private var showVoiceSheet = false
    
    // Deep Link State
    @State private var showNotificationsSheet = false
    @State private var notificationID: String? = nil
    
    var body: some View {
        ZStack {
            // Global Living Background
            ArgusGlobalBackground()
                .zIndex(0)
            
            if !isAppReady {
                ArgusCinematicIntro(onFinished: {
                    withAnimation {
                        isAppReady = true
                    }
                })
                .zIndex(2)
                .transition(.opacity)
            } else {
                ZStack(alignment: .bottom) {
                    // Main Content
                    Group {
                        switch selectedTab {
                        case 0:
                            MarketView()
                                .environmentObject(viewModel)
                        case 1:
                            ArgusCockpitView()
                                .environmentObject(viewModel)
                        case 2:
                            ArgusSimulatorView()
                        case 3:
                            PortfolioView(viewModel: viewModel)
                        case 4:
                            SettingsView(settingsViewModel: settingsViewModel)
                        default:
                            MarketView()
                                .environmentObject(viewModel)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    
                    // Custom Tab Bar (ADS Floating)
                    ArgusFloatingTabBar(selectedTab: $selectedTab, showVoiceSheet: $showVoiceSheet)
                        // Gradient Mask to hide content behind tab bar
                        .background(
                            Theme.background.opacity(0.8)
                                .mask(LinearGradient(colors: [.clear, .black], startPoint: .top, endPoint: .bottom))
                                .frame(height: 100)
                                .offset(y: 40)
                        )
                        .padding(.horizontal, 16)
                        .padding(.bottom, 20)
                }
                .zIndex(1)
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("ArgusNotificationTapped"))) { notification in
            if let id = notification.userInfo?["notificationId"] as? String {
                print("🔔 Argus Deep Link: ID found \(id)")
                self.notificationID = id
            } else {
                print("🔔 Argus Deep Link: No ID, opening Inbox")
                self.notificationID = nil
            }
            // Delay to allow UI to settle if waking from background
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                self.showNotificationsSheet = true
            }
        }
        .sheet(isPresented: $showNotificationsSheet) {
            NotificationsView(viewModel: viewModel, deepLinkID: notificationID)
        }
        .sheet(isPresented: $showVoiceSheet) {
            ArgusVoiceView()
                .environmentObject(viewModel)
        }
    }
}

#Preview {
    ContentView()
}
