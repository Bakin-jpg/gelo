# test_one_piece.py

import time
from playwright.sync_api import sync_playwright, TimeoutError

def test_one_piece_flow():
    """
    Fungsi ini HANYA untuk menguji alur scraping One Piece EP 01
    dan menyediakan output debug yang detail jika gagal.
    """
    ONE_PIECE_URL = "https://kickass-anime.ru/one-piece-0948"
    EPISODE_TO_FIND = "EP 01"
    PAGE_RANGE_TO_FIND = "01-100"

    print("="*50)
    print("   MEMULAI PENGUJIAN KHUSUS UNTUK ONE PIECE   ")
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
            
            print("5. Menunggu dropdown tertutup setelah memilih halaman...")
            page.wait_for_selector(".v-menu__content", state="hidden")
            print("   Berhasil pindah ke halaman episode yang benar.")
            time.sleep(2) # Beri waktu ekstra untuk JS merender ulang daftar episode

            print(f"6. Mencari elemen '{EPISODE_TO_FIND}' di halaman saat ini...")
            ep_element = page.locator(f"div.episode-item:has-text('{EPISODE_TO_FIND}')").first
            ep_element.wait_for(state="visible", timeout=10000)
            print("   Elemen episode ditemukan. Mengklik...")
            ep_element.click()

            print("7. Menunggu iframe player UTAMA (bisa lama karena intro)...")
            # Selector spesifik yang mengabaikan intro player
            main_iframe_selector = "div.player-container iframe[src*='krussdomi'], div.player-container iframe[src*='cat-player']"
            main_iframe_locator = page.locator(main_iframe_selector)
            
            # Timeout 90 detik untuk memberi waktu intro selesai
            main_iframe_locator.wait_for(state="attached", timeout=90000)
            
            iframe_src = main_iframe_locator.get_attribute('src')
            print(f"   BERHASIL! Iframe player utama ditemukan: {iframe_src}")

        except TimeoutError as e:
            print("\n" + "="*20 + " TEST GAGAL (TIMEOUT) " + "="*20)
            print(f"Detail Error: {e}")
            
            # Ambil screenshot dan HTML untuk debugging
            screenshot_path = "one_piece_failure.png"
            html_path = "one_piece_failure.html"
            page.screenshot(path=screenshot_path, full_page=True)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content())
                
            print(f"Screenshot disimpan sebagai: {screenshot_path}")
            print(f"Konten HTML disimpan sebagai: {html_path}")
            print("Silakan periksa file-file ini di artifact GitHub Actions.")
            
            # GAGALKAN WORKFLOW SECARA EKSPLISIT
            raise e 
        finally:
            print("Menutup browser...")
            browser.close()

if __name__ == "__main__":
    test_one_piece_flow()
