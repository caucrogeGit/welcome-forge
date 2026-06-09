"""
config.py — Configuration de l'application
==========================================
Charge les variables d'environnement depuis les fichiers env/* appropriés.

Environnements disponibles :
    dev  (défaut) — charge env/example puis env/dev
    prod          — charge env/example puis env/prod

Sélection de l'environnement :
    Variable d'environnement APP_ENV=prod  (shell ou .env)
    ou depuis le point d'entrée (app.py parse --env et pose os.environ["APP_ENV"])

Fichiers d'environnement :
    env/example  commité dans git — squelette des variables requises
    env/dev      ignoré par git   — valeurs réelles de développement
    env/prod     ignoré par git   — valeurs réelles de production

Ce module ne produit aucun effet de bord à l'import :
    - pas de parse CLI
    - pas de connexion réseau
    - pas de création de pool
"""
from dotenv import load_dotenv
import os

# ── Détection de l'environnement ───────────────────────────────────────────────

APP_ENV = os.getenv("APP_ENV", "dev")

# ── Chargement des variables d'environnement ───────────────────────────────────

load_dotenv("env/example")                   # valeurs par défaut (squelette)
load_dotenv(f"env/{APP_ENV}", override=True) # surcharge avec l'environnement choisi

# ── Variables de configuration ─────────────────────────────────────────────────

DB_ADMIN_HOST  = os.getenv("DB_ADMIN_HOST", "localhost")
DB_ADMIN_PORT  = int(os.getenv("DB_ADMIN_PORT", 3306))
DB_ADMIN_LOGIN = os.getenv("DB_ADMIN_LOGIN", "root")
DB_ADMIN_PWD   = os.getenv("DB_ADMIN_PWD", "")

DB_NAME        = os.getenv("DB_NAME", "forge_db")
DB_CHARSET     = os.getenv("DB_CHARSET", "utf8mb4")
DB_COLLATION   = os.getenv("DB_COLLATION", "utf8mb4_unicode_ci")

DB_APP_HOST    = os.getenv("DB_APP_HOST", "localhost")
DB_APP_PORT    = int(os.getenv("DB_APP_PORT", 3306))
DB_APP_LOGIN   = os.getenv("DB_APP_LOGIN", "forge")
DB_APP_PWD     = os.getenv("DB_APP_PWD", "")
DB_POOL_SIZE   = int(os.getenv("DB_POOL_SIZE", 5))

# Alias de compatibilité interne — le fonctionnement applicatif normal repose sur DB_APP_*.
DB_HOST        = DB_APP_HOST
DB_PORT        = DB_APP_PORT
DB_USER_LOGIN  = DB_APP_LOGIN
DB_USER_PWD    = DB_APP_PWD

APP_NAME          = os.getenv("APP_NAME",          "Forge")
APP_ROUTES_MODULE = os.getenv("APP_ROUTES_MODULE", "mvc.routes")
VIEWS_DIR         = os.getenv("VIEWS_DIR",         "mvc/views")
SQL_DIR           = os.getenv("SQL_DIR",           "mvc/models/sql")

UPLOAD_ROOT       = os.path.abspath(os.getenv("UPLOAD_ROOT", "storage/uploads"))
UPLOAD_MAX_SIZE   = int(os.getenv("UPLOAD_MAX_SIZE", 5 * 1024 * 1024))
UPLOAD_ALLOWED_EXTENSIONS = [
    item.strip().lower().lstrip(".")
    for item in os.getenv("UPLOAD_ALLOWED_EXTENSIONS", "jpg,jpeg,png,webp,pdf").split(",")
    if item.strip()
]
UPLOAD_ALLOWED_MIME_TYPES = [
    item.strip().lower()
    for item in os.getenv(
        "UPLOAD_ALLOWED_MIME_TYPES",
        "image/jpeg,image/png,image/webp,application/pdf",
    ).split(",")
    if item.strip()
]

MAIL_HOST      = os.getenv("MAIL_HOST", "")
MAIL_PORT      = int(os.getenv("MAIL_PORT", 587))
MAIL_USERNAME  = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD  = os.getenv("MAIL_PASSWORD", "")
_MAIL_FROM_ADDRESS = os.getenv("MAIL_FROM_ADDRESS", "noreply@localhost")
_MAIL_FROM_NAME    = os.getenv("MAIL_FROM_NAME", "Forge")
MAIL_FROM = (
    os.getenv("MAIL_FROM")
    or (f"{_MAIL_FROM_NAME} <{_MAIL_FROM_ADDRESS}>" if _MAIL_FROM_NAME else _MAIL_FROM_ADDRESS)
)
MAIL_USE_TLS   = os.getenv("MAIL_USE_TLS", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
MAIL_USE_SSL   = os.getenv("MAIL_USE_SSL", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
MAIL_TIMEOUT   = float(os.getenv("MAIL_TIMEOUT", 10))
MAIL_ENABLED   = os.getenv("MAIL_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on"
}
MAIL_TRANSPORT     = os.getenv("MAIL_TRANSPORT", "log")
MAIL_LOG_DIR       = os.getenv("MAIL_LOG_DIR", "storage/mail")
MAIL_TEMPLATES_DIR = os.getenv("MAIL_TEMPLATES_DIR", "mvc/mail/templates")
MAIL_LOG_ENABLED   = os.getenv("MAIL_LOG_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on"
}

APP_HOST          = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT          = int(os.getenv("APP_PORT", 8000))
_ssl_default      = "false" if APP_ENV == "prod" else "true"
APP_SSL_ENABLED   = os.getenv("APP_SSL_ENABLED", _ssl_default).strip().lower() in {
    "1", "true", "yes", "on"
}
SSL_CERTFILE      = os.getenv("SSL_CERTFILE", "cert.pem")
SSL_KEYFILE       = os.getenv("SSL_KEYFILE", "key.pem")
APP_CSP_NONCE_ENABLED = os.getenv("APP_CSP_NONCE_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on"
}

# Reverse proxy — IPs des proxies de confiance autorisés à fournir X-Real-IP.
# Liste séparée par virgules, espaces tolérés. Vide par défaut : Forge ignore
# alors complètement X-Real-IP (HTTP-TRUSTED-PROXY-IP-001).
APP_TRUSTED_PROXIES = frozenset(
    p.strip() for p in os.getenv("APP_TRUSTED_PROXIES", "").split(",") if p.strip()
)
