import io
import os
from datetime import datetime
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.units import mm

import qrcode
import requests
from flask import current_app
from flask import flash
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .helpers import format_date
from .models import Guest, Setting
import math
from flask_login import current_user

def generate_gast_card_pdf(guest_id):
    return generate_multiple_gast_cards_pdf([guest_id], double_sided=True)

def generate_multiple_gast_cards_pdf(guest_ids, double_sided=False, flip_backside=False):
    format = Setting.query.filter_by(setting_key="guestCardFormat").first()
    if format.value == "LP898":
        return generate_multiple_gast_cards_pdf_LP898(guest_ids, double_sided=double_sided, flip_backside=flip_backside)
    else:
        return generate_multiple_gast_cards_pdf_DP839(guest_ids, double_sided=double_sided, flip_backside=flip_backside)

def generate_multiple_gast_cards_pdf_LP898(guest_ids, double_sided=False, flip_backside=False):
    """
    Generate an A4 PDF sheet with multiple guest cards laid out for perforated paper.
    guest_ids: list of integer Guest IDs.
    Returns a BytesIO buffer containing the PDF.
    """
    from reportlab.lib.pagesizes import A4
    page_width, page_height = A4

    # card and margin sizes; fixed to 90×54 mm with 10 mm top/bottom and 15 mm left/right
    card_width = 90 * mm
    card_height = 54 * mm
    top_margin = 10 * mm
    left_margin = 15 * mm
    between_cols = 0 * mm

    bottom_margin = 10 * mm
    card_rows = 5  # two columns × 5 rows = 10 cards
    # vertical gap so cards + margins fill full A4 height
    vertical_gap = (
        page_height
        - top_margin
        - bottom_margin
        - (card_rows * card_height)
    ) / (card_rows - 1)
    # compute bottom Y for each row
    y_positions = [
        page_height
        - top_margin
        - row * (card_height + vertical_gap)
        - card_height
        for row in range(card_rows)
    ]


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
        y = y_positions[row]

        # Compute center of this card
        center_x = x + card_width / 2
        center_y = y + card_height / 2


        # QR-Code im linken Kartenviertel um den Kartenzentrum zentriert
        qr_size = card_width / 2
        # Horizontaler Mittelpunkt des linken Viertels
        qr_center_x = center_x - card_width / 4
        qr_x = qr_center_x - qr_size / 2
        qr_y = center_y - qr_size / 2
        qr_img = qrcode.make(str(guest.id))
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        qr_reader = ImageReader(qr_buffer)
        c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size)

        text_x = qr_x + qr_size + 1 * mm
        # Überschrift zentriert oben mittig
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(center_x, y + card_height - 7 * mm, "Gästekarte")

        # Infozeilen linksbündig in der rechten Spalte
        c.setFont("Helvetica", 12)
        info_y = y + card_height - 5 * mm - 26
        c.drawString(text_x, info_y, f"{guest.firstname}")
        info_y -= 14
        c.drawString(text_x, info_y, f"{guest.lastname}")
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
            if flip_backside:
                col = 1 - col
            x = left_margin + col * (card_width + between_cols)
            y = y_positions[row]

            # Logos innerhalb der Kartenränder platzieren
            inner_margin = 5 * mm
            small_size = 10 * mm
            spacing = 1 * mm

            # Großes Logo oben zentriert im inneren Bereich
            logo_size = min(card_width - 2 * inner_margin,
                            card_height - 2 * inner_margin - small_size - spacing)
            logo_x = x + (card_width - logo_size) / 2
            logo_y = y + card_height - inner_margin - logo_size
            c.drawImage(logo_reader,
                        logo_x, logo_y,
                        width=logo_size, height=logo_size,
                        preserveAspectRatio=True, mask="auto")

            # Kleines statisches Logo unten zentriert im inneren Bereich
            small_logo_path = os.path.join(current_app.root_path, "static", "logo.png")
            small_reader = ImageReader(small_logo_path)
            small_x = x + (card_width - small_size) / 2
            small_y = logo_y - small_size - spacing
            c.drawImage(small_reader,
                        small_x, small_y,
                        width=small_size, height=small_size,
                        preserveAspectRatio=True, mask="auto")



    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer



def generate_multiple_gast_cards_pdf_DP839(guest_ids, double_sided=False, flip_backside=False):
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
            if flip_backside:
                col = 1 - col
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

