# FİYAT BOTU — TEK DOSYALIK YAPIM TALİMATI

Bu dosya, bir AI kodlama asistanına (Claude Code, Cursor vb.) **tek parça** olarak
verilmek üzere hazırlanmıştır. İçinde (1) yapım talimatı/prompt ve (2) oluşturulacak
tüm config dosyalarının birebir içeriği vardır. AI bu dosyayı okuyup projeyi baştan
sona kurmalıdır.

> Hedef dosya: yerel `data/Masaustu_Bilgisayar_Toplama.xlsx`. 7 setup sayfası var
> (139k, 146k, 162k, 106k, 153k, 142k, last). Bunları tek-doğruluk-kaynağı modeline
> taşıyacağız: linkler tek yerde (Kaynaklar), fiyatlar bot tarafından çekilir,
> setup'lar formülle Katalog'tan okur.

---

## 1) YAPIM TALİMATI (PROMPT)

Python ile profesyonel, modüler ve hata toleranslı (fault-tolerant) bir fiyat
güncelleme botu yaz. Yalnızca ücretsiz/açık kaynak kütüphaneler; hiçbir ücretli
bulut/API yok. Tüm kullanıcıya dönük metinler/loglar Türkçe, kod İngilizce.

**Bağlam ve hedef yapı.** Elimde `Masaustu_Bilgisayar_Toplama.xlsx` var; 7 sayfa,
her biri bir bilgisayar toplama listesi ("setup"). Sütunlar:
`Tür | Çeşit | Ürün | Fiyat | Ay Bazlı Taksit | Alışveriş Sitesi(link)`. Aynı ürünler
birçok sayfada tekrar ediyor. Bunu 3 katmanlı tek-doğruluk-kaynağı modeline taşı:

- **Kaynaklar** sayfası — tüm linklerin yazıldığı TEK yer. Bir ürün × satıcı = bir
  satır. Sütunlar config'teki `sources_columns`. `Fiyat / Son Güncelleme / Durum`
  sütunlarını **bot** doldurur; `Aktif / Kilit` sütunlarını kullanıcı yönetir.
- **Katalog** sayfası — ürün başına çözülmüş **en ucuz** fiyat. Bot, o ürünün
  aktif+başarılı satırları arasından en düşüğünü buraya yazar.
- **Setup sayfaları** — mevcut 7 sayfa. `Ürün`'ü adıyla referans alır, fiyatı
  formülle (aşağıya bak) Katalog'tan çeker. Link/sabit fiyat içermez.
  **Bot bu sayfalara ASLA dokunmaz.**

Tüm yollar/eşikler/eş değerler ekteki `config/config.yaml` ve `config/sites/*.yaml`
dosyalarından okunsun; hiçbir şey hardcoded olmasın. Bu config dosyalarını bu
dokümanın 2. bölümündeki içerikle **birebir** oluştur.

**Setup formülü — uyumluluk (önemli).** Setup sayfalarında fiyatı Katalog'tan çeken
formülün stilini config'e ekle: `setup_formula_style: index_match | xlookup`.
**Varsayılan `index_match`** olsun (her tablo programında ve her sürümde çalışır,
sıfır risk). `xlookup` yalnızca kullanıcının tablo programı destekliyorsa
(güncel LibreOffice 24.8+, Google Sheets, Excel-web) seçilmeli. openpyxl formülü
metin olarak yazar; Excel/Calc dosyayı açınca hesaplar — bu normaldir.

**ADIM 0 — Göç/migration modu (`--migrate`).** Mevcut 7 setup sayfasını oku ve
Kaynaklar + Katalog sayfalarını otomatik üret:
- Tüm (ürün, link, satıcı) üçlülerini topla, **link'e göre tekilleştir** (aynı URL
  bir kez). Satıcı adını domainden türet (amazon.com.tr→Amazon vb.).
