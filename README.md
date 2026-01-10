# EcoShot CRM - System Zarządzania Fotografią

## 📸 Opis

Kompletny CRM dla firmy fotograficznej jako **Single Page Application (SPA)** z backendem REST API w Flask.

System realizuje wymuszony flow biznesowo-prawny:
**Klient → Zlecenie → Umowa → Faktura → Galeria**

### ✨ Kluczowe funkcjonalności

- **Klienci**: CRUD z walidacją NIP, osoby fizyczne i firmy
- **Zlecenia**: Flow ze statusami, dodatki (add-ons), oferty szablonowe
- **Umowy**: Generowanie PDF, podpisy cyfrowe (Base64), weryfikacja hash
- **Zgody**: Publikacja wizerunku z możliwością wycofania
- **Faktury**: Automatyczne numerowanie, pozycje, multi-płatności
- **Płatności**: Wiele płatności na fakturę, refundy, tracking
- **Galerie**: Proof/Selection/Final/Archive, publiczny dostęp po linku + PIN, watermarki, pobieranie ZIP i pojedynczych zdjęć (zgodnie z regułami)
- **Zdjęcia**: Upload, EXIF, wybór klienta, kolejność
- **Finanse**: Raporty przychodów, statystyki

### 🆕 Najnowsze poprawki / dodatki

- **Publiczna galeria dla klienta**: link `/g/<hash>` + PIN → sesja ważna 30 min (JWT ograniczony do galerii)
- **Bezpieczne pobieranie**: backend egzekwuje reguły (watermark przed płatnością, pobieranie finali dopiero po opłaceniu)
- **Pobieranie pojedynczego zdjęcia**: w modalu podglądu (gdy pobieranie jest dostępne)
- **Branding**: osobne logo dla CRM i osobne logo dla widoku galerii klienta
- **Archive**: galerie typu `archive` nie są publicznie dostępne
- **UX sesji**: po wygaśnięciu sesji CRM następuje automatyczne przekierowanie na login po ~2.5 s
- **Automatyzacje (CLI/cron)**: przypomnienia mailowe + auto-anulowanie nieopłaconych zleceń

### 🎟️ Vouchery + Canva (workflow)

CRM generuje vouchery jako PDF (z kodem + QR) i odpowiada za całą logikę rabatu (ważność, jednorazowość, przypięcie do zlecenia/faktury).

Canva w tym workflow jest używana wyłącznie jako wsparcie graficzne:
- **Canva project URL**: link referencyjny do projektu (żeby łatwo wrócić i edytować design).
- **Tło vouchera**: export PNG/JPG (przód/tył), które wgrywasz do CRM i jest używane jako tło w generowanym PDF.

Canva **nie** generuje kodów, **nie** personalizuje danych vouchera i **nie** jest wymagana do naliczania rabatu.

1) W Canva przygotuj tła vouchera (przód i opcjonalnie tył) i wyeksportuj do PNG/JPG.

2) W CRM:
- Ustawienia → **Promocje** → utwórz/edytuj promocję (typ, wartość, czas trwania)
- W tej samej edycji możesz wkleić **Canva project URL** i wgrać tła vouchera (przód/tył)

3) Generowanie voucherów:
- Menu → **Vouchery** → wybierz promocję → podaj ilość → **Generuj PDF**

4) Użycie vouchera:
- Zlecenia → Nowe/Edytuj → pole **Voucher (kod)** → zeskanuj QR lub wpisz kod → zapisz
- Rabat zostanie naliczony na zleceniu i uwzględniony przy generowaniu faktury (pozycja ujemna „Rabat (voucher …)”).

5) (Opcjonalnie) Canva credentials:
- Ustawienia → **Integracje → Canva**
- Pola są opcjonalne; jeśli puste, nie nadpisują istniejącej konfiguracji.
- W obecnej wersji workflow vouchery działają bez tego (credentials są przygotowaniem pod ewentualne przyszłe automatyzacje).

### 🔒 Enforcement biznesowy

