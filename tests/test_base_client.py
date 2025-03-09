from pynspd import Nspd


def test_more_than_one_request_filter(api: Nspd):
    """Когда на поисковой запрос выпадает больше одного объекта"""
    feat = api.find("77:04:0004018:3371")
    assert feat is not None


def test_iter_cn(api: Nspd):
    assert list(api.iter_cn("77:04:0004018:3371; 77:04:0004018:3372")) == [
        "77:04:0004018:3371",
        "77:04:0004018:3372",
    ]
