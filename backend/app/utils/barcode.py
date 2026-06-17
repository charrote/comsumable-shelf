"""Smart barcode recognition engine.

Handles multiple SMT reel barcode formats without fixed rules.
Supports:
  - Standard SMT component codes (R, C, IC, etc.)
  - GS1-128 / EAN-128 format
  - Supplier 2D Data Matrix (various formats)
  - Common SMT manufacturer formats (Murata, TDK, Yageo, Samsung, etc.)
  - Extracts quantity, batch/lot, date, spec from supplier barcodes
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from rapidfuzz import fuzz, process as fuzzy_process


@dataclass
class BarcodeParseResult:
    material_code: str
    confidence: float  # 0.0 - 1.0
    source_format: str  # e.g., "prefix_match", "suffix_match", "exact", "fuzzy"
    raw_barcode: str
    matched_material_id: Optional[int] = None
    extra: Dict = None
    # Enhanced fields for supplier barcode
    quantity: Optional[float] = None
    batch_no: Optional[str] = None
    date_code: Optional[str] = None
    date_code_type: Optional[str] = None  # date_code | mfg_date | expiry_date
    supplier_code: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None


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


async def parse_barcode(barcode: str, material_db=None) -> BarcodeParseResult:
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
    matched_material_id = None
    best_confidence = _calculate_confidence(raw, extracted)

    if material_db is not None:
        try:
            from app.models import MaterialMaster
            from sqlalchemy import select

            # Try exact match first
            result = await material_db.execute(
                select(MaterialMaster).where(MaterialMaster.code == extracted, MaterialMaster.active == 1)
            )
            material = result.scalar_one_or_none()
            if material:
                extracted = material.code
                matched_material_id = material.id
                best_confidence = 1.0
            else:
                # Try fuzzy match against all active materials
                result = await material_db.execute(
                    select(MaterialMaster).where(MaterialMaster.active == 1)
                )
                all_materials = result.scalars().all()
                if all_materials:
                    best_mat = None
                    best_score = 0.0
                    for mat in all_materials:
                        score = _calculate_confidence(raw, mat.code)
                        if score > best_score:
                            best_score = score
                            best_mat = mat
                    if best_mat and best_score > 0.5:
                        extracted = best_mat.code
                        matched_material_id = best_mat.id
                        best_confidence = best_score
        except Exception:
            pass

    # Boost confidence for known prefix matches
    if known_prefix:
        best_confidence = min(1.0, best_confidence + 0.1)

    # Determine format source
    if raw.upper() == extracted.upper():
        source = "exact"
    elif known_prefix:
        source = "prefix_match"
    else:
        source = "fuzzy"

    return BarcodeParseResult(
        material_code=extracted,
        confidence=best_confidence,
        source_format=source,
        raw_barcode=barcode,
        matched_material_id=matched_material_id,
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


async def find_material_candidates(
    db,
    barcode: str,
    top_n: int = 5,
    threshold: float = 0.3,
) -> List[dict]:
    """Find top N candidate materials matching a barcode.

    Args:
        db: Async database session
        barcode: Raw barcode string
        top_n: Maximum number of candidates to return
        threshold: Minimum confidence score (0.0 ~ 1.0)

    Returns:
        List of dicts, each with:
          - material_id: int
          - code: str
          - name: str
          - confidence: float
          - extracted_code: str (the code extracted from barcode)
        Sorted by confidence descending. Empty list if no match found.
    """
    raw = barcode.strip()
    if not raw:
        return []

    extracted = _extract_material_code(raw)
    known_prefix = _find_known_prefix(raw)

    from app.models import MaterialMaster
    from sqlalchemy import select

    try:
        # 1) Exact match — return immediately if found
        exact_result = await db.execute(
            select(MaterialMaster).where(
                MaterialMaster.code == extracted,
                MaterialMaster.active == 1,
            )
        )
        exact = exact_result.scalar_one_or_none()
        if exact:
            return [{
                "material_id": exact.id,
                "code": exact.code,
                "name": exact.name,
                "confidence": 1.0,
                "extracted_code": extracted,
            }]

        # 2) Fuzzy match against all active materials
        result = await db.execute(
            select(MaterialMaster).where(MaterialMaster.active == 1)
        )
        all_materials = result.scalars().all()

        scored = []
        for mat in all_materials:
            score = _calculate_confidence(raw, mat.code)
            if known_prefix:
                score = min(1.0, score + 0.1)
            if score >= threshold:
                scored.append({
                    "material_id": mat.id,
                    "code": mat.code,
                    "name": mat.name,
                    "confidence": round(score, 4),
                    "extracted_code": extracted,
                })

        # Sort by confidence descending, take top N
        scored.sort(key=lambda x: x["confidence"], reverse=True)
        return scored[:top_n]

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("find_material_candidates error: %s", e)
        return []


def add_material_pattern(material_code: str, category: str = None):
    """Register a material code pattern for future recognition."""
    KNOWN_PREFIXES.append(material_code.split('-')[0] if '-' in material_code else material_code)
    KNOWN_PREFIXES.sort()


# ══════════════════════════════════════════════════════════════════
# Enhanced supplier barcode parsing — extract quantity, batch, date
# ══════════════════════════════════════════════════════════════════

# GS1 Application Identifiers
GS1_AI = {
    "01": "gtin",
    "10": "batch_no",
    "11": "mfg_date",
    "15": "expiry_date",
    "17": "expiry_date",
    "30": "count",
    "37": "count",
    "240": "supplier_code",
    "241": "customer_part_no",
    "410": "ship_to",
}

# Known supplier barcode regex patterns
SUPPLIER_PATTERNS = [
    # Format: MATERIAL_CODE~QTY~LOT~DATE
    re.compile(r'^(?P<code>[A-Z0-9][A-Z0-9/\-.]+)[~\^](?P<qty>[\d.]+)[~\^](?P<lot>[A-Z0-9]+)[~\^](?P<date>\d{4,8})'),
    # Format: MATERIAL_CODE^LOT^DATE^QTY (Murata/TDK style)
    re.compile(r'^(?P<code>[A-Z0-9][A-Z0-9/\-.]+)[\^](?P<lot>[A-Z0-9]+)[\^](?P<date>\d{4,8})[\^](?P<qty>[\d.]+)'),
    # Format: P/N:MATERIAL_CODE QTY:1234 LOT:ABC123 D/C:2401
    re.compile(r'(?:P[/*]N[:\s]*|PART[:\s]*|MAT[:\s]*)(?P<code>[A-Z0-9][A-Z0-9/\-.]+)'),
    # GS1-128: (01)GTIN(10)LOT(17)DATE(30)QTY
    re.compile(r'\(01\)(?P<gtin>\d{14})\(10\)(?P<lot>[^)]+)\(1[157]\)(?P<date>\d{6})\(30\)(?P<qty>\d+)'),
    # Samsung/other 2D: MATERIAL_CODE QTY DATE LOT
    re.compile(r'(?P<code>[A-Z0-9]+(?:-[A-Z0-9]+){2,})\s+(?P<qty>\d+)\s+(?P<date>\d{4,8})\s+(?P<lot>[A-Z0-9]+)'),
    # Format: MATERIAL_CODE|QTY|LOT|DATE
    re.compile(r'^(?P<code>[A-Z0-9][A-Z0-9/\-.]+)\|(?P<qty>[\d.]+)\|(?P<lot>[A-Z0-9]+)\|(?P<date>\d{4,8})'),
]


def _detect_separator(barcode: str) -> Optional[str]:
    """Detect the separator character used in the barcode."""
    for sep in ['~', '^', '|', '/', ';', ',']:
        if sep in barcode:
            return sep
    return None


def extract_supplier_info(barcode: str) -> dict:
    """Extract quantity, batch/lot, date_code from supplier barcode.

    Attempts multiple supplier format patterns and GS1 parsing.
    Returns dict with keys: quantity, batch_no, date_code, spec, supplier_code
    """
    result = {
        "quantity": None,
        "batch_no": None,
        "date_code": None,
        "date_code_type": None,
        "supplier_code": None,
        "spec": None,
        "unit": None,
    }
    if not barcode:
        return result

    upper = barcode.strip().upper()

    # ── Try GS1-128 format ──
    if "(01)" in upper:
        gs1 = re.compile(r'(?:\((\d{2,3})\)([A-Z0-9]+))')
        ai_data = {}
        for m in gs1.finditer(upper):
            ai = m.group(1)
            value = m.group(2)
            ai_data[ai] = value
        if "30" in ai_data:
            result["quantity"] = float(ai_data["30"])
        elif "37" in ai_data:
            result["quantity"] = float(ai_data["37"])
        if "10" in ai_data:
            result["batch_no"] = ai_data["10"]
        if "11" in ai_data:
            result["date_code"] = ai_data["11"]
            result["date_code_type"] = "mfg_date"
        if "17" in ai_data:
            result["date_code"] = ai_data["17"]
            result["date_code_type"] = "expiry_date"
        if "240" in ai_data:
            result["supplier_code"] = ai_data["240"]
        if "241" in ai_data:
            result["spec"] = ai_data["241"]
        return result

    # ── Try known supplier patterns ──
    for pattern in SUPPLIER_PATTERNS:
        m = pattern.search(upper)
        if m:
            d = m.groupdict()
            if "qty" in d and d["qty"]:
                result["quantity"] = float(d["qty"])
            if "lot" in d and d["lot"]:
                batch = d["lot"].strip()
                if len(batch) < 50:  # sanity check
                    result["batch_no"] = batch
            if "date" in d and d["date"]:
                result["date_code"] = d["date"]
            if "gtin" in d:
                result["supplier_code"] = d["gtin"]

            # Try to extract spec/size from material code
            code = d.get("code", "")
            if code:
                # Extract size info like 0402, 0603, 0805 from code
                size_m = re.search(r'(0[46812]0[23568]|1[02]12|2[05]12|3216|3225|4532)', code)
                if size_m:
                    result["spec"] = size_m.group(1)
            return result

    # ── Fallback: try to find quantity in barcode ──
    qty_m = re.search(r'(?:QTY|QUANTITY|QTY:|QTY:)\s*(\d+)', upper)
    if qty_m:
        result["quantity"] = float(qty_m.group(1))

    lot_m = re.search(r'(?:LOT|LOT#|LOT:|BATCH|BATCH:)\s*([A-Z0-9]+)', upper)
    if lot_m:
        result["batch_no"] = lot_m.group(1)

    date_m = re.search(r'(?:D/C|D/C:|DATE|DATE:|DATE\s*CODE|DC:)\s*(\d{4,8})', upper)
    if date_m:
        result["date_code"] = date_m.group(1)

    return result
