import streamlit as st
from datetime import datetime
import requests
import base64
import json
from dotenv import load_dotenv

# --- Configuration ---
# Replace with your actual credentials and API key values.
load_dotenv()

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ASTRONOMY_API_URL = 'https://api.astronomyapi.com/api/v2/studio/star-chart'


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

with planet_position_tab:
    st.header("Planetary Positions")

    
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

    
with moon_phase_tab:
    st.header("Moon Phase")

# === Footer ===
st.markdown("---")
st.caption("Made with ❤️ by Wilfred Djumin")