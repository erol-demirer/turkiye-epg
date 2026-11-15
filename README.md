# Türkiye EPG — TiviMate / Xtream Codes

Bu proje, Türkiye XMLTV kaynaklarını birleştirir ve IPTV sağlayıcınızın **mevcut tvg-id** değerlerine göre `epg.xml` / `epg.xml.gz` oluşturur. Canlı yayın akışlarını barındırmaz veya yeniden yayınlamaz.

## Hızlı kurulum (Windows)

1. Python 3.10+ kurun. Dosyaları GitHub'da **yeni bir repository'ye** yükleyin. **Orijinal M3U dosyasını asla GitHub'a yüklemeyin**: yayın URL'leri hesap bilgisi içerebilir. Bu pakette kişisel URL veya hesap şifresi yoktur.
2. GitHub > Settings > Pages > Build and deployment > **GitHub Actions** seçin. Repository'nin varsayılan dalı `main` olmalıdır.
3. Actions > `Update Turkish EPG` > `Run workflow` diyerek ilk dosyayı oluşturun.
4. TiviMate > Settings > EPG > EPG sources > Add source bölümüne `https://KULLANICI.github.io/REPO/epg.xml.gz` URL'sini ekleyin. Bazı istemciler için `epg.xml` tercih edin.
5. TiviMate'de rehber kaynağını oynatma listesiyle ilişkilendirin; boş `tvg-id` kullanan kanallar için `Assign EPG` yapın.

## Yerel komutlar

```sh
python scripts/engine.py
python scripts/engine.py --offline-xml "epg (1).xml"  # internet gerektirmeyen test
python scripts/extract_targets.py kaynak.m3u --out config/targets.json --missing-out local/unnamed.json
```

`config/targets.json` dosyası M3U'nun **yalnızca kanal adlarını ve tvg-id'lerini** içerir. Yayın URL'lerini veya hesap parolasını içermez. Yine de kanal tercihlerinizin açık olmasını istemiyorsanız repoyu özel tutun ve Pages'ı herkese açık yayın yapmayın.

### Önemli sınırlamalar

- Kaynakların her gün çalışması ve bütün programları sağlaması garanti değildir.
- `tvg-id` boş olan kanallar, yalnızca XMLTV eklenerek TiviMate'de her zaman otomatik eşleşmez. Bunları TiviMate `Assign EPG` ile eşleştirin veya M3U'nun `tvg-id` alanını düzenleyebildiğiniz ayrı bir oynatma listesi kullanın.
- Çok kaynaklı rehberde aynı saatte çakışan kayıtlar arasında **önceliği yüksek kaynak** kazanır; diğerleri yalnızca çakışmayan zaman aralıklarını tamamlar.
- `status.json` hangi kaynakların çalıştığını, `matches.csv` kanal eşleşmelerini gösterir.
- Kaynak servislerin erişim ve yeniden dağıtım şartlarını kontrol edin. Kamuya açık yayınlama izni yoksa kişisel kullanım için yerel olarak oluşturun.
- GitHub Pages URL'niz, repository sahibi ve repo ismine göre değişir. Repo'da Pages seçeneğini **GitHub Actions** olarak ayarlayın ve `pages.yml` dağıtım akışının başarılı olduğunu doğrulayın.

## Test

```sh
python -m unittest discover -s tests -v
```

`tests` klasörü gerçek hesap bilgileri veya yayın URL'leri kullanmaz.
