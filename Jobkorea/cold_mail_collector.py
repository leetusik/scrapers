import csv
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import Page, Playwright, sync_playwright


class JobScraper:
    def __init__(self):
        self.base_url = "https://www.jobkorea.co.kr"
        self.search_url = (
            "https://www.jobkorea.co.kr/Search/"
            "?stext=si%20%EA%B0%9C%EB%B0%9C&ord=RelevanceDesc"
            "&careerType=1%2C2&careerMin=1&careerMax=6&tabType=recruit&Page_No="
        )
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.recruit_urls: Dict[str, str] = {}
        self.scrape_results: List[Tuple[str, str, str, str, str, str, str, str]] = (
            []
        )  # [(company, email, position_name, industry, len(employee), since(year), firm_size, homepage)]
        self.max_emails = 200  # Default value
        self.max_companies = 1000  # Default value
        self.max_companies_to_process = 1000  # Default value for email collection

    def set_max_emails(self, count: int) -> None:
        """Set the maximum number of emails to collect"""
        self.max_emails = count

    def set_max_companies(self, count: int) -> None:
        """Set the maximum number of companies to collect"""
        self.max_companies = count

    def set_companies_to_process(self, count: int) -> None:
        """Set the maximum number of companies to process when collecting emails"""
        self.max_companies_to_process = count

    def save_to_csv(self, filename: str) -> None:
        """Save collected data to CSV file"""
        with open(filename, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Company Name", "URL"])
            for name, url in self.recruit_urls.items():
                writer.writerow([name, url])

    def save_email_results(self, filename: str) -> None:
        """Save email collection results to CSV file"""
        with open(filename, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Company Name",
                    "Email",
                    "Position Name",
                    "Industry",
                    "Employees",
                    "Established Year",
                    "Company Size",
                    "Homepage",
                ]
            )
            writer.writerows(self.scrape_results)

    def process_job_listing(self, item) -> tuple[str, str]:
        """Extract company name and job URL from a listing item"""
        name_div = item.query_selector("div.list-section-corp")
        name = name_div.query_selector("a").text_content().strip()
        title_div = item.query_selector("div.information-title")
        link = title_div.query_selector("a").get_attribute("href")
        return name, self.base_url + link

    def process_page(self, page: Page, page_no: int, total_pages: int = 100) -> bool:
        """Process a single page of job listings. Returns False if no more listings."""
        url = self.search_url + str(page_no)
        page.goto(url)

        list_container = page.query_selector("article.list")
        if not list_container:
            print("No more job listings")
            return False

        list_items = list_container.query_selector_all("article.list-item")
        for item in list_items:
            if len(self.recruit_urls) >= self.max_companies:
                print(f"\nReached {self.max_companies} companies, ending process...")
                return False

            name, url = self.process_job_listing(item)
            self.recruit_urls[name] = url

        progress = (page_no / total_pages) * 100
        print(
            f"Page {page_no} processed. Progress: {progress:.1f}% | "
            f"Companies collected: {len(self.recruit_urls)}/{self.max_companies}"
        )
        return True

    def extract_email(self, text: str) -> Optional[str]:
        """Extract email from text using regex"""
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        match = re.search(email_pattern, text)
        return match.group(0).strip() if match else None

    def collect_email_from_page(self, page: Page, company: str, url: str) -> bool:
        """Collect email and other information from a job posting page. Returns False if should stop."""
        try:
            page.goto(url)

            # Check for security page
            security_check = page.query_selector("p.reasonExp")
            if security_check and "보안정책" in security_check.text_content():
                print("\n보안 체크 페이지 감지! 수동으로 처리해주세요...")
                time.sleep(30)  # Wait for manual intervention

                # Check if still on security page
                security_check = page.query_selector("p.reasonExp")
                while security_check and "보안정책" in security_check.text_content():
                    print("아직 보안 체크가 필요합니다. 계속 대기중...")
                    time.sleep(10)
                    security_check = page.query_selector("p.reasonExp")

                print("보안 체크 통과, 계속 진행합니다.")

            email_element = page.query_selector("span.tahoma a.devChargeEmail")

            if email_element:
                email_text = email_element.text_content()
                email = self.extract_email(email_text)
                if email:
                    print(f"Found email for {company}: {email}")

                    # 1. 직종명
                    position_name = ""
                    position_element = page.query_selector(
                        "article.artReadJobSum h3.hd_3"
                    )
                    if position_element:
                        position_name = (
                            position_element.text_content()
                            .strip()
                            .split("\n")[-1]
                            .strip()
                        )
                    print(f"Position name: {position_name}")

                    # Company info from tbList
                    company_info = {
                        "industry": "",
                        "employees": "",
                        "established": "",
                        "company_size": "",
                        "homepage": "",
                    }

                    # Find all dt/dd pairs in company info section
                    info_list = page.query_selector("div.tbCol.tbCoInfo dl.tbList")
                    if info_list:
                        dt_elements = info_list.query_selector_all("dt")
                        dd_elements = info_list.query_selector_all("dd")

                        for dt, dd in zip(dt_elements, dd_elements):
                            label = dt.text_content().strip()

                            if "산업(업종)" in label:
                                company_info["industry"] = (
                                    dd.query_selector("text").text_content().strip()
                                )
                            elif "사원수" in label:
                                employees = dd.query_selector("span.tahoma")
                                if employees:
                                    company_info["employees"] = (
                                        employees.text_content().strip()
                                    )
                            elif "설립년도" in label:
                                established = dd.query_selector("span.tahoma")
                                if established:
                                    company_info["established"] = (
                                        established.text_content().strip()
                                    )
                            elif "기업형태" in label:
                                company_info["company_size"] = (
                                    dd.text_content()
                                    .replace("\n", " ")
                                    .strip()
                                    .split()[0]  # Only take the first part
                                )
                            elif "홈페이지" in label:
                                homepage = dd.query_selector("a.devCoHomepageLink")
                                if homepage:
                                    company_info["homepage"] = homepage.get_attribute(
                                        "href"
                                    )

                    print(f"Industry: {company_info['industry']}")
                    print(f"Employees: {company_info['employees']}")
                    print(f"Established: {company_info['established']}")
                    print(f"Company Size: {company_info['company_size']}")
                    print(f"Homepage: {company_info['homepage']}")

                    self.scrape_results.append(
                        (
                            company,
                            email,
                            position_name,
                            company_info["industry"],
                            company_info["employees"],
                            company_info["established"],
                            company_info["company_size"],
                            company_info["homepage"],
                        )
                    )

                    if len(self.scrape_results) >= self.max_emails:
                        print(f"\nReached {self.max_emails} results, ending process...")
                        return False
                else:
                    print(f"No valid email format found for {company}")
            else:
                print(f"No email element found for {company}")

            return True

        except Exception as e:
            print(f"Error processing {company}: {str(e)}")
            return True

    def collect_urls(self) -> None:
        """Collect all job posting URLs"""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            # Initial page load and wait for login
            page.goto(self.search_url + "1")
            print("Please login now...")
            time.sleep(60)

            # Scrape all pages
            page_no = 1
            while self.process_page(page, page_no):
                page_no += 1
                time.sleep(2)

            # Save results
            urls_filename = f"recruit_urls_{self.timestamp}.csv"
            self.save_to_csv(urls_filename)
            print(f"\nURLs saved to {urls_filename}")
            print(f"Total companies collected: {len(self.recruit_urls)}")

            browser.close()

    def collect_emails_from_csv(self, csv_filename: str) -> None:
        """Process URLs from CSV file to collect emails"""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            # Initial page load and wait for login
            page.goto(self.base_url)
            print("Please login now...")
            time.sleep(60)

            # Count total companies to process
            total_to_process = min(
                self.max_companies_to_process,
                sum(
                    1 for _ in csv.DictReader(open(csv_filename, "r", encoding="utf-8"))
                ),
            )

            # Read URLs from CSV
            with open(csv_filename, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, 1):
                    if idx > self.max_companies_to_process:
                        print(
                            f"\nReached maximum companies to process ({self.max_companies_to_process})"
                        )
                        break

                    company = row["Company Name"]
                    url = row["URL"]
                    progress = (idx / total_to_process) * 100
                    print(
                        f"\nProcessing {company}... ({progress:.1f}% | {idx}/{total_to_process} | "
                        f"Emails collected: {len(self.scrape_results)}/{self.max_emails})"
                    )

                    if not self.collect_email_from_page(page, company, url):
                        break  # Stop if we've reached max_emails

                    # time.sleep(random.randint(1, 3)

            browser.close()

            # Save results
            results_filename = f"email_results_{self.timestamp}.csv"
            self.save_email_results(results_filename)
            print(f"\nResults saved to {results_filename}")
            print(f"Total emails collected: {len(self.scrape_results)}")


