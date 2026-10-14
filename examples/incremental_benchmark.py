"""Incremental SIC performance benchmark.

Run from the repository root after `python -m pip install -e '.[dev,benchmark]'`:
    python examples/incremental_benchmark.py --output benchmark-results

The minimum-validation path is an explicitly controlled microbenchmark only; it
must not be used for untrusted production inputs.
"""
import argparse
import csv
import json
import os
import platform
import subprocess
import re
from importlib import metadata
import statistics
import sys
import time
from pathlib import Path

from dtix_sic import (
    authorize_sic, build_payload, clear_cel_cache, evaluate_cel,
    get_payload_subject, graph_to_data, load_contract, parse_jsonld, validate_sic,
)
from dtix_sic.cel import _compile
from dtix_sic.casbin_engine import build_enforcer
from dtix_sic.policy import DEFAULT_MODEL_PATH, DEFAULT_POLICY_PATH

DEFAULT_SIZES = [0, 10, 25, 50, 100, 200, 300, 400]
WARMUPS = 2
REPEATS = 7


def stats(samples):
    values = sorted(samples)
    return {
        "mean_ms": statistics.mean(values),
        "median_ms": statistics.median(values),
        "p95_ms": values[min(len(values) - 1, int(0.95 * len(values)))],
        "min_ms": values[0],
        "max_ms": values[-1],
        "throughput_per_s": 1000.0 / statistics.mean(values) if statistics.mean(values) else None,
    }


def timed(fn):
    start = time.perf_counter_ns()
    result = fn()
    return (time.perf_counter_ns() - start) / 1_000_000, result


def measure(name, entries, fn, *, repeats=REPEATS, warmups=WARMUPS, batches=3, **metadata):
    """Measure repeated samples grouped into explicit batches; report batch count."""
    samples = []
    for batch in range(batches):
        for _ in range(warmups if batch == 0 else 0):
            fn()
        for _ in range(repeats):
            elapsed, _ = timed(fn)
            samples.append(elapsed)
    return {"scenario": name, "input_entries": entries, **metadata, **stats(samples),
            "warmups": warmups, "repeats_per_batch": repeats,
            "batch_count": batches, "sample_count": len(samples)}


def make_case(extra_properties, rule_count):
    """Build a case where property count and rule count vary independently."""
    payload_text = build_payload(150, extra_rules=extra_properties)
    graph = parse_jsonld(payload_text)
    contract = load_contract()
    # Add rules independently of payload growth. They read existing fields, so
    # increasing rule_count does not add payload properties.
    for i in range(rule_count):
        if extra_properties:
            expression = "rule_%d == %d" % (i % extra_properties, i % extra_properties)
        else:
            expression = "asset_id != ''"
        contract["rules"].append({
            "id": "benchmark_rule_%d" % i,
            "message": "benchmark rule %d" % i,
            "expression": expression,
        })
    subject = get_payload_subject(graph)
    data = graph_to_data(graph, subject)
    return payload_text, graph, contract, data


def expression_stage_rows(entries, contract, data):
    """Measure parser, compile, program creation, and precompiled execution.

    cel-python exposes compile() as a combined parse/compile operation. Parser
    timing is attempted through the runtime parser if it is exposed; the report
    labels compile_ms as parse+compile where a separate public parser is absent.
    """
    import celpy
    env = celpy.Environment()
    rows = []
    for rule in contract["rules"]:
        expr = rule["expression"]
        parser = getattr(env, "cel_parser", None)
        if parser is None:
            parser = getattr(env, "parser", None)
        if parser is not None and hasattr(parser, "parse"):
            rows.append(measure("4-expression-parse", entries,
                                lambda p=parser, e=expr: p.parse(e), repeats=REPEATS,
                                expression_id=rule["id"]))
        ast = env.compile(expr)
        rows.append(measure("4-expression-parse+compile", entries,
                            lambda e=expr, environment=env: environment.compile(e),
                            repeats=REPEATS, expression_id=rule["id"]))
        rows.append(measure("4-expression-program-create", entries,
                            lambda a=ast, environment=env: environment.program(a),
                            repeats=REPEATS, expression_id=rule["id"]))
        program = env.program(ast)
        activation = celpy.json_to_cel(data)
        rows.append(measure("4-expression-execute-precompiled", entries,
                            lambda p=program, a=activation: p.evaluate(a),
                            repeats=REPEATS, expression_id=rule["id"]))
    return rows



