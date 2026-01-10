"""Consents business logic.

Handles consent management with grant/revoke and scan/PDF support.
"""

from __future__ import annotations

import html
import os
from datetime import datetime

from flask import current_app
from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.utils import secure_filename

from app.consents.models import Consent
from app.extensions import db
from app.jobs.services import get_job_by_id
from app.settings.services import get_setting


def get_default_image_publication_consent_text_person(company_name: str = "") -> str:
    """Default Polish consent text (person): adult/minor with guardians section."""
    company = (company_name or "").strip() or "Wykonawca"
    return (
        "na podstawie art. 81 ustawy o prawie autorskim i prawach pokrewnych\n"
        "oraz art. 6 ust. 1 lit. a RODO\n\n"
        "1. Dane osoby, której wizerunek dotyczy\n\n"
        "Imię i nazwisko: ____________________________________________\n"
        "Data urodzenia: ____________________________________________\n\n"
        "(jeżeli osoba jest pełnoletnia – wypełnia sama; jeżeli nie – wypełniają opiekunowie)\n\n"
        "2. Dane przedstawicieli ustawowych (w przypadku osoby małoletniej)\n"
        "Rodzic / Opiekun prawny 1\n\n"
        "Imię i nazwisko: ____________________________________________\n"
        "PESEL / dokument tożsamości: ______________________________\n"
        "Podpis: _________________________________________________\n\n"
        "Rodzic / Opiekun prawny 2\n\n"
        "Imię i nazwisko: ____________________________________________\n"
        "PESEL / dokument tożsamości: ______________________________\n"
        "Podpis: _________________________________________________\n\n"
        "(jeżeli dziecko ma jednego opiekuna – drugi wpis nieobowiązkowy)\n\n"
        "3. Treść zgody\n\n"
        "Ja, niżej podpisany/a, działając w imieniu własnym / jako przedstawiciel ustawowy osoby małoletniej wskazanej powyżej, "
        "wyrażam dobrowolną i świadomą zgodę na:\n\n"
        "nieodpłatne utrwalanie, przetwarzanie i rozpowszechnianie wizerunku utrwalonego podczas realizacji usługi fotograficznej przez:\n\n"
        f"{company}\n\n"
        "w szczególności w postaci fotografii i materiałów wideo.\n\n"
        "Zgoda obejmuje publikację wizerunku w celach:\n\n"
        "promocyjnych,\n"
        "marketingowych,\n"
        "informacyjnych,\n"
        "portfolio wykonawcy,\n\n"
        "w tym w szczególności na:\n\n"
        "stronie internetowej,\n"
        "profilach w mediach społecznościowych (np. Facebook, Instagram),\n"
        "materiałach drukowanych i elektronicznych (portfolio, ulotki, reklamy),\n"
        "prezentacjach, wystawach, konkursach i publikacjach związanych z działalnością fotograficzną.\n\n"
        "4. Zakres i czas obowiązywania zgody\n\n"
        "Zgoda udzielona jest bez ograniczeń terytorialnych i czasowych.\n\n"
        "Wizerunek może być wykorzystywany w różnych formach publikacji i zestawieniach graficznych, pod warunkiem że nie narusza dóbr osobistych, "
        "godności ani dobrego imienia osoby przedstawionej.\n\n"
        "5. Cofnięcie zgody\n\n"
        "Zostałem/am poinformowany/a, że mam prawo w każdej chwili cofnąć niniejszą zgodę, wysyłając oświadczenie na adres wykonawcy.\n\n"
        "Cofnięcie zgody:\n\n"
        "nie wpływa na legalność publikacji dokonanych przed jej cofnięciem,\n"
        "powoduje zaprzestanie dalszego wykorzystywania wizerunku w przyszłości.\n\n"
        "6. Informacja RODO\n\n"
        "Administratorem danych osobowych (w tym wizerunku) jest:\n"
        f"{company}\n\n"
        "Dane przetwarzane są wyłącznie w celu realizacji niniejszej zgody i zgodnie z przepisami RODO.\n"
        "Osoba, której dane dotyczą (lub jej opiekun prawny), ma prawo do:\n\n"
        "dostępu do danych,\n"
        "ich poprawiania,\n"
        "ograniczenia przetwarzania,\n"
        "wniesienia sprzeciwu,\n"
        "cofnięcia zgody.\n\n"
        "7. Podpis\n\n"
        "Miejscowość i data: ______________________________________\n\n"
        "Podpis osoby pełnoletniej / rodzica / opiekuna prawnego: ______________________________________\n"
    )


