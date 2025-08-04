from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint, request, redirect, flash, render_template, current_app, send_file
)
from flask_login import login_required

from ..helpers import upload_file, delete_blob, get_form_value
from ..models import Attachment, Guest, db, Animal

att_bp = Blueprint("attachment", __name__, url_prefix="/attachment")


@att_bp.route("/<owner_id>/upload", methods=["POST"])
@login_required
def upload_attachment(owner_id):
    """
    Expects <input type="file" name="file"> in the form.
    Saves to GCS and records in the Attachment table.
    """
    file = request.files.get("file")
    if not file:
        flash("Keine Datei ausgewählt.", "warning")
        return redirect(request.referrer)
    # 1) upload to GCS
    gcs_path = upload_file(file, owner_id)
    # 2) store metadata
    att = Attachment(
        owner_id=str(owner_id),
        filename=file.filename,
        gcs_path=gcs_path,
        uploaded_on=datetime.today()
    )
    db.session.add(att)
    db.session.commit()
    flash("Datei erfolgreich hochgeladen.", "success")
    return redirect(request.referrer)


@att_bp.route("/<int:att_id>/download")
@login_required
def download_attachment(att_id):
    att = Attachment.query.get_or_404(att_id)
    blob = current_app.bucket.blob(att.gcs_path)
    data = blob.download_as_bytes()
    return send_file(
        BytesIO(data),
        download_name=att.filename,
        as_attachment=False,
        mimetype=blob.content_type or 'application/octet-stream'
    )


@att_bp.route("/<int:att_id>/delete", methods=["POST"])
@login_required
def delete_attachment(att_id):
    """
    Deletes both the GCS object and the DB record.
    """
    att = Attachment.query.get_or_404(att_id)
    delete_blob(att.gcs_path)
    db.session.delete(att)
    db.session.commit()
    flash("Datei gelöscht.", "success")
    return redirect(request.referrer)


@att_bp.route("/list")
@login_required
def list_attachments():
    """
    List all guest attachments with upload date, guest info, filename, and actions.
    """
    # Join Attachment with Guest on owner_id
    rows = (
        db.session.query(
            Attachment.id,
            Attachment.uploaded_on,
            Guest.number,
            Guest.lastname,
            Guest.firstname,
            Attachment.filename
        )
        .join(Guest, Guest.id == Attachment.owner_id)
        .order_by(Attachment.uploaded_on.desc())
        .all()
    )
    return render_template("list_attachments.html", attachments=rows)


# Blueprint and route for setting animal profile picture

@att_bp.route("/set_animal_picture/<int:animal_id>", methods=["POST"])
@login_required
def set_animal_picture(animal_id):
    attachment_id = get_form_value("attachment_id")
    animal = Animal.query.get_or_404(animal_id)
    animal.profile_attachment_id = attachment_id
    db.session.commit()
    return redirect(request.referrer)


@att_bp.route("/remove_animal_picture/<int:animal_id>", methods=["POST"])
@login_required
def remove_animal_picture(animal_id):
    """
    Removes the profile picture for the given animal.
    """
    animal = Animal.query.get_or_404(animal_id)
    animal.profile_attachment_id = None
    db.session.commit()
    flash("Profilbild entfernt.", "success")
    return redirect(request.referrer)
