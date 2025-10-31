# scraper.py (Versi Scroll Kondisional - Tanpa Pagination)

import json
import time
import os
import re
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

DATABASE_FILE = "anime_database.json"
EPISODE_BATCH_LIMIT = 20 # Berapa banyak episode terbaru yang diambil per siklus
SCROLL_THRESHOLD = 50    # Jumlah episode minimal untuk memicu scroll

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
        
        try:
            poster_style = page.locator("div.banner-section div.v-image__image").first.get_attribute("style")
            if poster_style and 'url(' in poster_style:
                poster_url = re.search(r'url\(["\']?(.*?)["\']?\)', poster_style).group(1)
                details["poster_image_url"] = poster_url
        except Exception: pass
        
        try:
            synopsis_element = page.locator("div.v-card__text div.text-caption").first
            if synopsis_element.is_visible():
                details["synopsis"] = synopsis_element.inner_text(timeout=5000)
        except Exception: pass
        
        try:
            genre_elements = page.locator(".anime-info-card .v-card__text span.v-chip__content").all()
            if genre_elements:
                details["genres"] = [g.inner_text() for g in genre_elements]
        except Exception: pass

        try:
            info_texts = [info.inner_text() for info in page.locator(".anime-info-card .d-flex.mt-2.mb-3 div.text-subtitle-2").all()]
            details["type"] = next((text for text in info_texts if text in ["TV", "Movie", "OVA", "ONA", "Special"]), "N/A")
            details["year"] = next((text for text in info_texts if re.match(r'^\d{4}$', text)), "N/A")
        except Exception: pass
        
        print("     Metadata berhasil diambil.")
    except Exception as e:
        print(f"     [PERINGATAN] Gagal mengambil metadata: {e}")
    return details

def get_episode_number(ep_str):
    """Fungsi helper untuk mengambil angka dari string episode"""
    match = re.search(r'(\d+)', ep_str)
    return int(match.group(1)) if match else 0

def main():
    db_shows = load_database()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        latest_shows_list = scrape_main_page_shows(page)
        page.close()

        if not latest_shows_list:
            browser.close(); return
        
        print("\n=== TAHAP 2: MEMPROSES EPISODE TERBARU ===")
        for show_summary in latest_shows_list:
            show_url = show_summary['show_url']
            
            if show_url not in db_shows:
                print(f"\nMemproses anime baru: '{show_summary['title']}'")
                page = browser.new_page()
                details = scrape_show_details(page, show_url)
                db_shows[show_url] = {**show_summary, **details, "episodes": []}
                page.close()
            else:
                print(f"\nMengecek episode terbaru untuk: '{show_summary['title']}'")

            page = browser.new_page()
            try:
                page.goto(show_url, timeout=90000)
                page.locator("a.pulse-button:has-text('Watch Now')").click()
                page.wait_for_selector("div.episode-item", timeout=60000)

                # --- LOGIKA SCROLL KONDISIONAL TANPA PAGINATION ---
                print("   Memeriksa jumlah episode untuk menentukan kebutuhan scroll...")
                initial_episode_count = page.locator("div.episode-item").count()
                print(f"   Ditemukan {initial_episode_count} episode awal.")

                if initial_episode_count >= SCROLL_THRESHOLD:
                    print(f"   Jumlah episode >= {SCROLL_THRESHOLD}. Melakukan scroll untuk memuat lebih banyak...")
                    episode_container = page.locator("div.v-card__text").filter(has=page.locator("div.episode-item")).first
                    
                    if episode_container.is_visible():
                        while True:
                            count_before = episode_container.locator("div.episode-item").count()
                            episode_container.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                            time.sleep(2)  # Tunggu konten baru muncul
                            count_after = episode_container.locator("div.episode-item").count()
                            
                            if count_after == count_before:
                                print("   Scroll selesai, tidak ada episode baru yang dimuat.")
                                break
                            print(f"   Memuat lebih banyak episode... (total: {count_after})")
                    else:
                        print("   [PERINGATAN] Kontainer scroll tidak ditemukan, melanjutkan tanpa scroll.")
                else:
                    print("   Jumlah episode sedikit, tidak perlu scroll.")

                # --- LANJUTAN PROSES: AMBIL SEMUA EPISODE YANG TERLIHAT ---
                existing_ep_numbers = {ep['episode_number'] for ep in db_shows[show_url].get('episodes', [])}
                
                all_visible_episodes = page.locator("div.episode-item").all()
                
                new_episodes_to_process = []
                for ep_element in all_visible_episodes:
                    try:
                        ep_num_text = ep_element.locator("span.v-chip__content").inner_text()
                        if ep_num_text not in existing_ep_numbers:
                            new_episodes_to_process.append(ep_num_text)
                    except Exception:
                        continue
                
                if not new_episodes_to_process:
                    print("   Tidak ada episode baru untuk di-scrape.")
                    continue

                # Urutkan dari yang terbaru dan ambil sesuai batas
                new_episodes_to_process.sort(key=get_episode_number, reverse=True)
                
                episodes_to_scrape = new_episodes_to_process[:EPISODE_BATCH_LIMIT]
                print(f"   Ditemukan {len(new_episodes_to_process)} episode baru. Akan memproses {len(episodes_to_scrape)} teratas.")

                for i, ep_num in enumerate(episodes_to_scrape):
                    print(f"      - Memproses iframe: {ep_num} ({i+1}/{len(episodes_to_scrape)})")
                    try:
                        ep_element = page.locator(f"div.episode-item:has-text('{ep_num}')").first
                        ep_element.click(timeout=15000)
                        
                        try:
                            page.wait_for_selector("div.player-container iframe.player", state='attached', timeout=30000)
                            iframe_src = page.locator("div.player-container iframe.player").get_attribute('src')
                            
                            if iframe_src:
                                db_shows[show_url]['episodes'].append({
                                    "episode_number": ep_num, "episode_url": page.url, "iframe_url": iframe_src
                                })
                                print(f"         Berhasil mengambil iframe untuk {ep_num}")
                            else:
                                print(f"         [PERINGATAN] Tidak dapat mengambil iframe URL untuk {ep_num}")
                        except Exception as e:
                            print(f"         [PERINGATAN] Gagal menunggu iframe untuk {ep_num}: {e}")
                    except Exception as e:
                        print(f"        [PERINGATAN] Gagal memproses iframe untuk {ep_num}: {e}")
                
                # Urutkan kembali episode di database dari yang terlama ke terbaru
                db_shows[show_url]['episodes'].sort(key=lambda x: get_episode_number(x.get('episode_number', '0')))

            except Exception as e:
                print(f"   [ERROR FATAL] Gagal memproses episode untuk '{show_summary['title']}'. Melewati. Detail: {e}")
            finally:
                page.close()

        browser.close()
        save_database(db_shows)

if __name__ == "__main__":
    main()
