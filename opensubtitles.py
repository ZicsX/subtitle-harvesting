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
from s3_manager import S3SubtitleManager

# Constants
BASE_URL = "https://www.opensubtitles.org/en/search/sublanguageid-hin/offset-"
SESSION = requests.Session()

# Regexp Patterns
TIME_PATTERN = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})")
INDEX_PATTERN = re.compile(r"^\d+$")
YEAR_PATTERN = re.compile(r"\b\d{4}\b")
ENTRY_CSS_SELECTOR = "tr.change.even.expandable, tr.change.odd.expandable"

# Set up logging
logging.basicConfig(level=logging.INFO)

s3_manager = S3SubtitleManager(bucket_name="")


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


def process_srt_content(content):
    """Process the srt content and return cleaned lines."""

    lines = content.splitlines()
    cleaned_lines = [
        line.strip()
        for line in lines
        if not (TIME_PATTERN.match(line) or INDEX_PATTERN.match(line))
    ]
    return "\n".join(cleaned_lines).replace("\n\n", "\n")


def download_and_extract_zip(download_link):
    zip_response = SESSION.get(download_link)
    z = zipfile.ZipFile(io.BytesIO(zip_response.content))

    srt_files = [name for name in z.namelist() if name.endswith(".srt")]

    for srt_file in srt_files:
        content = z.read(srt_file).decode("utf-8")
        processed_content = process_srt_content(content)
        output_filename = os.path.splitext(srt_file)[0] + ".txt"

        s3_manager.upload_subtitle(output_filename, processed_content)

        title, year = get_title_and_year_from_filename(srt_file)
        yield output_filename, title, year


def get_title_and_year_from_filename(filename):
    year_match = YEAR_PATTERN.search(filename)
    year = year_match.group(0) if year_match else "N/A"

    title = re.sub(
        r"\b\d{4}\b|S\d{2}E\d{2}|\d+p|WEB|HDTV|x264|x265|MiNX|HIN|[-_.]",
        " ",
        filename,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", title).strip(), year


def download_subtitles(driver, writer, file):
    try:
        driver.get(BASE_URL + "0")
        total_entries_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.msg.hint span b:nth-child(3)")
            )
        )
        total_entries = int(total_entries_element.text)

        for offset in range(0, total_entries, 40):
            driver.get(os.path.join(BASE_URL, str(offset)))
            entries = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, ENTRY_CSS_SELECTOR)
                )
            )
            for entry in entries:
                try:
                    download_id = entry.get_attribute("id").replace("name", "")
                    download_link = f"https://www.opensubtitles.org/en/subtitleserve/sub/{download_id}"
                    for output_filename, title, year in download_and_extract_zip(
                        download_link
                    ):
                        writer.writerow([title, year, output_filename])
                        file.flush()
                except Exception as e:
                    logging.error(f"Error processing an entry: {e}\n{format_exc()}")

    except Exception as e:
        logging.error(f"Error during downloading: {e}\n{format_exc()}")


def main():
    driver = setup_driver()
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
