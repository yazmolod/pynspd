# PyNSPD - работа с Национальной системой пространственных данных (ex-ПКК)

**pynspd** — Python-библиотека для работы с сайтом [НСПД](https://nspd.gov.ru/map). Особенности:
- **Синхронное и асинхронное API**: полностью идентичные API позволяют одинаково удобно работать как в старых синхронных, так и высокопроизводительных асинхронных проектах.
- **Полная типизации на [Pydantic](https://github.com/pydantic/pydantic)**: удобная работа с ответами благодаря автозаполнениям от IDE.
- **Автогенерация типов**: данные о перечне слоев, их полях и их типов подтягиваются напрямую с НСПД.
- **Встроенная поддержка [shapely](https://github.com/shapely/shapely)**: удобная аналитика полученной геометрии.

> ⚠️ **Важно**
> - Это неофициальная библиотека
> - НСПД часто меняет схемы объектов. Если у вас происходит ошибка валидации - попробуйте обновить библиотеку

## Пример использования
### Поиск ЗУ
```python
from pynspd import AsyncNspd

async with AsyncNspd() as api:
    feat = await api.search_zu("77:05:0001005:19")

    # исходная геометрия - geojson в EPSG:3857
    print(feat.geometry.wkt)
    > 'POLYGON ((4188557.382334785 7502956.580842949...'
    # но можем легко конвертировать в shapely EPSG:4326
    print(feat.geometry.to_shape(epsg4326=True).wkt)
    > 'POLYGON ((37.626451149629915 55.72040614723934...'

    # Доступ ко всему переченю свойств объекта
    print(feat.properties.options.model_dump())
    > {'land_record_type': 'Земельный участок', ...}
    # А также форматирование свойств по примеру карточки с сайта
    print(feat.properties.options.model_dump_human_readable())
    > {'Вид объекта недвижимости': 'Земельный участок', ...}
```

### Поиск типизированного объекта из любого слоя
```python
from pynspd import AsyncNspd, NspdFeature

async with AsyncNspd() as api:
    # либо импортируем определение слоя, зная его id (с сайта)
    from pynspd.schemas import Layer37578Feature as lf_def
    # либо найти определение слоя по названию, 
    # но тогда объект будет типизирован частично
    lf_def = NspdFeature.by_title(
        "ЗОУИТ объектов энергетики, связи, транспорта"
    ) # IDE знает весь перечень слоев и подсказывает ввод
    feat = await api.search_by_model("Останкинская телебашня", lf_def)    
```

### Поиск объекта с неизвестным слоем
```python
async with AsyncNspd() as api:
    feat = await api.search_by_theme("77:02:0021001:5304")
    print(feat.properties.options.type)
    > 'Машино-место'
```

### Поиск объекта в точке
```python
from shapely import Point

async with AsyncNspd() as api:
    features = await api.search_zu_at_point(Point(37.546440653, 55.787139958))
    print features[0].properties.options.cad_num
    > "77:09:0005008:11446"
```

### Поиск объектов в контуре
```python
from shapely import wkt
async with AsyncNspd() as api:
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = await api.search_zu_in_contour(contour)
    cns = [i.properties.options.cad_num for i in features]
    print(cns)
    > ["77:01:0001011:8", "77:01:0001011:14", "77:01:0001011:16"]
```

## Установка
```
pip install pynspd
```

## Зависимости
- `httpx` - запросы к API НСПД
- `pydantic`, `geojson-pydantic` - типизации проекта
- `pyproj`, `shapely` - для конвертации geojson-геометрии в удобный для аналитики формат
-  `mercantile` - решение задач обратного геокодирования