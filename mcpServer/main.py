import logging

from fastapi import FastAPI, HTTPException, Depends

from mcpServer.agents.base_agent import Agent
from mcpServer.models.message import Message
from mcpServer.protocols.a2a import A2AProtocol

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Agentic AI Chatbot")

def get_agent():
    return Agent(protocol=A2AProtocol())

@app.post("/chat", response_model=Message)
async def chat(message: Message, agent: Agent = Depends(get_agent)):
    try:
        response = await agent.handle_message(message)
        return response
    except Exception as e:
        logging.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
