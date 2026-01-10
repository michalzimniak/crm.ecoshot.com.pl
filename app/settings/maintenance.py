"""Maintenance / backup utilities.

Implements:
- database backup (SQL dump)
- database restore (SQL import)
- full backup (DB + uploads directory)
- destructive purge of selected business data (and related uploaded files)

All operations are intended to be protected by MANAGE_SETTINGS permission.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from flask import current_app
from werkzeug.exceptions import BadRequest

from app.extensions import db

from app.settings.models import Setting

try:
    from sqlalchemy import text
except Exception:  # pragma: no cover
    text = None  # type: ignore


def _now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _upload_base_dir() -> str:
    base = current_app.config.get("UPLOAD_FOLDER") or "uploads"
    return os.path.abspath(base)


def _backups_dir() -> str:
    # Store backups under uploads/backups
    base = _upload_base_dir()
    path = os.path.join(base, "backups")
    os.makedirs(path, exist_ok=True)
    return path


def _full_backups_dir() -> str:
    path = os.path.join(_backups_dir(), "full")
    os.makedirs(path, exist_ok=True)
    return path


def _auto_backup_lock_path() -> str:
    return os.path.join(_backups_dir(), "auto_backup.lock")


def _acquire_file_lock(path: str):
    """Return open file handle with an exclusive non-blocking lock, or None."""
    try:
        import fcntl

        f = open(path, "a+")
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            f.seek(0)
            f.truncate(0)
            f.write(str(os.getpid()))
            f.flush()
            return f
        except Exception:
            try:
                f.close()
            except Exception:
                pass
            return None
    except Exception:
        return None


def _is_within_base(path: str, base: str) -> bool:
    try:
        abs_path = os.path.abspath(path)
        abs_base = os.path.abspath(base)
        return abs_path == abs_base or abs_path.startswith(abs_base + os.sep)
    except Exception:
        return False


def _safe_unlink(path: str, base: str) -> bool:
    if not path:
        return False
    try:
        abs_path = os.path.abspath(path)
        if not _is_within_base(abs_path, base):
            return False
        if os.path.isfile(abs_path) or os.path.islink(abs_path):
            os.remove(abs_path)
            return True
        return False
    except Exception:
        return False


def _safe_rmtree(path: str, base: str) -> bool:
    if not path:
        return False
    try:
        abs_path = os.path.abspath(path)
        if not _is_within_base(abs_path, base):
            return False
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path, ignore_errors=True)
            return True
        return False
    except Exception:
        return False


def _db_url_info() -> dict:
    url = db.engine.url
    return {
        "drivername": url.drivername,
        "username": url.username,
        "password": url.password,
        "host": url.host,
        "port": url.port,
        "database": url.database,
    }


def _require_mysql_tools() -> tuple[str, str]:
    # Support common variants depending on distro (MariaDB packages).
    mysqldump = shutil.which("mysqldump") or shutil.which("mariadb-dump")
    mysql = shutil.which("mysql") or shutil.which("mariadb")
    if not mysqldump:
        raise BadRequest(
            'Brak narzędzia "mysqldump"/"mariadb-dump" na serwerze. '
            'Zainstaluj pakiet klienta MySQL/MariaDB (np. mysql-client lub mariadb-client).'
        )
    if not mysql:
        raise BadRequest(
            'Brak narzędzia "mysql"/"mariadb" na serwerze. '
            'Zainstaluj pakiet klienta MySQL/MariaDB (np. mysql-client lub mariadb-client).'
        )
    return mysqldump, mysql


def _mysql_escape_value(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (bytes, bytearray, memoryview)):
        b = bytes(value)
        return "0x" + b.hex()
    if isinstance(value, datetime):
        return "'" + value.strftime("%Y-%m-%d %H:%M:%S") + "'"
    # date objects are returned as date in some drivers
    try:
        from datetime import date as _date

        if isinstance(value, _date) and not isinstance(value, datetime):
            return "'" + value.strftime("%Y-%m-%d") + "'"
    except Exception:
        pass

    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("\x00", "\\0")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    s = s.replace("\x1a", "\\Z")
    s = s.replace("'", "\\'")
    return "'" + s + "'"


def _create_mysql_dump_via_sqlalchemy(out_path: str) -> None:
    if text is None:
        raise BadRequest("Brak SQLAlchemy text() - nie można wykonać backupu")

    with db.engine.connect() as conn, open(out_path, "w", encoding="utf-8") as f:
        f.write("-- EcoShot CRM backup (fallback, generated via SQLAlchemy)\n")
        f.write(f"-- Generated at: {datetime.utcnow().isoformat()}Z\n\n")
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")
        f.write("SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n")
        f.write("SET NAMES utf8mb4;\n\n")

        tables = [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]

        for table in tables:
            # Skip views (SHOW TABLES doesn't include type). Best-effort check.
            try:
                create_row = conn.execute(text(f"SHOW CREATE TABLE `{table}`")).fetchone()
                if not create_row or len(create_row) < 2:
                    continue
                create_sql = create_row[1]
            except Exception:
                continue

            f.write(f"\n-- ----------------------------\n")
            f.write(f"-- Table structure for `{table}`\n")
            f.write(f"-- ----------------------------\n")
            f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
            f.write(create_sql.rstrip(";") + ";\n\n")

            # Dump data
            result = conn.execute(text(f"SELECT * FROM `{table}`"))
            rows = result.fetchall()
            if not rows:
                continue

            cols = list(result.keys())
            col_list = ", ".join(f"`{c}`" for c in cols)

            f.write(f"-- Dumping data for `{table}`\n")
            batch_size = 200
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                values_sql = []
                for row in chunk:
                    vals = [_mysql_escape_value(row[j]) for j in range(len(cols))]
                    values_sql.append("(" + ", ".join(vals) + ")")
                f.write(f"INSERT INTO `{table}` ({col_list}) VALUES\n")
                f.write(",\n".join(values_sql))
                f.write(";\n")

        f.write("\nSET FOREIGN_KEY_CHECKS=1;\n")


def create_db_dump_file() -> tuple[str, str]:
    """Create a DB dump file and return (abs_path, download_name)."""
    info = _db_url_info()
    driver = (info.get("drivername") or "").lower()

    stamp = _now_stamp()

    if driver.startswith("sqlite"):
        # Best-effort for sqlite: copy the DB file if file-based.
        # For in-memory, backup is not available.
        db_path = None
        try:
            # sqlite:////abs/path.db or sqlite:///rel.db
            db_path = db.engine.url.database
        except Exception:
            db_path = None

        if not db_path or db_path in {":memory:", ""}:
            raise BadRequest("Backup SQLite in-memory nie jest wspierany")

        src = os.path.abspath(db_path)
        if not os.path.exists(src):
            raise BadRequest("Nie znaleziono pliku bazy SQLite")

        out_fd, out_path = tempfile.mkstemp(prefix=f"db_backup_{stamp}_", suffix=".sqlite")
        os.close(out_fd)
        shutil.copy2(src, out_path)
        return out_path, f"db_backup_{stamp}.sqlite"

    if driver.startswith("mysql"):
        database = info.get("database")
        if not database:
            raise BadRequest("Brak nazwy bazy w konfiguracji")

        out_fd, out_path = tempfile.mkstemp(prefix=f"db_backup_{stamp}_", suffix=".sql")
        os.close(out_fd)

        # Prefer native tools when present; otherwise fall back to SQLAlchemy dump.
        mysqldump = shutil.which("mysqldump") or shutil.which("mariadb-dump")
        if not mysqldump:
            try:
                _create_mysql_dump_via_sqlalchemy(out_path)
                return out_path, f"db_backup_{stamp}.sql"
            except Exception as e:
                try:
                    os.remove(out_path)
                except Exception:
                    pass
                raise BadRequest(
                    'Brak "mysqldump"/"mariadb-dump" oraz nie udało się wykonać fallback backupu. '
                    'Zainstaluj mysql-client/mariadb-client lub sprawdź dostęp do DB.'
                ) from e

        cmd = [
            mysqldump,
            "--single-transaction",
            "--quick",
            "--routines",
            "--events",
            "--triggers",
            "--add-drop-table",
            "--default-character-set=utf8mb4",
            "--set-gtid-purged=OFF",
            "--no-tablespaces",
        ]

        host = info.get("host")
        port = info.get("port")
        username = info.get("username")
        password = info.get("password")

        if host:
            cmd += ["-h", str(host)]
        if port:
            cmd += ["-P", str(port)]
        if username:
            cmd += ["-u", str(username)]

        cmd.append(str(database))

        env = os.environ.copy()
        if password:
            env["MYSQL_PWD"] = str(password)

        with open(out_path, "wb") as f:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)

        if proc.returncode != 0:
            try:
                os.remove(out_path)
            except Exception:
                pass
            stderr = (proc.stderr or b"").decode("utf-8", "ignore").strip()
            raise BadRequest(f"Nie udało się wykonać backupu bazy (mysqldump). {stderr}")

        return out_path, f"db_backup_{stamp}.sql"

    raise BadRequest(f"Nieobsługiwany typ bazy: {driver}")


def restore_db_from_sql_file(sql_path: str) -> None:
    info = _db_url_info()
    driver = (info.get("drivername") or "").lower()

    if driver.startswith("sqlite"):
        raise BadRequest("Restore dla SQLite nie jest zaimplementowany")

    if not driver.startswith("mysql"):
        raise BadRequest(f"Nieobsługiwany typ bazy: {driver}")

    # Prefer mysql client when available. If missing, do a limited in-process restore.
    mysql = shutil.which("mysql") or shutil.which("mariadb")
    if not mysql:
        if text is None:
            raise BadRequest('Brak narzędzia "mysql"/"mariadb" oraz brak SQLAlchemy text()')

        with open(sql_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_sql = f.read()

        if "DELIMITER" in raw_sql.upper():
            raise BadRequest(
                'Backup zawiera "DELIMITER" (procedury/triggery). Do przywrócenia zainstaluj mysql-client/mariadb-client.'
            )

        # Very small, conservative SQL splitter for typical dumps.
        # Strips line comments and block comments and splits on ";\n".
        lines = raw_sql.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        cleaned = []
        in_block = False
        for line in lines:
            s = line
            if in_block:
                if "*/" in s:
                    in_block = False
                    s = s.split("*/", 1)[1]
                else:
                    continue
            if "/*" in s:
                before, after = s.split("/*", 1)
                s = before
                if "*/" not in after:
                    in_block = True
                else:
                    # remove inline block comment
                    s += after.split("*/", 1)[1]
            striped = s.strip()
            if not striped:
                continue
            if striped.startswith("--"):
                continue
            cleaned.append(s)

        sql_clean = "\n".join(cleaned)
        statements = [stmt.strip() for stmt in sql_clean.split(";\n") if stmt.strip()]
        if not statements:
            raise BadRequest("Backup jest pusty lub nieczytelny")

        with db.engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for stmt in statements:
                # Skip MySQL dump directives we don't need.
                up = stmt.upper()
                if up.startswith("SET ") or up.startswith("LOCK TABLES") or up.startswith("UNLOCK TABLES"):
                    continue
                conn.exec_driver_sql(stmt)
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        return

    _mysqldump, _mysql = _require_mysql_tools()

    database = info.get("database")
    if not database:
        raise BadRequest("Brak nazwy bazy w konfiguracji")

    host = info.get("host")
    port = info.get("port")
    username = info.get("username")
    password = info.get("password")

    cmd = [mysql, "--default-character-set=utf8mb4"]
    if host:
        cmd += ["-h", str(host)]
    if port:
        cmd += ["-P", str(port)]
    if username:
        cmd += ["-u", str(username)]
    cmd.append(str(database))

    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = str(password)

    with open(sql_path, "rb") as f:
        proc = subprocess.run(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", "ignore").strip()
        raise BadRequest(f"Nie udało się przywrócić backupu bazy (mysql). {stderr}")


def create_full_backup_zip() -> tuple[str, str]:
    """Create a ZIP containing db dump + uploads directory."""
    stamp = _now_stamp()
    base_uploads = _upload_base_dir()

    dump_path, dump_name = create_db_dump_file()

    out_fd, out_zip = tempfile.mkstemp(prefix=f"full_backup_{stamp}_", suffix=".zip")
    os.close(out_fd)

    try:
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(dump_path, arcname=os.path.join("db", dump_name))

            if os.path.isdir(base_uploads):
                for root, dirs, files in os.walk(base_uploads):
                    # Never include persisted backups inside a full backup.
                    rel_root = os.path.relpath(root, base_uploads)
                    first = rel_root.split(os.sep, 1)[0] if rel_root != os.curdir else ""
                    if first == "backups":
                        dirs[:] = []
                        continue

                    if root == base_uploads and "backups" in dirs:
                        dirs.remove("backups")

                    for fn in files:
                        abs_path = os.path.join(root, fn)
                        rel = os.path.relpath(abs_path, base_uploads)
                        z.write(abs_path, arcname=os.path.join("uploads", rel))
    finally:
        try:
            os.remove(dump_path)
        except Exception:
            pass

    return out_zip, f"full_backup_{stamp}.zip"


_FULL_BACKUP_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.zip$")


def list_full_backups() -> list[dict]:
    """List persisted full backups (DB + uploads) stored on disk."""
    folder = _full_backups_dir()
    items = []
    for name in os.listdir(folder):
        if not name.endswith(".zip"):
            continue
        if not _FULL_BACKUP_NAME_RE.match(name):
            continue
        abs_path = os.path.join(folder, name)
        if not os.path.isfile(abs_path):
            continue
        try:
            st = os.stat(abs_path)
            items.append(
                {
                    "name": name,
                    "size": int(st.st_size),
                    "mtime": int(st.st_mtime),
                    "created_at": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
                    "kind": "auto" if name.startswith("full_auto_") else "manual",
                }
            )
        except Exception:
            continue

    items.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return items


def _prune_full_backups(keep: int = 3) -> None:
    # Keep only N newest full backups stored on disk.
    keep = max(1, int(keep or 3))
    items = list_full_backups()
    to_delete = items[keep:]
    folder = _full_backups_dir()
    for b in to_delete:
        name = b.get("name")
        if not name or not _FULL_BACKUP_NAME_RE.match(name):
            continue
        abs_path = os.path.join(folder, name)
        try:
            os.remove(abs_path)
        except Exception:
            pass


def create_persisted_full_backup(kind: str = "manual") -> dict:
    """Create a full backup ZIP and store it under uploads/backups/full."""
    kind = (kind or "manual").strip().lower()
    if kind not in {"manual", "auto"}:
        kind = "manual"

    stamp = _now_stamp()
    name = f"full_{kind}_{stamp}.zip" if kind == "auto" else f"full_backup_{stamp}.zip"

    tmp_zip, _tmp_name = create_full_backup_zip()
    dst_dir = _full_backups_dir()
    dst_path = os.path.join(dst_dir, name)

    # Atomic-ish move.
    shutil.move(tmp_zip, dst_path)

    _prune_full_backups(keep=3)

    st = os.stat(dst_path)
    return {
        "name": name,
        "size": int(st.st_size),
        "mtime": int(st.st_mtime),
        "created_at": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
        "kind": kind,
    }


def get_full_backup_abs_path(name: str) -> str:
    if not name or not _FULL_BACKUP_NAME_RE.match(name):
        raise BadRequest("Nieprawidłowa nazwa pliku backupu")
    abs_path = os.path.join(_full_backups_dir(), name)
    if not os.path.isfile(abs_path):
        raise BadRequest("Nie znaleziono backupu")
    return abs_path


def restore_full_backup_from_zip(name: str) -> dict:
    """Restore DB and uploads folder from a persisted full backup ZIP."""
    zip_path = get_full_backup_abs_path(name)
    stamp = _now_stamp()

    work_dir = tempfile.mkdtemp(prefix=f"full_restore_{stamp}_")
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(work_dir)

        # Restore DB: find db/*.sql (or db/*.sqlite)
        db_dir = os.path.join(work_dir, "db")
        sql_file = None
        if os.path.isdir(db_dir):
            for fn in os.listdir(db_dir):
                if fn.endswith(".sql") or fn.endswith(".sqlite"):
                    sql_file = os.path.join(db_dir, fn)
                    break
        if not sql_file or not os.path.exists(sql_file):
            raise BadRequest("Backup nie zawiera pliku bazy (db/*.sql)")

        restore_db_from_sql_file(sql_file)

        # Restore uploads: replace uploads content (except backups) with snapshot.
        uploads_snapshot = os.path.join(work_dir, "uploads")
        base = _upload_base_dir()
        if os.path.isdir(uploads_snapshot):
            for entry in os.listdir(base):
                if entry == "backups":
                    continue
                abs_entry = os.path.join(base, entry)
                try:
                    if os.path.isdir(abs_entry):
                        shutil.rmtree(abs_entry, ignore_errors=True)
                    else:
                        os.remove(abs_entry)
                except Exception:
                    pass

            for entry in os.listdir(uploads_snapshot):
                if entry == "backups":
                    continue
                src = os.path.join(uploads_snapshot, entry)
                dst = os.path.join(base, entry)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

        return {"restored": True, "backup": name}
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


AUTO_FULL_BACKUP_LAST_DATE_KEY = "AUTO_FULL_BACKUP_LAST_DATE"


def _get_setting_value(key: str) -> str | None:
    row = Setting.query.filter_by(key=key).first()
    return row.value if row else None


def _set_setting_value(key: str, value: str | None) -> None:
    row = Setting.query.filter_by(key=key).first()
    if row is None:
        row = Setting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value


def ensure_daily_auto_full_backup() -> dict:
    """Best-effort daily auto backup with retention=3.

    Uses a cross-process file lock + DB setting to avoid duplicates.
    """
    lock = _acquire_file_lock(_auto_backup_lock_path())
    if not lock:
        return {"skipped": True, "reason": "locked"}

    try:
        today = datetime.utcnow().date().isoformat()
        last = (_get_setting_value(AUTO_FULL_BACKUP_LAST_DATE_KEY) or "").strip()
        if last == today:
            return {"skipped": True, "reason": "already_ran"}

        info = create_persisted_full_backup(kind="auto")
        _set_setting_value(AUTO_FULL_BACKUP_LAST_DATE_KEY, today)
        db.session.commit()

        return {"created": True, "backup": info}
    finally:
        try:
            lock.close()
        except Exception:
            pass


PURGE_TARGETS = {
    "jobs",
    "invoices",
    "contracts",
    "consents",
    "galleries",
    "photos",
    "payments",
    "vouchers",
    "promotions",
}


def purge_data(targets: Iterable[str], delete_files: bool) -> dict:
    """Delete selected domain data from DB. Optionally delete uploaded files."""
    requested = {str(t).strip().lower() for t in (targets or []) if str(t).strip()}
    invalid = sorted([t for t in requested if t not in PURGE_TARGETS])
    if invalid:
        raise BadRequest(f"Nieprawidłowe cele usuwania: {', '.join(invalid)}")

    # Jobs imply all dependent data; enforce safe dependency order.
    if "jobs" in requested:
        requested |= {"payments", "invoices", "contracts", "consents", "photos", "galleries"}

    # Promotions imply vouchers.
    if "promotions" in requested:
        requested |= {"vouchers"}

    from app.payments.models import Payment
    from app.invoices.models import Invoice
    from app.contracts.models import Contract
    from app.consents.models import Consent
    from app.photos.models import Photo
    from app.galleries.models import Gallery
    from app.jobs.models import JobAddon, Job
    from app.vouchers.models import Voucher
    from app.promotions.models import Promotion

    deleted = {}

    # Leaf-to-root deletions. Use bulk deletes for performance.
    if "payments" in requested:
        deleted["payments"] = db.session.query(Payment).delete(synchronize_session=False)

    # If vouchers are being purged without purging jobs, detach them from jobs first.
    if "vouchers" in requested:
        try:
            db.session.query(Job).filter(Job.voucher_id.isnot(None)).update(
                {Job.voucher_id: None, Job.discount_amount: 0},
                synchronize_session=False,
            )
        except Exception:
            # Best-effort: if update fails for some reason, continue to delete vouchers.
            pass
        deleted["vouchers"] = db.session.query(Voucher).delete(synchronize_session=False)

    if "photos" in requested:
        deleted["photos"] = db.session.query(Photo).delete(synchronize_session=False)

    if "galleries" in requested:
        deleted["galleries"] = db.session.query(Gallery).delete(synchronize_session=False)

    if "invoices" in requested:
        deleted["invoices"] = db.session.query(Invoice).delete(synchronize_session=False)

    if "contracts" in requested:
        deleted["contracts"] = db.session.query(Contract).delete(synchronize_session=False)

    if "consents" in requested:
        deleted["consents"] = db.session.query(Consent).delete(synchronize_session=False)

    if "promotions" in requested:
        deleted["promotions"] = db.session.query(Promotion).delete(synchronize_session=False)

    if "jobs" in requested:
        deleted["job_addons"] = db.session.query(JobAddon).delete(synchronize_session=False)
        deleted["jobs"] = db.session.query(Job).delete(synchronize_session=False)

    db.session.commit()

    files_deleted = {}
    if delete_files:
        base = _upload_base_dir()

        # Remove only known subfolders to avoid surprises.
        folders = []
        if "photos" in requested or "jobs" in requested:
            folders.append(os.path.join(base, "photos"))
        if "galleries" in requested or "jobs" in requested:
            folders.append(os.path.join(base, "galleries"))
        if "contracts" in requested or "jobs" in requested:
            folders.append(os.path.join(base, "contracts"))
        if "consents" in requested or "jobs" in requested:
            folders.append(os.path.join(base, "consents"))
        if "invoices" in requested or "jobs" in requested:
            folders.append(os.path.join(base, "invoices"))

        if "vouchers" in requested or "promotions" in requested:
            folders.append(os.path.join(base, "vouchers", "templates"))

        for folder in sorted(set(folders)):
            ok = _safe_rmtree(folder, base)
            files_deleted[os.path.relpath(folder, base)] = bool(ok)

    return {
        "requested": sorted(requested),
        "deleted": deleted,
        "files_deleted": files_deleted,
    }