- Kategori adlarını kanonikleştir — dosyada tutarsızlar var: `CPU↔İşlemci`,
  `RAM↔Bellek (RAM)`, `SSD↔Depolama (SSD)`, `PSU↔Güç Kaynağı`. Bunun için config'e
  düzenlenebilir bir alias haritası ekle.
- Benzersiz kanonik ürün adlarından Katalog iskeletini kur.
- Setup'lardaki `Fiyat` ve `Alışveriş Sitesi` hücrelerini formülle değiştiren
  opsiyonel bir mod sun (önce kuru-çalıştır/rapor, kullanıcı onaylayınca uygula).
  Yazım hatasını önlemek için setup `Ürün` hücrelerine Katalog listesini kaynak alan
  **data-validation açılır liste** ekle.

**ADIM 1 — Scraping (`--once` ve `--watch`).** Kaynaklar'ı oku; `Aktif=Evet` ve
kilitsiz her satır için URL domainine göre doğru parser'ı seç (factory pattern, hepsi
ortak `BaseParser`'ı uygular). Fiyatı çek → normalize et → satırın
`Fiyat/Son Güncelleme/Durum` hücrelerini güncelle.
- **Fiyat çekme stratejisi config'teki `extraction` listesinden SIRAYLA denenir.**
  Birincil yöntem **JSON-LD** (`application/ld+json` içinden `offers.price`) — CSS
  değişse bile bozulmaz. Sonra CSS, sonra meta tag. İlk geçerli sonuç kazanır.
- Statik siteler `requests`+`BeautifulSoup`/`lxml`; `render:true` olanlar
  `Playwright`. Cloudflare 403'te `cloudscraper` fallback. Config'teki rastgele
  gecikme + per-domain bekleme + robots.txt'e saygı.

**Türkçe fiyat parser'ı (kritik — dosyada gerçek format kaosu var).** Şunların
hepsini doğru `float`'a çevir: `14799.0`, `2.798,80 ₺` (TR: nokta=binlik,
virgül=ondalık), `2,399.00 TL` (US: tersi — aynı üründe iki yazım var!), `53.599`.
Belirsizse kural: son ayraçtan sonra 2 hane varsa o ondalıktır. Para simgesi / `*` /
boşluk temizle.

**Kullanıcının elle koyduğu kararlara saygı (çok önemli).** Bot şu durumlarda fiyatı
ÇEKMEZ/EZMEZ, satırı korur (config `respect_manual`): `Kilit=Evet`; fiyat `*` ile
başlıyorsa; fiyatta parantez içi not varsa (`(Mevcut)`, `(Şuan Alınmayacak)`);
`Aktif=Hayır`.

**ADIM 2 — En ucuz çözücü.** Kaynaklar'ı kanonik ürün adına göre grupla (birebir,
fuzzy değil); her ürün için aktif+başarılı satırların en düşüğünü Katalog'a yaz. Bir
ürünün TÜM satıcıları başarısızsa: Katalog'daki eski fiyatı **silme**, `Durum=STALE`
işaretle ve değeri koru (setup formülleri `#N/A` vermesin).

**Hata toleransı (belkemiği).**
- `openpyxl` ile yükle, **yalnızca config'teki `writable_sheets`'e** yaz. Diğer tüm
  sayfalar, formüller, biçimlendirme, data-validation, named range birebir korunmalı.
- Yazmadan önce zaman damgalı yedek (`data/backups/`). Önce geçici dosyaya yaz, sonra
  atomik rename — yarıda çökerse dosya bozulmasın.
- Checkpoint/resume: işlenmiş satırları SQLite'a kaydet; tekrar çalışınca kaldığı
  yerden devam.
- Per-item izolasyon: tek satırın hatası tüm işi durdurmasın, loglanıp devam etsin.
- `tenacity` ile exponential backoff retry. `loguru` ile seviyeli log (`logs/`).
- Sanity check: yeni fiyat eskinin `max_change_ratio` katından fazla/azsa yazma →
  `flagged.csv`. Çekilemeyenler → `failed.csv`, Katalog'da karşılığı olmayanlar →
  `unmatched.csv`.

