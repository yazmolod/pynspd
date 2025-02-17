## Sync vs Async

!!! info "TL;DR"
    Для подавляющего большинства случаев вам подойдет синхронный клиент `Nspd`.

    Если вы строите асинхронное приложение, например, в [FastAPI](https://fastapi.tiangolo.com/) -
    используйте асинхронный клиент `AsyncNspd`.

Объяснение сути асинхронного программирования выходит за рамки данной документации. Однако, если попытаться сжать все в один тезис - 
это способ параллельного выполнения задач, требующих больших затрат на время ожидания (например, запрос к серверу).

`pynspd` предлагает оба, как синхронный, так и асинхронный клиент, что позволяет вам использовать его в любом проекте. Например, для разных API-фреймворков:

- [Flask](https://flask.palletsprojects.com/en/stable/) -> `from pynspd import Nspd`
- [FastAPI](https://fastapi.tiangolo.com/) -> `from pynspd import AsyncNspd`

Все методы, которые доступны в синхронном клиенте `Nspd`, также доступны и в асинхронном `AsyncNspd`. 
Однако, нужно не забывать про две важные вещи:

- всем вызовам асинхронных методов должно предшествовать ключевое слово `await`
- все вызовы асихронных методов должны осуществляться в `async` функциях

??? tip "Пример простого скрипта получения GeoJSON с НСПД, используя асинхронный API"
    ```python
    # Стандартная библиотека для работы с `async` функциями 
    import asyncio
    # Сторонняя библиотека - асинхронной аналог `open` для работы с файлами
    import aiofiles
    from pynspd import AsyncNspd


    async def main():
        async with AsyncNspd() as nspd:
            q = input("Введите к/н: ")
            feat = await nspd.search_by_theme(q)
            if feat is None:
                print("Ничего не найдено!")
                return
            async with aiofiles.open(f"{q.replace(':', '-')}.geojson", "w") as file:
                await file.write(feat.model_dump_json())


    if __name__ == "__main__":
        # Запуск функции в event-loop
        asyncio.run(main())
    ```

## Обработка исключений

## Кэширование
По умолчанию, `pynspd` не кэширует результаты запроса. 
Однако, благодаря превосходной библиотеке [Hishel](https://hishel.com/), мы можем активировать его всего за пару строк:

```python
from hishel import FileStorage

storage = FileStorage(base_path='my_storage')
client = Nspd(cache_storage=storage)
```

Теперь каждый результативный запрос (будь то ответ с объектом или ответ об отсутствии объекта), будет сохранен в папке `my_storage` внутри проекта.

Кроме хранения [на диске](https://hishel.com/advanced/storages/#filesystem-storage), в **Hishel** реализовано несколько видов хранилищ - `pynspd` поддерживает каждый из них:

- [В памяти](https://hishel.com/advanced/storages/#in-memory-storage)
- [Redis](https://hishel.com/advanced/storages/#redis-storage)
- [SQLite](https://hishel.com/advanced/storages/#sqlite-storage)
- [S3](https://hishel.com/advanced/storages/#aws-s3-storage)

!!! warning "Сторонние библиотеки для хранилищ"
    Для некоторых типов хранилищ (например, Redis или асихронный SQLite), 
    потребуется установить дополнительные библиотеки, о чем **Hishel** сообщит при попытки использования

??? info "О использовании `hishel.Controller` в `pynspd`"
    В **Hishel** есть три ключевых понятия: *Storage*, *Serializers*, *Controller*. 
    И если первые два всегда зависят от предпочтения конечного пользователя, то *Controller* чаще всего специфичен для каждого конкретного сайта.
    Поэтому в `pynspd` уже заложен *Controller*, специфичный для НСПД.