"""
app.py - Point d'entrée — Forge 1.0.0-beta.15
======================================
Serveur HTTP/HTTPS multi-thread pur Python basé sur http.server.
Le chiffrement SSL est activé via APP_SSL_ENABLED pour le développement local.
En production derrière Nginx, Forge écoute en HTTP local et Nginx termine TLS.

Responsabilités :
    - Démarrer le serveur HTTP/HTTPS
    - Recevoir chaque requête entrante
    - Encapsuler la requête dans un objet Request
    - Déléguer le traitement via Application.dispatch()
    - Retourner la réponse via un objet Response
    - Servir les fichiers statiques (CSS, JS, images, polices)

Ce fichier ne contient aucune logique métier.
La gestion de l'authentification (login, logout, protection des routes) est
entièrement du ressort de l'application : voir mvc/controllers/auth_controller.py.
Le framework fournit uniquement les outils (sessions, CSRF, hashing, décorateurs).

Les routes sont déclarées dans mvc/routes.py.
La configuration (hôte, port, certificats) est dans config.py.
Les classes Request et Response sont dans core/http/request.py
et core/http/response.py.

Flux simplifié :

    Navigateur HTTPS ou reverse proxy local
        → RequestHandler
        → Request
        → vérification route / session / CSRF
        → ROUTES[(method, path)]
        → contrôleur (+ décorateurs @require_auth / @require_role)
        → Response
        → navigateur

Remarques :
    - Une route non publique exige une session authentifiée
    - Une route unsafe exige un token CSRF sauf exemption explicite
    - Les routes /login et /logout restent publiques mais protégées par CSRF
    - Les permissions fines par rôle sont appliquées via @require_role dans
      les contrôleurs, pas dans ce handler

Prérequis — Génération du certificat SSL auto-signé (à faire une seule fois) :

    openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"

    req -x509        : génère un certificat auto-signé
    -newkey rsa:2048 : crée une clé privée RSA de 2048 bits
    -keyout key.pem  : enregistre la clé privée dans key.pem
    -out cert.pem    : enregistre le certificat dans cert.pem
    -days 365        : valide 1 an
    -nodes           : pas de mot de passe sur la clé
    -subj "/CN=localhost" : nom du serveur

    Le navigateur affichera un avertissement de sécurité car le certificat
    n'est pas émis par une autorité reconnue. Cliquer sur "Avancer quand même".

Démarrage :
    python3 app.py              → mode dev (défaut, HTTPS local)
    python3 app.py --env prod   → mode prod (HTTP local par défaut)
"""
import argparse as _argparse
import errno as _errno
import os as _os
import sys as _sys

# ── Détection de l'environnement avant tout import de config ──────────────────
# L'argument --env est parsé ici, point d'entrée unique de la CLI.
# config.py lit ensuite os.environ["APP_ENV"] sans effet de bord.
_p = _argparse.ArgumentParser(add_help=False)
_p.add_argument("--env", choices=["dev", "prod"], default="dev")
_os.environ.setdefault("APP_ENV", _p.parse_known_args()[0].env)

import logging
import mimetypes
import socket
import ssl
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import importlib
from config import (APP_HOST, APP_PORT, APP_SSL_ENABLED, SSL_CERTFILE, SSL_KEYFILE,
                    APP_ENV, APP_NAME, APP_ROUTES_MODULE,
                    VIEWS_DIR, SQL_DIR,
                    UPLOAD_ROOT, UPLOAD_MAX_SIZE,
                    UPLOAD_ALLOWED_EXTENSIONS, UPLOAD_ALLOWED_MIME_TYPES,
                    MAIL_HOST, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD,
                    MAIL_FROM, MAIL_USE_TLS, MAIL_USE_SSL, MAIL_TIMEOUT, MAIL_ENABLED,
                    MAIL_TRANSPORT, MAIL_LOG_DIR, MAIL_TEMPLATES_DIR, MAIL_LOG_ENABLED,
                    DB_APP_HOST, DB_APP_PORT, DB_NAME, DB_APP_LOGIN, DB_APP_PWD, DB_POOL_SIZE,
                    APP_CSP_NONCE_ENABLED, APP_TRUSTED_PROXIES)
