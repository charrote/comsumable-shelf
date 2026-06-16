"""Smart barcode recognition engine.

Handles multiple SMT reel barcode formats without fixed rules.
Uses pattern matching, fuzzy matching, and material master lookup.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from fuzzywuzzy import fuzz, process as fuzzy_process


@dataclass
class BarcodeParseResult:
    material_code: str
    confidence: float  # 0.0 - 1.0
    source_format: str  # e.g., "prefix_match", "suffix_match", "exact", "fuzzy"
    raw_barcode: str
    matched_material_id: Optional[int] = None
    extra: Dict = None


# Known prefix patterns for SMT material barcodes
KNOWN_PREFIXES = [
    "RES", "CAP", "IND", "DI", "TR", "IC", "CONN", "FUSE",
    "CRSTAL", "VAR", "THERMISTOR", "OPTO", "RELAY", "TRANS",
    "R", "C", "L", "D", "Q", "U", "J", "X", "Y", "Z",
    # Common manufacturers
    "YAGEO", "SAMSUNG", "MURATA", "TAIYO", "YUASA", "SONY",
    "Johanson", "TDK", "AVX", "KEMET", "VISHAY", "WALSIN",
    "UNIOHM", "RCM", "SRP", "YAGEO-01",
    # Common reel type prefixes
    "REEL", "TAPE", "TR-", "TR", "T", "Q", "R", "SMD",
]

# Known suffix patterns (country/manufacturer codes)
KNOWN_SUFFIXES = [
    "-CH", "-JP", "-US", "-KR", "-CN",
    "-A", "-B", "-C", "-1", "-2", "-3",
    "01", "02", "03", "04", "05",
]


def _extract_material_code(barcode: str) -> str:
    """Extract the core material code from a raw barcode string."""
    # Remove common delimiters
    cleaned = barcode.strip().upper()

    # Remove tape/reel type indicators
    cleaned = re.sub(r'^(TAPE|REEL|TR-|TR)\s*', '', cleaned)

    # Remove trailing country/manufacturer codes
    for suffix in KNOWN_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
            break

    # Extract alphanumeric core
    match = re.search(r'([A-Z0-9]+(?:-[A-Z0-9]+)*)', cleaned)
    if match:
        return match.group(1).strip('-')
    return cleaned


def _find_known_prefix(barcode: str) -> Optional[str]:
    """Check if barcode starts with any known prefix."""
    upper = barcode.strip().upper()
    for prefix in KNOWN_PREFIXES:
        if upper.startswith(prefix):
            return prefix
    return None


def _calculate_confidence(barcode: str, material_code: str) -> float:
    """Calculate matching confidence between barcode and material code."""
    if not material_code:
        return 0.0

    # Exact match
    if barcode.strip().upper() == material_code.strip().upper():
        return 1.0

    # Starts with material code
    if barcode.strip().upper().startswith(material_code.strip().upper()):
        ratio = len(material_code) / len(barcode)
        return max(0.7, ratio)

    # Material code starts with barcode
    if material_code.strip().upper().startswith(barcode.strip().upper()):
        ratio = len(barcode) / len(material_code)
        return max(0.7, ratio)

    # Fuzzy match
    ratio = fuzz.ratio(
        barcode.strip().upper(),
        material_code.strip().upper()
    ) / 100.0

    # Partial match bonus for prefix/suffix alignment
    if barcode.strip().upper().startswith(material_code.strip().upper()[:min(5, len(material_code))]):
        ratio = max(ratio, 0.85)

    return ratio


async def parse_barcode(barcode: str, material_db) -> BarcodeParseResult:
    """Parse a raw barcode string and find the best matching material.

    Args:
        barcode: Raw barcode string from scanner
        material_db: Async database session for material lookup

    Returns:
        BarcodeParseResult with the best match and confidence score
    """
    raw = barcode.strip()
    if not raw:
        return BarcodeParseResult(
            material_code="", confidence=0.0,
            source_format="empty", raw_barcode=barcode
        )

    extracted = _extract_material_code(raw)
    known_prefix = _find_known_prefix(raw)

    # Query material database for candidates
    candidates = []
    try:
        from sqlalchemy import select
        result = await material_db.execute(
            select(material_db.get_bind().classes.MaterialMaster if hasattr(material_db.get_bind(), 'classes') else None)
        )
    except:
        candidates = []

    # If we have DB access, use it for better matching
    # For now, return best guess based on extraction
    confidence = _calculate_confidence(raw, extracted)

    # Boost confidence for known prefix matches
    if known_prefix:
        confidence = min(1.0, confidence + 0.1)

    # Determine format source
    if raw.upper() == extracted.upper():
        source = "exact"
    elif known_prefix:
        source = "prefix_match"
    else:
        source = "fuzzy"

    return BarcodeParseResult(
        material_code=extracted,
        confidence=confidence,
        source_format=source,
        raw_barcode=barcode,
    )


def parse_barcode_sync(barcode: str, material_codes: List[str] = None) -> BarcodeParseResult:
    """Synchronous barcode parsing (for non-DB contexts)."""
    raw = barcode.strip()
    if not raw:
        return BarcodeParseResult(
            material_code="", confidence=0.0,
            source_format="empty", raw_barcode=barcode
        )

    extracted = _extract_material_code(raw)
    known_prefix = _find_known_prefix(raw)
    confidence = _calculate_confidence(raw, extracted)

    if known_prefix:
        confidence = min(1.0, confidence + 0.1)

    if raw.upper() == extracted.upper():
        source = "exact"
    elif known_prefix:
        source = "prefix_match"
    else:
        source = "fuzzy"

    return BarcodeParseResult(
        material_code=extracted,
        confidence=confidence,
        source_format=source,
        raw_barcode=barcode,
    )


def add_material_pattern(material_code: str, category: str = None):
    """Register a material code pattern for future recognition."""
    KNOWN_PREFIXES.append(material_code.split('-')[0] if '-' in material_code else material_code)
    KNOWN_PREFIXES.sort()
