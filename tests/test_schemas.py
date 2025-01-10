from pynspd import Nspd
from pynspd.schemas import Layer36049Feature


def test_feature_cast():
    with Nspd() as api:
        feat = api.search_by_theme("77:01:0001044:1033")
        assert feat is not None
        cf = feat.cast()
        assert isinstance(cf, Layer36049Feature)
        assert cf == api.search_oks("77:01:0001044:1033")
        assert len(cf.properties.options.model_dump_human_readable()) > 0
