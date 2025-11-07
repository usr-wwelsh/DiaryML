"""
DiaryML - FastAPI Backend
Main server for the private AI diary companion
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import base64
import os
import shutil
import zipfile
import io

# Import DiaryML modules
from database import get_database, DiaryDatabase
from rag_engine import get_rag_engine
from analytics import get_analytics, DeepAnalytics
from emotion_detector import get_emotion_detector
from qwen_interface import get_qwen_interface
from pattern_analyzer import get_pattern_analyzer
from recommender import get_recommender
from temporal_intelligence import TemporalIntelligence
from mobile_auth import create_access_token, verify_token, hash_password, Token, MobileAuthError


# Pydantic models
class UnlockRequest(BaseModel):
    password: str


class EntryCreate(BaseModel):
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    entry_id: Optional[int] = None


# Mobile-specific models
class MobileLoginRequest(BaseModel):
    password: str


class MobileSyncRequest(BaseModel):
    last_sync: Optional[str] = None  # ISO timestamp of last sync
    pending_entries: Optional[List[Dict[str, Any]]] = []  # Entries to upload


class MobileSyncResponse(BaseModel):
    success: bool
    new_entries: List[Dict[str, Any]]
    updated_entries: List[Dict[str, Any]]
    deleted_entry_ids: List[int]
    server_timestamp: str
    sync_conflicts: List[Dict[str, Any]] = []


# Security
security = HTTPBearer()


# Initialize FastAPI app
app = FastAPI(
    title="DiaryML",
    description="Private AI-powered diary and creative companion",
    version="1.0.0"
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
app_state = {
    "unlocked": False,
    "db": None,
    "rag": None,
    "emotion_detector": None,
    "qwen": None,
    "pattern_analyzer": None,
    "recommender": None,
    "analytics": None,
    "temporal": None
}


# === Authentication Endpoints ===

@app.post("/api/unlock")
async def unlock(request: UnlockRequest):
    """Unlock the diary with password"""
    try:
        # Initialize database with password
        db = DiaryDatabase(password=request.password)

        # Verify password is correct
        if not db.verify_password():
            raise HTTPException(status_code=401, detail="Incorrect password")

        # Initialize schema
        db.initialize_schema()

        # Store in app state
        app_state["db"] = db
        app_state["unlocked"] = True

        # Initialize other components (only if not already initialized)
        if not app_state.get("rag"):
            app_state["rag"] = get_rag_engine()
        if not app_state.get("emotion_detector"):
            app_state["emotion_detector"] = get_emotion_detector()
        if not app_state.get("pattern_analyzer"):
            app_state["pattern_analyzer"] = get_pattern_analyzer()
        if not app_state.get("recommender"):
            app_state["recommender"] = get_recommender()

        # Always recreate these as they depend on the database instance
        app_state["analytics"] = get_analytics(db)
        app_state["temporal"] = TemporalIntelligence(db)

        # Load Qwen model (this might take a moment)
        if not app_state.get("qwen"):
            try:
                app_state["qwen"] = get_qwen_interface()
            except Exception as e:
                print(f"Warning: Could not load Qwen model: {e}")
                app_state["qwen"] = None

        return {
            "success": True,
            "message": "Diary unlocked successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Check if diary is unlocked and encryption status"""
    db: DiaryDatabase = app_state.get("db")

    return {
        "unlocked": app_state["unlocked"],
        "ai_loaded": app_state.get("qwen") is not None,
        "encrypted": db.is_encrypted if db else False
    }


# === Mobile App Endpoints ===

