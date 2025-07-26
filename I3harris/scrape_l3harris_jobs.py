import asyncio
from playwright.async_api import async_playwright, expect
import pandas as pd

async def scrape_jobs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://careers.l3harris.com/en/search-jobs")
        print("Launching l3harris.com")
        print("Loading all jobs...")
        await page.wait_for_timeout(2000)

        job_data = []

        while True:
            jobs = page.locator("#search-results-list li")
            total = await jobs.count()
            print(f"Found {total} jobs")

            # Loop through all jobs in one page
            for i in range(total):
                # if i == 2:
                #     break
                job = jobs.nth(i)

                title = await job.locator("a h2").inner_text()
                location = await job.locator("span.job-location").inner_text()
                url_suffix = await job.locator("a").get_attribute("href")
                job_id = await job.locator("a").get_attribute("data-job-id")

                full_url = f"https://careers.l3harris.com{url_suffix}"

                # Visit job page to get description
                job_page = await browser.new_page()
                await job_page.goto(full_url)
                await job_page.wait_for_load_state("domcontentloaded")

                try:
                    description = await job_page.locator("div.job-description").inner_text()
                except:
                    description = "N/A"

                await job_page.close()

                job_data.append({
                    "Title": title,
                    "Location": location,
                    "Job ID": job_id,
                    "URL": full_url,
                    "Description": description
                })
                print(f"[{i+1}/{total}] Scraped: {title}")

            # page count tracking
            page_count = page.locator("#pagination-current-bottom")
            current_page = await page_count.get_attribute("value")
            max_page = await page_count.get_attribute("max")

            print(f"Page {current_page} of {max_page}")

            if int(current_page) == 3:
                break
            await page.locator(".next").click()



        # Save to EXCEL
        df = pd.DataFrame(job_data)
        df.to_excel("l3harris_jobs.xlsx", index=False)

        print("\nSaved to l3harris_jobs.xlsx")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_jobs())
