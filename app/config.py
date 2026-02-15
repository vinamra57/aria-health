import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto")
LLM_DEFAULT_TIER = os.getenv("LLM_DEFAULT_TIER", "fast")
LLM_MODEL_FAST = os.getenv("LLM_MODEL_FAST", "")
LLM_MODEL_STANDARD = os.getenv("LLM_MODEL_STANDARD", "")
LLM_MODEL_HIGH = os.getenv("LLM_MODEL_HIGH", "")

# Demo/Debug mode (explicit)
DUMMY_MODE = os.getenv("DUMMY_MODE", "false").lower() in ("1", "true", "yes", "on")

# Minimal flow: only voice → transcript and transcript → NEMSIS → DB. No Synthea, GP call, hospital summary, or dummy vitals.
SIMPLE_STREAM = os.getenv("SIMPLE_STREAM", "true").lower() in ("1", "true", "yes", "on")
VOICE_DUMMY = os.getenv("VOICE_DUMMY", "false").lower() in ("1", "true", "yes", "on")
GP_CALLS_ENABLED = os.getenv("GP_CALLS_ENABLED", "true").lower() in ("1", "true", "yes", "on")

DATABASE_PATH = os.getenv("DATABASE_PATH", "relay.db")

DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_MAX_CONNECTIONS = int(os.getenv("DATABASE_MAX_CONNECTIONS", "5"))
# Set true to seed demo-stemi, demo-stroke, demo-trauma (pre-filled NEMSIS). False = only real voice→NEMSIS.
SEED_DEMO_CASES = os.getenv("SEED_DEMO_CASES", "false").lower() == "true"

BASE_DIR = Path(__file__).resolve().parent.parent
GP_DOCUMENT_PATH = os.getenv(
    "GP_DOCUMENT_PATH",
    str(BASE_DIR / "data" / "doc" / "Medical Record.pdf"),
)
# Patient name this document is for (case-insensitive). Other patients get "No data found from the GP."
GP_DOCUMENT_PATIENT_NAME = (os.getenv("GP_DOCUMENT_PATIENT_NAME", "").strip() or None)
GP_DOCUMENT_DELAY_SECONDS = int(os.getenv("GP_DOCUMENT_DELAY_SECONDS", "60"))
GP_CALL_PENDING_SECONDS = int(os.getenv("GP_CALL_PENDING_SECONDS", "8"))

# Perplexity Sonar API (GP contact resolution)
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")

# Optional: fixed patient URL for testing. If unset, we do real name-based lookup on FHIR/Synthea.
FHIR_DEMO_PATIENT_URL = os.getenv("FHIR_DEMO_PATIENT_URL", "").strip() or None

# Twilio (outbound voice calls)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# ElevenLabs Conversational AI (voice agent)
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "")
ELEVENLABS_PHONE_NUMBER_ID = os.getenv("ELEVENLABS_PHONE_NUMBER_ID", "")

# Hospital callback number for GP voicemail
HOSPITAL_CALLBACK_NUMBER = os.getenv("HOSPITAL_CALLBACK_NUMBER", "+1-555-0100")

# Email for GPs to send medical records to
RECORDS_EMAIL = os.getenv("RECORDS_EMAIL", "records_relay@treehacks.com")

# Number for GP to call back if they need to reach Relay ("if you want to get back, call this number")
RELAY_CALLBACK_NUMBER = os.getenv("RELAY_CALLBACK_NUMBER", "123450")

# GCP (optional)
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_PUBSUB_TOPIC = os.getenv("GCP_PUBSUB_TOPIC", "")
GCP_PUBSUB_SUBSCRIPTION_PREFIX = os.getenv("GCP_PUBSUB_SUBSCRIPTION_PREFIX", "relay-events")