**Bonus.** Her başarılı çekimde `ürün–satıcı–fiyat–zaman` kaydını `Fiyat_Gecmisi`
sayfasına (veya SQLite) yaz; ileride fiyat düşüşü uyarısı için temel olsun.

**Teslimat.**
- Katmanlı yapı: `config/`, `src/data/` (excel_handler: yedek+atomik+sayfa-koruyan
  yazma, migration), `src/scraping/` (base_parser, factory, fetcher, jsonld/css/meta
  çıkarıcılar, parsers/), `src/core/` (orchestrator, checkpoint, retry, validation,
  lowest_price), `src/utils/` (logger, rate_limiter, price_parser),
  `data/{backups,checkpoints,reports}/`, `logs/`, `tests/`.
- `requirements.txt`; `main.py` argümanlarla: `--migrate`, `--once`, `--watch`,
  `--dry-run`.
- `README.md`: kurulum + yeni satıcı ekleme (sadece `config/sites/` YAML'ı) + yeni
  setup ekleme adımları.
- `pytest` testleri: (a) Türkçe fiyat parser'ı (yukarıdaki 4 formatın hepsi),
  (b) gruplama + en-ucuz mantığı, (c) **Excel'e yazınca diğer sayfaların/formüllerin
  bozulmadığını doğrulayan test** (zorunlu), (d) manuel-karar-koruma
  (`*`, parantez, Kilit) testi.
- Type hint + docstring.

Önce kısa bir uygulama planı sun, sonra dosya dosya implemente et.

---

## 2) OLUŞTURULACAK CONFIG DOSYALARI (birebir)

Aşağıdaki dosyaları belirtilen yollarda, içeriğiyle birebir oluştur.

### `config/config.yaml`

```yaml
# =====================================================================
#  FİYAT BOTU — ANA AYAR DOSYASI
#  Tek doğruluk kaynağı (single source of truth) modeli
# =====================================================================

# ---------------------------------------------------------------------
# DOSYA YOLLARI
# ---------------------------------------------------------------------
paths:
  workbook: "./data/Masaustu_Bilgisayar_Toplama.xlsx"   # üzerinde çalışılacak ana kitap
  backups_dir: "./data/backups"        # her yazımdan önce zaman damgalı yedek buraya
  reports_dir: "./data/reports"        # flagged.csv, failed.csv, unmatched.csv
  logs_dir: "./logs"
  checkpoint_db: "./data/checkpoints/state.sqlite"      # resume için işlenmiş satır kaydı

# ---------------------------------------------------------------------
# ÇALIŞMA KİTABI YAPISI
#   Kaynaklar  -> tüm linklerin yazıldığı TEK yer (bot fiyatı buraya yazar)
#   Katalog    -> ürün başına çözülmüş en ucuz fiyat (setup'lar buraya bakar)
#   Geçmiş     -> her başarılı çekimin log'u (fiyat takibi için)
#   Setup'lar  -> 139k, 146k... bot bunlara ASLA dokunmaz, sadece formül okur
# ---------------------------------------------------------------------
workbook:
  sources_sheet: "Kaynaklar"
  catalog_sheet: "Katalog"
  history_sheet: "Fiyat_Gecmisi"

  # Bot YALNIZCA bu iki sayfaya yazar. Geri kalan her sayfa (setup'lar)
  # dokunulmadan korunur. Buraya setup sayfa adlarını yazmana gerek yok;
  # "yazma listesi" beyaz liste mantığıyla çalışır: sadece aşağıdakiler yazılır.
  writable_sheets: ["Kaynaklar", "Katalog", "Fiyat_Gecmisi"]

  # Kaynaklar sayfasındaki sütun başlıkları (1. satır başlık kabul edilir).
  # Başlık metnini değiştirirsen burayı da güncelle.
  sources_columns:
    product:     "Ürün"          # kanonik ürün adı (Katalog ile birebir aynı olmalı)
    category:    "Çeşit"         # İşlemci / Ekran Kartı / RAM ... (kanonik)
    seller:      "Satıcı"        # Amazon, Hepsiburada, Tebilon...
    link:        "Link"          # ürün URL'i  -> botun çekeceği adres
    price:       "Fiyat"         # BOT YAZAR
    installment: "Taksit"        # opsiyonel, bot dokunmaz (manuel)
    updated:     "Son Güncelleme" # BOT YAZAR (zaman damgası)
    status:      "Durum"         # BOT YAZAR: OK / STALE / FAILED / FLAGGED
    active:      "Aktif"         # SEN YÖNETİRSİN: Evet/Hayır (Hayır = atla)
    lock:        "Kilit"         # SEN YÖNETİRSİN: Evet = elle girdim, EZME

  catalog_columns:
    product:        "Ürün"
    category:       "Çeşit"
    best_price:     "En Ucuz Fiyat"
    best_seller:    "En Ucuz Satıcı"
    best_link:      "Link"
    updated:        "Son Güncelleme"

# ---------------------------------------------------------------------
# EŞLEŞTİRME / GRUPLAMA
#   Ürünleri gruplamak için kanonik "Ürün" adı kullanılır (fuzzy DEĞİL).
#   Kaynaklar'daki ad, Katalog'daki ad ile BİREBİR aynı olmalı.
#   En sağlamı: Kaynaklar 'Ürün' sütununa Katalog listesinden data-validation
#   açılır liste koymak (yazım hatası = #N/A önlenir).
# ---------------------------------------------------------------------
matching:
  strategy: "exact_product_name"   # exact_product_name | exact_sku
  case_sensitive: false
  trim_whitespace: true

# ---------------------------------------------------------------------
# FİYAT NORMALİZASYONU  (senin dosyandaki gerçek formatlara göre)
#   Parser şunların HEPSİNİ float'a çevirebilmeli:
#     "14799.0"              -> 14799.00
#     "2.798,80 ₺"           -> 2798.80   (TR: nokta=binlik, virgül=ondalık)
#     "2,399.00 TL"          -> 2399.00   (US: virgül=binlik, nokta=ondalık)
#     "53.599"               -> 53599.00
#   Ayraç belirsizse kural: SON ayraçtan sonra 2 hane varsa o ondalıktır.
# ---------------------------------------------------------------------
price_parsing:
  currency_symbols: ["₺", "TL", "TRY", "tl"]
  strip_chars: ["*", "~", " "]      # senin "*17999" gibi işaretlerini temizle
  # Parantez içi notları fiyattan ayıkla ama LOG'la: "(Şuan Alınmayacak)" vb.
  strip_parenthetical_notes: true
  default_currency: "TRY"

# ---------------------------------------------------------------------
# SENİN ELLE KOYDUĞUN KARARLARA SAYGI  (çok önemli)
#   Bot bu durumlarda fiyatı ÇEKMEZ / EZMEZ, satırı olduğu gibi bırakır:
#     - Kilit sütunu = Evet
#     - Fiyat hücresi '*' ile başlıyorsa (senin "kesin değil" işaretin)
#     - Fiyat hücresinde parantez içi not varsa (Mevcut / Şuan Alınmayacak)
#     - Aktif = Hayır
# ---------------------------------------------------------------------
respect_manual:
  skip_if_locked: true
  skip_if_price_starts_with: ["*"]
  skip_if_has_parenthetical: true
  skip_if_inactive: true
  owned_keywords: ["Mevcut", "Var"]            # 0 (Mevcut) = sahip olunan, atla
  hold_keywords: ["Alınmayacak", "Beklemede"]  # şimdilik alınmayacak, atla

# ---------------------------------------------------------------------
# DOĞRULAMA / SANITY CHECK
# ---------------------------------------------------------------------
validation:
  max_change_ratio: 5.0     # yeni fiyat eskinin 5 katından fazla saparsa -> FLAGGED, yazma
  min_change_ratio: 0.2     # ya da 1/5'inden azsa -> FLAGGED (yanlış element ihtimali)
  min_valid_price: 1.0      # 0 / negatif -> geçersiz
  flag_instead_of_write: true

# ---------------------------------------------------------------------
# SCRAPING DAVRANIŞI
# ---------------------------------------------------------------------
scraping:
  request_timeout_sec: 25
  retries: 3                # tenacity ile exponential backoff
  backoff_base_sec: 2
  delay_between_requests_sec: [2, 5]   # siteler arası rastgele bekleme (nazik ol)
  per_domain_delay: true               # aynı siteye art arda vurmamak için
  respect_robots_txt: true

  # JS gerektiren siteler için Playwright kullan. Site config'inde render:true ise.
  render_engine: "playwright"          # playwright | none
  headless: true

  cloudscraper_fallback: true          # Cloudflare 403 alırsa cloudscraper dene

  user_agents:
    - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    - "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

# ---------------------------------------------------------------------
# LOG / RAPOR
# ---------------------------------------------------------------------
logging:
  level: "INFO"             # DEBUG | INFO | WARNING | ERROR
  rotate_mb: 10
  keep_backups: 5

reports:
  write_failed: true        # çekilemeyenler   -> failed.csv
  write_flagged: true       # sanity'e takılan -> flagged.csv
  write_unmatched: true     # Katalog'da karşılığı olmayan -> unmatched.csv
```

### `config/sites/amazon_com_tr.yaml`

```yaml
# Amazon Türkiye  —  dosyandaki en yoğun site (40 link)
# NOT: Amazon agresif anti-bot uygular. render:false ile başla; 403 alırsan
# cloudscraper_fallback devreye girer. JSON-LD bazen eksik olur, o yüzden
# CSS fallback (.a-offscreen) önemli — bu selector Amazon'da global olarak stabildir.
domain: "amazon.com.tr"
seller_name: "Amazon"
currency: "TRY"
render: false

# Fiyat çekme stratejileri SIRAYLA denenir; ilk geçerli sonuç kazanır.
extraction:
  - type: "css"
    selector: "span.a-price span.a-offscreen"   # genelde en güvenilir
  - type: "css"
    selector: "#corePrice_feature_div .a-offscreen"
  - type: "jsonld"
    path: "offers.price"                         # application/ld+json içinden
  - type: "meta"
    selector: 'meta[property="product:price:amount"]'

notes: "Sepete/stok dışı durumlarda fiyat gizlenebilir; FAILED'e düşmesi normaldir."
```

### `config/sites/hepsiburada_com.yaml`

```yaml
# Hepsiburada  (12 link)
# React ağırlıklı sayfa -> render:true ile başlamak güvenli.
# JSON-LD genelde mevcuttur ve CSS değişse bile bozulmaz (birincil yöntem).
domain: "hepsiburada.com"
seller_name: "Hepsiburada"
currency: "TRY"
render: true

extraction:
  - type: "jsonld"
    path: "offers.price"
  - type: "css"
    selector: '[data-test-id="price-current-price"]'   # DOĞRULA: sağ tık > İncele
  - type: "css"
    selector: 'span[data-bind*="price"]'
  - type: "meta"
    selector: 'meta[itemprop="price"]'

notes: "Fiyat boş gelirse önce render:true olduğundan emin ol, sonra CSS'i güncelle."
```

### `config/sites/trendyol_com.yaml`

```yaml
# Trendyol  (6 link)
# Next.js -> fiyat çoğu zaman __NEXT_DATA__ JSON'unda veya JSON-LD'de.
# .prc-dsc (indirimli fiyat) klasik CSS fallback'tir.
domain: "trendyol.com"
seller_name: "Trendyol"
currency: "TRY"
render: true

extraction:
  - type: "jsonld"
    path: "offers.price"
  - type: "css"
    selector: "span.prc-dsc"          # indirimli/sepet fiyatı
  - type: "css"
    selector: "div.product-price-container .prc-dsc"
  - type: "meta"
    selector: 'meta[property="product:price:amount"]'

notes: "Yorumlar/boutique parametreli URL'lerde de ürün fiyatı aynı selector'dan gelir."
```

### `config/sites/n11_com.yaml`

```yaml
# n11  (10 link)
# Genelde sunucu tarafında render edilir -> render:false ile başla.
domain: "n11.com"
seller_name: "n11"
currency: "TRY"
render: false

extraction:
  - type: "jsonld"
    path: "offers.price"
  - type: "css"
    selector: "div.newPrice ins"      # güncel/indirimli fiyat
  - type: "css"
    selector: ".unf-p-summary-price .newPrice"
  - type: "meta"
    selector: 'meta[itemprop="price"]'

notes: "Mağaza (?magaza=) parametresi fiyatı etkileyebilir; URL'i olduğu gibi kullan."
```

### `config/sites/_TEMPLATE.yaml`

```yaml
# =====================================================================
#  YENİ SİTE ŞABLONU  —  kopyala, adını site adı yap (örn. tebilon_com.yaml)
# =====================================================================
# Geriye kalan siteler (tebilon, pttavm, ucuzbudur, mediamarkt, idefix,
# teknobiyotik, wraithesports) bu şablonla 2 dakikada eklenir.
#
# EN SAĞLAM YÖNTEM — önce JSON-LD dene:
#   Sayfada Ctrl+U (kaynağı gör) -> "application/ld+json" ara.
#   İçinde "offers": { "price": "1234.56" } görürsen, JSON-LD yeter, CSS'e gerek yok.
#   Çoğu Türk e-ticaret sitesi (Google Shopping için) bunu içerir.
#
# JSON-LD yoksa CSS'e düş:
#   Fiyata sağ tıkla -> İncele -> elementin class'ını al -> selector yaz.
#
# wraithesports = Shopify. Shopify'da JSON-LD HER ZAMAN vardır; sadece
#   type: jsonld / path: offers.price yazman yeterli olur.

domain: "ornek-site.com"          # www. YAZMA
seller_name: "Örnek Satıcı"
currency: "TRY"
render: false                     # fiyat boş gelirse true yap (JS ile yükleniyordur)

extraction:
  - type: "jsonld"
    path: "offers.price"
  - type: "css"
    selector: ".price"            # DOĞRULA ve değiştir
  - type: "meta"
    selector: 'meta[itemprop="price"]'

notes: ""
```

---

## 3) KALAN SİTELER

Dosyandaki diğer siteler (`tebilon.com`, `pttavm.com`, `ucuzbudur.com`,
`mediamarkt.com.tr`, `idefix.com`, `teknobiyotik.com`, `wraithesports.com`) için
`_TEMPLATE.yaml`'ı kopyala, dosya adını domaine göre koy (örn. `tebilon_com.yaml`).
- Önce JSON-LD dene (sayfada Ctrl+U → "application/ld+json" → `offers.price`). Çoğu
  Türk e-ticaret sitesinde vardır ve en sağlamıdır.
- `wraithesports.com` Shopify'dır; Shopify'da JSON-LD her zaman bulunur, sadece
  `type: jsonld / path: offers.price` satırı bile yeter.
- Fiyat boş gelirse site config'inde `render: true` yap (JS ile yükleniyordur).

## 4) DOSYAYI ÜCRETSİZ DÜZENLEME

Excel ücretli; bu yerel dosyayı düzenlemek için **en güncel LibreOffice Calc** öner
(ücretsiz, masaüstü, botla aynı yerel dosyayı düzenler, XLOOKUP/data-validation
çalışır — eski sürümde XLOOKUP çıkmaz, en yeniyi kur). Kurulumsuz alternatif:
Google Sheets veya Excel web sürümü (yükle/indir gerekir). Bu yüzden setup formülü
varsayılanı `index_match`: her programda ve her sürümde sorunsuz çalışsın diye.
