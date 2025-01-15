import pytest
import pytest_asyncio
from shapely import wkt
from shapely.geometry import MultiPolygon, Point, Polygon

from pynspd import AsyncNspd, NspdFeature
from pynspd.errors import TooBigContour
from pynspd.schemas import Layer36048Feature, Layer36049Feature, Layer37578Feature


@pytest_asyncio.fixture(scope="session")
async def api():
    async with AsyncNspd(timeout=None) as client:
        yield client


@pytest.mark.asyncio(scope="session")
async def test_search_by_theme(api: AsyncNspd):
    feat = await api.search_by_theme("77:02:0021001:5304")
    assert feat is not None
    assert feat.properties.options.model_dump()["type"] == "Машино-место"


@pytest.mark.asyncio(scope="session")
async def test_search_by_model(api: AsyncNspd):
    lf_def = NspdFeature.by_title("ЗОУИТ объектов энергетики, связи, транспорта")
    assert lf_def == Layer37578Feature
    feat = await api.search_by_model("Останкинская телебашня", lf_def)
    assert isinstance(feat, lf_def)
    assert len(feat.properties.options.model_dump_human_readable()) > 0


@pytest.mark.asyncio(scope="session")
async def test_search_zu(api: AsyncNspd):
    feat = await api.search_zu("77:05:0001005:19")
    assert feat is not None
    assert feat.properties.options.land_record_type == "Земельный участок"
    assert isinstance(feat.geometry.to_shape(), Polygon)
    assert isinstance(feat.geometry.to_multi_shape(), MultiPolygon)


@pytest.mark.asyncio(scope="session")
async def test_search_many_zu(api: AsyncNspd):
    features = await api.search_many_zu(
        "77:03:0001001:82 77:03:0001001:26 77:03:0001001:132"
    )
    assert len(features) == 3
    assert all([i is not None for i in features])


@pytest.mark.asyncio(scope="session")
async def test_search_oks(api: AsyncNspd):
    feat = await api.search_oks("77:03:0001001:3030")
    assert feat is not None
    assert feat.properties.options.build_record_type_value == "Здание"
    assert isinstance(feat.geometry.to_shape(), Polygon)


@pytest.mark.asyncio(scope="session")
async def test_search_many_oks(api: AsyncNspd):
    features = await api.search_many_oks(
        "77:03:0001001:3030 77:03:0001001:1111 77:03:0001001:1112"
    )
    assert len(features) == 3
    assert all([i is not None for i in features])


@pytest.mark.asyncio(scope="session")
async def test_search_zu_in_contour(api: AsyncNspd):
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = await api.search_zu_in_contour(contour)
    assert features is not None
    assert all([isinstance(i, Layer36048Feature) for i in features])
    cns = [i.properties.options.cad_num for i in features]
    assert set(["77:01:0001011:8", "77:01:0001011:14", "77:01:0001011:16"]) == set(cns)


@pytest.mark.asyncio(scope="session")
async def test_search_oks_in_contour(api: AsyncNspd):
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = await api.search_oks_in_contour(contour)
    assert features is not None
    assert all([isinstance(i, Layer36049Feature) for i in features])
    cns = [i.properties.options.cad_num for i in features]
    assert set(["77:01:0001011:1164", "77:01:0001011:1002"]) == set(cns)


@pytest.mark.asyncio(scope="session")
async def test_search_too_big_contour(api: AsyncNspd):
    with pytest.raises(TooBigContour):
        contour = wkt.loads(
            "Polygon ((37.5658 55.8198, 37.5267 55.7710, 37.6214 55.8033, 37.5658 55.8198))"
        )
        await api.search_zu_in_contour(contour)


@pytest.mark.asyncio(scope="session")
async def test_search_in_contour_empty(api: AsyncNspd):
    contour = wkt.loads(
        "Polygon ((37.63215 55.75588, 37.63214 55.75557, 37.63271 55.75570, 37.63215 55.75588))"
    )
    features = await api.search_zu_in_contour(contour)
    assert features is None


@pytest.mark.asyncio(scope="session")
async def test_search_zu_at_point(api: AsyncNspd):
    features = await api.search_zu_at_point(Point(37.54658156, 55.78729561))
    assert features is None
    features = await api.search_zu_at_point(Point(37.546440653, 55.787139958))
    assert features is not None and len(features) == 1
    assert features[0].properties.options.cad_num == "77:09:0005008:11446"


@pytest.mark.asyncio(scope="session")
async def test_search_oks_at_point(api: AsyncNspd):
    features = await api.search_oks_at_point(Point(37.547790951, 55.786436698))
    assert features is None
    features = await api.search_oks_at_point(Point(37.547785813, 55.786436698))
    assert features is not None and len(features) == 1
    assert features[0].properties.options.cad_num == "77:09:0005014:1044"


@pytest.mark.asyncio(scope="session")
async def test_search_with_two_features(api: AsyncNspd):
    resp = await api._search({"query": "77:1:3033:1031", "thematicSearchId": 1})
    assert resp is not None and resp.data is not None
    features = resp.data.features
    assert len(features) > 1

    feat = await api._search_one({"query": "77:1:3033:1031", "thematicSearchId": 1})
    assert feat is None
