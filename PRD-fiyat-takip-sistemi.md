# PC Bileşen Fiyat Takip & Karşılaştırma Sistemi
## Yapay Zekâ İçin Ürün Gereksinim Dokümanı (PRD / Prompt)

> Bu doküman bir yapay zekâ kodlama aracına (Claude, Cursor, v0, Lovable, Bolt vb.) verilerek uygulamanın baştan sona geliştirilmesi için hazırlanmıştır. Aşağıdaki tüm bölümleri girdi olarak ver.

---

## 1. Tek Cümlelik Özet
Kullanıcının farklı bilgisayar konfigürasyonlarını "set" olarak oluşturup, her sete bileşen linkleri ekleyebildiği; tek tuşla tüm setin canlı fiyatlarını internetten çekebildiği; ve her bileşen için daha ucuz muadilleri Akakçe üzerinden karşılaştırabildiği bir web uygulaması.

## 2. Ana Amaç
PC toplayan bir kullanıcının "Intel Seti" ve "AMD Seti" gibi farklı senaryoları yan yana takip etmesini, fiyatları tek tek elle kontrol etmek yerine tek tıkla güncellemesini ve her parça için piyasadaki daha ucuz alternatifi görmesini sağlamak.

---

## 3. Veri Modeli (Temel Kavramlar)

**Set**
- `ad` (örn. "Intel Seti")
- `oluşturmaTarihi`
- `ürünler` → Ürün Kütüphanesi'ne referans listesi
- `toplamFiyat` → otomatik hesaplanır

**Ürün / Bileşen**
- `ad`
- `kategori`
- `kaynakLink` (Akakçe ürün sayfası)
- `güncelFiyat`
- `fiyatGeçmişi` → `[{tarih, fiyat}]` (grafik için)
- `sonGüncelleme` (tarih/saat)

**Kategori** (sabit liste)
- İşlemci (CPU), Anakart, Ekran Kartı (GPU), RAM, SSD/HDD, Güç Kaynağı (PSU), Kasa, Soğutma, Monitör

**Ürün Kütüphanesi**
- Eklenen tüm ürünlerin saklandığı ortak havuz. Setler buradan ürün seçer; aynı ürün birden fazla sette kullanılabilir.

---

## 4. Temel Özellikler (5 + 1)

### 4.1 Set Oluşturma
- Ana sayfada "Yeni Set Oluştur" butonu, set adı girilir.
- Setler kart/liste olarak ana sayfada görünür.
- Set açıldığında içindeki ürünler listelenir, en altta toplam fiyat görünür.

### 4.2 Ürün Ekleme — Kütüphane Mantığı (KRİTİK)
Akış:
1. Set içinde **"Ürün Ekle"** butonuna basılır.
2. Önce **kategori** seçilir (örn. Ekran Kartı).
3. İki yol sunulur:
   - **a) Kayıtlılardan Seç:** O kategoride kütüphanede kayıtlı ürünler listelenir → seçilir → sete eklenir.
   - **b) Yeni Ekle:** Akakçe linki yapıştırılır → sistem ürünün adını ve fiyatını çeker → **kütüphaneye kaydeder** → sete ekler.
4. Dışarıdan eklenen her yeni ürün **otomatik olarak kütüphaneye işlenir**; böylece bir sonraki sette "Kayıtlılardan Seç" altında görünür.

> Yani kullanıcı bir ürünü **bir kez ekler**, sonra tüm setlerde tekrar tekrar seçebilir. (İstenen "dışarıdan eklediğim kayıtlılara eklensin" davranışı budur.)

### 4.3 Tek Tıkla Fiyat Güncelleme
- Her setin üstünde **"Fiyatları Güncelle"** butonu.
- Basıldığında setteki tüm ürünlerin fiyatı **sunucu tarafında** yeniden çekilir.
- Her güncelleme `fiyatGeçmişi`'ne eklenir (grafik için).
- "Yükleniyor" göstergesi + "son güncelleme" zamanı gösterilir.

### 4.4 Temiz Kart Görünümü
- Varsayılan görünümde **sadece ürün adları** listelenir (sade liste).
- Bir ürüne tıklanınca kart açılır (accordion/expand) ve detaylar görünür:
  - Güncel fiyat
  - Fiyat değişim grafiği (zaman / fiyat)
  - "Kaynağa Git" linki
  - **"Karşılaştır"** butonu

### 4.5 Karşılaştırma (Muadil Sunma)
- Ürün kartında **"Karşılaştır"** butonu.
- Basıldığında o ürünün kategorisindeki benzer/muadil ürünler Akakçe'den çekilir.
- Daha ucuz alternatif varsa **vurgulanır** (örn. yeşil etiket: "%12 daha ucuz").
- **Yan yana karşılaştırma:** mevcut ürün vs. alternatif(ler) → ad, fiyat, fiyat farkı.
- Kullanıcı isterse alternatifi sete ekleyebilir veya mevcutla değiştirebilir.

