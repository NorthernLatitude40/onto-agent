def weather_lookup(city: str) -> str:
    fake_data = {"taipei": "28C, sunny", "osaka": "26C, cloudy"}
    key = city.lower()
    if key not in fake_data:
        raise ValueError(f"no data for {city}")
    return fake_data[key]