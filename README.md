# Nova

# Тикет-система

## Запуск проекта локально

1. Создать и активировать виртуальное окружение:
   ```
   python -m venv venv
   venv\Scripts\activate        (Windows)
   source venv/bin/activate     (Linux / Mac)
   ```

2. Установить зависимости:
   ```
   pip install -r req.txt
   ```

3. **Создать файл `.env` из образца** (один раз):
   ```
   copy .env.example .env       (Windows)
   cp .env.example .env         (Linux / Mac)
   ```
   Затем при необходимости вписать в `.env` реальные значения.
   Без этого файла сайт запустится в безопасном режиме (DEBUG=False),
   и статика/отладка работать не будут — для локальной разработки `.env` нужен.

4. Применить миграции и запустить сервер:
   ```
   python manage.py migrate
   python manage.py runserver
   ```

Адрес: http://127.0.0.1:8000/

> Файл `.env` содержит секреты (ключи, пароли) и НЕ хранится в git.