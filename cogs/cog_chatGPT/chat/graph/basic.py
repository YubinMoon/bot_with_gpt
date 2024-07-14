from functools import partial
from typing import Annotated, Literal, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.vectorstores import VectorStore
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict

from ..checkpoint import RedisSaver
from ..prompt import BasicPrompt


class BasicState(TypedDict):
    file_data: list[Document]
    messages: Annotated[list[AnyMessage], add_messages]


async def _retrieve(
    state: BasicState, config: RunnableConfig, memory: Optional[VectorStore]
):
    if memory is None:
        return {"file_data": []}
    retriever = memory.as_retriever(search_kwargs={"k": 10})
    user_messgaes = []
    for message in state["messages"]:
        if isinstance(message, HumanMessage):
            user_messgaes.append(str(message.content))
    user_query = "\n\n".join(user_messgaes[-3:])
    if user_messgaes:
        result = retriever.invoke(user_query)
    else:
        result = retriever.invoke(state["messages"])
    return {"file_data": result}


async def _agent(state: BasicState, config: RunnableConfig, model: BaseChatModel):
    prompt = BasicPrompt()
    chain = prompt | model.with_config(tags=["final_node"])
    result = await chain.ainvoke(state)
    return {"messages": result}


def get_basic_app(
    model: Literal["gpt-4o", "claude-3-5-sonnet-20240620"],
    memory: Optional[VectorStore] = None,
):
    if "gpt" in model:
        _model = ChatOpenAI(model=model, streaming=True)
    elif "claude" in model:
        model = ChatAnthropic(model=model, streaming=True)
    else:
        raise ValueError(f"Invalid model '{model}'")

    graph_builder = StateGraph(BasicState)

    retrieve = partial(_retrieve, memory=memory)
    agent = partial(_agent, model=_model)

    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("agent", agent)

    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "agent")
    graph_builder.add_edge("agent", END)

    checkpoint = RedisSaver()

    app = graph_builder.compile(checkpointer=checkpoint)

    return app
