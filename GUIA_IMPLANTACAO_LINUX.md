# Guia de Implantacao e Execucao 24/7 no Linux (GEINFORM / ITPS)

Este guia explica como rodar o Backend e o Cloudflare Tunnel no servidor Linux (/home/geinform/Área de trabalho/BACKINTRA).

---

## 1. Atualizar o Projeto na VM Linux
Abra o terminal na pasta do projeto:
```bash
cd "/home/geinform/Área de trabalho/BACKINTRA"
git pull origin main
```

---

## 2. Instalar o Cloudflare Tunnel no Linux (Debian / Ubuntu / Mint)
Para instalar o binario oficial do cloudflared no Linux:
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

---

## 3. Iniciar Tudo com 1 Comando (Em Segundo Plano)
De permissao de execucao ao script:
```bash
chmod +x iniciar_linux.sh
./iniciar_linux.sh
```

---

## 4. Como Deixar Rodando Como Servico Permanente do Linux (systemd - 24h por dia)
Se desejar que o backend inicie automaticamente no boot do Linux:

1. Crie o arquivo de servico:
```bash
sudo nano /etc/systemd/system/itps-backend.service
```

2. Cole o conteudo abaixo:
```ini
[Unit]
Description=ITPS Intranet Backend e Recadastramento GERH
After=network.target postgresql.service

[Service]
Type=simple
User=geinform
WorkingDirectory=/home/geinform/Área de trabalho/BACKINTRA
ExecStart=/usr/bin/python3 "/home/geinform/Área de trabalho/BACKINTRA/main.py"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Ative e inicie o servico:
```bash
sudo systemctl daemon-reload
sudo systemctl enable itps-backend
sudo systemctl start itps-backend
```
