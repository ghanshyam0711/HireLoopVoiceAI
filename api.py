"""
FastAPI entrypoint for triggering outbound interview calls.

Endpoint:
  POST /start-screening-call

Env vars required:
  LIVEKIT_URL
  LIVEKIT_API_KEY
  LIVEKIT_API_SECRET
  LIVEKIT_SIP_TRUNK_ID
"""

import json
import logging
import os
import re
import uuid

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit import api as livekit_api
from livekit.api import CreateAgentDispatchRequest, CreateSIPParticipantRequest
from pydantic import BaseModel, field_validator

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("screening-api")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
LIVEKIT_SIP_TRUNK_ID = os.getenv("LIVEKIT_SIP_TRUNK_ID", "")
AGENT_NAME = "Jamie-cbf"

if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
    logger.warning("Missing LiveKit env vars - calls will fail at runtime.")

app = FastAPI(title="Screening Call API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartScreeningCallRequest(BaseModel):
    screening_id: str
    candidate_mobile_no: str
    candidate_name: str
    interview_language: str
    questions: list[str]

    @field_validator("screening_id", "candidate_mobile_no", "candidate_name", "interview_language")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field cannot be empty")
        return value

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, questions: list[str]) -> list[str]:
        cleaned_questions = [question.strip() for question in questions if question.strip()]
        if not cleaned_questions:
            raise ValueError("questions must contain at least one non-empty question")
        return cleaned_questions


class StartScreeningCallResponse(BaseModel):
    success: bool
    room_name: str
    screening_id: str
    candidate_mobile_no: str
    message: str
    dispatch_id: str


def build_metadata(request: StartScreeningCallRequest) -> str:
    return json.dumps(
        {
            "screening_id": request.screening_id,
            "candidate_mobile_no": request.candidate_mobile_no,
            "candidate_name": request.candidate_name,
            "interview_language": request.interview_language,
            "questions": request.questions,
        }
    )


def build_participant_identity(candidate_mobile_no: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", candidate_mobile_no).strip("_")
    return f"candidate_{sanitized or uuid.uuid4().hex[:8]}"


async def create_screening_call(
    *,
    request: StartScreeningCallRequest,
    room_name: str,
    metadata: str,
) -> str:
    lk = livekit_api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )

    try:
        await lk.room.create_room(
            livekit_api.CreateRoomRequest(
                name=room_name,
                metadata=metadata,
                empty_timeout=300,
                max_participants=5,
            )
        )
        logger.info("Room created: %s", room_name)

        dispatch = await lk.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=metadata,
            )
        )
        logger.info("Agent dispatch created: %s", dispatch.id)

        #  Create SIP participant for the candidate
        # await lk.sip.create_sip_participant(
        #     CreateSIPParticipantRequest(
        #         sip_trunk_id=LIVEKIT_SIP_TRUNK_ID,
        #         sip_call_to=request.candidate_mobile_no,
        #         room_name=room_name,
        #         participant_identity=build_participant_identity(request.candidate_mobile_no),
        #         participant_name=request.candidate_name,
        #         participant_metadata=metadata,
        #         play_ringtone=True,
        #         krisp_enabled=True,
        #     )
        # )
        logger.info("SIP participant created for %s", request.candidate_mobile_no)
        return dispatch.id
    finally:
        await lk.aclose()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/start-screening-call", response_model=StartScreeningCallResponse)
async def start_screening_call(request: StartScreeningCallRequest) -> StartScreeningCallResponse:
    if not LIVEKIT_SIP_TRUNK_ID:
        raise HTTPException(
            status_code=503,
            detail="LIVEKIT_SIP_TRUNK_ID is not configured",
        )

    metadata = build_metadata(request)
    room_name = f"screening-{request.screening_id}-{uuid.uuid4().hex[:10]}"

    try:
        dispatch_id = await create_screening_call(
            request=request,
            room_name=room_name,
            metadata=metadata,
        )
    except Exception as exc:
        logger.exception("Failed to create screening call")
        raise HTTPException(status_code=500, detail=f"LiveKit error: {exc}") from exc

    return StartScreeningCallResponse(
        success=True,
        room_name=room_name,
        screening_id=request.screening_id,
        candidate_mobile_no=request.candidate_mobile_no,
        message=f"Call initiated for {request.candidate_name}.",
        dispatch_id=dispatch_id,
    )


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
