# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import subprocess
import google.oauth2.credentials
from google.cloud import firestore
from google.genai import types

# IMPORTANT: Hardcode project ID as string (NOT project number from auth/env)
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-3f6cb7b25903"


def _get_db() -> firestore.Client:
    """Returns a Firestore client for hardcoded project ID string."""
    try:
        client = firestore.Client(project=FIRESTORE_PROJECT_ID)
        list(client.collections())
        return client
    except Exception:
        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            creds = google.oauth2.credentials.Credentials(token)
            return firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
        except Exception:
            return firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_travel_spots(city: str = "", category: str = "") -> str:
    """Searches the Firestore destinations database for attractions, dining, or transit spots.

    Args:
        city: Optional city name to filter by (e.g. "San Francisco", "Seattle", "Tokyo").
        category: Optional category filter (e.g. "dining", "attraction", "transit").

    Returns:
        A JSON string listing matching travel spots with descriptions, cost, and dietary options.
    """
    db = _get_db()
    ref = db.collection("destinations")
    
    docs = ref.stream()
    results = []

    city_clean = city.strip().lower() if city else ""
    cat_clean = category.strip().lower() if category else ""

    for doc in docs:
        data = doc.to_dict()
        doc_city = str(data.get("city", "")).lower()
        doc_cat = str(data.get("category", "")).lower()

        if city_clean and city_clean not in doc_city:
            continue
        if cat_clean and cat_clean not in doc_cat:
            continue

        results.append(data)

    if not results:
        return f"No travel spots found matching city='{city}' and category='{category}'."

    return json.dumps(results, indent=2)


def add_travel_spot(
    name: str,
    city: str,
    category: str,
    description: str,
    estimated_cost_usd: float = 0.0,
    dietary_options: str = "",
) -> str:
    """Adds a new travel spot, dining location, or transit option to the Firestore database.

    Args:
        name: Name of the spot (e.g. "Lombard Street").
        city: City name (e.g. "San Francisco").
        category: Spot category ("attraction", "dining", "transit").
        description: Short description of the spot.
        estimated_cost_usd: Estimated cost per person in USD.
        dietary_options: Comma-separated list of dietary options if applicable (e.g. "vegan, gluten-free").

    Returns:
        A confirmation message with the saved document ID.
    """
    db = _get_db()
    
    doc_id = f"{city.lower().replace(' ', '-')}-{name.lower().replace(' ', '-')[:20]}"
    dietary_list = [d.strip().lower() for d in dietary_options.split(",") if d.strip()] if dietary_options else []

    item_data = {
        "id": doc_id,
        "name": name,
        "city": city,
        "category": category.lower(),
        "description": description,
        "estimated_cost_usd": float(estimated_cost_usd),
        "dietary_options": dietary_list,
        "rating": 4.5,
    }

    db.collection("destinations").document(doc_id).set(item_data)
    return f"Successfully added '{name}' in {city} to Firestore with ID '{doc_id}'."


CITY_TIERS = {
    "tokyo": {"multiplier": 1.25, "currency": "JPY", "rate": 155.0, "tip_rate": 0.0},
    "paris": {"multiplier": 1.15, "currency": "EUR", "rate": 0.92, "tip_rate": 0.0},
    "san francisco": {"multiplier": 1.10, "currency": "USD", "rate": 1.0, "tip_rate": 0.18},
    "seattle": {"multiplier": 1.00, "currency": "USD", "rate": 1.0, "tip_rate": 0.18},
    "bangkok": {"multiplier": 0.60, "currency": "THB", "rate": 36.5, "tip_rate": 0.0},
}

STYLE_RATES = {
    "budget": {"lodging": 70.0, "food_per_day": 35.0, "transit_per_day": 10.0},
    "moderate": {"lodging": 175.0, "food_per_day": 75.0, "transit_per_day": 20.0},
    "luxury": {"lodging": 380.0, "food_per_day": 180.0, "transit_per_day": 50.0},
}


