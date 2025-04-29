import pytest

from pynspd import AsyncNspd, NspdFeature


async def get_feat(async_api: AsyncNspd, cn: str) -> NspdFeature:
    feat = await async_api.find(cn)
    assert feat is not None
    return feat


@pytest.mark.asyncio(scope="session")
async def test_tab_land_parts(async_api: AsyncNspd):
    feat = await get_feat(async_api, "50:27:0000000:134535")
    res = await async_api.get_tab_data(feat, "Части ЗУ")
    assert res is not None
    assert len(res) > 10


@pytest.mark.asyncio(scope="session")
async def test_tab_land_links(async_api: AsyncNspd):
    feat = await get_feat(async_api, "77:01:0001001:1024")
    res = await async_api.get_tab_data(feat, "Связанные ЗУ")
    assert res == ["77:01:0001001:1001", "77:01:0001001:1514", "77:01:0001001:1829"]


@pytest.mark.asyncio(scope="session")
async def test_tab_permission_type(async_api: AsyncNspd):
    feat = await get_feat(async_api, "50:27:0000000:134535")
    res = await async_api.get_tab_data(feat, "Виды разрешенного использования")
    assert res is not None
    assert len(res) == 1
    assert res[0].startswith("заготовка древесины;")


@pytest.mark.asyncio(scope="session")
async def test_tab_build_parts(async_api: AsyncNspd):
    feat = await get_feat(async_api, "77:01:0001001:1024")
    res = await async_api.get_tab_data(feat, "Части ОКС")
    assert res == ["77:01:0001001:1024/1"]


@pytest.mark.asyncio(scope="session")
async def test_tab_objects_list(async_api: AsyncNspd):
    feat = await get_feat(async_api, "77:01:0001001:1024")
    res = await async_api.get_tab_data(feat, "Объекты")
    assert res is not None
    assert len(res) == 4
    assert res["Помещения (количество)"] == ["26"]


@pytest.mark.asyncio(scope="session")
async def test_tab_composition_land(async_api: AsyncNspd):
    feat = await get_feat(async_api, "48:06:0000000:111")
    assert feat.properties.options.no_coords
    res = await async_api.get_tab_data(feat, "Состав ЕЗП")
    assert res == [
        "48:06:1620101:209",
        "48:06:1620101:210",
        "48:06:1630501:28",
        "48:06:1630501:29",
    ]


@pytest.mark.asyncio(scope="session")
async def test_unsuitable_feat(async_api: AsyncNspd):
    feat = await get_feat(async_api, "50:27:0000000:134535")
    res = await async_api.tab_build_parts(feat)
    assert res is None


@pytest.mark.asyncio(scope="session")
async def test_empty_tab(async_api: AsyncNspd):
    feat = await get_feat(async_api, "50:27:0000000:134535")
    res = await async_api.tab_composition_land(feat)
    assert res is None


@pytest.mark.asyncio(scope="session")
async def test_tab_objects_key_format(async_api: AsyncNspd):
    feat = await get_feat(async_api, "50:21:0110501:792")
    res = await async_api.tab_objects_list(feat)
    assert res is not None
    assert "Объект недвижимости" in res
