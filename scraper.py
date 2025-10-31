# scraper.py (Final Version with Smart Pagination & Robust Metadata)

import json
import time
import os
import re
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

DATABASE_FILE = "anime_database.json"
PAGINATION_THRESHOLD = 50 
EPISODE_BATCH_LIMIT = 10 # Batas cicilan per eksekusi

def load_database():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                print(f"Database '{DATABASE_FILE}' ditemukan dan dimuat.")
                return {show['show_url']: show for show in json.load(f)}
        except json.JSONDecodeError:
            print(f"[PERINGATAN] File database '{DATABASE_FILE}' rusak. Memulai dari awal.")
            return {}
    print(f"Database '{DATABASE_FILE}' tidak ditemukan. Akan membuat yang baru.")
    return {}

def save_database(data_dict):
    sorted_data = sorted(data_dict.values(), key=lambda x: x.get('title', ''))
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=4)
    print(f"\nDatabase berhasil disimpan ke '{DATABASE_FILE}'.")

def scrape_main_page_shows(page):
    url = "https://kickass-anime.ru/"
    print("\n=== TAHAP 1: MENGAMBIL DAFTAR ANIME DARI HALAMAN UTAMA ===")
    try:
        page.goto(url, timeout=120000)
        page.wait_for_selector('div.latest-update div.show-item', timeout=60000)
        
        last_height = page.evaluate("document.body.scrollHeight")
        while True:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height: break
            last_height = new_height

        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        shows = {}
        for item in soup.find_all('div', class_='show-item'):
            try:
                title_element = item.find('h2', class_='show-title').find('a')
                title = title_element.text.strip()
                show_url = "https://kickass-anime.ru" + title_element['href']
                if show_url not in shows:
                    shows[show_url] = {'title': title, 'show_url': show_url}
            except (AttributeError, IndexError): continue
        
        print(f"Menemukan {len(shows)} anime unik di halaman utama.")
        return list(shows.values())
    except Exception as e:
        print(f"[ERROR di Tahap 1] Gagal mengambil daftar anime: {e}")
        return []

def scrape_show_details(page, show_url):
    print(f"   - Mengambil metadata dari: {show_url}")
    details = {}
    try:
        page.goto(show_url, timeout=90000)
        page.wait_for_load_state('networkidle', timeout=30000)
        
        # Perbaikan untuk poster image
        try:
            poster_style = page.locator("div.banner-section div.v-image__image").first.get_attribute("style")
            if poster_style and 'url(' in poster_style:
                poster_url = re.search(r'url\(["\']?(.*?)["\']?\)', poster_style).group(1)
                details["poster_image_url"] = poster_url
        except Exception as e:
            print(f"     [PERINGATAN] Gagal mengambil poster: {e}")
        
        # Perbaikan untuk synopsis
        try:
            synopsis_element = page.locator("div.v-card__text div.text-caption").first
            if synopsis_element.is_visible():
                details["synopsis"] = synopsis_element.inner_text(timeout=5000)
        except Exception as e:
            print(f"     [PERINGATAN] Gagal mengambil synopsis: {e}")
        
        # Perbaikan untuk genres
        try:
            genre_elements = page.locator(".anime-info-card .v-card__text span.v-chip__content").all()
            if genre_elements:
                details["genres"] = [g.inner_text() for g in genre_elements]
        except Exception as e:
            print(f"     [PERINGATAN] Gagal mengambil genres: {e}")

        # Perbaikan untuk metadata lainnya
        try:
            info_texts = [info.inner_text() for info in page.locator(".anime-info-card .d-flex.mt-2.mb-3 div.text-subtitle-2").all()]
            details["type"] = next((text for text in info_texts if text in ["TV", "Movie", "OVA", "ONA", "Special"]), "N/A")
            details["year"] = next((text for text in info_texts if re.match(r'^\d{4}$', text)), "N/A")
        except Exception as e:
            print(f"     [PERINGATAN] Gagal mengambil info tambahan: {e}")
        
        print("     Metadata berhasil diambil.")
    except Exception as e:
        print(f"     [PERINGATAN] Gagal mengambil sebagian atau semua metadata: {e}")
    return details