def calculate_trip_budget(
    city: str,
    days: int = 3,
    travelers: int = 1,
    style: str = "moderate",
    activity_fees_usd: float = 0.0,
) -> str:
    """Calculates an accurate travel budget breakdown for a specific city.

    Args:
        city: Destination city name (e.g. "Tokyo", "Paris", "San Francisco", "Seattle", "Bangkok").
        days: Number of travel days (default 3).
        travelers: Number of travelers in group (default 1).
        style: Travel style tier - "budget", "moderate", or "luxury" (default "moderate").
        activity_fees_usd: Estimated total attraction entry fees per person in USD (default 0.0).

    Returns:
        A formatted JSON string with itemized lodging, food, transit, taxes, and local currency conversion.
    """
    city_key = city.strip().lower()
    city_info = CITY_TIERS.get(city_key, {"multiplier": 1.0, "currency": "USD", "rate": 1.0, "tip_rate": 0.10})

    style_key = style.strip().lower()
    rates = STYLE_RATES.get(style_key, STYLE_RATES["moderate"])

    mult = city_info["multiplier"]
    base_lodging = rates["lodging"] * max(1, days - 1) * mult
    base_food = rates["food_per_day"] * days * travelers * mult * (1.0 + city_info["tip_rate"])
    base_transit = rates["transit_per_day"] * days * travelers * mult
    base_activities = activity_fees_usd * travelers * mult

    subtotal = base_lodging + base_food + base_transit + base_activities
    contingency = subtotal * 0.10
    total_usd = subtotal + contingency

    local_total = total_usd * city_info["rate"]

    result = {
        "city": city.title(),
        "days": days,
        "travelers": travelers,
        "style": style.lower(),
        "breakdown_usd": {
            "lodging": round(base_lodging, 2),
            "food_and_dining": round(base_food, 2),
            "local_transit": round(base_transit, 2),
            "activities": round(base_activities, 2),
            "contingency_10pct": round(contingency, 2),
            "total_usd": round(total_usd, 2),
        },
        "local_currency": {
            "currency_code": city_info["currency"],
            "total_local_currency": round(local_total, 2) if city_info["currency"] != "USD" else round(total_usd, 2)
        }
    }

    return json.dumps(result, indent=2)


import uuid
from google import genai
from google.cloud import storage

BUCKET_NAME = "wayfarer-travel-media-3f6cb7b25903"