import core.security.csp as _csp
from core.security.headers import apply_security_headers
import core.forge as forge
from core.app.dev_server import (
    format_port_in_use_message,
    format_prod_host_guard_error,
    format_startup_messages,
    should_block_prod_public_host,
)
forge.configure(
    app_name     = APP_NAME,
    app_env      = APP_ENV,
    views_dir    = VIEWS_DIR,
    sql_dir      = SQL_DIR,
    upload_root  = UPLOAD_ROOT,
    upload_max_size = UPLOAD_MAX_SIZE,
    upload_allowed_extensions = UPLOAD_ALLOWED_EXTENSIONS,
    upload_allowed_mime_types = UPLOAD_ALLOWED_MIME_TYPES,
    mail_host     = MAIL_HOST,
    mail_port     = MAIL_PORT,
    mail_username = MAIL_USERNAME,
    mail_password = MAIL_PASSWORD,
    mail_from     = MAIL_FROM,
    mail_use_tls  = MAIL_USE_TLS,
    mail_use_ssl  = MAIL_USE_SSL,
    mail_timeout  = MAIL_TIMEOUT,
    mail_enabled       = MAIL_ENABLED,
    mail_transport     = MAIL_TRANSPORT,
    mail_log_dir       = MAIL_LOG_DIR,
    mail_templates_dir = MAIL_TEMPLATES_DIR,
    mail_log_enabled   = MAIL_LOG_ENABLED,
    db_host      = DB_APP_HOST,
    db_port      = DB_APP_PORT,
    db_name      = DB_NAME,
    db_user      = DB_APP_LOGIN,
    db_password  = DB_APP_PWD,
    db_pool_size = DB_POOL_SIZE,
    trusted_proxies = APP_TRUSTED_PROXIES,
)
from core.http.request import Request, RequestEntityTooLarge
from core.http.response import Response
from core.http.helpers import html as _html
from core.app.application import Application
# CORE-DROP-UPLOADS-001 (ADR-019) : le service de fichiers est un opt-in
# (forge-mvc-files). Import lazy dans le handler /media (l'app démarre sans).
from integrations.jinja2.renderer import Jinja2Renderer
from core.templating.manager import template_manager

template_manager.register(Jinja2Renderer(VIEWS_DIR))

_routes = importlib.import_module(APP_ROUTES_MODULE)
forge.configure(router=_routes.router)
_app    = Application(_routes.router)

logger = logging.getLogger(__name__)

# ── Fichiers statiques ─────────────────────────────────────────────────────────

