import csv
import re
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

base_url = "https://www.kata.or.kr/v2/03_member/sub0301_memberSearch.asp"
detail_url = "https://www.kata.or.kr/v2/03_member/sub0301_memberSearchPopup.asp"


def extract_data_from_page(page):
    data = []

    # Wait for the table and tbody to be present
    page.wait_for_selector("table tbody", state="attached")
    page.wait_for_load_state("networkidle")

    tbody = page.locator("tbody")
    trs = tbody.locator("tr")

    try:
        count = trs.count()

        for i in range(count):
            tr = trs.nth(i)
            onclick = tr.get_attribute("onclick")
            if onclick:
                numbers = re.findall(r"'(\d+)'", onclick)
                if len(numbers) == 2:
                    data.append({"businesscode": numbers[0], "custcode": numbers[1]})
    except Exception as e:
        print(f"Error processing page: {e}")
        # If there's an error, wait and try one more time
        time.sleep(2)
        page.reload()
        page.wait_for_selector("table tbody", state="attached")
        page.wait_for_load_state("networkidle")

        # Try again
        tbody = page.locator("tbody")
        trs = tbody.locator("tr")
        count = trs.count()

        for i in range(count):
            tr = trs.nth(i)
            onclick = tr.get_attribute("onclick")
            if onclick:
                numbers = re.findall(r"'(\d+)'", onclick)
                if len(numbers) == 2:
                    data.append({"businesscode": numbers[0], "custcode": numbers[1]})

    return data


def visit_member_page(page, businesscode, custcode):
    try:
        member_url = f"{detail_url}?businesscode={businesscode}&custcode={custcode}"
        page.goto(member_url)
        page.wait_for_load_state("networkidle")

        # Wait for table to be visible
        page.wait_for_selector("table.talbe_01", state="visible", timeout=5000)
        time.sleep(0.5)

        # Initialize data dictionary
        member_data = {
            "businesscode": businesscode,
            "custcode": custcode,
            "company": "",
            "representative": "",
            "address": "",
            "tel": "",
            "email": "",
            "website": "",
        }

        # Process each field with timeout protection
        try:
            # Company name
            if (
                company := page.locator("td:has-text('회원사명') + td")
                .first.inner_text(timeout=5000)
                .strip()
            ):
                member_data["company"] = company

            # Representative
            if (
                rep := page.locator("td:has-text('대표자') + td")
                .first.inner_text(timeout=5000)
                .strip()
            ):
                member_data["representative"] = rep

            # Address
            if (
                addr := page.locator("td:has-text('주소') + td")
                .first.inner_text(timeout=5000)
                .strip()
            ):
                member_data["address"] = addr

            # Phone
            if (
                tel := page.locator("td:has-text('전화') + td")
                .first.inner_text(timeout=5000)
                .strip()
            ):
                member_data["tel"] = tel

            # Email
            if (
                email := page.locator("td:has-text('전자우편') + td")
                .first.inner_text(timeout=5000)
                .strip()
            ):
                member_data["email"] = email

            # Website
            website_cell = page.locator("td:has-text('누리집') + td").first
            if website := website_cell.inner_text(timeout=5000).strip():
                member_data["website"] = website
            else:
                return None  # Skip if no website

            print(member_data)
            return member_data

        except Exception as e:
            print(f"Error processing member {businesscode}-{custcode}: {str(e)}")
            return None

    except Exception as e:
        print(f"Error visiting member page {businesscode}-{custcode}: {str(e)}")
        return None


def save_to_csv(member_details):
    if not member_details:
        print("No data to save")
        return

    # Generate filename with current timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"kata_members_{timestamp}.csv"

    # Write to CSV
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "businesscode",
            "custcode",
            "company",
            "representative",
            "address",
            "tel",
            "email",
            "website",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(member_details)

    print(f"\nData saved to {filename}")


def main():
    all_members = []
    member_details = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            page.goto(base_url)
            page.wait_for_load_state("networkidle")

            total_pages = 52

            # First collect all member codes
            for page_num in range(1, total_pages + 1):
                print(f"Processing page {page_num}/{total_pages}")

                page_data = extract_data_from_page(page)
                all_members.extend(page_data)

                if page_num < total_pages:
                    page.evaluate(f"pageSend({page_num + 1})")
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)

            print(f"\nTotal members found: {len(all_members)}")

            # Process members with progress tracking
            total_members = len(all_members)
            for i, member in enumerate(all_members, 1):
                print(f"\nProcessing member {i}/{total_members}")
                member_detail = visit_member_page(
                    page, member["businesscode"], member["custcode"]
                )
                if member_detail:
                    member_details.append(member_detail)

                # Save progress every 50 members
                if i % 50 == 0:
                    save_to_csv(member_details)

        except Exception as e:
            print(f"Error in main process: {str(e)}")
        finally:
            browser.close()

    # Final save
    print(f"\nCollected details for {len(member_details)} members")
    save_to_csv(member_details)


if __name__ == "__main__":
    main()
