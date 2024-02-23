from datetime import datetime

from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from nba_helper_functions import page_has_loaded, convert_percentage_to_decimal, american_to_decimal


def extract_spread_data(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 60)
    wait.until(lambda d: page_has_loaded(d))

    # Time element, also a de-facto check for game status
    try:
        time_element = driver.find_element(By.CSS_SELECTOR,
                                           'body > div.event-header.module > div:nth-child(1) > div > div.event-header-score > div > span > span:nth-child(2)')
        # Retrieve the 'data-value' attribute, which contains the datetime in ISO 8601 format
        iso_datetime_str = time_element.get_attribute('data-value')
    except NoSuchElementException:
        print("Time element not found, indicating the game may be over. Skipping...")
        return None  # Gracefully exit the function if the game time element is not found

    # If iso_datetime_str is None, it indicates the game is over. Exit the function gracefully.
    if not iso_datetime_str:
        print("Game datetime not available, indicating the game may be over. Skipping...")
        return None

    # Proceed with converting the ISO 8601 datetime string to a Python datetime object
    game_time = datetime.fromisoformat(iso_datetime_str.replace('Z', '+00:00'))

    # Extract bookmakers
    header = driver.find_element(By.CSS_SELECTOR, "#odds-table-spread--0 tr:first-child")
    bookmakers_elements = header.find_elements(By.CSS_SELECTOR, "th.book-logo img")
    bookmakers = [el.get_attribute('alt') for el in bookmakers_elements if el.get_attribute('alt')]

    # Initialize list to store data for both teams
    game_data = []

    # CSS selectors to dynamically target the rows for both teams
    row_selectors = ["tr.divided", "tr.footer"]

    # Process data for each team
    for i in range(2):  # Loop through the two team rows
        # Extract team name using the image alt attribute
        team_img_selector = f"#odds-table-spread--0 > {row_selectors[i]} > td.game-team > div > img"
        team_img_element = driver.find_element(By.CSS_SELECTOR, team_img_selector)
        team_name = team_img_element.get_attribute('alt')

        # Extract spreads and odds
        team_element = driver.find_element(By.CSS_SELECTOR, f"#odds-table-spread--0 > {row_selectors[i]}")
        spreads = [el.text or 'NaN' for el in team_element.find_elements(By.CSS_SELECTOR, ".game-odds .data-value")]
        odds = [el.text or 'NaN' for el in team_element.find_elements(By.CSS_SELECTOR, ".game-odds .data-odds")]

        # cleaning
        cleaned_odds = []
        cleaned_bookmakers = []
        cleaned_spreads = []
        for val, spread, bookmaker in zip(odds, spreads, bookmakers):
            if val not in ['N/A', 'PK'] and spread not in ['N/A', 'PK']:
                val = float(val.replace('even', '-100'))
                val = american_to_decimal(val)
                cleaned_odds.append(val)
                cleaned_spreads.append(float(spread))
                cleaned_bookmakers.append(bookmaker)
        odds = cleaned_odds
        bookmakers = cleaned_bookmakers
        spreads = cleaned_spreads

        # Extract bets percentage
        bets_pc_selector = f"#trends-table-bets--0 > tr:nth-child({i + 2}) > td:nth-child(2) > div"
        bets_pc_element = driver.find_element(By.CSS_SELECTOR, bets_pc_selector)
        bets_pc = bets_pc_element.text

        # Switch to spread money percentage view
        money_pc_button = driver.find_element(By.CSS_SELECTOR, "#trends-component > div > ul > li:nth-child(2) > span")
        money_pc_button.click()
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "#trends-table-money--0 > tr:nth-child(2) > td:nth-child(2)")))

        # Extract money percentage with updated selectors
        money_pc_selector = f"#trends-table-money--0 > tr:nth-child({i + 2}) > td:nth-child(2)"
        try:
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, money_pc_selector)))
            money_pc_element = driver.find_element(By.CSS_SELECTOR, money_pc_selector)
            money_pc = money_pc_element.text
        except TimeoutException:
            print(f"No money percentage available in spread values, for {team_name}")
            money_pc = None

        # Create dictionary for current team
        team_data = {
            'time': game_time,
            'team': team_name,
            'bets_pc': convert_percentage_to_decimal(bets_pc),
            'money_pc': convert_percentage_to_decimal(money_pc)
        }
        # Add totals and odds for each bookmaker
        for j, bookmaker in enumerate(bookmakers):
            team_data[f'{bookmaker}_spread'] = spreads[j]
            team_data[f'{bookmaker}_odds'] = odds[j]

        # Append team data to game data list
        game_data.append(team_data)

    return game_data, bookmakers
