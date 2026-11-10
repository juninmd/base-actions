#!/usr/bin/env bash
# Instala um scanner (gitleaks | trufflehog | trivy) a partir do release oficial,
# com integridade conferida, e publica o diretorio no PATH do job.
#
#   install-tool.sh <ferramenta> <versao> <diretorio-destino>
#
# Por que um script unico: as tres instalacoes eram copias quase iguais dentro de
# action.yml diferentes, e cada copia conferia o tarball SO contra o checksums.txt
# do proprio release. Isso pega download corrompido, mas nao pega release
# adulterado: quem troca o tarball troca o checksums.txt junto (foi o que
# aconteceu com tags do Trivy em 2026). Para as versoes padrao o sha256 fica
# FIXADO aqui embaixo, revisado em PR; o checksums.txt do release so vale como
# fallback para versao customizada, e com aviso.
#
# O binario restaurado do cache tambem e conferido contra o hash fixado: cache do
# Actions e compartilhado entre workflows do repo, e um binario de seguranca
# trocado ali rodaria com o token de todo job seguinte.
set -euo pipefail

tool="${1:?uso: install-tool.sh <ferramenta> <versao> <destino>}"
version="${2:?versao ausente}"
dest="${3:?diretorio de destino ausente}"

# ferramenta|versao|arch|sha256 do tarball|sha256 do binario extraido
PINNED='
gitleaks|8.30.1|X64|551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb|88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509
gitleaks|8.30.1|ARM64|e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080|00e91bbe655bd7c47753e8cfe61cb76ea1a5d7e7702fe161ee40102b46b3823b
trufflehog|3.99.8|X64|7c3b02f160f28929a467e29e20fba98746e0729f6e37c3c25761e4f8789abe08|0f1dff85dbf3d4bcc55594e187ecc0a5fe1eea8810a37eb1845f2c263566fb40
trufflehog|3.99.8|ARM64|a0382d83dd58c967af5dd0175cc732c62c836ab1d15dc9ae71b01a2d3f0911b2|92136e058307d1f6dab56d350f569ca1031f39c31b2e3aea6a53b991f03d8c91
trivy|0.76.2|X64|bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf|6a972c69606c7b3ea4c6bdcc6fc9332ea9ad38381624310c1e85cc77345909f3
trivy|0.76.2|ARM64|ab9d51f86e6a5fb936f605faff6b593ac51bc378fff4d3e8b9d58358b9c367c3|7844c3851b28470b6d7f0975fa0b3262c5b2272c9a54a91f522801bb8926f51f
'

# A versao entra em URL e em nome de arquivo: so o formato de versao passa.
if ! printf '%s' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "::error::versao invalida para $tool: '$version' (esperado MAJOR.MINOR.PATCH)"
  exit 1
fi

arch="${RUNNER_ARCH:-}"
if [ -z "$arch" ]; then
  case "$(uname -m)" in
    x86_64) arch=X64 ;;
    aarch64 | arm64) arch=ARM64 ;;
    *) arch=unknown ;;
  esac
fi
if [ "$(uname -s)" != "Linux" ]; then
  echo "::error::$tool: so runners Linux sao suportados (recebido: $(uname -s))"
  exit 1
fi

case "$tool:$arch" in
  gitleaks:X64) asset="gitleaks_${version}_linux_x64.tar.gz" ;;
  gitleaks:ARM64) asset="gitleaks_${version}_linux_arm64.tar.gz" ;;
  trufflehog:X64) asset="trufflehog_${version}_linux_amd64.tar.gz" ;;
  trufflehog:ARM64) asset="trufflehog_${version}_linux_arm64.tar.gz" ;;
  trivy:X64) asset="trivy_${version}_Linux-64bit.tar.gz" ;;
  trivy:ARM64) asset="trivy_${version}_Linux-ARM64.tar.gz" ;;
  gitleaks:* | trufflehog:* | trivy:*)
    echo "::error::arquitetura nao suportada pelo $tool: $arch"
    exit 1
    ;;
  *)
    echo "::error::ferramenta desconhecida: $tool (use gitleaks, trufflehog ou trivy)"
    exit 1
    ;;
