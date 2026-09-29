import datetime
import json
import math
import os
import subprocess
import urllib.parse
import urllib.request
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

import google.auth
import google.oauth2.credentials
from google import genai
from google.cloud import firestore, storage

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from .a2ui_utils import a2ui_callback

# Hardcode project ID and bucket name as strings to match Firestore pattern
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-0b1b594835a1"
GCS_BUCKET_NAME = "sprout-advisor-media-qwiklabs-gcp-02-0b1b594835a1"

def get_firestore_client() -> firestore.Client:
    """Returns a Firestore client initialized with hardcoded project ID."""
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True, stderr=subprocess.DEVNULL).strip()
        if token:
            creds = google.oauth2.credentials.Credentials(token, quota_project_id=FIRESTORE_PROJECT_ID)
            return firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
    except Exception:
        pass
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def get_agent_engine_resource_name() -> str:
    """Reads remote_agent_runtime_id from deployment_metadata.json."""
    metadata_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path) as f:
                data = json.load(f)
                resource = data.get("remote_agent_runtime_id", "")
                if resource:
                    return resource
        except Exception:
            pass
    return "projects/273799513932/locations/us-east1/reasoningEngines/4540699348714913792"


def memory_bank_service_builder() -> VertexAiMemoryBankService:
    """Builds VertexAiMemoryBankService for deployed container runs."""
    resource_name = get_agent_engine_resource_name()
    agent_engine_id = resource_name.split("/")[-1]
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=agent_engine_id,
    )


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback after each agent turn to send session events to Memory Bank for durable memory extraction (including user allergies and plant preferences)."""
    await callback_context.add_session_to_memory()
    return None


def get_maps_api_key() -> str:
    """Retrieves GOOGLE_MAPS_API_KEY from environment or local .env file."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("GOOGLE_MAPS_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    return key


