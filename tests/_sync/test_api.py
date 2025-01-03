import pytest
from shapely import wkt
from shapely.geometry import MultiPolygon, Polygon

from pynspd import Nspd, NspdFeature
from pynspd.schemas import Layer36048Feature, Layer36049Feature, Layer37578Feature


@pytest.fixture(scope="session")
def api():
    with Nspd() as client:
        yield client


def test_search_by_theme(api: Nspd):
    feat = api.search_by_theme("77:02:0021001:5304")
    assert feat.properties.options.type == "Машино-место"


def test_search_by_model(api: Nspd):
    lf_def = NspdFeature.by_title("ЗОУИТ объектов энергетики, связи, транспорта")
    assert lf_def == Layer37578Feature
    feat = api.search_by_model("Останкинская телебашня", lf_def)
    assert isinstance(feat, lf_def)
    assert len(feat.properties.options.model_dump_human_readable()) > 0


def test_search_zu(api: Nspd):
    feat = api.search_zu("77:05:0001005:19")
    assert feat.properties.options.land_record_type == "Земельный участок"
    assert isinstance(feat.geometry.to_shape(), Polygon)
    assert isinstance(feat.geometry.to_multi_shape(), MultiPolygon)


def test_search_many_zu(api: Nspd):
    features = api.search_many_zu("77:03:0001001:82 77:03:0001001:26 77:03:0001001:132")
    assert len(features) == 3
    assert all([i is not None for i in features])


def test_search_oks(api: Nspd):
    feat = api.search_oks("77:03:0001001:3030")
    assert feat.properties.options.build_record_type_value == "Здание"
    assert isinstance(feat.geometry.to_shape(), Polygon)


def test_search_many_oks(api: Nspd):
    features = api.search_many_oks(
        "77:03:0001001:3030 77:03:0001001:1111 77:03:0001001:1112"
    )
    assert len(features) == 3
    assert all([i is not None for i in features])


def test_search_zu_in_contoir(api: Nspd):
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = api.search_zu_in_contour(contour)
    assert features is not None
    assert all([isinstance(i, Layer36048Feature) for i in features])
    cns = [i.properties.options.cad_num for i in features]
    assert set(["77:01:0001011:8", "77:01:0001011:14", "77:01:0001011:16"]) == set(cns)


def test_search_oks_in_contoir(api: Nspd):
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = api.search_oks_in_contour(contour)
    assert features is not None
    assert all([isinstance(i, Layer36049Feature) for i in features])
    cns = [i.properties.options.cad_num for i in features]
    assert set(["77:01:0001011:1164", "77:01:0001011:1002"]) == set(cns)


def test_search_in_contoir_empty(api: Nspd):
    contour = wkt.loads(
        "Polygon ((37.63215 55.75588, 37.63214 55.75557, 37.63271 55.75570, 37.63215 55.75588))"
    )
    features = api.search_zu_in_contour(contour)
    assert features is None
