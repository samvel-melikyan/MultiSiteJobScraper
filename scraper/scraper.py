import re
import pandas as pd
from collections import defaultdict
from playwright.async_api import async_playwright

class Scraper:
    def __init__(self, url: str, company: str, start_page=1, end_page="max", output_file=None) -> None:
        self.url = url
        self.page = None
        self.company = company
        self.start_page = start_page
        self.end_page = end_page
        self.output_file = output_file
        self.job_data = []
        self.total_pages = 0
        self.total_jobs = 0
        self.jobs = None
        self.browser = None

    async def goto_page(self, p: async_playwright, headless=True):
        self.browser = await p.chromium.launch(headless=headless)
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(10000)
        await self.page.goto(self.url, timeout=15000)
        print(f"Launching {self.company}")
        await self.page.wait_for_timeout(1000)

    async def goto_job_page(self):
        try:
            context = await self.browser.new_context()
            job_page = await context.new_page()
            await job_page.goto(self.job_data[-1]["URL"], timeout=20000)
            await job_page.wait_for_load_state("domcontentloaded", timeout=20000)
            return job_page
        except Exception as e:
            print(f"Error loading job page for {self.job_data[-1]['Title']}: {e}")
            return None

    async def goto_next_page(self, next_btn_locator, end_page, current_page):
        try:
            if await next_btn_locator.get_attribute("disabled") or int(current_page) >= int(end_page):
                return False
            await next_btn_locator.click()
            await self.page.wait_for_timeout(2000)  # Give time for page load
            await self.page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            print(f"Could not navigate to next page: {e}")
            return False

    async def page_tracker(self, total_pages_locator):
        total_pages = await total_pages_locator.inner_text()
        self.total_pages = int(''.join(re.findall(r'\d+', total_pages)))
        if self.end_page == "half":
            self.end_page = self.total_pages // 2
        elif self.start_page == "half":
            self.start_page = (self.total_pages // 2) + 1

    def define_end_page(self):
        if self.end_page == "half":
            return self.total_pages // 2
        elif isinstance(self.end_page, int):
            return self.end_page
        elif self.end_page == "max":
            return self.total_pages
        raise ValueError("Invalid end page value")

    def define_start_page(self):
        if self.start_page == "half":
            return (self.total_pages // 2) + 1
        return self.start_page

    async def find_jobs(self, jobs_locator, current_page):
        print(f"Scraping page {current_page} of {self.total_pages}")
        self.jobs = jobs_locator
        self.total_jobs = await self.jobs.count()
        print(f"Found {self.total_jobs} jobs on page {current_page}")

    def extract_sections(self, text):
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

        for key, value in sections.items():
            cleaned = re.sub(r"\bapply now\b", "", value, flags=re.IGNORECASE).strip()
            self.job_data[-1][key] = cleaned

    def save_to_excel(self):
        df = pd.DataFrame(self.job_data)
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

        if self.output_file:
            merged_df.to_excel(self.output_file, index=False)
            print(f"Data saved to {self.output_file}")
        else:
            print("No output file specified. Data not saved.")