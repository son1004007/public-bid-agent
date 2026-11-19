"""조달 공고 URL 라우팅 계약."""
from django.urls import path
from .cost_service import CostScenarioAPIView
from .views import (
    NoticeListAPIView,
    NoticeDetailAPIView,
    NoticeVersionsAPIView,
    DashboardAPIView,
    ProposalListAPIView,
    ProposalDetailAPIView,
    ProposalRevisionCreateAPIView,
    ProposalExportAPIView,
    StoredArtifactDownloadAPIView,
    DocumentExtractAPIView,
    DocumentStructureAPIView,
)

urlpatterns = [
    path("dashboard", DashboardAPIView.as_view(), name="procurement-dashboard"),
    path("notices", NoticeListAPIView.as_view(), name="notice-list"),
    path("notices/<uuid:notice_id>", NoticeDetailAPIView.as_view(), name="notice-detail"),
    path("notices/<uuid:notice_id>/versions", NoticeVersionsAPIView.as_view(), name="notice-versions"),
    path("notices/<uuid:notice_id>/cost-scenario", CostScenarioAPIView.as_view(), name="notice-cost-scenario"),
    path("proposals", ProposalListAPIView.as_view(), name="proposal-list"),
    path("proposals/<uuid:pk>", ProposalDetailAPIView.as_view(), name="proposal-detail"),
    path("proposals/<uuid:pk>/revisions", ProposalRevisionCreateAPIView.as_view(), name="proposal-revisions"),
    path("proposals/<uuid:pk>/export", ProposalExportAPIView.as_view(), name="proposal-export"),
    path("artifacts/<uuid:pk>/download", StoredArtifactDownloadAPIView.as_view(), name="artifact-download"),
    path("documents/<uuid:pk>/extract", DocumentExtractAPIView.as_view(), name="document-extract"),
    path("documents/<uuid:pk>/structures", DocumentStructureAPIView.as_view(), name="document-structures"),
]
