import asyncio
import argparse
from datetime import datetime

from playwright.async_api import async_playwright
from scraper.scraper import Scraper


async def scrape_jobs(start_page, end_page, output_file):
    url = "https://gdmissionsystems.com/careers/job-search"
    company = "General Dynamics"

    async with (async_playwright() as p):
        scraper = Scraper(url, company, start_page, end_page, output_file)
        await scraper.goto_page(p)
        total_pages_locator = scraper.page.locator(".pagination li")
        total_pages = await total_pages_locator.nth(-1).get_attribute("data-page-number")
        await scraper.define_total_pages(int(total_pages))
        next_btn = scraper.page.locator(".pagination li").nth(-2)

        async def get_current_page():
            current_page_raw = await scraper.page.locator(".pagination li").nth(2).inner_text()
            return int(current_page_raw)
        while True:
            current_page = await get_current_page()

            if current_page is None:
                break

            if current_page < scraper.start_page:
                print(f"Going to {scraper.start_page} page")
                while True:
                    if current_page == scraper.start_page:
                        break
                    else:
                        await next_btn.click()
                        current_page = await get_current_page()

            jobs_locator = scraper.page.locator(".career-search-result.col-12")
            await scraper.find_jobs(jobs_locator, current_page)


            for i in range(scraper.total_jobs):
                try:
                    job = scraper.jobs.nth(i)
                    title = await job.locator("h4").inner_text()
                    full_url = await job.get_by_text("VIEW JOB DESCRIPTION").get_attribute("href")
                except Exception as e:
                    print(f"[{i+1}] Failed extracting job summary: {e}")
                    continue

                scraper.job_data.append({
                    "Title": title,
                    "URL": full_url
                })

                job_page = await scraper.goto_job_page()
                if not job_page:
                    continue

                async def safe_get(selector, method="inner_text", attribute=None):
                    """Safely get text from a selector, returning 'N/A' if not found."""
                    if method == "inner_text":
                        try:
                            return await job_page.locator(selector).inner_text()
                        except Exception:
                            return "N/A"
                    elif method == "get_attribute":
                        try:
                            return await job_page.locator(selector).get_attribute(attribute)
                        except Exception:
                            return "N/A"

                location = await safe_get(".inset__location dd", method="get_attribute", attribute="data-value")
                job_id = await safe_get(".inset__id")
                category = await safe_get(".inset__category dt")
                employment_type = await safe_get(".inset__type dt")

                try:
                    raw_text = await safe_get(".career-detail-description")
                except Exception:
                    raw_text = ""

                await job_page.close()

                scraper.job_data[-1].update({
                    "Location": location,
                    "Job ID": job_id.replace("ID ", ""),
                    "Employment Type": employment_type.replace("Employment Type", ""),
                    "Category": category.replace("Category", ""),
                    "Job Description (Raw)": raw_text
                })

                scraper.extract_sections(raw_text)
                print(f"[{i+1}/{scraper.total_jobs}] Scraped: {title}")


            success = await scraper.goto_next_page(next_btn, current_page)
            if not success:
                break

        scraper.save_to_excel()
        await scraper.browser.close()


if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    default_output_file = f"boeing_jobs_{timestamp}.xlsx"

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")
    parser.add_argument("--output", type=str, default=default_output_file)
    args = parser.parse_args()

    asyncio.run(scrape_jobs(args.start, args.end, args.output))
