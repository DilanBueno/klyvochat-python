from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy import func as sql_func

from client.storage.database import get_session
from client.storage.models import (
    Friend,
    KeyPair,
    Message,
    Settings,
    UserLocal,
)

ModelType = TypeVar("ModelType", bound=Any)

SessionFactory = Callable[[], AbstractContextManager[Any]]


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session_factory: SessionFactory | None = None) -> None:
        self._session_factory = session_factory or get_session

    def save(self, entity: ModelType) -> ModelType:
        with self._session_factory() as session:
            session.add(entity)
            session.commit()
            session.refresh(entity)
            return entity

    def delete(self, entity: ModelType) -> None:
        with self._session_factory() as session:
            session.delete(entity)
            session.commit()

    def get_by_id(self, id: int) -> ModelType | None:
        with self._session_factory() as session:
            return session.get(self.model, id)

    def get_all(self) -> list[ModelType]:
        with self._session_factory() as session:
            result = session.execute(select(self.model))
            return list(result.scalars().all())


class UserRepository(BaseRepository[UserLocal]):
    model = UserLocal

    def get_by_email(self, email: str) -> UserLocal | None:
        with self._session_factory() as session:
            result = session.execute(select(self.model).where(self.model.email == email))
            return result.scalar_one_or_none()

    def get_current(self) -> UserLocal | None:
        with self._session_factory() as session:
            result = session.execute(select(self.model).limit(1))
            return result.scalar_one_or_none()

    def save_current(self, user: UserLocal) -> UserLocal:
        return self.save(user)

    def update_display_name(self, user_id: str, display_name: str) -> UserLocal | None:
        with self._session_factory() as session:
            user = session.get(self.model, str(user_id))
            if user is not None:
                user.display_name = display_name
                session.commit()
                return user
            return None

    def clear_current(self) -> None:
        with self._session_factory() as session:
            session.execute(delete(self.model))
            session.commit()


