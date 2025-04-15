import streamlit as st
from datetime import datetime, time as dtime
import requests
import base64
import json
import os
from dotenv import load_dotenv

# --- Configuration ---
# Replace with your actual credentials and API key values.
load_dotenv()

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ASTRONOMY_API_URL = 'https://api.astronomyapi.com/api/v2/studio/star-chart'

# New endpoints for planetary positions and moon phase
PLANETARY_POSITIONS_URL = "https://api.astronomyapi.com/api/v2/bodies/positions"
MOON_PHASE_URL = "https://api.astronomyapi.com/api/v2/studio/moon-phase"

# --- Functions for Google Places ---
def get_place_suggestions(api_key, user_input):
    """
    Fetch autocomplete suggestions from the Google Places Autocomplete API.
    Returns a list of dictionaries with 'description' and 'place_id'.
    """
    if not user_input:
        return []
    url = 'https://maps.googleapis.com/maps/api/place/autocomplete/json'
    params = {
        "input": user_input,
        "types": "geocode",
        "key": api_key
    }
    res = requests.get(url, params=params)
    suggestions = []
    if res.status_code == 200:
        data = res.json()
        if data.get("status") == "OK":
            for item in data["predictions"]:
                suggestions.append({
                    "description": item["description"],
                    "place_id": item["place_id"]
                })
    return suggestions

def get_place_details(api_key, place_id):
    """
    Fetch place details (latitude and longitude) using the Google Place Details API.
    """
    url = 'https://maps.googleapis.com/maps/api/place/details/json'
    params = {
        'place_id': place_id,
        'fields': 'geometry',
        'key': api_key
    }
    res = requests.get(url, params=params)
    if res.status_code == 200:
        data = res.json()
        if data.get('status') == 'OK':
            location = data['result']['geometry']['location']
            return location['lat'], location['lng']
        else:
            st.error(f"Place details error: {data.get('status')}")
    else:
        st.error(f"HTTP error: {res.status_code}")
    return None, None

# --- Basic Authentication Setup for AstronomyAPI ---
# According to the AstronomyAPI docs (see https://docs.astronomyapi.com/studio/star-chart/request),
# this endpoint uses Basic Auth. Credentials (APP_ID:APP_SECRET) are base64-encoded.
credentials = f"{APP_ID}:{APP_SECRET}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()
auth_headers = {
    "Authorization": f"Basic {encoded_credentials}",
    "Content-Type": "application/json"
}

# --- Streamlit App Setup ---
st.set_page_config(page_title="🌌 Constellation Viewer", layout="centered")
st.title("🔭 Constellation Viewer")

planet_position_tab ,star_charts_tab, moon_phase_tab = st.tabs(["Planetary Positions", "Star Charts", "Moon Phase"])

# ============================================================
# Tab 1: Planetary Positions
# ============================================================
with planet_position_tab:
    st.header("Planetary Positions")
    st.markdown(":green[Description]: Retrieve positions for all available celestial bodies for the given date range and observer's location. (Endpoint: GET /api/v2/bodies/positions)")
    
    col1, col2 = st.columns(2)
    with col1:
        pos_lat = st.number_input("Latitude", value=1.3521, key="pos_lat", format="%.4f")
    with col2:
        pos_lng = st.number_input("Longitude", value=103.8198, key="pos_lng", format="%.4f")
    pos_elevation = st.number_input("Elevation (m)", value=0, key="pos_elev")
    
    pos_from_date = st.date_input("From Date", value=datetime.today(), key="pos_from")
    pos_to_date = st.date_input("To Date", value=datetime.today(), key="pos_to")
    pos_time = st.time_input("Time", value=dtime(9, 0), key="pos_time")
    
    if st.button("Get Positions", key="pos_button"):
        # Format time as HH:MM:SS
        time_str = pos_time.strftime("%H:%M:%S")
        params = {
            "latitude": pos_lat,
            "longitude": pos_lng,
            "elevation": pos_elevation,
            "from_date": pos_from_date.strftime("%Y-%m-%d"),
            "to_date": pos_to_date.strftime("%Y-%m-%d"),
            "time": time_str,
            "output": "table"
        }
        st.info("Requesting planetary positions from AstronomyAPI...")
        try:
            pos_res = requests.get(PLANETARY_POSITIONS_URL, headers=auth_headers, params=params, timeout=120)
            pos_res.raise_for_status()
            pos_data = pos_res.json()
            # Display JSON data (you can format this into a table if desired)
            st.json(pos_data)
        except Exception as e:
            st.error(f"Error: {e}")

