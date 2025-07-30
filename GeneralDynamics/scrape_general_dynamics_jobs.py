import asyncio
from playwright.async_api import async_playwright
import pandas as pd



def extract_salary_range(raw_text):
    start_phrase = "Target salary range:"
    end_phrase = "This estimate"

    try:
        start = raw_text.index(start_phrase) + len(start_phrase)
        end = raw_text.index(end_phrase, start)
        return raw_text[start:end].strip()
    except ValueError:
        return None  # or log error / raise custom exception

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

async def scrape_jobs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(10000)
        await page.goto("https://gdmissionsystems.com/careers/job-search")
        print("Launching gdmissionsystems.com")
        print("Loading all jobs...")
        await page.wait_for_timeout(2000)

        job_data = []

        while True:
            try:
                jobs = page.locator("div .career-search-result.col-12")
            except TimeoutError:
                print("Timeout while trying to find job listings. Exiting...")
                break
            total = await jobs.count()
            print(f"Found {total} jobs")

            for i in range(total):
                if i == 5:
                    continue

                try:
                    job = jobs.nth(i)
                except TimeoutError:
                    break

                try:
                    title = await job.locator("h4").inner_text()
                    full_url = await job.get_by_text("VIEW JOB DESCRIPTION").get_attribute("href")
                    # full_url = f"https://gdmissionsystems.com/careers{url_suffix}"
                except Exception as e:
                    print(f"Error extracting job details for index {i}: {e}")
                    continue

                # Visit job page
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

            # Pagination
            pagination = page.locator(".pagination")
            current_page = int(await pagination.locator(".page-item.active").inner_text())
            next_page = pagination.get_by_text("›")
            max_page = int(await pagination.get_by_text("»").get_attribute("data-page-number")) + 1
            print(f"Page {current_page} of {max_page}")

            try:
                await next_page.click()
            except:
                break

        # Save to Excel
        df = pd.DataFrame(job_data)
        df.to_excel("general_dynamics_jobs.xlsx", index=False)
        print("\nSaved to general_dynamics_jobs.xlsx")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape_jobs())
