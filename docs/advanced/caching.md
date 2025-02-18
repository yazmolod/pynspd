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
