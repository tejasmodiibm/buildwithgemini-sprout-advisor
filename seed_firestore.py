import datetime
import subprocess
import google.auth
import google.oauth2.credentials
from google.cloud import firestore

# Hardcode project ID to avoid issue where GOOGLE_CLOUD_PROJECT returns project number on Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-0b1b594835a1"

def get_firestore_client() -> firestore.Client:
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
        if token:
            creds = google.oauth2.credentials.Credentials(token, quota_project_id=FIRESTORE_PROJECT_ID)
            return firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
    except Exception as e:
        print(f"Warning: could not retrieve gcloud access token ({e}), falling back to default auth")
    return firestore.Client(project=FIRESTORE_PROJECT_ID)

def seed_database():
    print(f"Connecting to Firestore with project ID: {FIRESTORE_PROJECT_ID}...")
    db = get_firestore_client()

    # Seed Plants Collection
    plants = [
        {
            "id": "coneflower",
            "name": "Purple Coneflower (Echinacea)",
            "category": "flower",
            "placement": "frontyard",
            "sun_exposure": "full_sun",
            "zone": "6a",
            "difficulty": "beginner",
            "season": "summer",
            "care_instructions": "Drought-tolerant perennial for Zone 6a frontyards. Water weekly until established. Thrives in full sun."
        },
        {
            "id": "black_eyed_susan",
            "name": "Black-Eyed Susan (Rudbeckia)",
            "category": "flower",
            "placement": "frontyard",
            "sun_exposure": "full_sun",
            "zone": "6a",
            "difficulty": "beginner",
            "season": "summer_fall",
            "care_instructions": "Low-maintenance flower perfect for Zone 6a frontyard beds. Long bloom season July to September."
        },
        {
            "id": "hosta",
            "name": "Patriot Hosta",
            "category": "flower",
            "placement": "frontyard",
            "sun_exposure": "partial_shade",
            "zone": "6a",
            "difficulty": "beginner",
            "season": "spring_summer",
            "care_instructions": "Thrives in shaded frontyard entryways. Requires moist, well-draining soil and minimal maintenance."
        },
        {
            "id": "cherry_tomato",
            "name": "Sweet 100 Cherry Tomato",
            "category": "vegetable",
            "placement": "backyard",
            "sun_exposure": "full_sun",
            "zone": "6a",
            "difficulty": "beginner",
            "season": "summer",
            "care_instructions": "Plant transplants after last frost (mid-May in Zone 6a). Requires 6-8 hours of direct sun and tomato cage."
        },
        {
            "id": "bush_zucchini",
            "name": "Black Beauty Zucchini",
            "category": "vegetable",
            "placement": "backyard",
            "sun_exposure": "full_sun",
            "zone": "6a",
            "difficulty": "beginner",
            "season": "summer",
            "care_instructions": "High-yielding crop for Zone 6a backyards. Plant seeds directly in late May after soil warms."
        },
        {
            "id": "sugar_snap_pea",
            "name": "Sugar Snap Pea",
            "category": "vegetable",
            "placement": "backyard",
            "sun_exposure": "full_sun",
            "zone": "6a",
            "difficulty": "beginner",
            "season": "spring_fall",
            "care_instructions": "Cool-season crop for Zone 6a. Plant in early April for spring harvest or August for fall crop."
        }
    ]

    print("Seeding 'plants' collection...")
    for plant in plants:
        doc_ref = db.collection("plants").document(plant["id"])
        doc_ref.set(plant)
        print(f"  Added plant: {plant['name']} ({plant['id']})")

    # Seed Garden Logs Collection
    sample_logs = [
        {
            "id": "log_1",
            "plant_name": "Sweet 100 Cherry Tomato",
            "action": "planted",
            "location": "backyard",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "notes": "Planted 2 seedlings in raised backyard bed #1."
        },
        {
            "id": "log_2",
            "plant_name": "Purple Coneflower (Echinacea)",
            "action": "planted",
            "location": "frontyard",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "notes": "Planted 3 perennials near front porch flowerbed."
        }
    ]

    print("Seeding 'garden_logs' collection...")
    for log in sample_logs:
        doc_ref = db.collection("garden_logs").document(log["id"])
        doc_ref.set(log)
        print(f"  Added log: {log['action']} {log['plant_name']}")

    print("Firestore database seeded successfully!")

if __name__ == "__main__":
    seed_database()
