Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "d:\download_music"

' 1. Inicia o servidor Python FastAPI 100% invisível (pythonw sem console)
WshShell.Run """C:\Users\davis\AppData\Local\Programs\Python\Python313\pythonw.exe"" d:\download_music\run_web.py", 0, False

' 2. Aguarda 3 segundos para o servidor subir
WScript.Sleep 3000

' 3. Inicia o Ngrok 100% invisível em segundo plano gravando log
WshShell.Run "ngrok http --url https://unpaved-counting-patio.ngrok-free.dev 8000 --log ""d:\download_music\ngrok.log""", 0, False

Set WshShell = Nothing



