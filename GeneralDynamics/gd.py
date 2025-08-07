import asyncio
import argparse
from playwright.async_api import async_playwright
import sys

from scraper.scraper import Scraper  # Update this import path if needed


async def scrape_jobs(start_page, end_page, output_file):
    url = "https://gdmissionsystems.com/careers/job-search"
    company = "General Dynamics"

    async with async_playwright() as p:
        scraper = Scraper(url, company, start_page, end_page, output_file)
        await scraper.goto_page(p)
        total_pages_locator = scraper.page.locator(".pagination li").last.get_attribute("data-page-number")
        await scraper.page_tracker(int(total_pages_locator))
        scraper.define_end_page()

        while True:
            current_page = int(await input_page_number.get_attribute("value"))
            if current_page is None:
                break

            jobs_locator = scraper.page.locator("#search-results-list li")
            await scraper.find_jobs(jobs_locator, current_page)\

            for i in range(scraper.total_jobs):
                if i == 4:
                    break
                try:
                    job = scraper.jobs.nth(i)
                    title = await job.locator("a span").inner_text()
                    url_suffix = await job.locator("a").get_attribute("href")
                    full_url = f"https://jobs.boeing.com{url_suffix}"
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

                def safe_get(selector):
                    try:
                        return job_page.locator(selector).inner_text()
                    except:
                        return "N/A"

                location = await safe_get(".job-description__job-location")
                posted_date = await safe_get(".job-date")
                job_id = await safe_get(".job-id")
                category = await safe_get(".job-category")
                role_type = await safe_get(".job-role-type")

                try:
                    raw_html = await job_page.locator("#ats-description").inner_text()
                except:
                    raw_html = ""

                await job_page.close()

                scraper.job_data[-1].update({
                    "Location": location,
                    "Job ID": job_id.replace("Job ID ", ""),
                    "Role Type": role_type.replace("Role Type ", ""),
                    "Category": category.replace("Category ", ""),
                    "Posted Date": posted_date.replace("Post Date ", ""),
                    "Job Description (Raw)": raw_html
                })

                scraper.extract_sections(raw_html)
                print(f"[{i+1}/{scraper.total_jobs}] Scraped: {title}")

            next_btn = scraper.page.locator(".next")
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
