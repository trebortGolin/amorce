"""
Agent Client (The "Brain") - Amorce Project (v1.2 - Real Tasks)

This file implements the logic for the agent, including:
- P-0: Secure registration with the Trust Directory (using DIRECTORY_ADMIN_KEY).
- P-1: Real LLM calls to Gemini for NLU and NLG.
- T-5.6 Fix: Added robust error handling to __init__ for Gemini initialization.
- P-1: Intent routing.
- P-4: Cryptographic signing of tasks.
- SPRINT V1.2 (T-6.1): Replacing mock task logic with real API call structure.
"""

import os
import json
import logging
import requests
import base64
import time
from pathlib import Path
from typing import Dict, Any, Optional

# --- P-1: LLM Import ---
import google.generativeai as genai

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

# --- Global Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- P-1: LLM System Prompts (from Briefing) ---
NLU_SYSTEM_PROMPT = """
You are an expert NLU (Natural Language Understanding) agent for a travel agency.
Your sole task is to extract information from the user's request and respond ONLY with a JSON object.
NEVER add any text before or after the JSON.

You will receive:
1. "conversation_state": The state of the conversation (can be empty {}).
2. "user_input": What the user just said.

Your rules:
- Identify the user's intent: 'SEARCH_FLIGHT', 'BOOK_FLIGHT', or 'CLARIFICATION'.
- If the request is a *new* search (e.g., "Find me a flight to Paris"), create a NEW, complete JSON for this intent.
- If the user provides missing information (e.g., "From Paris", "on Dec 15th"),
  USE the previous state and ONLY ADD or MODIFY the information provided. The intent should remain the same (e.g., 'SEARCH_FLIGHT').
- If the user confirms a booking (e.g., "yes", "book it", "confirm"), detect the 'BOOK_FLIGHT' intent.
- If the user input is not clear or is just conversational, use 'CLARIFICATION'.

Output JSON Structure:
{
  "intent": "SEARCH_FLIGHT" | "BOOK_FLIGHT" | "CLARIFICATION",
  "parameters": {
    "origin": "CITY_OR_IATA_CODE" (or null),
    "destination": "CITY_OR_IATA_CODE" (or null),
    "departure_date": "YYYY-MM-DD" (or null)
  }
}
"""

NLG_SYSTEM_PROMPT = """
You are a conversational, friendly, and helpful travel agent.
Your task is to respond to the user based on the context provided.

- Always be friendly and use a natural, engaging tone.
- If the NLU result has missing parameters (e.g., 'origin' is null), politely ask for the *one* missing piece of information.
- If 'task_results' contains successful results (e.g., {"item_id": "AF123", "price": 450.00}):
    - Present the best result clearly.
    - ALWAYS finish by asking a confirmation question to book it.
    - (Example: "I found an Air France flight for 450.00€. Would you like me to book it?")
"""

