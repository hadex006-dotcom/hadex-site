"""
Storage backend for Hadex Factory.

If R2 (Cloudflare) env vars are set, files, images and the catalog JSON are
stored in an R2 bucket (S3-compatible) so they survive restarts/redeploys.
Otherwise everything falls back to the local filesystem, so the local dev
server keeps working with no extra setup.
"""
import os
import io
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
IMAGE_DIR = os.path.join(BASE_DIR, "uploads", "images")
DB_FILE = os.path.join(BASE_DIR, "software.json")
DB_KEY = "software.json"

# Works with any S3-compatible store (Cloudflare R2, Supabase, AWS S3...).
# Env var names keep the R2_ prefix for backwards compatibility.
R2_BUCKET = os.environ.get("R2_BUCKET")
R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_REGION = os.environ.get("R2_REGION", "auto")  # Supabase needs a real region

REMOTE = all([R2_BUCKET, R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY])

_client = None
if REMOTE:
    import boto3
    from botocore.config import Config
    _client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},  # required by Supabase, fine for R2
        ),
        region_name=R2_REGION,
    )
else:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)


def backend_name():
    if not REMOTE:
        return "local disk"
    if "supabase" in (R2_ENDPOINT or ""):
        return "Supabase Storage"
    if "r2.cloudflarestorage" in (R2_ENDPOINT or ""):
        return "Cloudflare R2"
    return "S3-compatible storage"


def stream_size(fileobj):
    """Size of an open upload stream, leaving the cursor at the start."""
    fileobj.seek(0, os.SEEK_END)
    size = fileobj.tell()
    fileobj.seek(0)
    return size


# Catalog (software.json) ------------------------------------------------------
def read_db():
    if REMOTE:
        try:
            obj = _client.get_object(Bucket=R2_BUCKET, Key=DB_KEY)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except _client.exceptions.NoSuchKey:
            return []
        except Exception:
            return []
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def write_db(items):
    data = json.dumps(items, indent=2).encode("utf-8")
    if REMOTE:
        _client.put_object(
            Bucket=R2_BUCKET, Key=DB_KEY, Body=data,
            ContentType="application/json",
        )
        return
    with open(DB_FILE, "w", encoding="utf-8") as f:
        f.write(data.decode("utf-8"))


# Binary objects (files + images) ----------------------------------------------
def put(key, fileobj, content_type=None):
    """Store an upload stream under `key`. Returns its size in bytes."""
    size = stream_size(fileobj)
    if REMOTE:
        extra = {"ContentType": content_type} if content_type else {}
        _client.upload_fileobj(fileobj, R2_BUCKET, key, ExtraArgs=extra)
    else:
        path = _local_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fileobj.save(path)
    return size


def delete(key):
    if REMOTE:
        try:
            _client.delete_object(Bucket=R2_BUCKET, Key=key)
        except Exception:
            pass
    else:
        try:
            os.remove(_local_path(key))
        except OSError:
            pass


def presigned_url(key, download_name=None, expires=3600):
    """A temporary public URL for `key` (R2 only)."""
    params = {"Bucket": R2_BUCKET, "Key": key}
    if download_name:
        params["ResponseContentDisposition"] = (
            f'attachment; filename="{download_name}"'
        )
    return _client.generate_presigned_url(
        "get_object", Params=params, ExpiresIn=expires
    )


def _local_path(key):
    # keys look like "files/<name>" or "images/<name>"
    return os.path.join(UPLOAD_DIR, *key.split("/"))


def local_dir_and_name(key):
    """For local serving via send_from_directory."""
    path = _local_path(key)
    return os.path.dirname(path), os.path.basename(path)
