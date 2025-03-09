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

- всем вызовам асинхронных методов должно предшествовать ключевое слово `await`;
- все вызовы асихронных методов должны осуществляться в `async` функциях.

!!! example "Пример простого скрипта получения GeoJSON с НСПД, используя асинхронный API"
    ```python
    # Стандартная библиотека для работы с `async` функциями 
    import asyncio
    # Сторонняя библиотека - асинхронной аналог `open` для работы с файлами
    import aiofiles
    from pynspd import AsyncNspd


    async def main():
        async with AsyncNspd() as nspd:
            q = input("Введите к/н: ")
            feat = await nspd.find(q)
            if feat is None:
                print("Ничего не найдено!")
                return
            async with aiofiles.open(f"{q.replace(':', '-')}.geojson", "w") as file:
                await file.write(feat.model_dump_json())


    if __name__ == "__main__":
        # Запуск функции в event-loop
        asyncio.run(main())
    ```