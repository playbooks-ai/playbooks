from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from playbooks.core.runner import PlaybookRunner
from playbooks.config import DEFAULT_MODEL
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
    model: Optional[str] = DEFAULT_MODEL
    llm_options: Optional[Dict[str, Any]] = None
    stream: Optional[bool] = False

class PlaybookResponse(BaseModel):
    result: str

@app.post("/api/run-playbook", response_model=PlaybookResponse)
async def run_playbook(request: PlaybookRequest):
    try:
        runner = PlaybookRunner(model=request.model)
        
        if request.stream:
            async def stream_response():
                async for chunk in runner.stream(request.content):
                    if chunk.strip():
                        yield chunk

            return StreamingResponse(
                stream_response(),
                media_type="text/plain"
            )
        else:
            result = await runner.run(request.content)
            return PlaybookResponse(result=result)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/examples/{filename}")
async def get_example(filename: str):
    try:
        # Check for directory traversal in filename before constructing path
        if os.path.isabs(filename) or ".." in os.path.normpath(filename):
            raise HTTPException(status_code=400, detail="Invalid filename")
            
        examples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples/playbooks")
        file_path = os.path.join(examples_dir, filename)

        # Double check path is within examples directory
        norm_file_path = os.path.normpath(file_path)
        norm_examples_dir = os.path.normpath(examples_dir)
        if not norm_file_path.startswith(norm_examples_dir):
            raise HTTPException(status_code=400, detail="Invalid filename")
            
        # Check for file existence after security checks
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                content = f.read()
            return {"content": content}
        else:
            raise HTTPException(status_code=404, detail="Example Not Found")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
