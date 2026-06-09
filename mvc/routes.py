from core.http.router import Router
from mvc.controllers.home_controller import HomeController

router = Router()

with router.group("", public=True) as pub:
    pub.add("GET", "/", HomeController.index, name="home-index")
