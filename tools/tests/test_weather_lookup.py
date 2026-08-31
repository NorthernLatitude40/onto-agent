import pytest
from tool import weather_lookup


def test_returns_weather_for_known_city():
    assert weather_lookup("Taipei") == "28C, sunny"


def test_raises_for_unknown_city():
    with pytest.raises(ValueError):
        weather_lookup("Nowhere")