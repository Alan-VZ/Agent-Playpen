# Writing a Custom Tool — Example: WeatherTool

1. Create tools/packs/api/weather_tool.py
2. Subclass BaseTool and set name, description, and parameters
3. Implement run(**kwargs) -> str
4. Register in tools.yaml and in your runner
