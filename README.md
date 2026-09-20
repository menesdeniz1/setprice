# Current maintenance status

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

### 4. Sadece Muadilleri Güncelle
```bash
python main.py --alternatives-only
```

### 5. Deneme Çalıştırması (Dry Run)
Hiçbir dosyaya yazmadan ne yapacağını görmek için.
```bash
python main.py --once --dry-run
```

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
