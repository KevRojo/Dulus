"""
Dulus Batch API — provider-agnostic OpenAI-compatible batch processing.

Works with any provider that supports the OpenAI Batch API format:
  - OpenAI (api.openai.com)
  - Kimi/Moonshot (api.moonshot.ai)
  - Any OpenAI-compatible endpoint

Usage:
    mgr = BatchManager(api_key="sk-...", base_url="https://api.openai.com")
    jsonl = mgr.prepare_jsonl(["prompt1", "prompt2"], model="gpt-4o-mini")
    file_id = mgr.upload_file(jsonl)
    batch_id = mgr.create_batch(file_id)
"""

import json
import urllib.request
import os
import time
from typing import Optional, List, Dict, Any

# ── Defaults ─────────────────────────────────────────────────────────────────

OPENAI_BASE_URL = "https://api.openai.com"
KIMI_BASE_URL   = "https://api.moonshot.ai"

BATCH_SYSTEM_PROMPT = (
    "You are Dulus, an AI assistant. You are processing a batch request — "
    "respond directly to each task. Be concise, precise, and complete. "
    "Output in the same language the user writes in. "
    "No tool calls available — just answer with text."
)


# ── BatchManager ─────────────────────────────────────────────────────────────

class BatchManager:
    """Provider-agnostic manager for the OpenAI-compatible Batch API."""

    def __init__(self, api_key: str, base_url: str = OPENAI_BASE_URL):
        self.api_key  = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self, content_type: str = "application/json") -> dict:
        return {
            "Content-Type": content_type,
            "Authorization": f"Bearer {self.api_key}",
        }

    # ── JSONL preparation ────────────────────────────────────────────────

    def prepare_jsonl(
        self,
        prompts: List[str],
        model: str = "gpt-4o-mini",
        system_prompt: str = None,
        endpoint: str = "/v1/chat/completions",
    ) -> str:
        """Convert a list of prompts into JSONL content for the Batch API.

        Args:
            prompts:       List of user prompts.
            model:         Model name (provider-specific).
            system_prompt: Defaults to BATCH_SYSTEM_PROMPT. Pass "" to omit.
            endpoint:      API endpoint for each request.
        """
        if system_prompt is None:
            system_prompt = BATCH_SYSTEM_PROMPT

        lines = []
        ts = int(time.time())
        for i, prompt in enumerate(prompts):
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            request = {
                "custom_id": f"req_{ts}_{i}",
                "method": "POST",
                "url": endpoint,
                "body": {
                    "model": model,
                    "messages": messages,
                },
            }
            lines.append(json.dumps(request, ensure_ascii=False))
        return "\n".join(lines)

    # ── File upload (multipart/form-data) ────────────────────────────────

    def upload_file(self, jsonl_content: str, filename: str = "batch_input.jsonl") -> str:
        """Upload JSONL content and return the file_id."""
        url = f"{self.base_url}/v1/files"
        boundary = f"----DulusBatch{int(time.time())}"

        parts = []
        # purpose field
        parts.append(f"--{boundary}\r\n"
                      f'Content-Disposition: form-data; name="purpose"\r\n\r\n'
                      f"batch")
        # file field
        parts.append(f"--{boundary}\r\n"
                      f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                      f"Content-Type: application/octet-stream\r\n\r\n"
                      f"{jsonl_content}")
        parts.append(f"--{boundary}--\r\n")

        full_body = "\r\n".join(parts).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=full_body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))["id"]

    # ── Batch lifecycle ──────────────────────────────────────────────────

    def create_batch(
        self,
        file_id: str,
        endpoint: str = "/v1/chat/completions",
        completion_window: str = "24h",
    ) -> str:
        """Create a batch from an uploaded file. Returns batch_id."""
        url = f"{self.base_url}/v1/batches"
        payload = {
            "input_file_id": file_id,
            "endpoint": endpoint,
            "completion_window": completion_window,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))["id"]

    def retrieve_batch(self, batch_id: str) -> Dict[str, Any]:
        """Get batch status/info."""
        url = f"{self.base_url}/v1/batches/{batch_id}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def cancel_batch(self, batch_id: str) -> Dict[str, Any]:
        """Cancel a running batch."""
        url = f"{self.base_url}/v1/batches/{batch_id}/cancel"
        req = urllib.request.Request(url, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_file_content(self, file_id: str) -> str:
        """Download file content (e.g. batch results)."""
        url = f"{self.base_url}/v1/files/{file_id}/content"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8")


# ── Backward compat alias ────────────────────────────────────────────────────
KimiBatchManager = BatchManager  # old name still works


# ── Local job persistence ────────────────────────────────────────────────────

_JOBS_DIR = os.path.join(os.path.expanduser("~"), ".dulus", "jobs")


def save_batch_job(batch_id: str, description: str = "", file_id: str = "",
                   provider: str = "unknown") -> str:
    """Save a batch job record locally in ~/.dulus/jobs/."""
    os.makedirs(_JOBS_DIR, exist_ok=True)
    job_file = os.path.join(_JOBS_DIR, f"{batch_id}.json")

    job_data = {
        "job_id": batch_id,
        "id": batch_id,
        "tool_name": "batch",
        "provider": provider,
        "params": {"description": description, "file_id": file_id},
        "status": "created",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "description": description,
        "file_id": file_id,
        "batch_id": batch_id,
    }

    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=2)
    return job_file


