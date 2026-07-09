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
            "pollutants": [
                {"name": "pm25_ugm3", "value": random.uniform(0, 100), "last_updated": time.time()},
                {"name": "co_ppm", "value": random.uniform(0, 100), "last_updated": time.time()},
                {"name": "no2_ppm", "value": random.uniform(0, 100), "last_updated": time.time()},
                {"name": "temp_c", "value": random.uniform(-10, 40), "last_updated": time.time()},
                {"name": "humidity_pct", "value": random.uniform(0, 100), "last_updated": time.time()},
                {"name": "aqi", "value": random.uniform(0, 500), "last_updated": time.time()},
            ],
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

dashboard_manager = DashboardManager()