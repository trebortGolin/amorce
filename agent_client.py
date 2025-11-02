import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# We import the required cryptography dependencies
# For a Zero-Trust agent, this library is essential for Ed25519
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

# --- Global Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AgentClient:
    """
    The 'Brain' of the Agent. Manages private key initialization,
    the LLM logic (simulated here), and task signing.
    """

    def __init__(self):
        """Initializes the client and loads Zero-Trust assets."""
        logging.info("Initializing Agent Client (The Brain)...")

        # 1. Load the private key for signing (Zero-Trust)
        private_key_pem = os.environ.get("AGENT_PRIVATE_KEY")
        if not private_key_pem:
            logging.error("FATAL: AGENT_PRIVATE_KEY environment variable not set.")
            raise EnvironmentError("AGENT_PRIVATE_KEY must be set for signing.")

        # The actual code would load the Ed25519 key from the PEM format
        # self.private_key = serialization.load_pem_private_key(
        #     private_key_pem.encode('utf-8'),
        #     password=None, # The key is not password protected in this reference setup
        #     backend=default_backend()
        # )
        self.agent_private_key = private_key_pem  # Storing raw PEM for simulation
        logging.info("Agent Private Key loaded successfully (Simulated).")

        # 2. Load the model access key (LLM)
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not self.gemini_api_key:
            logging.error("FATAL: GEMINI_API_KEY environment variable not set.")
            raise EnvironmentError("GEMINI_API_KEY must be set for LLM access.")

        # 3. Load the Manifest to retrieve the agent_id (Phase 2 Compliance)
        self.manifest = self._load_manifest_locally()
        self.agent_id = self.manifest.get("agent_id", "unknown_agent")
        logging.info(f"Agent ID configured: {self.agent_id}")

    def _load_manifest_locally(self) -> Dict[str, Any]:
        """Loads the manifest from disk (used to retrieve the agent_id)."""
        try:
            manifest_path = Path(__file__).parent / "agent-manifest.json"
            with manifest_path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"FATAL: Could not load manifest locally: {e}")
            raise

    def _sign_task(self, task_data: Dict[str, Any]) -> str:
        """
        Generates the cryptographic Ed25519 signature of the task.
        This implementation is simulated (Phase 1).
        """
        # In production:
        # 1. task_data would be serialized into a canonical format (e.g., sorted JSON).
        # 2. task_bytes = canonical_json_dump(task_data).encode('utf-8')
        # 3. signature = self.private_key.sign(task_bytes)

        # Simulation:
        return f"mock_signature_for_{self.agent_id}_agent"

    def process_chat_turn(self, user_input: str, conversation_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main function. Handles NLU, NLG, and returns the signed task.
        """
        logging.info(f"Processing turn for Agent ID {self.agent_id} with input: {user_input}")

        # --- Step 1: LLM Logic (Simulated) ---
        # The actual code would call the Gemini API here.
        # NLU_result = self._call_llm_for_nlu(user_input, self.manifest)

        # --- Step 2: Task Creation ---
        # Based on the NLU, we create the task to be signed.
        task_data = {
            "task_name": "CHAT_TURN_RESPONSE",
            "message": f"Acknowledged. Agent {self.agent_id} is online and processing.",
            "agent_id": self.agent_id,  # **PHASE 2 UPDATE**
            "timestamp": "2025-11-01T20:00:00Z"
        }

        # --- Step 3: Task Signing ---
        signature = self._sign_task(task_data)

        # --- Step 4: ATP Response Construction ---
        mock_signed_response = {
            "new_state": conversation_state,
            "response_text": "I am unable to process that specific request at this time, but I am online and ready.",
            "signed_task": {
                "task": task_data,
                "signature": signature,
                "algorithm": "Ed25519"
            }
        }
        return mock_signed_response


# --- Entry Point (Not executed by the Orchestrator, but for testing) ---
if __name__ == '__main__':
    try:
        client = AgentClient()
        test_response = client.process_chat_turn("Hello, what is your name?", {"user_name": "Robert"})
        logging.info("Test Run Successful.")
        print(json.dumps(test_response, indent=2))
    except EnvironmentError as e:
        logging.critical(f"Client Test Failed: {e}")
