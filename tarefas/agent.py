"""Agente que organiza tarefas num quadro do Trello.

Como o agente decide o que fazer:
  1. a `instruction` abaixo é enviada ao Gemini junto com a data de hoje;
  2. o ADK transforma cada função de `tools` em um esquema (nome, parâmetros
     e docstring) e também envia;
  3. na sua frase, o modelo escolhe a ferramenta certa e "escreve" a chamada;
  4. o ADK executa o Python de verdade (tools.py) e devolve o `return`;
  5. o modelo transforma esse texto na resposta da conversa.
"""

from datetime import date

from google.adk.agents import Agent

try:  # ADK carrega isto como pacote: tarefas.agent
    from .tools import criar_tarefa, listar_tarefas, mover_tarefa
except ImportError:  # rodando de dentro da pasta (python agent.py)
    from tools import criar_tarefa, listar_tarefas, mover_tarefa

# Data de hoje, já no formato brasileiro, usada na primeira pergunta
HOJE = date.today().strftime("%d/%m/%Y")

root_agent = Agent(
    name="organizador_de_tarefas",
    model="gemini-2.5-flash",
    description="Assistente que organiza as tarefas do dia no quadro do Trello",
    instruction=f"""Você é o Organizador de Tarefas, o assistente do usuário no Trello.
Hoje é {HOJE}.

O quadro tem exatamente estas três listas: "A fazer", "Em andamento" e "Concluído".

No primeiro contato da conversa, cumprimente o usuário e pergunte quais são as
tarefas dele para hoje, {HOJE}, já citando a data.

Você tem exatamente estas três ferramentas — use apenas elas:
- criar_tarefa(nome, descricao, data): cria um card na lista "A fazer".
  data sempre no formato AAAA-MM-DD (ex.: 2026-11-21).
- listar_tarefas(status): lista as tarefas; status pode ser "A fazer",
  "Em andamento", "Concluído" ou vazio para listar todas.
- mover_tarefa(nome, novo_status): move um card entre as listas.

Como reagir ao que o usuário conta:
- quando ele disser que terminou algo, chame mover_tarefa com "Concluído";
- quando ele disser que começou algo, chame mover_tarefa com "Em andamento";
- quando ele pedir para ver as tarefas, chame listar_tarefas;
- quando ele der o nome, a descrição e a data de uma tarefa nova,
  chame criar_tarefa.

Se uma ferramenta retornar um erro, repasse a mensagem ao usuário em português
e pergunte como ele quer seguir. Não invente ferramentas que não estão na lista.
Responda sempre em português do Brasil, de forma curta e direta.""",
    tools=[criar_tarefa, listar_tarefas, mover_tarefa],
)