- **Umowa**: Można utworzyć tylko dla zlecenia z wypełnionym Customer
- **Faktura**: Można wygenerować tylko gdy umowa jest podpisana + zgoda udzielona
- **Galeria**: Publikacja tylko gdy faktura istnieje
- **Galeria finalna**: Pobieranie tylko gdy faktura w 100% opłacona

## 🛠️ Stack technologiczny

### Backend
- Python 3.10+
- Flask (REST API)
- MySQL / MariaDB
- SQLAlchemy (ORM)
- Flask-Migrate (migracje)
- Flask-JWT-Extended (autentykacja)
- Marshmallow (walidacja)
- WeasyPrint / ReportLab (PDF)
- Pillow (obrazy)

### Frontend
- HTML5 + CSS3
- Bootstrap 5 (UI)
- Vanilla JavaScript ES6 Modules
- Fetch API (komunikacja z REST)
- Toast notifications

## 📦 Instalacja

### 1. Klonowanie repozytorium

```bash
git clone <repo-url>
cd crm.ecoshot.com.pl3
```

### 2. Środowisko Python

```bash
# Utwórz virtual environment
python -m venv venv

# Aktywuj
source venv/bin/activate  # Linux/Mac
# lub
venv\Scripts\activate  # Windows

# Zainstaluj zależności
pip install -r requirements.txt
```

### 3. Baza danych MySQL

```bash
# Utwórz bazę danych
mysql -u root -p
CREATE DATABASE ecoshot_crm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ecoshot'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON ecoshot_crm.* TO 'ecoshot'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 4. Konfiguracja

Stwórz plik `.env` w głównym katalogu:

```env
FLASK_APP=app.app:create_app
FLASK_ENV=development
SECRET_KEY=your-secret-key-here-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key-here

DATABASE_URL=mysql+pymysql://ecoshot:strong_password@localhost/ecoshot_crm

UPLOAD_FOLDER=/var/www/uploads

# SMTP (przypomnienia)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_user
SMTP_PASSWORD=your_password
SMTP_USE_TLS=true
SMTP_FROM=kontakt@ecoshot.com.pl

# Reminders
REMINDERS_ENABLED=true
REMINDERS_SCHEDULE_TO=kontakt@ecoshot.com.pl
```

### 5. Migracje bazy danych

```bash
# Repo zawiera już migracje w katalogu migrations/.
# Wykonaj upgrade do najnowszej wersji:
flask db upgrade
```

### 6. Dane seed (oferty fotograficzne)

```bash
flask seed-offers
```

### 7. Utworzenie pierwszego użytkownika (admin)

```bash
flask shell
```

```python
from app.extensions import db
from app.auth.models import User

admin = User(
    username='admin',
    email='admin@ecoshot.pl',
    first_name='Admin',
    last_name='User',
    role='admin',
    is_active=True
)
admin.set_password('admin123')  # Zmień w produkcji!
db.session.add(admin)
db.session.commit()
exit()
```

## 🚀 Uruchomienie

### Development

```bash
flask run --debug
```

Backend API dostępne na: `http://localhost:5000/api`

### Frontend

SPA jest serwowana przez Flask pod `/`.

### Logowanie

- **Username**: `admin`
- **Password**: `admin123` (lub to co ustawiłeś)

## 📂 Struktura projektu

```
app/
├── app.py                  # Application factory
├── config.py               # Konfiguracja (Dev/Prod/Test)
├── extensions.py           # Flask extensions init
│
├── core/                   # Rdzeń systemu
│   ├── enforcement.py      # Business rules enforcement
│   ├── permissions.py      # Role-based permissions
│   └── decorators.py       # API decorators
│
├── auth/                   # Autentykacja
│   ├── models.py           # User model
│   ├── schemas.py          # Validation schemas
│   ├── services.py         # Business logic
│   └── routes.py           # REST endpoints
│
├── customers/              # Klienci
├── jobs/                   # Zlecenia + oferty
├── contracts/              # Umowy
├── consents/               # Zgody
├── invoices/               # Faktury
├── payments/               # Płatności
├── galleries/              # Galerie
├── photos/                 # Zdjęcia
└── finance/                # Raporty finansowe

frontend/
├── index.html              # SPA template
├── app.js                  # Inicjalizacja
├── router.js               # Hash routing
├── api.js                  # Fetch wrapper + JWT
├── toasts.js               # Notifications
├── sidebar.js              # Nawigacja
└── views/                  # Widoki
    ├── login.js
    ├── dashboard.js
    ├── customers.js
    └── ...
```

