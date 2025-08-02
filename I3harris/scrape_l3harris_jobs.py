import asyncio
import argparse
from playwright.async_api import async_playwright
import pandas as pd
from collections import defaultdict
import re

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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(7000)
        await page.goto("https://careers.l3harris.com/en/search-jobs", timeout=15000)
        print("Launching l3harris.com")
        await page.wait_for_timeout(1000)

        total_pages = await page.locator(".pagination-total-pages").inner_text()
        if end_page == "half":
            end_page = int(total_pages) // 2
        elif start_page == "half":
            start_page = int(total_pages) // 2

        if start_page > 1:
            await page.locator("#pagination-current-bottom").fill(str(start_page))
            await page.locator(".pagination-page-jump").click()
            await page.wait_for_timeout(1000)

        job_data = []
        current_page = start_page

        while current_page <= end_page:
            print(f"Scraping page {current_page} {total_pages}")
            jobs = page.locator("#search-results-list li")
            total = await jobs.count()
            print(f"Found {total} jobs on page {current_page}")

            for i in range(total):
                try:
                    job = jobs.nth(i)
                    title = await job.locator("a h2").inner_text()
                    location = await job.locator("span.job-location").inner_text()
                    url_suffix = await job.locator("a").get_attribute("href")
                    job_id = await job.locator("a").get_attribute("data-job-id")
                except Exception as e:
                    print(f"Error processing job {i + 1}: {e}")
                    continue

                full_url = f"https://careers.l3harris.com{url_suffix}"

                try:
                    job_page = await browser.new_page()
                    job_page.set_default_timeout(7000)
                    await job_page.goto(full_url)
                    await job_page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception as e:
                    print(f"Error loading job page for {title}: {e}")
                    await job_page.close()
                    continue

                try:
                    schedule_element = job_page.locator("text=Job Schedule:")
                    schedule = await schedule_element.evaluate(
                        "el => el.nextSibling?.textContent || el.parentElement?.textContent || 'N/A'"
                    )
                except:
                    schedule = "N/A"

                try:
                    raw_description = await job_page.locator("div.job-description").inner_text()
                except:
                    raw_description = ""

                await job_page.close()

                # Extract job format from title
                title_words = set(re.findall(r'\w+', title.lower()))
                job_fmt = next((fmt for fmt in job_format if any(fmt in word for word in title_words)), "N/A")

                # Section extraction
                description_sections = extract_sections(raw_description)

                job_entry = {
                    "Title": title,
                    "Location": location,
                    "Job ID": job_id,
                    "URL": full_url,
                    "Job Format": job_fmt,
                    "Schedule": schedule.replace("Job Schedule: ", ""),
                    "Job Description": raw_description
                }

                for key, value in description_sections.items():
                    cleaned = re.sub(r"\bapply now\b", "", value, flags=re.IGNORECASE).strip()
                    job_entry[key] = cleaned

                job_data.append(job_entry)
                print(f"[{i+1}/{total}] Scraped: {title}")

            try:
                next_btn = page.locator(".next")
                if await next_btn.get_attribute("disabled") or current_page >= end_page:
                    print("Reached last page or end limit.")
                    break
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                current_page += 1
            except Exception as e:
                print(f"Could not navigate to next page: {e}")
                break

        df = pd.DataFrame(job_data)

        # Efficient merge of duplicate columns
        merged_columns = defaultdict(list)
        for col in df.columns:
            merged_columns[col].append(df[col])

        concat_data = {}
        for col, col_list in merged_columns.items():
            if len(col_list) == 1:
                concat_data[col] = col_list[0]
            else:
                merged_col = col_list[0].astype(str)
                for additional_col in col_list[1:]:
                    merged_col += "\n" + additional_col.astype(str)
                concat_data[col] = merged_col

        merged_df = pd.concat(concat_data, axis=1).copy()
        merged_df.to_excel(output_file, index=False)
        print(f"\nSaved to {output_file}")

        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")
    parser.add_argument("--output", type=str, default="l3harris_jobs.xlsx")
    args = parser.parse_args()

    if args.end == "max":
        end_page = float("inf")
    else:
        try:
            end_page = int(args.end)
        except ValueError:
            raise ValueError("`--end` must be an integer or 'max'.")

    asyncio.run(scrape_jobs(args.start, end_page, args.output))