STATIC_DIR    = _os.path.realpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "static"))
STATIC_TYPES  = {"css": "text/css", "js": "application/javascript", "svg": "image/svg+xml",
                 "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "ico": "image/x-icon", "woff2": "font/woff2", "woff": "font/woff"}
# 1h en dev (rechargement facile), 7 jours en prod (fichiers versionnés)
STATIC_CACHE  = "max-age=3600" if APP_ENV == "dev" else "max-age=604800, immutable"
# Chemins auth sensibles — aucun cache navigateur toléré
_AUTH_NO_STORE_PATHS = frozenset({"/login", "/login/mfa", "/logout"})


def _is_safe_static_path(static_dir: str, filepath: str) -> bool:
    """Vérifie via commonpath que filepath est strictement sous static_dir."""
    try:
        return _os.path.commonpath([static_dir, filepath]) == static_dir
    except ValueError:
        return False


class RequestHandler(BaseHTTPRequestHandler):
    """
    Routeur/dispatcher des requêtes HTTP.

    Chaque requête entrante crée une instance de cette classe dans son propre thread.
    Elle encapsule la requête dans un objet Request, recherche le contrôleur
    correspondant dans ROUTES et lui délègue le traitement.

    Le contrôle d'accès ici est volontairement minimal :
        - si le chemin est public, la requête est dispatchée normalement
        - sinon, une session authentifiée est requise
    Les vérifications CSRF et de rôles sont traitées dans l'application et les
    contrôleurs, pas dans ce handler.

    Elle ne contient aucune logique métier.
    """

    def do_GET(self):
        """Traite les requêtes HTTP GET."""
        try:
            request = Request(self)
            if request.path == "/health":
                self._send_response(Response(200, b'{"status": "ok"}', "application/json"))
                return
            if request.path == "/favicon.ico":
                self._serve_static("/static/favicon.ico")
                return
            if request.path.startswith("/static"):
                self._serve_static(request.path)
                return
            if request.path.startswith("/media/"):
                self._serve_media(request.path)
                return
            self._send_response(self._dispatch(request))
        except Exception:
            logger.exception("Erreur GET %s", self.path)
            self._send_response(_html("errors/500.html", 500))

    def do_POST(self):
        """Traite les requêtes HTTP POST."""
        self._handle_dynamic_request("POST")

    def do_PUT(self):
        """Traite les requêtes HTTP PUT."""
        self._handle_dynamic_request("PUT")

    def do_PATCH(self):
        """Traite les requêtes HTTP PATCH."""
        self._handle_dynamic_request("PATCH")

    def do_DELETE(self):
        """Traite les requêtes HTTP DELETE."""
        self._handle_dynamic_request("DELETE")

    def _handle_dynamic_request(self, label: str):
        """Traite une requête applicative non statique."""
        try:
            request = Request(self)
            self._send_response(self._dispatch(request))
        except RequestEntityTooLarge:
            self._send_response(_html("errors/413.html", 413))
        except Exception:
            logger.exception("Erreur %s %s", label, self.path)
            self._send_response(_html("errors/500.html", 500))

    def _dispatch(self, request) -> Response:
        """Délègue le routage et le contrôle d'accès à l'Application."""
        if APP_CSP_NONCE_ENABLED:
            _csp.set_request_nonce(_csp.generate_nonce())
        else:
            _csp.set_request_nonce(None)
        return _app.dispatch(request)

    def _send_response(self, response: Response) -> None:
        """Envoie un objet Response au navigateur avec les headers de sécurité.

        Les headers de sécurité Forge (X-Frame-Options, CSP, etc.) sont posés
        en `setdefault` via `core.security.headers.apply_security_headers` —
        une route applicative qui définit explicitement un de ces headers
        garde la main. Voir `WSGI-SECURITY-HEADERS-001`.
        """
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))

        # Couche de défense partagée avec le chemin WSGI : un seul helper,
        # un seul contrat. `include_hsts=True` : le serveur de dev sait quand
        # il sert TLS via APP_SSL_ENABLED ; HSTS sur HTTP local est inoffensif.
        headers_out: dict[str, str] = {str(k): str(v) for k, v in response.headers.items()}
        if self.path.split("?")[0] in _AUTH_NO_STORE_PATHS:
            headers_out.setdefault("Cache-Control", "no-store")
        apply_security_headers(
            headers_out,
            include_hsts=True,
            csp=_csp.build_csp_header(_csp.get_request_nonce()),
        )
        for key, value in headers_out.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.body)

    def _serve_static(self, path: str) -> None:
        """
        Sert un fichier statique (CSS, JS, SVG, PNG, JPG, ICO, WOFF/WOFF2).

        Sécurité — Protection contre le Path Traversal :
            os.path.realpath() résout le chemin absolu réel ; commonpath()
            vérifie que le fichier est strictement sous static/. Sinon → 403.
        """
        filepath = _os.path.realpath(_os.path.join(STATIC_DIR, path.removeprefix("/static/")))

        if not _is_safe_static_path(STATIC_DIR, filepath):
            self._send_response(_html("errors/403.html", 403))
            return

        if not _os.path.isfile(filepath):
            self._send_response(_html("errors/404.html", 404))
            return

        try:
            with open(filepath, "rb") as file:
                content = file.read()
            ext          = path.split(".")[-1].lower()
            content_type = STATIC_TYPES.get(ext) or mimetypes.guess_type(filepath)[0] or "application/octet-stream"
            self._send_response(Response(200, content, content_type,
                                         headers={"Cache-Control": STATIC_CACHE}))
        except FileNotFoundError:
            self._send_response(_html("errors/404.html", 404))

    def _serve_media(self, path: str) -> None:
        try:
            from forge_mvc_files import serve_media_file
        except ImportError:
            self._send_response(Response(404, b"Not found", "text/plain; charset=utf-8"))
            return
        relative_path = path.removeprefix("/media/")
        self._send_response(serve_media_file(relative_path))

    def log_message(self, format, *args):
        """Affiche chaque requête reçue dans le terminal avec l'adresse IP du client."""
        logger.info("[%s] %s", self.address_string(), format % args)