class MessageRepository(BaseRepository[Message]):
    model = Message

    def save_message(self, msg: Message) -> Message:
        return self.save(msg)

    def get_by_msg_id(self, msg_id: str) -> Message | None:
        with self._session_factory() as session:
            result = session.execute(select(self.model).where(self.model.msg_id == str(msg_id)))
            return result.scalar_one_or_none()

    def get_conversation(self, user_id: str, friend_id: str, limit: int = 50) -> list[Message]:
        with self._session_factory() as session:
            result = session.execute(
                select(self.model)
                .where(
                    ((self.model.sender_id == user_id) & (self.model.receiver_id == friend_id))
                    | ((self.model.sender_id == friend_id) & (self.model.receiver_id == user_id))
                )
                .order_by(self.model.timestamp.desc())
                .limit(limit)
            )
            return list(reversed(result.scalars().all()))

    def get_last_conversation_message(self, user_id: str, friend_id: str) -> Message | None:
        with self._session_factory() as session:
            result = session.execute(
                select(self.model)
                .where(
                    ((self.model.sender_id == user_id) & (self.model.receiver_id == friend_id))
                    | ((self.model.sender_id == friend_id) & (self.model.receiver_id == user_id))
                )
                .order_by(self.model.timestamp.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    def mark_as_read(self, msg_id: int) -> None:
        with self._session_factory() as session:
            session.execute(update(self.model).where(self.model.id == msg_id).values(read=True))
            session.commit()

    def mark_delivered(self, msg_id: str) -> None:
        with self._session_factory() as session:
            session.execute(
                update(self.model).where(self.model.msg_id == str(msg_id)).values(delivered=True)
            )
            session.commit()

    def mark_read_by_msg_ids(self, msg_ids: list[str]) -> None:
        ids = [str(msg_id) for msg_id in msg_ids]
        if not ids:
            return
        with self._session_factory() as session:
            session.execute(update(self.model).where(self.model.msg_id.in_(ids)).values(read=True))
            session.commit()

    def get_unread_count(self, user_id: str, friend_id: str) -> int:
        with self._session_factory() as session:
            result = session.execute(
                select(sql_func.count(self.model.id)).where(
                    (self.model.sender_id == str(friend_id))
                    & (self.model.receiver_id == str(user_id))
                    & (self.model.read.is_(False))
                )
            )
            return result.scalar_one() or 0

    def get_total_unread(self, user_id: str) -> int:
        with self._session_factory() as session:
            result = session.execute(
                select(sql_func.count(self.model.id)).where(
                    (self.model.receiver_id == str(user_id)) & (self.model.read.is_(False))
                )
            )
            return result.scalar_one() or 0

    def get_unread_from_friend(self, user_id: str, friend_id: str) -> list[Message]:
        with self._session_factory() as session:
            result = session.execute(
                select(self.model).where(
                    (self.model.sender_id == str(friend_id))
                    & (self.model.receiver_id == str(user_id))
                    & (self.model.read.is_(False))
                )
            )
            return list(result.scalars().all())

    def get_undelivered(self, user_id: str) -> list[Message]:
        with self._session_factory() as session:
            result = session.execute(
                select(self.model)
                .where((self.model.sender_id == str(user_id)) & (self.model.delivered.is_(False)))
                .order_by(self.model.timestamp.asc())
            )
            return list(result.scalars().all())

    def delete_conversation(self, user_id: str, friend_id: str) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(self.model).where(
                    ((self.model.sender_id == user_id) & (self.model.receiver_id == friend_id))
                    | ((self.model.sender_id == friend_id) & (self.model.receiver_id == user_id))
                )
            )
            session.commit()

    def clear_conversation(self, user_id: str, friend_id: str) -> None:
        self.delete_conversation(user_id, friend_id)

    def delete_older_than(self, cutoff: datetime) -> int:
        with self._session_factory() as session:
            result = session.execute(delete(self.model).where(self.model.timestamp < cutoff))
            session.commit()
            return result.rowcount or 0


class FriendRepository(BaseRepository[Friend]):
    model = Friend

    def upsert_friend(
        self,
        user_id: str,
        friend_id: str,
        nickname: str | None = None,
        username: str | None = None,
        email: str | None = None,
        status: str | None = None,
    ) -> Friend:
        with self._session_factory() as session:
            friend = session.execute(
                select(self.model).where(
                    (self.model.user_id == user_id) & (self.model.friend_id == friend_id)
                )
            ).scalar_one_or_none()
            if friend is None:
                friend = self.model(
                    user_id=user_id,
                    friend_id=friend_id,
                    nickname=nickname,
                    username=username,
                    email=email,
                    status=status or "offline",
                )
                session.add(friend)
            else:
                if nickname is not None:
                    friend.nickname = nickname
                if username is not None:
                    friend.username = username
                if email is not None:
                    friend.email = email
                if status is not None:
                    friend.status = status
            session.commit()
            if hasattr(session, "refresh"):
                session.refresh(friend)
            return friend

    def add_friend(self, user_id: str, friend_id: str, nickname: str | None = None) -> Friend:
        return self.upsert_friend(user_id, friend_id, nickname=nickname)

    def remove_friend(self, user_id: str, friend_id: str) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(self.model).where(
                    (self.model.user_id == user_id) & (self.model.friend_id == friend_id)
                )
            )
            session.commit()

    def get_friends(self, user_id: str) -> list[Friend]:
        with self._session_factory() as session:
            result = session.execute(select(self.model).where(self.model.user_id == user_id))
            return list(result.scalars().all())

    def get_friend(self, user_id: str, friend_id: str) -> Friend | None:
        with self._session_factory() as session:
            result = session.execute(
                select(self.model).where(
                    (self.model.user_id == user_id) & (self.model.friend_id == friend_id)
                )
            )
            return result.scalar_one_or_none()


class SettingsRepository:
    def __init__(self, session_factory: SessionFactory | None = None) -> None:
        self._session_factory = session_factory or get_session

    def get(self, key: str, default: str | None = None) -> str | None:
        with self._session_factory() as session:
            result = session.execute(select(Settings).where(Settings.key == key))
            setting = result.scalar_one_or_none()
            return setting.value if setting else default

    def set(self, key: str, value: str) -> None:
        with self._session_factory() as session:
            existing = session.execute(
                select(Settings).where(Settings.key == key)
            ).scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                session.add(Settings(key=key, value=value))
            session.commit()

    def get_all(self) -> dict[str, str]:
        with self._session_factory() as session:
            result = session.execute(select(Settings))
            return {row.key: row.value for row in result.scalars().all()}


class KeyPairRepository(BaseRepository[KeyPair]):
    model = KeyPair

    def get_for_user(self, user_id: str) -> KeyPair | None:
        with self._session_factory() as session:
            result = session.execute(
                select(self.model)
                .where(self.model.user_id == str(user_id))
                .order_by(self.model.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    def save_keypair(self, keypair: KeyPair) -> KeyPair:
        return self.save(keypair)

    def delete_for_user(self, user_id: str) -> None:
        with self._session_factory() as session:
            session.execute(delete(self.model).where(self.model.user_id == str(user_id)))
            session.commit()
