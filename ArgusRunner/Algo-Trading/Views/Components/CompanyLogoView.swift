import SwiftUI

struct CompanyLogoView: View {
    let symbol: String
    var size: CGFloat = 44
    var cornerRadius: CGFloat = 8
    
    // Fallback logo URL service (Financial Modeling Prep or Parqet)
    // Parqet is usually good for US/EU stocks.
    private var logoUrl: URL? {
        // Financial Modeling Prep has comprehensive symbol-based logic
        URL(string: "https://financialmodelingprep.com/image-stock/\(symbol.uppercased()).png")
    }
    
    var body: some View {
        AsyncImage(url: logoUrl) { phase in
            switch phase {
            case .empty:
                placeholderView
            case .success(let image):
                image
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: size, height: size)
                    .background(Color.white) // Logos often transparent or need white bg
                    .cornerRadius(cornerRadius)
            case .failure:
                // Try Secondary Source or Fallback
                fallbackView
            @unknown default:
                placeholderView
            }
        }
        .frame(width: size, height: size)
    }
    
    var placeholderView: some View {
        ZStack {
            Theme.secondaryBackground
            ProgressView()
        }
        .frame(width: size, height: size)
        .cornerRadius(cornerRadius)
    }
    
    var fallbackView: some View {
        ZStack {
            Theme.tint.opacity(0.1) // Soft tint background
            Text(symbol.prefix(1).uppercased())
                .font(.system(size: size * 0.4, weight: .bold))
                .foregroundColor(Theme.tint)
        }
        .frame(width: size, height: size)
        .cornerRadius(cornerRadius)
    }
}