---

## 5. Örnek Kullanıcı Senaryosu (Akış Testi)
1. Kullanıcı siteye girer, **"Intel Seti"** oluşturur.
2. "Ürün Ekle" → "İşlemci" → yeni link yapıştırır (örn. i5-14400F) → eklenir, kütüphaneye kaydedilir.
3. "Ekran Kartı" → kütüphanede RTX 4060 zaten kayıtlı → seçer.
4. **"Fiyatları Güncelle"**ye basar → tüm fiyatlar tazelenir, toplam güncellenir.
5. RTX 4060 kartına tıklar → fiyat grafiğini görür.
6. **"Karşılaştır"**a basar → benzer ekran kartları listelenir → RX 7600 daha ucuz çıkar → yan yana görür.
7. Yeni bir **"AMD Seti"** oluşturur, kütüphaneden aynı ürünleri seçerek hızlıca doldurur.

---

## 6. ⚠️ Teknik Gerçekler ve Kısıtlar (MUTLAKA DİKKATE AL)
Projenin **en zor kısmı canlı fiyat çekme (web scraping)**. Yapay zekâya bunları net belirt:

- **Frontend'de yapılamaz:** Fiyat çekme tarayıcıda CORS engeline takılır. Mutlaka **sunucu tarafında** (backend / API route) yapılmalı.
- **Bot koruması:** Akakçe gibi siteler bot korumalı olabilir (Cloudflare vb.). Basit `fetch` engellenebilir → gerekirse uygun **User-Agent başlıkları** veya **headless tarayıcı** (Playwright / Puppeteer) kullanılmalı.
- **Kırılganlık:** Sitenin HTML yapısı değişirse scraper bozulur → CSS seçicileri (selector) tek yerde, kolay güncellenebilir tutulmalı.
- **Saygılı kazıma:** İstekler makul aralıklarla yapılmalı; kısa sürede çok istek atılmamalı (rate limit).
- **Kullanım şartları:** Toplu veri kazıma sitenin şartlarına aykırı olabilir; bunu **kişisel / küçük ölçekli** kullanım için tasarla.
- **İPUCU:** Akakçe zaten bir fiyat karşılaştırma sitesi olduğundan, tek bir ürün sayfası bile birçok satıcıyı ve benzer ürünleri içerir → "muadil" özelliği için Akakçe'nin kendi "benzer ürünler" / kategori / arama sayfaları kullanılabilir.
- **Yedek plan:** Fiyat çekilemezse **manuel fiyat girişi** veya "kaynağı aç" linki sunulmalı; sistem hatada çökmemeli, kullanıcıya net bir hata göstermeli.

---

## 7. Önerilen Teknoloji (Esnek)
- **Framework:** Next.js (full-stack; API route'lar scraping'i sunucuda yapar) — veya React + ayrı Node.js backend.
- **Scraping:** Cheerio + fetch (hızlı/hafif) veya Playwright (bot korumasına karşı daha güçlü).
- **Veritabanı:** SQLite (basit, tek dosya) veya Supabase/Postgres. Fiyat geçmişi için DB önerilir. (Çok basit MVP'de tarayıcı `localStorage` da olur ama geçmiş grafiği sınırlı kalır.)
- **UI:** Tailwind CSS, kart bazlı düzen.
- **Grafik:** Recharts veya Chart.js.

---

## 8. Arayüz / Tasarım Notları
- Sade, hızlı, **mobil uyumlu**.
- **Ana sayfa:** setlerin kart listesi + "Yeni Set".
- **Set sayfası:** ürün adlarının sade listesi + üstte "Fiyatları Güncelle" + altta toplam fiyat.
- **Ürün kartı kapalı:** sadece ad (+ küçük fiyat). **Açık:** fiyat, grafik, kaynağa git, karşılaştır.
- Yükleniyor ve hata durumları net gösterilsin.

---

## 9. Geliştirme Aşamaları (Öneri)
- **Aşama 1 (MVP):** Set oluştur → ürün ekle (link → ad + fiyat çek) → kütüphaneye kaydet → kayıtlıdan seç → fiyatları güncelle → sade liste + tıkla detay.
- **Aşama 2:** Fiyat geçmişi grafiği + toplam fiyat hesaplama.
- **Aşama 3:** Karşılaştırma / muadil sunma.
- **Aşama 4 (Opsiyonel):** Kullanıcı hesapları / giriş, çoklu kullanıcı.

---

## 10. (Opsiyonel) Giriş / Hesap Notu
"Giriş" özelliği MVP için **zorunlu değil**; tek kullanıcı olarak veriler yerelde/DB'de tutulabilir. Çok kullanıcılı yapı istenirse (Aşama 4) basit e-posta girişi (Supabase Auth / NextAuth) eklenebilir.
