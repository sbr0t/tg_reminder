# Telegram reminder

## Описание
Суть проекта заключается в разработке приложения-напоминалки в Telegram, поскольку существующие приложения для напоминаний на мобильных устройствах не вполне удобны для меня и нет особого смысла разбираться в них.
Поэтому для меня было бы логичным реализовать данное приложение в виде Telegram-бота с понятным и простым функционалом. 

В целях удобства я реализовал многоязычный интерфейс для работы с ботом, чтобы каждый мог настроить его под свои потребности.

Бот будет запущен на моём сервере (ссылка будет предоставлена ниже). Однако следует отметить, что информация из ваших сообщений не будет зашифрована и будет храниться в моей базе данных.

Если вы хотите обеспечить максимальную конфиденциальность, я рекомендую запустить собственный экземпляр бота. Как это сделать, я подробно опишу ниже.## Содержание


## Установка
Шаги для установки проекта:
1. Клонируйте репозиторий: `git clone https://github.com/sbr0t/tg_reminder`
2. Перейдите в директорию проекта: `cd tg_reminder`
3. Установите зависимости: `pip install -r requirements.txt`
4. Также вам потребуется изменить `configs.py` под свои параметры
5. Затем по желанию прописать собственный язык в `language_config.py`
6. Ещё вам потребуется база данных mongodb со следующей структурой:

- ### База данных - tg_reminder
  - Коллекции:
    - reminders
    - users

## Использование
Для запуска бота используйте:
```bash
  python main.py
```

## Контакты
TG - https://t.me/sbr0t
Ссылка на готового бота - https://t.me/reminder_by_sbr0t_bot
