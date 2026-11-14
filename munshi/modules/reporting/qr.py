"""QR helpers: PNG (API responses) and a reportlab drawing (embedded in the PDF, deterministic)."""
from __future__ import annotations

import base64
import io

import qrcode
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing


def png_base64(payload: str) -> str:
    img = qrcode.make(payload, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def drawing(payload: str, size: int = 90) -> Drawing:
    w = QrCodeWidget(payload)
    x1, y1, x2, y2 = w.getBounds()
    d = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    d.add(w)
    return d
