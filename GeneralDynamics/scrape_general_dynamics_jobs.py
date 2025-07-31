import asyncio
import argparse
from playwright.async_api import async_playwright
import pandas as pd
from collections import defaultdict


def extract_salary_range(raw_text):
    start_phrase = "Target salary range:"
    end_phrase = "This estimate"

    try:
        start = raw_text.index(start_phrase) + len(start_phrase)
        end = raw_text.index(end_phrase, start)
        return raw_text[start:end].strip()
    except ValueError:
        return None


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


job_levels = ["entry", "mid", "senior", "lead", "manager", "director", "executive", "internship", "intern", "associate"]


async def scrape_jobs(start_page, end_page, output_file):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(10000)
        await page.goto("https://gdmissionsystems.com/careers/job-search")
        print("Launching gdmissionsystems.com")
        print("Loading all jobs...")
        await page.wait_for_timeout(2000)

        job_data = []

        current_page = start_page
        while True:
            if current_page > end_page:
                break

            print(f"Scraping page {current_page}")

            jobs = page.locator("div .career-search-result.col-12")
            total = await jobs.count()
            print(f"Found {total} jobs on page {current_page}")

            for i in range(total):
                if i == 5:  # skipping job index 5 as per original code
                    continue

                try:
                    job = jobs.nth(i)
                    title = await job.locator("h4").inner_text()
                    full_url = await job.get_by_text("VIEW JOB DESCRIPTION").get_attribute("href")
                except Exception as e:
                    print(f"Error extracting job details for index {i} on page {current_page}: {e}")
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
                    location = await job_page.locator(".inset__location").inner_text()
                except:
                    location = "N/A"
                try:
                    job_id = await job_page.locator(".inset__id").inner_text()
                except:
                    job_id = "N/A"
                try:
                    category = await job_page.locator(".inset__category").inner_text()
                except:
                    category = "N/A"
                try:
                    role_type = await job_page.locator(".inset__company dd a").inner_text()
                except:
                    role_type = "N/A"
                try:
                    employment_type = await job_page.locator(".inset__type").inner_text()
                except:
                    employment_type = "N/A"
                try:
                    raw_html = await job_page.locator(".career-detail-description").inner_html()
                    raw_text = await job_page.locator(".career-detail-description").inner_text()
                except:
                    raw_html = ""
                    raw_text = ""

                await job_page.close()

                description_sections = extract_sections(raw_text)

                job_entry = {
                    "Title": title,
                    "Location": location,
                    "Job ID": job_id.replace("ID ", ""),
                    "Role Type": role_type.replace("Remote Option ", ""),
                    "Employment Type": employment_type.replace("Employment Type ", ""),
                    "Category": category.replace("Category ", ""),
                    "Level": str([level for level in job_levels if level in title.lower()]).strip("[]").replace("'", ""),
                    "Salary": extract_salary_range(raw_text),
                    "URL": full_url,
                    "Job Description (Raw)": raw_text
                }

                for key, value in description_sections.items():
                    job_entry[key] = value

                job_data.append(job_entry)
                print(f"[{i+1}/{total}] Scraped: {title}")

            try:
                next_btn = page.locator(".next")
                if await next_btn.get_attribute("disabled"):
                    print("Reached last page.")
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
        print(f"\n✅ Saved to {output_file}")

        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=str, default="max")  # now accepts "max"
    parser.add_argument("--output", type=str, default="general_dynamics_jobs.xlsx")
    args = parser.parse_args()

    if args.end == "max":
        end_page = float("inf")
    else:
        try:
            end_page = int(args.end)
        except ValueError:
            raise ValueError("`--end` must be an integer or 'max'.")

    asyncio.run(scrape_jobs(args.start, end_page, args.output))