def generate_payment_report(records, from_date, to_date):
    """
    Generate an A4 PDF report of payments, matching the HTML layout:
    header with logo and metadata, report title, date range,
    entry count, and a table with totals in the footer.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from flask_login import current_user
    from .models import Setting
    from flask import current_app
    import requests

    def f_n(n):
        return f"{n:.2f}".replace(".", ",")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=15 * mm
    )
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle('header', parent=styles['Normal'], fontSize=10, leading=12)
    footer_style = ParagraphStyle('footer', parent=styles['Normal'], fontSize=9, leading=11, alignment=1)
    title_style = styles['Heading1']

    elements = []

    # Load logo
    logo_setting = Setting.query.filter_by(setting_key="logourl").first()
    logo_url = logo_setting.value if logo_setting else None
    def load_logo(url):
        if not url or url == "/static/logo.png":
            return os.path.join(current_app.root_path, "static", "logo.png")
        if url.startswith("http"):
            resp = requests.get(url)
            resp.raise_for_status()
            tmp = io.BytesIO(resp.content)
            return tmp
        return os.path.join(current_app.root_path, "static", url)
    logo_src = load_logo(logo_url)

    # Pagination: split into pages of 25 rows
    page_size = 25
    chunks = [records[i:i+page_size] for i in range(0, len(records), page_size)]
    total_pages = len(chunks)

    for page_index, chunk in enumerate(chunks):
        # Logo zentriert oben auf jeder Seite
        logo_img = Image(logo_src, width=35*mm, height=25*mm)
        logo_img.hAlign = 'CENTER'
        elements.append(logo_img)
        elements.append(Spacer(1, 6))

        # Titel und Metadaten nur auf der ersten Seite
        if page_index == 0:
            elements.append(Paragraph(f"Zahlungsbericht {from_date.strftime('%d.%m.%Y')} – {to_date.strftime('%d.%m.%Y')}", title_style))
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"Erstellt von: {current_user.realname}, am {datetime.now().strftime('%d.%m.%Y %H:%M')}", header_style))
            elements.append(Paragraph(f"Anzahl Einträge: {len(records)}", header_style))
            elements.append(Spacer(1, 6))


        # Compute sums of all previous pages
        prev_records = [r for rec_chunk in chunks[:page_index] for r in rec_chunk]
        prev_food = sum(float(getattr(r, 'food_amount', getattr(r, 'futter_betrag', 0))) for r in prev_records)
        prev_other = sum(float(getattr(r, 'other_amount', getattr(r, 'zubehoer_betrag', 0))) for r in prev_records)



        # Table data for this page
        data = [['Datum', 'Gastnummer', 'Name', 'Futter (€)', 'Zubehör (€)', 'Kommentar']]
        # Carry-over-Zeile für alle Seiten außer der ersten
        if page_index > 0:
            data.append([
                'Übertrag', '', '',
                f_n(prev_food),
                f_n(prev_other),
                f_n(prev_other+prev_food),
            ])
        for r in chunk:
            data.append([
                r.paid_on.strftime('%d.%m.%Y'),
                getattr(r, 'number', getattr(r, 'guest_number', '')),
                f"{getattr(r, 'firstname')} {getattr(r, 'lastname')}",
                f_n(float(getattr(r, 'food_amount', getattr(r, 'futter_betrag', 0)))),
                f_n(float(getattr(r, 'other_amount', getattr(r, 'zubehoer_betrag', 0)))),
                getattr(r, 'comment') or ''
            ])
        # Zwischensumme inklusive Übertrag
        # Subtotal including carry-over
        page_food = sum(float(getattr(r, 'food_amount', getattr(r, 'futter_betrag', 0))) for r in chunk)
        page_other = sum(float(getattr(r, 'other_amount', getattr(r, 'zubehoer_betrag', 0))) for r in chunk)
        cumulative_food = prev_food + page_food
        cumulative_other = prev_other + page_other
        if page_index+1 == total_pages:
            data.append([
                'Gesamtsumme', '', '',
                f_n(cumulative_food),
                f_n(cumulative_other),
                f_n(cumulative_food + cumulative_other),
            ])
        else:
            data.append([
                'Zwischensumme', '', '',
                f_n(cumulative_food),
                f_n(cumulative_other),
                f_n(cumulative_food + cumulative_other),
            ])

        # Build table and apply base style
        table = Table(data, repeatRows=1)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ])

        # Bold "Übertrag" row if present (always at index 1 when page_index > 0)
        if page_index > 0:
            style.add('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold')

        # Bold the last row (subtotal or total)
        last_row = len(data) - 1
        style.add('FONTNAME', (0, last_row), (-1, last_row), 'Helvetica-Bold')

        table.setStyle(style)
        elements.append(table)
        elements.append(Spacer(1, 6))



        # Footer with page number
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"Seite {page_index+1} von {total_pages}", footer_style))
        elements.append(Spacer(1, 8))
        # Pfotenregister-Logo und Text im Footer
        logo_path = os.path.join(current_app.root_path, 'static', 'logo.png')
        elements.append(Image(logo_path, width=15 * mm, height=15 * mm))
        elements.append(Spacer(1, 4))

        elements.append(Paragraph("Erstellt mit Pfotenregister", footer_style))
        elements.append(Spacer(1, 6))

        if page_index < total_pages - 1:
            elements.append(PageBreak())

    # Build document
    doc.build(elements)
    buffer.seek(0)
    return buffer
