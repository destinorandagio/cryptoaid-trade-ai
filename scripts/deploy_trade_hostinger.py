#!/usr/bin/env python3
"""
CryptoAID Trade AI — Hostinger FTP Deployment Script
Uploads local public_html/trade contents to /public_html/trade on Hostinger.
"""

import os
import sys
import ftplib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FTP_HOST = "92.113.18.68"
FTP_PORT = 21
FTP_USER = "u173050672.cryptoaid.support"
FTP_PASS = "h29031976T."
REMOTE_TARGET_DIR = "/public_html/trade"
LOCAL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "public_html", "trade"))
if not os.path.exists(LOCAL_DIR):
    LOCAL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public_html", "trade"))



def ensure_remote_dir(ftp, remote_path):
    """Ensure remote path exists, creating subdirs recursively if needed."""
    parts = [p for p in remote_path.replace("\\", "/").strip("/").split("/") if p]
    current = ""
    for part in parts:
        current += "/" + part
        try:
            ftp.cwd(current)
        except ftplib.error_perm:
            print(f"  [+] Creating remote directory: {current}")
            try:
                ftp.mkd(current)
                ftp.cwd(current)
            except Exception as e:
                print(f"  [!] Note on mkdir {current}: {e}")

def upload_trade():
    print(f"=== DEPLOYING TRADEAID TO HOSTINGER ===")
    print(f"Host: {FTP_HOST}:{FTP_PORT}")
    print(f"User: {FTP_USER}")
    print(f"Local Source:  {LOCAL_DIR}")
    print(f"Remote Target: {REMOTE_TARGET_DIR}")

    if not os.path.exists(LOCAL_DIR):
        print(f"[ERROR] Local directory {LOCAL_DIR} does not exist!")
        sys.exit(1)

    ftp = ftplib.FTP(timeout=30)
    print("[*] Connecting to FTP server...")
    ftp.connect(FTP_HOST, FTP_PORT)
    print("[*] Logging in...")
    ftp.login(FTP_USER, FTP_PASS)
    ftp.set_pasv(True)
    print("[*] Connected successfully!")

    # Switch to remote directory
    ensure_remote_dir(ftp, REMOTE_TARGET_DIR)
    ftp.cwd(REMOTE_TARGET_DIR)
    print(f"[*] Working directory is: {ftp.pwd()}")

    # Check for default.php and remove/rename it
    remote_files = ftp.nlst()
    if "default.php" in remote_files:
        print("[*] Removing Hostinger placeholder 'default.php'...")
        try:
            ftp.delete("default.php")
            print("  [OK] Removed default.php")
        except Exception as e:
            print(f"  [!] Could not delete default.php: {e}")

    # Walk local files
    uploaded_count = 0
    total_bytes = 0

    for root, dirs, files in os.walk(LOCAL_DIR):
        rel_dir = os.path.relpath(root, LOCAL_DIR).replace("\\", "/")
        if rel_dir == ".":
            target_remote = REMOTE_TARGET_DIR
        else:
            target_remote = f"{REMOTE_TARGET_DIR}/{rel_dir}"

        ensure_remote_dir(ftp, target_remote)
        ftp.cwd(target_remote)

        # Check existing remote files
        try:
            remote_existing = ftp.nlst()
        except Exception:
            remote_existing = []

        for filename in files:
            local_filepath = os.path.join(root, filename)
            file_size = os.path.getsize(local_filepath)
            size_mb = file_size / (1024 * 1024)

            # Skip unchanged media files if already present on Hostinger
            if filename in remote_existing and (filename.endswith(".mp4") or filename.endswith(".jpeg") or filename.endswith(".jpg")):
                try:
                    rem_size = ftp.size(filename)
                    if rem_size == file_size:
                        print(f"  --> Skipping unchanged media: {rel_dir}/{filename} ({size_mb:.2f} MB)... [CACHED]")
                        continue
                except Exception:
                    pass

            print(f"  --> Uploading: {rel_dir}/{filename} ({size_mb:.2f} MB)...", end="", flush=True)

            with open(local_filepath, "rb") as f:
                ftp.storbinary(f"STOR {filename}", f, blocksize=65536)
            
            print(" [OK]")
            uploaded_count += 1
            total_bytes += file_size

    total_mb = total_bytes / (1024 * 1024)
    print(f"\n[SUCCESS] Deployed {uploaded_count} files ({total_mb:.2f} MB) successfully to {REMOTE_TARGET_DIR}!")

    # Verify listing
    ftp.cwd(REMOTE_TARGET_DIR)
    print("[*] Remote files in /public_html/trade:")
    print(ftp.nlst())

    ftp.quit()
    print("[*] FTP session closed.")

if __name__ == "__main__":
    upload_trade()
