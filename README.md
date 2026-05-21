# Interview Screening Flow

This repository contains a small LiveKit-based voice screening agent and a FastAPI service that triggers outbound screening calls.

The flow is designed for a resume-based interview screening use case:

1. A third-party screening project prepares the interview payload.
2. This API starts an outbound call and dispatches the LiveKit agent.
3. The agent runs the screening interview using the provided questions.
4. When the call ends, the agent formats the full conversation as SRT-style blocks with speaking timestamps.
5. The transcript is posted to a third-party evaluation endpoint for the next flow.

## Project Structure

- `api.py`: FastAPI service that starts the screening call.
- `src/agent.py`: LiveKit agent that conducts the interview and submits the transcript.
- `pyproject.toml`: Python dependencies and tooling configuration.

## Requirements

- Python 3.10 or newer
- LiveKit credentials
- SIP trunk access for outbound calls
- A third-party transcript evaluation API

## Environment Variables

Create a `.env` file or export these variables in your shell.

### Required for `api.py`

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_SIP_TRUNK_ID`

### Required for `src/agent.py`

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `SCREENING_API_BASE_URL`

### Optional

- `SCREENING_TRANSCRIPT_API_URL`: legacy alias for the transcript API base URL
- `SCREENING_API_URL`: legacy alias for the transcript API base URL
- `.env.local`: loaded by the agent process if present

## Install

Using `uv`:

```bash
uv sync
```

Using `pip`:

```bash
pip install -e .
```

## Run The API

Start the screening trigger API:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Run The Agent

Start the LiveKit agent worker:

```bash
python src/agent.py
```

## Docker

Build the LiveKit agent image:

```bash
docker build -t conversation-agent .
```

Run it with your LiveKit and screening environment variables:

```bash
docker run --rm --env-file .env conversation-agent
```

The container installs the locked agent dependencies, including
`livekit-agents[turn-detector]` and `onnxruntime`, so the multilingual turn
detector used in `src/agent.py` is available at runtime.

## API Contract

### Start a Screening Call

`POST /start-screening-call`

Request body:

```json
{
  "screening_id": "screening-123",
  "candidate_mobile_no": "+15551234567",
  "candidate_name": "Jane Doe",
  "interview_language": "English",
  "questions": [
    "Tell me about your experience with Python.",
    "What APIs have you built recently?",
    "Describe your SQL experience."
  ]
}
```

Example:

```bash
curl -X POST "http://localhost:8000/start-screening-call" ^
  -H "Content-Type: application/json" ^
  -d "{\"screening_id\":\"screening-123\",\"candidate_mobile_no\":\"+15551234567\",\"candidate_name\":\"Jane Doe\",\"interview_language\":\"English\",\"questions\":[\"Tell me about your experience with Python.\",\"What APIs have you built recently?\",\"Describe your SQL experience.\"]}"
```

Response:

```json
{
  "success": true,
  "room_name": "screening-screening-123-abc123def4",
  "screening_id": "screening-123",
  "candidate_mobile_no": "+15551234567",
  "message": "Call initiated for Jane Doe.",
  "dispatch_id": "..."
}
```

## Screening Agent Behavior

The agent reads the screening payload from LiveKit job metadata:

- `screening_id`
- `candidate_mobile_no`
- `candidate_name`
- `interview_language`
- `questions`

During the call it:

1. Greets the candidate.
2. Asks the provided questions one at a time.
3. Ends the screening with the `complete_screening` tool.
4. Builds an SRT-style transcript from `session.history` / session report timestamps.
5. Sends the transcript to the third-party evaluation API defined by `SCREENING_TRANSCRIPT_API_URL`.

## Transcript Handoff

The transcript payload is sent by the agent, not by `api.py`.

The agent posts a JSON body to `POST /screenings/{flow_id}/transcript` using the base URL in `SCREENING_API_BASE_URL`.

Example request:

```json
{
  "screening_id": "screening-123",
  "candidate_name": "Jane Doe",
  "candidate_mobile_no": "+15551234567",
  "interview_language": "English",
  "transcript": "1\n00:00:01,000 --> 00:00:04,500\nInterviewer: ..."
}
```

This keeps the screening API separate from the downstream evaluation system.

## Typical Workflow

1. Start the API server.
2. Start the LiveKit agent worker.
3. Call `POST /start-screening-call` with screening details.
4. The agent dials the candidate and runs the interview.
5. At the end of the session, the agent posts the transcript to the evaluation API.
6. Your downstream project resumes the screening flow from that transcript.

## Validation

Run the formatter/linter checks:

```bash
.venv\Scripts\ruff.exe check api.py src/agent.py
```

Run a syntax check:

```bash
python -m compileall api.py src/agent.py
```

## Notes

- `api.py` only starts the screening call. It does not own transcript evaluation.
- Transcript evaluation happens through the third-party API configured in the agent.
- If you change the question payload shape in the upstream screening project, update the agent metadata parsing in `src/agent.py`.

<!-- deployment trigger: no functional change -->
