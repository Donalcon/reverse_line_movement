import pandas as pd
import asyncio
from nba_helper_functions import remove_past_events, detect_and_accumulate, send_long_message
from nba.nba_scraper import scraper
import os

# Access environment variables
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
USERNAME = os.environ['VI_USERNAME']
PASSWORD = os.environ['VI_PASSWORD']

BASE_URL = 'https://www.vegasinsider.com/'
NBA = 'nba/odds/las-vegas/'

# Define filenames for saving dataframes
SPREAD_DF_FILE = 'nba_spread_df.csv'
TOTAL_DF_FILE = 'nba_total_df.csv'


async def scheduled_job():
    # Load existing dataframes if they exist
    try:
        nba_spread_df = pd.read_csv(SPREAD_DF_FILE)
        nba_total_df = pd.read_csv(TOTAL_DF_FILE)
    except FileNotFoundError:
        print("Files not found, creating new dataframes...")
        nba_spread_df, nba_total_df, _, _ = scraper(BASE_URL, NBA, USERNAME, PASSWORD)
        nba_spread_df.to_csv(SPREAD_DF_FILE, index=False)
        nba_total_df.to_csv(TOTAL_DF_FILE, index=False)
        return

    # Call the scraper to collect the latest data
    new_spread_df, new_total_df, bookmakers_spread, bookmakers_total = scraper(BASE_URL, NBA, USERNAME, PASSWORD)
    #  if Open or Consensus in bookmakers_spread and bookmakers_total, drop them
    if 'Open' in bookmakers_spread:
        bookmakers_spread.remove('Open')
    if 'Consensus' in bookmakers_spread:
        bookmakers_spread.remove('Consensus')
    if 'Open' in bookmakers_total:
        bookmakers_total.remove('Open')
    if 'Consensus' in bookmakers_total:
        bookmakers_total.remove('Consensus')

    all_messages = []
    # Merge the new data with the existing dataframes
    if not nba_spread_df.empty:
        updated_spread_df = pd.merge(nba_spread_df, new_spread_df, on='team', how='outer', suffixes=('_old', '_new'))
        spread_messages = detect_and_accumulate(updated_spread_df, 'spread', bookmakers_spread)
        all_messages.append(spread_messages)

    if not nba_total_df.empty:
        updated_total_df = pd.merge(nba_total_df, new_total_df, on='team', how='outer', suffixes=('_old', '_new'))
        points_messages = detect_and_accumulate(updated_total_df, 'total', bookmakers_total)
        all_messages.append(points_messages)

    # Remove past events from updated dataframes
    new_spread_df = remove_past_events(new_spread_df)
    new_total_df = remove_past_events(new_total_df)

    # Update the initial dataframes with the new data for the next iteration
    nba_spread_df = new_spread_df
    nba_total_df = new_total_df

    # Join the messages with two newlines for separation
    message_to_send = '\n\n'.join(all_messages)
    # email the opportunities
    await send_long_message(BOT_TOKEN, CHAT_ID, message_to_send)

    # At the end, save the updated dataframes
    nba_spread_df.to_csv(SPREAD_DF_FILE, index=False)
    nba_total_df.to_csv(TOTAL_DF_FILE, index=False)


# Execute the scheduler in a loop
if __name__ == "__main__":
    asyncio.run(scheduled_job())
