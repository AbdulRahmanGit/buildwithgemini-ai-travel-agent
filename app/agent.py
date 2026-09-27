# ruff: noqa
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

import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

load_dotenv()


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


from app.tools import (
    add_travel_spot,
    calculate_trip_budget,
    generate_destination_preview,
    generate_travel_item_image,
    geocode_address,
    get_live_exchange_rates,
    search_nearby_places,
    search_travel_spots,
)


import json
import os
from google.adk.code_executors import AgentEngineSandboxCodeExecutor

# Read agent runtime resource name from deployment_metadata.json if present
metadata_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
agent_engine_resource_name = None
if os.path.exists(metadata_path):
    try:
        with open(metadata_path, "r") as f:
            meta = json.load(f)
            agent_engine_resource_name = meta.get("remote_agent_runtime_id")
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from app.a2ui_utils import a2ui_callback
from google.adk.agents.callback_context import CallbackContext
from google.adk.memory import VertexAiMemoryBankService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

MEMORY_BANK_ID = "3503367302512902144"


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Wayfarer, a personalized travel concierge AI assistant. "
        "You help travelers discover attractions, curate food & dining spots, "
        "and plan transportation logistics. You remember the user's stated "
        "preferences and facts from previous conversations to personalize responses. "
        "When requested to generate a postcard or visual preview for a destination, "
        "you MUST call generate_destination_preview to create the image asset. "
        "Use search_travel_spots and add_travel_spot to manage Firestore recommendations, "
        "calculate_trip_budget to compute trip budgets, generate_destination_preview and "
        "generate_travel_item_image to generate AI destination postcards, get_live_exchange_rates "
        "to fetch exchange rates, geocode_address to convert addresses to coordinates, "
        "and search_nearby_places to find nearby points of interest."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Whenever a user asks to generate a postcard or image preview, call generate_destination_preview "
        "first to obtain the public image URL, then render an A2UI Card containing an Image component set to that URL. "
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows and an optional Image. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "Set the Image url to the exact public https link returned by generate_destination_preview. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback triggered after agent turns to store durable facts in Memory Bank."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def memory_bank_service_builder():
    """Memory service builder configured for Vertex AI Memory Bank for future deployments."""
    return VertexAiMemoryBankService(
        project="qwiklabs-gcp-02-3f6cb7b25903",
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        get_weather,
        get_current_time,
        search_travel_spots,
        add_travel_spot,
        calculate_trip_budget,
        generate_destination_preview,
        generate_travel_item_image,
        get_live_exchange_rates,
        geocode_address,
        search_nearby_places,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)



