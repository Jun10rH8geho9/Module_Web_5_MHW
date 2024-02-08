import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
import sys
import json

# Налаштування логування
logging.basicConfig(level=logging.INFO, filename="exchange_rates.log", filemode="w")

async def exchange_rates(currencies):
    url_base = "https://api.privatbank.ua/p24api/exchange_rates?date="
    today = datetime.now().date()
    date_limit = today - timedelta(days=10)
    exchange_data = []  # список для зберігання даних про курси обміну

    async with aiohttp.ClientSession() as session:
        while today > date_limit:
            url = url_base + today.strftime("%d.%m.%Y")
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()

                        if "exchangeRate" in data:
                            rates = {rate['currency']: rate for rate in data["exchangeRate"]}
                            rates_on_date = {currency: {"sale": rates[currency]['saleRateNB'], "purchase": rates[currency]['purchaseRateNB']} for currency in currencies if currency in rates}
                            exchange_data.append({today.strftime("%d.%m.%Y"): rates_on_date})
                        else:
                            logging.error(f"Помилка при отриманні курсів обміну на {today.strftime('%d.%m.%Y')}")
            except aiohttp.ClientError as e:
                logging.error(f"Помилка під час HTTP-запиту: {e}")
            
            today -= timedelta(days=1)

    return exchange_data

async def main():
    currencies = ["EUR", "USD", "GBP"]
    if len(sys.argv) > 1:
        currencies.extend(sys.argv[1:])
    exchange_data = await exchange_rates(currencies)

    with open('exchange_rates.json', 'w') as f:
        json.dump(exchange_data, f, ensure_ascii=False, indent=2)

    print("Виконання програми завершено. Натисніть Enter для виходу.")
    await asyncio.sleep(1)  # Зачекати одну секунду перед завершенням програми

if __name__ == "__main__":
    asyncio.run(main())
    input()  # Чекаємо на натискання клавіші Enter перед виходом