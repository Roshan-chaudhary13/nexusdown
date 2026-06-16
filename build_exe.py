#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BSE Extranet Downloader EXE Compiler
====================================
Runs PyInstaller programmatically to compile gui_app.py 
into a standalone, single-file Windows executable (BSE_Downloader.exe)
with dark-mode windowed styling (no console).
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

def main():
    script_dir = Path(__file__).parent.resolve()
    target_py = script_dir / "gui_app.py"
    
    print("=" * 60)
    print("  BSE EXTRANET DOWNLOADER STANDALONE COMPILER")
    print("=" * 60)
    print(f"Target Script: {target_py}")
    
    if not target_py.exists():
        print("ERROR: gui_app.py not found in script directory!")
        sys.exit(1)
        
    # Clean previous build artifacts if they exist
    dist_dir = script_dir / "dist"
    build_dir = script_dir / "build"
    
    for folder in [dist_dir, build_dir]:
        if folder.exists():
            print(f"Cleaning existing directory: {folder}")
            try:
                shutil.rmtree(folder)
            except Exception as e:
                print(f"Warning: could not clean {folder}: {e}")
                
    # Clean up all spec files in the directory
    for f in script_dir.glob("*.spec"):
        try:
            f.unlink()
        except Exception as e:
            print(f"Warning: could not remove spec file {f}: {e}")

    # Generate logo.ico from TRANSPARENT LOGO.png to set as the .exe icon
    ico_path = script_dir / "logo.ico"
    png_path = script_dir / "TRANSPARENT LOGO.png"
    if not png_path.exists():
        png_path = script_dir / "LOGO.png"
        
    if png_path.exists():
        try:
            from PIL import Image
            img = Image.open(png_path)
            img.save(ico_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            print(f"Generated windows icon file: {ico_path}")
        except Exception as e:
            print(f"Warning: could not generate logo.ico: {e}")

    # Build PyInstaller command
    # --onefile: bundle everything into single EXE
    # --noconsole: hide the background black terminal console
    # --name: NexusDown
    # --clean: clean PyInstaller cache before building
    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        "--name=NexusDown",
    ]
    if ico_path.exists():
        cmd.append(f"--icon={ico_path}")
        
    # Bundle the logo files directly inside the executable
    cmd.extend([
        "--add-data=TRANSPARENT LOGO.png;.",
        "--add-data=LOGO.png;."
    ])
        
    cmd.extend([
        "--clean",
        "--hidden-import=requests",
        "--hidden-import=bs4",
        "--hidden-import=cryptography",
        "--hidden-import=cv2",
        "--hidden-import=torch",
        "--hidden-import=numpy",
        "--hidden-import=pandas",
        "--hidden-import=gzip",
        "--hidden-import=captcha_solver",
        "--hidden-import=bse_extranet_downloader",
        "--hidden-import=nse",
        "--hidden-import=nse.NSE_CM_API_DOWNLOAD",
        "--hidden-import=nse.NSE_FO_API_DOWNLOAD",
        "--hidden-import=nse.NSE_CD_API_DOWNLOAD_AI",
        "--hidden-import=nse.NSE_SLB_API_DOWNLOAD",
        str(target_py)
    ])
    
    print("\nRunning PyInstaller command:")
    print(" ".join(cmd))
    print("\nStarting compilation... This might take a few minutes (packaging PyTorch & OpenCV)...\n")
    
    try:
        # Run command and show stdout
        result = subprocess.run(cmd, cwd=str(script_dir), check=True)
        if result.returncode == 0:
            print("\n" + "=" * 60)
            print("  COMPILATION SUCCESSFUL!")
            print("=" * 60)
            
            exe_path = dist_dir / "NexusDown.exe"
            if exe_path.exists():
                print(f"\nStandalone Executable created at:\n{exe_path}")
                print("\nTo run the software successfully on any PC, make sure you copy:")
                print("1. NexusDown.exe           (from dist/ folder)")
                print("2. config.json             (your configuration file)")
                print("3. captcha_solver_model.pth (the captcha solver network weights)")
                print("\nAll 3 files MUST be placed in the same folder on the target PC!")
            else:
                print(f"ERROR: Executable build reported success but {exe_path} was not found.")
                sys.exit(1)
        else:
            print(f"\nPyInstaller exited with code: {result.returncode}")
            sys.exit(result.returncode)
            
    except subprocess.CalledProcessError as err:
        print(f"\nCRITICAL: PyInstaller build failed: {err}")
        sys.exit(1)
    except Exception as ex:
        print(f"\nCRITICAL: Unexpected error during compilation: {ex}")
        sys.exit(1)

if __name__ == "__main__":
    main()
