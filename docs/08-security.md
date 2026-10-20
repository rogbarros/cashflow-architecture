# 08 — Segurança da Integração

> O enunciado lista “critérios de segurança de integração” como **diferencial**.
> Aqui eles são tratados como **requisitos de arquitetura** (não como hardening posterior).

## 1. Superfície e fronteiras de confiança

```
[Internet] ──▶ LB ──▶ cashflow-service ──▶ broker ──▶ consolidation-service
   (não confiável)      (confiável)         (confiável interno)
```

- O único ponto exposto é a **API** (atrás de LB/WAF/TLS).
- Broker e bancos ficam em **rede privada**, sem exposição pública.
- O evento trafega em **canal interno autenticado**.

## 2. Autenticação e autorização

| Ator | Mecanismo | Nota |
|---|---|---|
| Comerciante → API | **OAuth2/JWT** ou **API Key** por comerciante | escopo por `merchant_id` |
| Serviço → broker | credencial de broker em **secret manager** | nunca em código |
| Serviço → serviço | rede privada + mTLS (opcional) | defesa em profundidade |

- **Autorização por recurso:** o token só dá acesso aos **seus** lançamentos
  (`merchant_id` do token = dono do dado). Evita IDOR.
- **Menor privilégio:** o consumidor só lê a fila e escreve o agregado — sem acesso à
  API de lançamento.

## 3. Integridade do evento (não repúdio)

| Controle | Descrição |
|---|---|
| **Assinatura do evento** | Cada evento é assinado (HMAC) pelo produtor; o consumidor valida antes de aplicar. |
| **`event_id` imutável** | Identidade estável (base da idempotência, ADR-0005). |
| **Schema validado** | O consumidor valida o contrato do evento; evento inválido → DLQ, não corrupção. |
| **Sem PII no evento** | O contrato carrega o mínimo necessário (valores e datas; sem dados pessoais). |

## 4. Proteções na API de ingestão

| Risco | Mitigação |
|---|---|
| Injeção / payload malicioso | validação de schema (Pydantic), rejeição de campos inesperados |
| Abuso / DoS | rate limiting por comerciante; WAF |
| Picos legítimos | fila absorve (RNF-02) em vez de derrubar o serviço |
| Valores inválidos | `amount > 0`; `type ∈ {CREDIT,DEBIT}`; datas válidas |
| Replay de requisição | chave de idempotência opcional no `POST` + `event_id` determinístico |

## 5. Dados em repouso e em trânsito

- **Em trânsito:** TLS 1.2+ em todas as conexões; broker com TLS.
- **Em repouso:** criptografia do volume do banco (KMS); campos sensíveis cifrados se houve PII (aqui não há).
- **Segregação:** banco de lançamentos e de consolidado com credenciais distintas.

## 6. Segredos e configuração

- Segredos via **secret manager** (AWS Secrets Manager / Vault), nunca no repositório.
- Rotação de credenciais de broker e de API.
- Princípio do **menor privilégio** em IAM (role por serviço).

## 7. Auditoria e compliance

| Item | Como |
|---|---|
| Trilha de auditoria | Lançamentos imutáveis + log estruturado com `correlation_id` |
| Retenção | 5 anos (configurável) |
| LGPD | Sem PII no evento; dado do comerciante isolado por `merchant_id` |
| Não repúdio | Assinatura de evento + log de consumo |

## 8. Checklist de segurança da integração

- [ ] API autenticada (JWT/API Key) e autorizada por `merchant_id`
- [ ] Canal interno (broker) autenticado, em rede privada
- [ ] Evento assinado (HMAC) e schema validado no consumo
- [ ] Sem PII no contrato do evento
- [ ] Segredos em secret manager, com rotação
- [ ] Criptografia em trânsito (TLS) e repouso (KMS)
- [ ] Rate limiting e WAF na borda
- [ ] Logs com correlação e retenção definida
- [ ] Menor privilégio por serviço (IAM)