esac

case "$tool" in
  gitleaks)
    base="https://github.com/gitleaks/gitleaks/releases/download/v${version}"
    sums="gitleaks_${version}_checksums.txt"
    ;;
  trufflehog)
    base="https://github.com/trufflesecurity/trufflehog/releases/download/v${version}"
    sums="trufflehog_${version}_checksums.txt"
    ;;
  trivy)
    base="https://github.com/aquasecurity/trivy/releases/download/v${version}"
    sums="trivy_${version}_checksums.txt"
    ;;
esac

pin_tar=""
pin_bin=""
while IFS='|' read -r p_tool p_version p_arch p_tar p_bin; do
  if [ "$p_tool" = "$tool" ] && [ "$p_version" = "$version" ] && [ "$p_arch" = "$arch" ]; then
    pin_tar="$p_tar"
    pin_bin="$p_bin"
  fi
done <<< "$PINNED"

sha_of() { sha256sum "$1" | cut -d' ' -f1; }

publish() {
  if [ -n "${GITHUB_PATH:-}" ]; then
    echo "$dest" >> "$GITHUB_PATH"
  fi
}

bin="$dest/$tool"

if [ -x "$bin" ]; then
  if [ -n "$pin_bin" ]; then
    if [ "$(sha_of "$bin")" = "$pin_bin" ]; then
      echo "::notice::$tool $version reaproveitado do cache (sha256 do binario confere)"
      publish
      exit 0
    fi
    echo "::warning::$tool no cache NAO confere com o sha256 fixado — descartando e baixando de novo"
  elif "$bin" --version 2>&1 | grep -qF "$version" || "$bin" version 2>&1 | grep -qF "$version"; then
    echo "::notice::$tool $version reaproveitado do cache (versao sem hash fixado)"
    publish
    exit 0
  fi
fi
rm -rf "$dest"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

curl -fsSL --retry 3 --retry-delay 2 -o "$work/$asset" "$base/$asset"

if [ -n "$pin_tar" ]; then
  got="$(sha_of "$work/$asset")"
  if [ "$got" != "$pin_tar" ]; then
    echo "::error::$tool $version: sha256 do release ($got) difere do fixado no base-actions ($pin_tar). Release adulterado ou republicado — instalacao abortada."
    exit 1
  fi
else
  echo "::warning::$tool $version nao tem sha256 fixado no base-actions; conferindo apenas contra o checksums.txt do proprio release"
  curl -fsSL --retry 3 --retry-delay 2 -o "$work/$sums" "$base/$sums"
  line="$(grep -E "[[:space:]]\*?${asset}\$" "$work/$sums" || true)"
  if [ -z "$line" ]; then
    echo "::error::$asset nao aparece em $sums"
    exit 1
  fi
  (cd "$work" && printf '%s\n' "$line" | sha256sum -c -)
fi

tar -xzf "$work/$asset" -C "$work" "$tool"
chmod +x "$work/$tool"

if [ -n "$pin_bin" ] && [ "$(sha_of "$work/$tool")" != "$pin_bin" ]; then
  echo "::error::$tool $version: binario extraido nao confere com o sha256 fixado"
  exit 1
fi

# Roda o binario antes de publicar: um download que extrai mas nao executa nao
# pode virar entrada de cache.
"$work/$tool" --version > /dev/null 2>&1 || "$work/$tool" version > /dev/null

# So publica o diretorio depois do binario pronto e validado, para nunca deixar
# estado parcial no caminho que sera cacheado.
mkdir -p "$dest"
mv "$work/$tool" "$bin"
echo "::notice::$tool $version instalado (sha256 $(sha_of "$bin"))"
publish
