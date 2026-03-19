import SwiftUI

struct ArgusFloatingTabBar: View {
    @Binding var selectedTab: Int
    @Binding var showVoiceSheet: Bool
    @Namespace private var animationNamespace
    
    private let tabs = [
        "chart.bar.xaxis",
        "eye.trianglebadge.exclamationmark.fill",
        "cube.transparent",
        "briefcase.fill",
        "gearshape.fill"
    ]
    
    var body: some View {
        HStack(spacing: 0) {
            ForEach(0..<tabs.count, id: \.self) { index in
                Spacer()
                
                Button(action: {
                    // Index 2 is Voice
                    if index == 2 {
                        showVoiceSheet = true
                    } else {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                            selectedTab = index
                        }
                    }
                }) {
                    VStack(spacing: 6) {
                        Image(systemName: tabs[index])
                            .font(.system(size: 22, weight: (selectedTab == index || (index == 2 && showVoiceSheet)) ? .semibold : .regular))
                            .foregroundColor(
                                index == 2 ? Theme.primary : (selectedTab == index ? Theme.accent : Theme.textSecondary.opacity(0.5))
                            )
                            .scaleEffect(
                                index == 2 ? 1.3 : (selectedTab == index ? 1.15 : 1.0)
                            )
                            .shadow(
                                color: index == 2 ? Theme.primary.opacity(0.6) : (selectedTab == index ? Theme.accent.opacity(0.6) : .clear),
                                radius: index == 2 ? 12 : 8
                            )
                        
                        if selectedTab == index && index != 2 {
                            Circle()
                                .fill(Theme.accent)
                                .frame(width: 4, height: 4)
                                .shadow(color: Theme.accent, radius: 5)
                                .matchedGeometryEffect(id: "tab_dot", in: animationNamespace)
                        } else if index != 2 {
                            Circle().fill(.clear).frame(width: 4, height: 4)
                        }
                    }
                }
                .buttonStyle(PlainButtonStyle())
                
                Spacer()
            }
        }
        .padding(.vertical, 16)
        .padding(.horizontal, 4)
        .background(
            GlassCard(cornerRadius: 32) {
                Color.clear
            }
        )
        .padding(.horizontal, 16)
        .padding(.bottom, 8)
    }
}
