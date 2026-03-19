# PROMPT 13: YASAL UYARI EKRANI

## Açıklama

Uygulama ilk açılışında görünen yasal uyarı ekranı. Kullanıcı kabul etmeden uygulama açılmaz.

---

## PROMPT

```
Argus Terminal için yasal uyarı (disclaimer) ekranı oluştur. Kullanıcı kabul etmeden ana uygulama açılmamalı.

## DisclaimerView.swift

```swift
import SwiftUI

struct DisclaimerView: View {
    @Binding var hasAccepted: Bool
    @State private var hasScrolledToBottom = false
    @State private var checkboxChecked = false
    
    var body: some View {
        ZStack {
            // Background
            LinearGradient(
                colors: [Color.black, Color(red: 0.1, green: 0.05, blue: 0.15)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header
                headerSection
                
                // Scrollable Content
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 20) {
                            disclaimerContent
                            
                            // Bottom marker for scroll detection
                            Color.clear
                                .frame(height: 1)
                                .id("bottom")
                                .onAppear {
                                    hasScrolledToBottom = true
                                }
                        }
                        .padding()
                    }
                }
                
                // Footer with acceptance
                footerSection
            }
        }
    }
    
    // MARK: - Header
    
    private var headerSection: some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.shield.fill")
                .font(.system(size: 50))
                .foregroundColor(.orange)
            
            Text("YASAL UYARI")
                .font(.title)
                .bold()
                .foregroundColor(.white)
            
            Text("Devam etmeden önce lütfen okuyun")
                .font(.subheadline)
                .foregroundColor(.gray)
        }
        .padding(.vertical, 30)
    }
    
    // MARK: - Content
    
    private var disclaimerContent: some View {
        VStack(alignment: .leading, spacing: 24) {
            // Section 1: What this app is NOT
            DisclaimerSection(
                icon: "xmark.circle.fill",
                iconColor: .red,
                title: "Bu Uygulama NEDİR DEĞİL",
                items: [
                    "Yatırım tavsiyesi değildir",
                    "Finansal danışmanlık hizmeti değildir",
                    "Alım-satım emri vermez",
                    "Kar garantisi vermez",
                    "Lisanslı bir finansal kuruluş değildir"
                ]
            )
            
            // Section 2: What this app IS
            DisclaimerSection(
                icon: "info.circle.fill",
                iconColor: .blue,
                title: "Bu Uygulama NEDİR",
                items: [
                    "Eğitim ve araştırma aracıdır",
                    "Teknik ve temel analiz gösterir",
                    "Piyasa verilerini görselleştirir",
                    "Karar destek sistemidir (karar vermez)",
                    "Açık kaynak yazılımdır"
                ]
            )
            
            // Section 3: Risk Warning
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.yellow)
                    Text("RİSK UYARISI")
                        .font(.headline)
                        .foregroundColor(.yellow)
                }
                
                Text("""
                Finansal piyasalarda işlem yapmak yüksek risk içerir. \
                Yatırılan sermayenin tamamını kaybetme riski vardır. \
                Geçmiş performans gelecekteki sonuçların garantisi değildir. \
                Kaldıraçlı işlemler kayıpları artırabilir.
                """)
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.9))
                .padding()
                .background(Color.yellow.opacity(0.15))
                .cornerRadius(12)
            }
            
            // Section 4: User Responsibilities
            DisclaimerSection(
                icon: "person.fill.checkmark",
                iconColor: .green,
                title: "Kullanıcı Sorumlulukları",
                items: [
                    "Tüm yatırım kararlarınızdan kendiniz sorumlusunuz",
                    "Kayıplarınızdan kendiniz sorumlusunuz",
                    "Verilerin doğruluğunu kendiniz doğrulamalısınız",
                    "Profesyonel danışmanlık almanız önerilir",
                    "Kaybetmeyi göze alamayacağınız parayla işlem yapmayın"
                ]
            )
            
            // Section 5: Data Disclaimer
            DisclaimerSection(
                icon: "server.rack",
                iconColor: .cyan,
                title: "Veri Sorumluluğu",
                items: [
                    "Veriler üçüncü parti kaynaklardan alınmaktadır",
                    "Verilerin doğruluğu garanti edilmez",
                    "Veriler gecikmeli olabilir",
                    "Sistem hataları oluşabilir",
                    "Kesintiler yaşanabilir"
                ]
            )
            
            // Section 6: Legal
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: "doc.text.fill")
                        .foregroundColor(.purple)
                    Text("YASAL SORUMLULUK REDDİ")
                        .font(.headline)
                        .foregroundColor(.purple)
                }
                
                Text("""
                Bu uygulamanın geliştiricileri, yayıncıları ve katkıda bulunanlar, \
                uygulamanın kullanımından kaynaklanan doğrudan veya dolaylı \
                hiçbir zarar, kayıp veya maliyet için sorumlu tutulamaz. \
                Uygulama "olduğu gibi" sunulmaktadır, herhangi bir garanti \
                verilmemektedir.
                """)
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
                .padding()
                .background(Color.purple.opacity(0.15))
                .cornerRadius(12)
            }
        }
    }
    
    // MARK: - Footer
    
    private var footerSection: some View {
        VStack(spacing: 16) {
            Divider()
                .background(Color.gray)
            
            // Checkbox
            Button(action: { checkboxChecked.toggle() }) {
                HStack(spacing: 12) {
                    Image(systemName: checkboxChecked ? "checkmark.square.fill" : "square")
                        .font(.title2)
                        .foregroundColor(checkboxChecked ? .green : .gray)
                    
                    Text("Yukarıdaki uyarıları okudum, anladım ve tüm riskleri kabul ediyorum.")
                        .font(.caption)
                        .foregroundColor(.white)
                        .multilineTextAlignment(.leading)
                }
            }
            .padding(.horizontal)
            
            // Accept Button
            Button(action: acceptDisclaimer) {
                HStack {
                    Image(systemName: "shield.checkered")
                    Text("KABUL EDİYORUM VE DEVAM ET")
                        .bold()
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(canAccept ? Color.green : Color.gray)
                .foregroundColor(.white)
                .cornerRadius(12)
            }
            .disabled(!canAccept)
            .padding(.horizontal)
            
            // Decline Button
            Button(action: declineDisclaimer) {
                Text("Kabul Etmiyorum")
                    .font(.caption)
                    .foregroundColor(.gray)
            }
            .padding(.bottom, 20)
        }
        .padding(.top, 10)
        .background(Color.black.opacity(0.8))
    }
    
    // MARK: - Logic
    
    private var canAccept: Bool {
        hasScrolledToBottom && checkboxChecked
    }
    
    private func acceptDisclaimer() {
        // Save acceptance
        UserDefaults.standard.set(true, forKey: "disclaimer_accepted")
        UserDefaults.standard.set(Date(), forKey: "disclaimer_accepted_date")
        
        withAnimation {
            hasAccepted = true
        }
    }
    
    private func declineDisclaimer() {
        // Exit app (optional - or show message)
        exit(0)
    }
}

