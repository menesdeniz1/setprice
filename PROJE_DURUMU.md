# SetPrice — Proje Durumu ve Vizyon

> Bu doküman, projenin şu anki halini, ne işe yaradığını, hangi özelliklere
> sahip olduğunu ve nereye doğru evrildiğini anlatır. Yeni bir AI oturumuna
> bağlam vermek, bir geliştiriciyi onboard etmek ya da projeyi kendinize
> hatırlatmak için "prompt" olarak kullanılabilir.
>
> Son güncelleme: 2026-07-01

---

## 1) Tek Cümlelik Özet

SetPrice, kullanıcının satın almak istediği ürünleri **"Set"** adı verilen
temalı koleksiyonlar halinde organize edip, farklı mağazalardaki fiyatlarını
otomatik takip eden, fiyat geçmişi tutan, muadil/alternatif ürün önerileri
sunan ve **"şu an alsam mantıklı mı?"** sorusuna otomatik cevap veren
(BUY/WAIT/AVOID sinyali) bir akıllı alışveriş asistanı web uygulamasıdır.

## 2) Nereden Geldi, Nereye Gidiyor

**Başlangıç noktası:** Kullanıcının kendi masaüstü bilgisayar toplama
listesini (Excel'de tutulan, 7 farklı "setup" senaryosu) elle takip etmekten
kurtulmak için yazılan bir fiyat botu. Excel'deki linkleri okuyup fiyatları
otomatik çeken, tek-doğruluk-kaynağı modeliyle çalışan bir CLI aracı olarak
başladı (bkz. `FIYAT_BOTU_MASTER.md` — artık aktif geliştirilmiyor, referans
amaçlı duruyor).

**Sonra web uygulamasına evrildi:** Excel yerine veritabanı, CLI yerine React
arayüzü — "Set oluştur → ürün ekle (link yapıştır) → kütüphaneye otomatik
kaydedilsin → tek tıkla fiyatları güncelle" akışı (bkz. `PRD-fiyat-takip-sistemi.md`
— ilk web-app vizyonu, PC parçalarına özeldi).

