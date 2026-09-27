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

import subprocess
import google.oauth2.credentials
from google.cloud import firestore

# IMPORTANT: Hardcode project ID as string (NOT project number from auth/env)
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-3f6cb7b25903"


def get_firestore_client() -> firestore.Client:
    """Returns a Firestore client for the hardcoded project ID."""
    try:
        # Fallback to gcloud access token if running in local CLI with restricted GCE metadata scope
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], stderr=subprocess.DEVNULL).decode().strip()
        creds = google.oauth2.credentials.Credentials(token)
        client = firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
        # Test connection
        list(client.collections())
        return client
    except Exception:
        return firestore.Client(project=FIRESTORE_PROJECT_ID)


SEED_DESTINATIONS = [
    {
        "id": "sf-ferry-building",
        "name": "Ferry Building Marketplace",
        "city": "San Francisco",
        "category": "dining",
        "description": "Historic waterfront ferry terminal packed with artisan food vendors, bakeries, and local dining.",
        "recommended_time_hours": 2.0,
        "estimated_cost_usd": 35.0,
        "dietary_options": ["vegan", "vegetarian", "gluten-free", "seafood"],
        "rating": 4.8,
    },
    {
        "id": "sf-cable-car",
        "name": "Powell-Hyde Cable Car",
        "city": "San Francisco",
        "category": "transit",
        "description": "Iconic historic cable car transit route taking you from Market St down to Fisherman's Wharf.",
        "recommended_time_hours": 0.5,
        "estimated_cost_usd": 8.0,
        "dietary_options": [],
        "rating": 4.6,
    },
    {
        "id": "sf-golden-gate-park",
        "name": "Golden Gate Park & Japanese Tea Garden",
        "city": "San Francisco",
        "category": "attraction",
        "description": "Expansive urban park with botanical gardens, museums, and serene tea houses.",
        "recommended_time_hours": 3.0,
        "estimated_cost_usd": 15.0,
        "dietary_options": ["vegetarian", "tea"],
        "rating": 4.9,
    },
    {
        "id": "sea-pike-place",
        "name": "Pike Place Market",
        "city": "Seattle",
        "category": "dining",
        "description": "Famous public market overlooking Elliott Bay with fresh seafood stalls, flower stands, and food tours.",
        "recommended_time_hours": 2.5,
        "estimated_cost_usd": 30.0,
        "dietary_options": ["seafood", "vegan", "gluten-free"],
        "rating": 4.8,
    },
    {
        "id": "sea-light-rail",
        "name": "Sound Transit Light Rail",
        "city": "Seattle",
        "category": "transit",
        "description": "Fast and affordable light rail connecting SEA Airport to Downtown, Capitol Hill, and UW.",
        "recommended_time_hours": 0.75,
        "estimated_cost_usd": 3.5,
        "dietary_options": [],
        "rating": 4.5,
    },
    {
        "id": "tokyo-tsukiji-outer",
        "name": "Tsukiji Outer Market",
        "city": "Tokyo",
        "category": "dining",
        "description": "Vibrant food market specializing in fresh sushi, tamagoyaki, and Japanese street snacks.",
        "recommended_time_hours": 2.0,
        "estimated_cost_usd": 40.0,
        "dietary_options": ["seafood", "pescatarian"],
        "rating": 4.9,
    },
]


def seed_database():
    print(f"Connecting to Firestore for project: {FIRESTORE_PROJECT_ID}...")
    db = get_firestore_client()
    collection_ref = db.collection("destinations")

    count = 0
    for item in SEED_DESTINATIONS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"  [+] Seeded destination: {item['name']} ({item['city']})")
        count += 1

    print(f"\nSuccessfully seeded {count} items into Firestore collection 'destinations'!")


if __name__ == "__main__":
    seed_database()
