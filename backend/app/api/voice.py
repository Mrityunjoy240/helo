from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import json
import logging
import os
import time
from uuid import uuid4
from collections import defaultdict

from app.services.rag import RAGService
from app.config import settings
from app.services.tts import TTSService
from app.services.stt import STTService
from app.services.conversation_memory import ConversationMemory

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
rag_service = RAGService()
tts_service = TTSService()
stt_service = STTService()
conversation_memory = ConversationMemory()

# Audio cache for session-based responses (stores text responses, not audio bytes)
audio_cache: Dict[str, str] = {}

@router.websocket("")
async def voice_websocket(websocket: WebSocket):
    session_id = f"session_{int(time.time())}_{hash(websocket) % 10000}"
    client_id = str(uuid4())
    start_time = time.time()
    
    await websocket.accept()
    logger.info(f"[{session_id}] WebSocket connected from {websocket.client} (Client ID: {client_id})")
    
    # Send ready message with session ID
    await websocket.send_text(json.dumps({
        "type": "ready",
        "session_id": session_id
    }))
    
    # Initialize conversation memory for this session
    conversation_memory.create_session(session_id)
    
    try:
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                received_time = time.time()
                # logger.debug(f"[{session_id}] Received data at {received_time:.3f}s: {data[:50]}...")
                
                message_data = json.loads(data)
                
                if message_data.get("type") == "transcript":
                    transcript = message_data.get("text", "")
                    
                    if not transcript.strip():
                        continue
                        
                    logger.info(f"[{session_id}] Processing transcript: '{transcript}'")
                    
                    # Add to conversation memory
                    conversation_memory.add_interaction(
                        session_id, 
                        user_message=transcript, 
                        bot_response=""
                    )
                    
                    # Check if this query has been cached for this session
                    cache_key = f"{session_id}:{transcript.lower().strip()}"
                    
                    if cache_key in audio_cache:
                        logger.info(f"[{session_id}] Sending cached voice response")
                        # Send cached response
                        await websocket.send_text(json.dumps({
                            "type": "answer",
                            "text": audio_cache[cache_key], # Note: This seems to store text, not audio bytes based on original code usage
                            "session_id": session_id
                        }))
                        continue
                    
                    # Send transcript back to confirm receipt
                    await websocket.send_text(json.dumps({
                        "type": "transcript",
                        "text": transcript
                    }))
                    
                    # Process the query using RAG
                    process_start = time.time()
                    try:
                        # Check if Groq client is available
                        if not settings.groq_client:
                            error_msg = f"I'm having trouble connecting to the AI service."
                            await websocket.send_text(json.dumps({
                                "type": "answer",
                                "text": error_msg,
                                "session_id": session_id
                            }))
                            continue
                        
                        rag_service.set_clients(settings.groq_client, {
                            'name': settings.college_name,
                            'admissions_phone': settings.admissions_phone,
                            'support_email': settings.support_email
                        })
                        
                        # Helper for safe sending
                        async def safe_send(msg):
                            try:
                                await websocket.send_text(json.dumps(msg))
                                return True
                            except (WebSocketDisconnect, RuntimeError):
                                logger.warning(f"[{session_id}] Socket closed. Aborting.")
                                return False

                        import re
                        sentence_buffer = ""
                        full_response = ""
                        
                        async def process_sentence(text_block):
                            text_block = text_block.strip()
                            if not text_block: return
                            
                            try:
                                # Generate TTS URL
                                tts_start = time.time()
                                audio_bytes = await tts_service.text_to_speech(text_block)
                                
                                # Save to temp file
                                filename = f"voice_{session_id}_{int(time.time())}_{hash(text_block)}.wav"
                                filepath = os.path.join(settings.temp_audio_dir, filename)
                                os.makedirs(settings.temp_audio_dir, exist_ok=True)
                                
                                with open(filepath, "wb") as f:
                                    f.write(audio_bytes)
                                
                                logger.info(f"[{session_id}] Sentence TTS ready: {filename} ({time.time() - tts_start:.2f}s)")
                                
                                # Send audio URL to client Safely
                                if not await safe_send({
                                    "type": "audio_url",
                                    "url": f"/audio/{filename}"
                                }): return False
                                
                            except Exception as tts_e:
                                logger.error(f"[{session_id}] Sentence TTS failed: {tts_e}")
                            return True

                        # Stream the RAG response
                        async for result in rag_service.query_stream(transcript, session_id):
                            if result["type"] == "answer_chunk":
                                chunk = result["text"]
                                full_response += chunk
                                sentence_buffer += chunk
                                
                                # Send text chunk to frontend instantly
                                if not await safe_send({
                                    "type": "answer_chunk",
                                    "text": chunk
                                }): break # Socket closed
                                
                                # Buffer management for sentences
                                if any(punct in chunk for punct in [".", "?", "!"]):
                                    parts = re.split(r'(?<=[.?!])\s+', sentence_buffer)
                                    if len(parts) > 1:
                                        should_break = False
                                        for s in parts[:-1]:
                                            if len(s.split()) > 2:
                                                if not await process_sentence(s):
                                                    should_break = True
                                                    break
                                        if should_break: break
                                        sentence_buffer = parts[-1]
                                        
                            elif result["type"] == "answer":
                                full_response = result["answer"]
                                break
                            elif result["type"] == "error":
                                await safe_send({"type": "error", "message": result["message"]})
                                break
                        
                        # Process remaining buffer
                        if sentence_buffer.strip():
                            await process_sentence(sentence_buffer)
                            
                        # Final confirmation
                        await safe_send({
                            "type": "answer",
                            "text": full_response,
                            "session_id": session_id
                        })
                        
                        # Update conversation memory
                        conversation_memory.update_last_response(session_id, full_response)
                        
                    except Exception as e:
                        logger.error(f"[{session_id}] Error in streaming / processing: {e}", exc_info=True)
                        await websocket.send_text(json.dumps({
                            "type": "error", 
                            "message": "Encountered an error processing your request."
                        }))
                
                elif message_data.get("type") == "interrupt":
                    # Handle interruption if needed
                    logger.info(f"[{session_id}] Interruption received")
                    # Could implement interruption logic here if needed
                
            except json.JSONDecodeError:
                logger.error(f"[{session_id}] Invalid JSON received")
                continue
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"[{session_id}] Error in websocket loop: {e}", exc_info=True)
                break
                
    except WebSocketDisconnect:
        duration = time.time() - start_time
        logger.info(f"[{session_id}] WebSocket disconnected after {duration:.2f}s")
    except Exception as e:
        logger.error(f"[{session_id}] Unexpected error in websocket: {e}", exc_info=True)
    finally:
        # Cleanup session data
        conversation_memory.delete_session(session_id)
        # Clear any cached audio for this session (optional)
        keys_to_remove = [key for key in audio_cache if key.startswith(session_id)]
        for key in keys_to_remove:
            del audio_cache[key]