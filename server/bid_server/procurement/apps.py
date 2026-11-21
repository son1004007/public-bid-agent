"""앱 설정 계약.

목적/책임: 조달 공고, 문서 버전, 구조화 추출 및 레거시 식별자 도메인 앱을 등록한다.
입력/출력: Django 앱 설정.
신뢰 경계/권한: 내부 도메인 앱.
상태 변경/부작용: procurement 모델을 Django ORM 레지스트리에 등록.
실패/타임아웃/재시도: 해당 없음.
핵심 불변조건: 중복 등록 방지.
관련 요구사항/테스트/설계 문서: docs/server-migration/17-domain-and-postgresql-contract.md
"""
from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bid_server.procurement"
    verbose_name = "조달 공고 및 문서 관리"