def _command_output(command, timeout=4):
    """Return command stdout, or None when unavailable/unpermitted."""
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _sysctl_value(key):
    value = _command_output(["sysctl", "-n", key])
    return value.strip() if value else None


def _linux_cpuinfo():
    try:
        return Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def collect_hardware_info():
    """Best-effort hardware inventory; unavailable/permission-limited fields are explicit."""
    system = platform.system()
    logical = os.cpu_count()
    physical = None
    cpu_name = platform.processor() or None
    min_mhz = max_mhz = current_mhz = None
    ram_bytes = None
    ram_speed = []
    notes = []

    # psutil is optional and gives the best cross-platform CPU/RAM observations.
    try:
        import psutil
        freq = psutil.cpu_freq()
        if freq:
            current_mhz = freq.current or None
            min_mhz = freq.min or None
            max_mhz = freq.max or None
        physical = psutil.cpu_count(logical=False)
        ram_bytes = psutil.virtual_memory().total
    except ImportError:
        notes.append("psutil not installed; used operating-system-specific fallbacks")
    except Exception as exc:
        notes.append("psutil hardware query unavailable: " + type(exc).__name__)

    if system == "Darwin":
        physical = physical or _sysctl_value("hw.physicalcpu")
        logical = int(_sysctl_value("hw.logicalcpu") or _sysctl_value("hw.ncpu") or logical or 0) or None
        physical = int(physical) if physical is not None else None
        ram_bytes = ram_bytes or (int(_sysctl_value("hw.memsize")) if (_sysctl_value("hw.memsize") or "").isdigit() else None)
        cpu_name = cpu_name or _sysctl_value("machdep.cpu.brand_string")
        # Intel Macs may expose these values; Apple Silicon often does not expose clock rate.
        max_mhz = max_mhz or (int(_sysctl_value("hw.cpufrequency_max")) / 1_000_000 if (_sysctl_value("hw.cpufrequency_max") or "").isdigit() else None)
        current_mhz = current_mhz or (int(_sysctl_value("hw.cpufrequency")) / 1_000_000 if (_sysctl_value("hw.cpufrequency") or "").isdigit() else None)
        mem_json = _command_output(["system_profiler", "SPMemoryDataType", "-json"], timeout=12)
        if mem_json:
            try:
                mem_data = json.loads(mem_json)
                def walk(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if "speed" in k.lower() and isinstance(v, str) and re.search(r"\d+\s*(MHz|MT/s)", v, re.I):
                                ram_speed.append(v)
                            walk(v)
                    elif isinstance(obj, list):
                        for item in obj: walk(item)
                walk(mem_data)
            except (ValueError, TypeError):
                notes.append("macOS memory speed details could not be parsed")
    elif system == "Linux":
        cpuinfo = _linux_cpuinfo()
        if not cpu_name:
            match = re.search(r"^model name\s*:\s*(.+)$", cpuinfo, re.M)
            cpu_name = match.group(1).strip() if match else None
        if current_mhz is None:
            values = [float(x) for x in re.findall(r"^cpu MHz\s*:\s*([\d.]+)", cpuinfo, re.M)]
            current_mhz = statistics.median(values) if values else None
        lscpu = _command_output(["lscpu"])
        if lscpu:
            def lscpu_field(label):
                m = re.search(r"^" + re.escape(label) + r":\s*(.+)$", lscpu, re.M | re.I)
                return m.group(1).strip() if m else None
            physical = physical or (int(lscpu_field("Core(s) per socket")) * int(lscpu_field("Socket(s)")) if lscpu_field("Core(s) per socket") and lscpu_field("Socket(s)") else None)
            cpu_name = cpu_name or lscpu_field("Model name")
            max_mhz = max_mhz or (float(lscpu_field("CPU max MHz")) if lscpu_field("CPU max MHz") else None)
            min_mhz = min_mhz or (float(lscpu_field("CPU min MHz")) if lscpu_field("CPU min MHz") else None)
        if ram_bytes is None:
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                match = re.search(r"^MemTotal:\s+(\d+)\s+kB", meminfo.read_text(), re.M)
                ram_bytes = int(match.group(1)) * 1024 if match else None
        dmidecode = _command_output(["dmidecode", "--type", "memory"], timeout=4)
        if dmidecode:
            ram_speed = list(dict.fromkeys(re.findall(r"^\s*Speed:\s*(.+)$", dmidecode, re.M)))
        else:
            notes.append("RAM module speed requires dmidecode/root access on many Linux systems")
    elif system == "Windows":
        ps = "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed | ConvertTo-Json -Compress"
        out = _command_output(["powershell", "-NoProfile", "-Command", ps])
        if out:
            try:
                cpu = json.loads(out)
                cpu_name = cpu_name or cpu.get("Name")
                physical = physical or cpu.get("NumberOfCores")
                logical = logical or cpu.get("NumberOfLogicalProcessors")
                max_mhz = max_mhz or cpu.get("MaxClockSpeed")
                current_mhz = current_mhz or cpu.get("CurrentClockSpeed")
            except (ValueError, AttributeError):
                notes.append("Windows CPU inventory could not be parsed")
        ps_mem = "Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed | ConvertTo-Json -Compress"
        mem_out = _command_output(["powershell", "-NoProfile", "-Command", ps_mem])
        if mem_out:
            try:
                modules = json.loads(mem_out)
                modules = modules if isinstance(modules, list) else [modules]
                if ram_bytes is None:
                    ram_bytes = sum(int(m.get("Capacity", 0) or 0) for m in modules) or None
                ram_speed = list(dict.fromkeys(str(m.get("ConfiguredClockSpeed") or m.get("Speed")) + " MHz" for m in modules if m.get("ConfiguredClockSpeed") or m.get("Speed")))
            except (ValueError, AttributeError, TypeError):
                notes.append("Windows RAM inventory could not be parsed")

    def gib(value):
        return round(value / (1024 ** 3), 2) if value is not None else None

    return {
        "operating_system": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "cpu": {
            "model": cpu_name,
            "physical_cores": physical,
            "logical_processors": logical,
            "current_frequency_mhz": round(current_mhz, 1) if current_mhz is not None else None,
            "minimum_frequency_mhz": round(min_mhz, 1) if min_mhz is not None else None,
            "maximum_frequency_mhz": round(max_mhz, 1) if max_mhz is not None else None,
            "frequency_note": "Clock speed may vary dynamically; some systems, especially Apple Silicon, do not expose it to user-space tools.",
        },
        "memory": {
            "total_bytes": ram_bytes,
            "total_gib": gib(ram_bytes),
            "module_speeds": ram_speed or None,
            "speed_note": "RAM speed may be unavailable without elevated permissions or firmware support; missing values are not inferred.",
        },
        "collection_notes": notes,
    }


def run(output_dir, sizes, repeats, warmups, batches=3):
    suite_start = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    expression_rows = []
    total_points = len(sizes) * 2 * 9
    point = 0

    def progress(dimension, value, scenario):
        nonlocal point
        point += 1
        print(f"[{point}/{total_points}] {dimension}={value}: {scenario}", flush=True)

    # Sweep A: increase payload properties while keeping rule count fixed at 7.
    for properties in sizes:
        payload_text, graph, contract, data = make_case(properties, 0)
        base = {"payload_bytes": len(payload_text.encode("utf-8")),
                "contract_rules": len(contract["rules"]), "extra_properties": properties,
                "extra_rules": 0, "workload_dimension": "properties", "workload_value": properties,
                "fixed_properties": None, "fixed_rules": 7}
        scenarios = [
            ("1-policy-disabled", lambda g=graph, c=contract: validate_sic(g, c)),
            ("1-policy-enabled", lambda g=graph, c=contract: authorize_sic(
                g, contract=c, subject={"roles": ["researcher"]},
                resource={"type": "telemetry", "classification": "public"}, request={"action": "share"})),
        ]
        def uncached(g=graph, c=contract):
            clear_cel_cache(); return validate_sic(g, c)
        scenarios += [("2-cache-disabled", uncached)]
        clear_cel_cache()
        cold_ms, cold_result = timed(lambda g=graph, c=contract: validate_sic(g, c))
        rows.append({"scenario":"2-cache-cold", "input_entries":properties, **base,
                     "mean_ms":cold_ms, "median_ms":cold_ms, "p95_ms":cold_ms,
                     "min_ms":cold_ms, "max_ms":cold_ms,
                     "throughput_per_s":1000.0/cold_ms if cold_ms else None,
                     "warmups":0, "repeats_per_batch":1, "batch_count":1, "sample_count":1})
        scenarios += [("2-cache-warm", lambda g=graph, c=contract: validate_sic(g, c)),
                      ("3-validation-full", lambda g=graph, c=contract: validate_sic(g, c)),
                      ("3-validation-minimum-controlled", lambda c=contract, d=data: all(bool(evaluate_cel(r["expression"], d)) for r in c["rules"])),
                      ("4-direct-processing-no-expressions", lambda g=graph: graph_to_data(g, get_payload_subject(g))),
                      ("4-expression-evaluation-cached", lambda c=contract, d=data: all(bool(evaluate_cel(r["expression"], d)) for r in c["rules"]))]
        for name, fn in scenarios:
            progress("properties (rules fixed at 7)", properties, name)
            rows.append(measure(name, properties, fn, repeats=repeats, warmups=warmups, batches=batches, **base))
        expression_rows.extend(expression_stage_rows(properties, contract, data))

    # Sweep B: increase rule count while keeping payload properties fixed at max(sizes).
    fixed_properties = max(sizes) if sizes else 0
    for rule_count in sizes:
        payload_text, graph, contract, data = make_case(fixed_properties, rule_count)
        base = {"payload_bytes": len(payload_text.encode("utf-8")),
                "contract_rules": len(contract["rules"]), "extra_properties": fixed_properties,
                "extra_rules": rule_count, "workload_dimension": "rules", "workload_value": rule_count,
                "fixed_properties": fixed_properties, "fixed_rules": None}
        scenarios = [
            ("1-policy-disabled", lambda g=graph, c=contract: validate_sic(g, c)),
            ("1-policy-enabled", lambda g=graph, c=contract: authorize_sic(
                g, contract=c, subject={"roles": ["researcher"]},
                resource={"type": "telemetry", "classification": "public"}, request={"action": "share"})),
        ]
        def uncached(g=graph, c=contract):
            clear_cel_cache(); return validate_sic(g, c)
        scenarios += [("2-cache-disabled", uncached)]
        clear_cel_cache()
        cold_ms, _ = timed(lambda g=graph, c=contract: validate_sic(g, c))
        rows.append({"scenario":"2-cache-cold", "input_entries":rule_count, **base,
                     "mean_ms":cold_ms, "median_ms":cold_ms, "p95_ms":cold_ms,
                     "min_ms":cold_ms, "max_ms":cold_ms,
                     "throughput_per_s":1000.0/cold_ms if cold_ms else None,
                     "warmups":0, "repeats_per_batch":1, "batch_count":1, "sample_count":1})
        scenarios += [("2-cache-warm", lambda g=graph, c=contract: validate_sic(g, c)),
                      ("3-validation-full", lambda g=graph, c=contract: validate_sic(g, c)),
                      ("3-validation-minimum-controlled", lambda c=contract, d=data: all(bool(evaluate_cel(r["expression"], d)) for r in c["rules"])),
                      ("4-direct-processing-no-expressions", lambda g=graph: graph_to_data(g, get_payload_subject(g))),
                      ("4-expression-evaluation-cached", lambda c=contract, d=data: all(bool(evaluate_cel(r["expression"], d)) for r in c["rules"]))]
        for name, fn in scenarios:
            progress(f"rules (properties fixed at {fixed_properties})", rule_count, name)
            rows.append(measure(name, rule_count, fn, repeats=repeats, warmups=warmups, batches=batches, **base))

    def installed_version(package):
        try:
            return metadata.version(package)
        except metadata.PackageNotFoundError:
            return "not installed / metadata unavailable"

    hardware = collect_hardware_info()
    config = {
        "benchmark": "DTIX-A SIC incremental performance (independent workload sweeps)",
        "hardware": hardware,
        "library_version": "0.6.1 (from uploaded pyproject.toml)",
        "python": sys.version, "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "implementation": platform.python_implementation(),
        "installed_dependencies": {"dtix-sic": installed_version("dtix-sic"),
            "rdflib": installed_version("rdflib"), "cel-python": installed_version("cel-python"),
            "pycasbin": installed_version("pycasbin"), "matplotlib": installed_version("matplotlib")},
        "policy_engine": "pycasbin; enabled scenario uses authorize_sic()",
        # Portable labels only: do not expose local usernames or home-directory paths.
        "policy_model": "dtix_sic/policies/dtix_a_model.conf",
        "policy_file": "dtix_sic/policies/dtix_a_policy.csv",
        "expression_engine": "cel-python; in-process LRU compile cache (maxsize=256)",
        "input_sizes": sizes, "property_sweep_fixed_rule_count": 7,
        "rule_sweep_fixed_property_count": fixed_properties,
        "warmups": warmups, "repeats_per_batch": repeats, "batch_count": batches,
        "timer": "time.perf_counter_ns",
        "notes": [
            "Property sweep changes only additional payload properties; contract rule count remains fixed at 7.",
            "Rule sweep changes only additional CEL rules; payload property count remains fixed.",
            "Each result row aggregates batches × repeats_per_batch timed samples, except cold-cache rows which are single cold measurements.",
            "Progress is printed to console for every workload point and scenario.",
            "Minimum-validation is a controlled microbenchmark only, not safe for production inputs.",
        ],
    }
    config["suite_wall_clock_seconds"] = round(time.perf_counter() - suite_start, 3)
    (output_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output_dir / "machine_info.json").write_text(json.dumps(hardware, indent=2), encoding="utf-8")
    write_csv(output_dir / "results.csv", rows)
    write_csv(output_dir / "expression_stages.csv", expression_rows)
    (output_dir / "results.json").write_text(json.dumps({"config": config, "results": rows,
        "expression_stages": expression_rows}, indent=2), encoding="utf-8")
    make_plots(output_dir, rows, expression_rows, batches=batches, repeats=repeats, hardware=hardware)
    config["suite_wall_clock_seconds"] = round(time.perf_counter() - suite_start, 3)
    (output_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output_dir / "results.json").write_text(json.dumps({"config": config, "results": rows,
        "expression_stages": expression_rows}, indent=2), encoding="utf-8")
    print(f"\nBenchmark complete in {config['suite_wall_clock_seconds']} seconds. Results written to: {output_dir.name}", flush=True)
    print(json.dumps(config, indent=2))


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def make_plots(output_dir, rows, expression_rows, batches=3, repeats=REPEATS, hardware=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib unavailable; CSV/JSON written, plots skipped. Install .[benchmark].")
        return
    hardware = hardware or {}
    cpu = hardware.get("cpu", {})
    memory = hardware.get("memory", {})
    physical = cpu.get("physical_cores")
    logical = cpu.get("logical_processors")
    ram_gib = memory.get("total_gib")
    cpu_model = cpu.get("model") or "CPU model unavailable"
    os_platform = hardware.get("operating_system") or f"{platform.system()} {platform.release()} ({platform.machine()})"
    core_text = f"{physical} physical / {logical} logical cores" if physical is not None and logical is not None else f"{logical} logical processors" if logical is not None else "core count unavailable"
    ram_text = f"{ram_gib} GiB RAM" if ram_gib is not None else "RAM amount unavailable"
    frequency = cpu.get("current_frequency_mhz")
    freq_text = f"; CPU {frequency} MHz" if frequency is not None else ""
    # Repeated on every chart so exported figures remain interpretable when shared separately.
    machine_caption = f"System: {os_platform} | {cpu_model} | {core_text} | {ram_text}{freq_text}"

    scenarios = [
        ("1-policy", ["1-policy-disabled", "1-policy-enabled"], "Policy engine: disabled vs enabled"),
        ("2-cache", ["2-cache-disabled", "2-cache-cold", "2-cache-warm"], "CEL cache modes"),
        ("3-validation", ["3-validation-full", "3-validation-minimum-controlled"], "Full vs minimum controlled validation"),
        ("4-expressions", ["4-direct-processing-no-expressions", "4-expression-evaluation-cached"], "Direct processing vs CEL evaluation"),
    ]
    for dimension in ("properties", "rules"):
        for filename, names, title in scenarios:
            fig, ax = plt.subplots()
            for name in names:
                subset = sorted((r for r in rows if r["scenario"] == name and r.get("workload_dimension") == dimension), key=lambda r: r["workload_value"])
                if subset:
                    ax.plot([r["workload_value"] for r in subset], [r["median_ms"] for r in subset], marker="o", label=name)
            ax.set_title(f"{title} — {dimension} sweep\n{batches} batches × {repeats} samples/batch (cold cache is one sample)")
            ax.set_xlabel("Additional payload properties (rules fixed)" if dimension == "properties" else "Additional CEL rules (properties fixed)")
            ax.set_ylabel("Median elapsed time (ms)")
            ax.grid(True, alpha=0.3); ax.legend(fontsize="small")
            fig.text(0.01, 0.015, machine_caption, ha="left", va="bottom", fontsize=7, wrap=True)
            fig.tight_layout(rect=(0, 0.07, 1, 1))
            fig.savefig(output_dir / f"{filename}-{dimension}.png", dpi=160)
            plt.close(fig)

    # Stage timings currently use the fixed-base-contract property sweep.
    fig, ax = plt.subplots()
    stage_names = sorted(set(r["scenario"] for r in expression_rows))
    for stage in stage_names:
        points = []
        for size in sorted(set(r["input_entries"] for r in expression_rows)):
            vals = [r["median_ms"] for r in expression_rows if r["scenario"] == stage and r["input_entries"] == size]
            if vals: points.append((size, statistics.median(vals)))
        if points: ax.plot([p[0] for p in points], [p[1] for p in points], marker="o", label=stage)
    ax.set_title("CEL expression stage latency (fixed 7-rule contract)")
    ax.set_xlabel("Additional payload properties (rule count fixed)")
    ax.set_ylabel("Median elapsed time per expression (ms)")
    ax.grid(True, alpha=0.3); ax.legend(fontsize="small")
    fig.text(0.01, 0.015, machine_caption, ha="left", va="bottom", fontsize=7, wrap=True)
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(output_dir / "4-expression-stages.png", dpi=160); plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("benchmark-results"))
    parser.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES,
                        help="number of additional properties and CEL rules per test point")
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--warmups", type=int, default=WARMUPS)
    parser.add_argument("--batches", type=int, default=3, help="independent measurement batches per workload point")
    args = parser.parse_args()
    REPEATS = args.repeats
    WARMUPS = args.warmups
    run(args.output, args.sizes, args.repeats, args.warmups, args.batches)
