from datetime import datetime

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import time
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException
from nba_helper_functions import page_has_loaded, convert_percentage_to_decimal, american_to_decimal


def extract_moneyline_data(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 20)
    wait.until(lambda d: page_has_loaded(d))

    moneyline_toggle = driver.find_element(By.CSS_SELECTOR, "#odds-component > div > ul:nth-child(2) > li:nth-child(3)")
    moneyline_toggle.click()

    time_element = driver.find_element(By.CSS_SELECTOR,
                                       'body > div.event-header.module > div:nth-child(1) > div > div.event-header-score > div > span > span:nth-child(2)')

    # Retrieve the 'data-value' attribute, which contains the datetime in ISO 8601 format
    iso_datetime_str = time_element.get_attribute('data-value')
    # Convert the ISO 8601 datetime string to a Python datetime object
    game_time = datetime.fromisoformat(iso_datetime_str.replace('Z', '+00:00'))

    # Extract bookmakers
    header = driver.find_element(By.CSS_SELECTOR, "#odds-table-moneyline--0 tr:first-child")
    bookmakers_elements = header.find_elements(By.CSS_SELECTOR, "th.book-logo img")
    bookmakers = [el.get_attribute('alt') for el in bookmakers_elements if el.get_attribute('alt')]

    # Extract team 1 information
    team1_element = driver.find_element(By.CSS_SELECTOR,
                                        "#odds-table-moneyline--0 > tr.divided > td.game-team > div > img")
    team1 = team1_element.get_attribute('alt')
    # Find the game odds row for team 1
    moneyline_row_team1 = driver.find_element(By.CSS_SELECTOR, "#odds-table-moneyline--0 tr.divided")
    # Extract total values and odds for team 1
    moneyline_team1 = [element.text or 'NaN' for element in
                       moneyline_row_team1.find_elements(By.CSS_SELECTOR, ".game-odds .data-moneyline")]
    moneyline_team1 = [None if val == 'N/A' else float(val) for val in moneyline_team1]
    moneyline_team1 = [float(val.replace('even', '-100')) if 'even' in val else float(val) for val in moneyline_team1]
    moneyline_team1 = [float(val) for val in moneyline_team1]
    odds_team1 = [american_to_decimal(val) for val in moneyline_team1]

    # Extract team 2 information
    team2_element = driver.find_element(By.CSS_SELECTOR,
                                        "#odds-table-moneyline--0 > tr.footer > td.game-team > div > img")
    team2 = team2_element.get_attribute('alt')
    moneyline_row_team2 = driver.find_element(By.CSS_SELECTOR, "#odds-table-moneyline--0 tr.footer")
    moneyline_team2 = [element.text or 'NaN' for element in
                       moneyline_row_team2.find_elements(By.CSS_SELECTOR, ".game-odds .data-moneyline")]
    moneyline_team2 = [None if val == 'N/A' else float(val) for val in moneyline_team2]
    moneyline_team2 = [float(val.replace('even', '-100')) if 'even' in val else float(val) for val in moneyline_team2]
    moneyline_team2 = [float(val) for val in moneyline_team2]
    odds_team2 = [american_to_decimal(val) for val in moneyline_team2]

    # Initialize dictionaries to hold the data for each team
    team1_data = {'time': game_time, 'team': team1}
    team2_data = {'time': game_time, 'team': team2}

    for i, bookmaker in enumerate(bookmakers):
        team1_data[f'{bookmaker}'] = odds_team1[i]
        team2_data[f'{bookmaker}'] = odds_team2[i]

    # Wait for the trends component to load and then extract the spread bets percentages
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#trends-component > div > div > table")))
    moneyline_bets_pc_team1 = driver.find_element(By.CSS_SELECTOR,
                                                  "#trends-table-bets--0 > tr:nth-child(2) > td:nth-child(4)").text
    moneyline_bets_pc_team2 = driver.find_element(By.CSS_SELECTOR,
                                                  "#trends-table-bets--0 > tr:nth-child(3) > td:nth-child(4)").text

    # Click the button to switch to spread money percentage view
    money_pc_button = driver.find_element(By.CSS_SELECTOR, "#trends-component > div > ul > li:nth-child(2)")
    attempt = 0
    max_attempts = 5
    while attempt < max_attempts:
        try:
            money_pc_button.click()
            break
        except ElementClickInterceptedException:
            time.sleep(1)  # Wait for a second before retrying
            attempt += 1

    # Wait for the money percentage table to load and then extract the spread money percentages
    try:
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#trends-table-money--0 > tr:nth-child(2) > td:nth-child(4)")))
        moneyline_money_pc_team1 = driver.find_element(By.CSS_SELECTOR,
                                                       "#trends-table-money--0 > tr:nth-child(2) > td:nth-child(4)").text
        moneyline_money_pc_team2 = driver.find_element(By.CSS_SELECTOR,
                                                       "#trends-table-money--0 > tr:nth-child(3) > td:nth-child(4)").text
    except TimeoutException:
        print(f"No money percentage available.")
        moneyline_money_pc_team1 = None
        moneyline_money_pc_team2 = None

    # Assuming you have a dictionary for the current game data already set up (e.g., `current_game_data`)
    team1_data['bets_pc'] = convert_percentage_to_decimal(moneyline_bets_pc_team1)
    team2_data['bets_pc'] = convert_percentage_to_decimal(moneyline_bets_pc_team2)
    team1_data['money_pc'] = convert_percentage_to_decimal(moneyline_money_pc_team1)
    team2_data['money_pc'] = convert_percentage_to_decimal(moneyline_money_pc_team2)

    # # Convert to numeric
    # moneyline_columns = [f'{book}_moneyline' for book in bookmakers]
    # percentage_columns = ['bets_pc', 'money_pc']
    # # List of all columns that should be converted to numeric
    # columns_to_convert = moneyline_columns + percentage_columns
    # # Convert the specified columns to numeric, coerce errors to NaN
    # for col in columns_to_convert:
    #     team1_data[col] = pd.to_numeric(team1_data[col], errors='coerce')
    #     team2_data[col] = pd.to_numeric(team2_data[col], errors='coerce')

    return team1_data, team2_data, bookmakers
