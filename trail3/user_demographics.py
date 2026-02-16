import random


def get_user_types(premises: int, build_type: str = "Urban", city: str = ""):
    """
    Calculate user types and their distribution based on premises count and location type.
    
    Args:
        premises: Number of premises in the area
        build_type: Type of build (Urban, Semi-Urban, Rural)
        city: City name (optional)
    
    Returns:
        Dictionary containing user types with their counts and percentages
    """
    
    # Define user types with their base percentages based on build type
    user_types_config = {
        "Network Users": {
            "Urban": 15,
            "Semi-Urban": 10,
            "Rural": 5
        },
        "Residential Users": {
            "Urban": 50,
            "Semi-Urban": 60,
            "Rural": 70
        },
        "Business Users": {
            "Urban": 20,
            "Semi-Urban": 15,
            "Rural": 10
        },
        "Enterprise Users": {
            "Urban": 10,
            "Semi-Urban": 8,
            "Rural": 5
        },
        "Government Users": {
            "Urban": 5,
            "Semi-Urban": 7,
            "Rural": 10
        }
    }
    
    # Get base percentages for the build type
    build_type_key = build_type if build_type in ["Urban", "Semi-Urban", "Rural"] else "Urban"
    
    user_types = {}
    
    for user_type, percentages in user_types_config.items():
        base_percentage = percentages.get(build_type_key, 15)
        # Add some randomness to make it more realistic
        variance = random.uniform(-5, 5)
        percentage = max(5, min(95, base_percentage + variance))
        
        count = int(premises * (percentage / 100))
        user_types[user_type] = {
            "count": count,
            "percentage": round(percentage, 1)
        }
    
    return user_types


def get_network_user_details(premises: int, build_type: str = "Urban"):
    """
    Get detailed network user information.
    
    Args:
        premises: Number of premises
        build_type: Type of build
    
    Returns:
        Dictionary with network user breakdown
    """
    
    # Network users are those who need fiber network infrastructure
    network_users_count = int(premises * 0.15)  # 15% base
    
    # Calculate network infrastructure requirements
    network_details = {
        "total_network_users": network_users_count,
        "fiber_ready": int(network_users_count * 0.7),
        "copper_network": int(network_users_count * 0.2),
        "wireless_backup": int(network_users_count * 0.1),
        "ont_required": int(network_users_count * 0.85),  # Optical Network Terminal
        "splitters_required": max(1, int(network_users_count / 32)),  # Fiber splitters
    }
    
    return network_details


def calculate_user_growth(user_types: dict, years: int = 5):
    """
    Calculate projected user growth over time.
    
    Args:
        user_types: Dictionary of user types with counts
        years: Number of years to project
    
    Returns:
        List of yearly projections
    """
    
    projections = []
    
    for year in range(1, years + 1):
        growth_factor = 1 + (0.1 * year)  # 10% annual growth
        yearly_data = {}
        
        for user_type, data in user_types.items():
            yearly_data[user_type] = {
                "count": int(data["count"] * growth_factor),
                "percentage": data["percentage"]
            }
        
        projections.append({
            "year": year,
            "users": yearly_data,
            "total": sum(d["count"] for d in yearly_data.values())
        })
    
    return projections
