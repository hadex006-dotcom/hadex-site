"""
Hadex Factory - Software download site
A small Flask app: public download page + password-protected upload page.
Files are stored in Cloudflare R2 when configured, else on local disk.
"""
import os
from datetime import datetime
from functools import wraps
from flask import (
    Flask, request, render_template, redirect, url_for,
    send_from_directory, session, flash, abort
)
from werkzeug.utils import secure_filename

import storage

# Config from environment (with safe local defaults) ---------------------------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "500"))

# Allowed file types for upload
ALLOWED_EXT = {
    ".exe", ".msi", ".zip", ".rar", ".7z", ".bat", ".ps1",
    ".apk", ".dmg", ".pkg", ".deb", ".iso", ".tar", ".gz", ".jar"
}

# Allowed image types for software screenshots/icons
ALLOWED_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024


def human_size(num):
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


# Auth -------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# Routes -----------------------------------------------------------------------
@app.route("/")
def index():
    items = sorted(storage.read_db(), key=lambda x: x.get("uploaded", ""), reverse=True)
    total_downloads = sum(i.get("downloads", 0) for i in items)
    return render_template("index.html", items=items, total_downloads=total_downloads)


@app.route("/download/<file_id>")
def download(file_id):
    items = storage.read_db()
    item = next((i for i in items if i["id"] == file_id), None)
    if not item:
        abort(404)
    item["downloads"] = item.get("downloads", 0) + 1
    storage.write_db(items)

    key = f"files/{item['stored_name']}"
    if storage.REMOTE:
        return redirect(storage.presigned_url(key, download_name=item["filename"]))
    directory, name = storage.local_dir_and_name(key)
    return send_from_directory(
        directory, name, as_attachment=True, download_name=item["filename"]
    )


@app.route("/image/<path:filename>")
def image(filename):
    key = f"images/{filename}"
    if storage.REMOTE:
        return redirect(storage.presigned_url(key))
    directory, name = storage.local_dir_and_name(key)
    return send_from_directory(directory, name)


@app.route("/health")
def health():
    return {"backend": storage.backend_name(), "remote": storage.REMOTE}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin"))
        flash("Wrong password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if request.method == "POST":
        file = request.files.get("file")
        name = request.form.get("name", "").strip()
        version = request.form.get("version", "").strip()
        desc = request.form.get("description", "").strip()

        if not file or file.filename == "":
            flash("Pick a file to upload.")
            return redirect(url_for("admin"))

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            flash(f"File type {ext} not allowed.")
            return redirect(url_for("admin"))

        safe = secure_filename(file.filename)
        file_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        stored_name = f"{file_id}_{safe}"
        size = storage.put(f"files/{stored_name}", file)

        # Optional screenshot/icon image
        image_name = ""
        image = request.files.get("image")
        if image and image.filename:
            img_ext = os.path.splitext(image.filename)[1].lower()
            if img_ext in ALLOWED_IMG_EXT:
                image_name = f"{file_id}{img_ext}"
                storage.put(f"images/{image_name}", image,
                            content_type=f"image/{img_ext.lstrip('.')}")
            else:
                flash(f"Image type {img_ext} not allowed; uploaded without image.")

        items = storage.read_db()
        items.append({
            "id": file_id,
            "name": name or safe,
            "version": version,
            "description": desc,
            "filename": safe,
            "stored_name": stored_name,
            "image": image_name,
            "size": human_size(size),
            "uploaded": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "downloads": 0,
        })
        storage.write_db(items)
        flash(f"Uploaded '{name or safe}'.")
        return redirect(url_for("admin"))

    items = sorted(storage.read_db(), key=lambda x: x.get("uploaded", ""), reverse=True)
    return render_template("admin.html", items=items)


@app.route("/delete/<file_id>", methods=["POST"])
@login_required
def delete(file_id):
    items = storage.read_db()
    item = next((i for i in items if i["id"] == file_id), None)
    if item:
        storage.delete(f"files/{item['stored_name']}")
        if item.get("image"):
            storage.delete(f"images/{item['image']}")
        items = [i for i in items if i["id"] != file_id]
        storage.write_db(items)
        flash("Deleted.")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
