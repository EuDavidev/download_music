"""
build_windows.py — Script de empacotamento para Windows
Gera .exe + instalador NSIS

Pré-requisitos:
  pip install pyinstaller
  Instalar NSIS: https://nsis.sourceforge.io/

Uso:
  python build_windows.py
"""

import subprocess
import sys
import os
from pathlib import Path

BASE = Path(__file__).parent
DIST = BASE / "dist"
BUILD = BASE / "build"

def check_pyinstaller():
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build_exe():
    print("\n🔨 Empacotando América.exe...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "America",
        "--icon", "assets/icon.ico" if (BASE / "assets/icon.ico").exists() else "NONE",
        "--add-data", f"{BASE}/assets;assets" if sys.platform == "win32" else f"{BASE}/assets:assets",
        "--clean",
        "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        str(BASE / "america.py"),
    ]
    subprocess.check_call(cmd, cwd=str(BASE))
    print(f"\n✅ Executável gerado em: {DIST / 'America.exe'}")

def generate_nsis_script():
    """Gera script NSIS para o instalador."""
    exe_path = DIST / "America.exe"
    nsis = f"""
; América Installer — NSIS Script
; Compile com: makensis installer.nsi

!define APP_NAME "América"
!define APP_VERSION "1.0.0"
!define APP_EXE "America.exe"
!define APP_ICON "assets\\icon.ico"

Name "${{APP_NAME}} ${{APP_VERSION}}"
OutFile "America_Setup.exe"
InstallDir "$PROGRAMFILES\\America"
InstallDirRegKey HKCU "Software\\America" ""
RequestExecutionLevel admin

; Páginas
Page welcome
Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Principal" SecMain
  SetOutPath "$INSTDIR"
  File "{exe_path}"
  
  ; Atalhos
  CreateDirectory "$SMPROGRAMS\\América"
  CreateShortcut "$SMPROGRAMS\\América\\América.lnk" "$INSTDIR\\${{APP_EXE}}"
  CreateShortcut "$DESKTOP\\América.lnk" "$INSTDIR\\${{APP_EXE}}"
  
  ; Registro para desinstalação
  WriteRegStr HKCU "Software\\America" "" "$INSTDIR"
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\America" \\
                   "DisplayName" "${{APP_NAME}}"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\America" \\
                   "UninstallString" "$INSTDIR\\Uninstall.exe"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\America" \\
                   "DisplayVersion" "${{APP_VERSION}}"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\\${{APP_EXE}}"
  Delete "$INSTDIR\\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\\América\\América.lnk"
  RMDir "$SMPROGRAMS\\América"
  Delete "$DESKTOP\\América.lnk"
  DeleteRegKey HKCU "Software\\America"
  DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\America"
SectionEnd
"""
    nsis_file = BASE / "installer.nsi"
    nsis_file.write_text(nsis, encoding="utf-8")
    print(f"✓ Script NSIS gerado: {nsis_file}")
    print("  → Para gerar o instalador: makensis installer.nsi")

if __name__ == "__main__":
    check_pyinstaller()
    build_exe()
    generate_nsis_script()
    print("\n🎉 Build concluído!")
    print("   Executável: dist/America.exe")
    print("   Instalador: execute 'makensis installer.nsi' (requer NSIS)")