def get_default_image_publication_consent_text_company(company_name: str = "") -> str:
    """Default Polish consent text (company): employee/contractor consent for corporate session/event."""
    company = (company_name or "").strip() or "Wykonawca"
    return (
        "na podstawie art. 81 ustawy o prawie autorskim i prawach pokrewnych\n"
        "oraz art. 6 ust. 1 lit. a RODO\n\n"
        "1. Dane osoby, której wizerunek dotyczy\n\n"
        "Imię i nazwisko: ____________________________________________\n"
        "Stanowisko: ______________________________________________\n"
        "Nazwa firmy: _____________________________________________\n\n"
        "2. Treść zgody – pracownik / współpracownik\n\n"
        "Ja, niżej podpisany/a, wyrażam dobrowolną i świadomą zgodę na:\n\n"
        "nieodpłatne utrwalanie, przetwarzanie oraz rozpowszechnianie mojego wizerunku utrwalonego w trakcie sesji fotograficznej / wydarzenia firmowego "
        f"zrealizowanego przez:\n\n{company}\n\n"
        "w związku z działalnością firmy, którą reprezentuję.\n\n"
        "Zgoda obejmuje wykorzystanie mojego wizerunku w szczególności w:\n\n"
        "materiałach marketingowych i promocyjnych,\n"
        "stronie internetowej wykonawcy i firmy,\n"
        "mediach społecznościowych,\n"
        "prezentacjach, raportach, ofertach handlowych,\n"
        "materiałach drukowanych i cyfrowych.\n\n"
        "3. Zakres zgody\n\n"
        "Zgoda obejmuje:\n\n"
        "publikację wizerunku samodzielnie lub w grupie,\n"
        "kadrowanie, montaż, korekcję barwną oraz inne standardowe opracowania fotograficzne,\n"
        "łączenie wizerunku z innymi materiałami graficznymi lub tekstami.\n\n"
        "Zgoda udzielona jest bez ograniczeń czasowych i terytorialnych.\n\n"
        "4. Cofnięcie zgody\n\n"
        "Mam świadomość, że zgodę mogę w każdej chwili cofnąć, składając oświadczenie wykonawcy.\n\n"
        "Cofnięcie zgody:\n\n"
        "nie wpływa na zgodność z prawem publikacji dokonanych przed jej cofnięciem,\n"
        "skutkuje zaprzestaniem dalszego wykorzystywania wizerunku w przyszłości.\n\n"
        "5. Informacja RODO\n\n"
        "Administratorem danych osobowych (w tym wizerunku) jest:\n"
        f"{company}\n\n"
        "Dane przetwarzane są wyłącznie w celu realizacji niniejszej zgody oraz prowadzenia działalności marketingowej i portfolio wykonawcy.\n\n"
        "Przysługuje mi prawo do:\n\n"
        "dostępu do danych,\n"
        "ich poprawiania,\n"
        "ograniczenia przetwarzania,\n"
        "cofnięcia zgody w dowolnym momencie.\n\n"
        "6. Podpis\n\n"
        "Miejscowość i data: ______________________________________\n\n"
        "Podpis osoby wyrażającej zgodę: ______________________________________\n"
    )


def get_default_image_publication_consent_text(
    company_name: str = "",
    customer_type: str | None = None,
) -> str:
    """Image publication consent template chosen by customer type."""
    if (customer_type or "").strip().lower() == "company":
        return get_default_image_publication_consent_text_company(company_name)
    return get_default_image_publication_consent_text_person(company_name)


def get_image_publication_pdf_title(customer_type: str | None) -> str:
    if (customer_type or "").strip().lower() == "company":
        return "ZGODA NA UTRWALANIE I ROZPOWSZECHNIANIE WIZERUNKU (SESJA / EVENT FIRMOWY)"
    return "ZGODA NA UTRWALANIE I ROZPOWSZECHNIANIE WIZERUNKU (OSOBY DOROSŁEJ / MAŁOLETNIEGO)"


