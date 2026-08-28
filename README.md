# 🎵 América

> Conversor de YouTube para MP3 — Simples, rápido e bonito. Disponível em versão **Web (Nuvem / Celular / Qualquer Lugar)** e **Desktop (Windows)**.

**América** permite converter e baixar músicas e playlists do YouTube em formato MP3 de alta qualidade (320 kbps), M4A, FLAC e MP4 diretamente para o computador ou celular do usuário, sem acumular arquivos no servidor.

---

## 🌐 América Web (Pronto para Hospedagem na Nuvem & Atualizações Instantâneas)

A versão Web foi projetada com arquitetura **Stateless & Efêmera**, ideal para hospedar em provedores de nuvem (Render, Railway, Fly.io, VPS, AWS, etc.):

- ☁️ **Deploy Centralizado**: Quando você faz manutenção ou deploy no servidor, todos os clientes recebem a nova versão instantaneamente pelo navegador, sem precisar de visitas técnicas ou instalações manuais.
- 📁 **Escolha da Pasta pelo Usuário**: O usuário escolhe a pasta do seu próprio computador onde deseja salvar as músicas (via *File System Access API*), ou utiliza o download padrão do navegador/celular.
- 🗑️ **Zero Acúmulo no Servidor**: O servidor processa a conversão de forma temporária e descarta os arquivos temporários automaticamente (TTL) assim que são entregues ao cliente.

### Como Executar Localmente:

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Inicie o servidor Web
python run_web.py
# Ou dê duplo clique em start_web.bat no Windows
```

- **No Computador**: acesse `http://localhost:8000`
- **No Celular / Dispositivos na mesma rede Wi-Fi**: acesse `http://SEU_IP_LOCAL:8000` (com QR Code integrado)

### Hospedagem na Nuvem com Docker:

```bash
docker-compose up -d
```

---

## ✨ Funcionalidades

- 📁 **Escolha da Pasta Local** — O cliente escolhe onde salvar no próprio computador
- 🎯 **Colar e baixar** — Cole o link, clique em "Baixar" e pronto
- 📋 **Playlists** — Baixe playlists inteiras com seleção de faixas e empacotamento em ZIP
- 🎚️ **Qualidade** — Escolha entre Alta (320 kbps), Normal (128 kbps), M4A, FLAC ou MP4
- 🎧 **Player Web Integrado** — Escute as músicas baixadas diretamente no navegador
- 📱 **Acesso Mobile & QR Code** — Conecte smartphones com facilidade
- 📂 **Fila de downloads** — Gerencie múltiplos downloads com progresso em tempo real (WebSocket)
- 🕘 **Histórico** — Veja e baixe novamente seus downloads anteriores
- 🌙 **Tema claro/escuro** — Alterne entre temas com design moderno baseado em UI/UX Pro Max

---

## 🚀 Versão Desktop (Windows)

### Opção 1 — Instalador (recomendado)

1. Baixe o `AmericaM_Setup.exe` na aba [Releases](../../releases)
2. Execute o instalador
3. O app será instalado e um atalho criado na Área de Trabalho

### Opção 2 — Executar direto

1. Baixe o `AmericaM.exe` na aba [Releases](../../releases)
2. Dê duplo clique para abrir — sem instalação necessária

### Opção 3 — Rodar o código fonte Desktop

```bash
python america.py
```

---

## 🔧 Pré-requisitos (apenas para código fonte)

- **Python 3.10+**
- **FFmpeg** — necessário para conversão de áudio
  ```bash
  winget install Gyan.FFmpeg
  ```

---

## 📦 Build — Gerar executável

```bash
# Instale o PyInstaller
pip install pyinstaller

# Gere o .exe
python -m PyInstaller --onefile --windowed --name AmericaM america.py
```

O executável será gerado em `dist/AmericaM.exe`.

### Gerar instalador (opcional)

Requer [NSIS](https://nsis.sourceforge.io/) instalado:

```bash
makensis installer.nsi
```

O instalador será gerado em `installer_output/AmericaM_Setup.exe`.

---

## 📁 Estrutura do Projeto

```
America/
├── america.py          # Código principal do aplicativo
├── build_windows.py    # Script de build automatizado
├── installer.nsi       # Script NSIS para gerar instalador
├── requirements.txt    # Dependências Python
├── LICENSE             # Licença MIT
└── README.md           # Este arquivo
```

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|---|---|
| **Python 3** | Linguagem principal |
| **Tkinter** | Interface gráfica (nativa) |
| **yt-dlp** | Download de vídeos do YouTube |
| **FFmpeg** | Conversão para MP3 |
| **PyInstaller** | Empacotamento como .exe |
| **NSIS** | Geração de instalador |

---

## 📄 Licença

Este projeto está sob a licença [MIT](LICENSE).

---

<p align="center">
  Feito com ❤️ em Python
</p>
