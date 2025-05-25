"""Anki API client for managing flashcards."""

import logging
import subprocess
import time
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

from config import settings

logger = logging.getLogger(__name__)

# Suppress connection warnings during startup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)


class AnkiClient:
    """Client for interacting with Anki via AnkiConnect."""

    def __init__(self):
        self.url = settings.anki_url
        self.deck_name = settings.anki_deck_name
        self.model_name = settings.anki_model_name

        # Configure session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def is_running(self) -> bool:
        """Check if Anki is running and responsive."""
        try:
            response = self.session.get(self.url, timeout=2)
            logger.debug("Anki is running and responding")
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            logger.debug("Anki is not running (connection refused)")
            return False
        except Exception as e:
            logger.debug(f"Anki check failed: {e}")
            return False

    def start(self) -> bool:
        """Start Anki in background."""
        try:
            logger.info("Starting Anki process...")
            subprocess.Popen(
                ['anki'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait for Anki to start (with cleaner logging)
            for i in range(15):  # Increased to 15 seconds
                time.sleep(1)
                if i % 3 == 0:  # Log every 3 seconds
                    logger.info(f"Waiting for Anki to start... ({i+1}s)")
                if self.is_running():
                    logger.info(f"Anki started successfully after {i+1} seconds")
                    return True

            logger.error("Anki failed to start within 15 seconds")
            return False
        except FileNotFoundError:
            logger.error("Anki executable not found. Please ensure Anki is installed.")
            return False
        except Exception as e:
            logger.error(f"Failed to start Anki: {e}")
            return False

    def ensure_running(self) -> bool:
        """Ensure Anki is running, start if necessary."""
        if self.is_running():
            return True
        return self.start()

    def _make_request(self, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a request to AnkiConnect API."""
        data = {
            "action": action,
            "version": 6
        }
        if params:
            data["params"] = params

        try:
            response = self.session.post(
                self.url,
                json=data,
                timeout=settings.sync_timeout
            )
            response.raise_for_status()
            result = response.json()

            if result.get("error"):
                logger.error(f"AnkiConnect error: {result['error']}")
                return {"error": result["error"]}

            return {"result": result.get("result")}
        except Exception as e:
            logger.error(f"Request to Anki failed: {e}")
            return {"error": str(e)}

    def sync(self) -> bool:
        """Trigger Anki sync."""
        logger.info("Triggering Anki sync")
        result = self._make_request("sync")

        if "error" in result:
            logger.error(f"Sync failed: {result['error']}")
            return False

        logger.info("Anki sync completed successfully")
        return True

    def find_notes(self, query: str) -> list:
        """Find notes matching the query."""
        result = self._make_request("findNotes", {"query": query})

        if "error" in result:
            return []

        return result.get("result", [])

    def word_exists(self, word: str) -> bool:
        """Check if word already exists in the deck."""
        logger.info(f"Checking if word '{word}' exists in Anki")

        # Search in the specific deck
        query = f'deck:"{self.deck_name}" Front:"{word}"'
        notes = self.find_notes(query)

        exists = len(notes) > 0
        logger.info(f"Word '{word}' exists: {exists} (found {len(notes)} notes)")
        return exists

    def add_note(self, word: str, content: str) -> Dict[str, Any]:
        """Add a new note to Anki."""
        logger.info(f"Adding card to Anki for word '{word}'")

        params = {
            "note": {
                "deckName": self.deck_name,
                "modelName": self.model_name,
                "fields": {
                    "Front": word,
                    "Back": content
                },
                "options": {
                    "allowDuplicate": False,
                    "duplicateScope": "deck"
                }
            }
        }

        result = self._make_request("addNote", params)

        if "error" in result:
            logger.error(f"Failed to add note: {result['error']}")
            return {"success": False, "error": result["error"]}

        logger.info(f"Successfully added card for word '{word}'")
        return {"success": True, "note_id": result.get("result")}

    def get_deck_stats(self) -> Dict[str, Any]:
        """Get statistics for the current deck."""
        result = self._make_request("getDeckStats", {"decks": [self.deck_name]})

        if "error" in result:
            return {"error": result["error"]}

        return result.get("result", {})