def get_default_data_processing_consent_text(
    company_name: str = "",
    company_address: str = "",
    company_nip: str = "",
    company_email: str = "",
) -> str:
    """Default Polish consent text for personal data processing (RODO)."""
    name = (company_name or "").strip() or "[Nazwa firmy / Imię i nazwisko fotografa]"
    address = (company_address or "").strip() or "[Adres siedziby]"
    nip = (company_nip or "").strip() or "[NIP]"
    email = (company_email or "").strip() or "[E-mail]"

    return (
        "ZGODA NA PRZETWARZANIE DANYCH OSOBOWYCH (RODO)\n\n"
        "Ja, niżej podpisany/a, wyrażam zgodę na przetwarzanie moich danych osobowych przez:\n\n"
        "Administrator danych:\n"
        f"{name}\n"
        f"{address}\n"
        f"{nip}\n"
        f"{email}\n\n"
        "w celu realizacji usług fotograficznych, w szczególności:\n\n"
        "- obsługi zapytań i rezerwacji sesji zdjęciowych,\n"
        "- realizacji umowy (wykonania sesji, obróbki zdjęć, przekazania materiałów),\n"
        "- wystawienia faktury lub rachunku,\n"
        "- prowadzenia komunikacji związanej ze zleceniem,\n"
        "- przechowywania archiwum zleceń oraz galerii zdjęć.\n\n"
        "Zakres przetwarzanych danych\n\n"
        "Moje dane mogą obejmować w szczególności:\n\n"
        "- imię i nazwisko / nazwę firmy,\n"
        "- adres e-mail, numer telefonu, adres,\n"
        "- dane do faktury (w tym NIP – w przypadku firmy),\n"
        "- wizerunek utrwalony na zdjęciach,\n"
        "- inne dane przekazane w związku z realizacją usługi.\n\n"
        "Podstawa prawna\n\n"
        "Dane są przetwarzane zgodnie z:\n\n"
        "- art. 6 ust. 1 lit. b RODO – wykonanie umowy,\n"
        "- art. 6 ust. 1 lit. c RODO – obowiązki księgowe i podatkowe,\n"
        "- art. 6 ust. 1 lit. a RODO – zgoda osoby, której dane dotyczą.\n\n"
        "Odbiorcy danych\n\n"
        "Moje dane mogą być przekazywane podmiotom współpracującym z administratorem wyłącznie w zakresie niezbędnym do realizacji usługi, w szczególności:\n\n"
        "- firmom księgowym,\n"
        "- dostawcom hostingu i systemów CRM,\n"
        "- dostawcom galerii online i przechowywania danych.\n\n"
        "Okres przechowywania\n\n"
        "Dane osobowe będą przechowywane:\n\n"
        "- przez czas trwania umowy,\n"
        "- po jej zakończeniu przez okres wymagany przepisami prawa (np. podatkowymi),\n"
        "- oraz do czasu cofnięcia zgody w zakresie danych przetwarzanych na jej podstawie.\n\n"
        "Prawa osoby, której dane dotyczą\n\n"
        "Przysługuje mi prawo do:\n\n"
        "- dostępu do moich danych,\n"
        "- ich sprostowania,\n"
        "- usunięcia,\n"
        "- ograniczenia przetwarzania,\n"
        "- przenoszenia danych,\n"
        "- wniesienia sprzeciwu wobec przetwarzania,\n"
        "- cofnięcia zgody w dowolnym momencie,\n"
        "- wniesienia skargi do Prezesa Urzędu Ochrony Danych Osobowych.\n\n"
        "Oświadczenie\n\n"
        "Oświadczam, że:\n\n"
        "- zostałem/-am poinformowany/-a o celu i zakresie przetwarzania danych,\n"
        "- wiem, że podanie danych jest dobrowolne, ale niezbędne do realizacji usługi,\n"
        "- wiem, że mogę w każdej chwili cofnąć zgodę.\n\n"
        "Data: _______________________\n\n"
        "Imię i nazwisko: _______________________\n\n"
        "Podpis: _______________________\n"
    )


def create_consent(data: dict) -> Consent:
    """Tworzy nową zgodę dla zlecenia."""
    job = get_job_by_id(data["job_id"])
    consent_type = data["consent_type"]

    existing = Consent.query.filter_by(job_id=job.id, consent_type=consent_type).first()
    if existing:
        raise BadRequest(
            f"Zgoda typu {consent_type} już istnieje dla zlecenia #{data['job_id']}"
        )

    consent_text = (data.get("consent_text") or "").strip()
    if not consent_text:
        company_name = get_setting("COMPANY_NAME", "")
        if consent_type == "image_publication":
            customer = getattr(job, "customer", None)
            consent_text = get_default_image_publication_consent_text(
                company_name,
                customer_type=getattr(customer, "customer_type", None),
            )
        elif consent_type == "data_processing":
            consent_text = get_default_data_processing_consent_text(
                company_name=company_name,
                company_address=get_setting("COMPANY_ADDRESS", ""),
                company_nip=get_setting("COMPANY_NIP", ""),
                company_email=get_setting("COMPANY_EMAIL", ""),
            )
        else:
            raise BadRequest("Brak treści zgody")

    consent = Consent(
        job_id=job.id,
        consent_type=consent_type,
        consent_text=consent_text,
        scope=data.get("scope"),
        notes=data.get("notes"),
        is_granted=False,
        is_revoked=False,
    )

    db.session.add(consent)
    db.session.commit()
    return consent


