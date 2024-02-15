import pandas as pd
import schedule
import time
import asyncio
from selenium.common import TimeoutException
from nba_helper_functions import remove_past_events, detect_and_accumulate, send_notifications
from nba.nba_scraper import scraper

# Set your login credentials for VegasInsider
USERNAME = VI_USERNAME
PASSWORD = VI_PASSWORD
BASE_URL = 'https://www.vegasinsider.com/'
NBA = 'nba/odds/las-vegas/'

nba_spread_df, nba_total_df, _, _ = scraper(BASE_URL, NBA, USERNAME, PASSWORD)


async def scheduled_job():
    global nba_spread_df, nba_total_df, iterations, notified_movements

    chat_id = TELEGRAM_CHAT_ID
    bot_token = TELEGRAM_BOT_TOKEN

    max_retries = 5  # Maximum number of retries
    retry_delay = 5  # Seconds to wait between retries
    attempt = 0

    while attempt < max_retries:
        try:
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
            send_notifications(bot_token, chat_id, message_to_send)
            break
        except TimeoutException as e:
            print(f"TimeoutException encountered on attempt {attempt + 1}: {e}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)  # Wait before retrying
            attempt += 1
        except Exception as e:
            # Handle other exceptions you expect might occur
            print(f"An unexpected error occurred: {e}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            attempt += 1

        if attempt == max_retries:
            print(f"Failed to update after {max_retries} attempts.")


async def main():
    iterations = 0
    while True:
        print(f"Updating, iteration: {iterations} ...")
        await scheduled_job()  # Run the scheduled job
        await asyncio.sleep(60)  # Wait for 60 seconds or however long you want before running the job again
        iterations += 1


# Execute the scheduler in a loop
if __name__ == "__main__":
    asyncio.run(main())