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
                {"name": "pm25_ugm3", "value": round(random.uniform(0, 100), 2)},
                {"name": "co_ppm", "value": round(random.uniform(0, 100), 2)},
                {"name": "no2_ppm", "value": round(random.uniform(0, 100), 2)},
                {"name": "temp_c", "value": round(random.uniform(-10, 40), 2)},
                {"name": "humidity_pct", "value": round(random.uniform(0, 100), 2)},
                {"name": "aqi", "value": round(random.uniform(0, 500), 2)},
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
                    {"name": "pm25_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "co_ppm", "value": round(random.uniform(0, 100), 2)},
                    {"name": "no2_ppm", "value": round(random.uniform(0, 100), 2)},
                    {"name": "temp_c", "value": round(random.uniform(-10, 40), 2)},
                    {"name": "humidity_pct", "value": round(random.uniform(0, 100), 2)},
                    {"name": "aqi", "value": round(random.uniform(0, 500), 2)},
                ],
                "next_second_hour": [
                    {"name": "pm25_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "co_ppm", "value": round(random.uniform(0, 100), 2)},
                    {"name": "no2_ppm", "value": round(random.uniform(0, 100), 2)},
                    {"name": "temp_c", "value": round(random.uniform(-10, 40), 2)},
                    {"name": "humidity_pct", "value": round(random.uniform(0, 100), 2)},
                    {"name": "aqi", "value": round(random.uniform(0, 500), 2)},
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