**Şu anki hedef — genel akıllı alışveriş asistanı:** Kullanıcı, projeyi artık
sadece PC parçalarıyla sınırlı değil, **herhangi bir ürün kategorisi için**
kullanılabilir hale getirmek istiyor: kıyafet kombini, ev eşyası, hediye
listesi — "Set" kavramı korunuyor (isim olarak da beğenildi — hem "kurulum
seti" hem "fiyatı sabitliyoruz/yakalıyoruz" anlamı taşıyor), ama artık
**şablonlu ve serbest kategorili**: PC Setup şablonu (İşlemci/Anakart/RAM/...)
hâlâ var, ama kullanıcı "Kombin" gibi kendi şablonunu da seçebiliyor ya da
sıfırdan boş bir set açıp kategorilerini kendi belirleyebiliyor.

Fiyat takibinin ötesine geçilmesi isteniyor: sadece "fiyat şu" değil,
**"bu paraya değer mi, beklesem mi, kaçınsam mı"** sorusuna cevap veren bir
karar katmanı (Decision Engine), fiyat/performans analizi (özellikle
teknoloji ürünlerinde CPU/GPU benchmark bazlı), ve muadil/alternatif ürün
önerileri hedefleniyor.

## 3) Mimari — İki Katman

- **Legacy CLI bot** (`main.py`, `src/orchestrator.py`, `src/excel_handler.py`) —
  artık aktif geliştirilmiyor, Excel tabanlı orijinal araç. Scraping altyapısı
  (`src/scraper.py`, `src/akakce.py`, `src/price_parser.py`) hâlâ web app
  tarafından paylaşılıyor.
- **Web uygulaması** (aktif geliştirilen) — FastAPI + SQLAlchemy + SQLite
  backend (`src/web_backend/`), React 19 + Vite frontend (`frontend/`).
  Modern, sağlam bir stack; sıfırdan yazmak yerine bunun üzerine inşa etme
  kararı verildi (gerekçe: hard-won scraping mantığı, temiz veri modeli,
  bulunan sorunlar mimari kusur değil "yarım kalmış bağlantı" niteliğindeydi).

## 4) Veri Modeli (Özet)

- `User` → `ProductSet` ("Set") → `Product` (sete özel kilit/aktiflik) →
  `LibraryProduct` (paylaşılan ürün varlığı — fiyat, kategori, karar sinyali
  burada yaşar; bir ürün birden fazla sette kullanılabilir)
- `SetCategory` — set'e özel, kullanıcının düzenleyebildiği kategori/slot listesi
- `PriceHistory` — her fiyat değişiminin kaydı (grafik için)
- `Alternative` — muadil/aynı-ürün-farklı-mağaza sonuçları (`match_type` ile ayrılır)
- `Alert` — eşik/sinyal-değişimi/bull-trap/dip-bölge bildirimleri
- `BenchmarkEntry` — CPU/GPU performans referans skorları
- `DomainHealth` — hangi mağaza sitesinin scraping'i ne sıklıkla başarılı/başarısız

## 5) Güncel Özellikler

**Kimlik & Kullanıcı**
- E-posta/şifre ile kayıt-giriş (JWT), tek kullanıcı başına izole veri

**Set (Koleksiyon) Yönetimi**
- Şablonlu set oluşturma: Masaüstü Setup / Kombin-Kıyafet / Boş-Özel
- Set'e özel kategori listesi — ekle/yeniden adlandır/sil, şablondan bağımsız düzenlenebilir
- Hedef bütçe takibi + bütçe aşım uyarısı
- Kategoriye göre ya da karar-sinyaline göre gruplanmış ürün listesi

**Ürün Kütüphanesi**
- Bir ürün bir kez link ile eklenir, otomatik ada/fiyata/kategoriye çözülür,
  kütüphaneye kaydedilir; sonrasında istenilen tüm setlerde tekrar seçilebilir
- Kategori otomatik tahmini (önce setin kendi kategorileriyle, sonra genel
  elektronik anahtar-kelime sözlüğüyle) — kullanıcı her zaman elle geçersiz kılabilir

**Fiyat Takibi**
- Hibrit scraping: JSON-LD → CSS → meta sırayla denenir; requests →
  cloudscraper → Playwright fallback zinciri (anti-bot aşımı)
- Türkçe/Amerikan karma fiyat formatlarını doğru ayrıştıran parser
- Tek tıkla set taraması + 10 dakikada bir otomatik arka plan taraması
  (opsiyonel olarak Celery/Redis'e devredilebilir)
- Fiyat geçmişi grafiği

**Karar Motoru (Decision Engine)**
- Her ürün için: trend analizi, tarihsel dip-bölge tespiti, bull-trap
  (sahte indirim) dedektörü, value score (fiyat/benchmark), satisfaction
  score (rating/yorum), performance score (CPU/GPU için, PassMark bazlı)
- Nihai sinyal: BUY / WAIT / AVOID + gerekçe metni
- Dashboard'da "Alınması Gerekenler" / "Uzak Durulması Gerekenler" panelleri,
  set bazında "Portföy Sağlığı" skoru

**Karşılaştırma**
- İki mod: **Muadil Ürünler** (spec bazlı farklı ama karşılaştırılabilir ürün)
  ve **Başka Mağazada** (başlık benzerliğiyle "muhtemelen aynı ürün", farklı
  satıcı) — Akakçe arama sonuçları başlık benzerliğine göre otomatik sınıflandırılır
- İki sıralama: Fiyata Göre / Akıllı Sıralama (fiyat avantajı + eşleşme güveni)

**Bildirimler**
- Uygulama içi bildirim merkezi (eşik/sinyal-değişimi/bull-trap/dip alertleri)
- Telegram bot entegrasyonu (kullanıcı kendi chat ID'sini bağlar, sunucuda
  bot token'ı ayarlanınca aktif olur)

**Gözlemlenebilirlik**
- Scraper sağlığı endpoint'i — hangi mağaza sitesi ne sıklıkla başarısız oluyor

## 6) Şu Anki Sınırlamalar (Bilinçli Kapsam Kararları)

- **Benchmark verisi canlı değil** — PassMark'tan gerçek zamanlı senkron yok,
  ~37 popüler CPU/GPU'luk elle küratörlüğü yapılmış bir başlangıç veri seti
  var. Popüler olmayan/yeni parçalar için performans skoru şu an çıkmıyor.
- **GTIN/model no bazlı kesin ürün eşleştirme yok** — "aynı ürün" tespiti
  başlık benzerliğine dayanıyor, %100 kesin değil (güven skoru gösteriliyor).
- **E-posta bildirimi yok** — sadece Telegram (bilinçli tercih, e-posta
  altyapı olarak eklenmeye hazır ama bağlanmadı).
- **Scraper sağlığı için ayrı bir görsel panel yok** — veri API üzerinden
  erişilebilir, henüz frontend'de gösterilmiyor.

## 7) Ne İstiyorum / Bir Sonraki Adımlar İçin Prensip

- Proje PC parçalarına özel bir araçtan **genel bir akıllı alışveriş
  asistanına** evrilmeye devam etsin — "Set" kavramı ve şablon+serbest
  kategori sistemi bu evrimi destekleyecek şekilde tasarlandı.
- Her yeni özellik eklenirken **"var olanı olduğu gibi genişletmek" ile
  "daha profesyonel/doğru yolu bulmak"** arasında bilinçli bir tercih
  yapılmalı — kör kör mevcut deseni tekrarlamak yerine, gerekirse küçük
  mimari düzeltmelerle ilerlenmeli (ör. kategori sisteminin DB'ye taşınması,
  Akaçe eşleştirmesinin iki moda ayrılması gibi kararlar bu prensiple alındı).
- Doğrulanamayan/canlı test edilemeyen dış entegrasyonlar (ör. bir sitenin
  HTML yapısı) için **sahte/kırılgan kod yazmaktansa kapsamı dürüstçe
  daraltıp bunu açıkça belirtmek** tercih ediliyor — bu oturumda birkaç kez
  bu tercih yapıldı ve gerekçesi roadmap'te işaretlendi.

## 8) İlgili Dosyalar

- [`ROADMAP.md`](ROADMAP.md) — uygulanan mimari yol haritası, faz faz
  detaylar, bulunup düzeltilen buglar
- [`PRD-fiyat-takip-sistemi.md`](PRD-fiyat-takip-sistemi.md) — ilk web-app
  vizyonu (PC'ye özel, artık kısmen güncel değil ama tarihsel bağlam için değerli)
- [`FIYAT_BOTU_MASTER.md`](FIYAT_BOTU_MASTER.md) — orijinal CLI/Excel bot
  talimatı (artık aktif geliştirilmiyor)
