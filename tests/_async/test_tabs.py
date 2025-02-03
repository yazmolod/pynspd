import pytest
import pytest_asyncio

from pynspd import AsyncNspd, NspdFeature


async def get_feat(api: AsyncNspd, cn: str) -> NspdFeature:
    feat = await api.search_by_theme(cn)
    assert feat is not None
    return feat


@pytest_asyncio.fixture(scope="session")
async def api():
    async with AsyncNspd(timeout=None) as client:
        yield client


@pytest.mark.asyncio(scope="session")
async def test_tab_land_parts(api: AsyncNspd):
    feat = await get_feat(api, "50:27:0000000:134535")
    res = await api.tab_land_parts(feat)
    assert res is not None
    assert len(res) == 15


@pytest.mark.asyncio(scope="session")
async def test_tab_land_links(api: AsyncNspd):
    feat = await get_feat(api, "77:01:0001001:1024")
    res = await api.tab_land_links(feat)
    assert res == ["77:01:0001001:1001", "77:01:0001001:1514", "77:01:0001001:1829"]


@pytest.mark.asyncio(scope="session")
async def test_tab_permission_type(api: AsyncNspd):
    feat = await get_feat(api, "50:27:0000000:134535")
    res = await api.tab_permission_type(feat)
    assert res is not None
    assert len(res) == 1
    assert res[0].startswith("заготовка древесины;")


@pytest.mark.asyncio(scope="session")
async def test_tab_build_parts(api: AsyncNspd):
    feat = await get_feat(api, "77:01:0001001:1024")
    res = await api.tab_build_parts(feat)
    assert res == ["77:01:0001001:1024/1"]


@pytest.mark.asyncio(scope="session")
async def test_tab_objects_list(api: AsyncNspd):
    feat = await get_feat(api, "77:01:0001001:1024")
    res = await api.tab_objects_list(feat)
    assert res is not None
    assert len(res) == 4
    assert res["Помещения (количество)"] == ["26"]


@pytest.mark.asyncio(scope="session")
async def test_tab_composition_land(api: AsyncNspd):
    feat = await get_feat(api, "48:06:0000000:111")
    assert feat.properties.options.no_coords
    res = await api.tab_composition_land(feat)
    assert res == [
        "48:06:1620101:209",
        "48:06:1620101:210",
        "48:06:1630501:28",
        "48:06:1630501:29",
    ]


@pytest.mark.asyncio(scope="session")
async def test_unsuitable_feat(api: AsyncNspd):
    feat = await get_feat(api, "50:27:0000000:134535")
    res = await api.tab_build_parts(feat)
    assert res is None


@pytest.mark.asyncio(scope="session")
async def test_empty_tab(api: AsyncNspd):
    feat = await get_feat(api, "50:27:0000000:134535")
    res = await api.tab_composition_land(feat)
    assert res is None
