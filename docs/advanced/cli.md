## Установка

Установите пакет с опцией `[cli]` при помощи удобного для вас пакетного менеджера:

=== "uv"
    ``` shell
    $ uv tool install pynspd[cli]
    ```

=== "pipx"
    ``` shell
    $ pipx install pynspd[cli]
    ```

=== "pip"
    ``` shell
    $ python -m pip install pynspd[cli]
    ```

Проверьте корректность установки:
``` shell
$ pynspd -v
1.0.0
```
!!! tip 
    Если команда `pynspd` не найдена - перезапустите консоль

## Использование

При вводе команды без аргументов вам всегда будет доступна подсказка по опциям, аргументам и командам:
``` shell
$ pynspd
                                                                                                                                                                                     
 Usage: pynspd [OPTIONS] COMMAND [ARGS]...        

 Утилита командной строки для поиска на НСПД                                                                                                                                   
                                                                                                                                                                                     
╭─ Options ────────────────────────────────────────────────────────────────────────╮
│ --version             -v        Show current version                       │
│ --install-completion            Install completion for the current shell.  │
│ --show-completion               Show completion for the current shell,     │
│                                 to copy it or customize the installation.  │
│ --help                          Show this message and exit.                │
╰───────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────╮
│ geo        Поиск объектов по геоданным                                     │
│ search     Поиск объектов по тексту                                        │
╰───────────────────────────────────────────────────────────────────────────────────╯

```

Как видно по подсказке, доступны два варианта поиска - по тексту или по геоданным.


### `pynspd search`

``` shell
$ pynspd search
                                                                                                                                                                                     
Usage: pynspd search [OPTIONS] INPUT                                                                                                                                                  

Поиск объектов по тексту
По умолчанию разбивает запрос на кадастровые номера 
и ищет в объектах недвижимости.

╭─ Arguments ────────────────────────────────────────────────────────────────────────╮
│ *    input      TEXT  Список искомых к/н. Может быть текстовым файлом        │
╰─────────────────────────────────────────────────────────────────────────────────────╯
```

В качестве аргумента `input` принимается:

- Текстовый список к/н. Номеров может быть несколько (тогда их нужно заключить в кавычки);
``` shell
$ pynspd search "77:07:0006001:9 77:07:0006001:1512"
```

- Текстовый файл `.txt`, в котором хранится перечень к/н.
``` shell
$ pynspd search my_list.txt
```

Если требуется искать не по списку к/н, то можно отключить валидацию при помощи флага `--plain / -p`.
В таком случае обычный ввод будет восприниматься как есть, а файловый - построчно.
``` shell
$ pynspd search --plain cities.txt
```


### `pynspd geo`

``` shell
$ pynspd geo
                                                                                                                                                                                     
 Usage: pynspd geo [OPTIONS] INPUT [LAYER_NAME]                                                                                                                                      

 Поиск объектов по геоданным

╭─ Arguments ────────────────────────────────────────────────────────────────────────╮
│ *    input           TEXT          Путь к файлу с геоданными или WKT         │
╰─────────────────────────────────────────────────────────────────────────────────────╯
```

В качестве аргумента `input` принимается:

- Файл с геоданными (например `.geojson`). В данном файле может быть несколько объектов, но все они должны быть:
    - одного из поддерживаемого типов (`Point`, `Polygon`, `MultiPolygon`)
    - все объекты - одного типа (например, только точки);
``` shell
$ pynspd geo my_geo.geojson
```

- Координаты точки (lat, lng). Может быть несколько; могут содержаться в файле `.txt`:
``` shell
$ pynspd geo "55.605, 37.562"
```

- Строка геоданных формата [WKT](https://ru.wikipedia.org/wiki/WKT):
``` shell
$ pynspd geo "Point (37.562 55.605)"
```

!!! tip "Для пользователей QGIS"
    В QGIS WKT-представление геометрии можно быстро получить при помощи, например, [этого плагина](https://github.com/skeenp/QGIS3-getWKT)

В качестве аргумента `layer_name` принимается точное имя слоя с НСПД - именно в нем и будет производиться поиск.
По умолчанию, это слой с земельными участками.


### Опции

Для обоих методов есть одинаковый перечень опциональных параметров, которые указываются в подсказке:


**`-с, --choose-layer`**

> Выбрать слои из списка вместо слоя по умолчанию.

``` shell
$ pynspd search --plain --choose-layer "40:15:190101"
? Выберите слои:  (Use arrow keys to move, <space> to select, <a> to toggle, <i> to invert)
   ○ Кадастровые округа
   ○ Территории объектов культурного наследия
   ○ Кадастровые районы
 » ● Кадастровые кварталы
   ...
```

**`-o, --output`**

> Сохранить результат поиска в указанных файл. По умолчанию выводит результат поиска в терминал.

> Можно сохранить в формате табличных данных (файлы `.xlsx`, `.csv`), либо в формате геоданных (форматы `.gpkg`, `.geojson` и др.)


**`-l, --localize`**

> Использовать названия колонок, взятые со страницы НСПД, а не оригинальные названия. Например, `cad_num` -> `Кадастровый номер`.

> Из-за того, что не все колонки отображаются на сайте, часть данных будет утеряна.

> Если флаг не указан, то используются оригинальные названия.


**`--tab-objects`**

> При использовании этого флага полученные данные обогащаются данными со вкладки "Объекты"


### Переменные окружения

Для более тонкой настройки клиента, вам потребуется установить переменные окружения в активной сессии вашего терминала.
Например, для установки прокси или сохранения кэша:

=== "pwsh (Windows)"
    ``` shell
    $ $Env:PYNSPD_CLIENT_PROXY=http://my-proxy:42
    $ $Env:PYNSPD_CACHE_REDIS_URL=redis://localhost:6379/0
    ```

=== "bash (Linux)"
    ``` shell
    $ export PYNSPD_CLIENT_PROXY=http://my-proxy:42
    $ export PYNSPD_CACHE_REDIS_URL=redis://localhost:6379/0
    ```

Подробнее о доступных переменных окружения читайте [в этой статье](client.md).