"""
Authentication system for the feedback agent.

This module provides simple session-based authentication suitable for
the capstone project. It distinguishes between STUDENT and TEACHER roles.

For a production system, you would use:
- OAuth2/JWT tokens
- Secure password hashing (bcrypt)
- Multi-factor authentication
- Session expiration
- CSRF protection
"""

import uuid
import logging
from enum import Enum
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles in the system."""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


@dataclass
class User:
    """User model with authentication information."""
    user_id: str
    name: str
    email: str
    role: UserRole
    created_at: datetime

    def is_student(self) -> bool:
        """Check if user is a student."""
        return self.role == UserRole.STUDENT

    def is_teacher(self) -> bool:
        """Check if user is a teacher."""
        return self.role == UserRole.TEACHER

    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.role == UserRole.ADMIN

    def can_view_student_data(self, student_id: str) -> bool:
        """
        Check if user can view a specific student's data.

        Rules:
        - Students can only view their own data
        - Teachers can view all students' data
        - Admins can view all students' data
        """
        if self.is_teacher() or self.is_admin():
            return True
        if self.is_student() and self.user_id == student_id:
            return True
        return False

    def can_view_class_statistics(self) -> bool:
        """Check if user can view class-wide statistics."""
        return self.is_teacher() or self.is_admin()


@dataclass
class Session:
    """Session model for tracking authenticated users."""
    session_id: str
    user: User
    created_at: datetime
    expires_at: datetime

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now() > self.expires_at

    def is_valid(self) -> bool:
        """Check if session is valid (not expired)."""
        return not self.is_expired()


class AuthenticationService:
    """
    Simple authentication service for the feedback system.

    For capstone demonstration purposes, this uses in-memory storage.
    In production, you would use:
    - Database-backed session storage
    - Redis for session caching
    - JWT tokens for stateless authentication
    """

    def __init__(self, session_duration_hours: int = 24):
        """
        Initialize the authentication service.

        Args:
            session_duration_hours: How long sessions remain valid
        """
        self.sessions: Dict[str, Session] = {}
        self.users: Dict[str, User] = {}  # user_id -> User
        self.session_duration = timedelta(hours=session_duration_hours)

        logger.info(f"AuthenticationService initialized (session duration: {session_duration_hours}h)")

    def register_user(
        self,
        name: str,
        email: str,
        role: UserRole,
        user_id: Optional[str] = None
    ) -> User:
        """
        Register a new user in the system.

        Args:
            name: User's full name
            email: User's email address
            role: User's role (STUDENT, TEACHER, ADMIN)
            user_id: Optional user ID (generated if not provided)

        Returns:
            Created User object
        """
        if user_id is None:
            user_id = str(uuid.uuid4())

        # Check if user already exists
        if user_id in self.users:
            logger.warning(f"User {user_id} already exists")
            return self.users[user_id]

        user = User(
            user_id=user_id,
            name=name,
            email=email,
            role=role,
            created_at=datetime.now()
        )

        self.users[user_id] = user
        logger.info(f"Registered {role.value}: {name} ({user_id})")

        return user

    def create_session(self, user_id: str) -> Optional[Session]:
        """
        Create a new session for a user.

        Args:
            user_id: ID of the user to create session for

        Returns:
            Created Session object, or None if user not found
        """
        user = self.users.get(user_id)
        if not user:
            logger.error(f"Cannot create session: user {user_id} not found")
            return None

        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            user=user,
            created_at=datetime.now(),
            expires_at=datetime.now() + self.session_duration
        )

        self.sessions[session_id] = session
        logger.info(f"Created session {session_id} for user {user_id}")

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID to look up

        Returns:
            Session object if found and valid, None otherwise
        """
        session = self.sessions.get(session_id)

        if not session:
            logger.warning(f"Session {session_id} not found")
            return None

        if session.is_expired():
            logger.warning(f"Session {session_id} has expired")
            # Clean up expired session
            del self.sessions[session_id]
            return None

        return session

    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        return self.users.get(user_id)

    def logout(self, session_id: str) -> bool:
        """
        Logout a user by invalidating their session.

        Args:
            session_id: Session ID to invalidate

        Returns:
            True if session was found and deleted, False otherwise
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Session {session_id} logged out")
            return True
        return False

    def get_user_from_session(self, session_id: str) -> Optional[User]:
        """
        Get the user associated with a session.

        Args:
            session_id: Session ID to look up

        Returns:
            User object if session is valid, None otherwise
        """
        session = self.get_session(session_id)
        if session:
            return session.user
        return None

    def cleanup_expired_sessions(self):
        """Remove all expired sessions."""
        expired_sessions = [
            sid for sid, session in self.sessions.items()
            if session.is_expired()
        ]

        for session_id in expired_sessions:
            del self.sessions[session_id]

        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")


# Global authentication service instance
auth_service = AuthenticationService()


# Convenience functions for quick setup
def create_demo_users():
    """
    Create demo users for testing and demonstration.

    Returns:
        Dictionary mapping role names to user IDs
    """
    # Create a teacher
    teacher = auth_service.register_user(
        name="Ms. Sarah Johnson",
        email="sarah.johnson@school.edu",
        role=UserRole.TEACHER
    )

    # Create students
    student1 = auth_service.register_user(
        name="Alice Smith",
        email="alice.smith@student.edu",
        role=UserRole.STUDENT
    )

    student2 = auth_service.register_user(
        name="Bob Chen",
        email="bob.chen@student.edu",
        role=UserRole.STUDENT
    )

    student3 = auth_service.register_user(
        name="Carol Martinez",
        email="carol.martinez@student.edu",
        role=UserRole.STUDENT
    )

    logger.info("Created demo users: 1 teacher, 3 students")

    return {
        "teacher": teacher.user_id,
        "student1": student1.user_id,
        "student2": student2.user_id,
        "student3": student3.user_id
    }
