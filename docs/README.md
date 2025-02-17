# PyNSPD

<p align="center">
  <em> Python-библиотека для работы с <a href="https://nspd.gov.ru" target="_blank">НСПД - Национальной системой пространственных данных</a> (ex-ПКК)</em>
</p>
<p align="center">
  <a href="https://pypi.org/project/pynspd/" target="_blank">
      <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/pynspd">
  </a>
  <a href='https://coveralls.io/github/yazmolod/pynspd?branch=main'>
    <img src='https://coveralls.io/repos/github/yazmolod/pynspd/badge.svg?branch=main' alt='Coverage Status' />
  </a>

</p>

---

> ⚠️ **Важно**
>
> - Это неофициальная библиотека
>
> - НСПД часто меняет схемы объектов. Если у вас происходит ошибка валидации - попробуйте обновить библиотеку

## Особенности
- **Синхронное и асинхронное API**: полностью идентичные API позволяют одинаково удобно работать в разных проектах.
- **Полная типизации на [Pydantic](https://github.com/pydantic/pydantic)**: валидация данных и автозаполнения в IDE.
- **Встроенная поддержка [Shapely](https://github.com/shapely/shapely)**: удобная аналитика полученной геометрии.
- **Кэширование из коробки**: сохранение данных в Redis, SQLite и других форматах.
- **Автогенерация типов**: данные о перечне слоев, их полях и их типах подтягиваются напрямую с НСПД.

## Быстрый старт

Установите `pynspd`:

```
pip install pynspd
```

Найдите нужный вам объект:

```python
from pynspd import Nspd

with Nspd() as nspd:
    feat = nspd.search_by_theme("77:05:0001005:19")
```

Доступен полный список аттрибутов (в том числе скрытых), а также сокращенный в человекочитаемом формате:

```python
    print(feat.properties.options.model_dump())
    #> {'readable_address': 'г Москва, ул Серпуховская Б., вл 58',
    #>  'land_record_subtype': 'Землепользование', ...}

    print(feat.properties.cast().options.model_dump_human_readable())
    #> {'Адрес': 'г Москва, ул Серпуховская Б., вл 58',
    #>  'Вид земельного участка': 'Землепользование', ...}
```

Для доступа к дополнительным аттрибутам делаем запрос по вкладке:

```python
    print(await nspd.tab_objects_list(feat))
    #> {'Объект недвижимости: ': ['77:05:0001005:1012']}
```

Геометрию можно сразу конвертировать в `shapely`-формат (например, для работы с `geopandas`):

```python
    print(feat.geometry.to_shape().bounds)
    #> (37.62575417009177, 55.719792499833524, 37.626451149629915, 55.72046606889391)
```

## Документация
С полной документацией можно ознакомиться [здесь](https://yazmolod.github.io/pynspd/)

## Поддержка проекта

Самый простой способ - это оставить ⭐ проекту и отправить его своим коллегам. 
Если же вы хотите принять участие в его развитии, ознакомьтесь со статьей ["Как поддержать проект?"](https://yazmolod.github.io/pynspd/contributing/).