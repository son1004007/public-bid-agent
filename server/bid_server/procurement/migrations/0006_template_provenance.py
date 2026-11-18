from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("procurement", "0005_document_version_access")]
    operations = [
        migrations.AlterField(
            model_name="proposalrevision", name="status",
            field=models.CharField(max_length=30, default="AI_DRAFT", choices=[
                ("AI_DRAFT", "AI 초안"), ("TEMPLATE_DRAFT", "미검증 템플릿 초안"),
                ("EDITED", "사용자 편집"), ("REVIEWED", "검토 완료"), ("APPROVED", "승인 완료"),
            ]),
        ),
        migrations.AlterField(
            model_name="proposalrevision", name="provenance",
            field=models.CharField(max_length=30, default="AI_DRAFT", choices=[
                ("AI_DRAFT", "AI 자동 생성"), ("TEMPLATE", "정적 템플릿"), ("HUMAN", "사용자 수동 작성"),
            ]),
        ),
    ]
