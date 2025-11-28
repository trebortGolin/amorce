"""
Nexus Core Crypto Module (Task 1)
Handles identity management (Ed25519 keys) and cryptographic primitives.
"""

import os
import base64
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Union

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

# Configure logging
logger = logging.getLogger("nexus.crypto")


class IdentityProvider(ABC):
    """Abstract base class for retrieving private keys."""

    @abstractmethod
    def get_private_key(self) -> ed25519.Ed25519PrivateKey:
        pass


class LocalFileProvider(IdentityProvider):
    """Loads a private key from a local PEM file."""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def get_private_key(self) -> ed25519.Ed25519PrivateKey:
        try:
            with open(self.filepath, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
            if not isinstance(private_key, ed25519.Ed25519PrivateKey):
                raise ValueError("Key is not an Ed25519 private key.")
            return private_key
        except Exception as e:
            logger.error(f"Failed to load local key from {self.filepath}: {e}")
            raise


class EnvVarProvider(IdentityProvider):
    """Loads a private key directly from an environment variable string."""

    def __init__(self, env_var_name: str = "AGENT_PRIVATE_KEY"):
        self.env_var_name = env_var_name

    def get_private_key(self) -> ed25519.Ed25519PrivateKey:
        pem_data = os.environ.get(self.env_var_name)
        if not pem_data:
            raise ValueError(f"Environment variable {self.env_var_name} is not set.")

        # Handle cases where newlines are escaped (common in some CI/CD)
        pem_data = pem_data.replace("\\n", "\n")

        try:
            private_key = serialization.load_pem_private_key(
                pem_data.encode("utf-8"),
                password=None
            )
            return private_key
        except Exception as e:
            logger.error(f"Failed to load key from environment variable: {e}")
            raise


class GoogleSecretManagerProvider(IdentityProvider):
    """Loads a private key from Google Secret Manager."""

    def __init__(self, project_id: str, secret_name: str, version: str = "latest"):
        self.project_id = project_id
        self.secret_name = secret_name
        self.version = version

    def get_private_key(self) -> ed25519.Ed25519PrivateKey:
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self.project_id}/secrets/{self.secret_name}/versions/{self.version}"
            response = client.access_secret_version(request={"name": name})
            pem_data = response.payload.data

            private_key = serialization.load_pem_private_key(
                pem_data,
                password=None
            )
            return private_key
        except ImportError:
            logger.error("google-cloud-secret-manager not installed.")
            raise
        except Exception as e:
            logger.error(f"Failed to load key from Secret Manager: {e}")
            raise


class IdentityManager:
    """
    Central class to manage the agent's identity.
    """

    def __init__(self, provider: IdentityProvider):
        self._private_key = provider.get_private_key()
        self._public_key = self._private_key.public_key()

    @property
    def public_key_pem(self) -> str:
        """Returns the public key in PEM format (for registration)."""
        pem_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_bytes.decode("utf-8")

    def sign_data(self, data: bytes) -> str:
        """
        Signs raw bytes and returns a Base64 encoded signature.
        """
        signature = self._private_key.sign(data)
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def verify_signature(public_key_pem: str, data: bytes, signature_b64: str) -> bool:
        """
        Static utility to verify a signature given a public key PEM.
        """
        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode("utf-8")
            )
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                return False

            signature = base64.b64decode(signature_b64)
            public_key.verify(signature, data)
            return True
        except (InvalidSignature, Exception) as e:
            logger.warning(f"Signature verification failed: {e}")
            return False

    @staticmethod
    def get_canonical_json_bytes(payload: dict) -> bytes:
        """
        Returns the canonical JSON byte representation for signing.
        Strict: sort_keys=True, no whitespace.
        """
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':')
        ).encode("utf-8")