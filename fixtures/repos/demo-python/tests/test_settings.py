from shop.settings import load_settings


def test_settings_have_region():
    settings = load_settings()
    assert settings["region"] == "us-east"
