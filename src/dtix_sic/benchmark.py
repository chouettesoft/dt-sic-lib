"""Benchmark functions for DTIX-A SIC."""

import math
import statistics
import time

from .payload import build_payload
from .rdf import parse_jsonld
from .validator import validate_sic
from .contract import load_contract


def summarize_samples(samples_ms):
    """Return mean, median, P95, and estimated throughput."""
    if not samples_ms:
        raise ValueError("samples_ms must not be empty")

    ordered = sorted(samples_ms)
    count = len(ordered)
    mean_ms = statistics.mean(ordered)

    return {
        "mean_ms": mean_ms,
        "median_ms": statistics.median(ordered),
        "p95_ms": ordered[math.ceil(0.95 * count) - 1],
        "throughput_per_s": 1000.0 / mean_ms,
    }


def run_payload_experiment(target_bytes, warmup_iterations=2, measured_iterations=5):
    """Measure JSON-LD parsing + RDF graph construction + SIC validation."""
    _validate_iterations(warmup_iterations, measured_iterations)
    payload = build_payload(target_bytes)

    for _ in range(warmup_iterations):
        graph = parse_jsonld(payload)
        assert validate_sic(graph), "Warm-up payload did not satisfy the SIC."

    samples_ms = []

    for _ in range(measured_iterations):
        start_ns = time.perf_counter_ns()
        graph = parse_jsonld(payload)
        assert validate_sic(graph), "Measured payload did not satisfy the SIC."
        samples_ms.append((time.perf_counter_ns() - start_ns) / 1_000_000)

    return {
        "target_bytes": target_bytes,
        "actual_bytes": len(payload.encode("utf-8")),
        "warmup_iterations": warmup_iterations,
        "measured_iterations": measured_iterations,
        **summarize_samples(samples_ms),
    }


def run_contract_complexity_experiment(extra_rules, warmup_iterations=100,
                                       measured_iterations=5000):
    """Measure SIC validation only as the number of rules increases."""
    _validate_iterations(warmup_iterations, measured_iterations)
    payload = build_payload(5000, extra_rules=extra_rules)
    graph = parse_jsonld(payload)
    contract = load_contract()
    contract["rules"].extend(
        {
            "id": f"rule_{index}",
            "message": f"rule_{index} must equal {index}.",
            "rule": {"==": [{"var": f"rule_{index}"}, index]},
        }
        for index in range(extra_rules)
    )

    for _ in range(warmup_iterations):
        assert validate_sic(graph, contract), "Warm-up graph did not satisfy the SIC."

    samples_ms = []

    for _ in range(measured_iterations):
        start_ns = time.perf_counter_ns()
        assert validate_sic(graph, contract), "Measured graph did not satisfy the SIC."
        samples_ms.append((time.perf_counter_ns() - start_ns) / 1_000_000)

    return {
        "extra_rules": extra_rules,
        "total_contract_rules": 7 + extra_rules,
        "actual_bytes": len(payload.encode("utf-8")),
        "warmup_iterations": warmup_iterations,
        "measured_iterations": measured_iterations,
        **summarize_samples(samples_ms),
    }


def _validate_iterations(warmup_iterations, measured_iterations):
    if warmup_iterations < 0:
        raise ValueError("warmup_iterations must be >= 0")
    if measured_iterations <= 0:
        raise ValueError("measured_iterations must be > 0")
