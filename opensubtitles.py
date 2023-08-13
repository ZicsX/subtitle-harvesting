import io
import csv
import zipfile
import requests
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def setup_driver():
    options = Options()
    options.headless = True
    return webdriver.Chrome(options=options)


def download_subtitles(driver, writer, file):
    driver.get("https://www.opensubtitles.org/en/search/sublanguageid-hin/offset-0")
    total_entries_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div.msg.hint span b:nth-child(3)")
        )
    )
    total_entries = int(total_entries_element.text)

    for offset in range(0, total_entries, 40):
        try:
            driver.get(
                f"https://www.opensubtitles.org/en/search/sublanguageid-hin/offset-{offset}"
            )
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

                zip_response = requests.get(download_link)
                z = zipfile.ZipFile(io.BytesIO(zip_response.content))
                z.extractall(path="subtitles")

                srt_file = [name for name in z.namelist() if name.endswith(".srt")][0]

                # Extract year and clean title from srt file name
                year_match = re.search(r"\b\d{4}\b", srt_file)
                year = year_match.group(0) if year_match else ""

                title = re.sub(r"\b\d{4}\b", "", srt_file)  # Remove year
                title = re.sub(r"S\d{2}E\d{2}", "", title)  # Remove season and episode
                title = re.sub(r"\d+p", "", title)  # Remove resolution
                title = re.sub(
                    r"WEB|HDTV|x264|x265|MiNX|HIN", "", title, flags=re.I
                )  # Remove source or encoding
                title = re.sub(
                    r"[-_.]", " ", title
                )  # Replace hyphens and dots with spaces
                title = re.sub(r"\s+", " ", title).strip()  # Remove extra spaces

                writer.writerow([title, year, srt_file])
                file.flush()  # Flush the file buffer to write the data immediately

        except Exception as e:
            print(f"Error processing an entry: {e}")


def main():
    driver = setup_driver()

    try:
        with open("subtitles.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Title", "Year", "Subtitle File"])
            download_subtitles(driver, writer, file)

        print("Script completed successfully.")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
