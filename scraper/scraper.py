import re
import pandas as pd
from collections import defaultdict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


class Scraper:
    def __init__(self, url: str, company: str, start_page=1, end_page="max", output_file=None) -> None:
        self.url = url
        self.company = company
        self.start_page = start_page
        self.end_page = end_page
        self.output_file = output_file
        self.job_data = []
        self.total_pages = 0
        self.total_jobs = 0
        self.jobs = None
        self.page = None
        self.browser = None

    async def goto_page(self, p: async_playwright, headless=True):
        print(f"Launching {self.company}")
        self.browser = await p.chromium.launch(headless=headless)
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(10000)

        try:
            await self.page.goto(self.url, timeout=60000, wait_until="domcontentloaded")
        except Exception:
            print("Timeout while loading page. Retrying with unlimited timeout...")
            try:
                await self.page.goto(self.url, timeout=0, wait_until="domcontentloaded")
            except Exception as e:
                print(f"Failed to load the page after retry: {e}")
                await self.browser.close()
                raise

        await self.page.wait_for_timeout(1000)

    async def goto_job_page(self):
        try:
            context = await self.browser.new_context()
            job_page = await context.new_page()
            job_url = self.job_data[-1]["URL"]
            try:
                await job_page.goto(job_url, timeout=10000, wait_until="domcontentloaded")
            except Exception:
                print("Timeout on job page. Retrying with unlimited timeout...")
                await job_page.goto(job_url, timeout=0, wait_until="domcontentloaded")

            await job_page.wait_for_timeout(500)
            return job_page
        except Exception as e:
            print(f"Error loading job page for '{self.job_data[-1]['Title']}': {e}")
            return None

    async def goto_next_page(self, next_btn_locator, current_page):

        try:
            if await next_btn_locator.get_attribute("disabled") is not None or int(current_page) >= int(self.end_page):
                print("Reached the end page.")
                return False
            await next_btn_locator.click()
            await self.page.wait_for_timeout(2000)
            await self.page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            print(f"Could not navigate to next page: {e}")
            return False

    async def define_total_pages(self, total_pages_locator):
        if isinstance(total_pages_locator, int):
            self.total_pages = total_pages_locator
        else:
            total_pages = await total_pages_locator.inner_text()
            self.total_pages = int(''.join(re.findall(r'\d+', total_pages)))
        self.define_end_page()
        self.define_start_page()

    async def goto_starting_page(self, input_area):
        if not isinstance(self.start_page, int):
            self.start_page = self.define_start_page()
        if self.start_page > 1:
            await input_area.fill(str(self.start_page))
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(2000)

    def define_end_page(self):
        if self.end_page == "half":
            self.end_page = self.total_pages // 2
        elif isinstance(self.end_page, int):
            pass
        elif self.end_page == "max":
            self.end_page = self.total_pages
        else:
            self.end_page = self.total_pages

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
        # Define canonical headers
        known_headers = {
            "description": "Description",
            "skills": "Skills",
            "basic qualifications": "Basic Qualifications",
            "desired skills": "Desired Skills"
        }

        def normalize_header(header):
            """Map similar headers to a known one if similarity is high enough."""
            header_lower = header.lower()
            for key, canonical in known_headers.items():
                # Simple containment check
                if key in header_lower:
                    return canonical
                # Fuzzy match for near matches
                if SequenceMatcher(None, key, header_lower).ratio() > 0.75:
                    return canonical
            return header.strip()

        lines = text.splitlines()
        sections = {}
        current_header = "Job Description (Raw)"
        sections[current_header] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.endswith(":") and len(stripped.split()) < 10:
                raw_header = stripped.rstrip(":").strip()
                current_header = normalize_header(raw_header)
                if current_header not in sections:
                    sections[current_header] = []
            else:
                sections[current_header].append(stripped)

        # Join lines for each section
        for key in sections:
            sections[key] = "\n".join(sections[key]).strip()

        # Clean and store into job_data
        for key, value in sections.items():
            cleaned = re.sub(r"\bapply now\b", "", value, flags=re.IGNORECASE).strip()
            self.job_data[-1][key] = cleaned


    def extract_sections_from_html(self, html: str):
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

    async def safe_get(self, selector, page=None, method="inner_text", attribute=None):
        """
        Safely get data from a selector.
        Supported methods:
          - "inner_text"   → returns text inside element
          - "inner_html"   → returns HTML inside element
          - "get_attribute" → returns element attribute (needs 'attribute' param)
        Returns "N/A" if not found or error occurs.
        """
        if page is None:
            page = self.page
        locator = page.locator(selector)

        try:
            if method == "inner_text":
                return await locator.inner_text()
            elif method == "inner_html":
                return await locator.inner_html()
            elif method == "get_attribute" and attribute:
                return await locator.get_attribute(attribute)
            else:
                return "N/A"  # Unsupported method or missing attribute
        except Exception:
            return "N/A"