def get_consent_by_id(consent_id: int) -> Consent:
    consent = db.session.get(Consent, consent_id)
    if not consent:
        raise NotFound(f"Zgoda #{consent_id} nie istnieje")
    return consent


def get_consents_by_job_id(job_id: int):
    return Consent.query.filter_by(job_id=job_id).all()


def get_all_consents(filters: dict | None = None, page: int = 1, per_page: int = 50) -> dict:
    filters = filters or {}

    query = Consent.query

    if filters.get("job_id"):
        query = query.filter(Consent.job_id == int(filters["job_id"]))

    if filters.get("consent_type"):
        query = query.filter(Consent.consent_type == filters["consent_type"])

    status = (filters.get("status") or "").strip().lower()
    if status == "granted":
        query = query.filter(Consent.is_granted.is_(True), Consent.is_revoked.is_(False))
    elif status == "revoked":
        query = query.filter(Consent.is_revoked.is_(True))
    elif status == "pending":
        query = query.filter(Consent.is_granted.is_(False), Consent.is_revoked.is_(False))

    query = query.order_by(Consent.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": pagination.items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
        "total": pagination.total,
    }


# Back-compat (older name)
def get_consents_by_job(job_id: int):
    return get_consents_by_job_id(job_id)


def grant_consent(
    consent_id: int, signature_data: str | None = None, ip_address: str | None = None
) -> Consent:
    consent = get_consent_by_id(consent_id)

    if consent.is_granted and not consent.is_revoked:
        raise BadRequest("Zgoda jest już udzielona")

    consent.grant(signature_data=signature_data, ip_address=ip_address)
    db.session.commit()
    return consent


def revoke_consent(consent_id: int, reason: str) -> Consent:
    consent = get_consent_by_id(consent_id)

    if not consent.is_granted:
        raise BadRequest("Nie można cofnąć nieudzielonej zgody")

    if consent.is_revoked:
        raise BadRequest("Zgoda jest już cofnięta")

    consent.revoke(reason=reason)
    db.session.commit()
    return consent


def update_consent(consent_id: int, data: dict) -> Consent:
    consent = get_consent_by_id(consent_id)

    if consent.is_granted:
        raise BadRequest("Nie można edytować udzielonej zgody")

    for field in ["consent_text", "scope", "notes"]:
        if field in data:
            setattr(consent, field, data[field])

    db.session.commit()
    return consent


def delete_consent(consent_id: int):
    consent = get_consent_by_id(consent_id)

    if consent.is_granted and not consent.is_revoked:
        raise BadRequest("Nie można usunąć aktywnej zgody. Cofnij ją najpierw.")

    db.session.delete(consent)
    db.session.commit()


def _get_consents_folder() -> str:
    folder = current_app.config.get("CONSENTS_FOLDER")
    if folder:
        return folder
    upload_root = current_app.config.get("UPLOAD_FOLDER", "uploads")
    return os.path.join(upload_root, "consents")


