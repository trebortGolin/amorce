import os
import json
import logging
import requests
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import time

# --- P-1: LLM Import ---
import google.generativeai as genai

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

# --- Global Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- P-1: LLM System Prompts (Tâche 1.A) ---
# (Extraits de l'analyse du bytecode, comme demandé par le brief)

NLU_SYSTEM_PROMPT = """
You are an expert NLU (Natural Language Understanding) agent for a travel agency.
Your sole task is to update a JSON object based on the user's request.
Respond with NOTHING but the final JSON.

You will receive:
1.  "Previous JSON State": The state of the conversation (can be empty {}).
2.  "Current User Request": What the user just said.

Your rules:
- Identify the user's intent: 'SEARCH_FLIGHT', 'SEARCH_HOTEL', 'BOOK_ITEM', or 'CLARIFICATION'.
- If the request is a *new* search (e.g., "Find me a hotel in Paris"),
  ignore the previous state and create a NEW, complete JSON for this intent.
- If the user request is a *response* (e.g., "From Paris", "on Dec 15th"),
  USE the previous JSON state and ONLY ADD or MODIFY the information provided. The intent should be 'CLARIFICATION' or the one from the previous state.
- If the user confirms a booking (e.g., "yes", "book it", "that's perfect, confirm"),
  detect the 'BOOK_ITEM' intent.
- Always report the booking_context from the previous state.

Output JSON Structure:
{
  "intent": "SEARCH_FLIGHT" | "SEARCH_HOTEL" | "BOOK_ITEM" | "CLARIFICATION",
  "parameters": {
    "location": "CITY" (or null),
    "departure_date": "YYYY-MM-DD" (or null),
    "origin": "CITY_OR_IATA_CODE" (or null),
    "destination": "CITY_OR_IATA_CODE" (or null),
    "check_in_date": "YYYY-MM-DD" (or null),
    "check_out_date": "YYYY-MM-DD" (or null)
  },
  "booking_context": {
    "item_to_book": { "type": "flight" | "hotel" | null, "id": "ITEM_ID", "price": 123.45 },
    "is_confirmed": false
  }
}
"""

NLG_SYSTEM_PROMPT = """
You are a conversational, friendly, and helpful travel agent.
Your task is to respond to the user based on the context provided.

- Always be friendly and use a natural, engaging tone.
- If the conversation state is incomplete (e.g., 'SEARCH_FLIGHT' intent with no 'origin'), politely ask for the single missing piece of information.

- If 'task_results' contains an error (e.g., {"error": "NO_RESULTS"}):
    - Acknowledge the search but apologize for the lack of results.
    - If the error is 'NO_RESULTS', suggest searching again with a slightly different query or date.
    - If the error is 'SERVICE_ERROR', apologize and suggest retrying later or choosing an alternative service.

- If 'task_results' contains successful results (e.g., flight at 650 EUR):
    - Present the best result clearly.
    - ALWAYS finish by asking a confirmation question to book it.
    - (Example: "I found an Air France flight for 650€. Would you like me to book it?")

- If a booking was just confirmed (task_results status is "BOOKING_CONFIRMED"):
    - Confirm the booking to the user and include the confirmation code.
    - (Example: "It's done! Your flight to Montreal is confirmed. Your code is XYZ123.")
"""


# --- Fin des Prompts P-1 ---


