"""작업 앱 설정 계약.
목적/책임: 작업 원장(Job), 시도 이력(JobAttempt), Outbox 및 자동화 정책(AutomationPolicy) 모델을 등록한다.
입력/출력: Django 앱 설정.
신뢰 경계/권한: 내부 코어 서비스 앱.
상태 변경/부작용: jobs 모델을 Django ORM 레지스트리에 등록.
실패/타임아웃/재시도: 해당 없음.
핵심 불변조건: 중복 등록 방지.
관련 요구사항/테스트/설계 문서: docs/server-migration/19-automation-and-provider-contract.md, 17-domain-and-postgresql-contract.md.
"""
from django.apps import AppConfig


class JobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bid_server.jobs"
    verbose_name = "작업 원장 및 실행 관리"
