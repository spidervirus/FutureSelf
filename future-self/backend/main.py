from fastapi import FastAPI, Body
from pydantic import BaseModel

app = FastAPI()

class ChatMessageRequest(BaseModel):
    message: str
    user_id: str # Assuming user ID is passed for context

class ChatMessageResponse(BaseModel):
    response: str

@app.get('/')
async def read_root():
    return {'message': 'Future Self Backend is running!'}

@app.post('/chat')
async def chat_endpoint(request: ChatMessageRequest = Body(...)):
    # TODO: Integrate Ollama/Mistral here to generate a response
    print(f"Received message from user {request.user_id}: {request.message}")
    
    # Placeholder for AI response
    ai_response = f"Hello from your Future Self! You said: {request.message}"
    
    return ChatMessageResponse(response=ai_response)

# TODO: Add endpoints for AI interaction, user data, etc. 