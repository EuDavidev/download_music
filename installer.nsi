!include "MUI2.nsh"

Name "America"
OutFile "installer_output\AmericaM_Setup.exe"
InstallDir "$LOCALAPPDATA\America"
RequestExecutionLevel user

!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File "dist\AmericaM.exe"

  ; Start Menu shortcut
  CreateDirectory "$SMPROGRAMS\America"
  CreateShortcut "$SMPROGRAMS\America\America.lnk" "$INSTDIR\AmericaM.exe"

  ; Desktop shortcut
  CreateShortcut "$DESKTOP\America.lnk" "$INSTDIR\AmericaM.exe"

  ; Uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Add/Remove Programs entry
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\America" "DisplayName" "America"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\America" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\America" "DisplayVersion" "1.0.0"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\AmericaM.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  Delete "$SMPROGRAMS\America\America.lnk"
  RMDir "$SMPROGRAMS\America"
  Delete "$DESKTOP\America.lnk"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\America"
SectionEnd

; Launch after install
Function .onInstSuccess
  Exec "$INSTDIR\AmericaM.exe"
FunctionEnd
