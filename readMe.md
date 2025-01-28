# Telegram Quiz Bot

Этот бот для Telegram позволяет создавать викторины, обрабатывать их результаты и отслеживать победителей.

## Установка и запуск

### 1. Установка зависимостей
Установите зависимости:
```bash
pip install -r requirements.txt
```

### 1. Настройка
Добавь в код токен бота и айди чата в который вы хотите чтобы бот присылал викторины:
```ini
TOKEN=your_telegram_bot_token
CHAT_ID=your_chat_id
```

### 1. Запуск бота
```bash
python index.py
```

## Использование

- `/start` — показать доступные команды
- `/create_quiz` — начать создание новой викторины
- `/cancel` — отменить создание викторины
- `/process` — обработать результаты последней викторины
- `/winners` — показать текущий рейтинг победителей
- `/reset` — сбросить все результаты викторин