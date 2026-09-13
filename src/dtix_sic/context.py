"""JSON-LD context generation."""

from rdflib import Namespace

EX = Namespace("https://example.org/dtix#")
XSD = "http://www.w3.org/2001/XMLSchema#"


def build_context(extra_rules=0):
    """Return the JSON-LD context for the DTIX-A reference payload."""
    if extra_rules < 0:
        raise ValueError("extra_rules must be >= 0")

    context = {
        "@vocab": str(EX),
        "asset_id": {"@id": str(EX.asset_id), "@type": f"{XSD}string"},
        "information_type": {"@id": str(EX.information_type)},
        "rul_hours": {"@id": str(EX.rul_hours), "@type": f"{XSD}decimal"},
        "confidence": {"@id": str(EX.confidence), "@type": f"{XSD}decimal"},
        "model_id": {"@id": str(EX.model_id), "@type": f"{XSD}string"},
        "model_version": {"@id": str(EX.model_version), "@type": f"{XSD}string"},
        "latency_ms": {"@id": str(EX.latency_ms), "@type": f"{XSD}decimal"},
    }

    for index in range(extra_rules):
        name = f"rule_{index}"
        context[name] = {
            "@id": str(EX[name]),
            "@type": f"{XSD}integer",
        }

    return context
