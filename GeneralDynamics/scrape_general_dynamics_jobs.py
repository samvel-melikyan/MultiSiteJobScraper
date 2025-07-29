import asyncio
from playwright.async_api import async_playwright, expect
import pandas as pd
from bs4 import BeautifulSoup


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

    # Convert lists to strings
    for key in sections:
        sections[key] = "\n".join(sections[key]).strip()

    return sections

job_levels = ["entry", "mid", "senior", "lead", "manager", "director", "executive", "internship", "intern", "associate"]

async def scrape_jobs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
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
                if i == 3:
                    break

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

                description_sections = extract_sections_from_html(raw_html)

                job_entry = {
                    "Title": title,
                    "Location": location,
                    "Job ID": job_id.replace("ID ", ""),
                    "Role Type": role_type.replace("Remote Option ", ""),
                    "Employment Type": employment_type.replace("Employment Type ", ""),
                    "Category": category.replace("Category ", ""),
                    "Level": str([level for level in job_levels if level in title.lower()]).strip("[]").replace("'", ""),
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
            last_page = await next_page.is_disabled()
            print(f"Page {current_page} of {max_page}")

            # Limit for dev/debug — remove to scrape full site
            if int(current_page) == 1:
                break

            if last_page:
                break
            await next_page.click()

        # Save to Excel
        df = pd.DataFrame(job_data)
        df.to_excel("general_dynamics_jobs.xlsx", index=False)
        print("\nSaved to general_dynamics_jobs.xlsx")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape_jobs())
