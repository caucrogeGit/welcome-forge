# mvc/helpers/cookies.py
"""Façade de confort pour les cookies (helper applicatif).

Namespace de méthodes statiques : ne s'instancie pas.
Pour le cookie de SESSION (durci __Host-), utilisez plutôt le helper session
ou core.security.cookies, qui en garantit la politique de sécurité.
"""

from core.http.request import Request
from core.http.response import Response


class Cookies:
    def __new__(cls, *args, **kwargs):
        raise TypeError("Cookies ne s'instancie pas : namespace de méthodes statiques.")

    @staticmethod
    def get(request: Request, name: str, default: str | None = None) -> str | None:
        for part in request.headers.get("Cookie", "").split(";"):
            part = part.strip()
            if part.startswith(name + "="):
                return part[len(name) + 1:]
        return default

    @staticmethod
    def all(request: Request) -> dict[str, str]:
        jar: dict[str, str] = {}
        for part in request.headers.get("Cookie", "").split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                jar[k.strip()] = v.strip()
        return jar

    @staticmethod
    def set(response: Response, name: str, value: str, *, max_age: int | None = None,
            path: str = "/", secure: bool = True, http_only: bool = True,
            same_site: str = "Strict") -> None:
        parts = [f"{name}={value}", f"Path={path}"]
        if max_age is not None:
            parts.append(f"Max-Age={int(max_age)}")
        if http_only:
            parts.append("HttpOnly")
        if secure:
            parts.append("Secure")
        if same_site:
            parts.append(f"SameSite={same_site}")
        response.headers["Set-Cookie"] = "; ".join(parts)

    @staticmethod
    def clear(response: Response, name: str, *, path: str = "/") -> None:
        Cookies.set(response, name, "", max_age=0, path=path)

