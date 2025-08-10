import asyncio
import argparse
from datetime import datetime
import os

from playwright.async_api import async_playwright
import pandas as pd

from scraper.scraper import Scraper  # Ensure this path is correct


async def scrape_jobs(output_file: str):
    url = "https://navair.yellogov.com/job_boards/mdxt8VG0qqvc7z8xHhZztg"
    company_name = "NAVAIR"


    async with async_playwright() as p:
        scraper = Scraper(url, company_name, output_file=output_file)
        await scraper.goto_page(p)
        current_page = scraper.define_start_page()
        await scraper.find_jobs(scraper.page.locator("li.search-results__item"), current_page=current_page)
        total = await scraper.jobs.count()

        for i in range(total):

            job_dict = {
                "Title": await scraper.jobs.nth(i).locator("a").inner_text(),
                "Location": await scraper.jobs.nth(i).locator(".search-results__jobinfo.pull-left div").inner_text(),
                "Posted at": await scraper.jobs.nth(i).locator(".search-results__post-time.pull-right").inner_text(),
                "URL": f"https://navair.yellogov.com{await scraper.jobs.nth(i).locator('a').get_attribute('href')}"
            }
            scraper.job_data.append(job_dict)

            job_page = await scraper.goto_job_page()
            if not job_page:
                continue

            try:
                raw_description = await job_page.locator(".inner.clearfix.ck-rendered-content").inner_text()
            except:
                raw_description = ""
            await job_page.close()

            scraper.extract_sections(raw_description)

            print(f"[{i + 1}/{total}] Scraped: {scraper.job_data[-1]['Title']}")

        scraper.save_to_excel()
        await scraper.browser.close()


if __name__ == "__main__":
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    default_output_file = f"navair_jobs_{timestamp}.xlsx"

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=default_output_file)

    args = parser.parse_args()

    asyncio.run(scrape_jobs(args.output))
