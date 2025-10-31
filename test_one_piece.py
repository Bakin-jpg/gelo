# scraper.py (Final Version with New Tab Logic)

import json
import time
import os
import re
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

DATABASE_FILE = "anime_database.json"
EPISODE_BATCH_LIMIT = 10 

def load_database():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return {show['show_url']: show for show in json.load(f)}
        except json.JSONDecodeError:
            return {}
    return {}

def save_database(data_dict):
    sorted_data = sorted(data_dict.values(), key=lambda x: x.get('title', ''))
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=4)
    print(f"\nDatabase berhasil disimpan ke '{DATABASE_FILE}'.")

def scrape_main_page_shows(page):
    # ... (Fungsi ini tidak berubah) ...
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


def scrape_show_details_and_episode_urls(page, show_url):
    print(f"   - Mengambil detail dan daftar URL episode dari: {show_url}")
    details = {}
    episode_urls = {}
    try:
        page.goto(show_url, timeout=90000)
        
        # Ambil Metadata
        details["poster_image_url"] = page.locator("div.banner-section div.v-image__image").first.get_attribute("style").split('url("')[1].split('")')[0]
        details["synopsis"] = page.locator("div.v-card__text div.text-caption").inner_text(timeout=5000)
        info_texts = [info.inner_text() for info in page.locator(".anime-info-card .d-flex.mt-2.mb-3 div.text-subtitle-2").all()]
        details["type"] = next((text for text in info_texts if text in ["TV", "Movie", "OVA", "ONA", "Special"]), "N/A")
        details["year"] = next((text for text in info_texts if re.match(r'^\d{4}$', text)), "N/A")
        print("     Metadata berhasil diambil.")
        
        page.locator("a.pulse-button:has-text('Watch Now')").click()
        page.wait_for_selector("div.episode-item", timeout=60000)
        
        # Kumpulkan semua URL episode dari semua halaman paginasi
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
                    page_dropdown.click(force=True); time.sleep(0.5)
                    page.locator(f".v-menu__content .v-list-item__title:has-text('{page_range}')").click()
                    page.wait_for_selector(".v-menu__content", state="hidden"); time.sleep(1.5)
            
            # Ambil URL dari link, bukan elemennya
            for ep_element in page.locator("a.episode-item").all():
                ep_num = ep_element.locator("span.v-chip__content").inner_text()
                ep_url = "https://kickass-anime.ru" + ep_element.get_attribute("href")
                episode_urls[ep_num] = ep_url

    except Exception as e:
        print(f"     [PERINGATAN] Gagal mengambil detail/URL episode: {e}")
    
    print(f"   Ditemukan total {len(episode_urls)} URL episode.")
    return details, episode_urls

def scrape_iframe_from_url(browser, episode_url):
    """Buka URL episode di tab baru dan ambil iframenya."""
    iframe_src = "Not Found"
    page = browser.new_page()
    try:
        page.goto(episode_url, timeout=90000)
        
        # Tunggu iframe utama dengan timeout panjang
        main_iframe_selector = "div.player-container iframe[src*='krussdomi'], div.player-container iframe[src*='cat-player']"
        main_iframe_locator = page.locator(main_iframe_selector)
        main_iframe_locator.wait_for(state="attached", timeout=90000)
        
        iframe_src = main_iframe_locator.get_attribute('src')
    except Exception as e:
        print(f"        [PERINGATAN] Gagal mengambil iframe dari {episode_url}: {e}")
        page.screenshot(path=f"error_iframe_{time.time()}.png")
    finally:
        page.close()
    return iframe_src

def main():
    db_shows = load_database()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        main_page = browser.new_page()

        latest_shows_list = scrape_main_page_shows(main_page)
        main_page.close()

        if not latest_shows_list:
            browser.close(); return
        
        print("\n=== TAHAP 2: MEMPROSES SETIAP ANIME DAN EPISODENYA ===")
        for show_summary in latest_shows_list:
            show_url = show_summary['show_url']
            
            page = browser.new_page()
            try:
                details, episode_urls_map = scrape_show_details_and_episode_urls(page, show_url)
                
                if not episode_urls_map: # Jika gagal mengambil daftar episode, lewati
                    print(f"   Tidak ada episode yang ditemukan untuk '{show_summary['title']}'. Melewati.")
                    continue
                
                # Update atau buat entri baru
                if show_url in db_shows:
                    db_shows[show_url].update(details)
                    print(f"\nMengecek episode untuk: '{show_summary['title']}'")
                else:
                    db_shows[show_url] = {**show_summary, **details, "episodes": []}
                    print(f"\nMemproses anime baru: '{show_summary['title']}'")
                
                existing_ep_numbers = {ep['episode_number'] for ep in db_shows[show_url].get('episodes', [])}
                episodes_to_scrape = {k: v for k, v in episode_urls_map.items() if k not in existing_ep_numbers}

                if not episodes_to_scrape:
                    print("   Tidak ada episode baru untuk di-scrape.")
                    continue
                
                # Urutkan episode yang akan di-scrape
                sorted_ep_to_scrape = sorted(episodes_to_scrape.items(), key=lambda item: int(''.join(filter(str.isdigit, item[0].split()[-1])) or 0))

                print(f"   Ditemukan {len(sorted_ep_to_scrape)} episode baru untuk diproses.")
                if len(sorted_ep_to_scrape) > EPISODE_BATCH_LIMIT:
                     print(f"   Akan memproses {EPISODE_BATCH_LIMIT} episode saja (cicilan).")
                     sorted_ep_to_scrape = sorted_ep_to_scrape[:EPISODE_BATCH_LIMIT]
                
                for i, (ep_num, ep_url) in enumerate(sorted_ep_to_scrape):
                    print(f"      - Memproses: {ep_num} ({i+1}/{len(sorted_ep_to_scrape)})")
                    iframe_url = scrape_iframe_from_url(browser, ep_url)
                    db_shows[show_url]['episodes'].append({
                        "episode_number": ep_num,
                        "episode_url": ep_url,
                        "iframe_url": iframe_url
                    })
                
                db_shows[show_url]['episodes'].sort(key=lambda x: int(''.join(filter(str.isdigit, x.get('episode_number', '0').split()[-1])) or 0))

            except Exception as e:
                print(f"   [ERROR FATAL] Gagal memproses '{show_summary['title']}'. Melewati. Detail: {e}")
            finally:
                page.close()

        browser.close()
        save_database(db_shows)

if __name__ == "__main__":
    main()
