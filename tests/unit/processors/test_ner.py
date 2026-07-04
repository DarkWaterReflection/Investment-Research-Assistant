import pytest

from processors.ner import ExtractedEntities, MoneyMention, extract_entities


def test_dollar_shorthand_millions():
    money = extract_entities("Acme raised a $40M Series B.").money
    assert len(money) == 1
    assert money[0].amount == pytest.approx(40_000_000)
    assert money[0].currency == "USD"
    assert money[0].raw == "$40M"


def test_currency_code_with_word_multiplier():
    money = extract_entities("The round totaled USD 1.2 billion.").money
    assert money[0].amount == pytest.approx(1_200_000_000)
    assert money[0].currency == "USD"


def test_euro_thousands():
    money = extract_entities("It cost €500k to build the prototype.").money
    assert money[0].amount == pytest.approx(500_000)
    assert money[0].currency == "EUR"


def test_pound_with_grouped_digits():
    money = extract_entities("Revenue reached £2,500,000 in 2023.").money
    assert money[0].amount == pytest.approx(2_500_000)
    assert money[0].currency == "GBP"


def test_no_money_in_plain_text():
    assert extract_entities("There is nothing monetary here.").money == []


def test_iso_date_extracted():
    assert extract_entities("Announced on 2024-03-15 to press.").dates == ["2024-03-15"]


def test_multiple_date_formats_normalized_to_iso():
    dates = extract_entities("Signed March 15, 2024 and closed 3/20/2024.").dates
    assert dates == ["2024-03-15", "2024-03-20"]


def test_invalid_date_is_dropped():
    # Month 13 is not a real date and must not be emitted.
    assert extract_entities("The code 2024-13-40 is not a date.").dates == []


def test_org_suffix_detection():
    orgs = extract_entities("Foo Ventures and Bar Capital co-led the round.").orgs
    assert "Foo Ventures" in orgs
    assert "Bar Capital" in orgs


def test_people_extracted_from_title_prefix():
    people = extract_entities("CEO Mary Johnson addressed the shareholders.").people
    assert "Mary Johnson" in people


def test_empty_text_yields_empty_entities():
    assert extract_entities("") == ExtractedEntities()


def test_money_mention_shape():
    mention = extract_entities("A $5M seed round.").money[0]
    assert isinstance(mention, MoneyMention)
    assert set(mention.model_dump()) == {"amount", "currency", "raw"}
