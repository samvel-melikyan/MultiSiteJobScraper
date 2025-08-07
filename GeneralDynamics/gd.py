import asyncio
import argparse
from playwright.async_api import async_playwright
from scraper.scraper import Scraper


async def scrape_jobs(start_page, end_page, output_file):
    url = "https://gdmissionsystems.com/careers/job-search"
    company = "General Dynamics"

    async with async_playwright() as p:
        scraper = Scraper(url, company, start_page, end_page, output_file)
        await scraper.goto_page(p)
        total_pages_locator = scraper.page.locator(".pagination li")
        total_pages = await total_pages_locator.nth(-1).get_attribute("data-page-number")
        await scraper.define_total_pages(int(total_pages))

        while True:
            current_page_raw = await scraper.page.locator(".pagination li.page-item.active").inner_text()
            current_page = int(current_page_raw)
            if current_page is None:
                break

            jobs_locator = scraper.page.locator(".career-search-result.col-12")
            await scraper.find_jobs(jobs_locator, current_page)

            for i in range(scraper.total_jobs):
                if i == 4:
                    break
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

                def safe_get(selector, method="inner_text", attribute=None):
                    """Safely get text from a selector, returning 'N/A' if not found."""
                    if method == "inner_text":
                        try:
                            return job_page.locator(selector).inner_text()
                        except Exception:
                            return "N/A"
                    elif method == "get_attribute":
                        try:
                            return job_page.locator(selector).get_attribute(attribute)
                        except Exception:
                            return "N/A"

                location = await safe_get(".inset__location dd", method="get_attribute", attribute="data-value")
                job_id = await safe_get(".inset__id")
                category = await safe_get(".inset__category dt")
                employment_type = await safe_get(".inset__type dt")

                try:
                    raw_html = await job_page.locator(".career-detail-description").inner_html()
                except:
                    raw_html = ""

                await job_page.close()

                scraper.job_data[-1].update({
                    "Location": location,
                    "Job ID": job_id.replace("Job ID ", ""),
                    "Role Type": employment_type.replace("Role Type ", ""),
                    "Category": category.replace("Category ", ""),
                    "Job Description (Raw)": raw_html
                })

                scraper.extract_sections_from_html(raw_html)
                print(f"[{i+1}/{scraper.total_jobs}] Scraped: {title}")

            next_btn = scraper.page.locator(".pagination li").nth(-2)
            success = await scraper.goto_next_page(next_btn, current_page)
            if not success:
                break

        scraper.save_to_excel()
        await scraper.browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")
    parser.add_argument("--output", type=str, default="boeing_jobs.xlsx")
    args = parser.parse_args()

    asyncio.run(scrape_jobs(args.start, args.end, args.output))
