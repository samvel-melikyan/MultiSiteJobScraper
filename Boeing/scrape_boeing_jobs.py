import asyncio
import argparse
from playwright.async_api import async_playwright, TimeoutError
import pandas as pd
from bs4 import BeautifulSoup
from collections import defaultdict
import sys


def extract_sections_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    sections = {}
    current_header = "General"
    sections[current_header] = []

    for p in soup.find_all("p"):
        bold = p.find("b")
        if bold:
            header_text = bold.get_text(strip=True).rstrip(":")
            current_header = header_text
            if current_header not in sections:
                sections[current_header] = []
        else:
            text = p.get_text(strip=True)
            if text:
                sections[current_header].append(text)

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
            print("❌ Invalid value for --end. Use an integer or 'max'.")
            sys.exit(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(7000)
        await page.goto("https://jobs.boeing.com/search-jobs", wait_until="domcontentloaded")
        print("Launching jobs.boeing.com")
        print("Loading all jobs...")
        await page.wait_for_timeout(10000)

        job_data = []
        current_page = start_page

        while True:
            if current_page > end_page:
                break

            print(f"Scraping page {current_page}")
            jobs = page.locator("#search-results-list li")
            total = await jobs.count()
            print(f"Found {total} jobs on page {current_page}")

            for i in range(total):
                try:
                    job = jobs.nth(i)
                    title = await job.locator("a span").inner_text()
                    url_suffix = await job.locator("a").get_attribute("href")
                    full_url = f"https://jobs.boeing.com{url_suffix}"
                except Exception as e:
                    print(f"Error extracting job details for index {i} on page {current_page}: {e}")
                    continue

                try:
                    job_page = await browser.new_page()
                    job_page.set_default_timeout(7000)
                    await job_page.goto(full_url)
                    await job_page.wait_for_load_state("domcontentloaded")
                except Exception as e:
                    print(f"Error loading job page for {title}: {e}")
                    await job_page.close()
                    continue

                try:
                    location = await job_page.locator(".job-description__job-location").inner_text()
                except:
                    location = "N/A"

                try:
                    posted_date = await job_page.locator(".job-date").inner_text()
                except:
                    posted_date = "N/A"

                try:
                    job_id = await job_page.locator(".job-id").inner_text()
                except:
                    job_id = "N/A"

                try:
                    category = await job_page.locator(".job-category").inner_text()
                except:
                    category = "N/A"

                try:
                    role_type = await job_page.locator(".job-role-type").inner_text()
                except:
                    role_type = "N/A"

                try:
                    raw_html = await job_page.locator("#ats-description").inner_html()
                    raw_text = await job_page.locator("#ats-description").inner_text()
                except:
                    raw_html = ""
                    raw_text = ""

                await job_page.close()

                description_sections = extract_sections_from_html(raw_html)

                job_entry = {
                    "Title": title,
                    "Location": location,
                    "Job ID": job_id.replace("Job ID ", ""),
                    "Role Type": role_type.replace("Role Type ", ""),
                    "Category": category.replace("Category ", ""),
                    "Posted Date": posted_date.replace("Post Date ", ""),
                    "URL": full_url,
                    "Job Description (Raw)": raw_text
                }

                for key, value in description_sections.items():
                    job_entry[key] = value

                job_data.append(job_entry)
                print(f"[{i+1}/{total}] Scraped: {title}")

            # Try to go to next page
            try:
                next_btn = page.locator(".next")
                if await next_btn.get_attribute("disabled"):
                    print("✅ Reached the last page.")
                    break
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                current_page += 1
            except Exception as e:
                print(f"Could not navigate to next page: {e}")
                break

        # Merge duplicate columns with the same name
        df = pd.DataFrame(job_data)
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
                    merged_df[col] += "\n" + additional_col.astype(str)

        merged_df.to_excel(output_file, index=False)
        print(f"\n✅ Saved to {output_file}")
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")  # ← now accepts 'max'
    parser.add_argument("--output", type=str, default="boeing_jobs.xlsx")
    args = parser.parse_args()

    asyncio.run(scrape_jobs(args.start, args.end, args.output))
