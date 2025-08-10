import asyncio
import argparse
from datetime import datetime
from playwright.async_api import async_playwright
from scraper.scraper import Scraper


async def scrape_jobs(start_page, end_page, output_file):
    url = "https://www.lockheedmartinjobs.com/search-jobs"
    company = "Lockhead Martin"

    async with async_playwright() as p:
        scraper = Scraper(url, company, start_page, end_page, output_file)
        await scraper.goto_page(p)
        total_page_number = scraper.page.locator(".pagination-total-pages")
        await scraper.define_total_pages(total_page_number)

        input_page_number = scraper.page.locator("#pagination-current-bottom")
        await scraper.goto_starting_page(input_page_number)

        while True:
            current_page_raw = await input_page_number.get_attribute("value")
            if current_page_raw is None:
                break

            try:
                current_page = int(current_page_raw)
            except ValueError:
                print(f"Invalid current page value: {current_page_raw}")
                break

            if current_page == 2:
                break

            jobs_locator = scraper.page.locator("#search-results-list li")
            await scraper.find_jobs(jobs_locator, current_page)

            for i in range(scraper.total_jobs):
                if i == 3:  # Limit to 4 jobs per page
                    break

                try:
                    job = scraper.jobs.nth(i)
                    title = await job.locator(".job-title").inner_text()
                    location = await job.locator(".job-location").inner_text()
                    url_suffix = await job.locator("a").get_attribute("href")
                    full_url = f"https://www.lockheedmartinjobs.com/{url_suffix}"
                except Exception as e:
                    print(f"[{i+1}] Failed extracting job summary: {e}")
                    continue

                scraper.job_data.append({
                    "Title": title,
                    "Location": location,
                    "URL": full_url
                })

                job_page = await scraper.goto_job_page()
                if not job_page:
                    continue

                posted_date = await scraper.safe_get(".job-date", page = job_page)
                job_id = await scraper.safe_get(".job-id", page = job_page)
                raw_text = await scraper.safe_get(".ats-description.ajd_job-details__ats-description", page = job_page)
                if "Description:" in raw_text:
                    raw_text = "Description:" + raw_text.split("Description:", 1)[1]
                else:
                    pass

                await job_page.close()

                scraper.job_data[-1].update({
                    "Job ID": job_id.replace("JOB ID: ", ""),
                    "Posted Date": posted_date.replace("Date posted: ", ""),
                })

                scraper.extract_sections(raw_text)
                print(f"[{i+1}/{scraper.total_jobs}] Scraped: {title}")

            next_btn = scraper.page.locator(".next")
            success = await scraper.goto_next_page(next_btn, current_page)
            if not success:
                break

        scraper.save_to_excel()
        await scraper.browser.close()


if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    default_output_file = f"lockheed_martin_jobs_{timestamp}.xlsx"

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")
    parser.add_argument("--output", type=str, default=default_output_file)
    args = parser.parse_args()

    asyncio.run(scrape_jobs(args.start, args.end, args.output))
