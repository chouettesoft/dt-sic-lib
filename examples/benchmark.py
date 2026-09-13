import json

from dtix_sic import run_payload_experiment, run_contract_complexity_experiment

payload_sizes = [150, 5_000, 10_000, 50_000, 100_000]
rule_counts = [0, 10, 50, 100, 200]

report = {
    "experiment": "DTIX-A Reference Prototype Benchmark",
    "payload_experiment": [
        run_payload_experiment(
            size,
            warmup_iterations=3 if size == 150 else 2,
            measured_iterations=10 if size == 150 else 5,
        )
        for size in payload_sizes
    ],
    "contract_complexity_experiment": [
        run_contract_complexity_experiment(rules)
        for rules in rule_counts
    ],
}

print(json.dumps(report, indent=2))
