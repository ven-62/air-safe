from typing import Dict, List
import random
import time

class DashboardManager:
    async def get_pollutant_data(self, station_id: str) -> Dict[str, any]:
        """
        Retrieve pollutant data for a specific station.
        Temporarily returns placeholder data; replace with actual data retrieval logic.
        """

        return {
            "station_id": station_id,
            "timestamp": time.time(),
            "status": random.choice(["Good", "Moderate", "Unhealthy for Sensitive Groups", "Unhealthy", "Very Unhealthy", "Hazardous"]),
            "components": [
                {"name": "pm25_ugm3", "value": random.uniform(0, 100)},
                {"name": "co_ppm", "value": random.uniform(0, 100)},
                {"name": "no2_ppm", "value": random.uniform(0, 100)},
                {"name": "temp_c", "value": random.uniform(-10, 40)},
                {"name": "humidity_pct", "value": random.uniform(0, 100)},
                {"name": "aqi", "value": random.uniform(0, 500)},
            ],
        }
    
    async def get_forecast_data(self, station_id: str) -> Dict[str, any]:
        """
        Retrieve forecast data for a specific station.
        Temporarily returns placeholder data; replace with actual data retrieval logic.
        """
        return {
            "station_id": station_id,
            "forecast": {
                "next_first_hour": [
                    {"name": "pm25_ugm3", "value": random.uniform(0, 100)},
                    {"name": "co_ppm", "value": random.uniform(0, 100)},
                    {"name": "no2_ppm", "value": random.uniform(0, 100)},
                    {"name": "temp_c", "value": random.uniform(-10, 40)},
                    {"name": "humidity_pct", "value": random.uniform(0, 100)},
                    {"name": "aqi", "value": random.uniform(0, 500)},
                ],
                "next_second_hour": [
                    {"name": "pm25_ugm3", "value": random.uniform(0, 100)},
                    {"name": "co_ppm", "value": random.uniform(0, 100)},
                    {"name": "no2_ppm", "value": random.uniform(0, 100)},
                    {"name": "temp_c", "value": random.uniform(-10, 40)},
                    {"name": "humidity_pct", "value": random.uniform(0, 100)},
                    {"name": "aqi", "value": random.uniform(0, 500)},
                ],
                "next_third_hour": [
                    {"name": "pm25_ugm3", "value": random.uniform(0, 100)},
                    {"name": "co_ppm", "value": random.uniform(0, 100)},    
                    {"name": "no2_ppm", "value": random.uniform(0, 100)},
                    {"name": "temp_c", "value": random.uniform(-10, 40)},
                    {"name": "humidity_pct", "value": random.uniform(0, 100)},
                    {"name": "aqi", "value": random.uniform(0, 500)},
                ]
            }
        }

    def get_all_stations(self) -> List[Dict[str, any]]:
        """
        Retrieve a list of all stations.
        Temporarily returns placeholder data; replace with actual data retrieval logic.
        """
        return [
            {"station_id": "1", "name": "Plaza Rizal", "city": "Naga City, Camarines Sur", "latitude": 13.6218, "longitude": 123.1948},
            {"station_id": "2", "name": "Naga City People's Mall", "city": "Naga City, Camarines Sur", "latitude": 13.6258, "longitude": 123.1857},
        ]
    
dashboard_manager = DashboardManager()