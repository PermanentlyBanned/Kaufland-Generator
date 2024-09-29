import requests
import json
import time
import re
import threading
import os
import sys
import subprocess

def usage():
    print("Verwendung: python main.py --amount <Anzahl_der_Konten> [--output <Dateiname>]")
    print("Optionen:")
    print(" --amount Anzahl der zu erstellenden Konten (muss eine positive ganze Zahl sein).")
    print(" --output Datei zum Speichern der erzeugten E-Mails. Wenn angegeben, wird die Datei nach der Erzeugung geöffnet.")
    print("Beispiel: python main.py --amount 30 --output file.txt")
    print("")
    print("Manchmal hängt es ein wenig, weil der Registierungs-Code nicht an die 1secemail kommt.")

def get_random_email():
    url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=50000"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()[1]
    except requests.RequestException as e:
        print(f"Error beim Abrufen der E-Mail: {e}")
        return None

def get_request_id():
    url = "https://account.kaufland.com/authz-srv/authrequest/authz/generate"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": "https://www.kaufland.de/",
        "Origin": "https://www.kaufland.de"
    }

    try:
        response = requests.post(url, headers=headers, json={
            "client_id": "885e28ab-bbfe-4ee1-b437-5c31854a327d",
            "redirect_uri": "https://www.kaufland.de/iam/success",
            "scope": "profile email offline_access openid",
            "response_type": "code",
            "ui_locales": "de-DE",
            "state": "eyJzIjoiaHR0cHM6Ly93d3cua2F1ZmxhbmQuZGUifQ=="
        })
        response.raise_for_status()
        return response.json()["data"]["requestId"]
    except requests.RequestException as e:
        print(f"Fehler beim Abrufen der requestId: {e}")
        return None

def register_account(email, request_id):
    register_url = "https://account.kaufland.com/users-srv/register"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": "https://www.kaufland.de/",
        "requestId": request_id,
        "Origin": "https://www.kaufland.de"
    }
    data = {
        "given_name": email,
        "family_name": email,
        "provider": "self",
        "password": email,
        "customFields": {
            "marketplace_tos_de": True,
            "marketplace_closing_terms": True,
            "preferredStore": "DE0000"
        },
        "contact_source": "marketplace",
        "email": email
    }

    try:
        response = requests.post(register_url, headers=headers, json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Fehler beim Registrieren des Kontos: {e}")
        return False
    return True

def request_verification_code(email, request_id):
    verification_url = "https://account.kaufland.com/verification-srv/account/initiate/sdk"
    data = {
        "requestId": request_id,
        "processingType": "CODE",
        "email": email,
        "verificationMedium": "email"
    }

    try:
        response = requests.post(verification_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://www.kaufland.de/",
            "Origin": "https://www.kaufland.de"
        }, json=data)
        response.raise_for_status()
        return response.json()["data"]["accvid"]
    except requests.RequestException as e:
        print(f"Fehler beim Initiieren der Überprüfung: {e}")
        return None

def poll_for_verification_code(username, domain, timeout=60):
    login_url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={username}&domain={domain}"
    pattern = re.compile(r'Aktivierungs-Code: (\d+)')

    for _ in range(timeout):
        try:
            response = requests.get(login_url)
            if response.status_code == 200 and response.text != "[]":
                emails = response.json()
                match = pattern.search(str(emails))
                if match:
                    return match.group(1)
        except requests.RequestException as e:
            print(f"Fehler beim Abrufen der E-Mails: {e}")
        time.sleep(1)

    print(f"Timeout: Aktivierungs-Code konnte nicht innerhalb von {timeout} Sekunden abgerufen werden.")
    return None

def verify_account(accvid, email_code):
    verify_url = "https://account.kaufland.com/verification-srv/account/verify"
    data = {
        "accvid": str(accvid),
        "code": str(email_code)
    }

    try:
        response = requests.post(verify_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://www.kaufland.de/",
            "Origin": "https://www.kaufland.de"
        }, json=data)
        if response.status_code == 200:
            return True
    except requests.RequestException as e:
        print(f"Fehler beim Verifizieren des Kontos: {e}")
    return False

def generate_account(output_file=None):
    email = get_random_email()
    if not email:
        return None

    username, domain = email.split("@")
    request_id = get_request_id()
    if not request_id:
        return None

    if not register_account(email, request_id):
        return None

    accvid = request_verification_code(email, request_id)
    if not accvid:
        return None

    email_code = poll_for_verification_code(username, domain)
    if not email_code:
        return None

    if verify_account(accvid, email_code):
        print(f"Account erfolgreich generiert -> {email}")
        if output_file:
            with open(output_file, 'a') as file:
                file.write(email + '\n')
        return email
    return None

def thread_function(output_file):
    try:
        generate_account(output_file)
    except Exception as e:
        print(f"Error in thread: {e}")

def main():
    output_file = None
    amount = 0

    if len(sys.argv) < 3:
        usage()
        return

    for i in range(1, len(sys.argv)):
        if sys.argv[i] == '--amount' and i + 1 < len(sys.argv):
            try:
                amount = int(sys.argv[i + 1])
            except ValueError:
                print("Bitte geben Sie eine gültige Zahl für die Anzahl der Konten an.")
                return
        elif sys.argv[i] == '--output' and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]

    if amount <= 0:
        print("Bitte geben Sie eine positive Anzahl von Konten an.")
        return

    threads = [threading.Thread(target=thread_function, args=(output_file,)) for _ in range(amount)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    print("Account Generierung abgeschlossen.")
    if output_file:
        open_file(output_file)

def open_file(output_file):
    print(f"Öffne die Datei: {output_file}")
    if sys.platform == "win32":
        os.startfile(output_file)
    elif sys.platform == "darwin":
        subprocess.call(["open", output_file])
    else:
        subprocess.call(["xdg-open", output_file])

if __name__ == "__main__":
    main()