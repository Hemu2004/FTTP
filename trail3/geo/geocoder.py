from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

def get_coordinates_from_pincode(pincode: str):
    geolocator = Nominatim(user_agent="trail3_fttp_planner")
    location = geolocator.geocode(pincode)

    if location:
        return location.latitude, location.longitude

    return None, None


def get_location_details(postcode: str):
    """
    Get full location details from a postcode.
    Returns a dictionary with latitude, longitude, address, city, state, country.
    """
    geolocator = Nominatim(user_agent="trail3_fttp_planner")
    
    try:
        # Use rate limiter to avoid too many requests
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        location = geocode(postcode)
        
        if location:
            # Parse address components
            address_parts = location.raw.get('address', {})
            
            # Extract city, state, country
            city = address_parts.get('city') or address_parts.get('town') or address_parts.get('village') or address_parts.get('municipality') or postcode
            state = address_parts.get('state') or address_parts.get('county') or ''
            country = address_parts.get('country') or ''
            
            return {
                'latitude': location.latitude,
                'longitude': location.longitude,
                'address': location.address,
                'city': city,
                'state': state,
                'country': country,
                'raw': location.raw
            }
        else:
            return None
            
    except Exception as e:
        print(f"Error getting location details: {e}")
        return None
