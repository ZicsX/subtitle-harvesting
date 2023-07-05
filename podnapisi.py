import io
import csv
import zipfile
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def setup_driver():
    options = Options()
    options.headless = True
    return webdriver.Chrome(options=options)


def get_csrf_token(driver):
    return driver.execute_script('return document.querySelector(\'meta[name="csrf-token"]\').getAttribute("content");')


def set_language_filter(driver, csrf_token):
    remove_english_script = f"""
    fetch("https://www.podnapisi.net/glf/remove", {{
        headers: {{
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-csrftoken": "{csrf_token}",
            "x-requested-with": "XMLHttpRequest"
        }},
        body: "languages%5B%5D=en",
        method: "POST",
        credentials: "include"
    }});
    """

    add_hindi_script = f"""
    fetch("https://www.podnapisi.net/en/glf/add", {{
        headers: {{
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-csrftoken": "{csrf_token}",
            "x-requested-with": "XMLHttpRequest"
        }},
        body: "languages%5B%5D=hi",
        method: "POST",
        credentials: "include"
    }});
    """

    driver.execute_script(remove_english_script)
    driver.execute_script(add_hindi_script)
    driver.refresh()

def download_subtitles(driver, writer, file):
    page_number = 1
    while True:
        try:
            driver.get(f"https://www.podnapisi.net/subtitles/search/?page={page_number}&language=hi")
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tr.subtitle-entry')))
            entries = driver.find_elements(By.CSS_SELECTOR, 'tr.subtitle-entry')
            if not entries:
                break

            for entry in entries:
                title_element = entry.find_element(By.CSS_SELECTOR, 'a[alt="Subtitles\' page"]')
                title = title_element.text
                year = title.split('(')[-1].split(')')[0]
                title = title.split('(')[0].strip()

                download_link_element = entry.find_element(By.CSS_SELECTOR, 'a[rel="nofollow"]')
                download_link = download_link_element.get_attribute('href')

                zip_response = requests.get(download_link)
                z = zipfile.ZipFile(io.BytesIO(zip_response.content))
                z.extractall(path='subtitles')

                srt_file = [name for name in z.namelist() if name.endswith('.srt')][0]
                writer.writerow([title, year, srt_file])
                file.flush()  # Flush the file buffer to write the data immediately

            page_number += 1

        except TimeoutException:
            print("Timeout reached, moving to next page")
            page_number += 1
        except Exception as e:
            print(f"Error processing an entry: {e}")
            break


def main():
    driver = setup_driver()

    try:
        driver.get("https://www.podnapisi.net/")
        csrf_token = get_csrf_token(driver)

        if csrf_token is None:
            print("Could not find csrf token")
            return

        set_language_filter(driver, csrf_token)

        with open('subtitles.csv', 'w', newline='', encoding='utf-8') as file:
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
