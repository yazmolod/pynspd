import shutil
from functools import partial
from pathlib import Path

import pytest
from hishel import FileStorage
from shapely import wkt
from shapely.geometry import MultiPolygon, Point, Polygon

from pynspd import Nspd, NspdFeature
from pynspd.errors import TooBigContour
from pynspd.schemas import Layer36048Feature, Layer36049Feature, Layer37578Feature


@pytest.fixture(scope="session")
def api():
    with Nspd(timeout=None) as client:
        yield client


def test_search_by_theme(api: Nspd):
    feat = api.search_by_theme("77:02:0021001:5304")
    assert feat is not None
    assert feat.properties.options.model_dump()["type"] == "Машино-место"


def test_search_by_theme_non_exists(api: Nspd):
    feat = api.search_by_theme("77:02:0021001:5304111111")
    assert feat is None


def test_search_by_model(api: Nspd):
    lf_def = NspdFeature.by_title("ЗОУИТ объектов энергетики, связи, транспорта")
    assert lf_def == Layer37578Feature
    feat = api.search_by_model("Останкинская телебашня", lf_def)
    assert isinstance(feat, lf_def)
    assert len(feat.properties.options.model_dump_human_readable()) > 0


def test_search_by_model_non_exists(api: Nspd):
    feat = api.search_by_model("77:02:0021001:5304111111", Layer36048Feature)
    assert feat is None


def test_search_zu(api: Nspd):
    feat = api.search_zu("77:05:0001005:19")
    assert feat is not None
    assert feat.properties.options.land_record_type == "Земельный участок"
    assert isinstance(feat.geometry.to_shape(), Polygon)
    assert isinstance(feat.geometry.to_multi_shape(), MultiPolygon)


def test_search_many_zu(api: Nspd):
    features = api.search_many_zu("77:03:0001001:82 77:03:0001001:26 77:03:0001001:132")
    assert len(features) == 3
    assert all([i is not None for i in features])


def test_search_oks(api: Nspd):
    feat = api.search_oks("77:03:0001001:3030")
    assert feat is not None
    assert feat.properties.options.build_record_type_value == "Здание"
    assert isinstance(feat.geometry.to_shape(), Polygon)


def test_search_many_oks(api: Nspd):
    features = api.search_many_oks(
        "77:03:0001001:3030 77:03:0001001:1111 77:03:0001001:1112"
    )
    assert len(features) == 3
    assert all([i is not None for i in features])


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


def test_search_too_big_contour(api: Nspd):
    with pytest.raises(TooBigContour):
        contour = wkt.loads(
            "Polygon ((37.5658 55.8198, 37.5267 55.7710, 37.6214 55.8033, 37.5658 55.8198))"
        )
        api.search_zu_in_contour(contour)


def test_search_in_contour_empty(api: Nspd):
    contour = wkt.loads(
        "Polygon ((37.63215 55.75588, 37.63214 55.75557, 37.63271 55.75570, 37.63215 55.75588))"
    )
    features = api.search_zu_in_contour(contour)
    assert features is None


def test_search_zu_at_point(api: Nspd):
    features = api.search_zu_at_point(Point(37.54658156, 55.78729561))
    assert features is None
    features = api.search_zu_at_point(Point(37.546440653, 55.787139958))
    assert features is not None and len(features) == 1
    assert features[0].properties.options.cad_num == "77:09:0005008:11446"


def test_search_oks_at_point(api: Nspd):
    features = api.search_oks_at_point(Point(37.547790951, 55.786436698))
    assert features is None
    features = api.search_oks_at_point(Point(37.547785813, 55.786436698))
    assert features is not None and len(features) == 1
    assert features[0].properties.options.cad_num == "77:09:0005014:1044"


def test_search_with_two_features(api: Nspd):
    resp = api._search({"query": "77:1:3033:1031", "thematicSearchId": 1})
    assert resp is not None and resp.data is not None
    features = resp.data.features
    assert len(features) > 1

    feat = api._search_one({"query": "77:1:3033:1031", "thematicSearchId": 1})
    assert feat is None


def test_cache_client():
    cache_folder = Path.cwd() / ".cache/hishel"
    if cache_folder.exists():
        shutil.rmtree(cache_folder)
    with Nspd(cache_storage=FileStorage(base_path=cache_folder, ttl=10)) as nspd:
        req = partial(
            nspd.request,
            "get",
            "/api/geoportal/v2/search/geoportal",
            params={
                "query": "77:02:0021001:5304",
                "thematicSearchId": 1,
            },
        )
        r = req()
        assert not r.extensions["from_cache"]
        t1 = r.elapsed
        r = req()
        assert r.extensions["from_cache"]
        t2 = r.elapsed
        assert t2 < t1
