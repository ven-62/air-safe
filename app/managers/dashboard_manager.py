from typing import Dict, List
import random
import time

class DashboardManager:
    async def get_pollutant_data(self, station_id: str) -> Dict[str, any]:
        """
        Retrieve pollutant data for a specific station.
        Temporarily returns placeholder data; replace with actual data retrieval logic.
        /monitor/read/{station_id}
        """

        return {
            "station_id": station_id,
            "timestamp": time.time(),
            "status": random.choice(["Good", "Moderate", "Unhealthy for Sensitive Groups", "Unhealthy", "Very Unhealthy", "Hazardous"]),
            "components": [
                {"name": "pm25_ugm3", "value": round(random.uniform(0, 100), 2)},
                {"name": "co_ugm3", "value": round(random.uniform(0, 100), 2)},
                {"name": "no2_ugm3", "value": round(random.uniform(0, 100), 2)},
                {"name": "temp_c", "value": round(random.uniform(-10, 40), 2)},
                {"name": "humidity_pct", "value": round(random.uniform(0, 100), 2)},
                {"name": "aqi", "value": round(random.uniform(0, 500), 2)},
            ],
        }
    
    async def get_forecast_data(self, station_id: str) -> Dict[str, any]:
        """
        Retrieve forecast data for a specific station.
        Temporarily returns placeholder data; replace with actual data retrieval logic.
        from monitor/forecast/{station_id}
        """
        return {
            "station_id": station_id,
            "forecast": {
                "next_first_hour": [
                    {"name": "pm25_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "co_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "no2_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "temp_c", "value": round(random.uniform(-10, 40), 2)},
                    {"name": "humidity_pct", "value": round(random.uniform(0, 100), 2)},
                    {"name": "aqi", "value": round(random.uniform(0, 500), 2)},
                ],
                "next_second_hour": [
                    {"name": "pm25_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "co_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "no2_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "temp_c", "value": round(random.uniform(-10, 40), 2)},
                    {"name": "humidity_pct", "value": round(random.uniform(0, 100), 2)},
                    {"name": "aqi", "value": round(random.uniform(0, 500), 2)},
                ],
                "next_third_hour": [
                    {"name": "pm25_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "co_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "no2_ugm3", "value": round(random.uniform(0, 100), 2)},
                    {"name": "temp_c", "value": round(random.uniform(-10, 40), 2)},
                    {"name": "humidity_pct", "value": round(random.uniform(0, 100), 2)},
                    {"name": "aqi", "value": round(random.uniform(0, 500), 2)},
                ],
            }
        }

    def get_all_stations(self) -> List[Dict[str, any]]:
        """
        Retrieve a list of all stations.
        Temporarily returns placeholder data; replace with actual data retrieval logic.
        from monitor/stations
        """
        return [
            {"station_id": "1", "name": "Plaza Rizal", "city": "Naga City, Camarines Sur", "latitude": 13.6218, "longitude": 123.1948},
            {"station_id": "2", "name": "Naga City People's Mall", "city": "Naga City, Camarines Sur", "latitude": 13.6258, "longitude": 123.1857},
        ]

    async def get_latest_history(self, station_id: str) -> List[Dict[str, any]]:
        """
        Retrieve the latest history data for a specific station.
        Temporarily returns placeholder data; replace with actual data retrieval logic.
        from monitor/history/{station_id}
        """
        return [
            {
                "timestamp": time.time() - 3600 * i,
                "pm25_ugm3": round(random.uniform(0, 100), 2),
                "co_ugm3": round(random.uniform(0, 100), 2),
                "no2_ugm3": round(random.uniform(0, 100), 2),
                "temp_c": round(random.uniform(-10, 40), 2),
                "humidity_pct": round(random.uniform(0, 100), 2),
                "aqi": round(random.uniform(0, 500), 2),
            }
            for i in range(24)  # Last 24 hours
        ]
    
dashboard_manager = DashboardManager()
