import paramiko
import time
import csv
import os
import re
from datetime import datetime

# 🔐 Use variáveis de ambiente em vez de credenciais fixas
USERNAME = os.getenv("NOC_USERNAME")
PASSWORD = os.getenv("NOC_PASSWORD")

OUTPUT_DIR = "outputs_csv"
LOG_FILE = "errors.log"

DELAY = 5
READ_TIMEOUT = 25
MAX_SPACE_PRESSES = 100
MORE_REGEX = re.compile(r"-+\s*more\s*-+", re.IGNORECASE)

# Commands executed per vendor
COMMANDS_BY_VENDOR = {
    "HUAWEI": [
        "display current-configuration all",
    ],
    "JUNIPER": [
        "show configuration | display set | no-more",
    ],
}

# ⚠️ Lista de devices sanitizada (sem dados reais)
devices = [
    ("DEVICE-01", "10.0.0.1", "HUAWEI"),
    ("DEVICE-02", "10.0.0.2", "HUAWEI"),
    ("DEVICE-03", "10.0.0.3", "JUNIPER"),
]


def sanitize_filename(name):
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", name.strip())
    return sanitized or "device"


def save_device_csv(output_dir, device, ip, vendor, status, config_text):
    collected_at_dt = datetime.now()
    timestamp = collected_at_dt.strftime("%Y%m%d_%H%M%S")
    collected_at_iso = collected_at_dt.isoformat(timespec="seconds")

    filename = f"{sanitize_filename(device)}_{timestamp}.csv"
    path = os.path.join(output_dir, filename)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["COLLECTED_AT", collected_at_iso])
        writer.writerow([])
        writer.writerow(["DEVICE", "IP", "VENDOR", "STATUS", "CONFIG", "COLLECTED_AT"])
        writer.writerow([device, ip, vendor, status, config_text, collected_at_iso])

    return path


def log_error(device, ip, error_message):
    line = f"{datetime.now().isoformat(timespec='seconds')} | {device} ({ip}) -> {error_message}"
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(line + "\n")


def read_shell_output(shell, timeout_seconds):
    output = ""
    start = time.time()
    more_presses = 0

    while True:
        if shell.recv_ready():
            data = shell.recv(65535).decode(errors="ignore")
            print(data, end="", flush=True)
            output += data
            start = time.time()

            if MORE_REGEX.search(data):
                if more_presses < MAX_SPACE_PRESSES:
                    shell.send(" ")
                    more_presses += 1
                else:
                    print("\n[PAGER] Limite atingido.", flush=True)

        if time.time() - start > timeout_seconds:
            break

        time.sleep(0.4)

    return output


def executar(device, ip, vendor, output_dir):
    commands = COMMANDS_BY_VENDOR.get(vendor)

    if not commands:
        msg = f"Vendor nao suportado: {vendor}"
        log_error(device, ip, msg)
        return False

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"[INFO] Conectando em {device} ({ip})")

        client.connect(ip, username=USERNAME, password=PASSWORD, timeout=10)
        shell = client.invoke_shell()
        time.sleep(2)

        combined_output = ""

        for cmd in commands:
            print(f"[CLI] {device} -> {cmd}")
            shell.send(cmd + "\n")
            cmd_output = read_shell_output(shell, READ_TIMEOUT)
            combined_output += f"\n### COMMAND: {cmd}\n{cmd_output}"

        save_device_csv(output_dir, device, ip, vendor, "OK", combined_output.strip())
        return True

    except Exception as e:
        log_error(device, ip, str(e))
        return False

    finally:
        client.close()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total = len(devices)
    success = 0
    failed = 0

    print(f"[START] Total de dispositivos: {total}")

    for idx, (device, ip, vendor) in enumerate(devices, start=1):
        print(f"[{idx}/{total}] {device}")
        ok = executar(device, ip, vendor, OUTPUT_DIR)

        if ok:
            success += 1
        else:
            failed += 1

        if idx < total:
            time.sleep(DELAY)

    print("[END]")
    print(f"Sucesso: {success}")
    print(f"Falhas: {failed}")


if __name__ == "__main__":
    main()