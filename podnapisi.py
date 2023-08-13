import os
import io
import csv
import zipfile
import requests
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Constants
BASE_URL = "https://www.podnapisi.net"
LANGUAGE = "hi"
USER_AGENT_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

# Set up logging
logging.basicConfig(level=logging.INFO)

def setup_driver():
    options = Options()
    
    # Common settings
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--ignore-ssl-errors=yes")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument('--headless')

    platform = os.sys.platform
    if platform == "win32":
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument(f"user-agent={USER_AGENT_WIN}")
    elif platform.startswith("linux"):
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

    return webdriver.Chrome(options=options)

def get_csrf_token(driver):
    return driver.execute_script(
        'return document.querySelector(\'meta[name="csrf-token"]\').getAttribute("content");'
    )

def set_language_filter(driver, csrf_token):
    base_script = """
    fetch("{url}", {{
        headers: {{
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-csrftoken": "{csrf_token}",
            "x-requested-with": "XMLHttpRequest"
        }},
        body: "{body}",
        method: "POST",
        credentials: "include"
    }});
    """
    
    remove_english_script = base_script.format(url=f"{BASE_URL}/glf/remove", csrf_token=csrf_token, body="languages%5B%5D=en")
    add_hindi_script = base_script.format(url=f"{BASE_URL}/en/glf/add", csrf_token=csrf_token, body=f"languages%5B%5D={LANGUAGE}")
    
    driver.execute_script(remove_english_script)
    driver.execute_script(add_hindi_script)
    driver.refresh()

def download_and_extract_zip(download_link, session):
    if not os.path.exists('subtitles'):
        os.makedirs('subtitles')
    
    zip_response = session.get(download_link)
    z = zipfile.ZipFile(io.BytesIO(zip_response.content))

    srt_files = [name for name in z.namelist() if name.endswith(".srt")]
    if srt_files:
        srt_file_name = srt_files[0]
        z.extract(srt_file_name, path="subtitles")
        return srt_file_name
    return None

def download_subtitles(driver, writer, session, file):
    page_number = 1
    while True:
        try:
            driver.get(f"{BASE_URL}/subtitles/search/?page={page_number}&language={LANGUAGE}")
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr.subtitle-entry")))
            
            entries = driver.find_elements(By.CSS_SELECTOR, "tr.subtitle-entry")
            if not entries:
                break

            for entry in entries:
                try:
                    title_element = entry.find_element(By.CSS_SELECTOR, 'a[alt="Subtitles\' page"]')
                    title = title_element.text.strip()
                    
                    # Check for year existence
                    year = title.split("(")[-1].split(")")[0] if "(" in title and ")" in title else "N/A"

                    download_link_element = entry.find_element(By.CSS_SELECTOR, 'a[rel="nofollow"]')
                    download_link = download_link_element.get_attribute("href")

                    srt_file = download_and_extract_zip(download_link, session)
                    if srt_file:
                        writer.writerow([title, year, srt_file])
                        file.flush()

                except NoSuchElementException:
                    logging.warning("An expected element was not found on the page.")
            
            page_number += 1

        except TimeoutException:
            logging.warning("Timeout reached, moving to next page")
            page_number += 1
        except Exception as e:
            logging.error(f"Error processing an entry: {e}")
            break

def main():
    driver = setup_driver()
    session = requests.Session()

    try:
        driver.get(BASE_URL)
        csrf_token = get_csrf_token(driver)

        if csrf_token is None:
            logging.error("Could not find csrf token")
            return

        set_language_filter(driver, csrf_token)

        with open("subtitles.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Title", "Year", "Subtitle File"])
            download_subtitles(driver, writer, session, file)

        logging.info("Script completed successfully.")

    except Exception as e:
        logging.error(f"Error: {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
