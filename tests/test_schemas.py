import pytest

from pynspd import Nspd, UnknownLayer
from pynspd.schemas import Layer36049Feature, Options36369, Options36383
from pynspd.schemas.base_feature import BaseFeature


def search(cn: str):
    with Nspd(retries=10) as api:
        feat = api.search_by_theme(cn)
        assert feat is not None
        return feat


def test_feature_cast():
    """Приведение общего объекта к объекту конкретного слоя"""
    cf = search("77:01:0001044:1033").cast()
    assert isinstance(cf, Layer36049Feature)
    assert len(cf.properties.options.model_dump_human_readable()) > 0


def test_feature_cast_by_category():
    """Приведение объекта из скрытого слоя, но с известной категорией"""
    cf = search("77:01:0001044:2938").cast()
    assert isinstance(cf, BaseFeature)
    assert isinstance(cf.properties.options, Options36383)
    assert len(cf.properties.options.model_dump_human_readable()) > 0


def test_feature_failed_cast_on_hidden_layer():
    """Попытка приведения объекта из неизвестного слоя с неизвестной категорией"""
    with pytest.raises(UnknownLayer):
        search("77:02:0021001:5304").cast()


def test_props_cast():
    """Приведение общих свойств к свойствам конкретного слоя"""
    props = search("77:01:0001044:1033").properties.cast().options
    assert isinstance(props, Options36369)
    assert len(props.model_dump_human_readable()) > 0


def test_props_failed_cast_on_hidden_layer():
    """Попытка приведения свойств из неизвестного слоя"""
    with pytest.raises(UnknownLayer):
        search("77:02:0021001:5304").properties.cast()
