# 🔒 Política de segurança — Bot Integrador DPL

↩ [README do projeto](README.md)

Este repositório é **público**. O bot consulta dados de rede elétrica pelo Telegram e responde a uma API usada pela equipe técnica da DPL.

## Como reportar uma vulnerabilidade
Use o botão **Report a vulnerability** na aba **Security** deste repositório. O relato fica **privado** entre quem reporta e a equipe até a correção.
**Não abra issue, discussão ou PR público** com a falha, e **nunca cole** token, senha, sessão do Telegram, coordenadas reais ou dado de cliente.

## O que fazemos
- Confirmamos o recebimento em até **2 dias úteis**.
- Credencial exposta é tratada como urgente: **revogar e trocar primeiro**, investigar depois.
- A correção entra pela `main` (PR + testes) e sai numa **versão nova** (`vX.Y.Z`), registrada no `CHANGELOG.md`.

## Versões com correção de segurança
Somente a **última versão** liberada para produção (a tag mais nova).

## Regras do projeto
`.env`, tokens e a sessão do Telegram **nunca** vão para o git · dependências com alerta (Dependabot) são tratadas na semana · exemplos, prints e testes usam dados fictícios.
