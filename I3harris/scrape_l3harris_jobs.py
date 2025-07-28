import asyncio
from playwright.async_api import async_playwright, expect
import pandas as pd

job_format = ["remote", "onsite", "online", "full-time", "part-time", "contract", "internship", "temporary", "on site", "hybrid", "flexible"]

def extract_sections(text):
    lines = text.splitlines()
    sections = {}
    current_header = "General"
    sections[current_header] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith(":") and len(stripped.split()) < 10:
            current_header = stripped.rstrip(":")
            sections[current_header] = []
        else:
            sections[current_header].append(stripped)

    for key in sections:
        sections[key] = "\n".join(sections[key]).strip()

    return sections

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

            for i in range(total):
                try:
                    job = jobs.nth(i)
                except TimeoutError:
                    break

                title = await job.locator("a h2").inner_text()
                location = await job.locator("span.job-location").inner_text()
                url_suffix = await job.locator("a").get_attribute("href")
                job_id = await job.locator("a").get_attribute("data-job-id")
                full_url = f"https://careers.l3harris.com{url_suffix}"

                # Visit job page
                job_page = await browser.new_page()
                await job_page.goto(full_url)
                await job_page.wait_for_load_state("domcontentloaded")

                try:
                    schedule = await job_page.get_by_text("Job Schedule:").inner_text()
                except:
                    schedule = "N/A"

                try:
                    raw_description = await job_page.locator("div.job-description").inner_text()
                except:
                    raw_description = ""

                await job_page.close()

                description_sections = extract_sections(raw_description)

                job_entry = {
                    "Title": title,
                    "Location": location,
                    "Job ID": job_id,
                    "URL": full_url,
                    "Job Format": next((fmt for fmt in job_format if fmt in title.lower()), "N/A"),
                    "Schedule": schedule.replace("Job Schedule: ", ""),
                    "Job Description": raw_description
                }

                for key, value in description_sections.items():
                    cleaned = value.replace("APPLY NOW", "")
                    job_entry[key] = cleaned

                job_data.append(job_entry)
                print(f"[{i+1}/{total}] Scraped: {title}")

                # To test this part of limitation
                if i == total:
                    break

            # Pagination
            page_count = page.locator("#pagination-current-bottom")
            current_page = await page_count.get_attribute("value")
            max_page = await page_count.get_attribute("max")

            print(f"Page {current_page} of {max_page}")
            if int(current_page) == int(max_page):
                break
            await page.locator(".next").click()

        # Save to Excel
        df = pd.DataFrame(job_data)
        df.to_excel("l3harris_jobs.xlsx", index=False)
        print("\nSaved to l3harris_jobs.xlsx")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_jobs())
