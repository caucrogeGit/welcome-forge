from core.http.router import Router
from mvc.controllers.home_controller import HomeController
from mvc.controllers.welcome_controller import WelcomeController

router = Router()

with router.group("", public=True) as public:
    public.add("GET", "/", HomeController.index, name="home-index")
    public.add("GET", "/welcome", WelcomeController.index, name="welcome-index")
    public.add("GET", "/welcome/hello", WelcomeController.hello, name="welcome-hello")
    public.add("GET", "/welcome/html", WelcomeController.html, name="welcome-html")
    public.add("GET", "/welcome/article/{id}", WelcomeController.article, name="welcome-article")
    public.add("GET", "/welcome/debug", WelcomeController.debug, name="welcome-debug")
    public.add("GET", "/welcome/json", WelcomeController.json, name="welcome-json")
    public.add("GET", "/welcome/csrf", WelcomeController.csrf, name="welcome-csrf")
  
