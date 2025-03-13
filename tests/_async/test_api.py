from functools import partial

import pytest
from shapely import wkt
from shapely.geometry import MultiPolygon, Polygon

from pynspd import AsyncNspd, NspdFeature
from pynspd.errors import TooBigContour
from pynspd.schemas import Layer36048Feature, Layer36049Feature, Layer37578Feature


@pytest.mark.asyncio(scope="session")
async def test_find(async_api: AsyncNspd):
    feat = await async_api.find("77:02:0021001:5304")
    assert feat is not None
    assert feat.properties.options.model_dump()["type"] == "Машино-место"


@pytest.mark.asyncio(scope="session")
async def test_find_non_exists(async_api: AsyncNspd):
    feat = await async_api.find("77:02:0021001:5304111111")
    assert feat is None


@pytest.mark.asyncio(scope="session")
async def test_find_in_layer(async_api: AsyncNspd):
    lf_def = NspdFeature.by_title("ЗОУИТ объектов энергетики, связи, транспорта")
    assert lf_def == Layer37578Feature
    feat = await async_api.find_in_layer("Останкинская телебашня", lf_def)
    assert isinstance(feat, lf_def)
    assert len(feat.properties.options.model_dump_human_readable()) > 0


@pytest.mark.asyncio(scope="session")
async def test_find_in_layer_non_exists(async_api: AsyncNspd):
    feat = await async_api.find_in_layer("77:02:0021001:5304111111", Layer36048Feature)
    assert feat is None


@pytest.mark.asyncio(scope="session")
async def test_search_landplots(async_api: AsyncNspd):
    feat = await async_api.find_landplot("77:05:0001005:19")
    assert feat is not None
    assert feat.properties.options.land_record_type == "Земельный участок"
    assert isinstance(feat.geometry.to_shape(), Polygon)
    assert isinstance(feat.geometry.to_multi_shape(), MultiPolygon)


@pytest.mark.asyncio(scope="session")
async def test_search_buildings(async_api: AsyncNspd):
    feat = await async_api.find_building("77:03:0001001:3030")
    assert feat is not None
    assert feat.properties.options.build_record_type_value == "Здание"
    assert isinstance(feat.geometry.to_shape(), Polygon)


@pytest.mark.asyncio(scope="session")
async def test_search_landplots_in_contour(async_api: AsyncNspd):
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = await async_api.search_landplots_in_contour(contour)
    assert features is not None
    assert all([isinstance(i, Layer36048Feature) for i in features])
    cns = [i.properties.options.cad_num for i in features]
    assert set(["77:01:0001011:8", "77:01:0001011:14", "77:01:0001011:16"]) == set(cns)


@pytest.mark.asyncio(scope="session")
async def test_search_buildings_in_contour(async_api: AsyncNspd):
    contour = wkt.loads(
        "Polygon ((37.62381 55.75345, 37.62577 55.75390, 37.62448 55.75278, 37.62381 55.75345))"
    )
    features = await async_api.search_buildings_in_contour(contour)
    assert features is not None
    assert all([isinstance(i, Layer36049Feature) for i in features])
    cns = [i.properties.options.cad_num for i in features]
    assert set(["77:01:0001011:1164", "77:01:0001011:1002"]) == set(cns)


@pytest.mark.asyncio(scope="session")
async def test_search_in_big_contour(async_cache_api: AsyncNspd):
    with pytest.raises(TooBigContour):
        contour = wkt.loads(
            "Polygon ((37.6951 55.7320, 37.7338 55.7279, 37.7469 55.7563, 37.7283 55.7531, 37.7196 55.7343, 37.6981 55.7359, 37.6951 55.7320))"
        )
        await async_cache_api.search_landplots_in_contour(contour)
    async for oks_feat in async_cache_api.search_buildings_in_contour_iter(contour):
        assert oks_feat is not None
        break
    feats_all = [
        f async for f in async_cache_api.search_landplots_in_contour_iter(contour)
    ]
    feats_int = [
        f
        async for f in async_cache_api.search_landplots_in_contour_iter(
            contour, only_intersects=True
        )
    ]
    assert len(feats_all) > len(feats_int)


@pytest.mark.asyncio(scope="session")
async def test_search_in_contour_empty(async_api: AsyncNspd):
    contour = wkt.loads(
        "Polygon ((37.63215 55.75588, 37.63214 55.75557, 37.63271 55.75570, 37.63215 55.75588))"
    )
    features = await async_api.search_landplots_in_contour(contour)
    assert features is None


@pytest.mark.asyncio(scope="session")
async def test_search_landplots_at_coords(async_api: AsyncNspd):
    features = await async_api.search_landplots_at_coords(55.78729561, 37.54658156)
    assert features is None
    features = await async_api.search_landplots_at_coords(55.787139958, 37.546440653)
    assert features is not None and len(features) == 1
    assert features[0].properties.options.cad_num == "77:09:0005008:11446"


@pytest.mark.asyncio(scope="session")
async def test_search_buildings_at_point(async_api: AsyncNspd):
    features = await async_api.search_buildings_at_coords(55.786436698, 37.547790951)
    assert features is None
    features = await async_api.search_buildings_at_coords(55.786436698, 37.547785813)
    assert features is not None and len(features) == 1
    assert features[0].properties.options.cad_num == "77:09:0005014:1044"


@pytest.mark.asyncio(scope="session")
async def test_search_wrong_result(async_api: AsyncNspd):
    features = await async_api.search("77:1:3033:1031")
    assert features is not None
    feat = await async_api.find("77:1:3033:1031")
    assert feat is None


@pytest.mark.asyncio(scope="session")
async def test_cache_client(async_cache_api: AsyncNspd):
    req = partial(
        async_cache_api.request,
        "get",
        "/async_api/geoportal/v2/search/geoportal",
        params={
            "query": "77:02:0021001:5304",
            "thematicSearchId": 1,
        },
    )
    r = await req()
    if not r.extensions.get("from_cache", False):
        r = await req()
    assert r.extensions["from_cache"]