def _make_ssl_context() -> ssl.SSLContext:
    """
    Crée le contexte SSL du serveur HTTPS de développement.

    Réservé au développement local, à la pédagogie et aux tests.
    En production, TLS doit être terminé par Nginx ou un reverse proxy équivalent.

    TLS 1.2 est le minimum explicitement imposé ; TLS 1.3 est utilisé si disponible.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


# Délai max accordé au handshake TLS d'un client avant abandon de la connexion.
# Protège la boucle d'accept des clients muets, lents, ou des scanners.
TLS_HANDSHAKE_TIMEOUT = 10  # secondes


class TLSThreadingHTTPServer(ThreadingHTTPServer):
    """
    Serveur HTTPS de développement avec handshake TLS par thread client.

    Le socket d'écoute reste volontairement un socket TCP brut. L'ancien code
    `server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)`
    appliquait TLS au socket d'écoute, ce qui faisait exécuter le handshake
    dans la boucle accept() du thread principal : un client TLS lent, muet,
    parlant le mauvais protocole, ou refusant le certificat auto-signé
    pouvait alors figer tout le serveur de développement (Recv-Q saturé,
    ERR_TIMED_OUT côté client, aucun traceback).

    Flux réel :

        TCP accept()                       (thread principal — non bloquant)
            → ThreadingMixIn lance un thread (thread du client)
                → wrap_socket()              (handshake TLS, borné par timeout)
                    → RequestHandler         (requête HTTP)

    Ne pas simplifier cette classe en réintroduisant
    `wrap_socket(server.socket)` sur le socket d'écoute : ce serait
    exactement la régression du bug d'origine. Voir ADR-015 — Handshake TLS
    par thread client pour le serveur de développement
    (`docs/adr/015-dev-tls-handshake-per-thread.md`).
    """
    ssl_context: ssl.SSLContext | None = None

    def get_request(self):
        # accept() retourne un socket TCP brut, sans TLS.
        # Le wrap se fera dans process_request_thread (= thread du client).
        return self.socket.accept()

    def process_request_thread(self, request, client_address):
        # Cette méthode s'exécute dans le thread lancé par ThreadingMixIn,
        # donc le handshake TLS ne bloque jamais la boucle d'accept.
        if self.ssl_context is not None:
            request.settimeout(TLS_HANDSHAKE_TIMEOUT)
            try:
                request = self.ssl_context.wrap_socket(request, server_side=True)
            except (ssl.SSLError, OSError, socket.timeout) as exc:
                logger.warning(
                    "Handshake TLS échoué depuis %s : %s", client_address, exc
                )
                self.shutdown_request(request)
                return
            request.settimeout(None)  # comportement bloquant standard ensuite
        super().process_request_thread(request, client_address)


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _env = APP_ENV.upper()
    _fmt = {
        "dev" : f"[%(levelname)s-{_env}] %(message)s",
        "prod": f"%(asctime)s [%(levelname)s-{_env}] %(message)s",
    }
    logging.basicConfig(
        level  = logging.DEBUG if APP_ENV == "dev" else logging.INFO,
        format = _fmt[APP_ENV],
    )

    # APP-PY-PROD-HOST-GUARD-001 : `python app.py` n'est pas un serveur de
    # production publique. Si APP_ENV=prod ET APP_HOST écoute sur toutes les
    # interfaces (0.0.0.0 / ::), on refuse de démarrer plutôt que d'émettre
    # un simple warning ignorable. Le garde n'est PAS dans le chemin WSGI
    # (`create_configured_wsgi_app`) — la production WSGI/Gunicorn reste
    # entièrement fonctionnelle.
    if should_block_prod_public_host(APP_ENV, APP_HOST):
        for _line in format_prod_host_guard_error(APP_ENV, APP_HOST).splitlines():
            logger.error(_line)
        _sys.exit(1)

    TLSThreadingHTTPServer.allow_reuse_address = True
    try:
        server = TLSThreadingHTTPServer((APP_HOST, APP_PORT), RequestHandler)
    except OSError as exc:
        if exc.errno == _errno.EADDRINUSE:
            for _line in format_port_in_use_message(APP_HOST, APP_PORT).splitlines():
                logger.error(_line)
            _sys.exit(1)
        raise

    if APP_SSL_ENABLED:
        ssl_ctx = _make_ssl_context()
        ssl_ctx.load_cert_chain(certfile=SSL_CERTFILE, keyfile=SSL_KEYFILE)
        server.ssl_context = ssl_ctx

    logger.info("Environnement : %s", APP_ENV)
    for _line in format_startup_messages(APP_HOST, APP_PORT, APP_SSL_ENABLED):
        logger.info(_line)

    _server_sw = _os.environ.get("SERVER_SOFTWARE", "").lower()
    _web_concurrency = _os.environ.get("WEB_CONCURRENCY", "1")
    _multi_worker = (
        "gunicorn" in _server_sw
        or "uwsgi" in _server_sw
        or (_web_concurrency.isdigit() and int(_web_concurrency) > 1)
    )
    if _multi_worker:
        logger.warning(
            "AVERTISSEMENT — Forge utilise des sessions mémoire (backend mono-processus). "
            "Le multi-worker n'est pas supporté sans backend de session partagé. "
            "Voir ADR-002 : docs/adr/002-session-strategy.md"
        )

    from core.app.prod_warnings import emit_memory_store_warning_if_needed
    emit_memory_store_warning_if_needed(APP_ENV, forge.get("session_store"), logger=logger)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé — attente des requêtes en cours...")
        server.shutdown()   # attend la fin de tous les threads en vol
    finally:
        server.server_close()
        logger.info("Serveur arrêté.")
