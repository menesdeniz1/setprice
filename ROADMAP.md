# SetPrice — Mimari Yol Haritası

> Bu doküman, PC toplama fiyat takipçisinden genel "akıllı alışveriş asistanı"na evrilme
> planını tutar. Sırayla uygulanır; her faz bir öncekinin üzerine oturur (Faz 0 hariç
> hepsi büyük ölçüde bağımsızdır, sıra değişebilir).
>
> Not: Bazı maddelerde "daha profesyonel yol" tercih edildi — sebebi her madde altında
> **Neden** satırında açıklanıyor. "⏸ Karar gerekiyor" işaretli maddeler kullanıcı
> girdisi (API sağlayıcı seçimi, ücretli servis vb.) gerektirir, o noktaya gelince
> sorulacak.

---

## Faz 0 — Sağlamlaştırma ✅ Tamamlandı

Var olan özelliklerin gerçekten çalışır hale gelmesi. Sonraki her faz buna dayanır.

- [x] **Decision Engine'i tarama akışına bağla** — `crud.update_decision_signals()`
      artık `run_set_scan` ve `run_library_scan` içinde, alternatifler senkronize
      edildikten sonra çağrılıyor. Bu sırada ek bir bug daha bulundu ve düzeltildi:
      `run_set_scan` hiç import edilmemiş `schemas` modülünü kullanıyordu — Akakçe
      sonucu senkronize edilecek her "Fiyatları Güncelle" çağrısında `NameError`
      ile sessizce patlıyordu.
- [x] **Kırık testi düzelt** — `test_decision_engine.py::test_generate_signal`
      artık motorun 4 değerli dönüşünü doğru unpack ediyor.
- [x] **CSS custom property tutarlılığı** — 8 dosyada 65 yanlış isimlendirilmiş
      değişken `--color-*` şemasına taşındı. Ayrıca hiç import edilmeyen, Vite
      şablonundan kalma ölü `App.css` dosyası silindi.
- [x] **JWT secret sertleştirme** — Hardcoded fallback kaldırıldı; `JWT_SECRET`
      yoksa process başına `secrets.token_hex(32)` üretilip loga uyarı basılıyor.
- [x] **CORS daraltma** — `CORS_ORIGINS` env değişkeninden okunuyor, varsayılan
      `http://localhost:3000`.
- [x] Pydantic v2 `class Config` → `model_config = ConfigDict(...)`; ayrıca
      `schemas.py` içindeki tekrarlanan/gereksiz mid-file import satırı temizlendi.

Doğrulama: `pytest` 17/17 yeşil, `npm run build` başarılı, `python -c "from
src.web_backend.main import app"` sorunsuz.

---

## Faz 1 — Genel asistana pivot: Şablonlu Set + serbest kategori ✅ Tamamlandı

- [x] **`SetTemplate` statik Python config, `SetCategory` gerçek DB tablosu.**
      Plandan sapma: Başlangıçta `SetTemplate`'i de DB tablosu yapmayı
      düşünmüştüm, ama 3 satırlık nadiren-değişen sistem verisi için gereksiz
      karmaşıklıktı — statik config (`set_templates.py`) + gerçek kullanıcı
      verisi olan `SetCategory` tablosu (set_id, name, sort_order) daha doğru
      ayrım. Şablonlar: **Masaüstü Setup** (İşlemci/Anakart/RAM/...),
      **Kombin/Kıyafet** (Tişört/Pantolon/Ayakkabı/...), **Boş/Özel**.
- [x] Set oluşturma modalına şablon seçim kartları eklendi; Set Ayarları'na
      kategori ekle/yeniden-adlandır/sil UI'ı eklendi.
- [x] `category_utils.infer_category()` — önce setin kendi kategori listesiyle,
      bulamazsa PC-parçası anahtar-kelime sözlüğüyle eşleştiriyor; kullanıcı
      "Link ile Ekle" akışında kategori seçip otomatik tahmini geçersiz kılabiliyor.
      `main.py`'de iki yerde birebir kopyalanmış sözlük tek yerde birleştirildi.
