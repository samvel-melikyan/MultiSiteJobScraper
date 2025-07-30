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


async def scrape_jobs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(12000)
        await page.goto("https://jobs.boeing.com/search-jobs")
        print("Launching jobs.boeing.com")
        print("Loading all jobs...")
        await page.wait_for_timeout(2000)

        job_data = []

        while True:
            try:
                jobs = page.locator("#search-results-list li")
            except TimeoutError:
                print("Timeout while trying to find job listings. Exiting...")
                break
            total = await jobs.count()
            print(f"Found {total} jobs")

            for i in range(total):
                try:
                    job = jobs.nth(i)
                except TimeoutError:
                    break

                try:
                    title = await job.locator("a span").inner_text()
                    url_suffix = await job.locator("a").get_attribute("href")
                    full_url = f"https://jobs.boeing.com{url_suffix}"
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
                    location = await job_page.locator(".job-description__job-location").inner_text()
                except TimeoutError:
                    location = "N/A"
                try:
                    posted_date = await job_page.locator(".job-description__job-info.job-date").inner_text()
                except TimeoutError:
                    posted_date = "N/A"
                try:
                    job_id = await job_page.locator(".job-description__job-info.job-id").inner_text()
                except TimeoutError:
                    job_id = "N/A"
                try:
                    category = await job_page.locator(".job-description__job-info.job-category").inner_text()
                except TimeoutError:
                    category = "N/A"
                try:
                    role_type = await job_page.locator(".job-description__job-info.job-role-type").inner_text()
                except TimeoutError:
                    role_type = "N/A"
                try:
                    raw_html = await job_page.locator("#ats-description").inner_html()
                    raw_text = await job_page.locator("#ats-description").inner_text()
                except TimeoutError:
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
        df.to_excel("boeing_jobs.xlsx", index=False)
        print("\nSaved to boeing_jobs.xlsx")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape_jobs())
