"""RDF parsing helpers."""

from rdflib import Graph


def parse_jsonld(payload):
    """Parse a JSON-LD string into an RDFLib Graph."""
    if not isinstance(payload, str):
        raise TypeError("payload must be a JSON-LD string")
    return Graph().parse(data=payload, format="json-ld")
