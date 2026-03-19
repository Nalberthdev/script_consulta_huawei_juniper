import paramiko
import time
import csv
import os
import re
from datetime import datetime

USERNAME = "noc.franca"
PASSWORD = "06wb1gy!"

OUTPUT_DIR = "outputs_csv"
LOG_FILE = "errors.log"

DELAY = 5
READ_TIMEOUT = 25
MAX_SPACE_PRESSES = 100
MORE_REGEX = re.compile(r"-+\s*more\s*-+", re.IGNORECASE)

# Commands executed per vendor.
COMMANDS_BY_VENDOR = {
    "HUAWEI": [
        "dis current-configuration all",
    ],
    "JUNIPER": [
        "show configuration | display set | no-more",
    ],
}

devices = [
("ANG-PRI-H6730-TP-01","10.100.100.71","HUAWEI"),
("ANG-SCR-H6720-TP-01","10.100.100.73","HUAWEI"),
("ANP-PRI-H6720-TP-01","10.100.100.202","HUAWEI"),
("BFE-PRI-H6720-TP-01","10.100.100.65","HUAWEI"),
("BRE-SP2-H6730-TP-01","10.100.100.84","HUAWEI"),
("BRE-SP2-H6730-TP-02","10.100.100.86","HUAWEI"),
("BRE-SP4-H6730-TP-01","10.100.100.85","HUAWEI"),
("BTV-HE-H6730-TP-02","10.100.100.36","HUAWEI"),
("BTV-PRI-H6730-TP-01","10.100.100.1","HUAWEI"),
("CAS-OUV-H6730-TP-01","10.100.100.61","HUAWEI"),
("CAS-OUV-HNE40-PE-01","200.187.80.245","HUAWEI"),
("CEG-PRI-H6720-TP-01","10.100.100.41","HUAWEI"),
("CLT-PRI-H6730-TP-01","10.100.100.8","HUAWEI"),
("CMAL-PRI-H6720-TP-01","10.100.100.72","HUAWEI"),
("CNH-PRI-H6720-TP-01","10.100.100.3","HUAWEI"),
("COT-L3-H6730-TP-01","10.100.100.90","HUAWEI"),
("CQO-IDC-H6730-TP-01","10.100.100.10","HUAWEI"),
("CVT-PRI-H6720-TP-01","10.100.100.206","HUAWEI"),
("FAC-ESC-H6720-TP-01","10.100.100.200","HUAWEI"),
("IEO-PRI-H6730-TP-01","10.100.100.4","HUAWEI"),
("IGA-PRI-H6720-TP-01","10.100.100.62","HUAWEI"),
("ITU-PPTI-H6720-TP-01","10.100.100.11","HUAWEI"),
("ITU-PRI-H6720-TP-01","10.100.100.18","HUAWEI"),
("IYR-PRI-H6720-TP-01","10.100.100.205","HUAWEI"),
("PAA-MTF-H6720-TP-01","10.100.100.37","HUAWEI"),
("PAA-PRI-H6730-TP-01","10.100.100.32","HUAWEI"),
("PCP-CON-H6720-TP-01","10.100.100.201","HUAWEI"),
("PLL-PRI-H6720-TP-01","10.100.100.16","HUAWEI"),
("PON-PRI-H6720-TP-01","10.100.100.42","HUAWEI"),
("RCO-COL-HNE40-PE-01","200.187.80.250","HUAWEI"),
("RPO-NVR-H6720-TP-01","10.100.100.203","HUAWEI"),
("RRC-PRI-H6720-TP-01","10.100.100.204","HUAWEI"),
("SALN-PRI-H6730-TP-01","10.100.100.31","HUAWEI"),
("SLO-PRI-H6730-TP-01","10.100.100.63","HUAWEI"),
("SOC-BGT-H6730-TP-01","10.100.100.5","HUAWEI"),
("SOC-PIR-H12700-TP-01","10.100.100.15","HUAWEI"),
("SPB-SP3-H6730-TP-01","10.100.100.81","HUAWEI"),
("SPR-REGB-H6730-TP-01","10.100.100.20","HUAWEI"),
("SRP-PRI-H6720-TP-01","10.100.100.66","HUAWEI"),
("SUM-DSK-H6730-TP-01","10.100.100.60","HUAWEI"),
("TIE-PRI-H6720-TP-01","10.100.100.7","HUAWEI"),
("TTI-SRF-H6720-TP-01","10.100.100.34","HUAWEI"),
("TTI-WAV-H6720-TP-01","10.100.100.9","HUAWEI"),
("TTI-WAV-HNE40-PE-01","200.187.80.236","HUAWEI"),
("COA-L3-J10003-PE-01","200.187.80.242","JUNIPER"),
("CQO-IDC-J204-BNG-01","200.187.80.226","JUNIPER"),
("CQO-IDC-J204-BNG-02","200.187.80.227","JUNIPER"),
("CQO-IDC-J960-PE-01","200.187.80.220","JUNIPER"),
("FAC-ESC-J204-BNG-01","200.187.80.228","JUNIPER"),
("FAC-ESC-J204-PE-01","200.187.80.254","JUNIPER"),
("SOC-PIR-J10003-PE-01","200.187.80.248","JUNIPER"),
("SOC-PIR-J480-BNG-01","200.187.80.249","JUNIPER"),
("SPB-SP3-J10003-PE-01","200.187.80.243","JUNIPER"),
("SPB-SP3-J204-BNG-01","200.187.80.252","JUNIPER"),
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
        writer.writerow([
            device,
            ip,
            vendor,
            status,
            config_text,
            collected_at_iso,
        ])
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

            # Some devices still paginate output; press space automatically.
            if MORE_REGEX.search(data):
                if more_presses < MAX_SPACE_PRESSES:
                    shell.send(" ")
                    more_presses += 1
                    print(f"\n[PAGER] Detectado 'More'. Enviando ESPACO ({more_presses}/{MAX_SPACE_PRESSES})", flush=True)
                else:
                    print("\n[PAGER] Limite de ESPACO atingido para este comando.", flush=True)

        if time.time() - start > timeout_seconds:
            break

        time.sleep(0.4)

    return output


def executar(device, ip, vendor, output_dir):
    commands = COMMANDS_BY_VENDOR.get(vendor)
    if not commands:
        msg = f"Vendor nao suportado: {vendor}"
        print(f"[ERRO] {msg} para {device} ({ip})", flush=True)
        log_error(device, ip, msg)
        csv_path = save_device_csv(output_dir, device, ip, vendor, "ERRO", msg)
        return False, csv_path

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"\n[INICIO] Conectando em {device} ({ip}) - {vendor}", flush=True)
        client.connect(ip, username=USERNAME, password=PASSWORD, timeout=10)

        shell = client.invoke_shell()
        time.sleep(2)

        if shell.recv_ready():
            banner = shell.recv(65535).decode(errors="ignore")
            if banner:
                print(banner, end="", flush=True)

        combined_output = ""

        for cmd in commands:
            print(f"\n[CLI] {device}: enviando comando -> {cmd}", flush=True)
            shell.send(cmd + "\n")
            cmd_output = read_shell_output(shell, READ_TIMEOUT)
            combined_output += f"\n### COMMAND: {cmd}\n{cmd_output}"

        status = "OK"
        csv_path = save_device_csv(output_dir, device, ip, vendor, status, combined_output.strip())
        print(f"\n[OK] Finalizado {device}. CSV: {csv_path}", flush=True)
        return True, csv_path

    except Exception as e:
        err = str(e)
        print(f"\n[ERRO] {device} ({ip}) -> {err}", flush=True)
        log_error(device, ip, err)
        csv_path = save_device_csv(output_dir, device, ip, vendor, "ERRO", err)
        return False, csv_path

    finally:
        client.close()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total = len(devices)
    success = 0
    failed = 0

    print("=" * 80, flush=True)
    print("COLETA VIA CLI INICIADA", flush=True)
    print(f"Total de dispositivos: {total}", flush=True)
    print(f"Pasta de saida: {os.path.abspath(OUTPUT_DIR)}", flush=True)
    print("=" * 80, flush=True)

    for idx, (device, ip, vendor) in enumerate(devices, start=1):
        print(f"\n[{idx}/{total}] Processando {device} ({ip})", flush=True)
        ok, _ = executar(device, ip, vendor, OUTPUT_DIR)

        if ok:
            success += 1
        else:
            failed += 1

        if idx < total:
            print(f"\n[WAIT] Aguardando {DELAY}s para proximo device...", flush=True)
            time.sleep(DELAY)

    print("\n" + "=" * 80, flush=True)
    print("COLETA FINALIZADA", flush=True)
    print(f"Sucesso: {success}", flush=True)
    print(f"Falhas: {failed}", flush=True)
    print(f"CSVs gerados em: {os.path.abspath(OUTPUT_DIR)}", flush=True)
    print(f"Log de erros: {os.path.abspath(LOG_FILE)}", flush=True)
    print("=" * 80, flush=True)


if __name__ == "__main__":
    main()