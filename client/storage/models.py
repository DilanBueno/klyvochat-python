from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from client.storage.database import Base


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
    added_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="uq_user_friend"),
    )


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