## 🔑 REST API Endpoints

### Authentication
- `POST /api/auth/register` - Rejestracja
- `POST /api/auth/login` - Logowanie (zwraca JWT)
- `GET /api/auth/me` - Profil użytkownika
- `PUT /api/auth/me` - Aktualizacja profilu
- `POST /api/auth/me/password` - Zmiana hasła

### Customers
- `GET /api/customers` - Lista klientów (pagination)
- `GET /api/customers/{id}` - Szczegóły klienta
- `POST /api/customers` - Nowy klient
- `PUT /api/customers/{id}` - Aktualizacja
- `DELETE /api/customers/{id}` - Usunięcie

### Jobs
- `GET /api/jobs` - Lista zleceń
- `POST /api/jobs` - Nowe zlecenie
- `PUT /api/jobs/{id}/status` - Zmiana statusu (z enforcement)
- `PUT /api/jobs/{id}/addons/{addon_id}` - Toggle add-on
- `GET /api/jobs/offers` - Lista ofert

### Contracts
- `POST /api/contracts` - Generowanie umowy (PDF + hash)
- `POST /api/contracts/{id}/sign` - Podpis (public)
- `POST /api/contracts/{id}/send` - Wysłanie emailem
- `GET /api/contracts/{id}/pdf` - Pobieranie PDF

### Invoices
- `POST /api/invoices` - Generowanie faktury (z enforcement)
- `GET /api/invoices/{id}` - Szczegóły
- `POST /api/invoices/{id}/send` - Wysłanie
- `GET /api/invoices/{id}/pdf` - PDF

### Galleries
- `POST /api/galleries` - Nowa galeria
- `POST /api/galleries/{id}/publish` - Publikacja (z enforcement)
- `POST /api/galleries/{id}/send-access` - Wysłanie dostępu (hash + PIN)

#### Publiczne API galerii (dla klienta)
- `GET /api/gallery/{hash}` - Metadane + stan publicznej galerii (wymaga tokenu galerii jeśli zabezpieczona)
- `POST /api/gallery/{hash}/pin` - Weryfikacja PIN → token galerii ważny 30 min
- `GET /api/gallery/{hash}/download` - ZIP (tylko gdy dostępne wg reguł)

### Photos
- `POST /api/photos/upload` - Upload zdjęć (multipart)
- `POST /api/photos/{id}/toggle-selection` - Wybór klienta (public)
- `PUT /api/photos/batch-update` - Aktualizacja wielu
- `PUT /api/photos/reorder` - Zmiana kolejności

### Finance
- `GET /api/finance/revenue/summary` - Przychody (okres)
- `GET /api/finance/revenue/monthly` - Przychody miesięczne
- `GET /api/finance/dashboard` - Statystyki dashboardu

## 🔐 Role i uprawnienia

### Role
- `admin` - Pełen dostęp
- `photographer` - Klienci, zlecenia, galerie
- `accountant` - Faktury, płatności, raporty
- `viewer` - Tylko odczyt

### Permissions (przykłady)
- `VIEW_CUSTOMERS`, `CREATE_CUSTOMER`, `EDIT_CUSTOMER`
- `VIEW_JOBS`, `CREATE_JOB`, `CHANGE_JOB_STATUS`
- `CREATE_CONTRACT`, `VIEW_INVOICES`, `MANAGE_PAYMENTS`
- `PUBLISH_GALLERY`, `VIEW_REPORTS`

## 🧪 Testing

