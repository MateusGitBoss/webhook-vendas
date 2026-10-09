# Roteiro de estudo para entrevista

## 1. Explique o projeto em 1 minuto

"É uma API em FastAPI que recebe webhooks de venda da Hotmart e da Kiwify. Primeiro confere se o aviso é autêntico: na Hotmart por um token no cabeçalho, na Kiwify por uma assinatura HMAC do corpo. Grava o aviso bruto para auditoria, sem dados pessoais. Depois traduz o formato da plataforma para um modelo interno e grava a venda com upsert, então avisos repetidos não duplicam. Tem uma regra para avisos fora de ordem: uma aprovação atrasada não desfaz um reembolso. Responde 200 rápido e manda o aviso no Discord em segundo plano. Uso SQLAlchemy com Alembic e testo tudo com Postgres de verdade no CI."

## 2. Perguntas técnicas

**O que é webhook? Diferença para polling?**
Webhook: a plataforma chama a minha URL quando algo acontece. Polling: eu pergunto de tempos em tempos se mudou algo. Webhook é imediato e não desperdiça requisições, mas eu preciso estar no ar e tratar repetição e ordem.

**Por que o mesmo aviso pode chegar mais de uma vez?**
A plataforma reenvia se não recebe 2xx a tempo (timeout, queda, deploy). Entrega "pelo menos uma vez". Então meu sistema tem que ser idempotente.

**Como garante que não duplica?**
Restrição `UNIQUE (plataforma, id_transacao)` no banco e `INSERT ... ON CONFLICT DO NOTHING`. Checar com `SELECT` antes de inserir tem condição de corrida: duas requisições simultâneas veem "não existe" e as duas inserem. → `servico.registrar_venda`

**E a mudança de status com dois avisos ao mesmo tempo?**
`SELECT ... FOR UPDATE` trava a linha até o commit; a segunda requisição espera a primeira terminar.

**E se os avisos chegarem fora de ordem?**
Cada status tem um peso: pendente < aprovada/recusada < reembolsada/cancelada/chargeback. Só atualizo para um peso maior. Aprovação atrasada depois do reembolso é ignorada. → `PESO_STATUS`

**O que é HMAC e por que `compare_digest`?**
HMAC é um hash do conteúdo misturado com uma chave secreta. Só quem tem a chave gera a mesma assinatura, e qualquer alteração no corpo muda a assinatura. `compare_digest` compara em tempo constante; com `==` dá para descobrir o segredo medindo o tempo da resposta (timing attack).

**Por que ler o corpo cru (bytes) e não o JSON?**
A assinatura é calculada sobre os bytes exatos. Se eu fizer parse e depois serializar de novo, espaços e ordem das chaves mudam e a assinatura não bate.

**Por que responder 200 para evento que não interessa?**
Se eu responder erro, a plataforma acha que falhou e reenvia indefinidamente.

**Por que guardar o aviso bruto?**
Auditoria e reprocessamento. Se houver bug no processamento, o original está lá. Gravo antes de qualquer decisão e mascaro dados pessoais.

**LGPD: o que você guarda?**
E-mail só como HMAC-SHA256 com chave secreta: consigo achar as compras de uma pessoa sem guardar o e-mail. Hash sem chave seria fácil de reverter testando uma lista de e-mails. Nome, documento e telefone não são guardados.

**Por que o aviso no Discord é em background? Qual o risco?**
Para responder rápido à plataforma. O risco é perder o aviso se o processo morrer logo depois. A solução seria uma fila (Redis + worker) ou a tabela de eventos como fila (padrão outbox).

**Por que dinheiro em centavos e `Decimal(str(valor))`?**
`197.9 * 100` em float dá `19790.000000000004`. Convertendo para string e depois `Decimal`, o valor é exato.

**SQLAlchemy x SQL puro?**
ORM dá produtividade, tipagem e migrações (Alembic). SQL puro dá controle e clareza na consulta. Aqui uso ORM no CRUD e SQL (`text`) no resumo, que tem agregação com `FILTER` e fuso horário.

**Por que o resumo usa `AT TIME ZONE 'America/Sao_Paulo'`?**
O banco guarda em UTC. Uma venda às 22h de Brasília já é dia seguinte em UTC; sem converter, o "dia" ficaria errado.

**Como você testa?**
Cada teste recria o schema aplicando as migrações do Alembic num Postgres real (no CI, um container). As dependências do FastAPI (sessão, configurações, notificador) são trocadas por versões de teste com `dependency_overrides`.

## 3. Para praticar

1. Rode o simulador e confira no banco: `SELECT status, count(*) FROM vendas GROUP BY 1`.
2. Envie um aviso com o token errado e encontre-o em `eventos_webhook`.
3. Adicione o status `PURCHASE_PROTEST` da Hotmart e escreva o teste.
4. Explique o que aconteceria sem a `UNIQUE` se dois avisos chegassem juntos.
