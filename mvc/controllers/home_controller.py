from core.http.request import Request
from core.http.response import Response
from core.mvc.controller.base_controller import BaseController


class HomeController(BaseController):

    @staticmethod
    def index(request: Request) -> Response:
        return BaseController.render("home/index.html", request=request)