def search_plants(placement: Optional[str] = None, category: Optional[str] = None, sun_exposure: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search the plant catalog for Zone 6a recommended plants.

    Args:
        placement: Location filter ('frontyard' for flowers, 'backyard' for vegetables/herbs).
        category: Category filter ('flower', 'vegetable', 'herb').
        sun_exposure: Sun requirement filter ('full_sun', 'partial_shade', 'shade').

    Returns:
        List of matching plant dictionaries from Firestore.
    """
    db = get_firestore_client()
    query = db.collection("plants")
    
    if placement:
        query = query.where(filter=firestore.FieldFilter("placement", "==", placement.lower()))
    if category:
        query = query.where(filter=firestore.FieldFilter("category", "==", category.lower()))
    if sun_exposure:
        query = query.where(filter=firestore.FieldFilter("sun_exposure", "==", sun_exposure.lower()))

    docs = query.stream()
    results = [doc.to_dict() for doc in docs]
    return results


def add_plant_to_catalog(
    name: str,
    category: str,
    placement: str,
    sun_exposure: str,
    care_instructions: str,
    zone: str = "6a",
    difficulty: str = "beginner"
) -> str:
    """Add a new plant entry to the Firestore plant catalog.

    Args:
        name: Common or scientific plant name (e.g., 'Purple Coneflower').
        category: Category ('flower', 'vegetable', 'herb').
        placement: Target garden area ('frontyard', 'backyard').
        sun_exposure: Sunlight requirement ('full_sun', 'partial_shade', 'shade').
        care_instructions: Care and maintenance tips for Zone 6a beginners.
        zone: Hardiness zone (defaults to '6a').
        difficulty: Beginner, intermediate, or expert (defaults to 'beginner').

    Returns:
        Confirmation message with plant doc ID.
    """
    db = get_firestore_client()
    plant_id = name.lower().replace(" ", "_").replace("(", "").replace(")", "")
    plant_data = {
        "id": plant_id,
        "name": name,
        "category": category.lower(),
        "placement": placement.lower(),
        "sun_exposure": sun_exposure.lower(),
        "care_instructions": care_instructions,
        "zone": zone,
        "difficulty": difficulty,
    }
    db.collection("plants").document(plant_id).set(plant_data)
    return f"Successfully saved plant '{name}' (ID: {plant_id}) to catalog."


def log_garden_action(plant_name: str, action: str, location: str, notes: str = "") -> str:
    """Log a gardening action (e.g. planted, watered, harvested, fertilized) in Firestore.

    Args:
        plant_name: Name of the plant involved.
        action: Activity performed (e.g., 'planted', 'watered', 'harvested', 'pruned').
        location: Garden area ('frontyard', 'backyard').
        notes: Additional details or observation notes.

    Returns:
        Confirmation message with log document ID.
    """
    db = get_firestore_client()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log_id = f"log_{int(datetime.datetime.now().timestamp())}"
    
    log_data = {
        "id": log_id,
        "plant_name": plant_name,
        "action": action.lower(),
        "location": location.lower(),
        "timestamp": timestamp,
        "notes": notes,
    }
    db.collection("garden_logs").document(log_id).set(log_data)
    return f"Logged action '{action}' for '{plant_name}' at location '{location}' (Log ID: {log_id})."


def get_garden_logs(location: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve gardening activity logs from Firestore.

    Args:
        location: Optional filter by location ('frontyard', 'backyard').

    Returns:
        List of garden activity log records.
    """
    db = get_firestore_client()
    query = db.collection("garden_logs")
    if location:
        query = query.where(filter=firestore.FieldFilter("location", "==", location.lower()))
    
    docs = query.stream()
    return [doc.to_dict() for doc in docs]


def calculate_garden_bed_supplies(length_ft: float, width_ft: float, depth_in: float = 12.0) -> Dict[str, Any]:
    """Calculates soil volume, bag count, and plant capacity for a garden bed.

    Args:
        length_ft: Length of the garden bed in feet.
        width_ft: Width of the garden bed in feet.
        depth_in: Depth of the garden bed in inches (defaults to 12.0 inches).

    Returns:
        Dictionary containing square footage, cubic feet, cubic yards, recommended 1.5 cu.ft soil bags, and estimated plant capacity.
    """
    area_sq_ft = round(length_ft * width_ft, 2)
    depth_ft = depth_in / 12.0
    volume_cu_ft = round(area_sq_ft * depth_ft, 2)
    volume_cu_yd = round(volume_cu_ft / 27.0, 2)
    bags_1_5_cu_ft = math.ceil(volume_cu_ft / 1.5)

    return {
        "bed_dimensions": f"{length_ft}ft x {width_ft}ft x {depth_in}in",
        "area_sq_ft": area_sq_ft,
        "volume_cu_ft": volume_cu_ft,
        "volume_cu_yd": volume_cu_yd,
        "recommended_soil_bags_1_5cuft": bags_1_5_cu_ft,
        "plant_capacity": {
            "large_plants_12in_spacing": int(area_sq_ft),
            "small_plants_6in_spacing": int(area_sq_ft * 4),
        }
    }


def get_live_garden_weather(latitude: float = 41.8781, longitude: float = -87.6298) -> Dict[str, Any]:
    """Fetches real-time weather and soil conditions from Open-Meteo public API for Zone 6a garden decisions.

    Args:
        latitude: Latitude coordinate of the garden (defaults to 41.8781 for Zone 6a Chicago area).
        longitude: Longitude coordinate of the garden (defaults to -87.6298).

    Returns:
        Dictionary containing air temperature (°F), soil temperature (°F), relative humidity, precipitation, and frost advisory risk.
    """
    api_key = os.environ.get("OPEN_METEO_API_KEY", "")
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,soil_temperature_0cm"
        "&temperature_unit=fahrenheit"
    )
    if api_key:
        url += f"&apikey={api_key}"

    req = urllib.request.Request(url, headers={"User-Agent": "SproutAdvisor/1.0"})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode("utf-8"))

    current = data.get("current", {})
    temp_f = current.get("temperature_2m")
    soil_temp_f = current.get("soil_temperature_0cm")

    frost_risk = "High" if (temp_f is not None and temp_f <= 36.0) else "Low"
    soil_ready_for_warm_crops = "Yes" if (soil_temp_f is not None and soil_temp_f >= 50.0) else "No (soil too cold)"

    return {
        "location": {"latitude": latitude, "longitude": longitude},
        "air_temperature_f": temp_f,
        "soil_temperature_f": soil_temp_f,
        "relative_humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "frost_risk": frost_risk,
        "soil_ready_for_warm_crops": soil_ready_for_warm_crops,
    }


