import asyncio
import argparse
import sys
import os
from datetime import datetime

from playwright.async_api import async_playwright
import pandas as pd
from collections import defaultdict

job_format = [
    "remote", "onsite", "online", "full-time", "part-time",
    "contract", "internship", "temporary", "on site", "hybrid", "flexible"
]

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
    if end_page == "max":
        end_page = float('inf')
    else:
        try:
            end_page = int(end_page)
        except ValueError:
            print("Invalid value for --end. Use an integer or 'max'.")
            sys.exit(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(7000)

        await page.goto("https://www.lockheedmartinjobs.com/search-jobs", timeout=30000)
        print("Launched lockheedmartinjobs.com")
        print("Loading jobs...")

        job_data = []
        current_page = start_page

        while True:
            if current_page > end_page:
                break

            print(f"Scraping page {current_page}")
            jobs = page.locator("#search-results-list li a")
            total = await jobs.count()
            print(f"Found {total} jobs on page {current_page}")

            for i in range(total):
                
                try:
                    job = jobs.nth(i)
                    title = await job.locator("span.job-title").inner_text()
                    job_id = await job.get_attribute("data-job-id") or "N/A"
                    location = await job.locator("span.job-location").inner_text()
                    job_url = await job.get_attribute("href") or "#"
                    posted = await job.locator("span.job-date-posted").inner_text()
                    full_url = f"https://www.lockheedmartinjobs.com{job_url}"

                    job_page = await browser.new_page()
                    await job_page.goto(full_url)
                    await job_page.wait_for_load_state("domcontentloaded")
                    raw_text = await job_page.locator("div.ajd_job-details__ats-description").inner_text()
                    await job_page.close()

                    description_sections = extract_sections(raw_text)

                    job_entry = {
                        "Title": title,
                        "Job ID": job_id,
                        "Posted Date": posted.replace("Date Posted: ", ""),
                        "Location": location,
                        "URL": full_url,
                        "Job Description": raw_text
                    }

                    for key, value in description_sections.items():
                        job_entry[key] = value

                    job_data.append(job_entry)
                    print(f"[{i+1}/{total}] Scraped: {title}")

                except Exception as e:
                    print(f"Error on job index {i}: {e}")
                    continue

            try:
                next_btn = page.locator("a.next")
                is_disabled = await next_btn.get_attribute("disabled")
                if is_disabled:
                    print("No more pages to scrape.")
                    break
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                current_page += 1
            except Exception as e:
                print(f"Could not navigate to next page: {e}")
                break

        # Save once all pages are done
        df = pd.DataFrame(job_data)
        df.to_excel(output_file, index=False)
        print(f"\nSaved to {output_file}")

        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    # Generate timestamped filename if not passed
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output = f"LockheedMartin/lockheed_martin_jobs_{args.start}_{args.end}_{timestamp}.xlsx"

    asyncio.run(scrape_jobs(args.start, args.end, args.output))
