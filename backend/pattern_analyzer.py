"""
Pattern analyzer for DiaryML
Extracts projects, activities, and temporal patterns from journal entries
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter


class PatternAnalyzer:
    """Analyze patterns in journal entries"""

    # Regex patterns for different mention types
    PATTERNS = {
        "started": r"(?:start|started|began|beginning|initiated)\s+(?:working on |project |)\s*([A-Z][A-Za-z0-9\s-]+)",
        "finished": r"(?:finish|finished|completed|done with|wrapped up)\s+(?:working on |project |)\s*([A-Z][A-Za-z0-9\s-]+)",
        "working_on": r"(?:working on|continue|continuing)\s+(?:project |)\s*([A-Z][A-Za-z0-9\s-]+)",
        "project_mention": r"(?:project|Project)\s+([A-Z][A-Za-z0-9\s-]+)",

        # Media mentions
        "watched": r"(?:watched|saw|viewing)\s+['\"]?([^'\",.!?]+)['\"]?",
        "read": r"(?:read|reading)\s+['\"]?([^'\",.!?]+)['\"]?",
        "listened": r"(?:listened to|listening to|heard)\s+['\"]?([^'\",.!?]+)['\"]?",

        # Activities
        "activity": r"(?:went to|visited|attended)\s+([A-Za-z0-9\s-]+)",
    }

    def __init__(self):
        """Initialize pattern analyzer"""
        pass

    def extract_projects(self, text: str) -> List[Dict[str, str]]:
        """
        Extract project mentions with their type

        Returns:
            List of {"name": project_name, "type": mention_type}
        """
        projects = []

        for mention_type, pattern in self.PATTERNS.items():
            if mention_type in ["watched", "read", "listened", "activity"]:
                continue

            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                project_name = match.group(1).strip()

                # Clean up the project name
                project_name = self._clean_project_name(project_name)

                if project_name and len(project_name) > 2:
                    projects.append({
                        "name": project_name,
                        "type": mention_type
                    })

        return projects

    def extract_media(self, text: str) -> List[Dict[str, str]]:
        """
        Extract media mentions (movies, books, music)

        Returns:
            List of {"title": title, "type": media_type}
        """
        media = []

        media_patterns = {
            "movie": "watched",
            "book": "read",
            "music": "listened"
        }

        for media_type, pattern_key in media_patterns.items():
            pattern = self.PATTERNS[pattern_key]
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                title = match.group(1).strip()

                # Clean up title
                title = self._clean_title(title)

                if title and len(title) > 2:
                    media.append({
                        "title": title,
                        "type": media_type
                    })

        return media

    def extract_activities(self, text: str) -> List[str]:
        """Extract activities and events"""
        activities = []

        pattern = self.PATTERNS["activity"]
        matches = re.finditer(pattern, text, re.IGNORECASE)

        for match in matches:
            activity = match.group(1).strip()
            if activity and len(activity) > 2:
                activities.append(activity)

        return activities

    def analyze_project_timeline(
        self,
        project_mentions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze project progression over time

        Args:
            project_mentions: List of mentions with timestamp and type

        Returns:
            Analysis of project status and progression
        """
        if not project_mentions:
            return {"status": "unknown", "timeline": []}

        # Sort by timestamp
        sorted_mentions = sorted(project_mentions, key=lambda x: x.get("timestamp", datetime.min))

        # Determine current status
        latest_mention = sorted_mentions[-1]
        mention_type = latest_mention.get("type", "project_mention")

        if mention_type == "finished":
            status = "completed"
        elif mention_type == "started":
            status = "active"
        elif mention_type == "working_on":
            status = "active"
        else:
            status = "mentioned"

        # Calculate duration if project has start and end
        duration_days = None
        start_date = None
        end_date = None

        for mention in sorted_mentions:
            if mention.get("type") == "started" and not start_date:
                start_date = mention.get("timestamp")
            if mention.get("type") == "finished" and not end_date:
                end_date = mention.get("timestamp")

        if start_date and end_date:
            duration_days = (end_date - start_date).days

        return {
            "status": status,
            "first_mentioned": sorted_mentions[0].get("timestamp"),
            "last_mentioned": sorted_mentions[-1].get("timestamp"),
            "total_mentions": len(sorted_mentions),
            "duration_days": duration_days,
            "timeline": [
                {
                    "date": m.get("timestamp"),
                    "type": m.get("type"),
                    "entry_id": m.get("entry_id")
                }
                for m in sorted_mentions
            ]
        }

    def analyze_mood_patterns(
        self,
        mood_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze mood patterns and trends

        Args:
            mood_history: List of mood entries with date and emotions

        Returns:
            Mood pattern analysis
        """
        if not mood_history:
            return {"dominant_moods": [], "trend": "neutral"}

        # Count emotions
        emotion_counts = Counter()
        emotion_scores = defaultdict(list)

        for entry in mood_history:
            moods = entry.get("moods", {})
            for emotion, score in moods.items():
                emotion_counts[emotion] += 1
                emotion_scores[emotion].append(score)

        # Get dominant moods
        dominant_moods = [
            {
                "emotion": emotion,
                "frequency": count,
                "avg_intensity": sum(emotion_scores[emotion]) / len(emotion_scores[emotion])
            }
            for emotion, count in emotion_counts.most_common(3)
        ]

        # Analyze trend (recent vs earlier)
        trend = self._calculate_mood_trend(mood_history)

        return {
            "dominant_moods": dominant_moods,
            "trend": trend,
            "total_entries": len(mood_history)
        }

    def suggest_next_steps(
        self,
        active_projects: List[str],
        recent_activities: List[str],
        mood_state: str
    ) -> List[str]:
        """
        Generate suggestions for what to do next

        Args:
            active_projects: List of active project names
            recent_activities: Recent activities/interests
            mood_state: Current mood state

        Returns:
            List of suggestion strings
        """
        suggestions = []

        # Project-based suggestions
        if active_projects:
            project = active_projects[0]
            suggestions.append(f"Continue working on {project}")

            if len(active_projects) > 1:
                suggestions.append(f"Switch focus to {active_projects[1]}")

        # Mood-based suggestions
        if mood_state in ["joy", "excitement"]:
            suggestions.extend([
                "Channel this energy into creative work",
                "Start a new project while you're feeling inspired"
            ])
        elif mood_state in ["sadness", "melancholy"]:
            suggestions.extend([
                "Take time for reflection and journaling",
                "Watch a comforting movie or listen to calming music"
            ])
        elif mood_state in ["calm", "neutral"]:
            suggestions.extend([
                "Perfect time to tackle complex tasks",
                "Organize and plan upcoming projects"
            ])

        # Activity-based suggestions
        if recent_activities:
            suggestions.append(f"Explore more related to {recent_activities[0]}")

        # General creative suggestions
        suggestions.extend([
            "Capture your current mood through art",
            "Free-write for 10 minutes",
            "Take a walk and observe your surroundings"
        ])

        return suggestions[:5]  # Return top 5

    def _clean_project_name(self, name: str) -> str:
        """Clean and normalize project name"""
        # Remove common words
        stop_words = {"the", "a", "an", "my", "this", "that", "on", "in"}

        words = name.split()
        cleaned_words = [w for w in words if w.lower() not in stop_words]

        cleaned = " ".join(cleaned_words)

        # Remove trailing punctuation
        cleaned = re.sub(r'[,;:.!?]+$', '', cleaned)

        return cleaned.strip()

    def _clean_title(self, title: str) -> str:
        """Clean media title"""
        # Remove trailing words that aren't part of title
        title = re.sub(r'\s+(?:yesterday|today|tonight|last night|earlier).*$', '', title, flags=re.IGNORECASE)

        # Remove punctuation
        title = re.sub(r'[,;:.!?]+$', '', title)

        return title.strip()

    def _calculate_mood_trend(self, mood_history: List[Dict[str, Any]]) -> str:
        """Calculate if mood is trending up, down, or stable"""
        if len(mood_history) < 2:
            return "neutral"

        # Split into recent and earlier halves
        midpoint = len(mood_history) // 2
        earlier_moods = mood_history[:midpoint]
        recent_moods = mood_history[midpoint:]

        # Calculate average positivity scores
        def calc_positivity(entries):
            scores = []
            for entry in entries:
                moods = entry.get("moods", {})
                positive = moods.get("joy", 0) + moods.get("love", 0)
                negative = moods.get("sadness", 0) + moods.get("anger", 0) + moods.get("fear", 0)
                scores.append(positive - negative)

            return sum(scores) / len(scores) if scores else 0

        earlier_avg = calc_positivity(earlier_moods)
        recent_avg = calc_positivity(recent_moods)

        diff = recent_avg - earlier_avg

        if diff > 0.15:
            return "improving"
        elif diff < -0.15:
            return "declining"
        else:
            return "stable"


# Singleton
_pattern_analyzer: Optional[PatternAnalyzer] = None


def get_pattern_analyzer() -> PatternAnalyzer:
    """Get or create pattern analyzer singleton"""
    global _pattern_analyzer
    if _pattern_analyzer is None:
        _pattern_analyzer = PatternAnalyzer()
    return _pattern_analyzer
