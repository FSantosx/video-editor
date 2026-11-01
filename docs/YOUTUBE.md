# Publicação no YouTube

O app tem uma **agenda de publicação** com dois modos:

| Modo | Quando | Como funciona |
|---|---|---|
| **Assistido** | Sempre disponível (padrão) | Você agenda os cortes e eles entram nos próximos horários livres (12h, 18h e 21h, editáveis). No horário, o **celular avisa** com um lembrete; o toque abre a tela de postagem: o título já vai copiado, o compartilhamento abre com o vídeo e você escolhe o YouTube. Depois é só marcar como postado. |
| **Automático (API)** | Canal conectado **e** auditoria do Google aprovada | Ao agendar, o servidor já envia o vídeo com publicação programada (`publishAt`). O próprio YouTube publica no horário, sem precisar do celular nem do servidor ligados. |

Os lembretes do modo assistido são agendados **no próprio celular**, então funcionam mesmo
com o servidor do Railway "dormindo".

## Por que existe o modo assistido: a auditoria do Google

Projetos da API do YouTube criados depois de julho de 2020 que **não passaram pela
auditoria de conformidade do Google** só conseguem enviar vídeos **privados**: o YouTube
ignora o pedido de público ou programado. Segundo relatos, vídeos travados assim não podem
ser liberados depois, só reenviados. A auditoria é gratuita, mas leva de semanas a meses.

Por isso o modo automático só liga com `YOUTUBE_AUDITED=1`. Até lá, o app permite um
**envio de teste** (sai privado) para conferir a conexão.

## Passo a passo

### 1. Projeto no Google Cloud (uma vez)

1. Acesse **console.cloud.google.com** e crie um projeto (ex.: `video-editor-cortes`).
2. **APIs e serviços → Biblioteca**: ative a **YouTube Data API v3**.
3. **APIs e serviços → Tela de consentimento OAuth** (ou "Google Auth Platform"):
   - Tipo: **Externo**.
   - Nome do app, e-mail de suporte e e-mail do desenvolvedor.
   - Escopos: `youtube.upload` e `youtube.readonly`.
   - **Usuários de teste**: adicione o e-mail da conta dona do canal (enquanto o app
     estiver em modo de teste, só esses e-mails conseguem conectar).
4. **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo: **Aplicativo da Web**.
   - **URIs de redirecionamento autorizados**:
     `https://video-editor-production-2735.up.railway.app/youtube/callback`
     (o servidor mostra a URI exata em `GET /youtube/status`, no campo `redirect_uri`).
   - Copie o **ID do cliente** e a **chave secreta**.

### 2. Variáveis no Railway (serviço video-editor → Variables)

| Variável | Valor |
|---|---|
| `GOOGLE_CLIENT_ID` | ID do cliente OAuth |
| `GOOGLE_CLIENT_SECRET` | chave secreta do cliente |
| `PUBLIC_URL` | `https://video-editor-production-2735.up.railway.app` |
| `YOUTUBE_AUDITED` | `0` (mude para `1` quando a auditoria for aprovada) |
| `YOUTUBE_CATEGORY_ID` | opcional; padrão `25` (Notícias e política). `22` = Pessoas e blogs, `24` = Entretenimento |
| `PUBLISH_SLOTS` | opcional; padrão `12:00,18:00,21:00` (também dá para mudar pelo app) |
| `PUBLISH_TZ` | opcional; padrão `America/Sao_Paulo` |

### 3. Conectar o canal

No app: **Agenda → ⚙ → Conectar canal**. O login do Google abre no navegador; autorize com
a conta do canal e volte ao app. A tela mostra "Conectado: nome do canal".

### 4. Pedir a auditoria

No Google, procure o formulário **"YouTube API Services - Audit and Quota Extension"**
(está na documentação da YouTube Data API, em *Quota and Compliance Audits*). Informe:

- o **número do projeto** do Google Cloud do passo 1;
- **o que o app faz**: "ferramenta própria que gera cortes curtos dos meus vídeos e os
  publica/agenda no meu próprio canal";
- que o app é de **uso interno**, só no **seu canal**, e não coleta dados de terceiros;
- o fluxo do usuário, com prints (agenda, tela de postagem, login do Google).

Quando aprovarem, mude `YOUTUBE_AUDITED=1` no Railway e faça um novo deploy. A partir daí,
agendar um corte já o envia ao YouTube com o horário programado.

## Limites

- **Cota diária:** as fontes divergem (de cerca de 6 a 100 envios por dia na cota padrão).
  Isso cobre a meta de 2 a 3 Shorts por dia. Se estourar, o item fica com
  "limite diário de envios do YouTube atingido; tente amanhã".
- **Título:** até 100 caracteres. **Descrição:** até 5.000 (o app inclui trecho, chamada
  para comentar e hashtags, com `#shorts`).
- **Shorts:** vídeo vertical de até 3 minutos já é classificado como Short pelo YouTube.

## API do servidor

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/publish/settings` | horários, fuso, próximos horários livres e status do YouTube |
| `PUT` | `/publish/settings` | `{"slots": ["12:00", "18:00"]}` |
| `GET` | `/publish/queue` | fila (ativos + postados nos últimos 3 dias) |
| `POST` | `/publish/queue` | `{"video_id": "...", "short_ids": [1, 3]}` (sem `short_ids`: todos os 9:16 prontos) ou `slot_at` para horário específico |
| `PATCH` | `/publish/queue/{id}` | `slot_at`, `title`, `description`, `status` (`posted` / `skipped`) |
| `DELETE` | `/publish/queue/{id}` | tira da fila |
| `POST` | `/publish/queue/{id}/upload` | envio manual (teste privado sem auditoria) |
| `GET` | `/youtube/status`, `/youtube/connect` | status / URL de login do Google |
| `POST` | `/youtube/disconnect` | remove o acesso guardado |
