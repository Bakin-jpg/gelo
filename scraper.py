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
        # Ini adalah langkah kunci: skrip akan berhenti sejenak hingga JavaScript
        # selesai memuat dan menambahkan iframe ke dalam DOM.
        # Timeout diatur ke 30 detik.
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
            # Seharus
