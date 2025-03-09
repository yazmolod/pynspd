from functools import partial

import pytest
from shapely import wkt
from shapely.geometry import MultiPolygon, Polygon

from pynspd import Nspd, NspdFeature
from pynspd.errors import TooBigContour
from pynspd.schemas import Layer36048Feature, Layer36049Feature, Layer37578Feature


def test_find(api: Nspd):
    feat = api.find("77:02:0021001:5304")
    assert feat is not None
    assert feat.properties.options.model_dump()["type"] == "Машино-место"


def test_find_non_exists(api: Nspd):
    feat = api.find("77:02:0021001:5304111111")
    assert feat is None


def test_find_in_layer(api: Nspd):
    lf_def = NspdFeature.by_title("ЗОУИТ объектов энергетики, связи, транспорта")
    assert lf_def == Layer37578Feature
    feat = api.find_in_layer("Останкинская телебашня", lf_def)
    assert isinstance(feat, lf_def)
    assert len(feat.properties.options.model_dump_human_readable()) > 0


def test_find_in_layer_non_exists(api: Nspd):
    feat = api.find_in_layer("77:02:0021001:5304111111", Layer36048Feature)
    assert feat is None


def test_search_zu(api: Nspd):
    feat = api.find_zu("77:05:0001005:19")
    assert feat is not None
    assert feat.properties.options.land_record_type == "Земельный участок"
    assert isinstance(feat.geometry.to_shape(), Polygon)
    assert isinstance(feat.geometry.to_multi_shape(), MultiPolygon)


def test_search_oks(api: Nspd):
    feat = api.find_oks("77:03:0001001:3030")
    assert feat is not None
    assert feat.properties.options.build_record_type_value == "Здание"
    assert isinstance(feat.geometry.to_shape(), Polygon)


def test_search_zu_in_contour(api: Nspd):
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = api.search_zu_in_contour(contour)
    assert features is not None
    assert all([isinstance(i, Layer36048Feature) for i in features])
    cns = [i.properties.options.cad_num for i in features]
    assert set(["77:01:0001011:8", "77:01:0001011:14", "77:01:0001011:16"]) == set(cns)


def test_search_oks_in_contour(api: Nspd):
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = api.search_oks_in_contour(contour)
    assert features is not None
    assert all([isinstance(i, Layer36049Feature) for i in features])
    cns = [i.properties.options.cad_num for i in features]
    assert set(["77:01:0001011:1164", "77:01:0001011:1002"]) == set(cns)


def test_search_in_big_contour(cache_api: Nspd):
    with pytest.raises(TooBigContour):
        contour = wkt.loads(
            "Polygon ((37.6951 55.7320, 37.7338 55.7279, 37.7469 55.7563, 37.7283 55.7531, 37.7196 55.7343, 37.6981 55.7359, 37.6951 55.7320))"
        )
        cache_api.search_zu_in_contour(contour)
    for oks_feat in cache_api.search_oks_in_contour_iter(contour):
        assert oks_feat is not None
        break
    feats_all = [f for f in cache_api.search_zu_in_contour_iter(contour)]
    feats_int = [
        f for f in cache_api.search_zu_in_contour_iter(contour, only_intersects=True)
    ]
    assert len(feats_all) > len(feats_int)


def test_search_in_contour_empty(api: Nspd):
    contour = wkt.loads(
        "Polygon ((37.63215 55.75588, 37.63214 55.75557, 37.63271 55.75570, 37.63215 55.75588))"
    )
    features = api.search_zu_in_contour(contour)
    assert features is None


def test_search_zu_at_coords(api: Nspd):
    features = api.search_zu_at_coords(55.78729561, 37.54658156)
    assert features is None
    features = api.search_zu_at_coords(55.787139958, 37.546440653)
    assert features is not None and len(features) == 1
    assert features[0].properties.options.cad_num == "77:09:0005008:11446"


def test_search_oks_at_point(api: Nspd):
    features = api.search_oks_at_coords(55.786436698, 37.547790951)
    assert features is None
    features = api.search_oks_at_coords(55.786436698, 37.547785813)
    assert features is not None and len(features) == 1
    assert features[0].properties.options.cad_num == "77:09:0005014:1044"


def test_search_wrong_result(api: Nspd):
    features = api.search("77:1:3033:1031")
    assert features is not None
    feat = api.find("77:1:3033:1031")
    assert feat is None


def test_cache_client(cache_api: Nspd):
    req = partial(
        cache_api.request,
        "get",
        "/api/geoportal/v2/search/geoportal",
        params={
            "query": "77:02:0021001:5304",
            "thematicSearchId": 1,
        },
    )
    r = req()
    if not r.extensions.get("from_cache", False):
        r = req()
    assert r.extensions["from_cache"]
