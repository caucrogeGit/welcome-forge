# Contrôleur de démonstration Forge.
# Regroupe des actions « vitrine » illustrant les différentes façons de
# produire une réponse HTTP avec Forge. Chaque méthode publique est branchée
# sur une route dans mvc/routes.py.

from core.http import Response
from core.http.request import Request
from core.mvc.controller import BaseController
from core.security.cookies import set_session_cookie
from core.security.session import get_session, get_session_id
from core.sessions.manager import get_session_store


# Actions de démonstration exposées sous le préfixe /welcome.
class WelcomeController(BaseController):

    # Réponse texte minimale (route GET /welcome).
    @staticmethod
    def index(request: Request) -> Response:
        return Response.text("Bonjour, Forge")

    # Salutation paramétrée par la query string ?name= (route GET /welcome/hello).
    @staticmethod
    def hello(request: Request) -> Response:
        name = request.query("name", default="Forge")
        return Response.text(f"Bonjour, {name}")

    # Rend un template HTML (route GET /welcome/html).
    @staticmethod
    def html(request: Request) -> Response:
        return BaseController.render("welcome/first.html")

    # Écho du segment d'URL {id} (route GET /welcome/article/{id}).
    @staticmethod
    def article(request: Request) -> Response:
        article_id = request.route("id", default="unknown")
        return Response.text(f"Article id : {article_id}")

    # Affiche les données de la requête à des fins de debug (route GET /welcome/debug).
    @staticmethod
    def debug(request: Request) -> Response:
        return Response.debug(request.data)

    # Réponse JSON (route GET /welcome/json).
    @staticmethod
    def json(request: Request) -> Response:
        data = {
            "message": "Hello, Forge",
            "status": "success"
        }
        return Response.json(data)

    # Récupère ou crée la session de l'appelant et renvoie (session_id, csrf_token). Helper interne, non routé.
    @staticmethod
    def _start_session(request: Request):
        session_id = get_session_id(request)
        session = get_session(session_id) if session_id else None
        if session is None:
            session_id = get_session_store().create()
            session = get_session(session_id)
        return session_id, session["csrf_token"]

    # Rend un formulaire protégé par jeton CSRF et pose le cookie de session (route GET /welcome/csrf).
    @staticmethod
    def csrf(request: Request) -> Response:
        session_id, csrf_token = WelcomeController._start_session(request)
        response = BaseController.render(
            "welcome/csrf.html",
            request=request,
            context={"csrf_token": csrf_token},
        )
        set_session_cookie(response, session_id)
        return response
