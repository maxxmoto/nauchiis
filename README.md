# научИИсь

Практический гид по вайбкодингу и AI-инструментам: 61 статья, кейсы, чек-листы, калькуляторы, проверка знаний и помощник Маркус.

- **Домен:** https://научиим.рф/
- **Punycode:** https://xn--80aqaqb1b2a.xn--p1ai/
- **Репозиторий:** https://github.com/maxxmoto/nauchiis
- **Preview:** https://maxxmoto.github.io/nauchiis/

## Что внутри

- `index.html`, `articles-data.js` — статический сайт
- `server.py` — FastAPI: статика + `/api/marcus` для GigaChat
- `requirements.txt` — зависимости бэкенда
- `og.png`, `*.webp`, `logo.webp`, `favicon*` — ассеты
- `Dockerfile`, `amvera.yaml` — деплой на Amvera
- `.env.example` — пример переменных для локального запуска

## Локальный запуск

Только статика (Маркус работает в локальном режиме):

```bash
python -m http.server 8000
```

Полный сервер с GigaChat:

```powershell
pip install -r requirements.txt
$env:STATIC_DIR = "."
$env:GIGACHAT_AUTH_KEY = "..."   # ключ авторизации GigaChat
uvicorn server:app --host 0.0.0.0 --port 8000
```

Откройте http://localhost:8000

Без ключа `/api/marcus` вернёт 503, а фронтенд автоматически откатится к локальному поиску по статьям.

## GigaChat: переменные

Задайте один из вариантов:

- `GIGACHAT_AUTH_KEY` — готовый Authorization key (base64 `client_id:client_secret`);
- или `GIGACHAT_CLIENT_ID` + `GIGACHAT_CLIENT_SECRET`.

Дополнительно:

- `GIGACHAT_SCOPE` — `GIGACHAT_API_PERS` (по умолчанию) или `GIGACHAT_API_CORP`;
- `GIGACHAT_MODEL` — `GigaChat-2` по умолчанию; доступные модели смотрите в `/api/health?probe=1`;
- `GIGACHAT_VERIFY_SSL` — `false` по умолчанию. Если в контейнер добавлен российский корневой сертификат, поставьте `true`.

**Ключ никогда не попадает во фронтенд и репозиторий.** В Amvera добавьте его в переменные/секреты приложения.

## Проверка, что работает ИИ

- Откройте `https://научиим.рф/api/health?probe=1` — должно быть `gigachat_configured: true`, `gigachat_token: true`, `gigachat_models: true` и список доступных моделей.
- Ответы Маркуса приходят с источниками; если GigaChat недоступен, он отвечает локально.
- DevTools → Network: содержательный вопрос должен дать `/api/marcus` → `200` и JSON с `answer`.
- `503` — ключ не задан; `502`/`500` — ошибка GigaChat (смотрите логи Amvera); `429` — сработал лимит.
- Приветствия, «ты кто», квиз, тема, поделиться и локальный триггер на мат — всегда обрабатываются правилами, это нормально.

## Деплой на Amvera

1. Создайте приложение типа **Docker**.
2. Подключите GitHub-репозиторий `maxxmoto/nauchiis`, ветка `main`.
3. Amvera использует `amvera.yaml` и `Dockerfile`, приложение слушает порт **80**.
4. В **Переменные/Секреты** добавьте `GIGACHAT_AUTH_KEY` (или client id/secret).
5. **Домены → Добавить доменное имя → HTTPS → Свой домен**.
6. Введите `научиим.рф` в нижнем регистре (если кириллица не принимается — `xn--80aqaqb1b2a.xn--p1ai`).
7. У регистратора добавьте **A** для `@` и **TXT** для `_amvera` со значениями из Amvera. Дождитесь DNS и нажмите «Применить».
8. SSL-сертификат Amvera выпустит автоматически.

После переезда GitHub Pages можно оставить как превью или отключить — canonical и OG-теги указывают на `научиим.рф`.
