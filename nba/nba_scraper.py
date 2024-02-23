import pandas as pd
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import time
from selenium.common.exceptions import NoSuchElementException
from nba_helper_functions import page_has_loaded, initialize_webdriver
from nba.nba_points import extract_total_data
from nba.nba_spread import extract_spread_data


def scraper(BASE_URL, NBA, USERNAME, PASSWORD):
    driver = initialize_webdriver()
    wait = WebDriverWait(driver, 20)
    driver.get(BASE_URL + NBA)

    # Click the sign-in toggle button to reveal the sign-in options
    sign_in_toggle = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "body > header > div.page-social > span")))
    sign_in_toggle.click()

    # Click the sign-in button to navigate to the sign-in page
    sign_in_button = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#page-header\:menu\/user > li:nth-child(1) > a")))
    sign_in_button.click()

    # Wait until the sign-in fields are present
    wait.until(EC.presence_of_element_located((By.NAME, "username")))
    wait.until(EC.presence_of_element_located((By.NAME, "password")))

    # Accept cookies
    try:
        accept_cookies_button = driver.find_element(By.CSS_SELECTOR,
                                                    "body > footer > div:nth-child(6) > div > div > a.cookie-close.button")
        if accept_cookies_button:
            accept_cookies_button.click()
            time.sleep(1)  # Wait for the banner to disappear
    except NoSuchElementException:
        pass

    # Enter the email and password and submit the form
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.NAME, "password").submit()
    wait.until(EC.url_to_be("https://www.vegasinsider.com/"))

    # After redirection, go to nba odds page
    navigation_button = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#page-header\:menu > li:nth-child(6)")))
    ActionChains(driver).move_to_element(navigation_button).click().perform()

    # Get the table that contains the games
    wait.until(lambda d: page_has_loaded(d))
    table = driver.find_element(By.ID, "odds-table-spread--0")

    # Find all the 'td' elements that contain game links by using the class name for specificity
    game_link_elements = table.find_elements(By.CSS_SELECTOR, "td.game-links")

    game_urls = []

    # Iterate through each game link 'td' to extract the navigation urls
    for game_link_element in game_link_elements:
        # Find the "Matchup" link within each 'td' element
        matchup_link_element = game_link_element.find_element(By.CSS_SELECTOR,
                                                              "ul.nav > li.nav-item.buttons > a.button.matte.rounded")
        # Extract the 'href' attribute to get the URL
        url = matchup_link_element.get_attribute('href')
        # Ensure the URL is not None or empty before adding to the list
        if url:
            game_urls.append(url)

    # Go into each game and collect spread, total and money line odds.
    all_spread_data = []
    all_total_data = []
    bookmakers_spread = []
    bookmakers_total = []
    for url in game_urls:
        spread_data_result = extract_spread_data(driver, url)
        if spread_data_result:  # Check if result is not None
            current_spread_data, bookmakers_spread = spread_data_result
            all_spread_data.extend(current_spread_data)

        total_data_result = extract_total_data(driver, url)
        if total_data_result:  # Check if result is not None
            current_total_data, bookmakers_total = total_data_result
            all_total_data.extend(current_total_data)

    if all_spread_data:  # Checks if list is not empty
        nba_spread_df = pd.DataFrame(all_spread_data)
    else:
        nba_spread_df = pd.DataFrame()  # Create an empty DataFrame if no data

    if all_total_data:  # Checks if list is not empty
        nba_total_df = pd.DataFrame(all_total_data)
    else:
        nba_total_df = pd.DataFrame()

    driver.quit()

    return nba_spread_df, nba_total_df, bookmakers_spread, bookmakers_total
