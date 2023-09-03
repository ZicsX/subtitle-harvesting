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

# Constants
SUBTITLES_DIR = "subtitles"
CSV_FILENAME = "subtitles.csv"

# Regexp Patterns
TIME_PATTERN = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})")
INDEX_PATTERN = re.compile(r"^\d+$")

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.read()

async def get_total_entries(session):
    url = "https://www.opensubtitles.org/en/search/sublanguageid-hin/offset-0"
    page_content = await fetch(session, url)
    soup = BeautifulSoup(page_content, 'html.parser')
    total_entries_element = soup.select_one("div.msg.hint span b:nth-child(3)")
    return int(total_entries_element.text)

async def crawl_links(offset, session):
    url = f"https://www.opensubtitles.org/en/search/sublanguageid-hin/offset-{offset}"
    page_content = await fetch(session, url)
    soup = BeautifulSoup(page_content, 'html.parser')
    links = [a['href'].split('/')[-1] for a in soup.find_all('a', href=re.compile(r"^/en/subtitleserve/sub/\d+$"))]
    return links

def process_srt_content_blocking(content):
    lines = content.decode().splitlines()
    cleaned_lines = [
        line.strip()
        for line in lines
        if not (TIME_PATTERN.match(line) or INDEX_PATTERN.match(line))
    ]
    return "\n".join(cleaned_lines).replace("\n\n", "\n")

async def process_srt_content(content):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        processed_content = await loop.run_in_executor(pool, process_srt_content_blocking, content)
    return processed_content


async def download_and_extract_zip(session, download_id):
    try:
        download_link = f"https://www.opensubtitles.org/en/subtitleserve/sub/{download_id}"
        zip_response = await fetch(session, download_link)
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

async def download_subtitles():
    async with aiohttp.ClientSession() as session:
        async with aiofiles.open(CSV_FILENAME, 'r') as csvfile:
            async for line in csvfile:
                download_id = line.strip()
                await download_and_extract_zip(session, download_id)

async def main(args):
    try:
        if not os.path.exists(SUBTITLES_DIR):
            os.makedirs(SUBTITLES_DIR)
        
        if args.command == 'crawl':
            async with aiohttp.ClientSession() as session:
                limit = args.limit if args.limit else await get_total_entries(session)
                with open(CSV_FILENAME, 'w', newline='') as csvfile:
                    csvwriter = csv.writer(csvfile)
                    for i in range(0, limit, 40):
                        links = await crawl_links(i, session)
                        for link in links:
                            csvwriter.writerow([link])

        elif args.command == 'download':
            await download_subtitles()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Exiting the program.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Subtitle Crawler and Downloader')
    parser.add_argument('command', choices=['crawl', 'download'], help='Command to execute.')
    parser.add_argument('--limit', type=int, default=None, help='Limit for crawl.')
    args = parser.parse_args()

    asyncio.run(main(args))
