from geopy.geocoders import Nominatim

def get_location_info(latitude: float, longitude: float):
    """
    Get the city and place name for the given latitude and longitude.

    Args:
        latitude (float): The latitude of the location.
        longitude (float): The longitude of the location.
    """
    geolocator = Nominatim(user_agent="airsafe_app")
    location = geolocator.reverse((latitude, longitude), addressdetails=True, namedetails=True)

    if location:
        raw = location.raw
        addr = raw.get("address", {})
        city = (
            addr.get("city")
            or addr.get("municipality")
            or addr.get("town")
            or addr.get("village")
        )
        place_name = raw.get("name") or addr.get("park") or addr.get("building")

        return {
            "city": city,
            "place_name": place_name,
            "full_address": location.address,
        }
    else:
        return {
            "city": None,
            "place_name": None,
            "full_address": None,
        }