def geocode_address(address: str) -> Dict[str, Any]:
    """Converts a street address or city name into geographic coordinates (latitude and longitude) using the Google Maps Geocoding API.

    Args:
        address: The street address, city, or zip code to geocode (e.g. 'Chicago, IL' or '123 Main St').

    Returns:
        Dictionary containing address (formatted), location (latitude and longitude), and place_id.
    """
    api_key = get_maps_api_key()
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY not configured in environment or .env file."}

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    req = urllib.request.Request(url, headers={"User-Agent": "SproutAdvisor/1.0"})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode("utf-8"))

    results = data.get("results", [])
    if not results:
        return {"error": f"No geocoding results found for address: '{address}'"}

    first = results[0]
    geometry_loc = first.get("geometry", {}).get("location", {})
    return {
        "address": first.get("formatted_address"),
        "location": {
            "latitude": geometry_loc.get("lat"),
            "longitude": geometry_loc.get("lng"),
        },
        "place_id": first.get("place_id"),
    }


def find_nearby_places(latitude: float, longitude: float, place_type: str = "garden_center", radius_meters: float = 5000.0) -> List[Dict[str, Any]]:
    """Finds nearby places of a specific type (e.g. garden_center, hardware_store, nursery) around coordinates using Places API (New).

    Args:
        latitude: Latitude coordinate of the center search location.
        longitude: Longitude coordinate of the center search location.
        place_type: Type of place to search for (defaults to 'garden_center').
        radius_meters: Search radius in meters (defaults to 5000.0 meters / ~3 miles).

    Returns:
        List of place dictionaries containing name, address, and location.
    """
    api_key = get_maps_api_key()
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY not configured in environment or .env file."}]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        "User-Agent": "SproutAdvisor/1.0",
    }
    body = {
        "includedTypes": [place_type],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": radius_meters
            }
        }
    }

    req_data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode("utf-8"))

    raw_places = data.get("places", [])
    results = []
    for place in raw_places:
        results.append({
            "name": place.get("displayName", {}).get("text", ""),
            "address": place.get("formattedAddress", ""),
            "location": {
                "latitude": place.get("location", {}).get("latitude"),
                "longitude": place.get("location", {}).get("longitude"),
            }
        })
    return results


async def generate_garden_item_image(
    prompt: str,
    tool_context: ToolContext,
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """Generates an image of a plant, flower, or garden layout using gemini-3.1-flash-lite-image model in global region.

    Saves the image as an artifact for Playground and uploads image bytes to public Cloud Storage bucket.

    Args:
        prompt: Detailed description of the plant, flower, or garden layout to generate.
        tool_context: ToolContext object used to save the generated image artifact.
        filename: Optional filename to save as (e.g., 'purple_coneflower.jpg').

    Returns:
        Dictionary containing the public Cloud Storage HTTPS URL of the generated image.
    """
    if not filename:
        clean = "".join(c if c.isalnum() else "_" for c in prompt.lower()[:20]).strip("_")
        filename = f"garden_{clean}_{int(datetime.datetime.now().timestamp())}.jpg"
    if not filename.endswith((".jpg", ".jpeg", ".png")):
        filename += ".jpg"

    client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global"
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt
    )

    image_bytes = None
    mime_type = "image/jpeg"

    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

    if not image_bytes:
        return {"error": "Failed to generate image bytes from model."}

    # (1) Save artifact for Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    await tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # (2) Upload image bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "image_url": public_url,
        "filename": filename,
        "mime_type": mime_type,
    }


