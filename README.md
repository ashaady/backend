# Access Backend (FastAPI)

API de gestion des permissions et validations de comptes.

## Demarrage local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Variables d environnement

- `ACCESS_DATABASE_URL` (defaut: `sqlite:///./access.db`)
- `ACCESS_BACKEND_API_KEY` (defaut: `dev-local-access-key`)
- `ACCESS_ALLOWED_ORIGINS` (defaut: `*`)
- `ACCESS_ALLOWED_ORIGIN_REGEX` (optionnel, ex: `^https://.*\\.onrender\\.com$`)
- `ACCESS_CORS_ALLOW_CREDENTIALS` (defaut: `true`; ignore automatiquement si `ACCESS_ALLOWED_ORIGINS=*`)

Exemple Render (frontend + backend sur Render):
- `ACCESS_ALLOWED_ORIGINS=https://votre-frontend.onrender.com`
- ou `ACCESS_ALLOWED_ORIGIN_REGEX=^https://.*\\.onrender\\.com$`

## Structure

- `main.py`: bootstrap FastAPI (CORS, startup, include routers)
- `app/config.py`: configuration env
- `app/db.py`: engine, session, base SQLAlchemy
- `app/models.py`: modeles ORM
- `app/schemas.py`: schemas Pydantic
- `app/deps.py`: dependances (db, api key, admin approuve)
- `app/services/access_service.py`: logique metier
- `app/routers/*.py`: routes system/auth/admin

## Regles metier

- 4 roles: `viewer`, `editor`, `admin`, `owner`
- Toute nouvelle inscription est `pending`
- Exception bootstrap: le premier compte demandant `admin` est auto-approuve
- Ensuite, seul un compte `admin` approuve peut approuver/refuser les nouveaux comptes
