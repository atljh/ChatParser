import os
import sys
import json
import subprocess
import requests
from pathlib import Path
from typing import List, Generator
from basethon.base_thon import BaseThon
from basethon.base_session import BaseSession
from basethon.json_converter import JsonConverter
from telethon import functions
from telethon.errors import FloodWaitError
from console import console

import asyncio


class TelegramSearch(BaseThon):
    def __init__(self, item: str, json_data: dict):
        if not item:
            raise ValueError("Переданный параметр 'item' пустой или None.")
        if not isinstance(json_data, dict):
            raise ValueError("Переданный параметр 'json_data' должен быть словарем.")
        super().__init__(item, json_data)

        self.settings = self._load_settings()
        self.output_file = Path("output.txt")
        self.old_chats = set()

    @staticmethod
    def _load_settings() -> dict:
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("Файл settings.json не найден!")
        except json.JSONDecodeError:
            raise ValueError("Ошибка чтения settings.json! Убедитесь, что файл содержит корректный JSON.")

    @staticmethod
    def _load_file(filename: str) -> List[str]:
        file_path = Path(filename)
        if not file_path.exists():
            raise FileNotFoundError(f"Файл {filename} не найден.")
        with file_path.open("r", encoding="utf-8") as f:
            data = [line.strip() for line in f if line.strip()]
            if not data:
                raise ValueError(f"Файл {filename} пуст.")
            return data

    async def _search_chats(self, names: List[str], endings: List[str]):
        self.output_file.unlink(missing_ok=True)

        with self.output_file.open("w", encoding="utf-8") as file:
            for title in names:
                for end in endings:
                    name = (title + end).lower()
                    console.log(f"Поиск чатов с именем: {name}", style="blue")
                    try:
                        request = await self.client(functions.contacts.SearchRequest(q=name, limit=10))
                    except FloodWaitError as e:
                        console.log(f"FloodWaitError: Ожидание {e.seconds} секунд.", style="yellow")
                        await asyncio.sleep(e.seconds)
                        continue
                    except Exception as e:
                        console.log(f"Произошла ошибка при запросе: {e}", style="red")
                        continue

                    for channel in request.chats:
                        if channel.megagroup:
                            username = (channel.username or "").lower()
                            if username and username not in self.old_chats:
                                self.old_chats.add(username)
                                file.write(f"t.me/{channel.username}\n")
                                console.log(f"Добавлен чат: t.me/{channel.username}", style="green")

    def __get_sessions_and_users(self) -> Generator:
        session = BaseSession()
        for item, json_file, json_data in session.find_sessions():
            yield item, json_file, json_data

    async def main(self):
        try:
            names = self._load_file("names.txt")
            endings = self._load_file("endings.txt")
        except (FileNotFoundError, ValueError) as e:
            console.log(f"Ошибка при загрузке файлов: {e}", style="red")
            return False
    
        for item, json_file, json_data in self.__get_sessions_and_users():
            r = await self.check()
            print(r)
            if "OK" not in r:
                console.log("Аккаунт забанен", style="red")
            await self._search_chats(names, endings)
        return True


def set_settings(data):
    with open("settings.json", "w") as f:
        f.write(json.dumps(data))


def register_user(settings):
    print("Связываемся с сервером...")
    current_machine_id = (
        str(subprocess.check_output("wmic csproduct get uuid"), "utf-8")
        .split("\n")[1]
        .strip()
    )

    admin_username = settings.get("ADMIN_USERNAME")
    script_name = settings.get("SCRIPTNAME")
    BASE_API_URL = settings.get("BASE_API_URL", "http://142.93.105.98:8000")

    db_id = requests.get(
        f"{BASE_API_URL}/api/{script_name}/{current_machine_id}/{admin_username}"
    )
    db_id = db_id.json()
    if db_id.get("message"):
        print("Неправильный логин")
        sys.exit()
    file_key = settings.get("ACCESS_KEY")
    print(f"Ваш ID в системе: {db_id['id']}")
    if file_key:
        key = file_key
    else:
        key = input("Введите ваш ключ доступа: ")
    while True:
        is_correct = requests.post(
            f"{BASE_API_URL}/api/{script_name}/check/",
            data={"pk": current_machine_id, "key": key},
        ).json()["message"]
        if is_correct:
            print("Вход успешно выполнен!")
            settings["ACCESS_KEY"] = key
            set_settings(settings)
            return
        else:
            print("Неправильный ключ!")
            key = input("Введите ваш ключ доступа: ")

def get_settings():
    try:
        with open("settings.json", "r") as f:
            return json.loads(f.read())
    except:
        return {}


if __name__ == "__main__":
    settings = get_settings()  # Инициализация настроек
    # register_user(settings)  # Передача настроек в функцию

    item = "session"
    sessions_count = JsonConverter().main()
    if not sessions_count:
        console.log("Нет аккаунтов в папке с сессиями!", style="yellow")
    try:
        with open("session.json", "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except FileNotFoundError:
        console.log("Файл session.json не найден!", style="red")
        json_data = {}
    except json.JSONDecodeError:
        console.log("Ошибка чтения session.json! Убедитесь, что файл содержит корректный JSON.", style="red")
        json_data = {}

    try:
        telegram_search = TelegramSearch(item, json_data)
        asyncio.run(telegram_search.main())
    except Exception as e:
        console.log(f"Ошибка запуска: {e}", style="red")