class AgentClient:
    """
    The 'Brain' of the Agent (v1.2).
    Manages keys, LLM calls, intent routing, and task signing.
    """

    def __init__(self):
        """Initializes the client and loads Zero-Trust assets."""
        logging.info("Initializing Agent Client v1.2 (The Brain)...") # v1.2

        # --- 1. Load Trust Assets (Keys) ---
        private_key_pem = os.environ.get("AGENT_PRIVATE_KEY")
        if not private_key_pem:
            logging.error("FATAL: AGENT_PRIVATE_KEY environment variable not set.")
            raise EnvironmentError("AGENT_PRIVATE_KEY must be set for signing.")

        try:
            self.agent_private_key = serialization.load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None
            )
            logging.info("Agent Private Key object loaded successfully.")
        except Exception as e:
            logging.error(f"FATAL: Could not parse AGENT_PRIVATE_KEY PEM: {e}")
            raise

        self.agent_public_key_pem = os.environ.get("AGENT_PUBLIC_KEY")
        if not self.agent_public_key_pem:
            logging.error("FATAL: AGENT_PUBLIC_KEY environment variable not set.")
            raise EnvironmentError("AGENT_PUBLIC_KEY must be set for directory registration.")

        # --- 2. Load Model Access Key (LLM - P-1) ---
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not self.gemini_api_key:
            logging.error("FATAL: GEMINI_API_KEY environment variable not set.")
            raise EnvironmentError("GEMINI_API_KEY must be set for LLM access.")

        # --- P-1 & T-5.6 FIX: Add error handling for LLM initialization ---
        try:
            genai.configure(api_key=self.gemini_api_key)

            nlu_config = {"temperature": 0.0, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
            self.llm_nlu = genai.GenerativeModel(
                model_name="gemini-2.5-pro", # T-5.7 Fix
                system_instruction=NLU_SYSTEM_PROMPT
            )

            nlg_config = {"temperature": 0.7, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
            self.llm_nlg = genai.GenerativeModel(
                model_name="gemini-2.5-pro", # T-5.7 Fix
                system_instruction=NLG_SYSTEM_PROMPT
            )
            logging.info("Gemini NLU and NLG models initialized successfully.")
        except Exception as e:
            # If this fails (e.g., bad API key, API not enabled),
            # we must raise an error to stop the container.
            logging.error(f"FATAL: Failed to initialize Gemini models: {e}")
            raise EnvironmentError(f"Gemini model initialization failed: {e}")
        # --- Fin P-1 / T-5.6 ---

        # --- 3. Load Manifest and Agent ID (Phase 2) ---
        self.manifest = self._load_manifest_locally()
        self.agent_id = self.manifest.get("agent_id", "unknown_agent")
        logging.info(f"Agent ID configured: {self.agent_id}")

        # --- 4. Load Trust Directory Config (P-0 & P-3) ---
        self.trust_directory_url = os.environ.get("TRUST_DIRECTORY_URL")
        self.directory_admin_key = os.environ.get("DIRECTORY_ADMIN_KEY")

        if not self.trust_directory_url:
            logging.warning("TRUST_DIRECTORY_URL not set. Skipping directory registration.")
        elif not self.directory_admin_key:
            logging.warning("DIRECTORY_ADMIN_KEY not set. Skipping directory registration.")
        else:
            self._register_with_trust_directory()

    def _load_manifest_locally(self) -> Dict[str, Any]:
        """Loads the manifest from disk (used to retrieve the agent_id)."""
        try:
            manifest_path = Path(__file__).parent / "agent-manifest.json"
            with manifest_path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"FATAL: Could not load manifest locally: {e}")
            raise

    def _register_with_trust_directory(self):
        """
        P-0 / P-3: Publishes identity to the Trust Directory on startup
        using the required Admin Key.
        """
        logging.info(f"Registering agent {self.agent_id} with Trust Directory at {self.trust_directory_url}...")

        endpoint = f"{self.trust_directory_url}/api/v1/register"
        payload = {
            "agent_id": self.agent_id,
            "public_key": self.agent_public_key_pem,
            "algorithm": "Ed25519"
        }
        headers = { "X-Admin-Key": self.directory_admin_key }

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=5)
            if response.status_code == 200 or response.status_code == 201:
                logging.info(
                    f"Successfully registered/updated identity: {response.json().get('message')}")
            else:
                logging.error(
                    f"Failed to register with Trust Directory. Status: {response.status_code}, Body: {response.text}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Could not connect to Trust Directory at {endpoint}: {e}")

    # --- P-1.A: NLU Call ---
    def _call_llm_nlu(self, user_input: str, state: dict) -> dict:
        """Calls the Gemini NLU model to get a structured JSON intent."""
        logging.info(f"Calling NLU with input: '{user_input}'")
        try:
            prompt = f"""
            "conversation_state": {json.dumps(state, indent=2)},
            "user_input": "{user_input}"
            """
            response = self.llm_nlu.generate_content(prompt)

            json_response = response.text.strip().replace("```json", "").replace("```", "")
            nlu_result = json.loads(json_response)

            logging.info(f"NLU returned intent: {nlu_result.get('intent')}")
            return nlu_result
        except Exception as e:
            logging.error(f"NLU parsing failed: {e}. Raw response: {response.text if 'response' in locals() else 'N/A'}")
            return {"intent": "CLARIFICATION", "parameters": {}} # Fallback

    # --- P-1.A: NLG Call ---
    def _call_llm_nlg(self, nlu_result: dict, task_results: Optional[dict] = None) -> str:
        """Calls the Gemini NLG model to generate a human-readable response."""
        logging.info(f"Calling NLG for intent: {nlu_result.get('intent')}")
        try:
            prompt = f"""
            "nlu_result": {json.dumps(nlu_result, indent=2)},
            "task_results": {json.dumps(task_results, indent=2) if task_results else "null"}
            """
            response = self.llm_nlg.generate_content(prompt)
            logging.info("NLG call successful.")
            return response.text.strip()
        except Exception as e:
            logging.error(f"NLG call failed: {e}")
            return "I'm sorry, I encountered an error while processing my response." # Fallback

    # --- P-1.B: Task Preparation ---
    # SPRINT V1.2 (T-6.1) - This is now the entry point for real task logic

    def _prepare_search_task(self, parameters: dict) -> (dict, dict):
        """Prepares the task data for a SEARCH_FLIGHT intent."""
        logging.info("Preparing SEARCH_FLIGHT task.")

        # 1. Define the task for the external orchestrator
        task_data = {
            "task_name": "SEARCH_FLIGHT",
            "agent_id": self.agent_id,
            "timestamp": int(time.time()),
            "parameters": parameters # Pass the NLU parameters (origin, dest, date)
        }

        # 2. (SPRINT V1.2) Call the real 3rd-party API
        # This replaces the old mock.
        task_results = self._call_flight_api(parameters)

        return task_data, task_results

    def _prepare_book_task(self, parameters: dict) -> (dict, dict):
        """Prepares the task data for a BOOK_FLIGHT intent."""
        logging.info("Preparing BOOK_FLIGHT task.")
        task_data = {
            "task_name": "BOOK_FLIGHT",
            "agent_id": self.agent_id,
            "timestamp": int(time.time()),
            "parameters": parameters
        }
        # TODO (Sprint v1.2): Call the real booking API
        mock_task_results = {
            "status": "BOOKING_CONFIRMED",
            "confirmation_code": "XYZ789"
        }
        return task_data, mock_task_results

    def _prepare_chat_task(self) -> (dict, dict):
        """Prepares a simple chat response task."""
        logging.info("Preparing CHAT_TURN task.")
        task_data = {
            "task_name": "CHAT_TURN_RESPONSE",
            "agent_id": self.agent_id,
            "timestamp": int(time.time()),
            "message": "User needs clarification."
        }
        return task_data, None

    # --- SPRINT V1.2 (T-6.1): New function for 3rd Party API ---
    def _call_flight_api(self, parameters: dict) -> dict:
        """
        Simulates calling a real 3rd party API (e.g., Amadeus, Google Flights).
        This is where the agent's *real* specialized knowledge lives.
        """
        logging.info(f"Calling 3rd Party Flight API (Simulated) with parameters: {parameters}")

        # In a real implementation:
        # 1. We would need a new secret (e.g., AMADEUS_API_KEY)
        # 2. We would use 'requests' to call the external API
        # 3. We would handle errors from that API (e.g., 404, 503)

        # For Sprint v1.2, we just return the same mock data as before,
        # but it's now correctly isolated from the main logic.
        mock_task_results = {
            "results": [
                {"item_id": "AF123", "price": 450.00, "airline": "Air France"}
            ]
        }
        return mock_task_results

    # --- P-4: Real Signing ---
    def _sign_task(self, task_data: Dict[str, Any]) -> str:
        """Generates a real cryptographic Ed25519 signature (Base64-encoded)."""
        try:
            canonical_task = json.dumps(task_data, sort_keys=True, separators=(',', ':'))
            task_bytes = canonical_task.encode('utf-8')
            logging.info(f"Signing canonical task: {canonical_task}")

            signature_bytes = self.agent_private_key.sign(task_bytes)
            signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')

            return signature_b64
        except Exception as e:
            logging.error(f"Error during task signing: {e}", exc_info=True)
            return "signing_error:could_not_generate_signature"

    # --- P-1.B: Main Orchestration ---
    def process_chat_turn(self, user_input: str, conversation_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main function (P-1 Refactor).
        Orchestrates the NLU -> Routing -> Tasking -> NLG flow.
        """
        logging.info(f"Processing turn v1.2 for Agent ID {self.agent_id}...")

        # 1. Call NLU (P-1.A)
        nlu_result = self._call_llm_nlu(user_input, conversation_state)

        # 2. Route based on Intent (P-1.B)
        intent = nlu_result.get("intent", "CLARIFICATION")
        parameters = nlu_result.get("parameters", {})

        task_data = {}
        task_results = None # This is the *result* of the task

        if intent == "SEARCH_FLIGHT":
            task_data, task_results = self._prepare_search_task(parameters)
        elif intent == "BOOK_FLIGHT":
            task_data, task_results = self._prepare_book_task(parameters)
        elif intent == "CLARIFICATION":
            task_data, task_results = self._prepare_chat_task()
        else:
            logging.warning(f"Unknown intent: {intent}. Defaulting to CLARIFICATION.")
            task_data, task_results = self._prepare_chat_task()

        # 3. Sign the dynamically created task (P-4)
        signature = self._sign_task(task_data)

        # 4. Generate human response (P-1.A)
        # The NLG brain generates a response based on the NLU intent *and* the task results.
        response_text = self._call_llm_nlg(nlu_result, task_results)

        # 5. Construct Final Signed Response (P-4)
        signed_response = {
            "new_state": nlu_result, # The NLU result becomes the new state
            "response_text": response_text,
            "signed_task": {
                "task": task_data,
                "signature": signature,
                "algorithm": "Ed25519"
            }
        }
        return signed_response

