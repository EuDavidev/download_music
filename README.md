# 🎵 América

> Conversor de YouTube para MP3 — Simples, rápido e bonito.

**América** é um aplicativo desktop para Windows que permite baixar músicas e playlists do YouTube em formato MP3 com uma interface moderna e intuitiva.

---

## ✨ Funcionalidades

- 🎯 **Colar e baixar** — Cole o link, clique em "Baixar" e pronto
- 📋 **Playlists** — Baixe playlists inteiras com subpasta automática por playlist
- 🎚️ **Qualidade** — Escolha entre Alta (320 kbps) ou Normal (128 kbps)
- 📂 **Fila de downloads** — Gerencie múltiplos downloads simultaneamente
- ⏸️ **Controles** — Pause, retome ou cancele downloads a qualquer momento
- 🕘 **Histórico** — Veja todos os downloads anteriores
- 🌙 **Tema claro/escuro** — Alterne entre temas na interface
- ⚙️ **Configurações** — Pasta de destino, padrão de nomes, subpastas por playlist

---

## 📸 Preview

| Tema Claro | Tema Escuro |
|:-:|:-:|
| Interface limpa com azul, vermelho e branco | Modo escuro com cores suaves |

---

## 🚀 Instalação

### Opção 1 — Instalador (recomendado)

1. Baixe o `AmericaM_Setup.exe` na aba [Releases](../../releases)
2. Execute o instalador
3. O app será instalado e um atalho criado na Área de Trabalho

### Opção 2 — Executar direto

1. Baixe o `AmericaM.exe` na aba [Releases](../../releases)
2. Dê duplo clique para abrir — sem instalação necessária

### Opção 3 — Rodar o código fonte

```bash
# Clone o repositório
git clone https://github.com/SEU_USUARIO/America.git
cd America

# Instale as dependências
pip install -r requirements.txt

# Execute
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
