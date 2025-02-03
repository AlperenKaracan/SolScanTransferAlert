import winsound
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from bs4 import BeautifulSoup
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
import pyperclip
import os
import requests

TELEGRAM_BOT_TOKEN = ' '  # BotFather'dan aldığınız tokeni girmeniz gerekli
TELEGRAM_CHAT_ID = ' '   # Botun yazacağı Chat ID

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Telegram mesaj gönderme hatası: {response.text}")
    except Exception as e:
        print(f"Telegram mesaj gönderme sırasında hata oluştu: {e}")

def play_notification_sound():
    frequency = 1000
    duration = 2000
    try:
        winsound.Beep(frequency, duration)
    except RuntimeError as e:
        print(f"Ses çalma hatası: {e}")

def play_error_sound():
    frequency = 500
    duration = 1000
    try:
        winsound.Beep(frequency, duration)
    except RuntimeError as e:
        print(f"Ses çalma hatası: {e}")

def initialize_driver(headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        print("WebDriver başarıyla başlatıldı.")
        return driver
    except Exception as e:
        print(f"WebDriver başlatma hatası: {e}")
        play_error_sound()
        exit(1)

def load_page(driver, url):
    try:
        driver.get(url)
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - URL'ye gidiliyor: {url}")
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(5)
        print("Sayfa yüklendi ve transfer tablosu bulundu.")
        return driver.page_source
    except TimeoutException:
        print("Tablo bulunamadı veya sayfa yüklenemedi (Timeout).")
        play_error_sound()
        return None
    except Exception as e:
        print(f"Sayfa yükleme hatası: {e}")
        play_error_sound()
        return None

def refresh_page(driver):
    try:
        driver.refresh()
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Sayfa yenileniyor.")
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(5)
        print("Sayfa yenilendi ve transfer tablosu bulundu.")
        return driver.page_source
    except TimeoutException:
        print("Sayfa yenilenemedi veya tablo bulunamadı (Timeout).")
        play_error_sound()
        return None
    except Exception as e:
        print(f"Sayfa yenileme hatası: {e}")
        play_error_sound()
        return None

def extract_data_with_bs4(html):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    if not table:
        print("Tablo bulunamadı.")
        play_error_sound()
        return []
    data = []
    rows = table.find_all('tr')
    print(f"Bulunan toplam satır sayısı (başlık dahil): {len(rows)}")
    for row in rows[1:]:
        cols = row.find_all('td')
        if len(cols) < 9:
            print(f"Eksik veri bulunan satır atlanıyor. Sütun sayısı: {len(cols)}")
            continue
        signature = cols[1].get_text(strip=True)
        time_str = cols[2].get_text(strip=True)
        action = cols[3].get_text(strip=True)
        from_addr = cols[4].get_text(strip=True)
        to_addr = cols[5].get_text(strip=True)
        amount_str = cols[6].get_text(strip=True)
        value_str = cols[7].get_text(strip=True)
        token_cell = cols[8]
        try:
            value_str_clean = value_str.replace('$', '').replace(',', '').strip()
            value = float(value_str_clean)
            if value <= 5:
                continue
        except ValueError:
            print(f"Geçersiz 'Value' formatı: {value_str}. Satır atlanıyor.")
            continue
        try:
            amount_str_clean = amount_str.replace(',', '').strip()
            amount = float(amount_str_clean)
            if amount > 0:
                action_type = "Alım"
            elif amount < 0:
                action_type = "Satım"
            else:
                action_type = "Bilinmeyen"
        except ValueError:
            print(f"Geçersiz 'Amount' formatı: {amount_str}. Satır atlanıyor.")
            continue
        token_symbol = ''
        token_address = ''
        copy_icon = token_cell.find('svg', class_='lucide-copy')
        if copy_icon:
            a_tag = token_cell.find('a')
            if a_tag:
                token_symbol = a_tag.get_text(strip=True)
                token_href = a_tag.get('href', '')
                token_address = token_href.split('/')[-1] if '/' in token_href else ''
        else:
            token_symbol = token_cell.get_text(strip=True)
        if token_symbol.upper() in ['SOL', 'WSOL']:
            continue
        data.append({
            'Signature': signature,
            'Time': time_str,
            'Value': value,
            'Amount': amount,
            'Action Type': action_type,
            'Token Symbol': token_symbol,
            'Token Address': token_address
        })
    print(f"Çekilen toplam transfer sayısı: {len(data)}")
    return data

def copy_token_addresses(new_transfers):
    token_addresses = [
        transfer['Token Address']
        for transfer in new_transfers
        if transfer['Token Address'] and transfer['Token Symbol'].upper() not in ['SOL', 'WSOL']
    ]
    if token_addresses:
        clipboard_content = '\n'.join(token_addresses)
        try:
            pyperclip.copy(clipboard_content)
            print("Yeni Token Address'ler clipboard'a kopyalandı (SOL olmayanlar):")
            print(clipboard_content)
        except Exception as e:
            print(f"Clipboard kopyalama hatası: {e}")
            play_error_sound()
    else:
        print("Kopyalanacak SOL olmayan Token Address bulunamadı.")

def main():
    url = "https://solscan.io/account/TakipEdilecekCüzdanınCüzdanAdresiBurayaYazılacak#transfers" #Takip edilecek cüzdanın cüzdan adresi belirtilen kısma yazılmalı
    driver = initialize_driver(headless=False)
    previous_data = []
    try:
        html = load_page(driver, url)
        if not html:
            print("İlk sayfa yüklenemedi. Program sonlandırılıyor.")
            return
        current_data = extract_data_with_bs4(html)
        if not current_data:
            print("İlk veri çekilemedi veya tablo boş. Program sonlandırılıyor.")
            return
        previous_data = current_data
        while True:
            time.sleep(30)
            html = refresh_page(driver)
            if not html:
                print("Sayfa yenilenemedi, tekrar denenecek.")
                continue
            current_data = extract_data_with_bs4(html)
            if not current_data:
                print("Veri çekilemedi veya tablo boş.")
                continue
            if previous_data:
                previous_signatures = {item['Signature'] for item in previous_data}
                new_transfers = [item for item in current_data if item['Signature'] not in previous_signatures]
                if new_transfers:
                    print(f"{len(new_transfers)} yeni transfer bulundu!")
                    play_notification_sound()
                    for transfer in new_transfers:
                        if transfer['Action Type'].lower() == "satım":
                            action_type_display = "🔴 Satım"
                        elif transfer['Action Type'].lower() == "alım":
                            action_type_display = "🟢 Alım"
                        else:
                            action_type_display = transfer['Action Type']
                        print(f"İşlem Türü: {action_type_display}, Token: {transfer['Token Symbol']}, Token Adresi: {transfer['Token Address']}, Değer: {transfer['Value']}, Miktar: {transfer['Amount']}, Zaman: {transfer['Time']}, İşlem İmzası: {transfer['Signature']}")
                        message = (
                            f"<b>Alperen Transfer Bildirimi</b>\n" # istediğinizi yazabilirsiniz
                            f"📦 <b>Yeni Transfer Tespit Edildi!</b>\n"
                            f"<b>İşlem Türü:</b> {action_type_display}\n"
                            f"<b>Token:</b> {transfer['Token Symbol']}\n"
                            f"<b>Token Adresi:</b> <code>{transfer['Token Address']}</code>\n"
                            f"<b>Değer:</b> {transfer['Value']}\n"
                            f"<b>Miktar:</b> {transfer['Amount']}\n"
                            f"<b>Zaman:</b> {transfer['Time']}\n"
                            f"<b>İşlem İmzası:</b> {transfer['Signature']}"
                        )
                        send_telegram_message(message)
                    copy_token_addresses(new_transfers)
                else:
                    print("Yeni transfer bulunmadı.")
            else:
                print("Önceki veri mevcut değil, yeni veri kontrol edilemiyor.")
            previous_data = current_data
    except KeyboardInterrupt:
        print("Program durduruldu.")
    except Exception as e:
        print(f"Genel bir hata oluştu: {e}")
        play_error_sound()
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