@app.post("/api/mobile/login", response_model=Token)
async def mobile_login(request: MobileLoginRequest):
    """
    Mobile app login - returns JWT token for subsequent requests

    This allows the mobile app to authenticate once and use the token
    for all future requests without storing the password.
    """
    try:
        # Verify password by attempting to create database connection
        db = DiaryDatabase(password=request.password)

        if not db.verify_password():
            raise HTTPException(status_code=401, detail="Incorrect password")

        # Create JWT token valid for 30 days
        token = create_access_token(request.password)

        return token

    except MobileAuthError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> DiaryDatabase:
    """
    Dependency to verify JWT token and return authenticated database connection

    This is used by all mobile endpoints to ensure authentication.
    """
    token = credentials.credentials
    password_hash = verify_token(token)

    if password_hash is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Note: We need to reconstruct the password from the hash for database access
    # This is a limitation - in production, consider using session-based auth
    # For now, store password hash in app_state during token verification

    # Check if we have an active database connection
    if not app_state.get("unlocked") or not app_state.get("db"):
        raise HTTPException(status_code=401, detail="Session expired - please login again")

    return app_state["db"]


@app.post("/api/mobile/sync", response_model=MobileSyncResponse)
async def mobile_sync(
    request: MobileSyncRequest,
    db: DiaryDatabase = Depends(get_current_user)
):
    """
    Bidirectional sync endpoint for mobile app

    - Uploads pending entries from mobile
    - Downloads new/updated entries since last_sync
    - Handles conflicts with server-wins strategy

    This is the core of the mobile sync system.
    """
    try:
        server_timestamp = datetime.now().isoformat()
        new_entries = []
        updated_entries = []
        deleted_entry_ids = []
        sync_conflicts = []

        # Process pending entries from mobile (upload)
        if request.pending_entries:
            emotion_detector = app_state.get("emotion_detector")
            pattern_analyzer = app_state.get("pattern_analyzer")
            rag = app_state.get("rag")

            for entry_data in request.pending_entries:
                try:
                    content = entry_data.get("content", "")
                    timestamp_str = entry_data.get("timestamp")
                    mobile_id = entry_data.get("mobile_id")  # Temporary ID from mobile

                    # Parse timestamp
                    if timestamp_str:
                        entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        entry_time = datetime.now()

                    # Create entry in database
                    entry_id = db.add_entry(
                        content=content,
                        image_path=None,  # Images handled separately
                        timestamp=entry_time
                    )

                    # Detect emotions if available
                    if emotion_detector:
                        emotions = emotion_detector.detect_emotions(content)
                        db.add_mood(entry_id, emotions)

                    # Extract patterns if available
                    if pattern_analyzer:
                        projects = pattern_analyzer.extract_projects(content)
                        for project in projects:
                            db.link_project_to_entry(entry_id, project["name"], project["type"])

                        media = pattern_analyzer.extract_media(content)
                        for item in media:
                            db.add_media_mention(entry_id, item["type"], item["title"])

                    # Add to RAG if available
                    if rag and emotion_detector:
                        emotions = emotion_detector.detect_emotions(content)
                        mood_metadata = {f"mood_{emotion}": score for emotion, score in emotions.items()}
                        rag.add_entry(
                            entry_id=entry_id,
                            content=content,
                            timestamp=entry_time,
                            metadata=mood_metadata
                        )

                    # Return server ID for mobile to map
                    new_entries.append({
                        "server_id": entry_id,
                        "mobile_id": mobile_id,
                        "synced": True
                    })

                except Exception as e:
                    print(f"Error syncing entry: {e}")
                    sync_conflicts.append({
                        "mobile_id": entry_data.get("mobile_id"),
                        "error": str(e),
                        "action": "retry"
                    })

        # Fetch new entries from server (download)
        if request.last_sync:
            try:
                last_sync_dt = datetime.fromisoformat(request.last_sync.replace('Z', '+00:00'))

                # Get entries modified since last sync
                # For now, return all recent entries (can be optimized with timestamp tracking)
                recent_entries = db.get_recent_entries(limit=100)

                for entry in recent_entries:
                    entry_dt = datetime.fromisoformat(entry["timestamp"])
                    if entry_dt > last_sync_dt:
                        updated_entries.append(entry)

            except Exception as e:
                print(f"Error fetching updates: {e}")

        return MobileSyncResponse(
            success=True,
            new_entries=new_entries,
            updated_entries=updated_entries,
            deleted_entry_ids=deleted_entry_ids,
            server_timestamp=server_timestamp,
            sync_conflicts=sync_conflicts
        )

    except Exception as e:
        print(f"Sync error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.get("/api/mobile/entries/recent")
async def mobile_get_recent_entries(
    limit: int = 20,
    offset: int = 0,
    db: DiaryDatabase = Depends(get_current_user)
):
    """
    Get recent entries for mobile app (optimized payload)

    Returns compressed data suitable for mobile bandwidth.
    """
    try:
        entries = db.get_recent_entries(limit=limit)

        # Compress response for mobile
        mobile_entries = []
        for entry in entries:
            mobile_entries.append({
                "id": entry["id"],
                "content": entry["content"][:200] + "..." if len(entry["content"]) > 200 else entry["content"],
                "timestamp": entry["timestamp"],
                "moods": entry.get("moods", {}),
                "has_image": entry.get("image_path") is not None
            })

        return {
            "entries": mobile_entries,
            "count": len(mobile_entries)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mobile/insights/summary")
async def mobile_get_insights_summary(
    days: int = 7,
    db: DiaryDatabase = Depends(get_current_user)
):
    """
    Get compressed insights summary for mobile dashboard

    Returns lightweight analytics data optimized for mobile.
    """
    try:
        temporal = app_state.get("temporal")

        if not temporal:
            return {
                "mood_today": {},
                "streak": 0,
                "top_projects": [],
                "quick_insight": "Keep journaling to discover patterns!"
            }

        # Get quick mood summary
        recent_entries = db.get_recent_entries(limit=5)
        mood_totals = {}

        if recent_entries:
            from collections import defaultdict
            mood_counts = defaultdict(list)

            for entry in recent_entries:
                if entry.get("moods"):
                    for emotion, score in entry["moods"].items():
                        mood_counts[emotion].append(score)

            mood_totals = {
                emotion: sum(scores) / len(scores)
                for emotion, scores in mood_counts.items()
            }

        # Get top emotion
        top_emotion = max(mood_totals.items(), key=lambda x: x[1])[0] if mood_totals else "neutral"

        # Get active projects
        projects = db.get_active_projects()
        top_projects = [p["name"] for p in projects[:3]]

        # Get writing streak
        analytics = app_state.get("analytics")
        streak = 0
        if analytics:
            streak_data = analytics.get_writing_streak()
            streak = streak_data.get("current_streak", 0)

        return {
            "mood_today": mood_totals,
            "top_emotion": top_emotion,
            "streak": streak,
            "top_projects": top_projects,
            "quick_insight": f"You've been feeling {top_emotion} lately. Keep it up! 🌟"
        }

    except Exception as e:
        print(f"Error getting mobile insights: {e}")
        return {
            "mood_today": {},
            "streak": 0,
            "top_projects": [],
            "quick_insight": "Keep journaling!"
        }


# === Entry Endpoints ===

@app.post("/api/entries")
async def create_entry(
    content: str = Form(...),
    timestamp: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """Create a new diary entry"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        db: DiaryDatabase = app_state["db"]
        emotion_detector = app_state["emotion_detector"]
        rag = app_state["rag"]
        pattern_analyzer = app_state["pattern_analyzer"]

        # Parse timestamp (handle ISO format with 'Z' timezone)
        if timestamp:
            # Replace 'Z' with '+00:00' for ISO format compatibility
            timestamp_clean = timestamp.replace('Z', '+00:00')
            try:
                entry_time = datetime.fromisoformat(timestamp_clean)
            except ValueError:
                # Fallback to current time if parsing fails
                entry_time = datetime.now()
        else:
            entry_time = datetime.now()

        # Save image if provided
        image_path = None
        if image:
            # Save to uploads directory
            uploads_dir = Path(__file__).parent.parent / "uploads"
            uploads_dir.mkdir(exist_ok=True)

            image_filename = f"{int(entry_time.timestamp())}_{image.filename}"
            image_path = uploads_dir / image_filename

            with open(image_path, "wb") as f:
                f.write(await image.read())

        # Create entry in database
        entry_id = db.add_entry(
            content=content,
            image_path=str(image_path) if image_path else None,
            timestamp=entry_time
        )

        # Detect emotions
        emotions = emotion_detector.detect_emotions(content)
        db.add_mood(entry_id, emotions)

        # Extract patterns
        projects = pattern_analyzer.extract_projects(content)
        for project in projects:
            db.link_project_to_entry(entry_id, project["name"], project["type"])

        media = pattern_analyzer.extract_media(content)
        for item in media:
            db.add_media_mention(entry_id, item["type"], item["title"])

        # Add to RAG vector database
        # ChromaDB only accepts flat metadata, so convert moods to separate fields
        mood_metadata = {f"mood_{emotion}": score for emotion, score in emotions.items()}
        rag.add_entry(
            entry_id=entry_id,
            content=content,
            timestamp=entry_time,
            metadata=mood_metadata
        )

        return {
            "success": True,
            "entry_id": entry_id,
            "emotions": emotions,
            "projects": [p["name"] for p in projects]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entries")
async def get_entries(limit: int = 10, offset: int = 0):
    """Get recent diary entries"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    entries = db.get_recent_entries(limit=limit)

    return {
        "entries": entries
    }


@app.get("/api/entries/{entry_id}")
async def get_entry(entry_id: int):
    """Get specific entry by ID"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    entry = db.get_entry(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    return entry


@app.delete("/api/entries/{entry_id}")
async def delete_entry(entry_id: int):
    """Delete an entry"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        db: DiaryDatabase = app_state["db"]
        rag = app_state["rag"]

        # Delete from database (cascades to moods, projects, etc.)
        entry = db.get_entry(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        # Delete from vector database
        rag.delete_entry(entry_id)

        # Delete from SQLite
        db.delete_entry(entry_id)

        return {"success": True, "message": "Entry deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/entries/{entry_id}")
async def update_entry(
    entry_id: int,
    content: str = Form(...),
    timestamp: Optional[str] = Form(None)
):
    """Update an existing entry"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        db: DiaryDatabase = app_state["db"]
        emotion_detector = app_state["emotion_detector"]
        rag = app_state["rag"]
        pattern_analyzer = app_state["pattern_analyzer"]

        # Check if entry exists
        entry = db.get_entry(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        # Parse timestamp if provided
        entry_time = None
        if timestamp:
            timestamp_clean = timestamp.replace('Z', '+00:00')
            try:
                entry_time = datetime.fromisoformat(timestamp_clean)
            except ValueError:
                pass

        # Update entry in database
        db.update_entry(entry_id, content, entry_time)

        # Re-detect emotions
        emotions = emotion_detector.detect_emotions(content)
        # Delete old moods
        with db.get_connection() as conn:
            conn.execute("DELETE FROM moods WHERE entry_id = ?", (entry_id,))
        # Add new moods
        db.add_mood(entry_id, emotions)

        # Re-extract patterns
        # Delete old project mentions
        with db.get_connection() as conn:
            conn.execute("DELETE FROM project_mentions WHERE entry_id = ?", (entry_id,))
            conn.execute("DELETE FROM media_mentions WHERE entry_id = ?", (entry_id,))

        projects = pattern_analyzer.extract_projects(content)
        for project in projects:
            db.link_project_to_entry(entry_id, project["name"], project["type"])

        media = pattern_analyzer.extract_media(content)
        for item in media:
            db.add_media_mention(entry_id, item["type"], item["title"])

        # Update in RAG vector database
        mood_metadata = {f"mood_{emotion}": score for emotion, score in emotions.items()}
        rag.update_entry(
            entry_id=entry_id,
            content=content,
            timestamp=entry_time or datetime.fromisoformat(entry["timestamp"]),
            metadata=mood_metadata
        )

        return {
            "success": True,
            "entry_id": entry_id,
            "emotions": emotions,
            "projects": [p["name"] for p in projects]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === AI Chat Endpoints ===

class ChatSessionRequest(BaseModel):
    session_id: Optional[int] = None
    message: str

@app.post("/api/chat")
async def chat(request: ChatSessionRequest):
    """Chat with AI about entries"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    qwen = app_state.get("qwen")
    if not qwen:
        # Provide a helpful fallback response when AI isn't loaded
        return {
            "response": "The AI model is not currently loaded. This could be because:\n\n"
                       "1. The model files are incompatible with llama-cpp-python\n"
                       "2. You need to download a different GGUF format\n"
                       "3. The model requires GPU acceleration\n\n"
                       "You can still use DiaryML for journaling, mood tracking, and pattern analysis. "
                       "The AI chat feature will be available once the model loads successfully.\n\n"
                       "Try downloading a smaller quantized model (q4_k_m) if the current one doesn't work.",
            "mood_context": {}
        }

    try:
        db: DiaryDatabase = app_state["db"]
        rag = app_state["rag"]

        # Get or create chat session
        session_id = request.session_id
        if not session_id:
            # Create new session
            session_id = db.create_chat_session()

        # Save user message
        db.add_chat_message(session_id, "user", request.message)

        # Get current mood context
        recent_entries = db.get_recent_entries(limit=5)
        recent_moods = []
        for entry in recent_entries:
            if entry.get("moods"):
                recent_moods.extend(entry["moods"].items())

        # Average recent mood
        mood_context = {}
        if recent_moods:
            from collections import defaultdict
            mood_totals = defaultdict(list)
            for emotion, score in recent_moods:
                mood_totals[emotion].append(score)

            mood_context = {
                emotion: sum(scores) / len(scores)
                for emotion, scores in mood_totals.items()
            }

        # Get relevant past context via RAG (reduced to 1 to save tokens)
        past_context = rag.get_contextual_entries(request.message, n_results=1)

        # Generate AI response (max_tokens auto-detected based on message complexity)
        try:
            response = qwen.generate_response(
                user_message=request.message,
                mood_context=mood_context,
                past_context=past_context,
                max_tokens=None  # Auto-detect optimal length
            )
        except Exception as model_error:
            print(f"Error generating AI response: {model_error}")
            import traceback
            traceback.print_exc()
            # Return a helpful error message
            response = f"I encountered an error generating a response. This might be due to:\n\n" \
                      f"- The model running out of context memory\n- An incompatibility with the message format\n\n" \
                      f"Error: {str(model_error)}\n\n" \
                      f"Try asking a shorter question or restarting the server."

        # Save assistant response
        db.add_chat_message(session_id, "assistant", response)

        return {
            "response": response,
            "session_id": session_id,
            "mood_context": mood_context
        }

    except Exception as e:
        print(f"Chat endpoint error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# === Chat Session Management Endpoints ===

@app.get("/api/chat/sessions")
async def get_chat_sessions():
    """Get all chat sessions"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    sessions = db.get_chat_sessions()

    return {"sessions": sessions}


@app.post("/api/chat/sessions")
async def create_new_chat_session():
    """Create a new chat session"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    session_id = db.create_chat_session()

    return {"session_id": session_id, "message": "New chat session created"}


@app.get("/api/chat/sessions/{session_id}")
async def get_chat_session_messages(session_id: int):
    """Get messages from a specific chat session"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    messages = db.get_chat_messages(session_id)

    return {"messages": messages}


@app.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(session_id: int):
    """Delete a chat session"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    db.delete_chat_session(session_id)

    return {"success": True, "message": "Chat session deleted"}


@app.post("/api/chat/sessions/{session_id}/clear")
async def clear_chat_session(session_id: int):
    """Clear all messages in a chat session"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    db.clear_chat_messages(session_id)

    return {"success": True, "message": "Chat cleared"}


# === Daily Greeting Endpoint ===

@app.get("/api/daily-greeting")
async def get_daily_greeting():
    """Get personalized daily greeting and suggestions"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        db: DiaryDatabase = app_state["db"]
        recommender = app_state["recommender"]
        qwen = app_state.get("qwen")

        # Get active projects
        active_projects = db.get_active_projects()
        project_names = [p["name"] for p in active_projects[:3]]

        # Get recent mood
        recent_entries = db.get_recent_entries(limit=5)
        mood_scores = {}

        if recent_entries:
            from collections import defaultdict
            mood_totals = defaultdict(list)

            for entry in recent_entries:
                if entry.get("moods"):
                    for emotion, score in entry["moods"].items():
                        mood_totals[emotion].append(score)

            mood_scores = {
                emotion: sum(scores) / len(scores)
                for emotion, scores in mood_totals.items()
            }

        # Get mood pattern description
        pattern_analyzer = app_state["pattern_analyzer"]
        mood_pattern = "steady"

        if len(recent_entries) >= 3:
            analysis = pattern_analyzer.analyze_mood_patterns(recent_entries)
            mood_pattern = analysis.get("trend", "steady")

        # Generate suggestions
        suggestions_data = recommender.generate_daily_suggestions(
            db=db,
            active_projects=project_names,
            mood_state=mood_scores,
            recent_activities=[]
        )

        # Combine suggestions for Qwen
        all_suggestions = []
        all_suggestions.extend(suggestions_data.get("projects", []))
        all_suggestions.extend(suggestions_data.get("creative", []))
        all_suggestions.extend(suggestions_data.get("media", []))

        # Generate AI greeting if available
        greeting = suggestions_data.get("greeting", "Good morning!")

        if qwen:
            try:
                greeting = qwen.generate_daily_greeting(
                    recent_projects=project_names,
                    mood_pattern=mood_pattern,
                    suggestions=all_suggestions
                )
            except Exception as e:
                print(f"Error generating AI greeting: {e}")
        else:
            # Add a note about AI when it's not loaded
            if not project_names:
                greeting = "Good morning! Start capturing your thoughts and creative journey."
            else:
                greeting = f"Good morning! Ready to continue working on {project_names[0]}?"

        return {
            "greeting": greeting,
            "suggestions": suggestions_data,
            "mood_state": mood_scores,
            "active_projects": project_names
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Analytics Endpoints ===

@app.get("/api/analytics/mood-timeline")
async def get_mood_timeline(days: int = 30):
    """Get mood trends over time"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    timeline = db.get_mood_timeline(days=days)

    return {
        "timeline": timeline
    }


@app.get("/api/analytics/projects")
async def get_projects():
    """Get all projects and their status"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    db: DiaryDatabase = app_state["db"]
    projects = db.get_active_projects()

    return {
        "projects": projects
    }


# === Search Endpoint ===

@app.get("/api/search")
async def search_entries(
    q: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    emotions: Optional[str] = None,
    limit: int = 50
):
    """
    Search diary entries with filters

    Args:
        q: Text search query
        start_date: ISO format date string (start of range)
        end_date: ISO format date string (end of range)
        emotions: Comma-separated list of emotions (e.g., "joy,love")
        limit: Maximum number of results
    """
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        db: DiaryDatabase = app_state["db"]

        # Parse date filters
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                pass

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                pass

        # Parse emotion filters
        emotion_list = None
        if emotions:
            emotion_list = [e.strip() for e in emotions.split(',') if e.strip()]

        # Search entries
        results = db.search_entries(
            query=q,
            start_date=start_dt,
            end_date=end_dt,
            emotions=emotion_list,
            limit=limit
        )

        return {
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Deep Analytics Endpoints ===

@app.get("/api/analytics/comprehensive")
async def get_comprehensive_analytics():
    """Get all analytics insights in one call"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    analytics: DeepAnalytics = app_state["analytics"]
    return analytics.get_comprehensive_insights()


@app.get("/api/analytics/streak")
async def get_writing_streak():
    """Get writing streak information"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    analytics: DeepAnalytics = app_state["analytics"]
    return analytics.get_writing_streak()


@app.get("/api/analytics/productivity")
async def get_productivity_score():
    """Get creative productivity score"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    analytics: DeepAnalytics = app_state["analytics"]
    return analytics.get_creative_productivity_score()


@app.get("/api/analytics/temporal-moods")
async def get_temporal_mood_patterns(days: int = 30):
    """Get mood patterns over time"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    analytics: DeepAnalytics = app_state["analytics"]
    return analytics.analyze_temporal_mood_patterns(days=days)


# === Temporal Intelligence Endpoints ===

@app.get("/api/insights/mood-cycles")
async def get_mood_cycles(days: int = 90):
    """
    Discover mood cycles and patterns

    Analyzes mood data to find:
    - Best and worst days of the week
    - Time-of-day patterns (morning/afternoon/evening/night)
    - Volatile emotions (high variance)
    - Mood streaks (3+ consecutive similar days)
    """
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        temporal: TemporalIntelligence = app_state["temporal"]
        cycles = temporal.detect_mood_cycles(days=days)
        return cycles
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/project-momentum")
async def get_project_momentum(days: int = 90):
    """
    Track project momentum and detect stalled/accelerating projects

    Analyzes project mentions to classify:
    - Stalled projects (declining activity)
    - Accelerating projects (increasing activity)
    - Consistent projects (steady activity)
    - Common stall patterns (e.g., "projects die after 10 days")
    """
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        temporal: TemporalIntelligence = app_state["temporal"]
        momentum = temporal.track_project_momentum(days=days)
        return momentum
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/emotional-triggers")
async def get_emotional_triggers(days: int = 90):
    """
    Find emotional triggers - keywords correlated with specific emotions

    Identifies:
    - Positive triggers: words/topics associated with joy, love
    - Negative triggers: words/topics associated with sadness, anger, fear
    - Neutral topics
    """
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        temporal: TemporalIntelligence = app_state["temporal"]
        triggers = temporal.find_emotional_triggers(days=days)
        return triggers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Model Management Endpoints ===

@app.get("/api/models/list")
async def list_available_models():
    """List all GGUF models in the models directory"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    models_dir = Path(__file__).parent.parent / "models"
    models_dir.mkdir(exist_ok=True)

    models = []
    for model_file in models_dir.glob("*.gguf"):
        # Skip mmproj files
        if "mmproj" in model_file.name.lower():
            continue

        size_mb = model_file.stat().st_size / (1024 * 1024)

        models.append({
            "filename": model_file.name,
            "size_mb": round(size_mb, 2),
            "path": str(model_file)
        })

    # Sort by size (smaller first for CPU performance)
    models.sort(key=lambda x: x["size_mb"])

    # Get currently loaded model
    current_model = None
    qwen = app_state.get("qwen")
    if qwen and hasattr(qwen, 'model_info'):
        current_model = {
            "name": qwen.model_info.get("name", "unknown"),
            "filename": qwen.model_info.get("filename", "unknown"),
            "size": qwen.model_info.get("size", "unknown"),
            "quantization": qwen.model_info.get("quantization", "unknown"),
            "is_thinking": qwen.is_thinking_model,
            "has_vision": qwen.has_vision
        }

    return {
        "models": models,
        "current_model": current_model
    }


@app.post("/api/models/switch")
async def switch_model(model_filename: str = Form(...)):
    """Switch to a different model (supports both text-only and vision-language models)"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        models_dir = Path(__file__).parent.parent / "models"
        model_path = models_dir / model_filename

        if not model_path.exists():
            raise HTTPException(status_code=404, detail="Model file not found")

        # Import here to avoid circular imports
        from qwen_interface import QwenInterface

        # Load new model
        print(f"Switching to model: {model_filename}")

        # Explicitly pass mmproj_path - the QwenInterface will auto-detect if it's a vision model
        # For text-only models, it will not attempt to load mmproj
        new_qwen = QwenInterface(model_path=model_path, mmproj_path=None)

        # Save this as the preferred model for next startup
        new_qwen.save_model_preference()

        # Replace in app state
        app_state["qwen"] = new_qwen

        return {
            "success": True,
            "message": f"Successfully switched to {model_filename}",
            "model_info": {
                "name": new_qwen.model_info.get("name", model_filename),
                "filename": new_qwen.model_info.get("filename", model_filename),
                "size": new_qwen.model_info.get("size", "unknown"),
                "quantization": new_qwen.model_info.get("quantization", "unknown"),
                "context_window": new_qwen._get_recommended_context(),
                "is_thinking": new_qwen.is_thinking_model,
                "has_vision": new_qwen.has_vision
            }
        }

    except Exception as e:
        print(f"Error switching model: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to switch model: {str(e)}")


# === Backup & Restore Endpoints ===

@app.get("/api/backup")
async def create_backup():
    """Create a backup of the diary (database, vector store, and uploads)"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        base_dir = Path(__file__).parent.parent

        # Create a zip file in memory
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add diary.db
            db_path = base_dir / "diary.db"
            if db_path.exists():
                zip_file.write(db_path, "diary.db")

            # Add chroma_db directory
            chroma_dir = base_dir / "chroma_db"
            if chroma_dir.exists():
                for file_path in chroma_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(base_dir))
                        zip_file.write(file_path, arcname)

            # Add uploads directory
            uploads_dir = base_dir / "uploads"
            if uploads_dir.exists():
                for file_path in uploads_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(base_dir))
                        zip_file.write(file_path, arcname)

        # Reset buffer position
        zip_buffer.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"DiaryML_Backup_{timestamp}.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@app.post("/api/restore")
async def restore_backup(file: UploadFile = File(...)):
    """Restore a diary backup from a zip file"""
    if not app_state["unlocked"]:
        raise HTTPException(status_code=401, detail="Diary is locked")

    try:
        base_dir = Path(__file__).parent.parent

        # Read the uploaded zip file
        zip_data = await file.read()

        # Extract to a temporary location
        with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zip_file:
            # Verify it's a valid backup
            if 'diary.db' not in zip_file.namelist():
                raise HTTPException(status_code=400, detail="Invalid backup file: diary.db not found")

            # Create backup of current data before restoring
            backup_dir = base_dir / "backup_before_restore"
            backup_dir.mkdir(exist_ok=True)

            # Backup current diary.db
            current_db = base_dir / "diary.db"
            if current_db.exists():
                shutil.copy(current_db, backup_dir / "diary.db")

            # Backup current chroma_db
            current_chroma = base_dir / "chroma_db"
            if current_chroma.exists():
                backup_chroma = backup_dir / "chroma_db"
                if backup_chroma.exists():
                    shutil.rmtree(backup_chroma)
                shutil.copytree(current_chroma, backup_chroma)

            # Extract the backup
            zip_file.extractall(base_dir)

        return {
            "success": True,
            "message": "Backup restored successfully. Please restart the server."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")


# === Static Files ===

# Serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    async def serve_frontend():
        """Serve the main frontend page"""
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "DiaryML API is running"}


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("DiaryML - Your Private Creative Companion")
    print("=" * 60)
    print("\nStarting server...")
    print("Open http://localhost:8000 in your browser\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",  #127.0.0.1
        port=8000,
        reload=False,
        log_level="info"
    )
