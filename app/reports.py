import io
import os
from datetime import datetime

import qrcode
import requests
from flask import current_app
from flask import flash
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .helpers import format_date
from .models import Guest, Setting





def generate_gast_card_pdf(guest_id):
    return generate_multiple_gast_cards_pdf([guest_id],double_sided=True)

def generate_multiple_gast_cards_pdf(guest_ids, double_sided=False):
    format = Setting.query.filter_by(setting_key="guestCardFormat").first()
    if format.value == "LP898":
        return generate_multiple_gast_cards_pdf_LP898(guest_ids, double_sided=double_sided)
    else:
        return generate_multiple_gast_cards_pdf_DP839(guest_ids, double_sided=double_sided)

def generate_multiple_gast_cards_pdf_LP898(guest_ids, double_sided=False):
    """
    Generate an A4 PDF sheet with multiple guest cards laid out for perforated paper.
    guest_ids: list of integer Guest IDs.
    Returns a BytesIO buffer containing the PDF.
    """
    from reportlab.lib.pagesizes import A4
    # card and margin sizes in millimeters
    card_width = 90 * mm
    card_height = 54 * mm
    left_margin = 15 * mm
    between_cols = 0 * mm
    top_margin = 10 * mm

    page_width, page_height = A4

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)

    for idx, guest_id in enumerate(guest_ids):
        # Load Guest object
        guest = Guest.query.get(guest_id)
        if not guest:
            continue
        if idx > 0 and idx % 10 == 0:
            c.showPage()
        pos = idx % 10
        row = pos // 2
        col = pos % 2

        x = left_margin + col * (card_width + between_cols)
        y = page_height - top_margin - (row + 1) * card_height



        # QR Code
        qr_img = qrcode.make(str(guest.id))
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        qr_reader = ImageReader(qr_buffer)

        # QR-Code links vertikal mittig
        qr_size = card_width / 2
        qr_x = x + 5 * mm
        qr_y = y + (card_height - qr_size) / 2
        c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size)

        text_x = qr_x + qr_size + 5 * mm
        center_x = x + card_width / 2

        # Überschrift zentriert oben mittig
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(center_x, y + card_height - 5 * mm, "Gästekarte")

        # Infozeilen linksbündig in der rechten Spalte
        c.setFont("Helvetica", 12)
        info_y = y + card_height - 5 * mm - 26
        c.drawString(text_x, info_y, f"Name:")
        info_y -= 14
        c.drawString(text_x, info_y, f"{guest.firstname} {guest.lastname}")
        info_y -= 18
        c.drawString(text_x, info_y, f"Nummer:")
        info_y -= 14
        c.drawString(text_x, info_y, f"{guest.number}")
        info_y -= 18
        c.drawString(text_x, info_y, f"Mitglied seit:")
        info_y -= 14
        c.drawString(text_x, info_y, str(guest.member_since)[:4])

    if double_sided:
        # Rückseiten drucken
        c.showPage()
        # Logo-Einstellungen einmalig laden
        logo_setting = Setting.query.filter_by(setting_key="logourl").first()
        logo_url = logo_setting.value if logo_setting else None

        # Funktion zum Laden eines Logos
        def load_logo(url):
            if not url or url == "/static/logo.png":
                path = os.path.join(current_app.root_path, "static", "logo.png")
                return ImageReader(path)
            if url.startswith("http"):
                resp = requests.get(url)
                resp.raise_for_status()
                return ImageReader(io.BytesIO(resp.content))
            # lokaler Pfad relativ zum static-Ordner
            path = os.path.join(current_app.root_path, "static", url)
            return ImageReader(path)

        logo_reader = load_logo(logo_url)

        for idx, guest_id in enumerate(guest_ids):
            if idx > 0 and idx % 10 == 0:
                c.showPage()
            pos = idx % 10
            row = pos // 2
            col = pos % 2
            x = left_margin + col * (card_width + between_cols)
            y = page_height - top_margin - (row + 1) * card_height


            # Großes Logo zentriert
            logo_size = min(card_width - 20 * mm, card_height - 20 * mm)
            lx = x + (card_width - logo_size) / 2
            ly = y + (card_height - logo_size) / 2
            c.drawImage(logo_reader, lx, ly, width=logo_size, height=logo_size,
                        preserveAspectRatio=True, mask="auto")

            # Kleines statisches Logo unter dem großen Logo
            small_logo_path = os.path.join(current_app.root_path, "static", "logo.png")
            print(os.path.exists(small_logo_path))
            small_reader = ImageReader(small_logo_path)
            small_size = 10 * mm
            small_x = x + (card_width - small_size) / 2
            small_y = ly - small_size - 2 * mm
            c.drawImage(
                small_reader,
                small_x,
                small_y,
                width=small_size,
                height=small_size,
                preserveAspectRatio=True,
                mask="auto"
            )



    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer



def generate_multiple_gast_cards_pdf_DP839(guest_ids, double_sided=False):
    """
    Generate an A4 PDF sheet with multiple guest cards laid out for perforated paper.
    guest_ids: list of integer Guest IDs.
    Returns a BytesIO buffer containing the PDF.
    """
    from reportlab.lib.pagesizes import A4
    # card and margin sizes in millimeters
    card_width = 85 * mm
    card_height = 55 * mm
    left_margin = 15 * mm
    between_cols = 10 * mm
    top_margin = 10 * mm

    page_width, page_height = A4

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)

    for idx, guest_id in enumerate(guest_ids):
        # Load Guest object
        guest = Guest.query.get(guest_id)
        if not guest:
            continue
        if idx > 0 and idx % 10 == 0:
            c.showPage()
        pos = idx % 10
        row = pos // 2
        col = pos % 2

        x = left_margin + col * (card_width + between_cols)
        y = page_height - top_margin - (row + 1) * card_height



        # QR Code
        qr_img = qrcode.make(str(guest.id))
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        qr_reader = ImageReader(qr_buffer)
        qr_size = 1.5 * inch
        qr_x = x + 5
        qr_y = y + card_height - qr_size - 5
        c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size)

        # Text Block
        text_x = qr_x + qr_size + 2 * mm
        top_align = y + card_height - 30
        c.setFont("Helvetica-Bold", 12)
        c.drawString(text_x, top_align, "Gästekarte")
        issue_date = format_date(datetime.now())[-4:]
        c.setFont("Helvetica", 8)
        line_gap = 20
        line_y = top_align - line_gap
        fields = [
            ("Name:", f"{guest.firstname} {guest.lastname}"),
            ("Nummer:", guest.number),
            ("Mitglied seit:", guest.number[:4])
        ]
        for label, value in fields:
            c.drawString(text_x, line_y, label)
            line_y -= 10
            c.drawString(text_x, line_y, value)
            line_y -= 14

    if double_sided:
        # Rückseiten drucken
        c.showPage()
        # Logo-Einstellungen einmalig laden
        logo_setting = Setting.query.filter_by(setting_key="logourl").first()
        logo_url = logo_setting.value if logo_setting else None

        # Funktion zum Laden eines Logos
        def load_logo(url):
            if not url or url == "/static/logo.png":
                path = os.path.join(current_app.root_path, "static", "logo.png")
                return ImageReader(path)
            if url.startswith("http"):
                resp = requests.get(url)
                resp.raise_for_status()
                return ImageReader(io.BytesIO(resp.content))
            # lokaler Pfad relativ zum static-Ordner
            path = os.path.join(current_app.root_path, "static", url)
            return ImageReader(path)

        logo_reader = load_logo(logo_url)

        for idx, guest_id in enumerate(guest_ids):
            if idx > 0 and idx % 10 == 0:
                c.showPage()
            pos = idx % 10
            row = pos // 2
            col = pos % 2
            x = left_margin + col * (card_width + between_cols)
            y = page_height - top_margin - (row + 1) * card_height


            # Großes Logo zentriert
            logo_size = min(card_width - 20 * mm, card_height - 20 * mm)
            lx = x + (card_width - logo_size) / 2
            ly = y + (card_height - logo_size) / 2
            c.drawImage(logo_reader, lx, ly, width=logo_size, height=logo_size,
                        preserveAspectRatio=True, mask="auto")



    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer
