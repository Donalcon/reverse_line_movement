import os
from telegram import Bot
from telegram.error import BadRequest, RetryAfter
import asyncio
import telegram


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


async def main():
    messages_file = 'messages.txt'
    BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

    if os.path.exists(messages_file) and os.path.getsize(messages_file) > 0:
        with open(messages_file, 'r') as file:
            message_to_send = file.read()
            if message_to_send.strip():
                # Use the asynchronous function for sending long messages
                await send_long_message(BOT_TOKEN, CHAT_ID, message_to_send)
                # Clear the file content after sending the message
                open(messages_file, 'w').close()
            else:
                print("The message file is empty, no message sent.")
    else:
        print(f"{messages_file} does not exist or is empty, no message to send.")

if __name__ == "__main__":
    asyncio.run(main())