- [x] SQLite için hafif otomatik migrasyon (`database.run_lightweight_migrations`)
      eklendi — model'e yeni kolon eklendiğinde mevcut DB'ye ALTER TABLE ile
      otomatik uygulanıyor.

**Canlı tarayıcı testinde bulunup düzeltilen 3 önceden var olan/yeni bug:**
1. `tasks.py`'deki `run_set_scan`, hiç import edilmemiş `schemas` modülünü
   kullanıyordu — Akakçe sonucu senkronize edilecek her "Fiyatları Güncelle"
   çağrısında sessizce `NameError` ile patlıyordu (Faz 0'da bulundu).
2. `run_set_scan` sonunda `db.close()` sonrası `db_set.name`'e erişim —
   döngüdeki `commit()`'ler attribute'ları expire ettiği için `DetachedInstanceError`
   fırlatıyordu, arka plan görevini sessizce çökertiyordu.
3. `SetDetailPage.jsx`'teki `handleAddProduct`, `AddProductWidget`'tan gelen
   `category` alanını API çağrısına iletmeyi unutmuştu (prop-drilling gap) —
   kategori seçici UI'da vardı ama seçim hiç kaydedilmiyordu. Canlı test
   olmasa fark edilmezdi.

Doğrulama: `pytest` 17/17 yeşil, `npm run build` başarılı, gerçek tarayıcıda
uçtan uca test edildi (şablon seçimi → set oluşturma → kategori ekle/sil/rename
→ ürün ekleme + kategori seçimi → doğru kategori grubunda görünme).

---

## Faz 2 — Çift modlu karşılaştırma ✅ Tamamlandı

- [x] **Muadil Ürünler / Başka Mağazada** modları — Akakçe arama sonuçları başlık
      benzerliğine göre sınıflandırılıyor (`similarity_utils.classify_match`,
      stdlib `difflib`, eşik 0.55). Aynı arama tek seferde her iki bucket'ı da
      dolduruyor, ekstra network round-trip gerekmiyor.
      **Plandan sapma:** GTIN/model-no alanı eklenmedi — hiçbir site config'i
      şu an GTIN/EAN çıkarmıyor, bu ayrı bir scraping genişletmesi gerektirir
      (orantısız efor). Başlık benzerliği + görünür güven skoru (`match_confidence`)
      şimdilik daha pratik ve dürüst bir çözüm.
- [x] Sonuç sıralama: **Fiyata Göre** ve **Akıllı Sıralama** (fiyat avantajı skoru,
      eşitlikte eşleşme güveni).
      **Plandan sapma:** "Memnuniyete Göre" sıralama eklenmedi — Akakçe arama
      sonucu kartlarından rating/yorum sayısı çekilmiyor, gerçek veri olmadan
      sahte bir sıralama sunmak yanıltıcı olurdu.

**Bu fazda bulunan kritik bug:** `tasks.py`'deki her iki tarama fonksiyonu da
`akakce.search_batch()`'in gerçek dönüş tipini (`List[AlternativeRow]`, CLI
botuyla paylaşılan tip) yanlışlıkla dict gibi kullanıyordu (`.items()`) —
her çağrıda sessizce `AttributeError` fırlatıp yutuluyordu. Yani **Akakçe
muadil senkronizasyonu web app'te şimdiye kadar hiç çalışmamıştı** — Muadiller
sekmesi hep boştu. `_sync_akakce_alternatives()` helper'ı ile düzeltildi ve
`run_library_scan`'daki ayrı bir bug (ürün adları hiç iletilmiyordu, arama
sonuçsuz kalıyordu) da aynı anda giderildi.

Doğrulama: `pytest` 21/21 yeşil (yeni `test_similarity_utils.py` dahil),
`npm run build` başarılı, gerçek tarayıcıda test verisiyle iki mod + iki
sıralama uçtan uca doğrulandı.

---

