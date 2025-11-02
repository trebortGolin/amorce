import os
import json
import logging
from functools import wraps
from pathlib import Path
from typing import Callable, Any, Optional, Union

from flask import Flask, request, jsonify

# --- Configuration Globale ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")


# --- Initialisation de l'Agent Client (Simulé) ---
# Dans un projet réel, agent_client serait importé. Ici, on simule l'interface.
class AgentClientSimulator:
    def __init__(self):
        # The agent_client requires the private key (for signing) and the Gemini key (for the LLM call)
        # This orchestrator only ensures the variables are present. The client handles the logic.
        required_vars = ["AGENT_PRIVATE_KEY", "GEMINI_API_KEY"]
        for var in required_vars:
            if not os.environ.get(var):
                logging.error(f"FATAL: Missing required environment variable: {var}")
                raise EnvironmentError(f"Missing required environment variable: {var}")
        logging.info("Agent client dependencies checked.")

    def process_chat_turn(self, user_input: str, conversation_state: dict) -> dict:
        """Simulates the agent client processing the NLU and generating a signed task."""
        # This is where the actual LLM call and signing logic (from agent_client.py) would be.
        # For the orchestrator, we return a mock signed response for demonstration purposes.
        # Note: The real implementation must generate a valid Ed25519 signature.

        # Simulating a basic task response
        task_data = {
            "task_name": "CHAT_TURN",
            "message": "Acknowledged. The service is running on ATP SDK v2.0.",
            "agent_id": AGENT_MANIFEST.get('agent_id')
        }

        mock_signed_response = {
            "new_state": conversation_state,
            "response_text": "I am unable to process that specific request at this time, but I am online and ready.",
            "signed_task": {
                "task": task_data,
                "signature": "mock_signature_for_amorce_io_default_agent",
                "algorithm": "Ed25519"
            }
        }
        return mock_signed_response

    def get_manifest(self) -> dict:
        """Returns the full agent manifest."""
        return AGENT_MANIFEST


# --- Fonctions de Chargement et de Sécurité ---

def load_agent_manifest() -> dict:
    """
    Loads the agent manifest file and performs basic integrity checks.
    Phase 2 Compliance: Checks for the 'agent_id' field.
    """
    try:
        manifest_path = Path(__file__).parent / "agent-manifest.json"
        if not manifest_path.exists():
            logging.error("FATAL: agent-manifest.json not found in the application root.")
            raise FileNotFoundError(f"Manifest not found at {manifest_path}")

        with manifest_path.open('r', encoding='utf-8') as f:
            manifest = json.load(f)

        # Validation for Phase 2: Check for the required 'agent_id' field
        if "agent_id" not in manifest:
            logging.error("Manifest missing required 'agent_id' field. Phase 2 compliance failed.")
            raise ValueError("Manifest is invalid: Missing 'agent_id'.")

        logging.info(f"Manifest loaded successfully. Agent ID: {manifest.get('agent_id')}")
        return manifest

    except json.JSONDecodeError as e:
        logging.error(f"Error parsing agent-manifest.json: {e}")
        raise


def require_api_key(f: Callable) -> Callable:
    """
    Decorateur de sécurité Zero-Trust. Vérifie la présence et la validité de AGENT_API_KEY.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Union[Any, tuple[Any, int]]:
        if not AGENT_API_KEY:
            logging.error("FATAL: AGENT_API_KEY is not set in environment.")
            return jsonify({"error": "Server misconfiguration"}), 500

        provided_key = request.headers.get('X-ATP-Key')

        if not provided_key or provided_key != AGENT_API_KEY:
            logging.warning(f"Unauthorized access attempt. Key provided: {provided_key}")
            # Renvoyer 403 Forbidden est plus sûr pour les tentatives d'accès non autorisées avec une clé invalide
            return jsonify({"error": "Unauthorized"}), 403

        return f(*args, **kwargs)

    return decorated_function


# --- Initialisation de l'Application ---
try:
    # Charger le manifeste avant de démarrer l'application
    AGENT_MANIFEST = load_agent_manifest()
    AGENT_CLIENT = AgentClientSimulator()
    app = Flask(__name__)
    logging.info("Flask Application and Agent Client initialized.")
except (FileNotFoundError, ValueError, EnvironmentError):
    logging.critical("Application failed to initialize due to configuration error.")
    # Si la configuration échoue, l'application ne doit pas démarrer.
    AGENT_MANIFEST = {}
    AGENT_CLIENT = None
    app = Flask(__name__)


    # Route pour indiquer l'échec de la configuration si le serveur démarre quand même
    @app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
    @app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def fatal_error_route(path: str) -> tuple[Any, int]:
        return jsonify({"error": "Service not configured correctly. Check server logs."}), 500

    # Sortir ici si possible dans un environnement de production (ex: Cloud Run)
    # Dans Flask local, on laisse la route d'erreur


# --- Routes d'Application ---

@app.route('/manifest', methods=['GET'])
@require_api_key
def get_manifest_route() -> tuple[Any, int]:
    """Route pour que l'orchestrateur obtienne le manifeste public."""
    return jsonify(AGENT_MANIFEST), 200


@app.route('/chat_turn', methods=['POST'])
@require_api_key
def chat_turn_route() -> tuple[Any, int]:
    """
    Route principale pour le traitement du tour de conversation (NLU).
    Reçoit le user_input et l'état de la conversation.
    """
    if not request.is_json:
        return jsonify({"error": "Missing JSON in request"}), 400

    data = request.get_json()
    user_input = data.get('user_input')
    conversation_state = data.get('conversation_state', {})

    if not user_input:
        return jsonify({"error": "Missing 'user_input' field"}), 400

    try:
        # Déléguer le traitement au AgentClient (le cerveau)
        response = AGENT_CLIENT.process_chat_turn(user_input, conversation_state)
        return jsonify(response), 200
    except Exception as e:
        logging.error(f"Error processing chat turn: {e}")
        return jsonify({"error": "Internal Agent Error", "details": str(e)}), 500


# --- Point d'Entrée (Pour le développement local) ---
if __name__ == '__main__':
    # Cloud Run/Gunicorn/autres serveurs WSGI ne passent pas par ici.
    # Pour le développement local Uvicorn ou Flask natif:
    logging.warning("Running Flask in development mode. Use a proper WSGI server in production.")
    app.run(host='0.0.0.0', port=5000)
