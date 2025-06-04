# pynspd

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
> Данная библиотека является неофициальным проектом и создана исключительно в образовательных целях

## Особенности
- **Синхронное и асинхронное API**: полностью идентичные API позволяют одинаково удобно работать в разных проектах.
- **Полная типизации проекта**: автозаполнения в IDE, статический анализ и прочие удобства современного Python.
- **Автогенерация схем**: данные о перечне слоев, их полях и их типах подтягиваются напрямую с НСПД.
- **Валидации данных от [Pydantic](https://github.com/pydantic/pydantic)**: гарантия, что библиотека соответствует сайту.
- **Поддержка работы с геометрией от [Shapely](https://github.com/shapely/shapely)**: удобная аналитика полученной геометрии.
- **Кэширование из коробки от [Hishel](https://hishel.com)**: сохранение данных в Redis, SQLite и других форматах.

## Быстрый старт

Установите `pynspd`:

``` shell
$ pip install pynspd
```

Найдите нужный вам объект:

```python
from pynspd import Nspd

with Nspd() as nspd:
    feat = nspd.find("77:05:0001005:19")
```

Доступен полный список аттрибутов (в том числе скрытых):
```python
    print(feat.properties.options.model_dump())
    #> {'readable_address': 'г Москва, ул Серпуховская Б., вл 58',
    #>  'land_record_subtype': 'Землепользование', ...}
```

Который можно конвертировать в человекочитаемый формат:

```python
    print(feat.properties.cast().options.model_dump_human_readable())
    #> {'Адрес': 'г Москва, ул Серпуховская Б., вл 58',
    #>  'Вид земельного участка': 'Землепользование', ...}
```

Для доступа к дополнительным аттрибутам делаем запрос по вкладке:

```python
    print(nspd.tab_objects_list(feat))
    #> {'Объект недвижимости: ': ['77:05:0001005:1012']}
```

Геометрию можно сразу конвертировать в `shapely`-формат (например, для работы с `geopandas`):

```python
    print(feat.geometry.to_shape().bounds)
    #> (37.62575417009177, 55.719792499833524, 37.626451149629915, 55.72046606889391)
```

---

С более детальным описанием библиотеки можно ознакомиться в [руководстве пользователя](https://yazmolod.github.io/pynspd/userguide/).

## Работа из консоли (CLI)

Установка:
``` shell
$ pip install pynspd[cli]
$ pynspd --version
1.0.0
```

Для поиска по к/н:
``` shell
$ pynspd find "77:05:0001005:19"
```

Для поиска по геометрии:
``` shell
$ pynspd geo "55.605, 37.562" 
```

Подробный обзор можно найти в [этой статье](https://yazmolod.github.io/pynspd/advanced/cli/).

## Поддержка проекта

Самый простой способ - это оставить ⭐ проекту на [GitHub](https://github.com/yazmolod/pynspd) и отправить его своим коллегам. 
Если же вы хотите принять участие в его развитии, ознакомьтесь со статьей ["Как поддержать проект?"](https://yazmolod.github.io/pynspd/contributing/).