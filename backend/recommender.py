"""
Recommendation engine for DiaryML
Suggests activities, projects, and media based on patterns and mood
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import Counter
import random


class Recommender:
    """Generate personalized recommendations"""

    def __init__(self):
        """Initialize recommender"""
        pass

    def generate_daily_suggestions(
        self,
        db,
        active_projects: List[str],
        mood_state: Dict[str, float],
        recent_activities: List[str]
    ) -> Dict[str, Any]:
        """
        Generate personalized daily suggestions

        Args:
            db: Database instance
            active_projects: List of active project names
            mood_state: Current/recent mood scores
            recent_activities: Recent activities from entries

        Returns:
            Dict with categorized suggestions
        """
        suggestions = {
            "greeting": self._generate_greeting(mood_state),
            "projects": self._suggest_projects(active_projects),
            "creative": self._suggest_creative_activities(mood_state),
            "media": self._suggest_media(db, mood_state),
            "wellness": self._suggest_wellness(mood_state)
        }

        return suggestions

    def _generate_greeting(self, mood_state: Dict[str, float]) -> str:
        """Generate personalized morning greeting"""
        greetings = {
            "joy": [
                "Good morning! You're radiating positive energy today.",
                "Morning! Looks like you're in great spirits.",
                "Hey there! That creative spark is shining bright today."
            ],
            "sadness": [
                "Good morning. Take it easy on yourself today.",
                "Morning. Remember, it's okay to move at your own pace.",
                "Hey. Today's a good day for gentle reflection."
            ],
            "neutral": [
                "Good morning! Ready to see what today brings?",
                "Morning! A fresh day, a fresh canvas.",
                "Hey there! Let's make today count."
            ],
            "calm": [
                "Good morning. Perfect energy for deep work today.",
                "Morning! Clear mind, clear path ahead.",
                "Hey. Great energy for focused creativity today."
            ]
        }

        # Determine dominant mood category
        if not mood_state:
            mood_category = "neutral"
        else:
            dominant_emotion = max(mood_state.items(), key=lambda x: x[1])[0]

            if dominant_emotion in ["joy", "love", "excitement"]:
                mood_category = "joy"
            elif dominant_emotion in ["sadness", "melancholy", "fear"]:
                mood_category = "sadness"
            elif dominant_emotion in ["calm", "peaceful"]:
                mood_category = "calm"
            else:
                mood_category = "neutral"

        return random.choice(greetings.get(mood_category, greetings["neutral"]))

    def _suggest_projects(self, active_projects: List[str]) -> List[str]:
        """Suggest project-related actions"""
        if not active_projects:
            return ["Start a new creative project that excites you"]

        suggestions = []

        # Primary project
        suggestions.append(f"Continue working on {active_projects[0]}")

        # Alternative projects
        if len(active_projects) > 1:
            suggestions.append(f"Switch to {active_projects[1]} for fresh perspective")

        if len(active_projects) > 2:
            suggestions.append(f"Review progress across all {len(active_projects)} active projects")

        # General project suggestions
        suggestions.append("Wrap up one project before starting something new")

        return suggestions[:3]

    def _suggest_creative_activities(self, mood_state: Dict[str, float]) -> List[str]:
        """Suggest creative activities based on mood"""
        activities = {
            "high_energy": [
                "Start a bold new piece - your energy is perfect for it",
                "Experiment with a technique you've been curious about",
                "Work on something ambitious and challenging"
            ],
            "low_energy": [
                "Sketch or doodle - let your mind wander",
                "Organize your creative workspace",
                "Browse inspiration and save ideas for later"
            ],
            "emotional": [
                "Channel these feelings into your art",
                "Free-write about what you're feeling right now",
                "Create something raw and honest"
            ],
            "calm": [
                "Perfect time for detailed, focused work",
                "Refine something you've been working on",
                "Plan out your next creative project"
            ]
        }

        # Determine energy/emotional state
        if not mood_state:
            category = "calm"
        else:
            intensity = max(mood_state.values())
            dominant = max(mood_state.items(), key=lambda x: x[1])[0]

            if intensity > 0.7:
                if dominant in ["sadness", "anger", "fear"]:
                    category = "emotional"
                else:
                    category = "high_energy"
            elif intensity < 0.3:
                category = "low_energy"
            else:
                category = "calm"

        return random.sample(activities[category], min(2, len(activities[category])))

    def _suggest_media(self, db, mood_state: Dict[str, float]) -> List[str]:
        """Suggest media (movies, books, music) based on history and mood"""
        # Get media history
        media_history = db.get_media_history(limit=100)

        if not media_history:
            return self._default_media_suggestions(mood_state)

        # Analyze preferences
        media_by_type = {}
        for item in media_history:
            media_type = item.get("media_type", "movie")
            if media_type not in media_by_type:
                media_by_type[media_type] = []
            media_by_type[media_type].append(item)

        suggestions = []

        # Movie suggestions
        if "movie" in media_by_type:
            suggestions.append(self._suggest_similar_media(media_by_type["movie"], mood_state, "movie"))

        # Book suggestions
        if "book" in media_by_type:
            suggestions.append(self._suggest_similar_media(media_by_type["book"], mood_state, "book"))

        # Music suggestions
        if "music" in media_by_type:
            suggestions.append(self._suggest_similar_media(media_by_type["music"], mood_state, "music"))

        # Fill with defaults if needed
        while len(suggestions) < 2:
            suggestions.extend(self._default_media_suggestions(mood_state))

        return suggestions[:3]

    def _suggest_similar_media(
        self,
        media_history: List[Dict],
        mood_state: Dict[str, float],
        media_type: str
    ) -> str:
        """Suggest similar media based on history"""
        # Get positively received media
        positive_media = [
            m for m in media_history
            if m.get("sentiment") in ["positive", "love", None]
        ]

        if positive_media:
            # Pick a recent favorite
            recent = positive_media[:5]
            favorite = random.choice(recent)
            return f"Watch/read/listen to something similar to {favorite.get('title')}"

        return f"Explore new {media_type}s that match your current mood"

    def _default_media_suggestions(self, mood_state: Dict[str, float]) -> List[str]:
        """Default media suggestions when no history available"""
        suggestions = {
            "joy": [
                "Watch an uplifting film that inspires creativity",
                "Listen to energizing music while you work"
            ],
            "sadness": [
                "Watch a comforting favorite film",
                "Listen to calming, reflective music"
            ],
            "neutral": [
                "Explore a documentary on a topic you're curious about",
                "Try a new genre of music for fresh inspiration"
            ]
        }

        dominant = "neutral"
        if mood_state:
            dominant_emotion = max(mood_state.items(), key=lambda x: x[1])[0]
            if dominant_emotion in ["joy", "love"]:
                dominant = "joy"
            elif dominant_emotion in ["sadness", "fear"]:
                dominant = "sadness"

        return suggestions.get(dominant, suggestions["neutral"])

    def _suggest_wellness(self, mood_state: Dict[str, float]) -> List[str]:
        """Suggest wellness activities"""
        wellness = {
            "high_stress": [
                "Take a short walk to clear your mind",
                "Do some gentle stretching or movement",
                "Practice 5 minutes of deep breathing"
            ],
            "low_energy": [
                "Take a power nap if you need it",
                "Get some fresh air and natural light",
                "Hydrate and have a healthy snack"
            ],
            "balanced": [
                "Maintain your creative momentum",
                "Take regular breaks to stay fresh",
                "Check in with yourself throughout the day"
            ]
        }

        if not mood_state:
            category = "balanced"
        else:
            negative_emotions = sum([
                mood_state.get("sadness", 0),
                mood_state.get("anger", 0),
                mood_state.get("fear", 0)
            ])

            intensity = max(mood_state.values())

            if negative_emotions > 0.5 or intensity > 0.8:
                category = "high_stress"
            elif intensity < 0.3:
                category = "low_energy"
            else:
                category = "balanced"

        return [random.choice(wellness[category])]

    def suggest_next_project(
        self,
        completed_projects: List[str],
        interests: List[str]
    ) -> List[str]:
        """Suggest ideas for next project"""
        suggestions = [
            "Revisit an old idea with fresh perspective",
            "Combine two interests into something new",
            "Challenge yourself with an unfamiliar medium or technique",
            "Create a series based on a single theme or concept",
            "Collaborate or share your work with others"
        ]

        # Personalize based on interests
        if interests:
            interest = random.choice(interests)
            suggestions.insert(0, f"Explore {interest} more deeply through your art")

        return suggestions[:3]


# Singleton
_recommender: Optional[Recommender] = None


def get_recommender() -> Recommender:
    """Get or create recommender singleton"""
    global _recommender
    if _recommender is None:
        _recommender = Recommender()
    return _recommender
