from mcpServer.models.message import Message
from mcpServer.protocols.a2a import  A2AProtocol

class Agent:
    def __init__(self, protocol: A2AProtocol):
        self.protocol = protocol

    async def handle_message(self, message: Message) -> Message:
        # Implement agent logic here
        response_text = await self.protocol.communicate(message.text)
        return Message(text=response_text)
