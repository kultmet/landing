# landing

Сайт-лендинг для музыканта на Django.

## Первый запуск

1. Создать и активировать виртуальное окружение.
2. Установить зависимости:

```bash
pip install -r requirements.txt
```

3. Применить миграции:

```bash
python manage.py makemigrations
python manage.py migrate
```

4. Создать администратора:

```bash
python manage.py createsuperuser
```

5. Запустить проект:

```bash
python manage.py runserver
```

После запуска сайт будет доступен на главной странице, а админка — по адресу `/admin/`.

## Проверить на телефоне
Запускаем приложение:

```bash
python manage.py runserver 0.0.0.0:8000
```
