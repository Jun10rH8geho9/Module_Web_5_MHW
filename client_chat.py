import asyncio
import logging
import websockets
import names
import aiofile
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK
from datetime import datetime, timedelta
import aiohttp

logging.basicConfig(level=logging.INFO)

class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        """
        Реєстрація клієнта.
        """
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} підключився')

    async def unregister(self, ws: WebSocketServerProtocol):
        """
        Відключення клієнта.
        """
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} відключився')

    async def send_to_clients(self, message: str):
        """
        Відправлення повідомлення всім клієнтам.
        """
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def ws_handler(self, ws: WebSocketServerProtocol):
        """
        Обробка WebSocket з'єднання.
        """
        await self.register(ws)
        try:
            await self.distribute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def distribute(self, ws: WebSocketServerProtocol):
        """
        Розсилка повідомлень між клієнтами.
        """
        async for message in ws:
            if message.startswith("exchange today"):
                await self.handle_exchange_command(ws)
            elif message.startswith("exchange lastday"):
                await self.handle_last_day_exchange_command(ws)
            else:
                await self.send_to_clients(f"{ws.name}: {message}")

    async def handle_exchange_command(self, ws: WebSocketServerProtocol):
        """
        Обробка запиту на поточний обмінний курс.
        """
        exchange_rate = await self.get_exchange_rate() # Отримання курсу за сьогодні
        await self.log_exchange_command("exchange today", exchange_rate)  
        await ws.send(f"Обмінний курс Приватбанку за сьогодні: {exchange_rate}")

    async def handle_last_day_exchange_command(self, ws: WebSocketServerProtocol):
        """
        Обробка запиту на отримання курсу за останні 10 днів.
        """
        exchange_rates = await self.get_last_days_exchange_rate(10)  # Отримання курсу за останні 10 днів
        await self.log_exchange_command("exchange lastday", exchange_rates) 
        await ws.send(f"Обмінні курси за останні Приватбанку за 10 днів:")
        for date, rate in exchange_rates.items():
            await ws.send(f"{date}: {rate}")

    async def get_exchange_rate(self):
        """
        Отримання поточного обмінного курсу.
        """
        url = "https://api.privatbank.ua/p24api/exchange_rates?date="
        today = datetime.now().date()
        currencies = ["EUR", "USD", "GBP"]  # Вибір потрібніх валют
        exchange_rate = ""

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url + today.strftime("%d.%m.%Y")) as response:
                    if response.status == 200:
                        data = await response.json()

                        if "exchangeRate" in data:
                            rates = {rate['currency']: rate for rate in data["exchangeRate"]}
                            for currency in currencies:
                                if currency in rates:
                                    rate = rates[currency]
                                    exchange_rate += f"{currency}: Sale - {rate['saleRateNB']}, Purchase - {rate['purchaseRateNB']}\n"
                                else:
                                    logging.error(f"Курс для {currency} не знайдено.")
                        else:
                            logging.error(f"Помилка при отриманні курсів обміну на {today.strftime('%d.%m.%Y')}")
            except aiohttp.ClientError as e:
                logging.error(f"Помилка під час HTTP-запиту: {e}")
                
        return exchange_rate

    async def get_last_days_exchange_rate(self, days):
        """
        Отримання обмінного курсу за останні n днів.
        """
        exchange_rates = {}
        url = "https://api.privatbank.ua/p24api/exchange_rates?date="

        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in range(days):
                date = datetime.now().date() - timedelta(days=i+1)
                task = self.get_exchange_rate_for_date(session, url, date)
                tasks.append(task)
            results = await asyncio.gather(*tasks)
            for date, rate in results:
                exchange_rates[date] = rate

        return exchange_rates

    async def get_exchange_rate_for_date(self, session, url, date):
        """
        Отримання обмінного курсу для конкретної дати.
        """
        exchange_rate = ""
        try:
            async with session.get(url + date.strftime("%d.%m.%Y")) as response:
                if response.status == 200:
                    data = await response.json()

                    if "exchangeRate" in data:
                        rates = {rate['currency']: rate for rate in data["exchangeRate"]}
                        rate = rates.get("USD", None)  # Отримання курсу USD
                        if rate:
                            exchange_rate += f"{date}: USD - Sale: {rate['saleRateNB']}, Purchase: {rate['purchaseRateNB']}\n"
                        else:
                            logging.error(f"Курс для USD на {date.strftime('%d.%m.%Y')} не знайдено.")
                    else:
                        logging.error(f"Помилка при отриманні курсів обміну на {date.strftime('%d.%m.%Y')}")
        except aiohttp.ClientError as e:
            logging.error(f"Помилка під час HTTP-запиту: {e}")

        return date, exchange_rate

    async def log_exchange_command(self, command: str, exchange_rate: str):
        """
        Логування обмінного курсу.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - {command} - {exchange_rate}\n"

        async with aiofile.async_open("exchange_log.txt", mode="a") as log_file:
            await log_file.write(log_entry)

async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, 'localhost', 8080):
        await asyncio.Future()  # Безкінечний цикл

if __name__ == '__main__':
    asyncio.run(main())