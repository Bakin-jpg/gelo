# test_one_piece.py (Simplified & More Robust)

import time
from playwright.sync_api import sync_playwright, TimeoutError

def test_one_piece_flow():
    ONE_PIECE_URL = "https://kickass-anime.ru/one-piece-0948"
    EPISODE_TO_FIND = "EP 01"
    PAGE_RANGE_TO_FIND = "01-100"

    print("="*50)
    print("   MEMULAI PENGUJIAN ONE PIECE (PENDEKATAN BARU)   ")
    print("="*50)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print(f"1. Navigasi ke halaman detail: {ONE_PIECE_URL}")
            page.goto(ONE_PIECE_URL, timeout=90000)

            print("2. Mencari dan mengklik 'Watch Now'...")
            page.locator("a.pulse-button:has-text('Watch Now')").click()

            print("3. Menunggu daftar episode awal muncul...")
            page.wait_for_selector("div.episode-item", timeout=60000)
            print("   Daftar episode awal berhasil dimuat.")

            page_dropdown = page.locator("div.v-card__title .v-select").filter(has_text="Page")
            
            print(f"4. Mencari dan mengklik halaman paginasi '{PAGE_RANGE_TO_FIND}'...")
            page_dropdown.click(force=True, timeout=10000)
            page.wait_for_selector(".v-menu__content .v-list-item__title", state="visible")
            page.locator(f".v-menu__content .v-list-item__title:has-text('{PAGE_RANGE_TO_FIND}')").click()
            
            print("5. Menunggu dropdown tertutup...")
            page.wait_for_selector(".v-menu__content", state="hidden")
            time.sleep(2)

            print(f"6. Mencari dan mengklik elemen '{EPISODE_TO_FIND}'...")
            ep_element = page.locator(f"div.episode-item:has-text('{EPISODE_TO_FIND}')").first
            ep_element.wait_for(state="visible", timeout=10000)
            ep_element.click()

            # --- LOGIKA MENUNGGU YANG DIPERBAIKI ---
            print("7. Menunggu iframe APAPUN muncul di dalam player container...")
            iframe_selector = "div.player-container iframe"
            
            # Beri waktu 90 detik
            page.wait_for_selector(iframe_selector, state="attached", timeout=90000)
            print("   Iframe terdeteksi di dalam DOM.")
            
            iframe_locator = page.locator(iframe_selector).first
            iframe_locator.wait_for(state="visible", timeout=30000)
            print("   Iframe terlihat di halaman.")

            iframe_src = iframe_locator.get_attribute('src')
            if not iframe_src:
                raise Exception("Iframe ditemukan, tetapi atribut 'src' kosong atau tidak ada.")

            print(f"   BERHASIL! URL Iframe yang ditemukan: {iframe_src}")

        except Exception as e:
            print("\n" + "="*20 + " TEST GAGAL " + "="*20)
            print(f"Detail Error: {e}")
            
            screenshot_path = "one_piece_failure.png"
            html_path = "one_piece_failure.html"
            page.screenshot(path=screenshot_path, full_page=True)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content())
                
            print(f"Screenshot disimpan sebagai: {screenshot_path}")
            print(f"Konten HTML disimpan sebagai: {html_path}")
            
            raise e
        finally:
            print("Menutup browser...")
            browser.close()

if __name__ == "__main__":
    test_one_piece_flow()
