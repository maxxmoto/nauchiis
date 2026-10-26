# научИИсь

Практический гид по вайбкодингу и AI-инструментам: 59 статей, кейсы, чек-листы, калькуляторы, проверка знаний и помощник Маркус.

- **Домен:** https://научиим.рф/
- **Punycode:** https://xn--80aqaqb1b2a.xn--p1ai/
- **Preview на GitHub Pages:** https://maxxmoto.github.io/nauchiis/

## Локальный запуск

```bash
python -m http.server 8000
```

Откройте http://localhost:8000

## Docker

```bash
docker build -t nauchiis .
docker run --rm -p 8080:80 nauchiis
```

Откройте http://localhost:8080

## Деплой на Amvera

Проект уже подготовлен: `Dockerfile`, `nginx.conf`, `amvera.yaml`, `.dockerignore`.

1. Создайте приложение типа **Docker** в Amvera.
2. Подключите GitHub-репозиторий `maxxmoto/nauchiis` или запушьте код в Amvera Git.
3. Сборка идёт по `Dockerfile` / `amvera.yaml`, приложение слушает порт **80**.
4. Откройте **Домены → Добавить доменное имя → HTTPS → Свой домен**.
5. Введите домен в нижнем регистре: `научиим.рф` (если поле не принимает кириллицу — `xn--80aqaqb1b2a.xn--p1ai`).
6. Amvera покажет записи для DNS. У регистратора добавьте:
   - **A** для `@` на IP из Amvera;
   - **TXT** для `_amvera` со значением из Amvera.
7. Дождитесь распространения DNS (до 24 часов) и нажмите «Применить». SSL-сертификат Amvera выпустит автоматически.

После переезда GitHub Pages можно оставить как превью или отключить — canonical и OG-теги уже указывают на `научиим.рф`.

## Структура

- `index.html` — оболочка, стили и интерфейс
- `articles-data.js` — база статей
- `*.webp`, `logo.png`, `favicon*` — ассеты
- `manifest.json`, `robots.txt`, `sitemap.xml` — PWA и SEO
- `Dockerfile`, `nginx.conf`, `amvera.yaml` — деплой на Amvera
