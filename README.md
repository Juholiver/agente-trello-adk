# agente-trello-adk

Agente que organiza suas tarefas no **Trello** por conversa, usando o
**Agent Development Kit (ADK)** do Google e o **Gemini**.

Você conversa em português — ele cria, lista e move cards no seu quadro de
verdade. Cada ação é uma função Python comum, registrada como **ferramenta**
do agente: o modelo decide qual chamar e o ADK executa o código.

---

## O que o agente faz

Na primeira mensagem ele cumprimenta e pergunta **quais são as suas tarefas
para hoje, já com a data do dia**. Depois, na conversa:

- **cria** um card com nome, descrição e data;
- **lista** todas as tarefas, ou só as de um status;
- **move** o card entre `A fazer`, `Em andamento` e `Concluído` quando você
  conta o que já fez.

### Ferramentas

São três, todas em [`tarefas/tools.py`](tarefas/tools.py) e registradas em
[`tarefas/agent.py`](tarefas/agent.py):

| Ferramenta | O que faz |
|---|---|
| `criar_tarefa(nome, descricao, data)` | Cria um card na lista **A fazer**, com vencimento |
| `listar_tarefas(status)` | Lista as tarefas; `status` pode ser `A fazer`, `Em andamento`, `Concluído` ou vazio para listar todas |
| `mover_tarefa(nome, novo_status)` | Move o card para outra lista |

As funções auxiliares (`_quadro`, `_lista`, `_status_valido`,
`_formatar_data`) **não** são ferramentas: o modelo não as chama direto.
Elas concentram a conexão com o Trello, a validação de status e o formato
da data.

### Como o agente decide qual ferramenta chamar

1. a `instruction` do agente é enviada ao Gemini **junto com a data de hoje**;
2. o ADK transforma cada função de `tools` em um esquema (nome, parâmetros e
   docstring) e envia também;
3. na sua frase, o modelo escolhe a função certa e "escreve" a chamada;
4. o ADK **executa o Python de verdade** e devolve o `return` como texto;
5. o modelo transforma esse texto na resposta da conversa.

Por isso a docstring com `Args:` e a instrução alinhada às ferramentas
existentes fazem tanta diferença: é o que o modelo lê.

---

## Estrutura do projeto

```
agente-trello-adk/
├── tarefas/            # o agente (nome da pasta = nome do app no ADK)
│   ├── __init__.py
│   ├── agent.py        # instruction + registro das ferramentas
│   └── tools.py        # as funções conectadas ao Trello
├── requirements.txt
├── .env.exemplo        # modelo das credenciais (sem valores reais)
├── .gitignore          # mantém o .env fora do Git
└── README.md
```

> A pasta do agente precisa ter nome de identificador Python válido: letras,
> dígitos e `_`, sem hífen. Por isso o app chama-se `tarefas`, e não
> `agente-trello-adk`.

---

## Como configurar

Requisitos: **Python 3.10 ou superior** (o readme original do curso fala em
3.7, mas o ADK hoje exige 3.10+).

### 1. Trello

1. Crie um quadro com as listas **`A fazer`**, **`Em andamento`** e
   **`Concluído`** (nomes exatos).
2. Em [trello.com/power-ups/admin](https://trello.com/power-ups/admin), crie
   um aplicativo e pegue a **API Key** e o **API Secret**.
3. Gere o **Token** com permissão de leitura e escrita:

```
https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&key=SUA_API_KEY&name=Agente%20Trello
```

### 2. Gemini

Em [aistudio.google.com/apikey](https://aistudio.google.com/apikey), clique
em **Create API key** e copie a chave (começa com `AIza`).

### 3. Credenciais

```powershell
Copy-Item .env.exemplo .env
```

Preencha o `.env`:

```
GOOGLE_API_KEY=AIza...
TRELLO_API_KEY=...
TRELLO_API_SECRET=...
TRELLO_TOKEN=ATTA...
TRELLO_BOARD_NAME=DIO
```

`TRELLO_BOARD_NAME` é o **nome exato** do seu quadro. O `.env` está no
`.gitignore` — nunca será enviado ao Git.

### 4. Instalar e rodar

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

adk web .
```

Abra <http://127.0.0.1:8000>, escolha o app **`tarefas`** e converse.

---

## A melhoria escolhida

Das ideias propostas, esta é a que implementei:

> **Alinhar a instrução do agente às ferramentas que ele realmente tem.**

O código-base prometia mais do que entregava: a instrução citava ações que
não existiam como ferramenta, então o modelo às vezes tentava chamar algo
inventado. Hoje a `instruction` lista **exatamente** as três funções
registradas em `tools=[...]`, com os parâmetros e o formato da data, e diz
para não inventar outras.

Junto disso veio o segundo ponto da mesma melhoria:

> **`try/except` em todas as ferramentas, não só na de mudar status.**

Toda função pública de `tools.py` devolve uma mensagem em português quando
algo falha, em vez de quebrar a conversa:

```python
except Exception as erro:
    return f"Não consegui listar as tarefas: {erro}"
```

### Como testei

Primeiro validei cada ferramenta isoladamente (sem gastar cota do Gemini):

- `criar_tarefa` → card criado em `A fazer` com a data certa;
- `listar_tarefas()` → listou o card com lista e vencimento;
- `mover_tarefa` → moveu para `Em andamento`;
- `listar_tarefas("Em andamento")` → filtrou pelo status;
- `mover_tarefa(..., "Concluido")` (sem acento) →
  **`Status 'Concluido' inválido. Use um destes: A fazer, Em andamento,
  Concluído.`** — erro amigável, sem exceção estourando.

Depois, conversando no `adk web`:

| Mensagem | O que aconteceu |
|---|---|
| `Oi!` | *"Olá! Quais são as suas tarefas para hoje, 21/11/2026?"* |
| `Criar tarefa 'Estudar Google ADK' ... para 2026-11-25` | chamou `criar_tarefa` e o card apareceu no quadro |
| `Lista todas as minhas tarefas` | chamou `listar_tarefas` |
| `Terminei de estudar Google ADK` | chamou `mover_tarefa(novo_status="Concluído")` |
| `Lista só as concluídas` | chamou `listar_tarefas(status="Concluído")` |

O card final no Trello: `Estudar Google ADK [Concluído] (vence em 25/11/2026)`.

---

## Ideias para evoluir

- Corrigir a data que chega ao Trello com um dia a menos (o ajuste do fuso já
  está em `_formatar_data`, que envia meio-dia local).
- Aceitar variações de status, como `concluido` sem acento.
- Criar a ferramenta **remover tarefa**, que a instrução promete e o código
  não tem.
- Trabalhar com mais de um quadro, perguntando em qual a tarefa entra.

---

## Segurança

- Nenhuma chave, segredo ou token está versionado — o `.gitignore` ignora o
  `.env`.
- Se alguma credencial foi compartilhada em conversa ou print, regenere-a
  depois no painel do Power-Up do Trello.
