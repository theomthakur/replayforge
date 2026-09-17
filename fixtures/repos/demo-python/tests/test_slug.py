from shop.slug import slugify


def test_simple_title():
    assert slugify("Blue Mug") == "blue-mug"


def test_collapses_punctuation_and_spaces():
    assert slugify("  Tea -- Pot, Large!  ") == "tea-pot-large"


def test_keeps_digits():
    assert slugify("Pack of 12") == "pack-of-12"
