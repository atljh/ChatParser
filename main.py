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
from telethon import TelegramClient, functions, sync
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
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = f.read().splitlines()
                if not data:
                    raise ValueError(f"Файл {filename} пуст.")
                return data
        except FileNotFoundError:
            raise FileNotFoundError(f"Файл {filename} не найден.")
        except Exception as e:
            raise e


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
            if "OK" not in r:
                console.log("Аккаунт забанен", style="red")
                return
            await self._search_chats(names, endings)
        return True


def set_settings(data):
    with open("settings.json", "w") as f:
        f.write(json.dumps(data))


def register_user(settings):
    console.log("Связываемся с сервером...")
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
        console.log("Неправильный логин")
        sys.exit()
    file_key = settings.get("ACCESS_KEY")
    console.log(f"Ваш ID в системе: {db_id['id']}")
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
            console.log("Вход успешно выполнен!")
            settings["ACCESS_KEY"] = key
            set_settings(settings)
            return
        else:
            console.log("Неправильный ключ!")
            key = input("Введите ваш ключ доступа: ")

def get_settings():
    try:
        with open("settings.json", "r") as f:
            return json.loads(f.read())
    except:
        return {}
    
def load_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = f.read().splitlines()
            if not data:
                raise ValueError(f"Файл {filename} пуст.")
            return data
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл {filename} не найден.")
    except Exception as e:
        raise e


def main(settings):
    try:
        if not os.path.exists("names.txt") or not os.path.exists("endings.txt"):
            console.log("Файлы names.txt и endings.txt не найдены.")
            return
        try:
            names = load_file("names.txt")
            endings = load_file("endings.txt")
        except ValueError:
            console.log("Вы не заполнили или забыли сохранить файлы names и endings, я не могу начать парсинг без этого.")
            return

        client = TelegramClient("getchats", settings["API_ID"], settings["API_HASH"])
        client.start()

        old = []
        with open("output.txt", "w", encoding="utf-8") as file:
            console.log("Запуск скрипта...")
            for title in names:
                for end in endings:
                    name = title + end
                    console.log("Подбираются чаты, найденные по имени: ", name)
                    name = name.lower()
                    try:
                        request = client(functions.contacts.SearchRequest(q=name, limit=10))
                    except Exception as e:
                        if "A wait of" in str(e):
                            wait_time = int("".join(filter(str.isdigit, str(e))))
                            console.log(f"Ваш аккаунт ушел в мут на {wait_time} секунд.")
                            console.log("Удалите файл session и запустите скрипт заново, используя другой аккаунт, или дождитесь конца мута.")
                            return
                        else:
                            raise e
                    for channel in request.chats:
                        if channel.megagroup:
                            username = (
                                channel.username.lower() if channel.username is not None else ""
                            )
                            if username not in old:
                                if channel.title not in old:
                                    console.log(f"Найден чат: t.me/{channel.username}")
                                    file.write(f"t.me/{channel.username}\n")
                                    old.append(channel.username)
                                    console.log("Найден чат с подобранным именем: ", channel.title)
        console.log("Скрипт завершил свою работу...")

    except Exception as e:
        console.log(f"Произошла ошибка: {e}")
    finally:
        input("Для завершения работы скрипта нажмите Enter.")



def _main():
    settings = get_settings()
    register_user(settings)
    base_session = Path('getchats.session')
    basethon_session = Path('session.session')
    if not base_session.exists() and not basethon_session.exists()\
          or base_session.exists() and not basethon_session.exists():
        console.log(f"Файл getchats.session или session.session не найдены.", style='yellow')
        main(settings)
        return
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
        telegram_search = TelegramSearch('session', json_data)
        asyncio.run(telegram_search.main())
    except Exception as e:
        console.log(f"Ошибка запуска: {e}", style="red")


if __name__ == "__main__":
    _main()