def main():
    db_shows = load_database()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        latest_shows_list = scrape_main_page_shows(page)
        page.close()

        if not latest_shows_list:
            browser.close(); return
        
        print("\n=== TAHAP 2: MEMPROSES SETIAP ANIME DAN EPISODENYA ===")
        for show_summary in latest_shows_list:
            show_url = show_summary['show_url']
            
            if show_url not in db_shows:
                print(f"\nMemproses anime baru: '{show_summary['title']}'")
                page = browser.new_page()
                details = scrape_show_details(page, show_url)
                db_shows[show_url] = {**show_summary, **details, "episodes": []}
                page.close()
            else:
                print(f"\nMengecek episode untuk: '{show_summary['title']}'")

            page = browser.new_page()
            try:
                page.goto(show_url, timeout=90000)
                page.locator("a.pulse-button:has-text('Watch Now')").click()
                page.wait_for_selector("div.episode-item", timeout=60000)

                existing_ep_numbers = {ep['episode_number'] for ep in db_shows[show_url].get('episodes', [])}
                
                episodes_to_process_map = {}
                page_dropdown = page.locator("div.v-card__title .v-select").filter(has_text="Page")
                page_options_texts = ["default"]
                if page_dropdown.is_visible():
                    page_dropdown.click(timeout=10000)
                    page.wait_for_selector(".v-menu__content .v-list-item__title", state="visible")
                    page_options_texts = [opt.inner_text() for opt in page.locator(".v-menu__content .v-list-item__title").all()]
                    page.keyboard.press("Escape")
                
                for page_range in page_options_texts:
                    if page_range != "default":
                        current_page_text = page_dropdown.locator(".v-select__selection").inner_text()
                        if current_page_text != page_range:
                            print(f"         Navigasi ke halaman '{page_range}'...")
                            page_dropdown.click(force=True, timeout=10000)
                            page.wait_for_selector(".v-menu__content .v-list-item__title", state="visible")
                            page.locator(f".v-menu__content .v-list-item__title:has-text('{page_range}')").click()
                            page.wait_for_selector(".v-menu__content", state="hidden")
                            time.sleep(2) # Tunggu konten awal halaman muncul

                            # --- LOGIKA SCROLL BARU DI SINI ---
                            # Temukan kontainer yang bisa di-scroll untuk daftar episode
                            # Selector ini menargetkan card text yang berisi episode item
                            episode_list_container = page.locator("div.v-card__text").filter(has=page.locator("div.episode-item")).first
                            
                            if episode_list_container.is_visible():
                                print(f"         Meng-scroll untuk memuat semua episode di halaman '{page_range}'...")
                                last_height = episode_list_container.evaluate("el => el.scrollHeight")
                                while True:
                                    # Scroll ke bawah dalam kontainer
                                    episode_list_container.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                                    time.sleep(1.5) # Beri waktu untuk episode baru dimuat
                                    new_height = episode_list_container.evaluate("el => el.scrollHeight")
                                    if new_height == last_height:
                                        break
                                    last_height = new_height
                                print(f"         Selesai. Total tinggi scroll: {last_height}px")
                            else:
                                print(f"         [PERINGATAN] Kontainer scroll tidak ditemukan untuk halaman '{page_range}'. Mencoba tanpa scroll.")
                    
                    # Setelah scroll (atau jika tidak ada scroll), ambil semua episode yang terlihat
                    for ep_element in page.locator("div.episode-item").all():
                        ep_num = ep_element.locator("span.v-chip__content").inner_text()
                        if ep_num not in existing_ep_numbers:
                            episodes_to_process_map[ep_num] = page_range

                if not episodes_to_process_map:
                    print("   Tidak ada episode baru untuk di-scrape.")
                    continue

                episodes_to_scrape = sorted(list(episodes_to_process_map.keys()), key=lambda x: int(''.join(filter(str.isdigit, x.split()[-1])) or 0))

                print(f"   Ditemukan {len(episodes_to_scrape)} episode baru untuk diproses.")
                if len(episodes_to_scrape) > EPISODE_BATCH_LIMIT:
                     print(f"   Akan memproses {EPISODE_BATCH_LIMIT} episode saja (cicilan).")
                     episodes_to_scrape = episodes_to_scrape[:EPISODE_BATCH_LIMIT]

                for i, ep_num in enumerate(episodes_to_scrape):
                    print(f"      - Memproses iframe: {ep_num} ({i+1}/{len(episodes_to_scrape)})")
                    try:
                        target_page_range = episodes_to_process_map[ep_num]
                        current_page_text = page_dropdown.locator(".v-select__selection").inner_text() if page_dropdown.is_visible() else "default"

                        if target_page_range != "default" and target_page_range != current_page_text:
                            print(f"         Navigasi ke halaman '{target_page_range}'...")
                            page_dropdown.click(force=True, timeout=10000)
                            page.wait_for_selector(".v-menu__content .v-list-item__title", state="visible")
                            page.locator(f".v-menu__content .v-list-item__title:has-text('{target_page_range}')").click()
                            page.wait_for_selector(".v-menu__content", state="hidden"); time.sleep(2)
                            
                            # Scroll lagi jika perlu, karena kita pindah halaman
                            episode_list_container = page.locator("div.v-card__text").filter(has=page.locator("div.episode-item")).first
                            if episode_list_container.is_visible():
                                episode_list_container.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                                time.sleep(1.5)

                        # Klik episode yang ingin kita proses
                        ep_element = page.locator(f"div.episode-item:has-text('{ep_num}')").first
                        ep_element.click(timeout=15000)
                        
                        # Tunggu hingga player muncul dan video dimuat
                        try:
                            # Tunggu hingga player terlihat
                            page.wait_for_selector("div.player-container", state='visible', timeout=30000)
                            
                            # Tunggu hingga iframe muncul
                            page.wait_for_selector("div.player-container iframe", state='attached', timeout=30000)
                            
                            # Ambil iframe URL
                            iframe_element = page.locator("div.player-container iframe.player")
                            iframe_element.wait_for(state="visible", timeout=30000)
                            iframe_src = iframe_element.get_attribute('src')
                            
                            if iframe_src:
                                db_shows[show_url]['episodes'].append({
                                    "episode_number": ep_num, "episode_url": page.url, "iframe_url": iframe_src
                                })
                                print(f"         Berhasil mengambil iframe untuk {ep_num}")
                            else:
                                print(f"         [PERINGATAN] Tidak dapat mengambil iframe URL untuk {ep_num}")
                        except Exception as e:
                            print(f"         [PERINGATAN] Gagal menunggu iframe untuk {ep_num}: {e}")
                            
                            # Coba alternatif: coba ambil iframe langsung tanpa menunggu
                            try:
                                iframe_element = page.locator("iframe").first
                                if iframe_element.is_visible():
                                    iframe_src = iframe_element.get_attribute('src')
                                    if iframe_src:
                                        db_shows[show_url]['episodes'].append({
                                            "episode_number": ep_num, "episode_url": page.url, "iframe_url": iframe_src
                                        })
                                        print(f"         Berhasil mengambil iframe (alternatif) untuk {ep_num}")
                            except Exception as alt_e:
                                print(f"         [PERINGATAN] Metode alternatif juga gagal: {alt_e}")
                    except Exception as e:
                        print(f"        [PERINGATAN] Gagal memproses iframe untuk {ep_num}: {e}")
                
                db_shows[show_url]['episodes'].sort(key=lambda x: int(''.join(filter(str.isdigit, x.get('episode_number', '0').split()[-1])) or 0))

            except Exception as e:
                print(f"   [ERROR FATAL] Gagal memproses episode untuk '{show_summary['title']}'. Melewati. Detail: {e}")
            finally:
                page.close()

        browser.close()
        save_database(db_shows)

if __name__ == "__main__":
    main()
