"""작업 URL 라우팅 계약.
목적: /api/v1/jobs 하위 엔드포인트 URL 패턴을 정의한다.
관련: docs/server-migration/18-screen-api-contract.md §50-51.
"""
from django.urls import path
from . import views

urlpatterns = [
    path("jobs", views.JobListAPIView.as_view(), name="job_list"),
    path("jobs/<uuid:job_id>", views.JobDetailAPIView.as_view(), name="job_detail"),
    path("jobs/<uuid:job_id>/cancel", views.JobCancelAPIView.as_view(), name="job_cancel"),
    path("jobs/<uuid:job_id>/retry", views.JobRetryAPIView.as_view(), name="job_retry"),
]