def list_batch_jobs(include_pollers: bool = True, **_kw) -> List[Dict]:
    """List saved batch jobs from ~/.dulus/jobs/."""
    if not os.path.exists(_JOBS_DIR):
        return []

    batch_map: Dict[str, Dict] = {}
    poller_jobs: List[Dict] = []
    # Accept both old "kimi_batch" and new "batch" tool_name
    _batch_names  = {"kimi_batch", "batch"}
    _poller_names = {"kimi_batch_poll", "batch_poll"}

    for fname in os.listdir(_JOBS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(_JOBS_DIR, fname), "r", encoding="utf-8") as f:
                job = json.load(f)

            tn = job.get("tool_name", "")
            if tn in _batch_names:
                bid = job.get("batch_id") or job.get("id")
                if bid:
                    batch_map[bid] = job

            elif include_pollers and tn in _poller_names:
                poller_jobs.append(job)
                br = job.get("batch_result", {})
                if br:
                    bid = br.get("id")
                    if bid and bid in batch_map:
                        batch_map[bid]["status"]         = br.get("status", "unknown")
                        batch_map[bid]["request_counts"]  = br.get("request_counts", {})
                        batch_map[bid]["output_file_id"]  = br.get("output_file_id")
                        batch_map[bid]["completed_at"]    = br.get("completed_at")
                        batch_map[bid]["_poller_job_id"]  = job.get("job_id")
        except Exception:
            continue

    # Pollers for batches not yet in map → synthetic entry
    for poller in poller_jobs:
        br  = poller.get("batch_result", {})
        bid = br.get("id")
        if bid and bid not in batch_map:
            batch_map[bid] = {
                "job_id": bid, "id": bid,
                "tool_name": "batch",
                "status": br.get("status", "unknown"),
                "created_at": poller.get("created_at"),
                "description": f"(from poller {poller.get('job_id', '?')[:8]}...)",
                "batch_id": bid,
                "request_counts": br.get("request_counts", {}),
                "output_file_id": br.get("output_file_id"),
                "completed_at": br.get("completed_at"),
                "_from_poller": True,
                "_poller_job_id": poller.get("job_id"),
            }

    jobs = list(batch_map.values())
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jobs


def update_batch_job_status(batch_id: str, status_info: Dict[str, Any]) -> bool:
    """Update a batch job's status in its local file."""
    job_file = os.path.join(_JOBS_DIR, f"{batch_id}.json")
    if not os.path.exists(job_file):
        return False
    try:
        with open(job_file, "r", encoding="utf-8") as f:
            job = json.load(f)
        for key in ("status", "request_counts", "output_file_id", "completed_at"):
            if key in status_info:
                job[key] = status_info[key]
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(job, f, indent=2)
        return True
    except Exception:
        return False


def get_batch_job_by_id(batch_id: str) -> Optional[Dict]:
    """Get a batch job by ID (checks both batch and poller files)."""
    # Direct file
    job_file = os.path.join(_JOBS_DIR, f"{batch_id}.json")
    if os.path.exists(job_file):
        try:
            with open(job_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Scan pollers
    if os.path.exists(_JOBS_DIR):
        for fname in os.listdir(_JOBS_DIR):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(_JOBS_DIR, fname), "r", encoding="utf-8") as f:
                    job = json.load(f)
                if job.get("tool_name") in ("kimi_batch_poll", "batch_poll"):
                    if job.get("params", {}).get("batch_id") == batch_id:
                        return job
            except Exception:
                continue
    return None
