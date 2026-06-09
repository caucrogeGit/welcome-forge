# mvc/helpers/session.py
"""Façade de confort pour la session non-auth (helper applicatif).

Namespace de méthodes statiques : ne s'instancie pas.
La session vit dans le store, repérée par un identifiant.
"""

from core.http.request import Request
from core.security.session import get_session_id as _get_id
from core.sessions import get_session_store as _store


class Session:
    def __new__(cls, *args, **kwargs):
        raise TypeError("Session ne s'instancie pas : namespace de méthodes statiques.")

    @staticmethod
    def new() -> str:
        return _store().create()

    @staticmethod
    def current_id(request: Request) -> str | None:
        return _get_id(request)

    @staticmethod
    def get(session_id: str) -> dict | None:
        return _store().get(session_id)

    @staticmethod
    def set(session_id: str, values: dict) -> None:
        _store().set(session_id, values)   # merge, sans écraser csrf/flash
