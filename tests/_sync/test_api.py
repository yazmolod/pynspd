from shapely.geometry import MultiPolygon, Polygon

from pynspd import Nspd, NspdFeature
from pynspd.schemas import Layer37578Feature


def test_search_by_theme():
    with Nspd() as api:
        feat = api.search_by_theme("77:02:0021001:5304")
        assert feat.properties.options.type == "Машино-место"


def test_search_by_model():
    with Nspd() as api:
        lf_def = NspdFeature.by_title("ЗОУИТ объектов энергетики, связи, транспорта")
        assert lf_def == Layer37578Feature
        feat = api.search_by_model("Останкинская телебашня", lf_def)
        assert isinstance(feat, lf_def)
        assert len(feat.properties.options.model_dump_human_readable()) > 0


def test_search_zu():
    with Nspd() as api:
        feat = api.search_zu("77:05:0001005:19")
        assert feat.properties.options.land_record_type == "Земельный участок"
        assert isinstance(feat.geometry.to_shape(), Polygon)
        assert isinstance(feat.geometry.to_multi_shape(), MultiPolygon)


def test_search_many_zu():
    with Nspd() as api:
        features = api.search_many_zu(
            "77:03:0001001:82 77:03:0001001:26 77:03:0001001:132"
        )
        assert len(features) == 3
        assert all([i is not None for i in features])


def test_search_oks():
    with Nspd() as api:
        feat = api.search_oks("77:03:0001001:3030")
        assert feat.properties.options.build_record_type_value == "Здание"
        assert isinstance(feat.geometry.to_shape(), Polygon)


def test_search_many_oks():
    with Nspd() as api:
        features = api.search_many_oks(
            "77:03:0001001:3030 77:03:0001001:1111 77:03:0001001:1112"
        )
        assert len(features) == 3
        assert all([i is not None for i in features])
