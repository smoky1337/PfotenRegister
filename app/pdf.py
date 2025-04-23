import io
import os
from datetime import datetime
import qrcode
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from .helpers import format_date
from .db import get_setting_value
from flask import current_app  # <--- Importieren!
import requests


def generate_gast_card_pdf(name, user_code):
    card_width = 3.375 * inch
    card_height = 2.125 * inch
    total_height = card_height * 2

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=(card_width, total_height))

    # Front Side (top half)
    front_origin_y = card_height
    c.setLineWidth(1)
    c.rect(5, front_origin_y + 5, card_width - 10, card_height - 10)
    top_align = front_origin_y + card_height - 30

    # QR Code
    qr_img = qrcode.make(user_code)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_reader = ImageReader(qr_buffer)
    qr_size = 1.5 * inch
    qr_x = 10
    qr_y = top_align - qr_size
    c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size)

    # Text Block
    text_x = qr_x + qr_size + 10
    header_center_x = (qr_x + qr_size + (card_width - 10)) / 2
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(header_center_x, top_align, "Gästekarte")
    issue_date = format_date(datetime.now())
    c.setFont("Helvetica", 8)
    line_gap = 20
    line_y = top_align - line_gap
    fields = [("Name:", name), ("ID:", user_code), ("Ausstellungsdatum:", issue_date)]
    for label, value in fields:
        c.drawString(text_x, line_y, label)
        line_y -= 10
        c.drawString(text_x, line_y, value)
        line_y -= 14

    # Back Side (bottom half)
    c.saveState()
    c.translate(card_width, card_height)
    c.rotate(180)
    c.setLineWidth(1)
    c.rect(5, 5, card_width - 10, card_height - 10)
    logo_url = get_setting_value("logourl")
    logo_reader = None

    if not logo_url:
        logo_path = os.path.join("app", "static", "logo.png")
        logo_reader = ImageReader(logo_path)
    else:
        if logo_url.startswith("http"):
            # Versuche Bild von URL zu laden
            try:
                response = requests.get(logo_url)
                response.raise_for_status()
                logo_stream = io.BytesIO(response.content)
                logo_reader = ImageReader(logo_stream)
            except Exception as e:
                raise FileNotFoundError(f"Konnte Logo von URL nicht laden: {e}")
        else:
            # Lokaler Pfad
            logo_path = os.path.join("app", "static", logo_url)
            logo_reader = ImageReader(logo_path)

    if not logo_reader:
        raise FileNotFoundError("Kein gültiges Logo gefunden!")
    logo_width = 1.5 * inch
    logo_height = 1.5 * inch
    logo_x = (card_width - logo_width) / 2
    logo_y = (card_height - logo_height) / 2
    c.drawImage(
        logo_reader,
        logo_x,
        logo_y,
        width=logo_width,
        height=logo_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.restoreState()

    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer
