"""Voucher business logic.

- Generates unique, high-entropy voucher codes.
- Applies voucher to a Job (one-time use).
- Generates printable PDF (front/back) with QR codes.

PDF generation is done in CRM (WeasyPrint). Canva is used only for optional
background artwork uploaded to a Promotion.
"""

from __future__ import annotations

import base64
import os
import secrets
import tempfile
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal

import qrcode
from flask import current_app
from werkzeug.exceptions import BadRequest, NotFound

from PIL import Image, ImageDraw, ImageFont

from app.extensions import db
from app.customers.models import Customer
from app.notifications.email import send_email
from app.promotions.models import Promotion
from app.promotions import services as promotions_services
from app.settings.services import get_setting
from app.vouchers.models import Voucher


def validate_voucher_code(code_raw: str, *, job_id: int | None = None, total: str | None = None) -> dict:
    """Validate a voucher code without applying it.

    Returns a payload suitable for live UX checks.
    If job_id is provided and the voucher is already bound to that job, returns status "applied".
    If total is provided, returns discount_amount capped to that total.
    """
    code = str(code_raw or "").strip().upper()
    if not code:
        return {
            "status": "empty",
            "message": "Podaj kod vouchera",
        }

    v = Voucher.query.filter_by(code=code).first()
    if not v:
        return {
            "status": "not_found",
            "message": "Nieprawidłowy kod vouchera",
            "code": code,
        }

    promo = db.session.get(Promotion, v.promotion_id)
    promo_value = Decimal(str(getattr(promo, "value", 0) or 0)) if promo else Decimal("0")

    total_amount = None
    if total is not None and str(total).strip() != "":
        try:
            total_amount = Decimal(str(total))
        except Exception:
            total_amount = None

    discount = promo_value
    if discount < 0:
        discount = Decimal("0")
    if total_amount is not None and total_amount >= 0 and discount > total_amount:
        discount = total_amount

    # If voucher is already applied to this job, treat as OK.
    if job_id is not None:
        try:
            if v.job is not None and int(getattr(v.job, "id", 0) or 0) == int(job_id):
                return {
                    "status": "applied",
                    "message": "Voucher jest już przypisany do tego zlecenia",
                    "code": v.code,
                    "promotion_id": v.promotion_id,
                    "promotion_type": getattr(promo, "promo_type", None) if promo else None,
                    "promotion_value": str(promo_value),
                    "discount_amount": str(discount),
                    "issued_at": v.issued_at.isoformat() if v.issued_at else None,
                    "expires_at": v.expires_at.isoformat() if v.expires_at else None,
                    "used_at": v.used_at.isoformat() if v.used_at else None,
                }
        except Exception:
            pass

    if v.used_at is not None or v.job is not None:
        return {
            "status": "used",
            "message": "Voucher został już wykorzystany",
            "code": v.code,
            "promotion_id": v.promotion_id,
            "promotion_type": getattr(promo, "promo_type", None) if promo else None,
            "promotion_value": str(promo_value),
            "discount_amount": "0",
            "issued_at": v.issued_at.isoformat() if v.issued_at else None,
            "expires_at": v.expires_at.isoformat() if v.expires_at else None,
            "used_at": v.used_at.isoformat() if v.used_at else None,
        }

    if datetime.utcnow() > v.expires_at:
        return {
            "status": "expired",
            "message": "Voucher jest nieważny (po terminie)",
            "code": v.code,
            "promotion_id": v.promotion_id,
            "promotion_type": getattr(promo, "promo_type", None) if promo else None,
            "promotion_value": str(promo_value),
            "discount_amount": "0",
            "issued_at": v.issued_at.isoformat() if v.issued_at else None,
            "expires_at": v.expires_at.isoformat() if v.expires_at else None,
            "used_at": v.used_at.isoformat() if v.used_at else None,
        }

    if promo is None:
        return {
            "status": "invalid",
            "message": "Voucher nie ma poprawnej promocji",
            "code": v.code,
            "promotion_id": v.promotion_id,
            "promotion_type": None,
            "promotion_value": "0",
            "discount_amount": "0",
            "issued_at": v.issued_at.isoformat() if v.issued_at else None,
            "expires_at": v.expires_at.isoformat() if v.expires_at else None,
            "used_at": v.used_at.isoformat() if v.used_at else None,
        }

    if promo_value <= 0:
        return {
            "status": "invalid",
            "message": "Voucher ma nieprawidłową wartość",
            "code": v.code,
            "promotion_id": v.promotion_id,
            "promotion_type": getattr(promo, "promo_type", None),
            "promotion_value": str(promo_value),
            "discount_amount": "0",
            "issued_at": v.issued_at.isoformat() if v.issued_at else None,
            "expires_at": v.expires_at.isoformat() if v.expires_at else None,
            "used_at": v.used_at.isoformat() if v.used_at else None,
        }

    return {
        "status": "valid",
        "message": "Voucher ważny",
        "code": v.code,
        "promotion_id": v.promotion_id,
        "promotion_type": getattr(promo, "promo_type", None),
        "promotion_value": str(promo_value),
        "discount_amount": str(discount),
        "issued_at": v.issued_at.isoformat() if v.issued_at else None,
        "expires_at": v.expires_at.isoformat() if v.expires_at else None,
        "used_at": v.used_at.isoformat() if v.used_at else None,
    }


def _now() -> datetime:
    return datetime.utcnow()


def _upload_base_dir() -> str:
    base = current_app.config.get("UPLOAD_FOLDER") or "uploads"
    return os.path.abspath(base)


def _promo_bg_abs_path(promo: Promotion, which: str) -> str | None:
    rel = getattr(promo, f"voucher_bg_{which}_path", None)
    if not rel:
        return None

    base = _upload_base_dir()
    abs_path = rel
    if not os.path.isabs(str(rel)):
        abs_path = os.path.abspath(os.path.join(base, str(rel)))

    if not abs_path.startswith(base + os.sep) and abs_path != base:
        return None

    if not os.path.exists(abs_path):
        return None

    return abs_path


def _generate_code(length: int = 40) -> str:
    """Generate a high-entropy, QR-friendly code.

    Uses URL-safe base64 and strips non-alphanumerics. Returns uppercase.
    """
    # token_urlsafe(32) ~ 43 chars; we strip '-' '_' so length varies.
    while True:
        raw = secrets.token_urlsafe(48)
        cleaned = "".join(ch for ch in raw if ch.isalnum()).upper()
        if len(cleaned) >= length:
            return cleaned[:length]


def _create_voucher_row(promo: Promotion) -> Voucher:
    issued = _now()
    expires = issued + timedelta(days=int(promo.duration_days or 0))
    if expires <= issued:
        raise BadRequest("Nieprawidłowa długość promocji")

    # Ensure uniqueness without rolling back the whole session.
    for _ in range(50):
        code = _generate_code(40)
        exists = Voucher.query.filter_by(code=code).first() is not None
        if exists:
            continue

        v = Voucher(
            promotion_id=promo.id,
            code=code,
            issued_at=issued,
            expires_at=expires,
            used_at=None,
        )
        db.session.add(v)
        try:
            db.session.flush()
            return v
        except Exception:
            # In the extremely unlikely case of a race/collision, retry.
            db.session.expunge(v)
            continue

    raise BadRequest("Nie udało się wygenerować unikalnego kodu vouchera")


def generate_vouchers(promotion_id: int, count: int) -> list[Voucher]:
    promo = db.session.get(Promotion, int(promotion_id))
    if not promo:
        raise NotFound("Nie znaleziono promocji")

    try:
        count = int(count)
    except Exception:
        raise BadRequest("Nieprawidłowa liczba voucherów")

    if count <= 0 or count > 200:
        raise BadRequest("Nieprawidłowa liczba voucherów")

    vouchers: list[Voucher] = []
    for _ in range(count):
        vouchers.append(_create_voucher_row(promo))

    # Activation is used only for promotion UX/status, not for voucher validity.
    if not promo.activated_at:
        try:
            promotions_services.activate_promotion(promo.id)
        except Exception:
            # Ignore: activation may be blocked if another promotion of the same type is active.
            pass

    db.session.commit()
    return vouchers


def _qr_png_data_url(payload: str, *, transparent: bool = False) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    if transparent:
        # Convert white background to transparent.
        try:
            img = img.convert("RGBA")
            pixels = img.getdata()
            new_pixels = []
            for r, g, b, a in pixels:
                if r >= 250 and g >= 250 and b >= 250:
                    new_pixels.append((255, 255, 255, 0))
                else:
                    new_pixels.append((r, g, b, 255))
            img.putdata(new_pixels)
        except Exception:
            # Best-effort: if conversion fails, fall back to opaque QR.
            pass

    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _qr_pil_image(payload: str, *, transparent: bool = True) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img = img.convert("RGBA")

    if transparent:
        try:
            pixels = img.getdata()
            new_pixels = []
            for r, g, b, a in pixels:
                if r >= 250 and g >= 250 and b >= 250:
                    new_pixels.append((255, 255, 255, 0))
                else:
                    new_pixels.append((r, g, b, 255))
            img.putdata(new_pixels)
        except Exception:
            pass

    return img


def build_voucher_png_zip(promo: Promotion, voucher: Voucher) -> tuple[str, str]:
    """Return (zip_path, download_name) with PNG renders for a single voucher.

    Includes front.png always and back.png if a back template exists.
    Positions are interpreted in CSS px (same as PDF overlay).
    """

    # A4 at 96 CSS px per inch.
    a4_w = int(round(210 / 25.4 * 96))  # ~794
    a4_h = int(round(297 / 25.4 * 96))  # ~1123

    def _num(v, default: float) -> float:
        try:
            if v is None:
                return default
            return float(Decimal(str(v)))
        except Exception:
            return default

    text_x = _num(getattr(promo, "voucher_text_x_px", None), 75.59)
    text_y = _num(getattr(promo, "voucher_text_y_px", None), 75.59)
    qr_x = _num(getattr(promo, "voucher_qr_x_px", None), 604.72)
    qr_y = _num(getattr(promo, "voucher_qr_y_px", None), 75.59)

    font_family = (getattr(promo, "voucher_text_font_family", None) or "").strip()
    font_size_pt = _num(getattr(promo, "voucher_text_font_size_pt", None), 12.0)
    font_size_px = max(6, int(round(font_size_pt * 96.0 / 72.0)))

    # Best-effort font selection.
    font = None
    try:
        if font_family:
            font = ImageFont.truetype(font_family, font_size_px)
    except Exception:
        font = None

    if font is None:
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        ):
            try:
                if os.path.exists(path):
                    font = ImageFont.truetype(path, font_size_px)
                    break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    exp = voucher.expires_at.strftime("%d.%m.%Y")
    text = f"Bon ważny do {exp}"

    qr_img = _qr_pil_image(voucher.code, transparent=True)
    qr_size_px = int(round(36 / 25.4 * 96))  # 36mm to match PDF size
    try:
        qr_img = qr_img.resize((qr_size_px, qr_size_px), resample=Image.NEAREST)
    except Exception:
        qr_img = qr_img.resize((qr_size_px, qr_size_px))

    def _render_side(which: str) -> Image.Image:
        canvas = Image.new("RGBA", (a4_w, a4_h), (255, 255, 255, 255))

        bg_path = _promo_bg_abs_path(promo, which)
        if bg_path:
            try:
                bg = Image.open(bg_path).convert("RGBA")
                bw, bh = bg.size
                if bw > 0 and bh > 0:
                    scale = min(a4_w / bw, a4_h / bh)
                    nw = max(1, int(round(bw * scale)))
                    nh = max(1, int(round(bh * scale)))
                    bg_resized = bg.resize((nw, nh), resample=Image.LANCZOS)
                    ox = int((a4_w - nw) / 2)
                    oy = int((a4_h - nh) / 2)
                    canvas.alpha_composite(bg_resized, dest=(ox, oy))
            except Exception:
                pass

        # Only front side has text + QR.
        if which == "front":
            draw = ImageDraw.Draw(canvas)
            try:
                draw.text((int(round(text_x)), int(round(text_y))), text, fill=(0, 0, 0, 255), font=font)
            except Exception:
                # Fallback without custom font
                draw.text((int(round(text_x)), int(round(text_y))), text, fill=(0, 0, 0, 255))

            try:
                canvas.alpha_composite(qr_img, dest=(int(round(qr_x)), int(round(qr_y))))
            except Exception:
                pass

        return canvas.convert("RGB")

    front_png = _render_side("front")
    back_bg = _promo_bg_abs_path(promo, "back")
    back_png = _render_side("back") if back_bg else None

    zip_fd, zip_path = tempfile.mkstemp(prefix="voucher_", suffix=".zip")
    os.close(zip_fd)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        with tempfile.NamedTemporaryFile(prefix="voucher_front_", suffix=".png", delete=False) as tmp:
            front_tmp = tmp.name
        front_png.save(front_tmp, format="PNG")
        zf.write(front_tmp, arcname="front.png")
        try:
            os.remove(front_tmp)
        except Exception:
            pass

        if back_png is not None:
            with tempfile.NamedTemporaryFile(prefix="voucher_back_", suffix=".png", delete=False) as tmp:
                back_tmp = tmp.name
            back_png.save(back_tmp, format="PNG")
            zf.write(back_tmp, arcname="back.png")
            try:
                os.remove(back_tmp)
            except Exception:
                pass

    safe_code = (voucher.code or "voucher").strip().replace(" ", "_")
    download_name = f"voucher_{safe_code}.zip"
    return zip_path, download_name


def render_voucher_front_png_bytes(promo: Promotion, voucher: Voucher) -> bytes:
    """Render only the front side PNG and return raw bytes.

    Used for emailing vouchers (embed as inline image).
    """
    # A4 at 96 CSS px per inch.
    a4_w = int(round(210 / 25.4 * 96))  # ~794
    a4_h = int(round(297 / 25.4 * 96))  # ~1123

    def _num(v, default: float) -> float:
        try:
            if v is None:
                return default
            return float(Decimal(str(v)))
        except Exception:
            return default

    text_x = _num(getattr(promo, "voucher_text_x_px", None), 75.59)
    text_y = _num(getattr(promo, "voucher_text_y_px", None), 75.59)
    qr_x = _num(getattr(promo, "voucher_qr_x_px", None), 604.72)
    qr_y = _num(getattr(promo, "voucher_qr_y_px", None), 75.59)

    font_family = (getattr(promo, "voucher_text_font_family", None) or "").strip()
    font_size_pt = _num(getattr(promo, "voucher_text_font_size_pt", None), 12.0)
    font_size_px = max(6, int(round(font_size_pt * 96.0 / 72.0)))

    font = None
    try:
        if font_family:
            font = ImageFont.truetype(font_family, font_size_px)
    except Exception:
        font = None

    if font is None:
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        ):
            try:
                if os.path.exists(path):
                    font = ImageFont.truetype(path, font_size_px)
                    break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    exp = voucher.expires_at.strftime("%d.%m.%Y")
    text = f"Bon ważny do {exp}"

    qr_img = _qr_pil_image(voucher.code, transparent=True)
    qr_size_px = int(round(36 / 25.4 * 96))
    try:
        qr_img = qr_img.resize((qr_size_px, qr_size_px), resample=Image.NEAREST)
    except Exception:
        qr_img = qr_img.resize((qr_size_px, qr_size_px))

    canvas = Image.new("RGBA", (a4_w, a4_h), (255, 255, 255, 255))
    bg_path = _promo_bg_abs_path(promo, "front")
    if bg_path:
        try:
            bg = Image.open(bg_path).convert("RGBA")
            bw, bh = bg.size
            if bw > 0 and bh > 0:
                scale = min(a4_w / bw, a4_h / bh)
                nw = max(1, int(round(bw * scale)))
                nh = max(1, int(round(bh * scale)))
                bg_resized = bg.resize((nw, nh), resample=Image.LANCZOS)
                ox = int((a4_w - nw) / 2)
                oy = int((a4_h - nh) / 2)
                canvas.alpha_composite(bg_resized, dest=(ox, oy))
        except Exception:
            pass

    draw = ImageDraw.Draw(canvas)
    try:
        draw.text((int(round(text_x)), int(round(text_y))), text, fill=(0, 0, 0, 255), font=font)
    except Exception:
        draw.text((int(round(text_x)), int(round(text_y))), text, fill=(0, 0, 0, 255))

    try:
        canvas.alpha_composite(qr_img, dest=(int(round(qr_x)), int(round(qr_y))))
    except Exception:
        pass

    out = canvas.convert("RGB")
    from io import BytesIO

    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _sql_random_func():
    """Return a SQL random() function compatible with the current DB."""
    from sqlalchemy import func

    try:
        bind = db.session.get_bind()
        name = getattr(getattr(bind, "dialect", None), "name", "") or ""
    except Exception:
        name = ""

    if name in {"sqlite", "postgresql"}:
        return func.random()
    return func.rand()


def send_voucher_lottery(*, promotion_id: int | None, count: int) -> dict:
    """Randomly pick N customers and email them voucher front PNG.

    Uses vouchers that are: not used, not expired, not already sent/reserved.
    Marks vouchers as reserved first (to prevent concurrent sends), then as sent on success.
    """
    try:
        count = int(count)
    except Exception:
        raise BadRequest("Nieprawidłowa liczba")

    if count <= 0 or count > 200:
        raise BadRequest("Nieprawidłowa liczba (1-200)")

    cfg = current_app.config
    if not cfg.get("SMTP_HOST") or not cfg.get("SMTP_FROM"):
        raise BadRequest("Brak konfiguracji SMTP (SMTP_HOST/SMTP_FROM)")

    now = _now()
    rnd = _sql_random_func()

    customers_q = (
        Customer.query.filter(Customer.is_active.is_(True))
        .filter(Customer.email.isnot(None))
        .filter(Customer.email != "")
        .order_by(rnd)
    )
    customers = customers_q.limit(count).all()
    if len(customers) < count:
        raise BadRequest("Brak wystarczającej liczby aktywnych klientów z e-mailem")

    vouchers_q = (
        Voucher.query.filter(Voucher.used_at.is_(None))
        .filter(Voucher.expires_at >= now)
        .filter(Voucher.job == None)  # noqa: E711
        .filter(Voucher.lottery_reserved_at.is_(None))
        .filter(Voucher.lottery_sent_at.is_(None))
        .order_by(rnd)
    )
    if promotion_id:
        vouchers_q = vouchers_q.filter(Voucher.promotion_id == int(promotion_id))

    vouchers = vouchers_q.limit(count).all()
    if len(vouchers) < count:
        raise BadRequest("Brak wystarczającej liczby dostępnych voucherów (niewysłanych/niewykorzystanych/ważnych)")

    pairs = list(zip(customers, vouchers))

    # Reserve first to avoid concurrent sends reusing the same vouchers.
    for customer, voucher in pairs:
        voucher.lottery_reserved_at = now
        voucher.lottery_customer_id = customer.id
        voucher.lottery_sent_email = customer.email
    db.session.commit()

    company_name = str(get_setting("COMPANY_NAME", "") or "").strip()
    if not company_name:
        company_name = str(cfg.get("BRAND_NAME", "") or "").strip()

    sent = 0
    failed = 0

    from email.utils import make_msgid

    for customer, voucher in pairs:
        promo = voucher.promotion or db.session.get(Promotion, voucher.promotion_id)
        if not promo:
            # Make the voucher eligible again.
            voucher.lottery_reserved_at = None
            voucher.lottery_customer_id = None
            voucher.lottery_sent_email = None
            failed += 1
            continue

        img_bytes = render_voucher_front_png_bytes(promo, voucher)
        cid = make_msgid()
        cid_ref = cid[1:-1]

        promo_value = str(getattr(promo, "value", "") or "")
        exp = voucher.expires_at.strftime("%d.%m.%Y")

        subject = f"Voucher {promo_value} PLN - {company_name}".strip(" -")

        body_text = (
            f"Dzień dobry,\n\n"
            f"Przesyłamy voucher o wartości {promo_value} PLN.\n"
            f"Kod: {voucher.code}\n"
            f"Ważny do: {exp}\n"
        )

        body_html = f"""
        <div style='font-family: Arial, sans-serif; font-size: 14px; line-height: 1.4;'>
          <p>Dzień dobry,</p>
          <p>Przesyłamy voucher o wartości <strong>{promo_value} PLN</strong>.</p>
          <p><strong>Kod:</strong> {voucher.code}<br/>
             <strong>Ważny do:</strong> {exp}</p>
          <p><img alt='Voucher' src='cid:{cid_ref}' style='max-width: 100%; height: auto; border: 1px solid #eee;'/></p>
        </div>
        """

        ok = send_email(
            to_email=customer.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            inline_images=[{"content": img_bytes, "maintype": "image", "subtype": "png", "cid": cid}],
        )

        if ok:
            voucher.lottery_sent_at = _now()
            sent += 1
        else:
            # Make it eligible again.
            voucher.lottery_reserved_at = None
            voucher.lottery_customer_id = None
            voucher.lottery_sent_email = None
            failed += 1

    db.session.commit()

    return {
        "requested": count,
        "sent": sent,
        "failed": failed,
    }


def _money(value) -> str:
    return f"{Decimal(str(value or 0)).quantize(Decimal('0.01'))} zł"


def build_vouchers_pdf(promo: Promotion, vouchers: list[Voucher]) -> tuple[str, str]:
    """Return (pdf_path, download_name)."""
    from weasyprint import HTML

    front_bg = _promo_bg_abs_path(promo, "front")
    back_bg = _promo_bg_abs_path(promo, "back")

    # Layout defaults (CSS px from top-left of the page).
    def _num(v, default: float) -> float:
        try:
            if v is None:
                return default
            return float(Decimal(str(v)))
        except Exception:
            return default

    # Defaults preserve previous mm defaults (~20mm and ~160mm).
    text_x = _num(getattr(promo, "voucher_text_x_px", None), 75.59)
    text_y = _num(getattr(promo, "voucher_text_y_px", None), 75.59)
    qr_x = _num(getattr(promo, "voucher_qr_x_px", None), 604.72)
    qr_y = _num(getattr(promo, "voucher_qr_y_px", None), 75.59)

    font_family = (getattr(promo, "voucher_text_font_family", None) or "sans-serif").strip() or "sans-serif"
    font_size_pt = _num(getattr(promo, "voucher_text_font_size_pt", None), 12.0)

    def render_page(v: Voucher, side: str) -> str:
        bg = front_bg if side == "front" else back_bg
        bg_img = f"<img class='bg' src='file://{bg}'/>" if bg else ""

        # Only front side has text + QR.
        if side != "front":
            return f"<section class='page page-break'>{bg_img}</section>"

        exp = v.expires_at.strftime("%d.%m.%Y")
        qr = _qr_png_data_url(v.code, transparent=True)

        return f"""
        <section class='page page-break'>
          {bg_img}
              <div class='overlay-text' style='left:{text_x}px; top:{text_y}px; font-family:{font_family}; font-size:{font_size_pt}pt;'>
            Bon ważny do {exp}
          </div>
              <img class='overlay-qr' src='{qr}' style='left:{qr_x}px; top:{qr_y}px;'/>
        </section>
        """

    sections: list[str] = []
    for v in vouchers:
        sections.append(render_page(v, "front"))
        if back_bg:
            sections.append(render_page(v, "back"))

    html = f"""
    <html>
    <head>
      <meta charset='utf-8'/>
            <style>
                @page {{ size: A4; margin: 0; }}
                html, body {{ margin: 0; padding: 0; }}
                body {{ background: #fff; }}
                .page {{ position: relative; width: 210mm; height: 297mm; overflow: hidden; }}
                .page-break {{ page-break-after: always; }}

                /* Canva export should ideally match A4 aspect. We keep the whole PNG visible. */
                .bg {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }}

                .overlay-text {{ position: absolute; color: #000; }}
                .overlay-qr {{ position: absolute; width: 36mm; height: 36mm; }}
            </style>
    </head>
    <body>
      {"".join(sections)}
    </body>
    </html>
    """

    out_fd, out_path = tempfile.mkstemp(prefix="vouchers_", suffix=".pdf")
    os.close(out_fd)

    HTML(string=html, base_url=_upload_base_dir()).write_pdf(out_path)

    safe_type = (promo.promo_type or "voucher").strip().replace(" ", "_")
    name = f"vouchery_{safe_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return out_path, name


def apply_voucher_to_job(job, code_raw: str):
    """Validate and apply a voucher code to a job (one-time use)."""
    if not code_raw:
        return

    code = str(code_raw).strip().upper()
    if not code:
        return

    if getattr(job, "voucher_id", None):
        raise BadRequest("Do zlecenia jest już przypisany voucher")

    v = Voucher.query.filter_by(code=code).first()
    if not v:
        raise BadRequest("Nieprawidłowy kod vouchera")

    if v.used_at is not None or v.job is not None:
        raise BadRequest("Voucher został już wykorzystany")

    if datetime.utcnow() > v.expires_at:
        raise BadRequest("Voucher jest nieważny (po terminie)")

    promo = db.session.get(Promotion, v.promotion_id)
    if not promo:
        raise BadRequest("Voucher nie ma poprawnej promocji")

    # Recompute current job price (base + addons), then apply discount.
    try:
        job.update_final_price()
    except Exception:
        pass

    base_total = Decimal(str(getattr(job, "final_price", 0) or 0))
    discount = Decimal(str(promo.value or 0))
    if discount <= 0:
        raise BadRequest("Voucher ma nieprawidłową wartość")

    # Cap discount to job total.
    if discount > base_total:
        discount = base_total

    job.discount_amount = discount
    job.voucher_id = v.id

    v.used_at = _now()

    db.session.flush()

    return {
        "voucher": v,
        "discount_amount": str(discount),
    }
