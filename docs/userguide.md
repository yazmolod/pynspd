## API поиска (на примере ЗУ)

### По кадастровому номеру

```python
from pynspd import AsyncNspd

async with AsyncNspd() as nspd:
    feat = await nspd.search_zu("77:05:0001005:19")

    # исходная геометрия - geojson
    print(feat.geometry.model_dump())
    #> {'type': 'Polygon', 'coordinates': ...}
    
    # но можем легко конвертировать в shapely
    print(type(feat.geometry.to_shape()))
    #> <class 'shapely.geometry.polygon.Polygon'>

    # или принудительно привести к мульти-типу
    print(type(feat.geometry.to_multi_shape()))
    #> <class 'shapely.geometry.multipolygon.MultiPolygon'>

    # Доступ ко всему переченю свойств объекта
    print(feat.properties.options.model_dump())
    #> {'land_record_type': 'Земельный участок', ...}

    # А также форматирование свойств по примеру карточки с сайта
    print(feat.properties.options.model_dump_human_readable())
    #> {'Вид объекта недвижимости': 'Земельный участок', ...}
```

**В точке**:
```python
from shapely import Point

features = await nspd.search_zu_at_point(Point(37.546440653, 55.787139958))
print(features[0].properties.options.cad_num)
#> "77:09:0005008:11446"
```

**В контуре**:
```python
from shapely import wkt

contour = wkt.loads(
    "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
)
features = await nspd.search_zu_in_contour(contour)
cns = [i.properties.options.cad_num for i in features]
print(cns)
#> ["77:01:0001011:8", "77:01:0001011:14", "77:01:0001011:16"]
```

### Типизированный поиск объекта из любого слоя
Шорткаты для типизированного поиска из примеров выше реализованы только для часто используемых слоев *"Земельные участки ЕГРН"* и *"Здания"*. Однако, мы можем искать в любых слоях, представленных на НСПД
```python
# либо импортируем определение слоя, зная его id (с сайта)
from pynspd.schemas import Layer37578Feature as lf_def
# либо найти определение слоя по названию, 
# но тогда объект будет типизирован частично
from pynspd import NspdFeature
lf_def = NspdFeature.by_title(
    "ЗОУИТ объектов энергетики, связи, транспорта" # IDE знает весь перечень слоев 
)                                                  # и подсказывает ввод
feat = await nspd.search_by_model("Останкинская телебашня", lf_def) 

# аналогично для остального API
# nspd.search_in_contour_by_model(contour, lf_def)
# nspd.search_at_point_by_model(pt, lf_def)
```

### Поиск объекта из неизвестного слоя
```python
feat = await nspd.search_by_theme("77:01:0004042:23609")
print(feat.properties.category_name)
#> 'Объекты незавершенного строительства'
```

В данном случае вернется нетипизированный объект `NspdFeature`, 
в котором все еще доступны геометрия и все свойства, но уже без подсказок IDE и метода `.model_dump_human_readable()`

Чтобы это исправить, можно воспользоваться методом `.cast()`

```python
# Исходный результат поиска
print(type(feat).__name__)
#> NspdFeature
print(feat.layer_meta.layer_id, feat.layer_meta.category_id)
#> raise AttributeError

# Автоопределение типа
# Быстрый способ, но объект останется без подсказок IDE 
# и возможна ошибка UnknownLayer
casted_feat = feat.cast()
print(type(casted_feat).__name__)
#> Layer36329Feature

# Ручное определение типа
# Будут активны подсказки, 
# но возможна ошибка валидации, если модель не соответствует объекту
from pynspd.schemas import Layer36329Feature 
casted_feat = feat.cast(Layer36329Feature)
print(casted_feat.layer_meta.category_id)
#> 36384

# Также мы можем привести к типу только свойства
props = feat.properties
print(props.options.model_dump_human_readable())
#> {}

# Автоопределение без подсказок IDE
print(props.cast().options.human_readable())
#> {'Кадастровый номер': '77:01:0004042:23609', ...}

# Ручное определение
from pynspd.schemas import Options36384 
print(props.cast(Options36384).options.human_readable())
#> {'Кадастровый номер': '77:01:0004042:23609', ...}
```