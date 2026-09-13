"""JSON-LD payload generation."""

import json

from .context import build_context


def build_payload(target_bytes, extra_rules=0):
    """Create a JSON-LD payload of at least approximately target_bytes."""
    if target_bytes < 0:
        raise ValueError("target_bytes must be >= 0")
    if extra_rules < 0:
        raise ValueError("extra_rules must be >= 0")

    payload = {
        "@context": build_context(extra_rules),
        "@id": "https://example.org/dtix#payload-1",
        "@type": "Payload",
        "asset_id": "ARM-ROBOT-892",
        "information_type": "computed",
        "rul_hours": 12.5,
        "confidence": 0.87,
        "model_id": "RUL-Transformer",
        "model_version": "2.1",
        "latency_ms": 12.4,
        "diagnostic_history": [],
    }

    for index in range(extra_rules):
        payload[f"rule_{index}"] = index

    serialized = json.dumps(payload, separators=(",", ":"))
    sample_index = 0

    while len(serialized.encode("utf-8")) < target_bytes:
        payload["diagnostic_history"].append({
            "sample_id": sample_index,
            "vibration_rms": 2.31,
            "temperature_c": 71.2,
            "health_score": 0.91,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        sample_index += 1
        serialized = json.dumps(payload, separators=(",", ":"))

    return serialized
