import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.database import get_db
from app.models.summary import CaseSummary, HospitalSummary
from app.services.event_bus import event_bus
from app.services.summary import generate_summary, get_summary_for_hospital

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hospital", tags=["hospital"])


@router.get("/summary/{case_id}", response_model=HospitalSummary)
async def get_hospital_summary(case_id: str):
    """Get hospital-facing preparation summary for an incoming EMS patient.

    Returns structured sections so the receiving team can prepare
    resources, staff, and equipment before the patient arrives.
    """
    try:
        return await get_summary_for_hospital(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found") from None


@router.get("/case-summary/{case_id}", response_model=CaseSummary)
async def get_case_summary(
    case_id: str,
    urgency: str = Query("standard", pattern="^(critical|standard|handoff)$"),
):
    """Get a clinical case summary for paramedic/dispatch view.

    Urgency levels:
    - critical: immediate actionable summary
    - standard: comprehensive overview
    - handoff: hospital-ready transfer summary
    """
    try:
        return await generate_summary(case_id, urgency=urgency)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found") from None


@router.get("/active-cases")
async def get_active_cases():
    """Get all active cases with their current NEMSIS data for the dashboard."""
    db = await get_db()
    rows = await db.execute(
        "SELECT id, created_at, status, patient_name, patient_age, patient_gender, "
        "nemsis_data, core_info_complete, gp_response, medical_db_response "
        "FROM cases WHERE status = 'active' ORDER BY created_at DESC"
    )
    cases = await rows.fetchall()
    result = []
    for row in cases:
        nemsis: dict = {}
        try:
            nemsis = json.loads(row["nemsis_data"] or "{}")
        except json.JSONDecodeError:
            pass
        result.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "patient_name": row["patient_name"],
            "patient_age": row["patient_age"],
            "patient_gender": row["patient_gender"],
            "core_info_complete": bool(row["core_info_complete"]),
            "nemsis": nemsis,
        })
    return result


@router.websocket("/ws/hospital")
async def hospital_dashboard_ws(websocket: WebSocket):
    """WebSocket for real-time hospital dashboard updates.

    Hospital staff connects here to receive live updates about all active cases.
    Events include: nemsis_update, downstream_complete.
    """
    await websocket.accept()
    queue = event_bus.subscribe_all()
    logger.info("Hospital dashboard client connected")

    try:
        while True:
            event = await queue.get()
            try:
                await websocket.send_json(event)
            except Exception:
                logger.debug("Failed to send event to hospital client")
                break
    except WebSocketDisconnect:
        logger.info("Hospital dashboard client disconnected")
    except asyncio.CancelledError:
        pass
    finally:
        event_bus.unsubscribe_all(queue)
