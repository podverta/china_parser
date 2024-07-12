# Проект Парсинга с использованием FastAPI, Celery и Redis

Этот проект предназначен для выполнения парсинга с использованием FastAPI для API, Celery для асинхронных задач и Redis в качестве брокера сообщений.

## Установка

### 1. Клонирование репозитория

Клонируйте репозиторий на ваш локальный компьютер:

```bash
git clone <URL вашего репозитория>
cd <название директории вашего репозитория>
```
### 2. Создание виртуального окружения
Создайте виртуальное окружение и активируйте его:

```bash
python -m venv .venv
source .venv/bin/activate  # для Linux/MacOS
.venv\Scripts\activate  # для Windows
```
### 3. Установка зависимостей
Установите необходимые зависимости:
```bash
pip install -r requirements.txt
```
### 4. Установка и запуск Redis
Если у вас еще не установлен Redis, следуйте инструкциям:

Установите Redis:
```bash
sudo apt-get update && sudo apt-get install redis-server
```
Запустите Redis: 
```bash
sudo service redis-server start
```
### 5. Установка и запуск Celery
Установка Celery
Если у вас еще не установлен Celery, установите его с помощью pip:
```bash
pip install celery
```
Запуск Celery
```bash
celery -A services_app.celery_app worker --loglevel=info
```
### 6. Настройка окружения
Создайте файл .env в корневой директории проекта и добавьте следующие переменные окружения:
```bash
REDIS_URL=redis://localhost:6379/0
```
### 7. Запуск FastAPI
Запустите FastAPI приложение:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8123 --reload
```
### Использование
Отправка задачи парсинга
Для отправки задачи парсинга используйте следующий эндпоинт:
```text
POST /run_parser/
Content-Type: application/json
```
```json
{
    "parser_name": "FetchAkty",
    "args": [],
    "kwargs": {"leagues": ["league1", "league2"]}
}
```
### Проверка состояния задач
Celery и Redis позволяют проверять состояние задач. Вы можете настроить интерфейс для мониторинга, такой как Flower, чтобы отслеживать задачи Celery:
```bash
pip install flower
celery -A services_app.celery_app flower
```
Перейдите по адресу http://localhost:5555, чтобы просмотреть статус задач.
### Структура проекта
```plaintext
project/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── router.py
│   ├── schema.py
│   └── celery_app.py
├── fetch_data/
│   ├── __init__.py
│   ├── fetch.py
│   └── fb.py
├── services_app/
│   ├── __init__.py
│   └── tasks.py
├── .env
├── requirements.txt
└── README.md
```
Основные файлы
```text
Основные файлы

main.py: Запуск FastAPI приложения.

router.py: Определение маршрутов для FastAPI.

schema.py: Схемы данных для валидации входящих запросов.

celery_app.py: Настройка и инициализация Celery.

tasks.py: Определение задач Celery.

akty.py: Реализация парсера Akty.com.

fb.py: Реализация парсера fb.com.
```
