import sys
from playwright.sync_api import sync_playwright, TimeoutError

# URL dari halaman yang ingin di-scrape
target_url = "https://kickass-anime.ru/one-piece-0948/"

def run(playwright):
    """Fungsi utama untuk menjalankan proses scraping."""
    # Kita menggunakan Chromium, tetapi bisa juga 'firefox' atau 'webkit'
    browser = playwright.chromium.launch()
    page = browser.new_page()

    try:
        print(f"Mencoba membuka URL: {target_url}")
        # Buka halaman target
        page.goto(target_url, timeout=60000) # Timeout 60 detik

        print("Halaman berhasil dimuat. Menunggu iframe muncul...")
        # Menunggu selector 'iframe' muncul di halaman.
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
            # Blok ini yang menyebabkan error sebelumnya.
            # Sekarang sudah diperbaiki dengan indentasi yang benar.
            print("Tag iframe tidak ditemukan setelah menunggu.")
            sys.exit(1)

    except TimeoutError:
        print("Gagal: Waktu habis saat menunggu iframe muncul. Mungkin halaman berubah atau lambat dimuat.")
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
