import Foundation
import UIKit



class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationDelegate()
    
    // Uygulama ön plandayken bildirim gelirse
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        // Ön planda da göster (banner, ses)
        completionHandler([.banner, .sound, .badge])
    }
    
    // Bildirime tıklandığında
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        let userInfo = response.notification.request.content.userInfo
        print("🔔 Bildirime tıklandı: \(userInfo)")
        
        // Deep Link Event'i yayınla (ContentView yakalayacak)
        NotificationCenter.default.post(name: NSNotification.Name("ArgusNotificationTapped"), object: nil, userInfo: userInfo)
        
        completionHandler()
    }
}
