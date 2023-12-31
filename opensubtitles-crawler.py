import os
import csv
import re
import argparse
import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
import zipfile
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Constants
SUBTITLES_DIR = "subtitles"
MAX_RETRIES = 3

# Regexp Patterns
TIME_PATTERN = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})")
INDEX_PATTERN = re.compile(r"^\d+$")

async def fetch(session, url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537'}
    async with session.get(url, headers=headers) as response:
        return await response.read()

async def get_total_entries(session, lang):
    url = f"https://www.opensubtitles.org/en/sublanguageid-{lang}/offset-0"
    page_content = await fetch(session, url)
    soup = BeautifulSoup(page_content, 'html.parser')
    total_entries_element = soup.select_one("div.msg.hint span b:nth-child(3)")
    return int(total_entries_element.text)

async def crawl_links(offset, session, lang):
    url = f"https://www.opensubtitles.org/en/sublanguageid-{lang}/offset-{offset}"
    page_content = await fetch(session, url)
    soup = BeautifulSoup(page_content, 'html.parser')
    links = [a['href'].split('/')[-1] for a in soup.find_all('a', href=re.compile(r"^/en/subtitleserve/sub/\d+$"))]
    return links

def process_srt_content_blocking(content):
    lines = content.decode().splitlines()[1:]
    cleaned_lines = [
        line.strip()
        for line in lines
        if not (TIME_PATTERN.match(line) or INDEX_PATTERN.match(line) or line == '1')
    ]
    return "\n".join(cleaned_lines).replace("\n\n", "\n")

async def process_srt_content(content):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        processed_content = await loop.run_in_executor(pool, process_srt_content_blocking, content)
    return processed_content

async def download_and_extract_zip(session, download_id, retries=MAX_RETRIES):
    try:
        download_link = f"https://www.opensubtitles.org/en/subtitleserve/sub/{download_id}"
        zip_response = await fetch(session, download_link)

        if not zip_response.startswith(b'PK'):  # Check if it's a zip file
            raise ValueError("Not a zip file")

        z = zipfile.ZipFile(io.BytesIO(zip_response))

        for srt_file in z.namelist():
            if srt_file.endswith(".srt"):
                content = z.read(srt_file)
                processed_content = await process_srt_content(content)
                output_filename = os.path.join(SUBTITLES_DIR, f"{download_id}.txt")

                async with aiofiles.open(output_filename, "w", encoding='utf-8') as txt_file:
                    await txt_file.write(processed_content)
    except Exception as e:
        print(f"An error occurred while processing {download_id}: {e}")
        if retries > 0:
            print(f"Retrying {download_id}. Remaining retries: {retries-1}")
            await asyncio.sleep(2)
            async with aiohttp.ClientSession() as new_session:  # Refresh session
                await download_and_extract_zip(new_session, download_id, retries-1)

async def download_subtitles(csvname):
    async with aiohttp.ClientSession() as session:
        async with aiofiles.open(csvname, 'r') as csvfile:
            async for line in csvfile:
                download_id = line.strip()
                await download_and_extract_zip(session, download_id)
                await asyncio.sleep(1)

async def main(args):
    try:
        if not os.path.exists(SUBTITLES_DIR):
            os.makedirs(SUBTITLES_DIR)

        lang = args.lang
        csvname = f"subtitles_{lang}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        if args.command == 'crawl':
            async with aiohttp.ClientSession() as session:
                limit = args.l if args.l else await get_total_entries(session, lang)
                with open(csvname, 'w', newline='') as csvfile:
                    csvwriter = csv.writer(csvfile)
                    for i in range(0, limit, 40):
                        links = await crawl_links(i, session, lang)
                        for link in links:
                            csvwriter.writerow([link])

        elif args.command == 'download':
            await download_subtitles(args.csv)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Exiting the program.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Subtitle Crawler and Downloader')
    parser.add_argument('command', choices=['crawl', 'download'], help='Command to execute.')
    parser.add_argument('--l', type=int, default=None, help='Limit for crawl.')
    parser.add_argument('--lang', type=str, default='hin', help='Subtitle language ID.')
    parser.add_argument('--csv', type=str, default=None, help='CSV file for download.')
    args = parser.parse_args()

    asyncio.run(main(args))
