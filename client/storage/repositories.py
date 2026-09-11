from __future__ import annotations

from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy import select, delete, update, func as sql_func
from sqlalchemy.orm import Session
from client.storage.database import get_session
from client.storage.models import (
    UserLocal,
    Message,
    Friend,
    Settings,
    KeyPair,
)

ModelType = TypeVar("ModelType", bound=Any)


class BaseRepository(Generic[ModelType]):
    model: Type[ModelType]

    def save(self, entity: ModelType) -> ModelType:
        with get_session() as session:
            session.add(entity)
            session.commit()
            session.refresh(entity)
            return entity

    def delete(self, entity: ModelType) -> None:
        with get_session() as session:
            session.delete(entity)
            session.commit()

    def get_by_id(self, id: int) -> Optional[ModelType]:
        with get_session() as session:
            return session.get(self.model, id)

    def get_all(self) -> List[ModelType]:
        with get_session() as session:
            result = session.execute(select(self.model))
            return list(result.scalars().all())


class UserRepository(BaseRepository[UserLocal]):
    model = UserLocal

    def get_by_email(self, email: str) -> Optional[UserLocal]:
        with get_session() as session:
            result = session.execute(
                select(self.model).where(self.model.email == email)
            )
            return result.scalar_one_or_none()

    def get_current(self) -> Optional[UserLocal]:
        with get_session() as session:
            result = session.execute(select(self.model).limit(1))
            return result.scalar_one_or_none()

    def save_current(self, user: UserLocal) -> UserLocal:
        return self.save(user)

    def clear_current(self) -> None:
        with get_session() as session:
            session.execute(delete(self.model))
            session.commit()


class MessageRepository(BaseRepository[Message]):
    model = Message

    def save_message(self, msg: Message) -> Message:
        return self.save(msg)

    def get_conversation(
        self, user_id: str, friend_id: str, limit: int = 50
    ) -> List[Message]:
        with get_session() as session:
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

    def get_last_message(self, friend_id: str) -> Optional[Message]:
        with get_session() as session:
            result = session.execute(
                select(self.model)
                .where(self.model.receiver_id == friend_id)
                .order_by(self.model.timestamp.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    def mark_as_read(self, msg_id: int) -> None:
        with get_session() as session:
            session.execute(
                update(self.model).where(self.model.id == msg_id).values(read=True)
            )
            session.commit()

    def get_unread_count(self, friend_id: str) -> int:
        with get_session() as session:
            result = session.execute(
                select(sql_func.count(self.model.id))
                .where(
                    (self.model.receiver_id == friend_id) & (self.model.read == False)
                )
            )
            return result.scalar_one() or 0


class FriendRepository(BaseRepository[Friend]):
    model = Friend

    def add_friend(self, user_id: str, friend_id: str, nickname: Optional[str] = None) -> Friend:
        friend = Friend(user_id=user_id, friend_id=friend_id, nickname=nickname)
        return self.save(friend)

    def remove_friend(self, user_id: str, friend_id: str) -> None:
        with get_session() as session:
            session.execute(
                delete(self.model).where(
                    (self.model.user_id == user_id) & (self.model.friend_id == friend_id)
                )
            )
            session.commit()

    def get_friends(self, user_id: str) -> List[Friend]:
        with get_session() as session:
            result = session.execute(
                select(self.model).where(self.model.user_id == user_id)
            )
            return list(result.scalars().all())

    def get_friend(self, user_id: str, friend_id: str) -> Optional[Friend]:
        with get_session() as session:
            result = session.execute(
                select(self.model).where(
                    (self.model.user_id == user_id) & (self.model.friend_id == friend_id)
                )
            )
            return result.scalar_one_or_none()


class SettingsRepository:
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with get_session() as session:
            result = session.execute(
                select(Settings).where(Settings.key == key)
            )
            setting = result.scalar_one_or_none()
            return setting.value if setting else default

    def set(self, key: str, value: str) -> None:
        with get_session() as session:
            existing = session.execute(
                select(Settings).where(Settings.key == key)
            ).scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                session.add(Settings(key=key, value=value))
            session.commit()

    def get_all(self) -> dict[str, str]:
        with get_session() as session:
            result = session.execute(select(Settings))
            return {row.key: row.value for row in result.scalars().all()}