## Faz 3 — Teknoloji ürünleri için performans boyutu ✅ Tamamlandı (küçültülmüş kapsamla)

- [x] `BenchmarkEntry` DB tablosu + `benchmark_utils.py` (eşleştirme: başlık
      benzerliği ile, kategori içinde min-max normalizasyon 0-100).
- [x] `LibraryProduct.performance_score` / `benchmark_match_name` —
      `update_decision_signals` içinde her taramada hesaplanıyor.
- [x] UI'da "Performans: X/100" rozeti (ProductCard + LibraryPage kartları,
      sadece eşleşme varsa görünür, hover'da hangi referansla eşleştiği yazar).

**⚠️ Plandan kapsam daraltması — açıkça belirtiyorum:** Orijinal planda
"PassMark'tan periyodik canlı senkronizasyon" vardı. Bunun yerine **elle
küratörlüğü yapılmış, ~37 popüler CPU/GPU'luk bir başlangıç veri seti**
kullandım (`benchmark_utils.BENCHMARK_SEED`), çünkü:
- PassMark'ın sayfa yapısını bu oturumda canlı doğrulayamadım (WebFetch
  tabloyu göremedi, JS-render olasılığı var).
- Doğrulanmamış CSS selector'larla bir scraper yazmak, hiç yazmamaktan daha
  kötü olurdu — tam da bu oturum boyunca düzelttiğimiz "sessizce çalışmayan
  özellik" örüntüsünü tekrar üretirdi.

Mimari buna hazır: `BenchmarkEntry` gerçek bir DB tablosu, `seed_benchmark_entries`
idempotent upsert yapıyor — ileride gerçek bir scraper/senkron script'i bu
listeyi güncellemek yerine DB'yi upsert edecek şekilde eklenebilir, başka
hiçbir şey değişmeden. Popüler olmayan/yeni çıkan parçalar için şimdilik
eşleşme bulunamıyor (performans rozeti sessizce görünmüyor, hata vermiyor).

Doğrulama: `pytest` 26/26 yeşil (yeni `test_benchmark_utils.py` dahil),
`npm run build` başarılı, gerçek dev DB'de "Intel Core i5-14400F" adlı bir
ürünle uçtan uca test edildi (doğru eşleşme + doğru normalize skor: 24.4/100).

---

## Faz 4 — Bildirim kanallarını genişlet ✅ Tamamlandı (Telegram)

**Karar:** Kullanıcı e-postayı şimdilik istemedi, sadece Telegram bot ile
başlanması istendi. E-posta için altyapı (`Notifier` arayüzü) zaten pluggable
olduğu için ileride `EmailNotifier` eklemek `notifiers.py`'ye birkaç satır +
bir sağlayıcı kararı (SMTP vs Resend/SendGrid) meselesi.

- [x] Pluggable `Notifier` arayüzü (`src/web_backend/notifiers.py`).
- [x] `TelegramNotifier` — Telegram Bot API'ye doğrudan REST çağrısı (dokümante,
      kararlı bir API; PassMark'ın aksine canlı doğrulama gerektirmedi).
- [x] `User.telegram_chat_id` alanı + Sidebar'dan erişilen "Bildirim Ayarları"
      modalı (kurulum talimatları + chat ID kaydetme + test mesajı gönderme).
- [x] `crud._create_alert_if_not_exists` her alert oluştuğunda otomatik olarak
      kullanıcının aktif kanallarından bildirim gönderir (sessizce başarısız
      olur — bildirim gönderimi ana akışı asla bloklamaz/çökertmez).

