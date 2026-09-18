from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from client.storage.database import Base


@dataclass
class FriendRequestData:
    request_id: str = ""
    requester_id: str = ""
    addressee_id: str = ""
    username: str = ""
    name: str = ""
    email: str = ""
    status: str = "pending"
    direction: str = ""
    created_at: Any = None
    updated_at: Any = None

    def __post_init__(self) -> None:
        if not self.request_id:
            self.request_id = str(self.created_at or "")
        if not self.name:
            self.name = self.username

    @property
    def id(self) -> str:
        return self.request_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.request_id,
            "request_id": self.request_id,
            "requester_id": self.requester_id,
            "addressee_id": self.addressee_id,
            "username": self.username,
            "name": self.name,
            "email": self.email,
            "status": self.status,
            "direction": self.direction,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class FriendData:
    id: str = ""
    name: str = ""
    email: str = ""
    status: str = "offline"
    friend_id: str = ""
    user_id: str = ""
    username: str = ""
    nickname: str | None = None
    added_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.friend_id
        if not self.friend_id:
            self.friend_id = self.id

    @property
    def display_name(self) -> str:
        return self.name or self.username or self.nickname or self.id

    @property
    def is_online(self) -> bool:
        return self.status == "online"

    @property
    def online(self) -> bool:
        return self.is_online

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "friend_id": self.friend_id,
            "user_id": self.user_id,
            "username": self.username,
            "name": self.name,
            "email": self.email,
            "status": self.status,
            "nickname": self.nickname,
            "added_at": self.added_at,
        }

    def __getitem__(self, key: str) -> object:
        return getattr(self, key)

    def get(self, key: str, default: object = None) -> object:
        return getattr(self, key, default)


class UserLocal(Base):
    __tablename__ = "users_local"

    id = Column(String(255), primary_key=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    avatar_path = Column(String(512), nullable=True)
    theme = Column(String(32), nullable=False, default="dark")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    msg_id = Column(String(64), nullable=False, index=True)
    sender_id = Column(String(255), nullable=False, index=True)
    receiver_id = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    encrypted = Column(Boolean, nullable=False, default=False)
    read = Column(Boolean, nullable=False, default=False)
    delivered = Column(Boolean, nullable=False, default=False)


class Friend(Base):
    __tablename__ = "friends"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    friend_id = Column(String(255), nullable=False, index=True)
    nickname = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="offline")
    added_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="uq_user_friend"),)


class Settings(Base):
    __tablename__ = "settings"

    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=True)


class KeyPair(Base):
    __tablename__ = "key_pairs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    private_key = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
