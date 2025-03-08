from pynspd import Nspd, NspdFeature


def get_feat(api: Nspd, cn: str) -> NspdFeature:
    feat = api.find(cn)
    assert feat is not None
    return feat


def test_tab_land_parts(api: Nspd):
    feat = get_feat(api, "50:27:0000000:134535")
    res = api.tab_land_parts(feat)
    assert res is not None
    assert len(res) > 10


def test_tab_land_links(api: Nspd):
    feat = get_feat(api, "77:01:0001001:1024")
    res = api.tab_land_links(feat)
    assert res == ["77:01:0001001:1001", "77:01:0001001:1514", "77:01:0001001:1829"]


def test_tab_permission_type(api: Nspd):
    feat = get_feat(api, "50:27:0000000:134535")
    res = api.tab_permission_type(feat)
    assert res is not None
    assert len(res) == 1
    assert res[0].startswith("заготовка древесины;")


def test_tab_build_parts(api: Nspd):
    feat = get_feat(api, "77:01:0001001:1024")
    res = api.tab_build_parts(feat)
    assert res == ["77:01:0001001:1024/1"]


def test_tab_objects_list(api: Nspd):
    feat = get_feat(api, "77:01:0001001:1024")
    res = api.tab_objects_list(feat)
    assert res is not None
    assert len(res) == 4
    assert res["Помещения (количество)"] == ["26"]


def test_tab_composition_land(api: Nspd):
    feat = get_feat(api, "48:06:0000000:111")
    assert feat.properties.options.no_coords
    res = api.tab_composition_land(feat)
    assert res == [
        "48:06:1620101:209",
        "48:06:1620101:210",
        "48:06:1630501:28",
        "48:06:1630501:29",
    ]


def test_unsuitable_feat(api: Nspd):
    feat = get_feat(api, "50:27:0000000:134535")
    res = api.tab_build_parts(feat)
    assert res is None


def test_empty_tab(api: Nspd):
    feat = get_feat(api, "50:27:0000000:134535")
    res = api.tab_composition_land(feat)
    assert res is None
