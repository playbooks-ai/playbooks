from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playbooks.core.runner import PlaybookRunner
from typing import Optional, Dict, Any
import os
import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

app = FastAPI(title="Playbooks API")

# Configure CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlaybookRequest(BaseModel):
    content: str
    llm_provider: Optional[str] = "anthropic"
    llm_options: Optional[Dict[str, Any]] = None

class PlaybookResponse(BaseModel):
    result: str

@app.post("/api/run-playbook", response_model=PlaybookResponse)
async def run_playbook(request: PlaybookRequest):
    try:
        # Create runner with just the LLM provider
        runner = PlaybookRunner(llm=request.llm_provider)
        result = runner.run(request.content, user_input="Hello")
        return PlaybookResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/examples/{filename}")
async def get_example(filename: str):
    try:
        examples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
        file_path = os.path.join(examples_dir, filename)
        
        # Basic security check to prevent directory traversal
        if not os.path.normpath(file_path).startswith(os.path.normpath(examples_dir)):
            raise HTTPException(status_code=400, detail="Invalid filename")
            
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Example not found")
            
        with open(file_path, "r") as f:
            content = f.read()
            
        return {"content": content}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
