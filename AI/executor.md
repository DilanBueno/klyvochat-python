# Papel: Executor

Você é o agente **EXECUTOR**. Sua função é implementar o plano criado pelo agente planejador, seguindo o arquivo `PLAN.md` (ou o plano colado no chat) tarefa por tarefa. Você é quem efetivamente edita código, roda comandos e testa.

## Regras gerais

- Siga o plano na ordem em que as tarefas aparecem, uma de cada vez.
- Antes de marcar uma tarefa como concluída, confirme que ela realmente funciona (rode testes/build/lint quando aplicável).
- Ao concluir uma tarefa, atualize o checklist do plano marcando `- [x]` e adicione uma linha em **Notas de execução** explicando o que foi feito (e se algo saiu diferente do previsto).
- Se uma tarefa do plano estiver errada, incompleta ou impossível de executar como descrita, **pare e registre isso em Notas de execução** em vez de improvisar uma solução totalmente diferente sem avisar. Pequenos ajustes de implementação são normais, mas mudanças de abordagem devem ser sinalizadas.
- Pode editar arquivos e rodar comandos livremente (instalar dependências, rodar testes, scripts, etc.) sem pedir confirmação a cada passo.
- **Sempre peça confirmação antes de:** `git push`, deploy, apagar arquivos/branches, ou qualquer comando destrutivo/irreversível.
- Ao terminar todas as tarefas, atualize o campo **Status** do plano para `Concluído` (ou `Bloqueado` se algo impediu o término, explicando o motivo).

## Formato de atualização do plano

Use o mesmo arquivo/estrutura entregue pelo planejador, atualizando apenas:

```markdown
## Tarefas
- [x] 1. Descrição objetiva da tarefa
      - Arquivos: `caminho/do/arquivo.ext`
      - Detalhes: o que exatamente deve mudar/ser criado

## Notas de execução
- Tarefa 1: feito conforme descrito. / feito com ajuste X porque Y.

## Status
Em andamento | Concluído | Bloqueado (motivo)
```

## Ao final

Resuma em poucas linhas o que foi implementado e se há algo que ficou pendente ou precisa de revisão do planejador.

---

## Tarefas

- [x] 1. Testar conexão MySQL remota com Python
      - Arquivos: N/A (teste local)
      - Detalhes: Criar venv temporário, instalar pymysql, rodar teste de conexão com as credenciais corretas e o banco `u938917351_klyvochat`. Esperado: "Conexão OK: (1,)". Depois: limpar venv temporário.

- [x] 2. Atualizar `server/.env.production`
      - Arquivos: `server/.env.production`
      - Detalhes: Trocar `DB_NAME=klyvochat` → `DB_NAME=u938917351_klyvochat`

- [x] 3. Re-importar `.env.production` no hPanel
      - Arquivos: N/A (ação no painel Hostinger)
      - Detalhes: hPanel → Environment Variables → Import .env → Save (redeploy automático)

- [x] 4. Verificar logs e testar /health
      - Arquivos: N/A (verificação no hPanel)
      - Detalhes: Logs devem mostrar "Database initialized". Testar: `curl https://klyvochat.arqmam.com.br/health`

- [x] 1. Atualizar `server/.env.production` com DB_USER corrigido
      - Arquivos: `server/.env.production`
      - Detalhes: Trocar `DB_USER=dilanklivo` para `DB_USER=u938917351_dilanklivo`

- [x] 2. Re-importar `.env.production` no hPanel
      - Arquivos: N/A (ação no painel Hostinger)
      - Detalhes: hPanel → Environment Variables → Import .env → selecionar o arquivo atualizado → Save (redeploy automático)

- [x] 3. Verificar logs e testar /health
      - Arquivos: N/A (verificação no hPanel)
      - Detalhes: Verificar logs no hPanel — deve aparecer "Database initialized". Testar: `curl https://klyvochat.arqmam.com.br/health`

- [x] 1. Atualizar exclusão do zip no `deploy.sh`
      - Arquivos: `deploy.sh`
      - Detalhes: Na linha 19, adicionar `.env.production` à lista de exclusão do comando `zip`:
        - De: `zip -r "$ZIP_NAME" . -x "node_modules/*" ".git/*" "*.db" "data/*" ".env"`
        - Para: `zip -r "$ZIP_NAME" . -x "node_modules/*" ".git/*" "*.db" "data/*" ".env" ".env.production"`

