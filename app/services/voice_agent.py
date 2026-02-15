"""Voice call agent using ElevenLabs Conversational AI + Twilio.

Places outbound calls to GP practices via the ElevenLabs native Twilio
integration. The ElevenLabs agent handles the conversation script, voicemail
detection, and response capture.
"""

import logging

import httpx

from app.config import (
    ELEVENLABS_AGENT_ID,
    ELEVENLABS_API_KEY,
    ELEVENLABS_PHONE_NUMBER_ID,
    GP_CALLS_ENABLED,
    HOSPITAL_CALLBACK_NUMBER,
    RECORDS_EMAIL,
    RELAY_CALLBACK_NUMBER,
)

logger = logging.getLogger(__name__)

ELEVENLABS_OUTBOUND_URL = "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"
ELEVENLABS_TIMEOUT = 30.0


async def place_gp_call(
    phone_number: str,
    patient_name: str,
    patient_age: str | None = None,
    patient_gender: str | None = None,
    patient_address: str | None = None,
    patient_dob: str | None = None,
    hospital_callback: str | None = None,
    case_id: str | None = None,
    chief_complaint: str | None = None,
    records_email: str | None = None,
) -> dict:
    """Place an outbound call to a GP practice via ElevenLabs + Twilio.

    Returns:
        Dict with keys: call_sid, conversation_id, status
    """
    if not GP_CALLS_ENABLED:
        logger.info("GP_CALLS_ENABLED=false, skipping outbound call")
        return {
            "call_sid": None,
            "conversation_id": None,
            "status": "skipped",
            "transcript": "GP calls disabled by configuration.",
        }

    if not ELEVENLABS_API_KEY:
        logger.info("ELEVENLABS_API_KEY not set; skipping real GP call")
        return {"call_sid": None, "conversation_id": None, "status": "skipped", "transcript": "GP call skipped: API not configured."}

    if not ELEVENLABS_AGENT_ID:
        logger.error("ELEVENLABS_AGENT_ID not set, cannot place GP call")
        return {"call_sid": None, "conversation_id": None, "status": "error",
                "error": "ELEVENLABS_AGENT_ID not configured"}

    if not ELEVENLABS_PHONE_NUMBER_ID:
        logger.error("ELEVENLABS_PHONE_NUMBER_ID not set, cannot place GP call")
        return {"call_sid": None, "conversation_id": None, "status": "error",
                "error": "ELEVENLABS_PHONE_NUMBER_ID not configured"}

    callback = hospital_callback or HOSPITAL_CALLBACK_NUMBER
    situation = chief_complaint or "a medical emergency"
    email = records_email or RECORDS_EMAIL
    relay_callback = RELAY_CALLBACK_NUMBER

    # Reason for call: patient en route to hospital + chief complaint / expected problem
    reason_for_call = (
        f"The patient is on the way to the hospital. Reason for transport: {situation}."
    )

    # Dynamic variables fill {{placeholders}} in the ElevenLabs agent prompt.
    # See docs/GP_CALL_AGENT_PROMPT.md for the script to paste into your ElevenLabs agent.
    payload = {
        "agent_id": ELEVENLABS_AGENT_ID,
        "agent_phone_number_id": ELEVENLABS_PHONE_NUMBER_ID,
        "to_number": phone_number,
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "patient_name": patient_name,
                "patient_age": patient_age or "unknown",
                "patient_gender": patient_gender or "unknown",
                "patient_address": patient_address or "unknown",
                "patient_dob": patient_dob or "unknown",
                "chief_complaint": situation,
                "reason_for_call": reason_for_call,
                "hospital_callback": callback,
                "records_email": email,
                "relay_callback_number": relay_callback,
                "case_id": case_id or "unknown",
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=ELEVENLABS_TIMEOUT) as client:
            resp = await client.post(
                ELEVENLABS_OUTBOUND_URL,
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()

        data = resp.json()
        result = {
            "call_sid": data.get("callSid"),
            "conversation_id": data.get("conversation_id"),
            "status": "initiated",
        }
        logger.info(
            "GP call initiated: call_sid=%s, conversation_id=%s, to=%s",
            result["call_sid"], result["conversation_id"], phone_number,
        )
        return result

    except httpx.HTTPStatusError as e:
        logger.error(
            "ElevenLabs outbound call failed (HTTP %s): %s",
            e.response.status_code, e.response.text[:500],
        )
        return {"call_sid": None, "conversation_id": None, "status": "error",
                "error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        logger.error("GP call failed: %s", e)
        return {"call_sid": None, "conversation_id": None, "status": "error",
                "error": str(e)}


