"""OCR text recognition engine — PaddleOCR (Baidu open-source).

Handles material label reading, barcode image extraction, and general
text recognition for SMT consumable management.

Usage:
    # Backend API
    from app.utils.ocr import ocr_engine, extract_text_from_image

    result = await extract_text_from_image(image_bytes)
    # {"lines": ["物料编码：ABC-2024-001", "批次号：20260616"], "text": "物料编码：ABC-2024-001 批次号：20260616"}
"""

import io
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

# Lazy import so the backend starts even without PaddleOCR installed.
# On first real use the model downloads automatically (~50MB).
_ocr_engine = None


def _get_ocr():
    """Get or create the PaddleOCR instance (lazy init)."""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR

            _ocr_engine = PaddleOCR(
                use_angle_cls=True,  # auto-orient detection
                lang="ch",           # Chinese + English digits
                show_log=False,      # silence download logs
                # Performance flags for CPU
                det_db_score_mode=True,
            )
        except ImportError:
            raise RuntimeError(
                "PaddleOCR not installed. Run: pip install paddleocr paddlepaddle"
            )
    return _ocr_engine


@dataclass
class OCRResult:
    """Single detected text line from OCR."""

    text: str              # recognized text
    confidence: float      # 0.0 – 1.0
    bbox: List[List[float]]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]


@dataclass
class OCRDocument:
    """Full OCR result from one image."""

    lines: List[OCRResult] = field(default_factory=list)
    full_text: str = ""       # all lines joined
    rotated_angle: int = 0    # auto-detected rotation angle


def extract_text_from_image(image_bytes: bytes) -> OCRDocument:
    """Extract text from an image (barcode label, material tag, etc.).

    Args:
        image_bytes: raw image data (PNG, JPEG, BMP, etc.)

    Returns:
        OCRDocument with all recognized lines and full text.
    """
    ocr = _get_ocr()
    # PaddleOCR accepts file path or BytesIO
    img_stream = io.BytesIO(image_bytes)
    result = ocr.ocr(img_stream, cls=True)

    doc = OCRDocument()
    if not result or not result[0]:
        return doc

    for line in result[0]:
        bbox = line[0]          # 4-point polygon
        text = line[1][0]       # recognized string
        confidence = line[1][1] # float score

        doc.lines.append(
            OCRResult(
                text=text,
                confidence=float(confidence),
                bbox=[[float(p[0]), float(p[1])] for p in bbox],
            )
        )

    doc.full_text = " ".join(l.text for l in doc.lines)
    return doc


def extract_text_from_file(image_path: str) -> OCRDocument:
    """Same as extract_text_from_image but reads from disk path."""
    with open(image_path, "rb") as f:
        return extract_text_from_image(f.read())


# ── SMT label extraction helpers ──────────────────────────────────────────


def extract_material_code_from_ocr(ocr_result: OCRDocument) -> Optional[str]:
    """Pick out the material code from OCR lines (e.g. "ABC-2024-001").

    Tries common label prefixes first, then falls back to alphanumeric codes.
    """
    import re

    keywords = [
        "物料编码", "物料代码", "物料号", "MATERIAL", "CODE", "PART",
        "料号", "料号编码",
    ]

    for line in ocr_result.lines:
        upper = line.text.upper()
        for kw in keywords:
            if kw in upper:
                # extract alphanumeric code after the prefix
                match = re.search(r'([A-Z0-9]+(?:-[A-Z0-9]+)+)', line.text)
                if match:
                    return match.group(1)
                return line.text.strip()

    # Fallback: find longest alphanumeric code that looks like a material ID
    candidates = []
    for line in ocr_result.lines:
        match = re.search(r'([A-Z0-9]+(?:-[A-Z0-9]+){2,})', line.text)
        if match:
            candidates.append((len(match.group(1)), match.group(1)))

    if candidates:
        return max(candidates, key=lambda c: c[0])[1]

    return None


def extract_batch_info_from_ocr(
    ocr_result: OCRDocument,
) -> dict:
    """Extract batch / lot / date info from OCR lines."""
    info: dict = {}
    import re

    label_map = {
        "批次号": ("batch", re.compile(r"[A-Z0-9\-]{6,}")),
        "LOT": ("lot", re.compile(r"[A-Z0-9\-]{6,}")),
        "DATE": ("date", re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}")),
        "生产日期": ("date", re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}")),
        "有效期": ("expiry", re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}")),
        "EXPIRY": ("expiry", re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}")),
    }

    for line in ocr_result.lines:
        for keyword, (key, pattern) in label_map.items():
            if keyword in line.text:
                match = pattern.search(line.text)
                if match:
                    info[key] = match.group()
    return info