**Not:** Gerçek gönderim, sunucuda `TELEGRAM_BOT_TOKEN` ortam değişkeni
ayarlanmadan çalışmaz (kullanıcının @BotFather'dan bot oluşturup token'ı
env'e eklemesi gerekiyor — bkz. modal içindeki talimatlar). Token olmadan
"Test Gönder" düzgün bir hata mesajıyla başarısız olur, sessizce yutulmaz.

Doğrulama: `pytest` 26/26 yeşil, `npm run build` başarılı, gerçek tarayıcıda
ayarları kaydetme + token-yok durumunda doğru hata mesajı uçtan uca test edildi.

---

## Faz 5 — Ölçek ve gözlemlenebilirlik ✅ Tamamlandı (uyarlanmış kapsamla)

**⚠️ Plandan sapma — Celery kararı:** Orijinal planda periyodik taramayı
"tamamen" Celery/Redis'e taşımak vardı. Bunun yerine mevcut `USE_CELERY` env
anahtarına bağladım (zaten `scan_set` endpoint'inin kullandığı desen):
- `USE_CELERY=true` → periyodik tarama Celery Beat üzerinden çalışır
  (`periodic_library_scan_celery_task`, ayrı bir `celery beat` process'i ister).
- `USE_CELERY` yoksa/false → mevcut `asyncio`-tabanlı döngü devrede kalır.

**Neden bu şekilde:** "Tamamen taşımak" Redis'i zorunlu bağımlılık yapardı —
şu an sıfır ek altyapıyla (`python run_web.py` tek başına) çalışan bir
projeyi, Redis kurulmadan periyodik taraması hiç çalışmayan bir projeye
çevirirdi. Ayrıca mevcut `asyncio.to_thread` kullanımı zaten event loop'u
bloklamıyor (asıl sınırlama paralel değil sıralı taramadır, "sunucu donuyor"
değil) — yani ilk düşündüğümden daha az acil bir sorunmuş. Opsiyonel toggle,
isteyen için ölçeklenebilirliği sağlıyor, istemeyen için hiçbir şeyi bozmuyor.

- [x] `DomainHealth` tablosu (domain başına tekil satır, upsert — sınırsız
      büyüyen bir log değil) + her taramadan sonra otomatik kayıt.
- [x] `GET /api/scraper-health` — hangi domain ne sıklıkla OK/FAILED veriyor.
      **Kapsam notu:** Bu bir API endpoint'i; ayrı bir frontend paneli
      eklenmedi (zaman/kapsam dengesi) — veri zaten sorgulanabilir durumda,
      görsel panel istenirse hızlı bir sonraki adım olur.

Doğrulama: `pytest` 26/26 yeşil, `npm run build` başarılı, hem `USE_CELERY=true`
hem varsayılan (false) durumda app'in sorunsuz boot ettiği doğrulandı.

---

## Durum: Tüm fazlar tamamlandı ✅ (2026-07-01)

Faz 0 → Faz 1 → Faz 2 → Faz 3 → Faz 4 → Faz 5, hepsi tamamlandı. Her fazın
notlarında plandan sapmalar ve nedenleri açıkça işaretli.

**Bu oturumda bulunup düzeltilen, önceden var olan 5 gerçek bug** (hepsi
canlı test veya kod incelemesiyle yakalandı, hiçbiri varsayımla değil):
1. `run_set_scan` sonunda `NameError` (import edilmemiş `schemas`) — her
   "Fiyatları Güncelle" çağrısında Akakçe senkronunu sessizce çökertiyordu.
2. `run_set_scan` sonunda `DetachedInstanceError` — session kapandıktan
   sonra expire olmuş bir attribute'a erişim.
3. `SetDetailPage.jsx`'te kategori seçiminin API'ye hiç iletilmemesi
   (prop-drilling gap) — UI'da seçenek vardı, işe yaramıyordu.
4. Her iki tarama fonksiyonunda `search_batch()`'in dönüş tipinin yanlış
   kullanılması (`List` yerine `dict` gibi) — **Akakçe muadil senkronizasyonu
   web app'te bu oturuma kadar hiç çalışmamıştı.**
5. `run_library_scan`'de Akakçe'ye hiç ürün adı gönderilmemesi (boş liste) —
   arama her zaman sonuçsuz kalıyordu.

Toplam: 26/26 test yeşil, frontend build temiz, tüm yeni akışlar gerçek
tarayıcıda uçtan uca test edildi.
