import folium

def create_map(lat, lon, zones):
    m = folium.Map(location=[lat, lon], zoom_start=14)

    # Main site marker
    folium.Marker(
        [lat, lon],
        popup="FTTP Deployment Site",
        icon=folium.Icon(color="blue")
    ).add_to(m)

    # No-signal zones (Red circles)
    for zone in zones:
        folium.Circle(
            location=[zone["lat"], zone["lon"]],
            radius=zone["radius"],
            color="red",
            fill=True,
            fill_opacity=0.4
        ).add_to(m)

    return m
