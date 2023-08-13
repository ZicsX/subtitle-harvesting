import os
import io
import csv
import zipfile
import requests
import re
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from traceback import format_exc

# Set up logging
logging.basicConfig(level=logging.INFO)

# Constants
SUBTITLES_DIR = "subtitles"
BASE_URL = "https://www.opensubtitles.org/en/search/sublanguageid-hin/offset-"
SESSION = requests.Session()


def setup_driver():
    options = Options()
    # Common settings
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--ignore-ssl-errors=yes")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--headless")

    platform = os.sys.platform
    if platform == "win32":
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
    elif platform.startswith("linux"):
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    return webdriver.Chrome(options=options)


def download_and_extract_zip(download_link):
    zip_response = SESSION.get(download_link)
    z = zipfile.ZipFile(io.BytesIO(zip_response.content))

    srt_files = [name for name in z.namelist() if name.endswith(".srt")]
    for srt_file in srt_files:
        z.extract(srt_file, path=SUBTITLES_DIR)

    return srt_files


def get_title_and_year_from_filename(filename):
    year_match = re.search(r"\b\d{4}\b", filename)
    year = year_match.group(0) if year_match else "N/A"

    title = re.sub(
        r"\b\d{4}\b|S\d{2}E\d{2}|\d+p|WEB|HDTV|x264|x265|MiNX|HIN|[-_.]",
        " ",
        filename,
        flags=re.I,
    )
    title = re.sub(r"\s+", " ", title).strip()

    return title, year


def download_subtitles(driver, writer, file):
    driver.get(BASE_URL + "0")
    total_entries_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div.msg.hint span b:nth-child(3)")
        )
    )
    total_entries = int(total_entries_element.text)

    for offset in range(0, total_entries, 40):
        try:
            driver.get(BASE_URL + str(offset))
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (
                        By.CSS_SELECTOR,
                        "tr.change.even.expandable, tr.change.odd.expandable",
                    )
                )
            )
            entries = driver.find_elements(
                By.CSS_SELECTOR, "tr.change.even.expandable, tr.change.odd.expandable"
            )

            for entry in entries:
                download_id = entry.get_attribute("id").replace("name", "")
                download_link = (
                    f"https://www.opensubtitles.org/en/subtitleserve/sub/{download_id}"
                )

                srt_files = download_and_extract_zip(download_link)

                for srt_file in srt_files:
                    title, year = get_title_and_year_from_filename(srt_file)
                    writer.writerow([title, year, srt_file])
                    file.flush()

        except Exception as e:
            logging.error(f"Error processing an entry: {e}\n{format_exc()}")


def main():
    driver = setup_driver()

    # Ensure the subtitles directory exists
    if not os.path.exists(SUBTITLES_DIR):
        os.makedirs(SUBTITLES_DIR)

    try:
        with open("subtitles.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Title", "Year", "Subtitle File"])
            download_subtitles(driver, writer, file)

        logging.info("Script completed successfully.")

    except Exception as e:
        logging.error(f"Error: {e}\n{format_exc()}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
