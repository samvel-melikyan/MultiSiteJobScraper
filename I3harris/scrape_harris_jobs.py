import asyncio
import argparse
from datetime import datetime

from playwright.async_api import async_playwright
from scraper.scraper import Scraper

async def scrape_jobs(start_page, end_page, output_file):
    url = "https://careers.l3harris.com/en/search-jobs"
    company_name = "L3harris.com"
    async with async_playwright() as p:
        scraper = Scraper(url, company_name, start_page, end_page, output_file)
        await scraper.goto_page(p)
        total_page_number = scraper.page.locator(".pagination-total-pages")
        await scraper.define_total_pages(total_page_number)
        input_page_number = scraper.page.locator("#pagination-current-bottom")
        await scraper.goto_starting_page(input_page_number)

        while True:
            current_page = await scraper.page.locator("#pagination-current-bottom").get_attribute("value")
            if current_page is None:
                print("Error: Unable to retrieve current page number.")
                break

            await scraper.find_jobs(scraper.page.locator("#search-results-list li"), current_page)
            total = await scraper.jobs.count()

            for i in range(total):

                job_dict = {
                    "Title": await scraper.jobs.nth(i).locator("a h2").inner_text(),
                    "Location": await scraper.jobs.nth(i).locator("span.job-location").inner_text(),
                    "Job ID": await scraper.jobs.nth(i).locator("a").get_attribute("data-job-id"),
                    "URL": f"https://careers.l3harris.com{await scraper.jobs.nth(i).locator('a').get_attribute('href')}"
                }
                scraper.job_data.append(job_dict)

                job_page = await scraper.goto_job_page()
                if not job_page:
                    continue

                try:
                    schedule_element = job_page.locator("text=Job Schedule:")
                    schedule = await schedule_element.evaluate(
                        "el => el.nextSibling?.textContent || el.parentElement?.textContent || 'N/A'"
                    )
                except Exception:
                    schedule = "N/A"
                scraper.job_data[-1]["Schedule"] = schedule.replace("Job Schedule: ", "")

                raw_description = await job_page.locator("div.job-description").inner_text()
                await job_page.close()

                scraper.extract_sections(raw_description)

                print(f"[{i+1}/{total}] Scraped: {scraper.job_data[-1]['Title']}")

            has_next = await scraper.goto_next_page(scraper.page.locator("a.next"), current_page)
            if not has_next:
                break

        scraper.save_to_excel()
        await scraper.browser.close()

if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    default_output_file = f"l3harris_jobs_{timestamp}.xlsx"

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")
    parser.add_argument("--output", type=str, default=default_output_file)
    args = parser.parse_args()

    asyncio.run(scrape_jobs(args.start, args.end, args.output))