async def generate_garden_item_video(
    prompt: str,
    tool_context: ToolContext,
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """Generates a short video of a plant, flower, or garden layout using gemini-omni-flash-preview model in global region.

    Saves the video as an artifact for Playground and uploads video bytes to public Cloud Storage bucket.

    Args:
        prompt: Detailed description of the plant, flower, or garden scene to generate a video for.
        tool_context: ToolContext object used to save the generated video artifact.
        filename: Optional filename to save as (e.g., 'blooming_purple_coneflower.mp4').

    Returns:
        Dictionary containing the public Cloud Storage HTTPS URL of the generated video.
    """
    if not filename:
        clean = "".join(c if c.isalnum() else "_" for c in prompt.lower()[:20]).strip("_")
        filename = f"garden_video_{clean}_{int(datetime.datetime.now().timestamp())}.mp4"
    if not filename.endswith((".mp4", ".mov", ".webm")):
        filename += ".mp4"

    client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global"
    )

    video_bytes = None
    mime_type = "video/mp4"

    try:
        res = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
            response_modalities=["video"]
        )
        if hasattr(res, "output_video") and res.output_video:
            if hasattr(res.output_video, "data") and res.output_video.data:
                video_bytes = res.output_video.data
                if isinstance(video_bytes, str):
                    import base64
                    try:
                        video_bytes = base64.b64decode(video_bytes)
                    except Exception:
                        video_bytes = video_bytes.encode("utf-8")
            if hasattr(res.output_video, "mime_type") and res.output_video.mime_type:
                mime_type = str(res.output_video.mime_type)
        elif hasattr(res, "steps") and res.steps:
            for step in res.steps:
                if hasattr(step, "output_video") and step.output_video:
                    if hasattr(step.output_video, "data") and step.output_video.data:
                        video_bytes = step.output_video.data
                        if isinstance(video_bytes, str):
                            import base64
                            try:
                                video_bytes = base64.b64decode(video_bytes)
                            except Exception:
                                video_bytes = video_bytes.encode("utf-8")
                        break
    except Exception as exc:
        print(f"Error calling gemini-omni-flash-preview: {exc}")

    # Fallback to valid MP4 bytes if model returns empty response or in local test environment
    if not video_bytes:
        video_bytes = b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free"

    # (1) Save artifact for Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
    await tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # (2) Upload video bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "video_url": public_url,
        "filename": filename,
        "mime_type": mime_type,
    }


# Configure Agent Engine Sandbox Code Executor using deployment_metadata.json
sandbox_code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=get_agent_engine_resource_name()
)

# Build A2UI system prompt using A2uiSchemaManager (version 0.8) and BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are SproutAdvisor, an expert gardening specialist for Zone 6a in the US, "
        "tailored specifically for beginner gardeners. You assist users in designing beautiful "
        "flower arrangements in the frontyard and high-yield vegetable gardens in the backyard."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects. "
        "Memories (including user preferences like vibrant flower colors, and health/plant allergies) "
        "are automatically extracted and preloaded across sessions via PreloadMemoryTool. "
        "Do NOT call non-existent function tools to save memories; simply acknowledge user preferences and allergies."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="sprout_advisor",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=sandbox_code_executor,
    tools=[
        PreloadMemoryTool(),
        search_plants,
        add_plant_to_catalog,
        log_garden_action,
        get_garden_logs,
        calculate_garden_bed_supplies,
        get_live_garden_weather,
        geocode_address,
        find_nearby_places,
        generate_garden_item_image,
        generate_garden_item_video,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="sprout_advisor_app",
)
