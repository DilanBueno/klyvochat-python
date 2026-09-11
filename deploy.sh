#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/server"

VERSION="$(grep -E '"version"' package.json | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' || true)"
if [[ -z "${VERSION}" ]]; then
  echo "Aviso: não foi possível ler a versão de package.json, usando 0.0.0"
  VERSION="0.0.0"
fi

ZIP_NAME="klyvochat-server-${VERSION}.zip"

echo "Removendo zips antigos..."
rm -f klyvochat-server-*.zip

echo "Criando ${ZIP_NAME} (excluindo node_modules/, .git/, *.db, data/, .env)..."
zip -r "$ZIP_NAME" . -x "node_modules/*" ".git/*" "*.db" "data/*" ".env" ".env.production"

ZIP_PATH="${SCRIPT_DIR}/server/${ZIP_NAME}"
ZIP_SIZE="$(du -h "$ZIP_PATH" | cut -f1)"

echo ""
echo "Gerado: ${ZIP_PATH} (versão ${VERSION}, ${ZIP_SIZE})"
echo ""

# --- Gerar JWT_SECRET aleatório para configurar no hPanel ---
JWT_SECRET="$(openssl rand -hex 32)"
echo "JWT_SECRET gerado (anote esse valor para configurar no hPanel):"
echo "  ${JWT_SECRET}"
echo ""

# Criar .env temporário com o secret gerado (NÃO entra no zip, NÃO vai para o git)
TEMP_ENV="$(mktemp)"
cat > "$TEMP_ENV" <<EOF
PORT=8080
NODE_ENV=production
JWT_SECRET=${JWT_SECRET}
JWT_EXPIRES_IN=15m
REFRESH_EXPIRES_IN=7d
EOF
echo "Arquivo temporário criado: ${TEMP_ENV}"
echo "IMPORTANTE: esse .env NÃO deve ser incluído no zip (o secret seria exposto)."
echo "Importe server/.env.production via hPanel → Environment Variables → Import .env"
echo "ou copie as variáveis manualmente a partir do valor acima."
echo ""

echo "Próximos passos (hPanel):"
echo "1. Websites → Node.js web app (ou adicione o site)"
echo "2. Faça upload do arquivo ${ZIP_NAME}"
echo "3. Entry file: src/index.js"
echo "4. Node.js version: 22"
echo "5. Use o database wizard do hPanel para criar o banco (configura DB_* automaticamente)"
echo "6. Importe server/.env.production via hPanel → Environment Variables → Import .env"
echo "   - As variáveis DB_* já configuradas pelo wizard NÃO devem ser sobrescritas"
echo "7. Clique em Deploy / Restart"