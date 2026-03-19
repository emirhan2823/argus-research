# 📱 ARGUS TERMİNAL KULLANICI REHBERİ

## Başlamadan Önce Oku

Bu rehber, **hiç programlama bilmeyenler** için yazılmıştır. Adım adım takip et.

---

# ⚖️ YASAL UYARI VE SORUMLULUK REDDİ

## ÖNEMLİ - MUTLAKA OKUYUN

**Argus Terminal** bir **eğitim ve araştırma aracıdır.**

### Bu Uygulama

- ❌ Yatırım tavsiyesi **DEĞİLDİR**
- ❌ Finansal danışmanlık **DEĞİLDİR**
- ❌ Alım-satım emri **VERMEZ**
- ❌ Kar garantisi **VERMEZ**

### Kullanıcı Olarak Siz

- ✅ Tüm yatırım kararlarınızdan **kendiniz sorumlusunuz**
- ✅ Kayıplarınızdan **kendiniz sorumlusunuz**
- ✅ Uygulamanın sağladığı verilerin doğruluğunu **kendiniz doğrulamalısınız**
- ✅ Profesyonel finansal danışmanlık **almanız önerilir**

### Risk Uyarısı
>
> ⚠️ **Finansal piyasalarda işlem yapmak yüksek risk içerir.** Yatırılan sermayenin tamamını kaybetme riski vardır. Kaybetmeyi göze alamayacağınız parayla işlem yapmayın.

### Bu Uygulamayı Kullanarak

1. Yukarıdaki uyarıları okuduğunuzu
2. Riskleri anladığınızı
3. Tüm sorumluluğu kabul ettiğinizi
4. Geliştiricileri/Yayıncıları sorumlu tutmayacağınızı

**KABUL ETMİŞ OLURSUNUZ.**

---

# 🖥️ ADIM 1: BİLGİSAYARINI HAZIRLA

## Mac Kullanıyorsan

### A) Xcode Kur (Ücretsiz)

1. **App Store** aç
2. Arama kutusuna **"Xcode"** yaz
3. **Xcode** uygulamasını bul (mavi çekiç ikonu)
4. **"Al"** veya **"İndir"** butonuna tıkla
5. **~12 GB** indirme - sabırla bekle
6. İndirme bitince **"Aç"** tıkla
7. Ek bileşenleri kurmasını bekle (5-10 dk)

### B) Xcode Hazır mı Kontrol Et

1. Xcode açıldıktan sonra
2. Üst menüden: **Xcode → Settings → Locations**
3. **Command Line Tools** kısmında Xcode seçili olmalı

✅ **Mac hazır!**

---

## Windows Kullanıyorsan

### ⚠️ Önemli Bilgi

iOS uygulaması geliştirmek için **Mac gereklidir.** Windows'ta doğrudan Xcode çalışmaz.

### Seçeneklerin

**Seçenek 1: Sanal Mac (Zor)**

- VMware veya VirtualBox ile macOS kurulumu
- Teknik bilgi gerektirir
- Apple lisans kurallarına dikkat

**Seçenek 2: Mac Mini Satın Al**

- En ucuz Mac seçeneği (~$599)
- Uzun vadeli çözüm

**Seçenek 3: Cloud Mac Kirala**

- MacStadium, MacinCloud gibi servisler
- Aylık ücretli ($30-50/ay)
- Hemen başlayabilirsin

**Seçenek 4: SwiftUI Web (Flutter/React Native)**

- Windows'ta çapraz platform geliştirme
- Bu promptlar iOS/Swift için, dönüştürme gerekir

### Windows için Öneri

En kolay yol **Mac Mini** veya **Cloud Mac** kiralaması.

---

# 📁 ADIM 2: PROJEYİ OLUŞTUR

## Xcode'da Yeni Proje

1. **Xcode** aç
2. **"Create a new Xcode project"** tıkla
3. **"iOS"** sekmesinde **"App"** seç → **"Next"**
4. Ayarları gir:
   - **Product Name:** `Argus-Terminal`
   - **Team:** Kendi Apple ID'n (yoksa "Add Account" ile ekle)
   - **Organization Identifier:** `com.benimadim`
   - **Interface:** `SwiftUI` ✅
   - **Language:** `Swift` ✅