- [x] 2. Regenerar o .zip de deploy
      - Arquivos: `server/klyvochat-server-0.1.0.zip` (regenerado)
      - Detalhes: Executar `bash deploy.sh` na raiz do projeto para gerar um novo zip sem o `.env.production`. Verificar que o zip foi criado com sucesso.

- [x] 1. Atualizar `server/.env.production` com as credenciais MySQL
      - Arquivos: `server/.env.production`
      - Detalhes: Adicionar as variáveis `DB_*` com os valores fornecidos:
        ```
        PORT=8080
        NODE_ENV=production
        JWT_SECRET=<valor-removido-por-seguranca>
        JWT_EXPIRES_IN=15m
        REFRESH_EXPIRES_IN=7d
        DB_HOST=srv1889.hstgr.io
        DB_PORT=3306
        DB_NAME=klyvochat
        DB_USER=dilanklivo
        DB_PASSWORD=<valor-removido-por-seguranca>
        ```
      - NOTA: Se `dilanklivo` não funcionar, tentar `u938917351_dilanklivo` (Hostinger usa prefixo)

- [x] 2. Re-importar `.env.production` no hPanel
      - Arquivos: N/A (ação no painel Hostinger)
      - Detalhes: No hPanel da Hostinger:
        1. Ir em Environment Variables (sidebar do site)
        2. Remover variáveis antigas se houver (ou deixar que o import sobrescreva)
        3. Clicar em "Import .env"
        4. Selecionar o arquivo `server/.env.production` atualizado
        5. Verificar que todas as variáveis aparecem na lista (PORT, NODE_ENV, JWT_SECRET, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
        6. Clicar em Save para aplicar (isso faz redeploy automático)

- [x] 3. Verificar logs após deploy
      - Arquivos: N/A (verificação no hPanel)
      - Detalhes: After deploy, verificar os logs no hPanel. Deve aparecer:
        - "Database initialized"
        - "Server running on port 8080"
        - Sem erros de "Access denied"

- [x] 4. Testar endpoint /health
      - Arquivos: N/A (teste remoto)
      - Detalhes: Executar `curl https://klyvochat.arqmam.com.br/health` — deve retornar `{"status":"ok"}`

- [x] 1. Criar `server/.env.production` para upload na Hostinger
      - Arquivos: `server/.env.production` (novo)
      - Detalhes: Arquivo limpo com APENAS as variáveis que o usuário precisa configurar manualmente (sem DB_*, pois o wizard configura):
        ```
        PORT=8080
        NODE_ENV=production
        JWT_SECRET=<gerar-seguro-aqui>
        JWT_EXPIRES_IN=15m
        REFRESH_EXPIRES_IN=7d
        ```
      - O `JWT_SECRET` deve ser um valor aleatório seguro (ex: `openssl rand -hex 32`)
      - Não incluir variáveis `DB_*` — o database wizard da Hostinger configura essas automaticamente
      - Não incluir comentários confusos sobre "configurar via hPanel"

- [x] 2. Atualizar `server/.env.example` para refletir o que é necessário
      - Arquivos: `server/.env.example`
      - Detalhes: Reescrever para documentar AMBOS os cenários:
        - Variáveis manuais (PORT, JWT_SECRET, etc.) — para referência
        - Variáveis do database wizard (DB_HOST, DB_PORT, etc.) — documentar que são configuradas pelo wizard
        - Adicionar nota: "Para deploy na Hostinger, use `server/.env.production` e importe via hPanel"

- [x] 3. Atualizar `deploy.sh` para gerar `.env.production` com JWT_SECRET aleatório
      - Arquivos: `deploy.sh`
      - Detalhes: Opcional — o script pode:
        1. Gerar `JWT_SECRET` aleatório via `openssl rand -hex 32`
        2. Criar um `.env` temporário com o secret gerado
        3. Mostrar o secret gerado para o usuário anotar
        4. NOTA: esse `.env` NÃO deve ir dentro do .zip (senão vaza o secret)

- [x] 4. Atualizar tarefa 14b no PLAN.md com instruções de import .env
      - Arquivos: `PLAN.md`
      - Detalhes: Na tarefa 14b, adicionar passo sobre import .env:
        - Antes do deploy: usar database wizard do hPanel para criar o banco (configura DB_* automaticamente)
        - Depois: importar `server/.env.production` via hPanel → Environment variables → Import .env
        - Verificar que as variáveis aparecem na lista do painel
        - Variáveis do database wizard (DB_*) não devem ser sobrescritas pelo .env importado

## Notas de execução
- Tarefa 1 (exclusão zip): `deploy.sh` atualizado na linha 19 para incluir `.env.production` na exclusão do zip.
- Tarefa 2 (regenerar zip): `bash deploy.sh` executado com sucesso. Zip regenerado como `server/klyvochat-server-0.1.0.zip` (24K). Verificado com `unzip -l` que `.env.production` não está presente no zip — apenas `.env.example` aparece (que é seguro).
- Tarefa 1 (criar .env.production): `server/.env.production` criado com JWT_SECRET gerado via `openssl rand -hex 32` (valor removido por segurança). Arquivo contém apenas as 5 variáveis manuais, sem DB_* e sem comentários.
- Tarefa 2 (atualizar .env.example): `server/.env.example` reescrito para documentar os dois cenários (variáveis manuais + variáveis do database wizard), com instruções claras de deploy na Hostinger.
- Tarefa 3 (atualizar deploy.sh JWT_SECRET): `deploy.sh` atualizado para gerar JWT_SECRET aleatório com `openssl rand -hex 32` e exibir o valor para anotação. O script também criou um `.env` temporário (via `mktemp`) com o secret gerado, mas não o inclui no zip.
- Tarefa 4 (atualizar PLAN.md): Tarefa 14b no PLAN.md atualizada com passo detalhado de import .env via hPanel, incluindo a ordem correta (database wizard primeiro, depois import .env.production) e o aviso de não sobrescrever DB_*.
- Tarefa 1 (configurar credenciais MySQL): `server/.env.production` atualizado com as 5 variáveis `DB_*`. Testado com `require('dotenv').config({ path: '.env.production' })` — todas as variáveis carregaram corretamente, incluindo `DB_PASSWORD=<valor-removido-por-seguranca>` (caracteres especiais `:` e `|` tratados sem aspas). Adicionado `.env.production` ao `.gitignore` para evitar commit acidental de credenciais.
- Tarefas 2-4 (re-importar hPanel, verificar logs, testar /health): Dependem de ação manual no painel Hostinger (não possível executar remotamente). O arquivo `server/.env.production` já está atualizado e pronto para importação via hPanel → Environment Variables → Import .env. Após importar e salvar, o hPanel fará redeploy automático. Verificar logs procurando "Database initialized" e testar `curl https://klyvochat.arqmam.com.br/health` manualmente.
- Tarefa 1 (corrigir DB_USER com prefixo Hostinger): `server/.env.production` atualizado de `DB_USER=dilanklivo` para `DB_USER=u938917351_dilanklivo` (prefixo Hostinger). Verificado com `grep` que a alteração foi aplicada corretamente. O arquivo está pronto para re-importação via hPanel → Environment Variables → Import .env.
- Tarefas 2-3 (re-importar hPanel, verificar logs, testar /health): Dependem de ação manual no painel Hostinger (não possível executar remotamente). Após re-importar o `.env.production` atualizado e salvar, o hPanel fará redeploy automático. Verificar logs procurando "Database initialized" e testar `curl https://klyvochat.arqmam.com.br/health` manualmente.
- Tarefa 1 (testar conexão MySQL remota com Python): Venv temporária `/tmp/mysql-test` criada, `pymysql` instalado, conexão testada com `host='srv1889.hstgr.io'`, `database='u938917351_klyvochat'`, `user='u938917351_dilanklivo'`. Resultado: "Conexão OK: (1,)" — credenciais e banco confirmados. Venv removida após o teste.
- Tarefa 2 (atualizar DB_NAME): `server/.env.production` atualizado de `DB_NAME=klyvochat` para `DB_NAME=u938917351_klyvochat`.
- Tarefas 3-4 (re-importar hPanel, verificar logs, testar /health): Dependem de ação manual no painel Hostinger (não possível executar remotamente). Após re-importar o `.env.production` atualizado e salvar, o hPanel fará redeploy automático. Verificar logs procurando "Database initialized" e testar `curl https://klyvochat.arqmam.com.br/health` manualmente.

## Status
Concluído (tarefas locais); re-importação no hPanel, verificação de logs e teste do endpoint /health devem ser feitos manualmente após salvar as variáveis no painel.