```bash
# Unit tests
pytest tests/

# Coverage
pytest --cov=app tests/
```

## 📝 Licencja

Proprietary - EcoShot © 2026

## 👨‍💻 Autor

Michał - EcoShot CRM Development Team

## ⏰ Cron (automatyzacje)

Poniższe komendy są przygotowane do uruchamiania z crona (Flask CLI). Uruchamiaj je w katalogu projektu, na tym samym env co aplikacja.

1) Plan na jutro (wewnętrzny email):

```bash
flask remind-schedule-tomorrow
```

2) Przypomnienie o nieopłaconej fakturze po 7 dniach od terminu:

```bash
flask remind-unpaid --days-after-due 7
```

3) Auto-anulowanie nieopłaconych zleceń po 31 dniach od terminu (opcjonalny email do klienta):

```bash
flask cancel-unpaid --days-after-due 31 --notify
```

### Przykładowe wpisy crontab

Uwaga: dopasuj ścieżki, użytkownika oraz ustaw zmienne środowiskowe (np. w crontab lub w pliku, który sourcujesz).

```cron
# Plan na jutro (18:00)
0 18 * * * cd /home/michal/Dokumenty/Projects/crm.ecoshot.com.pl3 && FLASK_ENV=production /home/michal/Dokumenty/Projects/crm.ecoshot.com.pl3/venv/bin/flask remind-schedule-tomorrow >> /var/log/crm_reminders.log 2>&1

# Unpaid reminder (09:00)
0 9 * * * cd /home/michal/Dokumenty/Projects/crm.ecoshot.com.pl3 && FLASK_ENV=production /home/michal/Dokumenty/Projects/crm.ecoshot.com.pl3/venv/bin/flask remind-unpaid --days-after-due 7 >> /var/log/crm_reminders.log 2>&1

# Auto-cancel unpaid (09:30)
30 9 * * * cd /home/michal/Dokumenty/Projects/crm.ecoshot.com.pl3 && FLASK_ENV=production /home/michal/Dokumenty/Projects/crm.ecoshot.com.pl3/venv/bin/flask cancel-unpaid --days-after-due 31 --notify >> /var/log/crm_reminders.log 2>&1
```

## ✅ Deploy checklist (production)

Minimalna lista kontrolna na serwerze:

1) **Sekrety i env**
- Ustaw `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL` oraz dane SMTP jako zmienne środowiskowe (nie commituj `.env`).
- Ustaw `FLASK_APP=app.app:create_app` oraz `FLASK_ENV=production`.

2) **Uploads**
- Ustaw `UPLOAD_FOLDER` (np. `/var/www/uploads`) i nadaj uprawnienia do zapisu dla użytkownika, który uruchamia aplikację.
- Upewnij się, że folder jest **persistowany** (nie w kontenerze ephemeral).

3) **Migracje DB**
Po deployu nowej wersji kodu uruchom:

```bash
flask db upgrade
```

4) **Uruchomienie aplikacji**
- Produkcyjnie uruchamiaj przez WSGI (np. gunicorn) lub systemd service, nie przez `flask run`.
- Zadbaj o logowanie (stdout/systemd journal lub plik logów).

5) **Cron i zmienne środowiskowe**
Cron często nie ma tych samych zmiennych co shell użytkownika — najprościej w każdej linijce jawnie załadować env.

Przykład (env w pliku `/etc/ecoshot/crm.env`):

```cron
# Przykład: wczytaj env i uruchom komendę
0 9 * * * set -a; . /etc/ecoshot/crm.env; set +a; cd /home/michal/Dokumenty/Projects/crm.ecoshot.com.pl3 && /home/michal/Dokumenty/Projects/crm.ecoshot.com.pl3/venv/bin/flask remind-unpaid --days-after-due 7 >> /var/log/crm_reminders.log 2>&1
```

6) **Backupy**
- Jeśli używasz wbudowanych komend backupu, dodaj je do crona (np. `flask daily-full-backup`) i rotuj pliki zgodnie z potrzebami.
