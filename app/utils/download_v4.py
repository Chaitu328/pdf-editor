import os
import tarfile
import requests
import shutil
import time

def download_file_with_resume(url, dest_path, max_retries=45, force_clean=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    parent_dir = os.path.dirname(dest_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    temp_dest = dest_path + ".tmp"
    
    if force_clean:
        if os.path.exists(temp_dest):
            os.remove(temp_dest)
        if os.path.exists(dest_path):
            os.remove(dest_path)
            
    initial_pos = 0
    if os.path.exists(temp_dest):
        initial_pos = os.path.getsize(temp_dest)
        print(f"Resuming download from byte position {initial_pos}")
        
    for attempt in range(1, max_retries + 1):
        try:
            if initial_pos > 0:
                headers["Range"] = f"bytes={initial_pos}-"
            else:
                headers.pop("Range", None)
                
            print(f"Attempt {attempt}/{max_retries} to download {url}...")
            r = requests.get(url, headers=headers, stream=True, timeout=20)
            
            if r.status_code not in [200, 206]:
                if r.status_code == 416:
                    initial_pos = 0
                    if os.path.exists(temp_dest):
                        os.remove(temp_dest)
                    continue
                raise Exception(f"HTTP status {r.status_code}")
                
            mode = "ab" if (r.status_code == 206 and initial_pos > 0) else "wb"
            if mode == "wb":
                initial_pos = 0
                
            total_size = int(r.headers.get('content-length', 0)) + initial_pos
            print(f"Target size: {total_size / (1024*1024):.2f} MB")
            
            downloaded = initial_pos
            with open(temp_dest, mode) as f:
                for chunk in r.iter_content(chunk_size=1024 * 32):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (1024 * 256) < 1024 * 32 or downloaded == total_size:
                            print(f"Downloaded: {downloaded / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB ({(downloaded/total_size)*100:.1f}%)")
                            
            if downloaded >= total_size:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                os.rename(temp_dest, dest_path)
                return True
            else:
                initial_pos = downloaded
                raise Exception("Incomplete download")
        except Exception as e:
            print(f"Error on attempt {attempt}: {e}")
            if os.path.exists(temp_dest):
                initial_pos = os.path.getsize(temp_dest)
            time.sleep(2)
    return False

def download_and_extract(url, tar_dest, extract_dest, file_to_check, force_clean=False):
    extracted_folder = os.path.join(extract_dest, os.path.basename(tar_dest).replace(".tar", ""))
    check_path = os.path.join(extracted_folder, file_to_check)
    if os.path.exists(check_path):
        print(f"Success! Already verified file exists: {check_path}")
        return True
        
    if os.path.exists(extracted_folder) and force_clean:
        shutil.rmtree(extracted_folder, ignore_errors=True)
        
    if not download_file_with_resume(url, tar_dest, force_clean=force_clean):
        return False

    try:
        os.makedirs(extract_dest, exist_ok=True)
        try:
            with tarfile.open(tar_dest, "r:gz") as tar:
                tar.extractall(path=extract_dest)
        except Exception:
            with tarfile.open(tar_dest, "r") as tar:
                tar.extractall(path=extract_dest)
        print("Extraction completed successfully!")
    except Exception as e:
        print(f"Extraction failed: {e}")
        return False
        
    if os.path.exists(check_path):
        try:
            os.remove(tar_dest)
        except Exception:
            pass
        return True
    return False

def main():
    success_rec = download_and_extract(
        url="http://paddleocr.bj.bcebos.com/PP-OCRv4/multilingual/te_PP-OCRv4_rec_infer.tar",
        tar_dest=r"C:\Users\admin\.paddleocr\whl\rec\te\te_PP-OCRv4_rec_infer.tar",
        extract_dest=r"C:\Users\admin\.paddleocr\whl\rec\te",
        file_to_check="inference.pdmodel"
    )
    if success_rec:
        print("TELUGU V4 MODEL DOWNLOADED AND VERIFIED.")
    else:
        print("TELUGU V4 MODEL DOWNLOAD FAILED.")

if __name__ == "__main__":
    main()
