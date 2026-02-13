# ARGUS v2.5: Environment Rebuild Instructions (Python 3.12)

**Role:** Principal Quant Developer & Environment Architect
**Objective:** Resolve dependency conflicts (pandas-ta) and optimize for Python 3.12.

---

## 1. Environment Re-construction

### What
Mevcut Python 3.11 sanal ortamını (virtual environment) silip, performans ve kütüphane uyumluluğu için Python 3.12 tabanlı temiz bir ortam kuracağız.

### Why
`pandas-ta` gibi bazı kütüphaneler, eski `numpy` sürümleriyle çakışabilir veya Python 3.12 ile gelen performans iyileştirmelerinden (daha hızlı yorumlayıcı) yararlanmak isteyebiliriz. Temiz kurulum, "Dependency Hell" riskini ortadan kaldırır.

### How (Manual Instructions)

**Windows:**
```powershell
rmdir /s /q .venv
py -3.12 -m venv .venv
```

**Linux/Mac:**
```bash
rm -rf .venv
python3.12 -m venv .venv
```

---

## 2. Dependency Management

### What
`requirements.txt` dosyasını güncelleyerek `pandas-ta`'nın geliştirme sürümünü (GitHub master) kullanacağız, çünkü PyPI sürümü bazen `numpy 2.0` ile uyumsuzdur. Ayrıca `numexpr` ekleyerek `pandas` hızını artıracağız.

### Why
*   **pandas-ta:** PyPI sürümü eski olabilir. Kaynaktan kurulum en güncel fix'leri içerir.
*   **numexpr:** Pandas işlemlerini çok çekirdekli işlemcilerde (i7-11800H) hızlandırır.

---

## 3. Multi-Asset Optimization Check (Python 3.12)

### What
Python 3.12, `multiprocessing` başlatma yöntemi olarak `spawn` kullanmaya daha meyillidir (özellikle Windows'ta varsayılandır). Bu yöntem, `fork` yöntemine göre daha güvenlidir ancak taşınacak nesnelerin (pickle) serileştirilebilir olmasını zorunlu kılar.

### Why
`DarwinEngine` içindeki `evaluate_population` fonksiyonu, iç içe (nested) fonksiyonları process havuzuna gönderirse `PicklingError` hatası alırız.

### How
Kodumuzda `evaluate_population` fonksiyonuna gönderilen işlevin (`backtest_func`) en üst seviyede (top-level) tanımlanmış olması veya bir sınıfın statik metodu olması gerekir.

---

## 4. Generation 0 Trigger

Aşağıdaki scriptler, ortamı hazırlar ve Gen0 evrimini başlatır.
