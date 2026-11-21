"""Ferramentas de tarefa conectadas ao Trello.

Cada função pública deste arquivo vira uma ferramenta do agente (ver agent.py).
O Gemini lê o nome, os parâmetros e a docstring de cada função e decide,
a partir da conversa, qual delas chamar — depois o ADK executa o código de
verdade e devolve o `return` como texto para o modelo responder.

Regras seguidas por todas as ferramentas aqui:
  * conexão com o Trello concentrada em uma única função auxiliar (_quadro);
  * docstring com `Args:` — é o que o modelo usa para preencher os argumentos;
  * `try/except` em todas — erro vira mensagem em português, nunca exceção
    estourando no meio da conversa;
  * `return` sempre `str`.
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from trello import TrelloClient

# Procura o arquivo .env na pasta do projeto e carrega as variáveis
load_dotenv()

# As três listas do quadro, na ordem em que aparecem
LISTAS = ("A fazer", "Em andamento", "Concluído")

# Lista em que os cards novos nascem
LISTA_INICIAL = "A fazer"


# ---------------------------------------------------------------------------
# Auxiliares (não são ferramentas: o modelo não pode chamá-las direto)
# ---------------------------------------------------------------------------

def _quadro():
    """Conecta no Trello e devolve o quadro cujo nome está no .env.

    É a única parte que fala com a API: toda ferramenta usa esta função
    em vez de repetir as credenciais.
    """
    nome_desejado = os.getenv("TRELLO_BOARD_NAME", "DIO").strip()

    cliente = TrelloClient(
        api_key=os.getenv("TRELLO_API_KEY"),
        api_secret=os.getenv("TRELLO_API_SECRET"),
        token=os.getenv("TRELLO_TOKEN"),
    )

    for quadro in cliente.list_boards():
        if quadro.name.strip().casefold() == nome_desejado.casefold():
            return quadro

    raise ValueError(
        f"Quadro '{nome_desejado}' não encontrado. "
        "Confira TRELLO_BOARD_NAME no .env e o nome do quadro no Trello."
    )


def _lista(quadro, nome_lista: str):
    """Devolve a lista (coluna) do quadro pelo nome, ignorando maiúsculas."""
    alvo = nome_lista.strip().casefold()
    for lista in quadro.get_lists("open"):
        if lista.name.strip().casefold() == alvo:
            return lista
    raise ValueError(
        f"Lista '{nome_lista}' não existe no quadro. "
        f"Listas disponíveis: {', '.join(LISTAS)}."
    )


def _status_valido(status: str) -> str:
    """Confere se o status pedido existe e devolve o nome oficial da lista.

    Aceita variações de maiúsculas/minúsculas e espaços, mas não muda o
    texto: "em andamento" vira "Em andamento".
    """
    alvo = (status or "").strip().casefold()
    for lista in LISTAS:
        if lista.casefold() == alvo:
            return lista
    raise ValueError(
        f"Status '{status}' inválido. Use um destes: {', '.join(LISTAS)}."
    )


def _formatar_data(data: str) -> str:
    """Converte a data pedida pelo usuário para o formato que o Trello aceita.

    Aceita AAAA-MM-DD ou DD/MM/AAAA e devolve um horário do meio-dia no fuso
    local (ex.: 2026-11-21T12:00:00-03:00). O meio-dia é proposital: uma data
    sem hora é interpretada como meia-noite UTC e o card apareceria com um dia
    a menos no Brasil.
    """
    texto = (data or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            momento = datetime.strptime(texto, formato)
            return momento.replace(hour=12).astimezone().isoformat()
        except ValueError:
            continue
    raise ValueError(
        f"Data '{data}' inválida. Use o formato AAAA-MM-DD (ex.: 2026-11-21)."
    )


# ---------------------------------------------------------------------------
# Ferramentas (registradas no agent.py)
# ---------------------------------------------------------------------------

def criar_tarefa(nome: str, descricao: str, data: str) -> str:
    """Cria uma tarefa (card) na lista "A fazer" do quadro.

    Args:
        nome: título curto da tarefa (ex.: "Estudar ADK").
        descricao: detalhes da tarefa; pode ser uma frase curta.
        data: data da tarefa no formato AAAA-MM-DD (ex.: 2026-11-21).
    """
    try:
        quadro = _quadro()
        lista = _lista(quadro, LISTA_INICIAL)
        vencimento = _formatar_data(data)

        card = lista.add_card(nome.strip(), (descricao or "").strip(), due=vencimento)

        return (
            f"Tarefa criada na lista '{LISTA_INICIAL}': "
            f"'{card.name}' com vencimento em {data}."
        )
    except Exception as erro:  # noqa: BLE001 - qualquer erro vira resposta amigável
        return f"Não consegui criar a tarefa: {erro}"


def listar_tarefas(status: str = "") -> str:
    """Lista as tarefas do quadro, todas ou apenas as de um status.

    Args:
        status: um dos valores "A fazer", "Em andamento" ou "Concluído".
            Deixe vazio para listar todas as tarefas.
    """
    try:
        quadro = _quadro()
        nomes_das_listas = {
            lista.id: lista.name for lista in quadro.get_lists("open")
        }

        alvo = _status_valido(status) if status and status.strip() else None

        linhas = []
        for card in quadro.get_cards():
            onde_esta = nomes_das_listas.get(card.idList, "lista desconhecida")
            if alvo and onde_esta.casefold() != alvo.casefold():
                continue
            vencimento = (
                datetime.fromisoformat(card.due).strftime("%d/%m/%Y")
                if card.due
                else "sem data"
            )
            linhas.append(f"- {card.name} [{onde_esta}] (vence em {vencimento})")

        if not linhas:
            if alvo:
                return f"Nenhuma tarefa na lista '{alvo}'."
            return "O quadro está vazio: ainda não há tarefas."

        titulo = f"Tarefas ({alvo})" if alvo else "Todas as tarefas"
        return f"{titulo}:\n" + "\n".join(linhas)
    except Exception as erro:  # noqa: BLE001
        return f"Não consegui listar as tarefas: {erro}"


def mover_tarefa(nome: str, novo_status: str) -> str:
    """Move uma tarefa para outra lista quando o usuário conta o que já fez.

    Args:
        nome: nome exato (ou parte) da tarefa que será movida.
        novo_status: para qual lista mover: "A fazer", "Em andamento"
            ou "Concluído".
    """
    try:
        quadro = _quadro()
        destino = _status_valido(novo_status)
        lista_destino = _lista(quadro, destino)

        alvo = nome.strip().casefold()
        encontradas = [
            card for card in quadro.get_cards()
            if alvo in card.name.casefold()
        ]

        if not encontradas:
            return f"Não achei nenhuma tarefa chamada '{nome}'."

        movidas = []
        for card in encontradas:
            if card.idList == lista_destino.id:
                movidas.append(f"'{card.name}' já está em '{destino}'")
                continue
            card.change_list(lista_destino.id)
            movidas.append(f"'{card.name}' → {destino}")

        return "Movimento feito:\n" + "\n".join(f"- {item}" for item in movidas)
    except Exception as erro:  # noqa: BLE001
        return f"Não consegui mover a tarefa: {erro}"