class AgentClient:
    """
    The 'Brain' of the Agent (v1.1 - P-0 and P-1).
    - P-0: Sends DIRECTORY_ADMIN_KEY for secure registration.
    - P-1: Implements real LLM NLU/NLG calls.
    """

    def __init__(self):
        """Initializes the client and loads Zero-Trust assets."""
        logging.info("Initializing Agent Client v1.1 (The Brain)...")

        # 1. Load Trust Assets (Keys)
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

        # 2. Load Model Access Key (LLM)
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not self.gemini_api_key:
            logging.error("FATAL: GEMINI_API_KEY environment variable not set.")
            raise EnvironmentError("GEMINI_API_KEY must be set for LLM access.")

        # --- P-1: Configure GenAI Client ---
        genai.configure(api_key=self.gemini_api_key)

        nlu_config = {"temperature": 0.0, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
        self.llm_nlu = genai.GenerativeModel(
            model_name="gemini-1.5-flash",  # Utilisons un modèle moderne
            generation_config=nlu_config,
            system_instruction=NLU_SYSTEM_PROMPT
        )

        nlg_config = {"temperature": 0.7, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
        self.llm_nlg = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=nlg_config,
            system_instruction=NLG_SYSTEM_PROMPT
        )
        logging.info("Gemini NLU and NLG models initialized.")
        # --- Fin P-1 ---

        # 3. Load Manifest and Agent ID (Phase 2)
        self.manifest = self._load_manifest_locally()
        self.agent_id = self.manifest.get("agent_id", "unknown_agent")
        logging.info(f"Agent ID configured: {self.agent_id}")

        # 4. Load Trust Directory URL & Admin Key (P-0)
        self.trust_directory_url = os.environ.get("TRUST_DIRECTORY_URL")

        # P-0: Load the new Admin Key for the Directory
        self.directory_admin_key = os.environ.get("DIRECTORY_ADMIN_KEY")

        if not self.trust_directory_url:
            logging.warning("TRUST_DIRECTORY_URL not set. Skipping directory registration.")
        elif not self.directory_admin_key:
            logging.warning("DIRECTORY_ADMIN_KEY not set. Trust Directory registration will fail.")
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
        P-0: Publishes identity to the central Trust Directory
        using the required X-Admin-Key.
        """
        if not self.trust_directory_url or not self.directory_admin_key:
            logging.error("Cannot register with Trust Directory: URL or Admin Key is missing.")
            return

        logging.info(f"Registering agent {self.agent_id} with Trust Directory at {self.trust_directory_url}...")
        endpoint = f"{self.trust_directory_url}/api/v1/register"

        # P-0: Create the required security header
        headers = {
            "X-Admin-Key": self.directory_admin_key,
            "Content-Type": "application/json"
        }

        payload = {
            "agent_id": self.agent_id,
            "public_key": self.agent_public_key_pem,
            "algorithm": "Ed25519"
        }

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=5)
            if response.status_code == 200 or response.status_code == 201:
                logging.info(f"Successfully registered/updated identity: {response.json().get('message')}")
            else:
                logging.error(f"Failed to register. Status: {response.status_code}, Body: {response.text}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Could not connect to Trust Directory at {endpoint}: {e}")

    # --- P-1: Tâche 1.A - Implémentation LLM NLU ---
    def _call_llm_nlu(self, user_input: str, state: dict) -> dict:
        """
        Takes user input and state, calls Gemini NLU, and returns a structured JSON.
        """
        logging.info(f"Calling NLU with input: '{user_input}'")
        nlu_context = f"""
        Previous JSON State:
        {json.dumps(state, indent=2)}
        Current User Request:
        "{user_input}"
        Updated JSON:
        """
        try:
            response = self.llm_nlu.generate_content(nlu_context)

            # Nettoyer la réponse pour obtenir un JSON pur
            json_string = response.text.strip().lstrip("```json").rstrip("```")

            nlu_result = json.loads(json_string)
            logging.info(f"NLU result: {nlu_result.get('intent')}")
            return nlu_result
        except Exception as e:
            logging.error(
                f"NLU parsing failed: {e}. Raw response: {response.text if 'response' in locals() else 'N/A'}")
            return {"intent": "CLARIFICATION", "parameters": {}}  # Fallback

    # --- P-1: Tâche 1.A - Implémentation LLM NLG ---
    def _call_llm_nlg(self, state: dict, task_results: Optional[dict]) -> str:
        """
        Takes the final state and any task results, calls Gemini NLG,
        and returns a natural language response.
        """
        logging.info(f"Calling NLG for intent: {state.get('intent')}")
        nlg_context = f"""
        Current Conversation State (JSON):
        {json.dumps(state, indent=2)}
        Task Results (provided by external tool):
        {json.dumps(task_results, indent=2) if task_results else "null"}
        Your Response:
        """
        try:
            response = self.llm_nlg.generate_content(nlg_context)
            logging.info("NLG response generated successfully.")
            return response.text
        except Exception as e:
            logging.error(f"NLG call failed: {e}")
            return "I'm sorry, I encountered an error while processing my response."

    # --- P-1: Tâche 1.B - Préparation des Tâches ---
    def _prepare_search_task(self, params: dict) -> dict:
        """Prepares the task_data for SEARCH_FLIGHT."""
        logging.info("Preparing SEARCH_FLIGHT task.")
        return {
            "task_name": "SEARCH_FLIGHT",
            "agent_id": self.agent_id,
            "timestamp": int(time.time()),
            "query": f"flight from {params.get('origin')} to {params.get('destination')} on {params.get('departure_date')}"
        }

    def _prepare_book_task(self, params: dict, context: dict) -> dict:
        """Prepares the task_data for BOOK_FLIGHT."""
        logging.info("Preparing BOOK_FLIGHT task.")
        item_to_book = context.get("item_to_book", {})
        return {
            "task_name": "BOOK_FLIGHT",
            "agent_id": self.agent_id,
            "timestamp": int(time.time()),
            "item_id": item_to_book.get("id"),
            "price": item_to_book.get("price")
        }

    def _prepare_chat_task(self, message: str) -> dict:
        """Prepares a simple chat task (no external action)."""
        logging.info("Preparing CHAT_TURN task.")
        return {
            "task_name": "CHAT_TURN_RESPONSE",
            "agent_id": self.agent_id,
            "timestamp": int(time.time()),
            "message": message
        }

    def _sign_task(self, task_data: Dict[str, Any]) -> str:
        """
        PHASE 4: Generates a real cryptographic Ed25519 signature.
        """
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

    # --- P-1: Tâche 1.B - Flux de Processus Principal ---
    def process_chat_turn(self, user_input: str, conversation_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main function (v1.1). Orchestrates NLU, Task Routing, Signing, and NLG.
        """
        logging.info(f"Processing turn v1.1 for Agent ID {self.agent_id}...")

        # --- Step 1: NLU (Tâche 1.A) ---
        nlu_result = self._call_llm_nlu(user_input, conversation_state)

        # Mettre à jour l'état avec le résultat de NLU
        current_state = nlu_result
        intent = current_state.get("intent", "CLARIFICATION")
        params = current_state.get("parameters", {})
        context = current_state.get("booking_context", {})

        # --- Step 2: Task Routing (Tâche 1.B) ---
        task_data = {}
        task_results = None  # Nous n'exécutons pas encore la tâche

        if intent == "SEARCH_FLIGHT":
            # (Dans un vrai SDK, nous exécuterions la recherche ici et obtiendrions des task_results)
            task_data = self._prepare_search_task(params)
            # Simuler des résultats pour que NLG puisse en parler
            task_results = {"results": [{"item_id": "AF123", "price": 450.00}]}

        elif intent == "BOOK_FLIGHT":
            task_data = self._prepare_book_task(params, context)
            # Simuler une confirmation de réservation
            task_results = {"status": "BOOKING_CONFIRMED", "confirmation_code": "XYZ123"}

        elif intent == "CLARIFICATION":
            task_data = self._prepare_chat_task("User needs clarification.")

        else:  # Gérer les intents inconnus
            logging.warning(f"Unknown intent detected: {intent}")
            task_data = self._prepare_chat_task("Unknown intent.")

        # --- Step 3: Task Signing (PHASE 4) ---
        signature = self._sign_task(task_data)

        # --- Step 4: NLG (Tâche 1.A) ---
        # Générer la réponse textuelle basée sur l'état final et les résultats (simulés)
        response_text = self._call_llm_nlg(current_state, task_results)

        # --- Step 5: ATP Response Construction ---
        signed_response = {
            "new_state": current_state,
            "response_text": response_text,
            "signed_task": {
                "task": task_data,
                "signature": signature,
                "algorithm": "Ed25519"
            }
        }
        return signed_response


# --- Entry Point (Not executed by the Orchestrator, but for testing) ---
if __name__ == '__main__':
    """
    Allows for local testing of this client without running the Flask orchestrator.
    """
    try:
        # We must generate a real key pair for testing
        pk = ed25519.Ed25519PrivateKey.generate()
        priv_key_pem = pk.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

        pub_key_pem = pk.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        # Set mock environment variables
        os.environ["AGENT_PRIVATE_KEY"] = priv_key_pem
        os.environ["AGENT_PUBLIC_KEY"] = pub_key_pem
        os.environ["GEMINI_API_KEY"] = "YOUR_GEMINI_KEY_HERE"  # REMPLACEZ-MOI
        os.environ["TRUST_DIRECTORY_URL"] = "http://127.0.0.1:8080"  # Notre annuaire FastAPI local
        os.environ["DIRECTORY_ADMIN_KEY"] = "dev_admin_key_12345"  # Clé P-0

        if os.environ["GEMINI_API_KEY"] == "YOUR_GEMINI_KEY_HERE":
            logging.warning("=" * 50)
            logging.warning("TESTING: GEMINI_API_KEY n'est pas définie. Le test local va échouer.")
            logging.warning("Veuillez la définir dans votre environnement pour tester localement.")
            logging.warning("=" * 50)

        client = AgentClient()
        test_response = client.process_chat_turn("find me a flight from Paris to New York on 2025-12-20", {})

        logging.info("--- Test Run 1 (Search) Successful ---")
        print(json.dumps(test_response, indent=2))

        # Test 2 (Booking)
        state = test_response.get("new_state")
        # Simuler que l'orchestrateur ajoute les résultats de la tâche à l'état
        state["booking_context"] = {"item_to_book": {"id": "AF123", "price": 450.00}, "is_confirmed": True}

        test_response_2 = client.process_chat_turn("Yes, book it", state)
        logging.info("--- Test Run 2 (Book) Successful ---")
        print(json.dumps(test_response_2, indent=2))


    except EnvironmentError as e:
        logging.critical(f"Client Test Failed: {e}")
    except Exception as e:
        logging.critical(f"A general error occurred during test run: {e}", exc_info=True)
