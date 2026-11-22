from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    ActionLog,
    EmailAccount,
    EmailMessage,
    EmailDraft,
    Reminder,
    Note,
    SystemAlert,
    ApplicationShortcut,
    Setting,
    AuditLog,
    ActionStatus,
    AssistantStatus,
    EmailProvider,
    AIProviderType,
)


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        ai_provider: AIProviderType,
        model_used: str,
        tokens_used: Optional[int] = None,
    ) -> Conversation:
        conversation = Conversation(
            session_id=session_id,
            user_message=user_message,
            assistant_response=assistant_response,
            ai_provider=ai_provider,
            model_used=model_used,
            tokens_used=tokens_used,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_by_session(self, session_id: str, limit: int = 50) -> Sequence[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.session_id == session_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 100) -> Sequence[Conversation]:
        stmt = select(Conversation).order_by(desc(Conversation.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ActionLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        action_type: str,
        action_params: str,
        conversation_id: Optional[int] = None,
        requires_confirmation: bool = False,
    ) -> ActionLog:
        action = ActionLog(
            conversation_id=conversation_id,
            action_type=action_type,
            action_params=action_params,
            status=ActionStatus.PENDING,
            requires_confirmation=requires_confirmation,
        )
        self.session.add(action)
        await self.session.flush()
        return action

    async def update_status(
        self,
        action_id: int,
        status: ActionStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
        confirmed: bool = False,
    ) -> Optional[ActionLog]:
        stmt = select(ActionLog).where(ActionLog.id == action_id)
        result_obj = await self.session.execute(stmt)
        action = result_obj.scalar_one_or_none()
        if action:
            action.status = status
            if result is not None:
                action.result = result
            if error is not None:
                action.error = error
            if confirmed:
                action.confirmed_by_user = True
            if status in (ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.CANCELLED):
                action.completed_at = datetime.utcnow()
            await self.session.flush()
        return action

    async def get_pending_confirmations(self) -> Sequence[ActionLog]:
        stmt = select(ActionLog).where(
            and_(
                ActionLog.status == ActionStatus.PENDING,
                ActionLog.requires_confirmation == True,
                ActionLog.confirmed_by_user == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 100) -> Sequence[ActionLog]:
        stmt = select(ActionLog).order_by(desc(ActionLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class EmailAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        provider: EmailProvider,
        email_address: str,
        display_name: Optional[str],
        access_token_encrypted: str,
        refresh_token_encrypted: Optional[str],
        token_expires_at: Optional[datetime],
        scopes: str,
    ) -> EmailAccount:
        account = EmailAccount(
            provider=provider,
            email_address=email_address,
            display_name=display_name,
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            token_expires_at=token_expires_at,
            scopes=scopes,
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def get_by_email(self, email_address: str) -> Optional[EmailAccount]:
        stmt = select(EmailAccount).where(EmailAccount.email_address == email_address)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(self) -> Sequence[EmailAccount]:
        stmt = select(EmailAccount).where(EmailAccount.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_tokens(
        self,
        account_id: int,
        access_token_encrypted: str,
        refresh_token_encrypted: Optional[str],
        token_expires_at: Optional[datetime],
    ) -> Optional[EmailAccount]:
        stmt = select(EmailAccount).where(EmailAccount.id == account_id)
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if account:
            account.access_token_encrypted = access_token_encrypted
            if refresh_token_encrypted:
                account.refresh_token_encrypted = refresh_token_encrypted
            account.token_expires_at = token_expires_at
            account.updated_at = datetime.utcnow()
            await self.session.flush()
        return account

    async def update_last_sync(self, account_id: int) -> Optional[EmailAccount]:
        stmt = select(EmailAccount).where(EmailAccount.id == account_id)
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if account:
            account.last_sync_at = datetime.utcnow()
            await self.session.flush()
        return account

    async def deactivate(self, account_id: int) -> bool:
        stmt = select(EmailAccount).where(EmailAccount.id == account_id)
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if account:
            account.is_active = False
            await self.session.flush()
            return True
        return False


class EmailMessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, message: EmailMessage) -> EmailMessage:
        stmt = select(EmailMessage).where(
            and_(
                EmailMessage.account_id == message.account_id,
                EmailMessage.message_id == message.message_id,
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.sender = message.sender
            existing.sender_email = message.sender_email
            existing.recipients = message.recipients
            existing.subject = message.subject
            existing.snippet = message.snippet
            existing.body_text = message.body_text
            existing.body_html = message.body_html
            existing.is_read = message.is_read
            existing.is_starred = message.is_starred
            existing.has_attachments = message.has_attachments
            existing.received_at = message.received_at
            await self.session.flush()
            return existing
        else:
            self.session.add(message)
            await self.session.flush()
            return message

    async def get_by_account(
        self,
        account_id: int,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        search_query: Optional[str] = None,
    ) -> Sequence[EmailMessage]:
        stmt = select(EmailMessage).where(EmailMessage.account_id == account_id)

        if unread_only:
            stmt = stmt.where(EmailMessage.is_read == False)

        if search_query:
            stmt = stmt.where(
                or_(
                    EmailMessage.subject.ilike(f"%{search_query}%"),
                    EmailMessage.sender.ilike(f"%{search_query}%"),
                    EmailMessage.snippet.ilike(f"%{search_query}%"),
                )
            )

        stmt = stmt.order_by(desc(EmailMessage.received_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_unread_count(self, account_id: int) -> int:
        stmt = select(func.count(EmailMessage.id)).where(
            and_(EmailMessage.account_id == account_id, EmailMessage.is_read == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def mark_as_read(self, message_id: int) -> bool:
        stmt = select(EmailMessage).where(EmailMessage.id == message_id)
        result = await self.session.execute(stmt)
        message = result.scalar_one_or_none()
        if message and not message.is_read:
            message.is_read = True
            await self.session.flush()
            return True
        return False


class EmailDraftRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        account_id: int,
        to_recipients: str,
        subject: str,
        body_text: str,
        cc_recipients: Optional[str] = None,
        bcc_recipients: Optional[str] = None,
        body_html: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
    ) -> EmailDraft:
        draft = EmailDraft(
            account_id=account_id,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            bcc_recipients=bcc_recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to_message_id=reply_to_message_id,
        )
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def get_pending(self, account_id: int) -> Sequence[EmailDraft]:
        stmt = (
            select(EmailDraft)
            .where(and_(EmailDraft.account_id == account_id, EmailDraft.is_sent == False))
            .order_by(desc(EmailDraft.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_sent(self, draft_id: int) -> Optional[EmailDraft]:
        stmt = select(EmailDraft).where(EmailDraft.id == draft_id)
        result = await self.session.execute(stmt)
        draft = result.scalar_one_or_none()
        if draft:
            draft.is_sent = True
            draft.sent_at = datetime.utcnow()
            await self.session.flush()
        return draft


class ReminderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        title: str,
        due_at: datetime,
        description: Optional[str] = None,
        is_recurring: bool = False,
        recurrence_rule: Optional[str] = None,
        notify_before_minutes: int = 0,
    ) -> Reminder:
        reminder = Reminder(
            title=title,
            description=description,
            due_at=due_at,
            is_recurring=is_recurring,
            recurrence_rule=recurrence_rule,
            notify_before_minutes=notify_before_minutes,
        )
        self.session.add(reminder)
        await self.session.flush()
        return reminder

    async def get_pending(self, before: Optional[datetime] = None) -> Sequence[Reminder]:
        stmt = select(Reminder).where(Reminder.is_completed == False)
        if before:
            stmt = stmt.where(Reminder.due_at <= before)
        stmt = stmt.order_by(Reminder.due_at)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all(self, include_completed: bool = False) -> Sequence[Reminder]:
        stmt = select(Reminder)
        if not include_completed:
            stmt = stmt.where(Reminder.is_completed == False)
        stmt = stmt.order_by(desc(Reminder.created_at))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def complete(self, reminder_id: int) -> Optional[Reminder]:
        stmt = select(Reminder).where(Reminder.id == reminder_id)
        result = await self.session.execute(stmt)
        reminder = result.scalar_one_or_none()
        if reminder and not reminder.is_completed:
            reminder.is_completed = True
            reminder.completed_at = datetime.utcnow()
            await self.session.flush()
        return reminder

    async def delete(self, reminder_id: int) -> bool:
        stmt = select(Reminder).where(Reminder.id == reminder_id)
        result = await self.session.execute(stmt)
        reminder = result.scalar_one_or_none()
        if reminder:
            await self.session.delete(reminder)
            await self.session.flush()
            return True
        return False


class NoteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, title: str, content: str, tags: Optional[str] = None) -> Note:
        note = Note(title=title, content=content, tags=tags)
        self.session.add(note)
        await self.session.flush()
        return note

    async def get_all(self, search_query: Optional[str] = None) -> Sequence[Note]:
        stmt = select(Note)
        if search_query:
            stmt = stmt.where(
                or_(
                    Note.title.ilike(f"%{search_query}%"),
                    Note.content.ilike(f"%{search_query}%"),
                    Note.tags.ilike(f"%{search_query}%"),
                )
            )
        stmt = stmt.order_by(desc(Note.updated_at))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, note_id: int, title: str, content: str, tags: Optional[str] = None) -> Optional[Note]:
        stmt = select(Note).where(Note.id == note_id)
        result = await self.session.execute(stmt)
        note = result.scalar_one_or_none()
        if note:
            note.title = title
            note.content = content
            note.tags = tags
            note.updated_at = datetime.utcnow()
            await self.session.flush()
        return note

    async def delete(self, note_id: int) -> bool:
        stmt = select(Note).where(Note.id == note_id)
        result = await self.session.execute(stmt)
        note = result.scalar_one_or_none()
        if note:
            await self.session.delete(note)
            await self.session.flush()
            return True
        return False


class SystemAlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        source: str,
        metric_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
    ) -> SystemAlert:
        alert = SystemAlert(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            source=source,
            metric_value=metric_value,
            threshold_value=threshold_value,
        )
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def get_unacknowledged(self) -> Sequence[SystemAlert]:
        stmt = (
            select(SystemAlert)
            .where(and_(SystemAlert.is_acknowledged == False, SystemAlert.is_resolved == False))
            .order_by(desc(SystemAlert.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 50) -> Sequence[SystemAlert]:
        stmt = select(SystemAlert).order_by(desc(SystemAlert.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def acknowledge(self, alert_id: int) -> Optional[SystemAlert]:
        stmt = select(SystemAlert).where(SystemAlert.id == alert_id)
        result = await self.session.execute(stmt)
        alert = result.scalar_one_or_none()
        if alert and not alert.is_acknowledged:
            alert.is_acknowledged = True
            alert.acknowledged_at = datetime.utcnow()
            await self.session.flush()
        return alert

    async def resolve(self, alert_id: int) -> Optional[SystemAlert]:
        stmt = select(SystemAlert).where(SystemAlert.id == alert_id)
        result = await self.session.execute(stmt)
        alert = result.scalar_one_or_none()
        if alert and not alert.is_resolved:
            alert.is_resolved = True
            alert.resolved_at = datetime.utcnow()
            await self.session.flush()
        return alert


class ApplicationShortcutRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        executable_path: str,
        arguments: Optional[str] = None,
        working_directory: Optional[str] = None,
        icon_path: Optional[str] = None,
        is_approved: bool = False,
    ) -> ApplicationShortcut:
        shortcut = ApplicationShortcut(
            name=name,
            executable_path=executable_path,
            arguments=arguments,
            working_directory=working_directory,
            icon_path=icon_path,
            is_approved=is_approved,
        )
        self.session.add(shortcut)
        await self.session.flush()
        return shortcut

    async def get_approved(self) -> Sequence[ApplicationShortcut]:
        stmt = select(ApplicationShortcut).where(ApplicationShortcut.is_approved == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all(self) -> Sequence[ApplicationShortcut]:
        stmt = select(ApplicationShortcut).order_by(ApplicationShortcut.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def record_launch(self, shortcut_id: int) -> Optional[ApplicationShortcut]:
        stmt = select(ApplicationShortcut).where(ApplicationShortcut.id == shortcut_id)
        result = await self.session.execute(stmt)
        shortcut = result.scalar_one_or_none()
        if shortcut:
            shortcut.launch_count += 1
            shortcut.last_launched_at = datetime.utcnow()
            await self.session.flush()
        return shortcut


class SettingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> Optional[str]:
        stmt = select(Setting).where(Setting.key == key)
        result = await self.session.execute(stmt)
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    async def set(self, key: str, value: str, description: Optional[str] = None, is_sensitive: bool = False) -> Setting:
        stmt = select(Setting).where(Setting.key == key)
        result = await self.session.execute(stmt)
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
            if description:
                setting.description = description
            setting.is_sensitive = is_sensitive
            setting.updated_at = datetime.utcnow()
        else:
            setting = Setting(key=key, value=value, description=description, is_sensitive=is_sensitive)
            self.session.add(setting)

        await self.session.flush()
        return setting

    async def get_all(self, include_sensitive: bool = False) -> Sequence[Setting]:
        stmt = select(Setting)
        if not include_sensitive:
            stmt = stmt.where(Setting.is_sensitive == False)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class AuditLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        event_type: str,
        user_action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        audit = AuditLog(
            event_type=event_type,
            user_action=user_action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )
        self.session.add(audit)
        await self.session.flush()
        return audit

    async def get_recent(self, limit: int = 100) -> Sequence[AuditLog]:
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()