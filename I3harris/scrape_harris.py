import asyncio
import argparse
from playwright.async_api import async_playwright
from scraper.scraper import Scraper

async def scrape_jobs(start_page, end_page, output_file):
    url = "https://careers.l3harris.com/en/search-jobs"
    company_name = "L3harris.com"
    async with async_playwright() as p:
        scraper = Scraper(url, company_name, start_page, end_page, output_file)
        await scraper.goto_page(p)
        await scraper.page_tracker(scraper.page.locator(".pagination-total-pages"))

        if start_page > 1:
            await scraper.page.locator("#pagination-current-bottom").fill(str(start_page))
            await scraper.page.locator(".pagination-page-jump").click()
            await scraper.page.wait_for_timeout(1000)

        while True:
            current_page = await scraper.page.locator("#pagination-current-bottom").get_attribute("value")
            if current_page is None or (end_page != float("inf") and int(current_page) > end_page):
                break

            await scraper.find_jobs(scraper.page.locator("#search-results-list li"), current_page)
            total = await scraper.jobs.count()

            for i in range(total):
                if i == 5:
                    break

                job_dict = {
                    "Title": await scraper.jobs.nth(i).locator("a h2").inner_text(),
                    "Location": await scraper.jobs.nth(i).locator("span.job-location").inner_text(),
                    "Job ID": await scraper.jobs.nth(i).locator("a").get_attribute("data-job-id"),
                    "URL": f"https://careers.l3harris.com{await scraper.jobs.nth(i).locator('a').get_attribute('href')}"
                }
                scraper.job_data.append(job_dict)

                job_page = await scraper.goto_job_page(i)
                if not job_page:
                    continue

                try:
                    schedule_element = job_page.locator("text=Job Schedule:")
                    schedule = await schedule_element.evaluate(
                        "el => el.nextSibling?.textContent || el.parentElement?.textContent || 'N/A'"
                    )
                except:
                    schedule = "N/A"

                scraper.job_data[i]["Schedule"] = schedule.replace("Job Schedule: ", "")
                raw_description = await job_page.locator("div.job-description").inner_html()
                scraper.job_data[i]["Description(raw)"] = raw_description
                scraper.extract_sections(raw_description, i)
                await job_page.close()

                print(f"[{i+1}/{total}] Scraped: {scraper.job_data[i]['Title']}")

            has_next = await scraper.goto_next_page(scraper.page.locator(".next"), current_page)
            if not has_next:
                break

        scraper.save_to_excel()
        await scraper.browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")
    parser.add_argument("--output", type=str, default="l3harris_jobs.xlsx")
    args = parser.parse_args()

    start_page = args.start
    if args.end == "max":
        end_page = float("inf")
    else:
        try:
            end_page = int(args.end)
        except ValueError:
            raise ValueError("`--end` must be an integer or 'max'.")

    asyncio.run(scrape_jobs(start_page, end_page, args.output))
