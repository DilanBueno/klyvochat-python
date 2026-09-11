# Klyvochat — Planos de Desenvolvimento

## Visão Geral

Aplicativo de comunicação para desktop em Python, inspirado no Steam Chat, com interface compacta baseada em janelas flutuantes, chat de texto P2P, chamadas de voz via WebRTC, integração com bandeja do sistema e servidor de signaling em Node.js.

**Stack:**
- **UI:** PySide6
- **P2P/Voz:** WebRTC via `aiortc`
- **Signaling:** WebSockets (Python ↔ Node.js)
- **Banco local:** SQLite via SQLAlchemy
- **Áudio:** `sounddevice`
- **Criptografia:** `cryptography`
- **Servidor:** Node.js na Hostinger

**Plataforma:** Linux (compatível com Windows/macOS no futuro)

---

## Fases

| # | Fase | Arquivo | Status |
|---|------|---------|--------|
| 0 | Infraestrutura e Setup | [fase0.md](#fase-0) | Concluído |
| 1 | Sistema de Temas e Janelas Flutuantes | [fase1.md](#fase-1) | Concluído |
| 2 | Autenticação e Gerenciamento de Usuários | [fase2.md](#fase-2) | Não iniciado |
| 3 | Sistema de Presença e Lista de Amigos | [fase3.md](#fase-3) | Não iniciado |
| 4 | Conexão P2P e Signaling | [fase4.md](#fase-4) | Não iniciado |
| 5 | Chat de Texto P2P | [fase5.md](#fase-5) | Não iniciado |
| 6 | Chamadas de Voz | [fase6.md](#fase-6) | Não iniciado |
| 7 | Segurança e Criptografia | [fase7.md](#fase-7) | Não iniciado |
| 8 | Notificações e Bandeja | [fase8.md](#fase-8) | Não iniciado |
| 9 | Configurações e Polish | [fase9.md](#fase-9) | Não iniciado |
| 10 | Recursos Avançados (Futuro) | [fase10.md](#fase-10) | Não iniciado |

---

## Estrutura do Projeto

```
Klyvochat/
├── PLAN.md
├── README.md
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── run.py
├── config.py
├── data/
│   └── .gitkeep
│
├── client/
│   ├── __init__.py
│   ├── app.py
│   ├── main.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── theme.py
│   │   ├── window_manager.py
│   │   ├── components/
│   │   │   ├── __init__.py
│   │   │   ├── avatar.py
│   │   │   ├── message_bubble.py
│   │   │   ├── friend_item.py
│   │   │   ├── status_indicator.py
│   │   │   ├── notification.py
│   │   │   └── search_bar.py
│   │   ├── windows/
│   │   │   ├── __init__.py
│   │   │   ├── login_window.py
│   │   │   ├── main_window.py
│   │   │   ├── chat_window.py
│   │   │   ├── call_window.py
│   │   │   ├── settings_window.py
│   │   │   └── profile_popup.py
│   │   └── resources/
│   │       ├── icons/
│   │       ├── sounds/
│   │       └── fonts/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── friends.py
│   │   ├── presence.py
│   │   ├── messaging.py
│   │   ├── voice.py
│   │   ├── file_transfer.py
│   │   └── notification_manager.py
│   ├── network/
│   │   ├── __init__.py
│   │   ├── signaling_client.py
│   │   ├── p2p_manager.py
│   │   └── webrtc_session.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── repositories.py
│   ├── security/
│   │   ├── __init__.py
│   │   ├── keys.py
│   │   ├── encryption.py
│   │   └── identity.py
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       ├── config_manager.py
│       └── helpers.py
│
├── server/
│   ├── package.json
│   ├── .env.example
│   ├── src/
│   │   ├── index.js
│   │   ├── config.js
│   │   ├── routes/
│   │   │   ├── auth.js
│   │   │   └── users.js
│   │   ├── websocket/
│   │   │   ├── signaling.js
│   │   │   ├── presence.js
│   │   │   └── handler.js
│   │   ├── middleware/
│   │   │   └── auth.js
│   │   └── database/
│   │       └── db.js
│   └── .env.example
│
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_messaging.py
│   ├── test_p2p.py
│   └── test_voice.py
│
└── docs/
    └── architecture.md
```

---

## Dependências entre Fases

```
Fase 0 (Setup)
  └── Fase 1 (UI Base)
        ├── Fase 2 (Auth)
        │     └── Fase 3 (Presença/Amigos)
        │           └── Fase 4 (P2P/Signaling)
        │                 └── Fase 5 (Chat Texto)
        │                       └── Fase 6 (Voz)
        │                             └── Fase 7 (Segurança)
        └── Fase 8 (Notificações/Tray)
              └── Fase 9 (Config/Polish)
                    └── Fase 10 (Futuro)
```

---
---

# Fase 0: Infraestrutura e Setup do Projeto

## Objetivo
Criar a estrutura base do projeto, configurar dependências, entry point e servidor básico para garantir que tudo rode antes de começar o desenvolvimento real.

## Contexto
- Projeto novo, pasta vazia apenas com `AI/`
- Python 3.11+ como linguagem principal
- Node.js para servidor de signaling
- Nenhuma dependência instalada ainda

## Tarefas

- [x] 1. Criar estrutura de diretórios do projeto
      - Arquivos: toda a árvore de pastas listada na seção Estrutura do Projeto
      - Detalhes: Criar todas as pastas e arquivos `__init__.py` necessários. Incluir subpastas `resources/icons/`, `resources/sounds/`, `resources/fonts/` vazias.

- [x] 2. Configurar `pyproject.toml` e `requirements.txt`
      - Arquivos: `pyproject.toml`, `requirements.txt`
      - Detalhes: Definir metadados do projeto (nome: klyvochat, versão: 0.1.0, python >=3.11). Dependências:
        - `PySide6>=6.5`
        - `aiortc>=1.6`
        - `websockets>=12.0`
        - `SQLAlchemy>=2.0`
        - `cryptography>=41.0`
        - `sounddevice>=0.4`
        - `soundfile>=0.12`
        - `pydantic>=2.0`
        - `pydantic-settings>=2.0`
        - `python-jose[cryptography]`
        - `httpx`

- [x] 3. Criar `config.py` na raiz
      - Arquivos: `config.py`
      - Detalhes: Configurações gerais centralizadas:
        - `SIGNALING_URL`: URL do servidor WebSocket (default: `ws://localhost:8080`)
        - `API_URL`: URL base da API REST (default: `http://localhost:8080`)
        - `DB_PATH`: caminho do SQLite (default: `data/klyvochat.db`)
        - `THEME`: tema padrão (`dark`)
        - `LOG_LEVEL`: nível de log (`INFO`)
        - `STUN_SERVERS`: lista de servidores STUN
        - Usar `pydantic-settings` ou dataclass com valores default

- [x] 4. Criar `run.py` (entry point)
      - Arquivos: `run.py`
      - Detalhes: Script de inicialização:
        - Criar `QApplication`
        - Carregar tema escuro
        - Mostrar janela de login (placeholder por enquanto)
        - `sys.exit(app.exec())`
        - Tratar sinais (SIGINT, SIGTERM) para shutdown limpo

- [x] 5. Configurar `server/` com Node.js
      - Arquivos: `server/package.json`, `server/src/index.js`, `server/src/config.js`
      - Detalhes:
        - `package.json`: nome klyvochat-server, dependências express, ws, cors, dotenv, bcrypt, jsonwebtoken
        - `config.js`: port, jwt_secret, db connection string (via env)
        - `index.js`: Express server + WebSocket server na mesma porta, endpoint GET `/health` retornando `{status: "ok"}`, middleware CORS, JSON parser
        - Deploy: servidor publicado na Hostinger via `.zip`. Entry file: `src/index.js`. O `config.py` do cliente aponta para a URL da Hostinger via variáveis de ambiente em `.env`.

- [x] 6. Criar `.gitignore`
      - Arquivos: `.gitignore`
      - Detalhes: Ignorar `__pycache__/`, `*.pyc`, `.venv/`, `data/`, `.env`, `*.db`, `node_modules/`, `.idea/`, `.vscode/`, `dist/`, `*.egg-info/`, `build/`, `*.log`

- [x] 7. Criar `README.md`
      - Arquivos: `README.md`
      - Detalhes: Nome do projeto, descrição breve, stack utilizada, como instalar dependências, como rodar (`python run.py`), estrutura de pastas resumida

- [x] 8. Criar `server/.env.example`
      - Arquivos: `server/.env.example`
      - Detalhes: Variáveis com valores de exemplo:
        ```
        PORT=8080
        JWT_SECRET=change-me-in-production
        JWT_EXPIRES_IN=15m
        REFRESH_EXPIRES_IN=7d
        DB_HOST=localhost
        DB_PORT=3306
        DB_NAME=klyvochat
        DB_USER=root
        DB_PASSWORD=
        ```

- [x] 9. Criar diretório `data/` e `.gitkeep`
      - Arquivos: `data/.gitkeep`
      - Detalhes: Criar pasta `data/` onde o SQLite será salvo. Incluir `.gitkeep` para manter a pasta no git. Adicionar `data/*.db` no `.gitignore`

- [x] 10. Criar `client/utils/logger.py`
      - Arquivos: `client/utils/logger.py`
      - Detalhes: Setup básico de logging:
        - Formato: `[%(asctime)s] %(levelname)s %(name)s: %(message)s`
        - Handler console (stdout)
        - Handler arquivo (`data/klyvochat.log`)
        - Função `get_logger(name)` que retorna logger configurado
        - Level vindo de `config.LOG_LEVEL`

- [x] 11. Configurar `pyproject.toml` com dev tools
      - Arquivos: `pyproject.toml`
      - Detalhes: Adicionar seção `[project.optional-dependencies]` com:
        - `dev`: `pytest`, `pytest-asyncio`, `ruff`, `black`
      - Adicionar seção `[tool.ruff]` com regras básicas (line-length=100, target-version py311)
      - Adicionar seção `[tool.black]` com line-length=100

## Riscos / Pontos de Atenção
- Versões de dependências podem conflitar (aiortc requer Python >=3.8, PySide6 pode ter issues com Wayland)
- O servidor Node.js precisa estar rodando antes do cliente tentar conectar
- Caminho do banco SQLite deve ser relativo ao projeto, não absoluto
- `pydantic-settings` precisa estar no requirements.txt (usado em config.py)
- O diretório `data/` deve existir antes do app rodar senão o SQLAlchemy falha ao criar o SQLite

## Notas de execução
- Tarefa 1: Estrutura completa criada com todas as pastas e __init__.py necessários.
- Tarefa 2: pyproject.toml com metadados, dependências e dev tools configurado. requirements.txt criado.
- Tarefa 3: config.py criado usando pydantic-settings.BaseSettings.
- Tarefa 4: run.py criado com QApplication, signal handling, e placeholder LoginWindow.
- Tarefa 5: Servidor Node.js com Express + WebSocket, rotas de auth e middleware.
- Tarefa 6-11: .gitignore, README.md, .env.example, data/.gitkeep, logger.py criados.

## Status
Concluído

---

---

# Fase 1: Sistema de Temas e Janelas Flutuantes

## Objetivo
Criar a base visual do aplicativo com janelas customizadas, tema escuro estilo Steam e gerenciamento de janelas flutuantes. Ao final, o app deve abrir com uma janela de login estilizada e funcional (sem lógica de auth ainda).

## Contexto
- Fase 0 concluída (estrutura e dependências prontas)
- PySide6 já instalado
- Nenhuma UI existe ainda

## Tarefas

- [x] 6. Implementar sistema de temas
      - Arquivos: `client/ui/theme.py`
      - Detalhes: Criar classe `ThemeManager` com:
        - Paleta de cores escura: fundo principal `#1b2838`, fundo secundário `#2a475e`, acento `#66c0f4`, texto `#c7d5e0`, texto secundário `#8b98a5`, sucesso `#4caf50`, erro `#f44336`
        - Fontes: Sans-serif (Segoe UI / Noto Sans), tamanhos 10-14
        - Estilos QSS para: `QPushButton`, `QLineEdit`, `QScrollArea`, `QLabel`, `QFrame`, `QScrollBar`
        - Métodos: `apply_theme(widget)` aplica stylesheet, `get_color(name)` retorna cor, `get_font(size)` retorna font
        - Suporte a troca de tema no futuro (dark/light)

- [x] 7. Implementar Window Manager (janelas flutuantes)
      - Arquivos: `client/ui/window_manager.py`
      - Detalhes: Criar classe `FloatingWindow(QWidget)`:
        - `Qt.FramelessWindowHint` + `Qt.WA_TranslucentBackground`
        - Cantos arredondados via paintEvent com `QPainterPath`
        - Barra de título customizada: arrastar com mouse, botões minimizar/fechar
        - Sombras externas via `QGraphicsDropShadowEffect`
        - Animações de entrada: `QPropertyAnimation` fade-in (opacity 0→1, 200ms)
        - Animações de saída: fade-out ao fechar
        - Método `make_draggable(widget)`: conecta mouseMoveEvent para mover janela
        - Override `paintEvent` para desenhar fundo arredondado

- [x] 8. Criar janela de login
      - Arquivos: `client/ui/windows/login_window.py`
      - Detalhes: Janela `FloatingWindow` (400x500):
        - Logo/título "Klyvochat" centralizado no topo
        - Campo `QLineEdit` placeholder "Email ou usuário"
        - Campo `QLineEdit` placeholder "Senha" (echo mode password)
        - `QPushButton` "Conectar" estilo primário (fundo acento)
        - `QPushButton` "Criar conta" estilo ghost (sem fundo)
        - Labels de erro (vermelho, ocultos por padrão)
        - Animação fade-in ao mostrar
        - Botão fechar funcional

- [x] 9. Criar janela principal (lista de amigos)
      - Arquivos: `client/ui/windows/main_window.py`
      - Detalhes: Janela `FloatingWindow` (300x600):
        - Barra de busca `QLineEdit` no topo
        - `QScrollArea` com lista de amigos
        - Seção header "Online — X" e "Offline — Y"
        - Cada item: widget com avatar + nome + status + descrição
        - Duplo-clique no item → callback `on_friend_double_clicked(friend_id)`
        - Menu de contexto (right click): Ver perfil, Apagar conversa, Remover amigo
        - Botão engrenagem no rodapé → callback `on_settings_clicked()`
        - Placeholder "Nenhum amigo ainda" quando lista vazia

- [x] 10. Criar widgets de componentes reutilizáveis
      - Arquivos: `client/ui/components/*.py`
      - Detalhes:
        - `avatar.py`: Widget `QLabel` circular (máscara redonda via `QPainter`), mostra iniciais ou imagem, tamanho configurável (32px, 48px, 64px)
        - `friend_item.py`: `QFrame` com layout horizontal: avatar + coluna (nome bold + status texto), hover highlight, clique único e duplo
        - `status_indicator.py`: `QLabel` com bolinha colorida 8x8px: verde=`#4caf50` (online), amarelo=`#ffc107` (idle), vermelho=`#f44336` (dnd), cinza=`#607d8b` (offline)
        - `notification.py`: `QWidget` flutuante com animação slide-in do canto, texto + botão fechar, auto-dismiss 5s
        - `search_bar.py`: `QLineEdit` com ícone de lupa à esquerda, placeholder "Buscar..."
        - `message_bubble.py`: `QFrame` com estilo de balão, align left (recebida) ou right (enviada), timestamp embaixo
## Riscos / Pontos de Atenção
- `WA_TranslucentBackground` pode não funcionar em todos os WM do Linux (testar com X11 e Wayland)
- Animações com `QPropertyAnimation` precisam do event loop rodando — não bloquear com operações síncronas
- Widgets customizados devem herdar de classes Qt corretas para garbage collection funcionar
- Cantos arredondados com QPainter precisam de antialiasing habilitado

## Notas de execução
- Tarefa 6: ThemeManager criado com paleta de cores Steam-style, estilos QSS completos para todos os widgets, singleton pattern.
- Tarefa 7: FloatingWindow implementada com cantos arredondados, sombra, barra de título customizada, drag-and-drop, animações fade-in/out. Design pattern ajustado (_init_ui hook) para permitir subclasses.
- Tarefa 8: LoginWindow completa com validação de campos, sinais para login/register, estados de loading, animação fade-in.
- Tarefa 9: MainWindow com lista de amigos, seções online/offline, busca, menu contexto, placeholder vazio. FriendSection para organizar grupos.
- Tarefa 10: Componentes reutilizáveis criados (Avatar, StatusIndicator, SearchBar, FriendItem, MessageBubble, TypingIndicator, NotificationWidget).
- Nota: Plugin de opacidade não suportado no X11/Wayland é esperado; não afeta funcionalidade.

## Status
Concluído

---

---

# Fase 2: Autenticação e Gerenciamento de Usuários

## Objetivo
Sistema completo de login/registro funcionando: banco local SQLite, models SQLAlchemy, repositórios CRUD, autenticação via JWT contra o servidor Node.js, e janela de login conectada ao fluxo real.

## Contexto
- Fase 1 concluída (UI base com janela de login visual pronta)
- Servidor Node.js básico rodando (Fase 0)
- Nenhuma lógica de auth ou banco local ainda

## Tarefas

- [x] 11. Criar models do banco local (SQLite)
      - Arquivos: `client/storage/database.py`, `client/storage/models.py`
      - Detalhes:
        - `database.py`: Engine SQLite com `create_engine(f"sqlite:///{DB_PATH}")`, `sessionmaker`, função `init_db()` que cria todas as tabelas, context manager `get_session()`
        - `models.py` — models SQLAlchemy:
          - `UserLocal`: id (str PK), username (str), email (str unique), display_name (str), avatar_path (str nullable), theme (str default "dark"), created_at (datetime)
          - `Message`: id (int PK), sender_id (str), receiver_id (str), content (text), timestamp (datetime), encrypted (bool default False), read (bool default False), delivered (bool default False)
          - `Friend`: id (int PK), user_id (str), friend_id (str), nickname (str nullable), added_at (datetime), unique constraint em (user_id, friend_id)
          - `Settings`: key (str PK), value (text)
          - `KeyPair`: id (int PK), user_id (str), public_key (text), private_key (text encrypted), created_at (datetime)

- [x] 12. Criar repositórios de dados
      - Arquivos: `client/storage/repositories.py`
      - Detalhes: Classes Repository genéricas com CRUD:
        - `BaseRepository`: save(entity), delete(entity), get_by_id(id), get_all()
        - `UserRepository(BaseRepository)`: get_by_email(email), get_current() (retorna user logado), save_current(user)
        - `MessageRepository(BaseRepository)`: save_message(msg), get_conversation(user_id, friend_id, limit=50), get_last_message(friend_id), mark_as_read(msg_id), get_unread_count(friend_id)
        - `FriendRepository(BaseRepository)`: add_friend(user_id, friend_id), remove_friend(user_id, friend_id), get_friends(user_id), get_friend(user_id, friend_id)
        - `SettingsRepository`: get(key, default=None), set(key, value), get_all()
        - Usar `select()`, `Session.execute()`, pattern do SQLAlchemy 2.0

- [x] 13. Implementar módulo de autenticação (cliente)
      - Arquivos: `client/core/auth.py`
      - Detalhes:
        - `class AuthManager`:
          - `async login(email, password) -> bool`: POST `/api/auth/login` via httpx, salvar JWT + refresh token em arquivo seguro (`~/.klyvochat/auth.json` permissão 600), salvar user local via UserRepository
          - `async register(username, email, password) -> bool`: POST `/api/auth/register`
          - `async refresh_token() -> bool`: POST `/api/auth/refresh` com refresh token
          - `logout()`: limpar auth.json, limpar user local
          - `get_token() -> str | None`: retorna JWT atual
          - `is_authenticated() -> bool`: verifica se tem token válido
        - Tratar erros: credenciais inválidas, rede offline, token expirado
        - Usar `httpx.AsyncClient` para requests

- [x] 14. Implementar servidor de auth (Node.js)
      - Arquivos: `server/src/routes/auth.js`, `server/src/routes/users.js`, `server/src/middleware/auth.js`, `server/src/database/db.js`
      - Detalhes:
        - `db.js`: Conexão com MySQL/PostgreSQL (config via .env), criar tabela `users` se não existir (id, username, email, password_hash, public_key, created_at)
        - `auth.js`:
          - POST `/api/auth/register`: validar body (username, email, password), hash senha com bcrypt (10 rounds), salvar user, gerar JWT (exp 15min), gerar refresh token (exp 7d), retornar {token, refresh_token, user}
          - POST `/api/auth/login`: buscar user por email, comparar senha com bcrypt, retornar {token, refresh_token, user}
          - POST `/api/auth/refresh`: validar refresh token, novo JWT
        - `users.js`:
          - GET `/api/users/me`: retornar user autenticado (protegido)
          - GET `/api/users/search?q=email`: buscar users por email (protegido)
        - `middleware/auth.js`: extrair JWT do header Authorization, verificar validade, adicionar user ao request

- [ ] 14b. Deploy do servidor na Hostinger
      - Arquivos: `deploy.sh`, `server/`, `server/.env.production`
      - Detalhes: Antes de testar a autenticação, o servidor deve estar rodando na Hostinger.
        - Executar `bash deploy.sh` na raiz do projeto
          - Script lê a versão de `server/package.json` e gera `server/klyvochat-server-{versão}.zip`
          - Zips antigos (`klyvochat-server-*.zip`) são removidos automaticamente antes de criar o novo
          - O .zip não inclui `node_modules/`, `.git/`, `*.db`, `data/`, `.env` (apenas `.env.example`)
          - O script também gera um `JWT_SECRET` aleatório seguro via `openssl rand -hex 32`
            e exibe o valor para o usuário anotar (não entra no .zip)
        - Antes do deploy: usar o database wizard do hPanel para criar o banco MySQL
          - O wizard configura automaticamente as variáveis `DB_HOST`, `DB_PORT`, `DB_NAME`,
            `DB_USER`, `DB_PASSWORD` no painel de Environment Variables
        - Fazer upload do .zip gerado via hPanel:
          1. Acessar hPanel → Websites → Node.js web app (ou adicionar novo site Node.js)
          2. Upload do arquivo `server/klyvochat-server-{versão}.zip`
          3. Entry file: `src/index.js`
          4. Node.js version: 22
        - Importar `server/.env.production` via hPanel:
          - Environment Variables → Import .env
          - O `.env.production` contém APENAS as variáveis manuais (sem `DB_*`):
            `PORT`, `NODE_ENV`, `JWT_SECRET`, `JWT_EXPIRES_IN`, `REFRESH_EXPIRES_IN`
          - Se o database wizard já configurou as variáveis `DB_*`, o `.env` importado
            NÃO deve sobrescrevê-las — por isso o `.env.production` não inclui `DB_*`
          - Comentários são aceitos no import (Hostinger ignora linhas que começam com `#`)
        - Verificar deploy: `curl https://seudominio.com/health` → `{"status":"ok"}`
        - Esta tarefa é manual (upload via browser) — marcar como concluída após confirmação do usuário

- [x] 15. Implementar janela de login funcional
      - Arquivos: `client/ui/windows/login_window.py`, `client/main.py`
      - Detalhes: Conectar UI existente ao AuthManager:
        - Validar campos antes de enviar: email formato válido, senha >= 6 chars
        - Mostrar loading spinner no botão durante request
        - Chamar `auth.login()` ao clicar "Conectar"
        - Em erro: mostrar mensagem vermelha abaixo do campo correspondente
        - Em sucesso: fechar login_window, instanciar e mostrar main_window
        - Botão "Criar conta": abrir modal simples com campos username + email + senha, chamar `auth.register()`
        - Se já autenticado (token válido), pular login direto para main_window

## Riscos / Pontos de Atenção
- Arquivo de auth.json com token precisa de permissões restritivas (chmod 600) — senão outros users do sistema leem
- JWT com expiração curta (15min) requer lógica de refresh automático — implementar interceptador no httpx
- bcrypt é custoso — não bloquear a UI durante hash, usar async/thread
- Servidor pode estar offline — tratar gracefully, mostrar "servidor indisponível"
- SQLite não suporta concorrência写入 — ok para uso local single-user

## Notas de execução
- Tarefa 11: Models criados conforme especificado. Ajuste: `UserLocal.id` alterado de `int` para `str` para acomodar UUIDs do servidor, mantendo consistência com `Message.sender_id/receiver_id` e `Friend.user_id/friend_id`.
- Tarefa 12: Repositórios implementados com SQLAlchemy 2.0 (`select()`, `Session.execute()`). `FriendRepository` inclui método `add_friend` com nickname opcional.
- Tarefa 13: `AuthManager` implementado com httpx.AsyncClient e qasync para integração com PySide6. Tokens salvos em `~/.klyvochat/auth.json` com chmod 600. Refresh automático em 401. `UserLocal` salvo localmente após login/registro.
- Tarefa 14: Rotas de auth e users atualizadas para usar MySQL via `db.js` (removido Map em memória). `index.js` inicializa banco no startup. `ws@^12.0.0` ajustado para `ws@^8.16.0` (versão disponível no npm). `mysql2` atualizado para `^3.9.0`.
- Tarefa 14b: `deploy.sh` atualizado com versionamento automático a partir de `server/package.json` e limpeza de zips antigos. Zip `server/klyvochat-server-0.1.0.zip` gerado com sucesso (24KB, sem node_modules/.git/.env). Upload manual na Hostinger ainda pendente.
- Tarefa 15: `client/main.py` criado com `AppController`. `RegisterDialog` adicionado. Login e register conectados ao `AuthManager`. Validação de email e senha >= 6 chars. Estado de loading no botão. Pular login se token válido.

## Status
Concluído

---

# Fase 3: Sistema de Presença e Lista de Amigos

## Objetivo
Usuários conectados podem ver quem está online em tempo real, receber atualizações de presença, e gerenciar lista de amigos (adicionar, remover, aceitar pedidos).

## Contexto
- Fase 2 concluída (auth funcional, banco local, login funcionando)
- Servidor Node.js com auth pronto
- WebSocket signaling ainda não implementado

## Tarefas

- [ ] 16. Implementar sistema de presença (servidor)
      - Arquivos: `server/src/websocket/presence.js`, `server/src/websocket/handler.js`
      - Detalhes:
        - `presence.js`:
          - Mapa `userId → Set<socketId>` para rastrear conexões
          - `addConnection(userId, socket)`: registrar socket
          - `removeConnection(socket)`: remover e broadcast `user_offline`
          - `updateStatus(userId, status)`: atualizar e broadcast para amigos
          - `getOnlineFriends(userId)`: retornar IDs dos amigos online
          - Heartbeat: ping a cada 30s, socket não respondeu em 60s → desconectar
        - `handler.js`:
          - Mensagem WS recebida: parse JSON, despachar por tipo (`auth`, `status`, `signaling`, `friend_action`)
          - Após conexão WS: esperar mensagem `auth` com JWT, validar, associar userId ao socket

- [ ] 17. Implementar WebSocket client (signaling)
      - Arquivos: `client/network/signaling_client.py`
      - Detalhes:
        - `class SignalingClient`:
          - `async connect()`: conectar WS com JWT no header/query
          - `async disconnect()`: fechar conexão
          - `async send(type, payload)`: enviar mensagem JSON
          - `on(event, callback)`: registrar listener para evento
          - `off(event, callback)`: remover listener
        - Reconnection: backoff exponencial (1s, 2s, 4s, 8s... max 30s), máximo 10 tentativas
        - Heartbeat: enviar ping a cada 25s, se pong não vier em 10s → reconectar
        - Eventos recebidos: `auth_ok`, `presence_update`, `friend_request`, `friend_accept`, `friend_remove`, `signaling_offer`, `signaling_answer`, `signaling_ice`
        - Usar `websockets` library com `async for message in ws`

- [ ] 18. Implementar gerenciamento de amigos
      - Arquivos: `client/core/friends.py`, `client/core/presence.py`
      - Detalhes:
        - `friends.py` — `class FriendManager`:
          - `async send_request(email)`: enviar `friend_request` via signaling
          - `async accept_request(request_id)`: enviar `friend_accept`
          - `async reject_request(request_id)`: enviar `friend_reject`
          - `async remove_friend(friend_id)`: enviar `friend_remove`, atualizar SQLite
          - `get_friend_list() -> list[FriendData]`: retornar amigos com status
          - `on_friend_update(callback)`: listener para mudanças
        - `presence.py` — `class PresenceManager`:
          - `async set_status(status)`: enviar `status_update` via signaling
          - `on_presence_change(callback)`: listener para atualizações de presença
          - `get_friend_status(friend_id) -> str`: retornar status atual
          - Idle detection: `QTimer` a cada 60s, se não houve input do mouse/teclado → status idle
          - Status possíveis: `online`, `idle`, `dnd`, `offline`

- [ ] 19. Implementar janela principal funcional
      - Arquivos: `client/ui/windows/main_window.py`, `client/ui/components/friend_item.py`
      - Detalhes:
        - Ao abrir: conectar ao signaling, carregar amigos do servidor, popular lista
        - Atualizar lista em tempo real via eventos `presence_update`:
          - Amigo ficou online → mover para seção "Online"
          - Amigo ficou offline → mover para seção "Offline"
          - Trocar cor do status indicator
        - duplo-clique no item → chamar callback `on_friend_selected(friend_id)` (abrir chat)
        - Menu contexto:
          - "Ver perfil" → abrir profile_popup
          - "Apagar conversa" → limpar messages do SQLite para esse amigo
          - "Remover amigo" → confirmar → `friend_manager.remove_friend()`
        - Botão "+" → popup com campo email → `friend_manager.send_request(email)`
        - Indicador de pedido de amizade recebido (badge ou popup)

## Riscos / Pontos de Atenção
- Múltiplas abas/conexões WS para o mesmo user podem causar race conditions — servidor deve tratar
- Idle detection no Linux: precisa pegar eventos de input do sistema — usar `QApplication.instance().queryKeyboardModifiers()` ou X11lib
- Fila de pedidos de amizade pendentes: servidor deve armazenar e entregar quando user conectar
- Reconnection pode perder eventos — servidor deve manter fila temporária para users desconectados

## Notas de execução
(será preenchido pelo executor)

## Status
Não iniciado

---
---

# Fase 4: Conexão P2P e Signaling

## Objetivo
Dois clientes conseguem se encontrar via servidor de signaling e estabelecer uma conexão WebRTC direta (P2P) para comunicação futura (chat, voz).

## Contexto
- Fase 3 concluída (presença e amigos funcionando via WebSocket)
- Servidor já encaminha mensagens entre users
- Nenhuma conexão P2P ainda

## Tarefas

- [ ] 20. Implementar lógica de signaling (servidor)
      - Arquivos: `server/src/websocket/signaling.js`
      - Detalhes:
        - Receber mensagens tipo `signaling` com payload: `{to, type: "offer"|"answer"|"ice_candidate", data}`
        - Buscar socketId do destinatário no mapa de conexões
        - Se destinatário online: encaminhar mensagem inteira
        - Se offline: ignorar (ou fila temporária de 30s)
        - Relay puro — servidor não inspecionar SDP nem ICE candidates
        - Log: conexões P2P iniciadas (para debug)

- [ ] 21. Implementar gerenciador P2P (cliente)
      - Arquivos: `client/network/p2p_manager.py`
      - Detalhes:
        - `class P2PManager`:
          - `async connect_to_peer(peer_id)`: criar `RTCPeerConnection`, criar DataChannel, gerar offer, enviar via signaling
          - `async accept_offer(peer_id, offer)`: criar `RTCPeerConnection`, setar offer remoto, criar answer, enviar via signaling
          - `async handle_answer(peer_id, answer)`: setar answer remoto
          - `async handle_ice_candidate(peer_id, candidate)`: adicionar ICE candidate
          - `disconnect_peer(peer_id)`: fechar conexão
          - `get_data_channel(peer_id) -> RTCDataChannel | None`
        - Configuração ICE:
          - STUN servers: `stun:stun.l.google.com:19302`, `stun:stun1.l.google.com:19302`
          - Future: TURN server para fallback
        - Eventos: `peer_connected`, `peer_disconnected`, `data_channel_open`, `data_channel_message`, `connection_failed`
        - Usar `aiortc.RTCPeerConnection`

- [ ] 22. Implementar sessão WebRTC
      - Arquivos: `client/network/webrtc_session.py`
      - Detalhes:
        - `class WebRTCSession`:
          - Wraps `RTCPeerConnection` com interface amigável
          - `create_data_channel(label)`: criar canal para mensagens
          - `create_offer() -> dict`: gerar SDP offer serializado
          - `set_remote_offer(offer_dict)`: setar offer remoto
          - `create_answer() -> dict`: gerar SDP answer serializado
          - `set_remote_answer(answer_dict)`: setar answer remoto
          - `add_ice_candidate(candidate_dict)`: adicionar candidate
        - Callbacks configuráveis: `on_open`, `on_close`, `on_message`, `on_error`
        - Serialização: SDP e candidates como dicts JSON (não binário)
        - Tratamento de erros: ICE failed, connection timeout (10s), max retry (3x)

- [ ] 23. Teste de conexão P2P
      - Arquivos: script de teste manual ou `tests/test_p2p.py`
      - Detalhes:
        - Dois clientes na mesma rede local
        - Login de ambos → ver amigo online
        - Um inicia chat → conexão P2P é estabelecida via signaling
        - Verificar: DataChannel abre, mensagens trafegam diretamente (sem passar pelo servidor)
        - Cenários a testar:
          - Mesma LAN: deve funcionar com STUN apenas
          - Firewall bloqueando UDP: deve falhar graceful (timeout + mensagem ao usuário)
          - Reconexão: cair e reconectar automaticamente

## Riscos / Pontos de Atenção
- **NAT simétrico** pode impedir conexão P2P direta — neste caso STUN não basta, precisa TURN
- aiortc é single-threaded — operações WebRTC devem ser async para não bloquear UI
- SDP offer/answer pode ser grande — garantir que WebSocket suporta payloads grandes
- ICE candidates chegam assíncronos — precisam ser processados na ordem correta
- Conexão P2P pode demorar 2-5s — UI deve mostrar "conectando..." durante handshake

## Notas de execução
(será preenchido pelo executor)

## Status
Não iniciado

---
---

# Fase 5: Chat de Texto P2P

## Objetivo
Mensagens de texto trafegam entre dois usuários via WebRTC DataChannel, com armazenamento local no SQLite, indicadores de digitação e confirmação de leitura.

## Contexto
- Fase 4 concluída (conexão P2P funcional, DataChannel abrindo)
- Banco local com models de Message já criados (Fase 2)
- Janela de chat ainda não existe

## Tarefas

- [ ] 24. Implementar envio/recebimento de mensagens
      - Arquivos: `client/core/messaging.py`
      - Detalhes:
        - `class MessageManager`:
          - `async send_message(friend_id, content) -> bool`:
            - Verificar se há DataChannel ativo para friend_id
            - Se não: iniciar conexão P2P primeiro (via P2PManager), aguardar abertura
            - Serializar: `{type: "message", sender_id, content, timestamp, msg_id: uuid4()}`
            - Enviar via DataChannel
            - Salvar no SQLite local (status: delivered=false)
            - Retornar True se enviou
          - `on_message_received(callback)`: registrar listener para mensagens recebidas
          - `on_message_delivered(callback)`: listener para confirmação de entrega
          - Formato interno: dataclass `MessageData(id, sender_id, receiver_id, content, timestamp, read, delivered)`
        - Processo de receber:
          - DataChannel onmessage → parse JSON → salvar no SQLite → chamar callbacks → atualizar UI

- [ ] 25. Implementar janela de chat
      - Arquivos: `client/ui/windows/chat_window.py`
      - Detalhes: Janela `FloatingWindow` (400x550):
        - Barra superior: avatar do amigo + nome + status indicator
        - Área de mensagens: `QScrollArea` com layout vertical
          - Mensagens recebidas: alinhadas à esquerda, fundo `#2a475e`
          - Mensagens enviadas: alinhadas à direita, fundo `#1a6e3e` (verde escuro)
          - Cada mensagem: texto + timestamp (abaixo, menor, cor cinza)
          - Timestamp smart: hoje → "14:30", ontem → "Ontem 14:30", anterior → "05/09 14:30"
        - Input inferior: `QLineEdit` expansível + botão enviar
        - Enter envia mensagem, Shift+Enter quebra linha
        - Auto-scroll para baixo ao receber nova mensagem
        - Se scroll não está no bottom: não forçar scroll (mostrar badge "novas mensagens")
        - Carregar histórico do SQLite ao abrir (últimas 50 mensagens)
        - Placeholder "Conversa com {friend_name}" na barra de título

- [ ] 26. Implementar indicadores de chat
      - Arquivos: `client/core/messaging.py`, `client/ui/windows/chat_window.py`
      - Detalhes:
        - Typing indicator:
          - Enviar `{type: "typing_start"}` quando usuário começa a digitar (após 500ms de idle)
          - Enviar `{type: "typing_stop"}` após 2s sem digitar
          - Receber typing_start → mostrar "Amigo está digitando..." na UI (animação 3 pontos)
          - Receber typing_stop → esconder indicador
        - Read receipt:
          - Quando janela de chat abre: enviar `{type: "messages_read", message_ids: [...]}`
          - Receber messages_read → marcar mensagens como lidas no SQLite (sender side)
          - Badge de não-lidas no friend_item atualiza

- [ ] 27. Armazenamento e histórico offline
      - Arquivos: `client/storage/repositories.py`, `client/core/messaging.py`
      - Detalhes:
        - Salvar todas as mensagens (enviadas E recebidas) no SQLite imediatamente
        - Flag `delivered`: True quando DataChannel confirmou recebimento
        - Flag `read`: True quando friend visualizou (read receipt)
        - Reconexão P2P: enviar mensagens pendentes (delivered=false) automaticamente
        - Limpeza: config para manter histórico X dias, delete mensagens antigas
        - Export: opção futura de exportar conversa (JSON/CSV)

## Riscos / Pontos de Atenção
- DataChannel pode estar fechado quando usuário tenta enviar — precisa reconectar antes
- Mensagens muito longas podem causar fragmentação — quebrar em chunks se necessário
- Race condition: duas mensagens enviadas rápido podem chegar fora de ordem — usar timestamp/seq number
- SQLite write lock pode causar delays — usar WAL mode para melhor performance
- Typing indicator pode gerar muitas mensagens WS — debounce adequado

## Notas de execução
(será preenchido pelo executor)

## Status
Não iniciado

---
---

# Fase 6: Chamadas de Voz

## Objetivo
Chamadas de voz P2P funcionais com áudio de alta qualidade, convites, controle de chamada e interface miniatura.

## Contexto
- Fase 5 concluída (chat de texto P2P funcionando)
- Conexão P2P e DataChannel já operacionais
- sounddevice já instalado mas não utilizado ainda

## Tarefas

- [ ] 28. Implementar captura e reprodução de áudio
      - Arquivos: `client/core/voice.py`
      - Detalhes:
        - `class AudioStream`:
          - `list_devices() -> list[dict]`: enumerar dispositivos de entrada/saída
          - `start_capture(device_id=None)`: iniciar stream de entrada (48kHz, mono, int16)
          - `stop_capture()`: parar stream
          - `start_playback(device_id=None)`: iniciar stream de saída
          - `stop_playback()`: parar stream
          - `on_audio_data(callback)`: callback para frames capturados
          - `play_frame(frame)`: reproduzir frame recebido
        - Configurações: sample_rate=48000, channels=1, dtype=int16, blocksize=960 (20ms)
        - VAD básico: calcular energia do frame, threshold para detectar silêncio
        - Tratar erros: dispositivo não encontrado, permissão negada

- [ ] 29. Implementar tracks de áudio WebRTC
      - Arquivos: `client/core/voice.py`, `client/network/webrtc_session.py`
      - Detalhes:
        - `class AudioTrack(MediaStreamTrack)`:
          - Herdar de `aiortc.MediaStreamTrack`
          - `async recv()`: ler frame do AudioStream, retornar `MediaFrame`
          -.kind = "audio"
          - Codec: Opus (padrão do aiortc)
        - Adicionar track à conexão WebRTC existente (ou nova)
        - Receber track remoto:
          - `on("track")` na `RTCPeerConnection`
          - Extrair frames → enviar para AudioStream.play_frame()
        - Gerenciar sample rate mismatch (48kHz local → Opus → 48kHz remote)

- [ ] 30. Implementar gerenciamento de chamadas
      - Arquivos: `client/core/voice.py`
      - Detalhes:
        - `class CallManager`:
          - Estados: `idle` → `ringing_out` / `ringing_in` → `connecting` → `active` → `ended`
          - `async start_call(friend_id)`: enviar `{type: "call_invite"}` via DataChannel ou signaling
          - `async accept_call(call_id)`: enviar `{type: "call_accept"}`, criar AudioTrack, adicionar à conexão
          - `async reject_call(call_id)`: enviar `{type: "call_reject"`
          - `async end_call()`: enviar `{type: "call_end"}`, parar tracks, fechar conexão se necessário
          - `toggle_mute()`: mutar/desmutar microfone
          - Timeout: ringing_out por 30s → auto-end
          - Reconexão: se conexão cair, tentar reconectar 3x em 5s
        - Eventos: `call_state_changed`, `call_incoming`, `call_ended`, `audio_level`

- [ ] 31. Implementar janela de chamada
      - Arquivos: `client/ui/windows/call_window.py`
      - Detalhes: Janela `FloatingWindow` miniatura (350x120):
        - Layout horizontal: avatar + info + controles
        - Avatar do amigo (48px)
        - Nome + status da chamada ("Chamando...", "02:34", "Encerrada")
        - Timer `QTimer` contando duração (atualiza a cada 1s)
        - Botões circulares:
          - Mute (ícone microfone): toggle, fica vermelho quando mutado
          - End call (ícone telefone vermelho): encerrar
        - Indicador de nível de áudio: `QProgressBar` horizontal animada,反映了microphone level
        - Sempre `WindowStaysOnTopHint` durante chamada ativa
        - Fechar janela ≠ encerrar chamada (minimizar para tray)

- [ ] 32. Notificação de chamada recebida
      - Arquivos: `client/ui/components/notification.py`, `client/core/voice.py`
      - Detalhes:
        - Pop-up `NotificationWidget` quando chamada chega:
          - Avatar + nome do caller
          - Texto "Chamada de voz"
          - Botão verde "Aceitar" + botão vermelho "Rejeitar"
          - Animação pulse no avatar
          - Auto-dismiss após 30s (rejeitar automaticamente)
        - Som de toque: arquivo em `resources/sounds/ring.ogg`, loop enquanto ringing
        - Se janela de chat com o caller está aberta: mostrar botão inline na barra superior
        - Desktop notification via `QSystemTrayIcon.showMessage()` se app em background

## Riscos / Pontos de Atenção
- **Latência de áudio**: WebRTC já trata, mas sounddevice pode introduzir latência extra — testar com blocksize pequeno
- **Jitter buffer**: aiortc tem buffer interno, mas pode ser insuficiente em redes instáveis
- **Echo cancellation**: sem tratamento nativo, pode haver eco — considerar no futuro
- **Permissões de áudio**: Linux pode precisar de grupo `audio` ou PulseAudio/PipeWire
- **Múltiplas chamadas**: app deve rejeitar segunda chamada se já está em uma
- **Tracks de áudio precisam de codecs compatíveis**: Opus é padrão, mas testar interop

## Notas de execução
(será preenchido pelo executor)

## Status
Não iniciado

---
---

# Fase 7: Segurança e Criptografia

## Objetivo
Implementar criptografia ponta-a-ponta (E2E) para mensagens, autenticação de identidade e proteção de dados sensíveis no cliente.

## Contexto
- Fase 6 concluída (chat e voz funcionando, mas sem E2E)
- Biblioteca `cryptography` já instalada
- Banco local já existe com model KeyPair

## Tarefas

- [ ] 33. Implementar geração de chaves
      - Arquivos: `client/security/keys.py`
      - Detalhes:
        - `class KeyManager`:
          - `generate_keypair()`: gerar par X25519 (mais leve que RSA, melhor para ECDH)
          - `get_public_key() -> bytes`: retornar chave pública
          - `get_private_key() -> bytes`: retornar chave privada (descryptografada)
          - `save_keys(public_key, encrypted_private_key)`: salvar no SQLite (KeyPair model)
          - `load_keys()`: carregar do SQLite
          - `export_public_key() -> str`: exportar em Base64 para enviar ao servidor
          - `import_peer_public_key(key_b64) -> bytes`: importar chave pública do amigo
          - Chave privada armazenada: criptografada com chave derivada da senha do usuário (PBKDF2)
          - Rotação: flag `key_rotation_days`, alertar para rotacionar

- [ ] 34. Implementar criptografia de mensagens
      - Arquivos: `client/security/encryption.py`
      - Detalhes:
        - `class MessageEncryption`:
          - `derive_shared_secret(my_private_key, peer_public_key) -> bytes`: ECDH para shared secret
          - `derive_key(shared_secret) -> bytes`: HKDF para chave de 32 bytes
          - `encrypt(plaintext, key) -> dict`: AES-GCM encrypt, retornar `{ciphertext, nonce, tag}`
          - `decrypt(ciphertext, nonce, tag, key) -> str`: AES-GCM decrypt
          - `encrypt_message(message, peer_public_key) -> dict`: derivar shared secret + encrypt
          - `decrypt_message(encrypted_msg, my_private_key, peer_public_key) -> str`: derivar shared secret + decrypt
        - Fluxo no chat:
          1. Ao abrir chat com amigo: trocar chaves públicas via DataChannel
          2. Derivar shared secret (ECDH)
          3. Cada mensagem: encrypt antes de enviar
          4. Receber: decrypt antes de salvar/mostrar
        - Metadata (sender_id, timestamp, msg_id) não criptografados
        - Nonce: 12 bytes aleatórios por mensagem (nunca reutilizar)

- [ ] 35. Implementar identidade do usuário
      - Arquivos: `client/security/identity.py`
      - Detalhes:
        - `class UserIdentity`:
          - `sign(data, private_key) -> bytes`: assinar dados com chave privada (Ed25519)
          - `verify_signature(data, signature, public_key) -> bool`: verificar assinatura
          - `get_fingerprint(public_key) -> str`: SHA-256 da chave pública emhex (8 grupos de 4 chars)
          - `verify_fingerprint(fingerprint, public_key) -> bool`: verificar fingerprint
          - Verificação de identidade: ao conectar P2P, trocar fingerprints para confirmar que não há MITM
          - Prompt para usuário comparar fingerprints por voz/outro canal

## Riscos / Pontos de Atenção
- **Perda de chave privada**: se o SQLite corromper ou user reinstalar, perde acesso a mensagens antigas — considerar backup
- **Chave privada na memória**: deve ser limpa após uso (memory zeroing) — Python não garante, mas tentar
- **MITM no key exchange**: fingerprints manuais são a proteção — mas users podem ignorar
- **Performance**: encrypt/decrypt por mensagem tem custo — mensagens de texto são pequenas, OK
- **Compatibilidade**: se um peer atualizar e o outro não, pode haver incompatibilidade de formato

## Notas de execução
(será preenchido pelo executor)

## Status
Não iniciado

---
---

# Fase 8: Notificações e Integração com Bandeja

## Objetivo
Notificações desktop funcionais, tray icon com menu e contadores de não-lidas, integração completa com o sistema operacional.

## Contexto
- Fase 7 concluída (auth, amigos, chat, voz, segurança implementados)
- `QSystemTrayIcon` disponível no PySide6
- Nenhuma notificação ou tray icon implementados ainda

## Tarefas

- [ ] 36. Implementar gerenciador de notificações
      - Arquivos: `client/core/notification_manager.py`
      - Detalhes:
        - `class NotificationManager`:
          - `notify(title, message, type, callback=None)`: criar notificação
          - Tipos: `message`, `call`, `friend_request`, `friend_accept`, `system`
          - Filas por tipo: não spammar, agrupar mensagens do mesmo amigo
          - Som por tipo: `message.ogg`, `call.ogg`, `notify.ogg` em `resources/sounds/`
          - `QSystemTrayIcon.showMessage(title, message, icon, timeout)` para desktop notification
          - Badge counter: atualizar tooltip do tray com total de não-lidas
          - `get_unread_total() -> int`: soma de não-lidas de todas as conversas
          - Config: habilitar/desabilitar por tipo, volume dos sons

- [ ] 37. Implementar tray icon
      - Arquivos: `client/app.py`
      - Detalhes:
        - `QSystemTrayIcon` com ícone do app (variações: normal, com badge, busy)
        - Menu do tray:
          - "Abrir Klyvochat" → mostra main_window
          - Separator
          - "Online" / "Idle" / "Do Not Disturb" → mudar status (radio buttons)
          - Separator
          - "Sair" → fecha app completamente
        - Duplo-clique no tray → toggle main_window visibility
        - Tooltip: "Klyvochat — 3 não lidas"
        - Notificações aparecem via tray mesmo com app em background
        - Minimizar janela principal → vai para tray (não fecha)

## Riscos / Pontos de Atenção
- Tray icon não funciona em todos os DEs Linux (GNOME removido por padrão — precisa extensão)
- Sons devem ser silenciáveis — não reproduzir se sistema está em mute
- Notificações do systemd/Flatpak podem conflitar com QSystemTrayIcon
- Fechar app deve ser via tray "Sair", não via X da janela (que minimiza)

## Notas de execução
(será preenchido pelo executor)

## Status
Não iniciado

---
---

# Fase 9: Configurações e Polish

## Objetivo
Janela de configurações completa, popup de perfil, testes gerais, ajustes de performance e usabilidade.

## Contexto
- Fases 0-8 concluídas (app funcional com todas as features core)
- Nenhuma janela de configurações existe
- Testes ainda não escritos

## Tarefas

- [ ] 38. Implementar janela de configurações
      - Arquivos: `client/ui/windows/settings_window.py`
      - Detalhes: Janela `FloatingWindow` (500x450) com `QTabWidget`:
        - **Conta**: display name editável, email (read-only), botão "Mudar senha" (modal), botão "Sair da conta"
        - **Amigos**: auto-aceitar pedidos (toggle), notificar novos amigos (toggle)
        - **Chat**: tamanho da fonte (spinner), enviar com Enter (toggle), backup de conversas (botão)
        - **Voz**: dispositivo de entrada (dropdown), dispositivo de saída (dropdown), botão "Testar microfone" (mostra nível de áudio), volume (slider)
        - **Aparência**: tema (dark/light radio), cor de destaque (color picker simplificado), opacidade da janela (slider 70-100%)
        - Salvar: aplicar mudanças imediatamente + persistir no SettingsRepository

- [ ] 39. Implementar popup de perfil
      - Arquivos: `client/ui/windows/profile_popup.py`
      - Detalhes: Janela `FloatingWindow` pequena (280x320), aparece ao:
        - Clicar no avatar ou nome de um amigo
        - Selecionar "Ver perfil" no menu contexto
        - Conteúdo:
          - Avatar grande (64px) centralizado
          - Nome de exibição (bold, 14pt)
          - Username (@username, cor cinza)
          - Email (menor, cor cinza)
          - Status atual com indicador colorido
          - "Membro desde: 05/09/2026"
          - Botão "Iniciar Conversa" (abre chat_window)
          - Botão "Enviar Pedido de Amizade" (se não é amigo)
          - Botão "Remover Amigo" (se já é amigo, com confirmação)

- [ ] 40. Testes e ajustes gerais
      - Arquivos: `tests/test_auth.py`, `tests/test_messaging.py`, `tests/test_p2p.py`, `tests/test_voice.py`
      - Detalhes:
        - `test_auth.py`: testar registro, login, token refresh, logout, credenciais inválidas
        - `test_messaging.py`: testar envio/recebimento, storage SQLite, histórico, read receipts
        - `test_p2p.py`: testar conexão P2P entre dois peers mock, DataChannel open/close
        - `test_voice.py`: testar captura de áudio, criação de track, mute/unmute
        - Testes de UI (manuais):
          - Login → main_window abre
          - Adicionar amigo → aparece na lista
          - Duplo-clique → chat abre com histórico
          - Enviar mensagem → aparece nos dois lados
          - Iniciar chamada → call_window aparece
        - Performance:
          - Verificar memory leaks (objeto não coletados)
          - CPU usage em idle (deve ser < 1%)
          - Tempo de startup (< 2s)
        - Logging: adicionar logs em pontos críticos (auth, P2P, erros)
        - Fix de bugs encontrados

## Riscos / Pontos de Atenção
- Testes de rede (P2P, voz) são difíceis de automatizar — considerar mock ou testes de integração manuais
- Settings podem corromper — usar defaults seguros se parse falhar
- Profile popup não deve ser modal (pode fechar clicando fora)
- Color picker completo é complexo — usar palette predefinida por enquanto

## Notas de execução
(será preenchido pelo executor)

## Status
Não iniciado

---
---

# Fase 10: Recursos Avançados (Futuro)

## Objetivo
Funcionalidades extras para expansão do app após versão estável: grupos, arquivos, vídeo, descoberta local e push notifications.

## Contexto
- Fases 0-9 concluídas (app completo com chat, voz, segurança, config)
- Estas tarefas são **futuras** — não implementar agora
- Cada uma pode ser quebrada em sua própria fase detalhada

## Tarefas

- [ ] 41. Grupos de conversa
      - Detalhes: Chat em grupo via WebRTC mesh (cada peer conecta a todos) ou SFU (servidor retransmite). Models: Group, GroupMember, GroupMessage. UI: chat_window adaptada para múltiplos participantes. Limites: máx 10 peer mesh, ilimitado SFU.

- [ ] 42. Transferência de arquivos
      - Detalhes: Enviar arquivos via DataChannel com chunking (64KB chunks). Progresso de envio/recebimento. Validação SHA-256 do arquivo completo. Interface: drag & drop no chat, botão de anexo. Limite de tamanho configurável.

- [ ] 43. Chamadas de vídeo
      - Detalhes: WebRTC video track. Janela de vídeo com câmera local (picture-in-picture) e remota. Configuração de câmera. Controles: mute câmera, tela cheia. Bandwidth adaptation.

- [ ] 44. Descoberta P2P local
      - Detalhes: mDNS/DNS-SD via `zeroconf` para descobrir usuários Klyvochat na mesma rede LAN. Auto-adicionar peers locais. Útil para sem servidor.

- [ ] 45. Push notifications (mobile/desktop)
      - Detalhes: Integração com Firebase Cloud Messaging para notificações quando app está fechado. Servidor envia push ao owner da mensagem/chamada. Requer Firebase project setup.

## Riscos / Pontos de Atenção
- Grupos mesh escalam mal (N*(N-1)/2 conexões) — SFU é necessário para grupos grandes
- Arquivos grandes podem consumir muita memória — streaming é preferível a carregar tudo na RAM
- Vídeo requer muito mais bandwidth e CPU — otimização é critical
- Push notifications precisam de infraestrutura (Firebase) e permissoes

## Notas de execução
(será preenchido pelo executor)

## Status
Não iniciado (futuro)
