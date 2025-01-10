import pytest

from pynspd import Nspd, UnknownLayer
from pynspd.schemas import Layer36049Feature, Options36383
from pynspd.schemas.feature import _BaseFeature


def find_and_cast(cn: str):
    with Nspd() as api:
        feat = api.search_by_theme(cn)
        assert feat is not None
        cf = feat.cast()
        return cf


def test_feature_cast():
    cf = find_and_cast("77:01:0001044:1033")
    assert isinstance(cf, Layer36049Feature)
    assert len(cf.properties.options.model_dump_human_readable()) > 0


def test_feature_cast_by_category():
    cf = find_and_cast("77:01:0001044:2938")
    assert isinstance(cf, _BaseFeature)
    assert isinstance(cf.properties.options, Options36383)
    assert len(cf.properties.options.model_dump_human_readable()) > 0


def test_feature_failed_cast_on_hidden_layer():
    with pytest.raises(UnknownLayer):
        find_and_cast("77:02:0021001:5304")
