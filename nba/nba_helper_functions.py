import re
from datetime import datetime
import pandas as pd
import pytz
import telegram
from selenium import webdriver
from telegram import Bot
import asyncio
from telegram.error import RetryAfter, BadRequest
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


async def send_telegram_message(bot_token, chat_id, message, parse_mode='HTML'):
    if not message.strip():
        return
    bot = Bot(token=bot_token)
    try:
        print("Attempting to send message...")
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        print("Message sent successfully!")
        await asyncio.sleep(10)
    except BadRequest as e:
        print(f"Failed to send message due to BadRequest: {e}")
    except RetryAfter as e:
        wait_time = e.retry_after
        print(f"Hit rate limit, retrying after {wait_time} seconds...")
        await asyncio.sleep(wait_time)
        await send_telegram_message(bot_token, chat_id, message, parse_mode)  # Retry sending the message
        await asyncio.sleep(10)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


async def send_long_message(bot_token, chat_id, long_message, parse_mode='HTML', delay=10):
    MAX_LENGTH = 4096
    parts = [long_message[i:i+MAX_LENGTH] for i in range(0, len(long_message), MAX_LENGTH)]
    print(f'Number of messages to send: {len(parts)}')
    total_wait_time = 0
    for part in parts:
        try:
            print('Sending message...')
            await send_telegram_message(bot_token, chat_id, part, parse_mode='HTML')
            await asyncio.sleep(delay)  # Respect Telegram's rate limits
        except telegram.error.RetryAfter as e:
            print(f"Rate limit exceeded, waiting for {e.retry_after} seconds.")
            wait_time = e.retry_after + 1
            total_wait_time += wait_time
            await asyncio.sleep(e.retry_after + 1)  # Wait a bit longer than recommended
            await send_telegram_message(bot_token, chat_id, part, parse_mode)  # Wait a bit between messages to avoid hitting rate limits
    return total_wait_time


def page_has_loaded(driver):
    return driver.execute_script("return document.readyState") == "complete"


def convert_percentage_to_decimal(percentage_string):
    if percentage_string is None:
        return None  # or return 0, if that makes more sense for your calculations
    matches = re.findall(r'(\d+)%', percentage_string)
    if matches:
        return float(matches[0]) / 100
    return None


def american_to_decimal(american_odds):
    if american_odds is None:
        return None  # or return a default decimal odds value, if preferred
    if american_odds > 0:
        return american_odds / 100 + 1
    else:
        return 100 / abs(american_odds) + 1


def decimal_to_american(decimal_odds):
    if decimal_odds >= 2.0:
        # For decimal odds of 2.0 or greater, the American odds are positive.
        return (decimal_odds - 1) * 100
    else:
        # For decimal odds less than 2.0, the American odds are negative.
        return -100 / (decimal_odds - 1)


def detect_reverse_line_movements(merged_df, bet_type, bookmakers):
    # Initialize a list to store profitable opportunities
    rlm_opportunities = []
    disagreement_opportunities = []
    # Detect reverse line movements and identify bookmakers that haven't moved their line or offer the best value
    for index, row in merged_df.iterrows():
        if row['money_pc_new'] is None:
            continue

        unchanged_bookmakers = []
        best_value = None
        best_value_bookmaker = None
        best_value_line = None
        best_disagreement_value = None
        best_disagreement_bookmaker = None
        best_disagreement_odds = None
        best_disagreement_line = None

        # Convert American odds to Decimal odds for comparison
        for bookmaker in bookmakers:
            old_line = row[f'{bookmaker}_{bet_type}_old']
            new_line = row[f'{bookmaker}_{bet_type}_new']
            money_pc = row['money_pc_new']
            bets_pc = row['bets_pc_new']
            new_odds = row[f'{bookmaker}_odds_new']
            opening_odds = row[f'Open_{bet_type}_new']
            disagreement = money_pc - bets_pc

            # Check for reverse line movement condition
            if (money_pc > 0.5 and new_line > old_line) or (money_pc < 0.5 and new_line < old_line):
                if old_line == new_line:
                    unchanged_bookmakers.append(bookmaker)
                if best_value is None or new_odds > best_value:
                    best_value = new_odds
                    best_value_bookmaker = bookmaker
                    best_value_line = new_line

            # Handle disagreements
            if disagreement > 0.4:  # Example threshold
                if best_disagreement_value is None or (new_odds > best_disagreement_odds
                                                       and disagreement > best_disagreement_value
                                                       and (abs(new_odds - opening_odds) <= 1)):
                    best_disagreement_value = disagreement
                    best_disagreement_bookmaker = bookmaker
                    best_disagreement_odds = new_odds
                    best_disagreement_line = new_line

            # After processing all bookmakers, append the best disagreement opportunity
            if best_disagreement_value:
                disagreement_opportunities.append({
                    'time': row['time_new'],
                    'team': row['team'],
                    'line': best_disagreement_line,
                    'bookmaker': best_disagreement_bookmaker,
                    'odds': round(best_disagreement_odds, 2),
                    'money_pc': money_pc * 100,
                    'bets_pc': bets_pc * 100,
                    'disagreement': round((best_disagreement_value * 100), 2),
                    'bet_type': bet_type,
                    'open': opening_odds
                })

            # Add RLM opportunities as before
            if unchanged_bookmakers and best_value_bookmaker:
                rlm_opportunities.append({
                    'time_new': row['time_new'],
                    'team': row['team'],
                    'best_value_bookmaker': best_value_bookmaker,
                    'best_value_odds': best_value,
                    'line': best_value_line,
                    'bet_type': bet_type,
                })

    return rlm_opportunities, disagreement_opportunities


def detect_and_accumulate(df, bet_type, bookmakers):
    rlm_opportunities, disagreement_opportunities = detect_reverse_line_movements(df, bet_type, bookmakers)
    NOTIFIED_MOVEMENTS_FILE = 'notified_movements.csv'

    try:
        notified_movements = pd.read_csv(NOTIFIED_MOVEMENTS_FILE)
        notified_movements = remove_past_events(notified_movements)
    except FileNotFoundError:
        notified_movements = pd.DataFrame(columns=['identifier', 'time'])

    all_messages = []
    for opportunity in rlm_opportunities:
        identifier = f"{opportunity['team']}_{opportunity['bet_type']}_{opportunity['line']}_{opportunity['best_value_bookmaker']}_rlm"
        time = opportunity['time_new']
        new_row = {'identifier': identifier, 'time': time}

        if identifier not in notified_movements['identifier'].values:
            subject = f"<b>Reverse Line Movement Detected for {opportunity['team']}</b>"
            message = f"""{subject}<br>
                    - Best value is with <b>{opportunity['best_value_bookmaker']}</b> offering odds <b>{opportunity['best_value_odds']}</b> on <b>{opportunity['bet_type']}</b> , line: <b>{opportunity['line']}</b>."""
            all_messages.append(message)
            new_row_df = pd.DataFrame([new_row])  # Convert the new row to a single-row DataFrame
            notified_movements = pd.concat([notified_movements, new_row_df], ignore_index=True)

    for opportunity in disagreement_opportunities:
        identifier = f"{opportunity['team']}_{opportunity['bet_type']}_{opportunity['line']}_{opportunity['bookmaker']}_dg"
        time = opportunity['time']
        new_row = {'identifier': identifier, 'time': time}

        if identifier not in notified_movements['identifier'].values:
            decision = "on" if opportunity['money_pc'] > 50 else "against"
            bet_message = f'Bet {decision} {opportunity["team"]} on {opportunity["bet_type"]}, line: {opportunity["line"]}'
            bet_line = opportunity["line"]
            bookmaker = opportunity['bookmaker']
            odds = opportunity['odds']
            american_odds = decimal_to_american(opportunity['odds'])
            money_pc = opportunity['money_pc']
            bets_pc = opportunity['bets_pc']
            disagreement = opportunity['disagreement']
            message = (f"{bet_message}\n"
                       f"- <b>Bookmaker</b>: {bookmaker}\n"
                       f"- <b>Odds</b>: {odds} (American: {round(american_odds)})\n"
                       f"- <b>Line</b>: {bet_line}\n"
                       f"- <b>Money Percentage</b>: {money_pc}%\n"
                       f"- <b>Betting Percentage</b>: {bets_pc}%\n"
                       f"- <b>Disagreement</b>: {disagreement}%\n")
            all_messages.append(message)
            new_row_df = pd.DataFrame([new_row])  # Convert the new row to a single-row DataFrame
            notified_movements = pd.concat([notified_movements, new_row_df], ignore_index=True)

    # Save the updated DataFrame to CSV
    notified_movements.to_csv(NOTIFIED_MOVEMENTS_FILE, index=False)

    return "\n\n".join(all_messages)


def initialize_webdriver():
    chrome_service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    chrome_options = Options()
    options = ["--disable-dev-shm-usage", "--headless", "window-size=1920x1080",
               "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36"]
    for option in options:
        chrome_options.add_argument(option)
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    return driver


def remove_past_events(df):
    if df.empty or 'time' not in df.columns:
        return df
    current_time = datetime.now(pytz.utc)
    # Convert 'time' column to datetime if it's not already
    if not pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = pd.to_datetime(df['time'])
    df = df[df['time'] > current_time]
    return df
