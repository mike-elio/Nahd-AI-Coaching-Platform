from app.schemas.responses import DiagnosticResultModel


def test_diagnostic_result_model_keeps_expert_fields_but_not_display_only_fields():
    fields = set(DiagnosticResultModel.model_fields)

    assert {
        "expert_analysis",
        "diagnostic_trace",
        "evidence_plan",
        "command_plan",
        "hypothesis_details",
    } <= fields
    assert "display_result" not in fields
    assert "debug_diagnostics" not in fields
