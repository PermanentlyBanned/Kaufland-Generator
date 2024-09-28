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
    print(" --amount Anzahl der zu erzeugenden Konten (muss eine positive ganze Zahl sein).")
    print(" --output Datei zum Speichern der generierten Emails. Wenn angegeben, wird die Datei nach der Generierung geöffnet.")
    print("Beispiel: python main.py --amount 30 --output file.txt")

def generate_account(output_file=None):
    url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=50000"

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error beim Abrufen der E-Mail: {e}")
        return None

    chosen_email = response.json()[1]
    username, domain = chosen_email.split("@")

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

    x_request_id = get_request_id()
    if not x_request_id:
        return None

    register_url = "https://account.kaufland.com/users-srv/register"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": "https://www.kaufland.de/",
        "requestId": x_request_id,
        "Origin": "https://www.kaufland.de"
    }
    data = {
        "given_name": chosen_email,
        "family_name": chosen_email,
        "provider": "self",
        "password": chosen_email,
        "customFields": {
            "marketplace_tos_de": True,
            "marketplace_closing_terms": True,
            "preferredStore": "DE0000"
        },
        "contact_source": "marketplace",
        "email": chosen_email
    }

    try:
        response = requests.post(register_url, headers=headers, json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Fehler beim Registrieren des Kontos: {e}")
        return None

    verification_url = "https://account.kaufland.com/verification-srv/account/initiate/sdk"
    data = {
        "requestId": x_request_id,
        "processingType": "CODE",
        "email": chosen_email,
        "verificationMedium": "email"
    }

    try:
        response = requests.post(verification_url, headers=headers, json=data)
        response.raise_for_status()
        accvid = response.json()["data"]["accvid"]
    except requests.RequestException as e:
        print(f"Fehler beim Initiieren der Überprüfung: {e}")
        return None

    while True:
        emails = get_emails(username, domain)
        if emails:
            pattern = re.compile(r'Aktivierungs-Code: (\d+)')
            match = pattern.search(str(emails))
            if match:
                email_code = match.group(1)
                break
        print("Warte auf den Aktivierungs-Code...")
        time.sleep(1)

    verify_url = "https://account.kaufland.com/verification-srv/account/verify"
    data = {
        "accvid": str(accvid),
        "code": str(email_code)
    }

    try:
        response = requests.post(verify_url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Account erfolgreich generiert -> {chosen_email}")
            if output_file:
                with open(output_file, 'a') as file:
                    file.write(chosen_email + '\n')
            return chosen_email
        else:
            print(f"Fehler bei der Verifizierung des Kontos -> {chosen_email}")
            return None
    except requests.RequestException as e:
        print(f"Fehler beim Verifizieren des Kontos: {e}")
        return None

def get_emails(username, domain):
    login_url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={username}&domain={domain}"
    try:
        response = requests.get(login_url)
        if response.status_code == 200 and response.text != "[]":
            return response.json()
    except requests.RequestException as e:
        print(f"Fehler beim Abrufen der E-Mails: {e}")
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
        if sys.argv[i] == '--amount':
            if i + 1 < len(sys.argv):
                try:
                    amount = int(sys.argv[i + 1])
                except ValueError:
                    print("Bitte geben Sie eine gültige Zahl für die Anzahl der Konten an.")
                    return
            else:
                print("Bitte geben Sie eine Anzahl nach --amount an.")
                return
        elif sys.argv[i] == '--output':
            if i + 1 < len(sys.argv):
                output_file = sys.argv[i + 1]
            else:
                print("Bitte geben Sie einen Dateinamen nach --output an.")
                return

    if amount <= 0:
        print("Bitte geben Sie eine positive Anzahl von Konten an.")
        return

    threads = []
    for _ in range(amount):
        thread = threading.Thread(target=thread_function, args=(output_file,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print("Account Generierung abgeschlossen.")

    if output_file:
        print(f"Öffne die Datei: {output_file}")
        if sys.platform == "win32":
            os.startfile(output_file)
        elif sys.platform == "darwin":
            subprocess.call(["open", output_file])
        else:
            subprocess.call(["xdg-open", output_file])

if __name__ == "__main__":
    main()
    os.system("pause")