def generate_consent_pdf(consent: Consent) -> str:
    """Generuje PDF zgody (do druku/podpisu)."""
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as e:
        raise BadRequest("Brak biblioteki WeasyPrint - nie można wygenerować PDF") from e

    consents_folder = _get_consents_folder()
    os.makedirs(consents_folder, exist_ok=True)

    pdf_path = os.path.join(consents_folder, f"consent_{consent.id}.pdf")

    job = consent.job or get_job_by_id(consent.job_id)
    customer = getattr(job, "customer", None)

    company_name = get_setting("COMPANY_NAME", "")
    company_address = get_setting("COMPANY_ADDRESS", "")
    company_nip = get_setting("COMPANY_NIP", "")
    company_email = get_setting("COMPANY_EMAIL", "")
    company_phone = get_setting("COMPANY_PHONE", "")

    customer_name = (
        getattr(customer, "display_name", None)
        or getattr(customer, "full_name", None)
        or ""
    )
    customer_email = getattr(customer, "email", "") or ""
    customer_phone = getattr(customer, "phone", "") or ""

    customer_type = getattr(customer, "customer_type", None)

    if (consent.consent_text or "").strip():
        consent_text = (consent.consent_text or "").strip()
    else:
        if consent.consent_type == "data_processing":
            consent_text = get_default_data_processing_consent_text(
                company_name=company_name,
                company_address=company_address,
                company_nip=company_nip,
                company_email=company_email,
            )
        else:
            consent_text = get_default_image_publication_consent_text(company_name, customer_type=customer_type)

    def esc(value: str) -> str:
        return html.escape(value or "")

    consent_html = "<br>".join(esc(consent_text).splitlines())
    job_title = esc(getattr(job, "title", "") or "")

    if consent.consent_type == "data_processing":
        title = "ZGODA NA PRZETWARZANIE DANYCH OSOBOWYCH (RODO)"
    elif consent.consent_type == "image_publication":
        title = get_image_publication_pdf_title(customer_type)
    else:
        title = "ZGODA"

    html_doc = f"""<!doctype html>
<html lang='pl'>
<head>
  <meta charset='utf-8'>
  <style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: DejaVu Sans, Arial, sans-serif; font-size: 11pt; line-height: 1.35; }}
    h1 {{ font-size: 14pt; margin: 0 0 6mm 0; text-align: center; }}
    .box {{ border: 1px solid #ddd; padding: 6mm; margin-bottom: 6mm; }}
    .row {{ margin: 2mm 0; }}
    .label {{ color: #444; }}
    .sigline {{ margin-top: 18mm; border-top: 1px solid #000; padding-top: 2mm; text-align: center; }}
  </style>
</head>
<body>
    <h1>{esc(title)}</h1>

  <div class='box'>
    <div class='row'><span class='label'>Zlecenie:</span> #{job.id} — {job_title}</div>
    <div class='row'><span class='label'>Klient:</span> <strong>{esc(customer_name)}</strong></div>
    <div class='row'><span class='label'>Email:</span> {esc(customer_email)} &nbsp;&nbsp; <span class='label'>Tel.:</span> {esc(customer_phone)}</div>
  </div>

  <div class='box'>
    <div class='row'>{consent_html}</div>
  </div>

  <div class='box'>
    <div class='row'><strong>Dane wykonawcy</strong></div>
    <div class='row'>{esc(company_name)}</div>
    <div class='row'>{esc(company_address)}</div>
    <div class='row'><span class='label'>NIP:</span> {esc(company_nip)} &nbsp;&nbsp; <span class='label'>Tel.:</span> {esc(company_phone)} &nbsp;&nbsp; <span class='label'>Email:</span> {esc(company_email)}</div>
  </div>

  <div class='sigline'>Podpis klienta</div>
</body>
</html>"""

    HTML(string=html_doc).write_pdf(pdf_path)

    consent.pdf_path = pdf_path
    db.session.commit()
    return pdf_path


def upload_signed_scan(consent_id: int, file_storage) -> Consent:
    """Upload signed consent scan/photo; scan implies granted consent."""
    consent = get_consent_by_id(consent_id)

    if not file_storage or not getattr(file_storage, "filename", None):
        raise BadRequest("Brak pliku")

    original_name = str(file_storage.filename)
    filename = secure_filename(original_name)
    if not filename:
        raise BadRequest("Nieprawidłowa nazwa pliku")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"pdf", "png", "jpg", "jpeg"}:
        raise BadRequest("Nieobsługiwany format pliku (dozwolone: PDF/JPG/PNG)")

    consents_folder = _get_consents_folder()
    scans_folder = os.path.join(consents_folder, "signed_scans")
    os.makedirs(scans_folder, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    stored_name = f"consent_{consent.id}_signed_{timestamp}_{filename}"
    stored_path = os.path.join(scans_folder, stored_name)

    file_storage.save(stored_path)

    try:
        size = os.path.getsize(stored_path)
    except OSError:
        size = None

    consent.signed_scan_path = stored_path
    consent.signed_scan_original_filename = original_name
    consent.signed_scan_mime_type = getattr(file_storage, "mimetype", None)
    consent.signed_scan_size = size
    consent.signed_scan_uploaded_at = datetime.utcnow()

    consent.grant(signature_data=None, ip_address=None)
    db.session.commit()
    return consent


def send_consent(consent_id: int) -> Consent:
    """Placeholder for sending consent (email/SMS)."""
    return get_consent_by_id(consent_id)
