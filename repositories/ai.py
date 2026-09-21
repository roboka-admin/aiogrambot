from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai import AIProviderConfig, AIProviderKind, AIProviderStatus, AIReport, AIReportKind
from models.ai_db import AIProviderRecord, AIReportRecord
from repositories.interfaces.ai import IAIProviderRepository, IAIReportRepository


class AIProviderRepository(IAIProviderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[AIProviderConfig]:
        result = await self._session.execute(
            select(AIProviderRecord).order_by(AIProviderRecord.priority, AIProviderRecord.key)
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def get(self, key: str) -> AIProviderConfig | None:
        record = await self._session.get(AIProviderRecord, key)
        return None if record is None else self._to_domain(record)

    async def upsert(self, provider: AIProviderConfig) -> AIProviderConfig:
        record = await self._session.get(AIProviderRecord, provider.key)
        if record is None:
            record = AIProviderRecord(key=provider.key, created_at=provider.created_at)
            self._session.add(record)

        record.display_name = provider.display_name
        record.kind = provider.kind.value
        record.base_url = provider.base_url
        record.model = provider.model
        record.api_key_env = provider.api_key_env
        record.enabled = provider.enabled
        record.priority = provider.priority
        record.status = provider.status.value
        record.cooldown_until = provider.cooldown_until
        record.daily_token_budget = provider.daily_token_budget
        record.tokens_in_total = provider.tokens_in_total
        record.tokens_out_total = provider.tokens_out_total
        record.tokens_today = provider.tokens_today
        record.tokens_today_date = provider.tokens_today_date
        record.last_error = provider.last_error
        record.last_used_at = provider.last_used_at
        record.updated_at = provider.updated_at
        await self._session.flush()
        return self._to_domain(record)

    async def delete(self, key: str) -> bool:
        result = await self._session.execute(
            delete(AIProviderRecord).where(AIProviderRecord.key == key)
        )
        return bool(result.rowcount)

    @staticmethod
    def _to_domain(record: AIProviderRecord) -> AIProviderConfig:
        return AIProviderConfig(
            key=record.key,
            display_name=record.display_name,
            kind=AIProviderKind(record.kind),
            base_url=record.base_url,
            model=record.model,
            api_key_env=record.api_key_env,
            enabled=record.enabled,
            priority=record.priority,
            status=AIProviderStatus(record.status),
            cooldown_until=record.cooldown_until,
            daily_token_budget=record.daily_token_budget,
            tokens_in_total=record.tokens_in_total,
            tokens_out_total=record.tokens_out_total,
            tokens_today=record.tokens_today,
            tokens_today_date=record.tokens_today_date,
            last_error=record.last_error,
            last_used_at=record.last_used_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class AIReportRepository(IAIReportRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, report: AIReport) -> AIReport:
        record = AIReportRecord(
            kind=report.kind.value,
            provider_key=report.provider_key,
            severity=report.severity,
            summary=report.summary,
            anomaly_keys=report.anomaly_keys,
            tokens_in=report.tokens_in,
            tokens_out=report.tokens_out,
            created_at=report.created_at,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def list_recent(self, *, offset: int, limit: int) -> list[AIReport]:
        result = await self._session.execute(
            select(AIReportRecord)
            .order_by(AIReportRecord.created_at.desc(), AIReportRecord.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(AIReportRecord))
        return result.scalar_one()

    async def get_latest(self, kind: str | None = None) -> AIReport | None:
        statement = select(AIReportRecord).order_by(
            AIReportRecord.created_at.desc(), AIReportRecord.id.desc()
        )
        if kind is not None:
            statement = statement.where(AIReportRecord.kind == kind)
        result = await self._session.execute(statement.limit(1))
        record = result.scalar_one_or_none()
        return None if record is None else self._to_domain(record)

    async def sum_tokens_since(self, since: datetime) -> tuple[int, int]:
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(AIReportRecord.tokens_in), 0),
                func.coalesce(func.sum(AIReportRecord.tokens_out), 0),
            ).where(AIReportRecord.created_at >= since)
        )
        tokens_in, tokens_out = result.one()
        return int(tokens_in), int(tokens_out)

    async def delete_before(self, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` reports older than ``cutoff``; returns rows removed."""
        result = await self._session.execute(
            delete(AIReportRecord)
            .where(AIReportRecord.created_at < cutoff)
            .with_dialect_options(mysql_limit=limit)
        )
        return int(result.rowcount or 0)

    @staticmethod
    def _to_domain(record: AIReportRecord) -> AIReport:
        return AIReport(
            id=record.id,
            kind=AIReportKind(record.kind),
            provider_key=record.provider_key,
            severity=record.severity,
            summary=record.summary,
            anomaly_keys=record.anomaly_keys,
            tokens_in=record.tokens_in,
            tokens_out=record.tokens_out,
            created_at=record.created_at,
        )
