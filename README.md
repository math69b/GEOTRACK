# GeoTrack

Plataforma moderna de geolocalização para engagements de red team e testes de engenharia social.

## Funcionalidades

- **Dashboard em tempo real** — mapa ao vivo com hits aparecendo em real-time via WebSocket
- **Sistema de campanhas** — organize links por engagement/cliente
- **3 templates prontos** — Verificação Pix, Rastreamento Correios, Prêmio/Sorteio
- **Coleta expandida** — GPS, IP, fingerprint, device info, bateria, rede, fuso horário
- **Notificações Telegram** — receba coordenadas direto no celular
- **Deploy em 1 comando** — Docker Compose pronto

## Quick Start

### Opção 1: Docker (recomendado)

```bash
git clone https://github.com/seu-usuario/geotrack.git
cd geotrack
docker compose up -d
```

Acesse `http://localhost:8000`

### Opção 2: Manual

```bash
git clone https://github.com/seu-usuario/geotrack.git
cd geotrack
pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

## Como Usar

### 1. Criar uma Campanha

No dashboard, clique em **"Nova Campanha"**, defina o nome e escolha o template.

### 2. Gerar um Link

Clique em **"Novo Link"**, selecione a campanha e gere o link de tracking.
O link terá o formato: `https://seu-dominio.com/t/abc12345`

### 3. Enviar o Link

Envie o link para o alvo via email, SMS ou rede social.

### 4. Monitorar

Os hits aparecem em tempo real no dashboard com:
- Coordenadas GPS (latitude/longitude)
- Precisão em metros
- IP do alvo
- Dispositivo, OS, navegador
- Nível de bateria
- Tipo de rede (WiFi/4G/5G)
- Fuso horário e idioma

## Templates Disponíveis

| Template | Descrição |
|----------|-----------|
| `pix` | Verificação de transferência Pix |
| `correios` | Rastreamento de encomenda |
| `premio` | Prêmio / sorteio |

Para criar templates customizados, adicione um arquivo `.html` na pasta `templates/`.

## Deploy em Produção (VPS)

```bash
# Na sua VPS
git clone https://github.com/seu-usuario/geotrack.git
cd geotrack
docker compose up -d

# Configurar Nginx como proxy reverso
sudo apt install nginx certbot python3-certbot-nginx -y
```

Nginx config (`/etc/nginx/sites-available/default`):

```nginx
server {
    listen 80;
    server_name seudominio.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
sudo nginx -t && sudo systemctl restart nginx
sudo certbot --nginx -d seudominio.com
```

## Notificações Telegram

1. Crie um bot com @BotFather e copie o token
2. Descubra seu chat_id enviando mensagem para @userinfobot
3. Configure no `docker-compose.yml`:

```yaml
environment:
  - TELEGRAM_TOKEN=123456:ABC-DEF
  - TELEGRAM_CHAT_ID=987654321
```

## API Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Dashboard |
| GET | `/t/{slug}` | Landing page do alvo |
| POST | `/api/collect/{slug}` | Coleta de dados (chamado pelo JS) |
| GET/POST | `/api/campaigns` | Listar/criar campanhas |
| DELETE | `/api/campaigns/{id}` | Excluir campanha |
| POST | `/api/links` | Criar link de tracking |
| GET | `/api/links/{campaign_id}` | Listar links da campanha |
| GET | `/api/hits` | Listar hits |
| GET | `/api/stats` | Estatísticas gerais |
| WS | `/ws` | WebSocket para real-time |

## Estrutura do Projeto

```
geotrack/
├── backend/
│   └── app.py              # API FastAPI
├── frontend/
│   └── dashboard.html      # Dashboard com mapa
├── templates/
│   ├── pix.html            # Template Pix
│   ├── correios.html       # Template Correios
│   └── premio.html         # Template Prêmio
├── static/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Disclaimer

Esta ferramenta é destinada exclusivamente para testes de segurança autorizados e engagements de red team com consentimento. O uso indevido é de responsabilidade do operador.