def generate_destination_preview(prompt: str, destination_name: str) -> str:
    """Generates an AI visual preview/postcard of a travel destination or dish and uploads it to Cloud Storage.

    Args:
        prompt: Descriptive prompt for image generation (e.g. "Scenic view of Mount Fuji during cherry blossom season").
        destination_name: Name of the destination or dish for filename creation (e.g. "Mount Fuji").

    Returns:
        The public Cloud Storage HTTPS image URL of the generated image.
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="us-central1")
        res = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=f"Generate a vibrant, high-quality travel photography image of: {prompt}"
        )

        image_bytes = None
        if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
            for part in res.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_bytes = part.inline_data.data
                    break

        if not image_bytes:
            return "Failed to extract generated image data."

        clean_name = destination_name.lower().replace(" ", "-")[:20]
        filename = f"{clean_name}-{uuid.uuid4().hex[:6]}.png"

        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            creds = google.oauth2.credentials.Credentials(token)
            storage_client = storage.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
        except Exception:
            storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)

        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return f"Successfully generated destination preview for '{destination_name}': {public_url}"
    except Exception as e:
        return f"Error generating destination preview: {str(e)}"


import os
import urllib.request


def get_live_exchange_rates(
    base_currency: str = "USD",
    target_currencies: str = "EUR,JPY,GBP,CAD,AUD,THB",
) -> str:
    """Fetches real live foreign exchange conversion rates from the Frankfurter open finance API.

    Args:
        base_currency: The base ISO currency code (default "USD").
        target_currencies: Comma-separated list of target currency codes (e.g. "EUR,JPY,GBP,THB").

    Returns:
        A formatted JSON string with live real-time currency exchange rates and publication date.
    """
    try:
        base = base_currency.strip().upper()
        targets = ",".join([c.strip().upper() for c in target_currencies.split(",") if c.strip()])
        url = f"https://api.frankfurter.app/latest?from={base}&to={targets}"

        # If an optional API key env var is set, append or header it
        api_key = os.getenv("EXCHANGE_RATE_API_KEY", "")
        headers = {"User-Agent": "WayfarerTravelConcierge/1.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error fetching live exchange rates: {str(e)}"


import urllib.parse
from dotenv import load_dotenv

load_dotenv()


def geocode_address(address: str) -> str:
    """Converts an address or landmark into latitude/longitude coordinates using Google Maps Geocoding API.

    Args:
        address: The location address or landmark name (e.g. "Space Needle, Seattle", "Eiffel Tower, Paris").

    Returns:
        A JSON string containing the formatted address and latitude/longitude coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode(
            {"address": address, "key": api_key}
        )
        req = urllib.request.Request(url, headers={"User-Agent": "WayfarerTravelConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if not data.get("results"):
            return f"No geocoding results found for address: '{address}'."

        first_result = data["results"][0]
        formatted = {
            "query_address": address,
            "formatted_address": first_result.get("formatted_address"),
            "location": first_result.get("geometry", {}).get("location"),
        }
        return json.dumps(formatted, indent=2)
    except Exception as e:
        return f"Error geocoding address: {str(e)}"


def search_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
    max_results: int = 5,
) -> str:
    """Searches for nearby places (restaurants, cafes, attractions, museums) around coordinates using Google Places API (New).

    Args:
        latitude: Latitude coordinate of search center point.
        longitude: Longitude coordinate of search center point.
        place_type: Type of place to search for (e.g. "restaurant", "cafe", "tourist_attraction", "museum", "park").
        radius_meters: Search radius in meters (default 1000.0).
        max_results: Maximum number of results to return (1-20, default 5).

    Returns:
        A JSON string listing nearby places with name, formatted address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    try:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        body = json.dumps({
            "includedTypes": [place_type.strip().lower()],
            "maxResultCount": min(20, max(1, max_results)),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": float(latitude), "longitude": float(longitude)},
                    "radius": float(radius_meters),
                }
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
                "User-Agent": "WayfarerTravelConcierge/1.0",
            }
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        places_list = data.get("places", [])
        if not places_list:
            return f"No nearby places of type '{place_type}' found within {radius_meters}m."

        results = []
        for p in places_list:
            results.append({
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "address": p.get("formattedAddress"),
                "location": p.get("location"),
            })

        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching nearby places: {str(e)}"


from google.adk.tools import ToolContext


async def generate_travel_item_image(
    prompt: str,
    item_name: str,
    tool_context: ToolContext,
) -> str:
    """Generates an image for a travel item (destination, food dish, attraction) using gemini-3.1-flash-lite-image in global region.

    Saves the image as an ADK artifact using tool_context.save_artifact, uploads it to the public Cloud Storage bucket,
    and returns its public https URL.

    Args:
        prompt: Descriptive prompt for image generation (e.g. "A gourmet bowl of ramen in Tokyo").
        item_name: Name of the travel item or destination (e.g. "Tokyo Ramen").
        tool_context: ADK ToolContext automatically injected by ADK runtime.

    Returns:
        The public HTTPS Cloud Storage URL of the generated image (https://storage.googleapis.com/wayfarer-travel-media-3f6cb7b25903/<object>).
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
        res = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"Generate a vibrant, high-quality travel photography image of: {prompt}",
        )

        image_bytes = None
        if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
            for part in res.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_bytes = part.inline_data.data
                    break

        if not image_bytes:
            return "Error: Failed to extract generated image bytes."

        clean_name = item_name.lower().replace(" ", "-")[:20]
        filename = f"{clean_name}-{uuid.uuid4().hex[:6]}.png"

        # 1. Save artifact with tool_context.save_artifact
        if tool_context:
            try:
                artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                await tool_context.save_artifact(filename, artifact_part)
            except Exception as artifact_err:
                print(f"Warning: tool_context.save_artifact failed: {artifact_err}")

        # 2. Upload image bytes to public Cloud Storage bucket
        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            creds = google.oauth2.credentials.Credentials(token)
            storage_client = storage.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
        except Exception:
            storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)

        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return public_url
    except Exception as e:
        return f"Error generating travel item image: {str(e)}"