// MARK: - Disclaimer Section Component

struct DisclaimerSection: View {
    let icon: String
    let iconColor: Color
    let title: String
    let items: [String]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(iconColor)
                Text(title)
                    .font(.headline)
                    .foregroundColor(iconColor)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                ForEach(items, id: \.self) { item in
                    HStack(alignment: .top, spacing: 8) {
                        Text("•")
                            .foregroundColor(iconColor.opacity(0.7))
                        Text(item)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.9))
                    }
                }
            }
            .padding(.leading, 4)
        }
    }
}

// MARK: - Preview

#Preview {
    DisclaimerView(hasAccepted: .constant(false))
}
```

## App Entry Point Güncelleme

Ana uygulama dosyasını (örn: `Argus_TerminalApp.swift`) güncelle:

```swift
import SwiftUI

@main
struct ArgusTerminalApp: App {
    @State private var hasAcceptedDisclaimer = UserDefaults.standard.bool(forKey: "disclaimer_accepted")
    
    var body: some Scene {
        WindowGroup {
            if hasAcceptedDisclaimer {
                // Ana uygulama
                WatchlistView()
                    .preferredColorScheme(.dark)
            } else {
                // Yasal uyarı ekranı
                DisclaimerView(hasAccepted: $hasAcceptedDisclaimer)
                    .preferredColorScheme(.dark)
            }
        }
    }
}
```

## Özellikler

1. **Scroll Kontrolü:** Kullanıcı en alta kaydırmadan kabul butonu aktif olmaz
2. **Checkbox:** Kullanıcı açıkça onay vermeli
3. **Kalıcı Kayıt:** UserDefaults'a kabul tarihi kaydedilir
4. **Decline Seçeneği:** Kabul etmezse uygulama kapanır

## Test

1. Uygulamayı ilk kez aç
2. Yasal uyarı ekranı görünmeli
3. En alta kaydır
4. Checkbox'ı işaretle
5. "Kabul Ediyorum" butonu yeşile dönmeli
6. Tıklayınca ana ekran açılmalı
7. Uygulamayı kapat ve tekrar aç - direkt ana ekran açılmalı

## Sıfırlama (Test için)

```swift
// Ayarlarda veya debug menüsünde:
func resetDisclaimer() {
    UserDefaults.standard.removeObject(forKey: "disclaimer_accepted")
    UserDefaults.standard.removeObject(forKey: "disclaimer_accepted_date")
}
```
