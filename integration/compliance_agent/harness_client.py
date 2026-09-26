"""Bounded AgentCore Harness invocation for the read-only Compliance Agent."""
from __future__ import annotations

import re
import uuid
from typing import Any

HARNESS_RE = re.compile(
    r"^arn:aws[a-zA-Z-]*:bedrock-agentcore:[a-z0-9-]+:[0-9]{12}:harness/compliance_agent_v1-[A-Za-z0-9]+$"
)


class HarnessError(RuntimeError):
    pass


def _contains_tool_use(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() == "tooluse" or _contains_tool_use(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_tool_use(item) for item in value)
    return False


def _client(region: str):
    try:
        import boto3
    except ImportError as exc:
        raise HarnessError("boto3 is required for AgentCore Harness invocation") from exc
    client = boto3.client("bedrock-agentcore", region_name=region)
    if not hasattr(client, "invoke_harness"):
        raise HarnessError("installed boto3 does not support AgentCore InvokeHarness")
    return client


def invoke(prompt: str, harness_arn: str, *, region: str = "ap-southeast-1", client=None) -> dict[str, Any]:
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 24000:
        raise HarnessError("Harness prompt is invalid")
    if not HARNESS_RE.fullmatch(harness_arn or ""):
        raise HarnessError("Compliance Agent Harness ARN is invalid")
    client = client or _client(region)
    session_id = str(uuid.uuid4())
    try:
        response = client.invoke_harness(
            harnessArn=harness_arn,
            runtimeSessionId=session_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            maxIterations=1,
            maxTokens=1200,
            timeoutSeconds=90,
        )
    except Exception as exc:
        raise HarnessError("AgentCore Harness invocation failed") from exc

    stream = response.get("stream") if isinstance(response, dict) else None
    if stream is None:
        raise HarnessError("AgentCore Harness returned no stream")
    parts: list[str] = []
    try:
        for event in stream:
            if not isinstance(event, dict):
                continue
            if "runtimeClientError" in event:
                raise HarnessError("AgentCore Harness returned a runtime error")
            if _contains_tool_use(event):
                raise HarnessError("read-only Compliance Agent attempted an unexpected tool call")
            delta = event.get("contentBlockDelta", {}).get("delta", {})
            text = delta.get("text") if isinstance(delta, dict) else None
            if isinstance(text, str):
                parts.append(text)
    except HarnessError:
        raise
    except Exception as exc:
        raise HarnessError("AgentCore Harness stream failed") from exc
    answer = "".join(parts).strip()
    if not answer:
        raise HarnessError("AgentCore Harness returned no text")
    return {"answer": answer, "session_id": session_id}
