# Current maintenance status

> **Superseded:** this prototype was continued as [KeepMoney](https://github.com/menesdeniz1/keepmoney) (multi-user web dashboard + Telegram bot, CI, Docker Compose). This repository is kept for reference and is no longer developed.

Publication scope: experimental source code, not a production-ready hosted service. Nineteen selected offline tests passed during the September 2026 publication pass (price parsing, benchmark helpers, decision logic, manual-price rules, similarity helpers, lowest-price selection and mocked migration logic). Full API, scraping, browser, real-workbook migration and deployment behavior were not validated. Older feature descriptions below describe implementation goals and are not guarantees of retailer compatibility or security.

Use synthetic data first. Keep workbooks, database files and logs outside version control. Only access sites you are authorized to use; do not treat anti-bot tooling as permission to bypass access restrictions. Before any hosting, review authentication, CORS, rate limits and account isolation. Configure a private persistent `JWT_SECRET` for a deployment; without one the server generates a process-local secret, so sessions do not survive restarts consistently.

Hardcoded initial passwords were removed from reachable history. Export SETPRICE_INITIAL_ADMIN_PASSWORD (unique, 16+ characters) before initial account creation; do not commit it. Environment variables are configuration, not encryption. Existing accounts are NOT reset: change their passwords separately. Password storage already uses bcrypt. The legacy Excel importer has not been fully validated.

See [PUBLICATION_NOTES.md](PUBLICATION_NOTES.md).

---

# Fiyat Botu

Özel PC toplama Excel tabloları için gelişmiş, anti-bot korumalarını (Cloudflare vb.) aşabilen, Akakçe destekli fiyat takip botu.

## Özellikler

- **Hibrit Fetch Sistemi:** Basit siteler (Tebilon, n11) için hızlı `requests`, zorlu siteler (Amazon, Hepsiburada, Trendyol) için `Playwright`.
- **Excel Mimarisi:** Bot yalnızca `Kaynaklar`, `Katalog`, `Muadiller` ve `Fiyat_Gecmisi` sayfalarına yazar. Setup (`139k`, `146k` vb.) sayfalarına ASLA DOKUNMAZ.
- **Akıllı Parse:** Hem Türkçe (`2.798,80 ₺`) hem Amerikan (`2,399.00 TL`) hem de düz formatları (`57.528`) sorunsuz algılar.
- **Muadil Arama:** Akakçe üzerinden her ürün için en ucuz ilk 3 muadili bulur.
- **Manuel Kararlara Saygı:** Excel'de `Kilit=Evet` yapılan veya başına `*` konulan fiyatlara dokunmaz. `(Alınmayacak)`, `(Mevcut)` notlarını anlar.
- **Güvenlik:** Her güncellemeden önce otomatik yedek (`data/backups/`) alır.

## Kurulum

```bash
# 1. Gerekli kütüphaneleri kurun
pip install -r requirements.txt

# 2. Playwright tarayıcısını kurun
playwright install chromium
```

## Kullanım

### 1. İlk Kez (Göç / Migration)
Mevcut `pc_setup.xlsx` dosyanızı analiz edip bot'un kullanacağı sayfaları oluşturur.
```bash
python main.py --migrate
```
*Not: Eğer setup sayfalarındaki fiyat sütunlarına INDEX/MATCH formüllerini de uygulamasını istiyorsanız `--apply-formulas` ekleyin. Güvenli gitmek için bunu manuel yapmanız önerilir.*

### 2. Tek Seferlik Güncelleme
```bash
python main.py --once
```

### 3. Otomatik İzleme Modu
Botu arka planda bırakın, her saat başı fiyatları güncellesin.
```bash
python main.py --watch --interval 60
```

### 4. Durum ve Excel aktarımı
```bash
python main.py --status                      # veritabanı durumunu göster
python main.py --import-excel --excel-path pc_setup.xlsx   # Excel'den DB'ye toplu aktarım
python main.py --export-excel                # DB'den Excel'e güncel verileri yaz
python main.py --once --force                # checkpoint'leri yok sayıp sıfırdan tara
```

### 5. Deneme Çalıştırması (Dry Run)
Hiçbir dosyaya yazmadan ne yapacağını görmek için.
```bash
python main.py --once --dry-run
```

## Web Uygulaması (prototip)

CLI'nin yanında bir web arayüzü de var. Doğrulanmış bir dağıtım değildir; yalnızca yerelde deneyin.

- **Backend:** FastAPI + SQLAlchemy (`src/web_backend/`), JWT + bcrypt ile giriş. `python run_web.py` → http://localhost:8000
- **Frontend:** React (`frontend/`), derlenmiş hali `src/web_backend/static_build/`
- **Arka plan işleri (opsiyonel):** Celery + Redis (`src/web_backend/tasks.py`, `REDIS_URL`)
- **Bildirimler:** Telegram (`src/web_backend/notifiers.py`)
- **AI karar motoru:** `src/core/ai_decision_engine.py` — sırayla Gemini → Groq → Cerebras → OpenRouter → GitHub Models sağlayıcılarını dener; anahtarlar ortam değişkeninden okunur (ör. `GEMINI_API_KEY`)
- **Testler:** `tests/` (pytest; fiyat ayrıştırma, karar mantığı, manuel kilitler, migration, web API)

## Yeni Satıcı Eklemek

`config/sites/` klasörüne yeni bir `satıcı_domain.yaml` oluşturun:
```yaml
domain: "itopya.com"
seller_name: "İtopya"
render: false   # JS gerekmiyorsa false

extraction:
  - type: "jsonld"
    path: "offers.price"
```

## Yeni Kasa Setup'ı Eklemek
Mevcut setup'ı çoğaltın, fiyat hücrelerine şu formülü kopyalayın:
`=INDEX(Katalog!$C:$C, MATCH($C5, Katalog!$A:$A, 0))`

(Burada `C` ürün adı sütunu, `Katalog!C` katalogdaki fiyat sütunu, `Katalog!A` katalogdaki ürün sütunudur)
