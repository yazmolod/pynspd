# PyNSPD - работа с Национальной системой пространственных данных (ex-ПКК)

**pynspd** — асинхронная Python-библиотека для работы с сайтом НСПД. Особенности:
- **Асинхронность**: обеспечивает высокую производительность и удобство работы в асинхронных приложениях.
- **Полная типизации на [Pydantic](https://github.com/pydantic/pydantic)**: удобная работа с ответами благодаря автозаполнениям от IDE.
- **Автогенерация типов**: данные о перечне слоев, их полях и их типов подтягиваются напрямую с НСПД.
- **Встроенная поддержка [shapely](https://github.com/shapely/shapely)**: удобная аналитика полученной геометрии.

> ⚠️ **Важно**
> - Это неофициальная библиотека
> - Она в фазе активной разработки
> - НСПД в любой день может обновить API

## Пример использования
### Получение ЗУ
```python
from pynspd import AsyncNspd

async with AsyncNspd() as api:
    feat = await api.search_zu("77:05:0001005:19")
    print(feat.geometry.wkt)
    > 'POLYGON ((4188557.382334785 7502956.580842949...'
    print(feat.geometry.to_shape(epsg4326=True).wkt)
    > 'POLYGON ((37.626451149629915 55.72040614723934...'
    print(feat.properties.options.model_dump())
    > {'land_record_type': 'Земельный участок', 'land_record_subtype': 'Землепользование', ...}
    print(feat.properties.options.model_dump_human_readable())
    > {'Вид объекта недвижимости': 'Земельный участок', 'Вид земельного участка': 'Землепользование', ...}
```

### Получение типизированного объекта из любого слоя
```python
from pynspd import AsyncNspd, NspdFeature

async with AsyncNspd() as api:
    # либо импортируем определение слоя, зная его id (с сайта)
    from pynspd import Layer37578Feature as lf_def
    # либо найти определение слоя по названию, но тогда объект будет типизирован частично
    lf_def = NspdFeature.by_title("ЗОУИТ объектов энергетики, связи, транспорта") # IDE знает весь перечень слоев и подсказывает ввод
    feat = await api.search_one("Останкинская телебашня", lf_def)    
```

### Получение объекта с неизвестным слоем
```python
from pynspd import AsyncNspd

async with AsyncNspd() as api:
    feat = await api.search_by_theme("77:02:0021001:5304")
    print(feat.properties.options.type)
    > 'Машино-место'
```

## Установка
На период разработки установка возможна из репозитория 
```
pip install git+https://github.com/yazmolod/pynspd.git
```

## Зависимости
- `httpx` - для запросов к API НСПД
- `pydantic` - для типизации проекта
- `geojson-pydantic` - для типизации ответов НСПД
- `shapely` - для конвертации geojson-геометрии в удобный для аналитики формат
- `pyproj` - для перепроецирования геометрии