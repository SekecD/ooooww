import asyncio
import re
from abc import ABC, abstractmethod
from typing import Optional

import pyzmail
from imapclient import IMAPClient
from telegram import Bot


class DefaultParser(ABC):
    @abstractmethod
    def new(self, raw) -> Optional[str]:
        pass


class SteamParser(DefaultParser):
    def new(self, raw):
        message = pyzmail.PyzMessage.factory(raw)
        from_email = message.get_addresses('from')[0][1]
        to_email = message.get_addresses('to')[0][1]
        if from_email != "noreply@steampowered.com":
            return None
        body = ""
        if message.text_part:
            body = message.text_part.get_payload().decode(message.text_part.charset)

        match = re.search(r'Код доступа\s+([A-Z0-9]{5})', body)
        if match:
            code = match.group(1)
            return f"На почту {to_email} пришел код: {code}"
        return None


class MailListener(object):
    def __init__(self, queue_in, queue_out, token, parser=SteamParser):
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.token = token
        self.parser = parser()

        self._listeners = {}

    def listen(self):
        asyncio.run(self.alisten())

    async def alisten(self):
        while True:
            if self.queue_in.empty():
                await asyncio.sleep(0.1)
                continue

            msg = self.queue_in.get()

            if msg["type"] == "new":
                self._listeners[msg["chat_id"]] = self.Listener(self, msg['chat_id'])
            elif msg['type'] == "info":
                listener = self._listeners.get(msg['chat_id'])
                info = []

                for task in listener.tasks:
                    info.append({
                        "email": task['email'],
                        "password": task['password'],
                        "imap": task['imap'],
                    })
                self.queue_out.put(info)
            elif msg['type'] == "append":
                listener = self._listeners.get(msg['chat_id'])
                await listener.add_task(**msg['kwargs'])
            elif msg['type'] == "remove":
                listener = self._listeners.get(msg['chat_id'])
                await listener.remove_task(msg['email'])
            elif msg['type'] == "close":
                listener = self._listeners.get(msg['chat_id'])
                await listener.close()
                del self._listeners[msg['chat_id']]

    def __call__(self, chat_id, msg):
        resp = self.parser.new(msg)
        if resp:
            asyncio.run(self.__call(chat_id, resp))

    async def __call(self, chat_id, msg):
        bot = Bot(token=self.token)
        await bot.send_message(chat_id=chat_id, text=msg)

    class Listener:
        def __init__(self, father, chat_id):
            self.father = father
            self.chat_id = chat_id

            self.tasks = []

        def __call__(self, msg):
            self.father(self.chat_id, msg)

        async def add_task(self, email, password, imap):
            stop_event = asyncio.Event()
            task = asyncio.create_task(listen_mailbox(
                {"email": email, "password": password, "imap": imap},
                self,
                stop_event
            ))

            self.tasks.append({
                "email": email,
                "password": password,
                "imap": imap,
                "task": task,
                'stop_event': stop_event
            })

        async def remove_task(self, email):
            tasks = list(filter(lambda t: t["email"] == email, self.tasks))
            if len(tasks) == 1:
                for task in tasks:
                    task['stop_event'].set()
                    self.tasks.remove(task)

        async def close(self):
            for task in self.tasks:
                await self.remove_task(task['email'])


async def listen_mailbox(account, instance, event):
    def sync_listen():
        with IMAPClient(account["imap"], ssl=True) as client:
            client.login(account["email"], account["password"])
            client.select_folder("INBOX")
            existing_uids = client.search(['ALL'])
            last_seen_uid = max(existing_uids) if existing_uids else 0

            while True:
                try:
                    client.idle()
                    responses = client.idle_check(timeout=60 * 29)
                    if responses:
                        for response in responses:
                            if response[1] == b'EXISTS':
                                new_uids = client.search(['UID', f'{last_seen_uid + 1}:*'])
                                for uid in new_uids:
                                    data = client.fetch([uid], ['INTERNALDATE', 'RFC822'])[uid]
                                    raw = data[b'RFC822']
                                    instance(raw)
                                    last_seen_uid = max(last_seen_uid, uid)
                finally:
                    try:
                        client.idle_done()
                    except:
                        pass

    await asyncio.to_thread(sync_listen)
