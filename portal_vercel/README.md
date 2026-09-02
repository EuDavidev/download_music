# 🚀 América Web — Portal de Recepção (Vercel)

Esta pasta contém a página estática de recepção pronta para deploy na Vercel.

## 📁 Arquivos inclusos:
- `index.html`: Página principal com o botão de redirecionamento para `https://unpaved-counting-patio.ngrok-free.dev`.
- `style.css`: Design system com glassmorphism, Midnight Obsidian e sem scroll (viewport fit).
- `favicon.svg`: Ícone oficial do América Web.
- `vercel.json`: Configuração de deploy estático limpo.

## 🌐 Como fazer o deploy na Vercel:

### Método 1: Pelo Painel Web da Vercel (Arrastar e Soltar)
1. Acesse [vercel.com](https://vercel.com) e faça login.
2. Clique em **"Add New..."** ➔ **"Project"**.
3. Se você usar o GitHub, envie esta pasta para um repositório e importe na Vercel.
4. Ao criar o projeto, escolha o nome/domínio que quiser (ex: `america-web.vercel.app`).

### Método 2: Pelo Terminal (Vercel CLI)
No terminal, dentro da pasta `portal_vercel`:
```bash
npx vercel
```
Siga as instruções na tela e o deploy será publicado em segundos com seu subdomínio customizado!
