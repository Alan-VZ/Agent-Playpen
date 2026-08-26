import requests
from tools.base_tool import BaseTool


class WeatherTool(BaseTool):
    """Fetches current weather for a given city using Open-Meteo."""

    name = "weather"
    description = "Get current temperature and conditions for a city."
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, e.g. 'London'",
            },
            "country_code": {
                "type": "string",
                "description": "ISO 3166-1 alpha-2 country code, e.g. 'GB'",
            },
        },
        "required": ["city"],
    }

    def run(self, **kwargs) -> str:
        city = kwargs["city"]
        country_code = kwargs.get("country_code", "")
        # Step 1: Geocode the city to lat/lon
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_params = {"name": city, "count": 1, "language": "en", "format": "json"}
        if country_code:
            geo_params["country"] = country_code
        geo = requests.get(geo_url, params=geo_params, timeout=10).json()

        if not geo.get("results"):
            return f"City '{city}' not found."

        lat = geo["results"][0]["latitude"]
        lon = geo["results"][0]["longitude"]

        # Step 2: Fetch weather
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
        }
        weather = requests.get(weather_url, params=weather_params, timeout=10).json()
        cw = weather.get("current_weather", {})
        return (
            f"Weather in {city}: {cw.get('temperature')}C, "
            f"wind {cw.get('windspeed')} km/h, "
            f"code {cw.get('weathercode')}"
        )
        