# ============================================================
# Tab 2: Star Charts 
# ============================================================
with star_charts_tab:
    st.header("Star Charts")
    st.markdown(":green[Description]: Generate a star map for a specific constellation based on your location and date.")

    # --- Session State Initialization for Location ---
    if "latitude" not in st.session_state:
        st.session_state.latitude = 0.0
    if "longitude" not in st.session_state:
        st.session_state.longitude = 0.0
    if "selected_place_id" not in st.session_state:
        st.session_state.selected_place_id = None

    # --- Location Form with Autocomplete ---
    with st.form("location_form", clear_on_submit=True):
        user_input = st.text_input("📍 Type a location (e.g. Singapore)")
        suggestions = get_place_suggestions(GOOGLE_API_KEY, user_input) if user_input else []
        if suggestions:
            options = {item["description"]: item["place_id"] for item in suggestions}
            selected_description = st.selectbox("Suggested Locations", list(options.keys()))
        else:
            selected_description = user_input
            options = {}
        submit_loc = st.form_submit_button("Submit Location")
        if submit_loc:
            if options and selected_description in options:
                place_id = options[selected_description]
                st.session_state.selected_place_id = place_id
                lat, lng = get_place_details(GOOGLE_API_KEY, place_id)
                if lat is not None and lng is not None:
                    st.session_state.latitude = lat
                    st.session_state.longitude = lng
            else:
                # Fallback: use geocoding with the text input.
                def get_lati_longi(api_key, address):
                    url = 'https://maps.googleapis.com/maps/api/geocode/json'
                    params = {
                        "address": address,
                        "key": api_key
                    }
                    response = requests.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if data["status"] == "OK" and data["results"]:
                            location = data["results"][0]["geometry"]["location"]
                            return location["lat"], location["lng"]
                    return 0.0, 0.0
                lat, lng = get_lati_longi(GOOGLE_API_KEY, user_input)
                st.session_state.latitude = lat
                st.session_state.longitude = lng

    st.write("**Current Coordinates:**", st.session_state.latitude, st.session_state.longitude)

    # --- User Inputs for Star Map ---
    col1, col2 = st.columns(2)
    with col1:
        latitude = st.number_input("Latitude", value=st.session_state.latitude, format="%.4f")
    with col2:
        longitude = st.number_input("Longitude", value=st.session_state.longitude, format="%.4f")

    date = st.date_input("📅 Select date", value=datetime.today())

    constellation = st.selectbox("✨ Choose constellation", [
        "Andromeda", "Aquarius", "Aries", "Cancer", "Capricornus", "Gemini",
        "Leo", "Libra", "Pisces", "Sagittarius", "Scorpius", "Taurus", "Virgo"
    ])
    constellation_ids = {
        "Andromeda": "and", "Aquarius": "aqr", "Aries": "ari", "Cancer": "cnc",
        "Capricornus": "cap", "Gemini": "gem", "Leo": "leo", "Libra": "lib",
        "Pisces": "psc", "Sagittarius": "sgr", "Scorpius": "sco", "Taurus": "tau", "Virgo": "vir"
    }

    # --- Generate Star Map ---
    if st.button("📷 Generate Star Map"):
        payload = {
            "style": "inverted",
            "observer": {
                "latitude": latitude,
                "longitude": longitude,
                "date": date.strftime("%Y-%m-%d")
            },
            "view": {
                "type": "constellation",
                "parameters": {
                    "constellation": constellation_ids[constellation]
                }
            }
        }

        st.info("Requesting your constellation map from AstronomyAPI...")
        try:
            # Increase the timeout because generating the star map can take time
            res = requests.post(ASTRONOMY_API_URL, headers=auth_headers, json=payload, timeout=120)
            res.raise_for_status()
            result = res.json()
            # Pretty-print the JSON response for clarity
            print(json.dumps(result, indent=4))
            image_url = res.json()['data']['imageUrl']
            st.image(image_url, caption=f"Constellation: {constellation}", use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")

# ============================================================
# Tab 3: Moon Phase
# ============================================================
with moon_phase_tab:
    st.header("Moon Phase")
    st.markdown(":green[Description]: Generate an image of the moon phase using AstronomyAPI's POST endpoint.")
    
    # Observer details
    col1, col2 = st.columns(2)
    with col1:
        mp_lat = st.number_input("Latitude", value=st.session_state.latitude, key="mp_lat", format="%.4f")
    with col2:
        mp_lng = st.number_input("Longitude", value=st.session_state.longitude, key="mp_lng", format="%.4f")
    mp_date = st.date_input("Select date", value=datetime.today(), key="mp_date")
    
    # Additional style configuration for Moon Phase (optional)
    mp_format = st.selectbox("Image Format", options=["png", "svg"], index=0)
    mp_moonStyle = st.selectbox("Moon Style", options=["default", "sketch", "shaded"], index=0)
    mp_backgroundStyle = st.selectbox("Background Style", options=["stars", "solid"], index=0)
    if mp_backgroundStyle == "solid":
        mp_backgroundColor = st.color_picker("Background Color", value="#000000")
    else:
        mp_backgroundColor = None

    # Observer, style and view parameters for moon phase.
    mp_payload = {
        "format": mp_format,
        "style": {
            "moonStyle": mp_moonStyle,
            "backgroundStyle": mp_backgroundStyle,
            # Only include backgroundColor if background is solid.
            **({"backgroundColor": mp_backgroundColor} if mp_backgroundStyle == "solid" else {})
        },
        "observer": {
            "latitude": mp_lat,
            "longitude": mp_lng,
            "date": mp_date.strftime("%Y-%m-%d")
        },
        "view": {
            "type": "portrait-simple",
            # Optional: let user choose orientation
            "orientation": st.selectbox("Orientation", options=["north-up", "south-up"], index=0)
        }
    }
    
    if st.button("Get Moon Phase", key="mp_button"):
        st.info("Requesting moon phase image from AstronomyAPI...")
        try:
            mp_res = requests.post(MOON_PHASE_URL, headers=auth_headers, json=mp_payload, timeout=120)
            mp_res.raise_for_status()
            mp_data = mp_res.json()
            if "data" in mp_data and "imageUrl" in mp_data["data"]:
                st.image(mp_data["data"]["imageUrl"], caption="Moon Phase", use_container_width=True)
            else:
                st.write("Received data:", json.dumps(mp_data, indent=4))
        except Exception as e:
            st.error(f"Error: {e}")

# === Footer ===
st.markdown("---")
st.caption("Made with ❤️ by Wilfred Djumin")