5. **"Next"** → Klasör seç → **"Create"**

✅ **Boş proje hazır!**

---

# 🔑 ADIM 3: API ANAHTARLARI AL

## FRED API (Zorunlu - Ücretsiz)

1. Tarayıcıda aç: **<https://fred.stlouisfed.org>**
2. Sağ üstten **"My Account"** tıkla
3. **"Create Account"** ile kayıt ol
4. E-posta doğrula
5. Giriş yap
6. **"API Keys"** sayfasına git
7. **"Request API Key"** tıkla
8. Formu doldur (ne için kullanacağın: "Personal research")
9. API key'i **kopyala ve bir yere kaydet**

## FMP API (Zorunlu - Ücretsiz)

1. Aç: **<https://site.financialmodelingprep.com>**
2. **"Get Free API Key"** tıkla
3. E-posta ile kayıt ol
4. Dashboard'dan API key'i **kopyala**

## Groq API (Opsiyonel - Ücretsiz)

1. Aç: **<https://console.groq.com>**
2. Google/GitHub ile giriş yap
3. **"API Keys"** → **"Create API Key"**
4. Kopyala

---

# 📝 ADIM 4: PROMPTLARI KULLAN

## İlk Dosyalar

1. Xcode'da sol panelde **sağ tıkla** → **"New File"**
2. **"Swift File"** seç → **"Next"**
3. İsim: `Secrets` → **"Create"**

## Secrets.swift İçeriği

Bu kodu yapıştır (API key'lerini değiştir):

```swift
import Foundation

struct Secrets {
    // Buraya kendi key'lerini yaz:
    static let fredAPIKey = "SENIN_FRED_KEY"
    static let fmpAPIKey = "SENIN_FMP_KEY"
    static let groqAPIKey = "SENIN_GROQ_KEY"  // Yoksa boş bırak ""
}
```

## Diğer Dosyalar

Her prompt dosyasını sırayla aç:

1. Prompt içindeki Swift kodunu kopyala
2. Xcode'da yeni dosya oluştur
3. Kodu yapıştır
4. Kaydet (Cmd+S)
5. Build et (Cmd+B)
6. Hata varsa düzelt
7. Sonraki prompta geç

---

# ▶️ ADIM 5: ÇALIŞTIR

1. Sol üstten **iPhone Simulator** seç (iPhone 15 Pro)
2. **"▶"** (Play) butonuna tıkla veya **Cmd+R**
3. Simulator açılacak
4. Uygulama yüklenecek
5. **Yasal uyarı ekranı** çıkacak
6. **"Kabul Ediyorum"** tıkla
7. Watchlist ekranı açılacak

---

# 🔄 GÜNCELLEME YAPACAKLAR İÇİN

Eğer daha önce eski promptlarla projeyi kurmuşsan:

1. `GUNCELLEME_REHBERI.md` dosyasını oku
2. Hangi dosyaların değiştiğini kontrol et
3. Sadece değişen dosyaları güncelle
4. Build et ve test et

---

# ❓ SIKÇA SORULAN SORULAR

**S: Xcode ücretsiz mi?**
C: Evet, App Store'dan ücretsiz.

**S: iPhone'um olmadan test edebilir miyim?**
C: Evet, Simulator ile test edersin.

**S: API key'ler ücretli mi?**
C: Hayır, hepsi ücretsiz plan sunuyor.

**S: Windows'ta yapabilir miyim?**
C: Doğrudan hayır. Mac veya Cloud Mac gerekli.

**S: Hata alıyorum, ne yapmalıyım?**
C: `12_HATA_AYIKLAMA.md` dosyasını oku.

**S: Bu uygulama ile para kazanabilir miyim?**
C: Bu bir eğitim aracıdır. Yatırım tavsiyesi değildir. Tüm risk size aittir.

---

# 📞 DESTEK

Sorun yaşarsan:

1. Önce `12_HATA_AYIKLAMA.md` kontrol et
2. Google'da hata mesajını ara
3. ChatGPT/Claude'a hata mesajını yapıştır

---

**İyi kodlamalar! 🚀**

*Bu rehber eğitim amaçlıdır. Finansal tavsiye içermez.*
