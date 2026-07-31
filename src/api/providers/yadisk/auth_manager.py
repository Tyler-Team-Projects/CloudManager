import keyring
from core.constants import App, Settings, Timeouts, Providers, Views, Urls, Auth

class AuthManager:
    @staticmethod
    def save_token(token):
        keyring.set_password(App.NAME, Auth.TOKEN_KEY, token)

    @staticmethod
    def load_token():
        return keyring.get_password(App.NAME, Auth.TOKEN_KEY)
