import asyncio
import argparse
from playwright.async_api import async_playwright
import pandas as pd
from collections import defaultdict


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


async def scrape_jobs(start_page, end_page, output_file):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        page.set_default_timeout(7000)

        await page.goto("https://www.lockheedmartinjobs.com/search-jobs", timeout=30000)
        print("Launched lockheedmartinjobs.com")
        print("Loading jobs...")

        job_data = []

        current_page = start_page
        while current_page <= end_page:
            print(f"Scraping page {current_page}")

            # Wait for job listings container
            await page.wait_for_selector("div.results-container")

            jobs = page.locator("#search-results-list li a")
            total = await jobs.count()
            print(f"Found {total} jobs on page {current_page}")

            for i in range(total):
                try:
                    job = jobs.nth(i)
                    title = await job.locator("span.job-title").inner_text()
                    job_id = await job.get_attribute("data-job-id")
                    location = await job.locator("span.job-location").inner_text()
                    job_url = await job.get_attribute("href")
                    posted = await job.locator("span.job-date-posted").inner_text()
                    full_url = f"https://www.lockheedmartinjobs.com{job_url}"
                except Exception as e:
                    print(f"Error extracting job info at index {i}: {e}")
                    continue

                try:
                    job_page = await browser.new_page()
                    await job_page.goto(full_url)
                    await job_page.wait_for_load_state("domcontentloaded")
                except Exception as e:
                    print(f"Error loading job page for {title}: {e}")
                    await job_page.close()
                    continue

                try:
                    raw_text = await job_page.locator("div.job-description").inner_text()
                except:
                    raw_text = ""

                await job_page.close()

                description_sections = extract_sections(raw_text)

                job_entry = {
                    "Title": title,
                    "Location": location,
                    "URL": full_url,
                    "Job Description (Raw)": raw_text
                }

                for key, value in description_sections.items():
                    job_entry[key] = value

                job_data.append(job_entry)
                print(f"[{i+1}/{total}] Scraped: {title}")

            if current_page >= end_page:
                break

            try:
                # Click next page button if exists and enabled
                next_btn = page.locator("button[aria-label='Next Page']")
                is_disabled = await next_btn.get_attribute("disabled")
                if is_disabled:
                    print("No more pages to scrape.")
                    break
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                current_page += 1
            except Exception as e:
                print(f"Could not navigate to next page: {e}")
                break

        df = pd.DataFrame(job_data)

        # --- Merge duplicate columns ---
        merged_columns = defaultdict(list)
        for col in df.columns:
            merged_columns[col].append(df[col])

        merged_df = pd.DataFrame()
        for col, col_list in merged_columns.items():
            if len(col_list) == 1:
                merged_df[col] = col_list[0]
            else:
                merged_df[col] = col_list[0].astype(str)
                for additional_col in col_list[1:]:
                    merged_df[col] = merged_df[col] + "\n" + additional_col.astype(str)

        merged_df.to_excel(output_file, index=False)
        print(f"\nSaved to {output_file}")

        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=10)
    parser.add_argument("--output", type=str, default="lockheed_martin_jobs.xlsx")
    args = parser.parse_args()

    asyncio.run(scrape_jobs(args.start, args.end, args.output))
