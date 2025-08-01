import asyncio
import argparse
from playwright.async_api import async_playwright
import pandas as pd

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

        job_data = []
        current_page = start_page

        print("Navigating to NAVAIR job board...")
        await page.goto("https://navair.yellogov.com/job_boards/mdxt8VG0qqvc7z8xHhZztg", timeout=15000)

        while current_page <= end_page:
            print(f"\nScraping page {current_page}...")

            job_items = page.locator("li.search-results__item")
            total = await job_items.count()
            print(f"Found {total} job posts on page {current_page}")

            for i in range(total):
                # if i == 4:
                #     break
                try:
                    job = job_items.nth(i)
                except Exception as e:
                    print(f"Error selecting job item #{i}: {e}")
                    continue

                try:
                    title = await job.locator("a").inner_text()
                except Exception:
                    title = "N/A"

                try:
                    location = await job.locator(".search-results__jobinfo.pull-left div").inner_text()
                except Exception:
                    location = "N/A"

                try:
                    posted = await job.locator(".search-results__post-time.pull-right").inner_text()
                except Exception:
                    posted = "N/A"

                try:
                    job_url = await job.locator("a.search-results__req_title").get_attribute("href")
                    full_url = f"https://navair.yellogov.com{job_url}"
                except Exception as e:
                    print(f"Error extracting job URL for job #{i}: {e} \nurl: {full_url}")
                    full_url = "N/A"

                try:
                    job_page = await browser.new_page()
                    await job_page.goto(full_url)
                    await job_page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception as e:
                    print(f"Error loading job page for {title}: {e}")
                    continue

                try:
                    raw_text = await job_page.locator(".inner.clearfix.ck-rendered-content").inner_text()
                except:
                    raw_text = ""

                await job_page.close()

                description_sections = extract_sections(raw_text)

                job_data.append({
                    "Title": title.strip(),
                    "Location": location.replace(title, "").strip(),
                    "Posted": posted.strip(),
                    "URL": full_url.strip(),
                    "Description raw": description_sections,
                })
                print(f"[{i+1}/{total}] Scraped: {title.strip()}")

            # Try to go to the next page
            try:
                next_btn = page.locator("a[aria-label='Next']")
                if await next_btn.count() == 0:
                    print("No next button — stopping.")
                    break
                if await next_btn.get_attribute("aria-disabled") == "true":
                    print("Next button is disabled — end of pages.")
                    break
                await next_btn.click()
                await page.wait_for_timeout(2000)
                await page.wait_for_load_state("domcontentloaded")
                current_page += 1
            except Exception as e:
                print(f"Navigation to next page failed: {e}")
                break

        df = pd.DataFrame(job_data)
        df.to_excel(output_file, index=False)
        print(f"\nScraping complete. Saved to: {output_file}")
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1, help="Start page number")
    parser.add_argument("--end", type=int, default=5, help="End page number")
    parser.add_argument("--output", type=str, default="navair_jobs.xlsx", help="Output Excel file")
    args = parser.parse_args()

    asyncio.run(scrape_jobs(args.start, args.end, args.output))