def main():
    scraper = JobScraper()

    # Choose operation mode
    mode = input("Enter mode (1 for collect URLs, 2 for collect emails): ")

    if mode == "1":
        # Set maximum number of companies to collect
        try:
            max_companies = int(
                input("Enter number of companies to collect (default 1000): ") or "1000"
            )
            scraper.set_max_companies(max_companies)
        except ValueError:
            print("Invalid input, using default value of 1000")
            scraper.set_max_companies(1000)

        # Collect URLs
        scraper.collect_urls()
    elif mode == "2":
        # Set maximum number of emails to collect
        try:
            max_emails = int(
                input("Enter number of emails to collect (default 200): ") or "200"
            )
            scraper.set_max_emails(max_emails)
        except ValueError:
            print("Invalid input, using default value of 200")
            scraper.set_max_emails(200)

        # Set maximum number of companies to process
        try:
            max_companies = int(
                input("Enter number of companies to process (default 1000): ") or "1000"
            )
            scraper.set_companies_to_process(max_companies)
        except ValueError:
            print("Invalid input, using default value of 1000")
            scraper.set_companies_to_process(1000)

        # Collect emails from existing CSV
        csv_filename = "recruit_urls_20250207_112942.csv"
        scraper.collect_emails_from_csv(csv_filename)
    else:
        print("Invalid mode selected")


if __name__ == "__main__":
    main()
