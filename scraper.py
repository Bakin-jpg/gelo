import sys
from playwright.sync_api import sync_playwright, TimeoutError

# URL target adalah halaman detail anime, ini sudah benar
target_url = "https://kickass-anime.ru/one-piece-0948/"

def run(playwright):
    """Fungsi utama untuk menjalankan proses scraping."""
    browser = playwright.chromium.launch()
    page = browser.new_page()

    try:
        print(f"Mencoba membuka URL: {target_url}")
        # 1. Buka halaman detail anime, tunggu sampai selesai dimuat
        page.goto(target_url, timeout=60000, wait_until='domcontentloaded')

        print("Halaman detail anime dimuat. Mencari tombol 'Watch Now'...")
        # 2. Cari tombol 'Watch Now'. Selector 'a.pulse-button' cukup spesifik.
        #    Playwright akan otomatis menunggu elemen ini muncul.
        watch_now_button = page.locator('a.pulse-button')

        print("Tombol ditemukan. Mengklik tombol 'Watch Now'...")
        # 3. Klik tombol tersebut. Playwright akan menunggu navigasi ke halaman baru selesai.
        watch_now_button.click()
        
        # Sekarang kita berada di halaman episode/pemutar video
        print("Halaman episode dimuat. Menunggu iframe muncul...")
        # 4. Di halaman baru ini, tunggu sampai iframe muncul
        iframe_element = page.wait_for_selector('iframe', timeout=30000)

        # Jika iframe ditemukan, ambil atribut 'src'-nya
        if iframe_element:
            iframe_url = iframe_element.get_attribute('src')
            if iframe_url:
                print(f"URL Iframe ditemukan: {iframe_url}")
            else:
                print("Iframe ditemukan tetapi tidak memiliki atribut 'src'.")
                sys.exit(1)
        else:
            # Bagian ini secara teknis tidak akan tercapai karena wait_for_selector akan error jika gagal
            print("Tag iframe tidak ditemukan setelah menunggu.")
            sys.exit(1)

    except TimeoutError as e:
        print(f"Gagal: Waktu habis saat menunggu elemen. Mungkin tombol 'Watch Now' atau iframe tidak muncul tepat waktu. Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Terjadi error: {e}")
        sys.exit(1)
    finally:
        # Selalu tutup browser setelah selesai
        browser.close()

# Menjalankan fungsi utama
with sync_playwright() as playwright:
    run(playwright)
