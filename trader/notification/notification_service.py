import requests


class NotificationService:
    def __init__(self, chat_id: str, token: str):
        self.chat_id = chat_id
        self.token = token

    def send_message(self, message: str) -> None:
        pass


class NullNotificationService(NotificationService):
    def __init__(self):
        pass

    def send_message(self, message: str) -> None:
        pass


class TelegramNotificationService(NotificationService):
    def __init__(self, chat_id: str, token: str):
        super().__init__(chat_id, token)
        self.url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, message: str) -> None:
        try:
            response = requests.post(
                self.url + "/sendMessage",
                data={"chat_id": self.chat_id, "text": message},
            )
            response.raise_for_status()
        except Exception as e:
            print("Erro ao enviar alerta Telegram:", e)
